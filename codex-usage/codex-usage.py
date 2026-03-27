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
from pathlib import Path
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

DEFAULT_CODEX_CONFIG_OVERRIDES = (
    "mcp_servers.chrome-devtools.enabled=false",
)
TERMINAL_QUERY_DEVICE_ATTRIBUTES = b"\x1b[c"
TERMINAL_QUERY_FOREGROUND_COLOR = b"\x1b]10;?\x1b\\"
TERMINAL_REPLY_DEVICE_ATTRIBUTES = b"\x1b[?1;2c"
TERMINAL_REPLY_FOREGROUND_COLOR = b"\x1b]10;rgb:ffff/ffff/ffff\x1b\\"


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
        if exc.errno in {5, 6, 9, 11}:
            return b""
        raise


def reply_to_terminal_queries(fd: int, chunk: bytes) -> None:
    if TERMINAL_QUERY_DEVICE_ATTRIBUTES in chunk:
        os.write(fd, TERMINAL_REPLY_DEVICE_ATTRIBUTES)
    if TERMINAL_QUERY_FOREGROUND_COLOR in chunk:
        os.write(fd, TERMINAL_REPLY_FOREGROUND_COLOR)


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


def build_codex_argv(codex_cmd: str) -> list[str]:
    argv = [codex_cmd]
    for override in DEFAULT_CODEX_CONFIG_OVERRIDES:
        argv.extend(["-c", override])
    return argv


def capture_status(
    codex_cmd: str,
    init_seconds: float,
    status_wait_seconds: float,
    codex_home: Optional[str] = None,
) -> str:
    pid, fd = pty.fork()
    if pid == 0:
        os.environ["TERM"] = "xterm-256color"
        if codex_home is not None:
            os.environ["CODEX_HOME"] = codex_home
        os.execvp(codex_cmd, build_codex_argv(codex_cmd))

    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 140, 0, 0))

    out = bytearray()
    current_scope = "global"
    status_found = False

    bootstrap_deadline = dt.datetime.now().timestamp() + init_seconds
    while dt.datetime.now().timestamp() < bootstrap_deadline:
        chunk = read_chunk(fd, bootstrap_deadline)
        if not chunk:
            continue
        reply_to_terminal_queries(fd, chunk)
        out.extend(chunk)

    for attempt in range(2):
        os.write(fd, b"/status\r\n")

        status_deadline = dt.datetime.now().timestamp() + status_wait_seconds
        while dt.datetime.now().timestamp() < status_deadline:
            chunk = read_chunk(fd, status_deadline)
            if not chunk:
                continue

            reply_to_terminal_queries(fd, chunk)
            out.extend(chunk)
            text = strip_ansi(chunk.decode("utf-8", errors="replace"))

            for raw_line in text.splitlines():
                line = clean_line(raw_line)
                if not line:
                    continue

                if "Try new model" in line:
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

            if status_found:
                break

        if status_found:
            break

    os.write(fd, b"exit\r\n")

    end = dt.datetime.now().timestamp() + 2.0
    while dt.datetime.now().timestamp() < end:
        chunk = read_chunk(fd, end)
        if not chunk:
            continue
        reply_to_terminal_queries(fd, chunk)
        out.extend(chunk)

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass

    try:
        os.waitpid(pid, 0)
    except OSError:
        pass

    try:
        os.close(fd)
    except OSError:
        pass

    return out.decode("utf-8", errors="replace")


def parse_status(raw: str) -> dict[str, object]:
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

    return {
        "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status_info": info,
        "limits_by_scope": grouped,
        "raw_lines": [clean_line(line) for line in lines if clean_line(line)],
    }


def build_contexts(codex_homes: Optional[list[str]]) -> list[dict[str, Optional[str]]]:
    if not codex_homes:
        return [{"context": None, "codex_home": None}]

    contexts = []
    for raw_path in codex_homes:
        path = Path(raw_path).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f"--codex-home must point to a directory: {raw_path}")
        if not (path / "auth.json").is_file():
            raise ValueError(f"--codex-home is missing auth.json: {path}")

        contexts.append({"context": str(path), "codex_home": str(path)})

    return contexts


def format_pretty(snapshot: dict[str, object]) -> str:
    retrieved_at = str(snapshot["retrieved_at"])
    grouped = snapshot["limits_by_scope"]
    parts = []
    if snapshot.get("context") is not None:
        parts.append(str(snapshot["context"]))
    parts.append(retrieved_at)

    scope_names = []
    if "global" in grouped:
        scope_names.append("global")
    scope_names.extend(sorted(name for name in grouped if name != "global"))

    for scope in scope_names:
        entries = grouped[scope]
        rendered = ", ".join(
            f"{entry['window']}={entry['percent_left']}% reset={entry['resets']}"
            for entry in entries
        )
        parts.append(f"{scope}: {rendered}")
    return " | ".join(parts)


def emit_snapshot(snapshot: dict[str, object], *, pretty: bool, ndjson: bool) -> None:
    if pretty:
        print(format_pretty(snapshot), flush=True)
        return

    if ndjson:
        print(json.dumps(snapshot, separators=(",", ":")), flush=True)
        return

    print(json.dumps(snapshot, indent=2), flush=True)


def emit_snapshots(
    snapshots: list[dict[str, object]],
    *,
    pretty: bool,
    ndjson: bool,
    multiple: bool,
) -> None:
    if pretty or ndjson:
        for snapshot in snapshots:
            emit_snapshot(snapshot, pretty=pretty, ndjson=ndjson)
        return

    if multiple:
        print(json.dumps(snapshots, indent=2), flush=True)
        return

    emit_snapshot(snapshots[0], pretty=False, ndjson=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default="codex", help="codex executable to launch")
    parser.add_argument(
        "--init-seconds",
        type=float,
        default=2.5,
        help="seconds to allow Codex to initialize before sending /status",
    )
    parser.add_argument(
        "--status-seconds",
        type=float,
        default=10.0,
        help="seconds to wait for the /status card after requesting it",
    )
    parser.add_argument(
        "--watch",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help="poll repeatedly every N seconds until interrupted",
    )
    parser.add_argument(
        "--codex-home",
        action="append",
        metavar="DIR",
        help="repeatable CODEX_HOME directory containing auth.json and optional config.toml",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="emit compact human-readable summaries instead of JSON",
    )
    parser.add_argument(
        "--ndjson",
        action="store_true",
        help="emit one compact JSON object per line",
    )
    parser.add_argument(
        "--no-raw",
        action="store_true",
        help="omit raw parsed lines from the output payload",
    )
    return parser


def make_snapshot(args: argparse.Namespace, context: dict[str, Optional[str]]) -> dict[str, object]:
    snapshot = parse_status(
        capture_status(
            args.codex,
            args.init_seconds,
            args.status_seconds,
            codex_home=context["codex_home"],
        )
    )
    if args.no_raw:
        snapshot.pop("raw_lines", None)
    if context["context"] is not None:
        snapshot["context"] = context["context"]
        snapshot["codex_home"] = context["codex_home"]
    return snapshot


def main() -> int:
    args = build_parser().parse_args()
    if args.pretty and args.ndjson:
        raise SystemExit("--pretty and --ndjson are mutually exclusive")
    contexts = build_contexts(args.codex_home)

    if args.watch <= 0:
        snapshots = [make_snapshot(args, context) for context in contexts]
        emit_snapshots(
            snapshots,
            pretty=args.pretty,
            ndjson=args.ndjson,
            multiple=len(contexts) > 1,
        )
        return 0

    while True:
        snapshots = [make_snapshot(args, context) for context in contexts]
        emit_snapshots(
            snapshots,
            pretty=args.pretty,
            ndjson=args.ndjson,
            multiple=len(contexts) > 1,
        )
        time.sleep(args.watch)


if __name__ == "__main__":
    raise SystemExit(main())
