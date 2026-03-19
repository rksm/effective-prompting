#!/usr/bin/env python
"""
Codex Loop Script - Runs Codex CLI in a loop to process PRD phases.

Usage:
    python codex_loop.py <iterations> <prd_file> <prompt_file> <progress_file>
    python codex_loop.py <prd_file> <prompt_file> <progress_file>

Arguments:
    iterations    - Maximum number of iterations to run (optional; unlimited if omitted)
    prd_file      - Path to PRD.jsonc or PRD.json file
    prompt_file   - Path to PROMPT.md file
    progress_file - Path to PROGRESS.md file (created if missing, errors if non-empty)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ANSI color codes for terminal output
BOLD = "\033[1m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
DIM = "\033[2m"
RED = "\033[31m"
RESET = "\033[0m"

# Disable colors if not a TTY or NO_COLOR is set
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    BOLD = CYAN = YELLOW = GREEN = DIM = RED = RESET = ""


DONE_PATTERNS = [
    r"<CODEX>DONE</CODEX>",
    r"<CLAUDE>DONE</CLAUDE>",
]

BLOCKED_PATTERNS = [
    r"<CODEX>BLOCKED:\s*(.+?)</CODEX>",
    r"<CLAUDE>BLOCKED:\s*(.+?)</CLAUDE>",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Codex CLI in a loop to process PRD phases"
    )
    parser.add_argument(
        "args",
        nargs="+",
        metavar="arg",
        help=(
            "Either: <iterations> <prd> <prompt> <progress> "
            "or: <prd> <prompt> <progress>"
        ),
    )
    parsed = parser.parse_args()

    if len(parsed.args) == 3:
        iterations = None
        prd_str, prompt_str, progress_str = parsed.args
    elif len(parsed.args) == 4:
        try:
            iterations = int(parsed.args[0])
        except ValueError:
            parser.error(
                "When four arguments are provided, the first must be an integer "
                "iteration count"
            )
        prd_str, prompt_str, progress_str = parsed.args[1:]
    else:
        parser.error(
            "Expected either 3 arguments (<prd> <prompt> <progress>) or 4 arguments "
            "(<iterations> <prd> <prompt> <progress>)"
        )

    return argparse.Namespace(
        iterations=iterations,
        prd=Path(prd_str),
        prompt=Path(prompt_str),
        progress=Path(progress_str),
    )


def truncate(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def format_assistant_text(text: str) -> str:
    return f"{BOLD}{CYAN}{text}{RESET}"


def format_system(text: str) -> str:
    return f"{DIM}{text}{RESET}"


def format_warning(text: str) -> str:
    return f"{YELLOW}{text}{RESET}"


def format_error(text: str) -> str:
    return f"{RED}{text}{RESET}"


def format_command(command: str, status: str) -> str:
    return f"{DIM}[Command:{status}] {truncate(command, 120)}{RESET}"


def format_command_result(output: str, exit_code: int | None) -> str:
    details = [f"exit={exit_code}" if exit_code is not None else "exit=unknown"]
    stripped = output.strip()
    if stripped:
        details.append(f"output={truncate(stripped, 200)}")
    return f"{DIM}[CommandResult] {', '.join(details)}{RESET}"


def strip_json_comments(text: str) -> str:
    """Remove // and /* */ comments while preserving strings and newlines."""
    result: list[str] = []
    in_string = False
    in_line_comment = False
    in_block_comment = False
    escape = False
    i = 0

    while i < len(text):
        char = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else ""

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
                result.append(char)
            i += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                i += 2
                continue
            if char == "\n":
                result.append("\n")
            i += 1
            continue

        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            i += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            i += 1
            continue

        if char == "/" and next_char == "/":
            in_line_comment = True
            i += 2
            continue

        if char == "/" and next_char == "*":
            in_block_comment = True
            i += 2
            continue

        result.append(char)
        i += 1

    return "".join(result)


def load_prd(prd_path: Path) -> dict[str, Any]:
    raw = prd_path.read_text()
    return json.loads(strip_json_comments(raw))


def verify_done(prd_path: Path) -> tuple[bool, str]:
    """
    Verify locally that the PRD indicates all steps are done.
    Returns (is_verified, explanation).
    """
    try:
        prd = load_prd(prd_path)
    except Exception as exc:
        return False, f"Could not parse PRD: {exc}"

    steps = prd.get("steps")
    if not isinstance(steps, list) or not steps:
        return False, "PRD has no steps to verify"

    incomplete: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            incomplete.append("invalid step entry")
            continue
        status = step.get("status")
        if status != "done":
            step_id = step.get("id") or step.get("title") or "<unknown>"
            incomplete.append(f"{step_id} ({status})")

    if incomplete:
        return False, ", ".join(incomplete)

    return True, "All PRD steps verified as done"


def build_codex_prompt(prd: Path, prompt: Path, progress: Path) -> str:
    prompt_text = prompt.read_text()

    return f"""You are Codex running inside an automated PRD execution loop.

Repository root: {Path.cwd()}
PRD file: {prd.resolve()}
Prompt file: {prompt.resolve()}
Progress file: {progress.resolve()}

Loop-specific requirements:
- Read and follow the embedded PROMPT.md instructions below.
- Treat any @file references inside the prompt as ordinary file paths to inspect from disk.
- If the prompt mentions Claude-specific completion tags, ignore the agent name and use the Codex tags below instead.
- Use <CODEX>DONE</CODEX> only when the PRD is actually complete.
- Use <CODEX>BLOCKED: explanation</CODEX> only when you are truly blocked.
- Update the PRD file in place as work progresses.
- Append progress notes to the exact progress file path above.
- If the PRD already indicates all work is complete, respond with <CODEX>DONE</CODEX>.

Begin embedded PROMPT.md content:

{prompt_text}
"""


def process_json_line(line: str) -> str | None:
    """
    Parse a Codex JSONL event line and return human-readable output.
    Returns None if the line should not be printed.
    """
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        text = line.rstrip()
        return text if text else None

    event_type = data.get("type")

    if event_type == "thread.started":
        thread_id = str(data.get("thread_id", ""))[:8]
        return format_system(f"[System] Session started (thread: {thread_id}...)")

    if event_type == "turn.started":
        return format_system("[Turn] Started")

    if event_type == "turn.completed":
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        usage_parts = []
        if input_tokens is not None:
            usage_parts.append(f"in={input_tokens}")
        if output_tokens is not None:
            usage_parts.append(f"out={output_tokens}")
        suffix = f" ({', '.join(usage_parts)})" if usage_parts else ""
        return f"{GREEN}[Turn] Completed{suffix}{RESET}"

    if event_type == "error":
        message = data.get("message") or json.dumps(data)
        return format_error(f"[Error] {message}")

    if event_type not in {"item.started", "item.updated", "item.completed"}:
        return None

    item = data.get("item", {})
    item_type = item.get("type")

    if item_type == "agent_message" and event_type == "item.completed":
        text = item.get("text", "").strip()
        return format_assistant_text(text) if text else None

    if item_type == "command_execution":
        command = item.get("command", "")
        exit_code = item.get("exit_code")
        output = item.get("aggregated_output", "")
        status = item.get("status", "")

        if event_type == "item.started":
            return format_command(command, "start")

        if event_type == "item.completed":
            if output.strip() or exit_code not in (None, 0):
                return format_command_result(output, exit_code)
            return format_command(command, "done")

        return None

    if event_type == "item.completed":
        item_id = item.get("id", "unknown")
        return format_system(f"[Item] {item_type or 'unknown'} completed ({item_id})")

    return None


def run_codex(
    prd: Path, prompt: Path, progress: Path, log_file: Path, iteration: int
) -> tuple[int, str]:
    """
    Run codex exec and stream output while capturing it.
    Returns (exit_code, captured_output).
    """
    cmd = [
        "codex",
        "exec",
        "--json",
        "--yolo",
        "-C",
        str(Path.cwd()),
        "-",
    ]

    captured_output: list[str] = []
    codex_prompt = build_codex_prompt(prd, prompt, progress)

    with open(log_file, "a") as log:
        log.write(f"\n{'='*60}\n")
        log.write(f"Iteration {iteration} - {datetime.now().isoformat()}\n")
        log.write(f"{'='*60}\n")

    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdin is not None
    process.stdin.write(codex_prompt)
    process.stdin.close()

    with open(log_file, "a") as log:
        if process.stdout:
            for line in process.stdout:
                log.write(line)
                log.flush()

                captured_output.append(line)

                readable = process_json_line(line)
                if readable:
                    print(readable, flush=True)

    process.wait()
    return process.returncode, "".join(captured_output)


def check_output(output: str) -> tuple[str, str | None]:
    """
    Check output for DONE or BLOCKED tags.
    Returns (status, explanation) where status is 'done', 'blocked', or 'continue'.
    """
    for pattern in DONE_PATTERNS:
        if re.search(pattern, output):
            return "done", None

    for pattern in BLOCKED_PATTERNS:
        match = re.search(pattern, output, re.DOTALL)
        if match:
            return "blocked", match.group(1).strip()

    return "continue", None


def main() -> int:
    args = parse_args()

    if not args.prd.exists():
        print(f"Error: PRD file not found: {args.prd}", file=sys.stderr)
        return 1

    if not args.prompt.exists():
        print(f"Error: Prompt file not found: {args.prompt}", file=sys.stderr)
        return 1

    if args.iterations is not None and args.iterations < 1:
        print("Error: Iterations must be at least 1", file=sys.stderr)
        return 1

    if args.progress.exists():
        if args.progress.stat().st_size > 0:
            print(
                f"WARNING: Progress file already exists and is not empty: {args.progress}",
                file=sys.stderr,
            )
            input("Press Enter to continue or Ctrl+C to exit...")
    else:
        args.progress.touch()
        print(f"Created progress file: {args.progress}")

    log_file = args.prompt.parent / "codex.log"

    iteration = 1
    while args.iterations is None or iteration <= args.iterations:
        print(f"\n{'='*60}")
        if args.iterations is None:
            print(f"Iteration {iteration}")
        else:
            print(f"Iteration {iteration}/{args.iterations}")
        print(f"{'='*60}\n")

        exit_code, output = run_codex(
            args.prd,
            args.prompt,
            args.progress,
            log_file,
            iteration,
        )

        if exit_code != 0:
            print(f"\nError: Codex exited with code {exit_code}", file=sys.stderr)
            return 1

        status, explanation = check_output(output)

        if status == "done":
            verified, verify_reason = verify_done(args.prd)
            if verified:
                print("\n" + "=" * 60)
                print("SUCCESS: All phases completed (verified)")
                print("=" * 60)
                return 0

            print(
                f"\n{YELLOW}[Warning] Codex claimed DONE but verification failed: "
                f"{verify_reason}{RESET}"
            )
            print(f"{YELLOW}[Warning] Continuing loop...{RESET}")

        if status == "blocked":
            print("\n" + "=" * 60)
            print(f"BLOCKED: {explanation}")
            print("=" * 60)
            return 1

        iteration += 1

    print("\n" + "=" * 60)
    print(f"FAILED: Maximum iterations ({args.iterations}) reached without completion")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
