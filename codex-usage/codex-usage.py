#!/usr/bin/env python3
"""Fetch Codex usage limits as JSON without interactive work."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import select
import signal
import struct
import termios
import time
from dataclasses import dataclass
from typing import Optional

import fcntl
import pty

ANSI_ESCAPE_RE = re.compile(
    r"\x1b(?:[@-_][0-?]*[ -/]*[@-~]|\[[0-?]*[ -/]*[@-~]|\][^\x1b\x07]*\x07|\][^\x1b]*\x1b\\)"
)
LIMIT_LINE_RE = re.compile(
    r"^(?P<window>.+?)\s+limit:\s+(?P<bar>\[[^\]]*\])\s+(?P<percent>[0-9]+)%\s+left\s*\(resets (?P<resets>[^\)]*)\)$"
)
LIMIT_LINE_NO_RESET_RE = re.compile(
    r"^(?P<window>.+?)\s+limit:\s+(?P<bar>\[[^\]]*\])\s+(?P<percent>[0-9]+)%\s+left$"
)
HEADING_RE = re.compile(r"^(?P<scope>.*\S)\s+limit:\s*$")
KEY_VALUE_RE = re.compile(r"^(?P<key>[A-Za-z][A-Za-z0-9 \._/-]*):\s*(?P<value>.+)$")


@dataclass
class LimitRecord:
    scope: str
    window: str
    bar: str
    percent_left: int
    resets: Optional[str]


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)


def clean_line(raw_line: str) -> str:
    return raw_line.strip().strip("│").strip()


def read_chunk(fd: int, deadline: float, *, pause: float = 0.05) -> bytes:
    now = dt.datetime.now().timestamp()
    if now >= deadline:
        return b""

    timeout = max(0.0, min(pause, deadline - now))
    ready, _, _ = select.select([fd], [], [], timeout)
    if not ready:
        return b""

    try:
        return os.read(fd, 65536)
    except OSError as exc:
        if exc.errno in {6, 9, 11}:
            return b""
        raise


def parse_chunk(chunk: str, scope: str) -> list[LimitRecord]:
    found: list[LimitRecord] = []
    for raw_line in chunk.splitlines():
        line = clean_line(raw_line)
        if not line:
            continue

        match = LIMIT_LINE_RE.match(line)
        if not match:
            match = LIMIT_LINE_NO_RESET_RE.match(line)
            resets = None
        else:
            resets = match.group("resets").strip()

        if match:
            found.append(
                LimitRecord(
                    scope=scope,
                    window=match.group("window").strip(),
                    bar=match.group("bar"),
                    percent_left=int(match.group("percent")),
                    resets=resets,
                )
            )

    return found


def capture_status(codex_cmd: str, init_seconds: float, status_wait_seconds: float) -> str:
    pid, fd = pty.fork()
    if pid == 0:
        os.environ["TERM"] = "xterm-256color"
        os.execvp(codex_cmd, [codex_cmd])

    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 140, 0, 0))

    out = bytearray()
    current_scope = "global"
    status_found = False

    # Initialize session.
    bootstrap_deadline = dt.datetime.now().timestamp() + init_seconds
    while dt.datetime.now().timestamp() < bootstrap_deadline:
        chunk = read_chunk(fd, bootstrap_deadline)
        if chunk:
            out.extend(chunk)

    # Ask for the status card.
    os.write(fd, b"/status\r\n")

    status_deadline = dt.datetime.now().timestamp() + status_wait_seconds
    while dt.datetime.now().timestamp() < status_deadline:
        chunk = read_chunk(fd, status_deadline)
        if not chunk:
            continue

        text = strip_ansi(chunk.decode("utf-8", errors="replace"))
        out.extend(chunk)

        for raw_line in text.splitlines():
            line = clean_line(raw_line)
            if not line:
                continue

            if "Try new model" in line:
                # Use the existing model and re-run /status.
                os.write(fd, b"2\r\n")
                os.write(fd, b"/status\r\n")
                status_deadline = dt.datetime.now().timestamp() + status_wait_seconds
                break

            heading = HEADING_RE.match(line)
            if heading:
                current_scope = heading.group("scope").strip()
                continue

            parsed = parse_chunk(line, current_scope)
            if parsed:
                status_found = True
                status_deadline = min(status_deadline, dt.datetime.now().timestamp() + 1.0)

    os.write(fd, b"exit\r\n")

    end = dt.datetime.now().timestamp() + 2.0
    while dt.datetime.now().timestamp() < end:
        chunk = read_chunk(fd, end)
        if chunk:
            out.extend(chunk)

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass

    try:
        os.waitpid(pid, 0)
    except OSError:
        pass

    os.close(fd)
    return out.decode("utf-8", errors="replace")


def parse_status(raw: str):
    plain = strip_ansi(raw)
    lines = plain.splitlines()

    info = {
        "model": None,
        "directory": None,
        "permissions": None,
        "account": None,
        "collaboration_mode": None,
        "session": None,
        "agents_md": None,
        "cli": None,
    }

    limits: list[LimitRecord] = []
    current_scope = "global"

    for raw_line in lines:
        line = clean_line(raw_line)
        if not line:
            continue

        heading = HEADING_RE.match(line)
        if heading:
            current_scope = heading.group("scope").strip()
            continue

        parsed = parse_chunk(line, current_scope)
        if parsed:
            limits.extend(parsed)
            continue

        kv = KEY_VALUE_RE.match(line)
        if not kv:
            continue

        key = kv.group("key").strip()
        value = kv.group("value").strip()

        if key == "Model":
            info["model"] = value
        elif key == "Directory":
            info["directory"] = value
        elif key == "Permissions":
            info["permissions"] = value
        elif key == "Account":
            info["account"] = value
        elif key == "Collaboration mode":
            info["collaboration_mode"] = value
        elif key == "Session":
            info["session"] = value
        elif key == "Agents.md":
            info["agents_md"] = value
        elif key == "OpenAI Codex":
            info["cli"] = value

    if not limits:
        raise RuntimeError("Could not parse usage limit lines from codex output")

    deduped: dict[tuple[str, str], LimitRecord] = {}
    for entry in limits:
        deduped[(entry.scope, entry.window)] = entry

    grouped: dict[str, list[dict[str, object]]] = {}
    for (scope, _), entry in deduped.items():
        scope_list = grouped.setdefault(scope, [])
        scope_list.append(
            {
                "window": entry.window,
                "bar": entry.bar,
                "percent_left": entry.percent_left,
                "resets": entry.resets,
            }
        )

    for scope_values in grouped.values():
        scope_values.sort(key=lambda item: item["window"])

    parsed = {
        "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status_info": info,
        "limits_by_scope": grouped,
        "raw_lines": [clean_line(line) for line in lines if clean_line(line)],
    }

    return parsed


def collect_status(
    codex_cmd: str,
    init_seconds: float,
    status_wait_seconds: float,
    include_raw: bool,
) -> dict[str, object]:
    raw = capture_status(codex_cmd, init_seconds, status_wait_seconds)
    result = parse_status(raw)

    if not include_raw:
        result.pop("raw_lines", None)

    return result


def emit_json(payload: dict[str, object], pretty: bool, ndjson: bool) -> None:
    if ndjson:
        print(json.dumps(payload), flush=True)
        return

    print(json.dumps(payload, indent=2 if pretty else None), flush=True)


def run_watch(
    codex_cmd: str,
    init_seconds: float,
    status_wait_seconds: float,
    include_raw: bool,
    pretty: bool,
    ndjson: bool,
    interval_seconds: float,
) -> int:
    if interval_seconds <= 0:
        raise ValueError("--watch must be greater than 0")

    try:
        while True:
            payload = collect_status(
                codex_cmd=codex_cmd,
                init_seconds=init_seconds,
                status_wait_seconds=status_wait_seconds,
                include_raw=include_raw,
            )
            emit_json(payload, pretty, ndjson)
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Codex usage limits from /status and return JSON."
    )
    parser.add_argument(
        "--codex",
        default="codex",
        help="Path to codex executable. Defaults to `codex`.",
    )
    parser.add_argument(
        "--init-seconds",
        type=float,
        default=2.0,
        help="Time to let Codex boot before sending /status.",
    )
    parser.add_argument(
        "--status-seconds",
        type=float,
        default=24.0,
        help="Time to wait for /status output after sending the command.",
    )
    parser.add_argument(
        "--watch",
        type=float,
        metavar="SECONDS",
        help="Poll continuously and emit a JSON snapshot every N seconds.",
    )
    parser.add_argument(
        "--ndjson",
        action="store_true",
        help="Emit newline-delimited JSON objects. Useful with --watch.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument(
        "--no-raw",
        action="store_true",
        help="Do not include the parsed raw text lines in output.",
    )

    args = parser.parse_args()

    try:
        if args.watch is not None:
            return run_watch(
                codex_cmd=args.codex,
                init_seconds=args.init_seconds,
                status_wait_seconds=args.status_seconds,
                include_raw=not args.no_raw,
                pretty=args.pretty,
                ndjson=args.ndjson,
                interval_seconds=args.watch,
            )

        result = collect_status(
            codex_cmd=args.codex,
            init_seconds=args.init_seconds,
            status_wait_seconds=args.status_seconds,
            include_raw=not args.no_raw,
        )
        emit_json(result, args.pretty, args.ndjson)
        return 0

    except Exception as exc:
        payload = {
            "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "error": str(exc),
        }
        emit_json(payload, args.pretty, args.ndjson)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
