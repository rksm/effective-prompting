#!/usr/bin/env python
"""
Claude Loop Script - Runs Claude CLI in a loop to process PRD phases.

Usage:
    python claude_loop.py <iterations> <prd_file> <prompt_file> <progress_file>

Arguments:
    iterations    - Maximum number of iterations to run
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

# ANSI color codes for terminal output
BOLD = "\033[1m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
DIM = "\033[2m"
RESET = "\033[0m"

# Disable colors if not a TTY or NO_COLOR is set
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    BOLD = CYAN = YELLOW = GREEN = DIM = RESET = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Claude CLI in a loop to process PRD phases"
    )
    parser.add_argument(
        "iterations",
        type=int,
        help="Maximum number of iterations to run",
    )
    parser.add_argument(
        "prd",
        type=Path,
        help="Path to PRD.jsonc or PRD.json file",
    )
    parser.add_argument(
        "prompt",
        type=Path,
        help="Path to PROMPT.md file",
    )
    parser.add_argument(
        "progress",
        type=Path,
        help="Path to PROGRESS.md file (created if missing, errors if non-empty)",
    )
    return parser.parse_args()


def format_tool_use(tool_name: str, tool_input: dict) -> str:
    """Format tool use for human-readable output."""
    # Show tool name and high-level details without full input/output
    details = []

    if tool_name == "Read":
        if "file_path" in tool_input:
            details.append(f"file: {tool_input['file_path']}")
    elif tool_name == "Write":
        if "file_path" in tool_input:
            details.append(f"file: {tool_input['file_path']}")
    elif tool_name == "Edit":
        if "file_path" in tool_input:
            details.append(f"file: {tool_input['file_path']}")
    elif tool_name == "Bash":
        if "command" in tool_input:
            cmd = tool_input["command"]
            # Truncate long commands
            if len(cmd) > 80:
                cmd = cmd[:77] + "..."
            details.append(f"cmd: {cmd}")
    elif tool_name == "Glob":
        if "pattern" in tool_input:
            details.append(f"pattern: {tool_input['pattern']}")
    elif tool_name == "Grep":
        if "pattern" in tool_input:
            details.append(f"pattern: {tool_input['pattern']}")
    elif tool_name == "Task":
        if "description" in tool_input:
            details.append(f"desc: {tool_input['description']}")
    elif tool_name == "WebFetch":
        if "url" in tool_input:
            details.append(f"url: {tool_input['url']}")
    elif tool_name == "TodoWrite":
        if "todos" in tool_input:
            details.append(f"todos: {len(tool_input['todos'])} items")

    detail_str = ", ".join(details) if details else ""
    if detail_str:
        return f"{DIM}[Tool: {tool_name}] {detail_str}{RESET}"
    return f"{DIM}[Tool: {tool_name}]{RESET}"


def format_tool_result(content: str) -> str:
    """Format tool result for human-readable output."""
    # Truncate long results
    if len(content) > 200:
        return f"{DIM}[Result: {content[:197]}...]{RESET}"
    return f"{DIM}[Result: {content}]{RESET}"


def format_assistant_text(text: str) -> str:
    """Format assistant text for highlighted output."""
    return f"{BOLD}{CYAN}{text}{RESET}"


def format_thinking(text: str) -> str:
    """Format thinking/reasoning blocks."""
    return f"{YELLOW}[Thinking] {text}{RESET}"


def process_json_line(line: str) -> str | None:
    """
    Parse a JSON line and return human-readable output.
    Returns None if the line should not be printed.
    """
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        # Not valid JSON, return as-is
        return line.rstrip()

    msg_type = data.get("type")

    if msg_type == "system":
        subtype = data.get("subtype")
        if subtype == "init":
            model = data.get("model", "unknown")
            session_id = data.get("session_id", "")[:8]
            return f"{DIM}[System] Session started (model: {model}, session: {session_id}...){RESET}"
        return None

    elif msg_type == "assistant":
        message = data.get("message", {})
        content = message.get("content", [])

        output_parts = []
        for item in content:
            item_type = item.get("type")
            if item_type == "text":
                text = item.get("text", "")
                if text.strip():
                    output_parts.append(format_assistant_text(text))
            elif item_type == "thinking":
                text = item.get("thinking", "")
                if text.strip():
                    output_parts.append(format_thinking(text))
            elif item_type == "tool_use":
                tool_name = item.get("name", "unknown")
                tool_input = item.get("input", {})
                output_parts.append(format_tool_use(tool_name, tool_input))

        if output_parts:
            return "\n".join(output_parts)
        return None

    elif msg_type == "user":
        # Tool results come as user messages
        message = data.get("message", {})
        content = message.get("content", [])

        for item in content:
            if item.get("type") == "tool_result":
                result_content = item.get("content", "")
                if isinstance(result_content, str) and result_content.strip():
                    return format_tool_result(result_content)
        return None

    elif msg_type == "result":
        subtype = data.get("subtype")
        duration_ms = data.get("duration_ms", 0)
        duration_s = duration_ms / 1000
        cost = data.get("total_cost_usd", 0)

        if subtype == "success":
            return f"{GREEN}[Result] Completed in {duration_s:.1f}s (cost: ${cost:.4f}){RESET}"
        else:
            return f"{GREEN}[Result] {subtype} in {duration_s:.1f}s (cost: ${cost:.4f}){RESET}"

    return None


def run_claude(prompt: Path, log_file: Path, iteration: int) -> tuple[int, str]:
    """
    Run claude CLI and stream output while capturing it.
    Returns (exit_code, captured_output).
    """
    cmd = [
        "claude",
        "--dangerously-skip-permissions",
        "--print",
        "--verbose",
        "--output-format=stream-json",
        "--chrome",
        f"@{prompt}",
    ]

    captured_output = []

    # Append to log file with iteration header
    with open(log_file, "a") as log:
        log.write(f"\n{'='*60}\n")
        log.write(f"Iteration {iteration} - {datetime.now().isoformat()}\n")
        log.write(f"{'='*60}\n")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    with open(log_file, "a") as log:
        if process.stdout:
            for line in process.stdout:
                # Append raw line to log file
                log.write(line)
                log.flush()

                captured_output.append(line)

                # Parse and print human-readable version
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
    done_match = re.search(r"<CLAUDE>DONE</CLAUDE>", output)
    if done_match:
        return "done", None

    blocked_match = re.search(r"<CLAUDE>BLOCKED:\s*(.+?)</CLAUDE>", output, re.DOTALL)
    if blocked_match:
        return "blocked", blocked_match.group(1).strip()

    return "continue", None


def main() -> int:
    args = parse_args()

    # Validate files exist
    if not args.prd.exists():
        print(f"Error: PRD file not found: {args.prd}", file=sys.stderr)
        return 1

    if not args.prompt.exists():
        print(f"Error: Prompt file not found: {args.prompt}", file=sys.stderr)
        return 1

    if args.iterations < 1:
        print("Error: Iterations must be at least 1", file=sys.stderr)
        return 1

    # Handle progress file: create if missing, error if non-empty
    if args.progress.exists():
        if args.progress.stat().st_size > 0:
            print(
                f"Error: Progress file already exists and is not empty: {args.progress}",
                file=sys.stderr,
            )
            return 1
    else:
        args.progress.touch()
        print(f"Created progress file: {args.progress}")

    # Log file in the same directory as the prompt file
    log_file = args.prompt.parent / "claude.log"

    for iteration in range(1, args.iterations + 1):
        print(f"\n{'='*60}")
        print(f"Iteration {iteration}/{args.iterations}")
        print(f"{'='*60}\n")

        exit_code, output = run_claude(args.prompt, log_file, iteration)

        if exit_code != 0:
            print(f"\nError: Claude exited with code {exit_code}", file=sys.stderr)
            return 1

        status, explanation = check_output(output)

        if status == "done":
            print("\n" + "=" * 60)
            print("SUCCESS: All phases completed")
            print("=" * 60)
            return 0

        if status == "blocked":
            print("\n" + "=" * 60)
            print(f"BLOCKED: {explanation}")
            print("=" * 60)
            return 1

        # status == "continue" - loop continues

    print("\n" + "=" * 60)
    print(f"FAILED: Maximum iterations ({args.iterations}) reached without completion")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
