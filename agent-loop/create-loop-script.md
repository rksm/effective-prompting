I want you to create a script which controls the Claude code CLI. The script should be written in Python. And it should take three arguments:

1. Iteration count. It should run Claude for at maximum this amount of iterations.
2. A PRD.jsonc (preferred; comments allowed) or PRD.json (strict JSON) file. This file should roughly have the format like:
```
{
  "title": "Some plan",
  "status": "in-progress",
  "goals": [
    "List of things to achieve"
  ],
  "non_goals": [
    "Restrictions, caveats",
    "No refactors or behavior changes beyond mechanical moves and toolchain alignment."
  ],
  // phases are listed in order and processed one at a time
  "steps": [
    {
      "id": "step-1-preparation",
      "title": "Prepare for the plan",
      "status": "done",
      "tasks": [
        "Some tasks"
      ]
    },
    {
      "id": "step-2-do-the-work",
      "title": "Work man",
      "status": "planned",
      "tasks": [
        "Scan packages/cf-webrtc for internal workspace deps (for example: @hyper-lite/logging, @hyper-lite/ui, @hyper-lite/ts-config) and list everything that must move with the subsystem.",
        "Collect all catalog entries used by cf-webrtc and the supporting packages so the new repo can reuse the same version map."
      ],
      "validation": [
        {
          "id": "Manual browser tests",
          "type": "browser-testing",
          "instructions": [
            "Start a dev server with `just run`",
            "Use claude-in-chrome mcp to control the browser and check if the functionality works"
          ],
          "expected": "Dependencies install without errors."
        }
      ]
    }
  ],
  "global_validation": [
    {
      "id": "Manual browser tests",
      "type": "browser-testing",
      "instructions": [
        "Start a dev server with `just run`",
        "Use claude-in-chrome mcp to control the browser and check if the functionality works"
      ],
      "expected": "Dependencies install without errors."
    },
    {
      "id": "lint",
      "type": "automated",
      "instructions": [
        "just lint"
      ],
      "expected": "No lint errors across packages."
    },
    {
      "id": "build",
      "type": "automated",
      "instructions": [
        "just build"
      ],
      "expected": "Build completes without errors."
    }
  ]
}
```
The purpose of this file is to clearly state steps to achieve a desired outcome. This should be very well structured; hence, the JSON/JSONC format.
Schema notes: top-level `status` and per-step `status` should be one of `planned`, `in-progress`, `done`, or `blocked`. Each entry in `steps` is a phase, and each phase uses a `tasks` array (strings) plus optional `validation`.
3. A PROMPT.md file. Example:
```
@PRD.jsonc

## Task
- Find the first phase with `"status": "planned"`.
- Implement all tasks for that phase according to "tasks". Follow those tasks precisely.
- Run the phase’s listed validation instructions and any lightweight `global_validation` checks that make sense at this point.
- Update the phase status to `"done"` once complete.
- Append progress notes to `PROGRESS.md` (include what was done, what remains, any blockers, and any additional observations that might be important for follow up work).
- Commit all changes with a concise conventional-commit style message.

If while implementing the steps you find that the prd is complete, output <CLAUDE>DONE</CLAUDE>.

If while implementing the steps you run into an issue you cannot resolve or find conceptual problems with the plan, output <CLAUDE>BLOCKED: [explanation]</CLAUDE>.

## Context, scope and intent
- Some narrative about the why
- What to change
- What the outcome should be, high-level

## Workflow expectations
- Follow the phase tasks exactly; do not implement future phases early.
- For git history moves, use `git filter-repo` on a fresh clone as described in the plan.
- Avoid destructive operations on the source repo; use the filtered clone for history extraction.
- Update paths in config files only as required by the new root layout.

## Tests and validation
- Prefer the phase’s listed commands/tests.
- If a test can’t be run, explain why and provide manual verification steps.
- Keep tests lightweight and scoped to the current phase.

## Dev environment
- If tools are missing, you may need a Nix dev shell (`nix develop`).
- ...

## Constraints
- Keep changes scoped to the current phase. DO NOT IMPLEMENT other phases.
- Don’t remove or alter unrelated code.
- Prefer small, clear changes; avoid introducing new dependencies unless required.

## Progress

@PROGRESS.md
```

The script should output the current iteration then run claude with `claude --dangerously-skip-permissions --print --verbose --output-format=stream-json --chrome "@PROMPT.md"`. It should stream claude output to stdout/stderr while also capturing it for parsing. It should check the output for either `<CLAUDE>DONE</CLAUDE>` or `<CLAUDE>BLOCKED: [explanation]</CLAUDE>`.

`--output-format=stream-json` outputs a stream of JSON objects. The script should try to parse new json output objects and print only a human readable version of it to stdout/stderr. In particular, for assistant and user messages, only the text content should be printed. For tool uses, the tool used and high-level details should be printed but not the full input/output.

The full output should be appended to a claude.log file for auditability.

Here is an example of how claude output looks like:

```jsonl
{"type":"system","subtype":"init","cwd":"/home/robert/projects/ai/2026-01-07-prompts","session_id":"707c48df-3786-4b9f-ac05-a93054f0a542","tools":["Task","TaskOutput","Bash","Glob","Grep","ExitPlanMode","Read","Edit","Write","NotebookEdit","WebFetch","TodoWrite","WebSearch","KillShell","AskUserQuestion","Skill","EnterPlanMode","LSP","mcp__consult-llm__consult_llm","mcp__chrome-devtools__click","mcp__chrome-devtools__close_page","mcp__chrome-devtools__drag","mcp__chrome-devtools__emulate","mcp__chrome-devtools__evaluate_script","mcp__chrome-devtools__fill","mcp__chrome-devtools__fill_form","mcp__chrome-devtools__get_console_message","mcp__chrome-devtools__get_network_request","mcp__chrome-devtools__handle_dialog","mcp__chrome-devtools__hover","mcp__chrome-devtools__list_console_messages","mcp__chrome-devtools__list_network_requests","mcp__chrome-devtools__list_pages","mcp__chrome-devtools__navigate_page","mcp__chrome-devtools__new_page","mcp__chrome-devtools__performance_analyze_insight","mcp__chrome-devtools__performance_start_trace","mcp__chrome-devtools__performance_stop_trace","mcp__chrome-devtools__press_key","mcp__chrome-devtools__resize_page","mcp__chrome-devtools__select_page","mcp__chrome-devtools__take_screenshot","mcp__chrome-devtools__take_snapshot","mcp__chrome-devtools__upload_file","mcp__chrome-devtools__wait_for","mcp__context7__resolve-library-id","mcp__context7__query-docs"],"mcp_servers":[{"name":"consult-llm","status":"connected"},{"name":"chrome-devtools","status":"connected"},{"name":"context7","status":"connected"}],"model":"claude-opus-4-5-20251101","permissionMode":"bypassPermissions","slash_commands":["code-review-simple","clipboard","commit-staged","orchestrate","code-review-simple-zen","create-prompt-from-context","code-review-big-picture","custom-compact","hyper:pr-fix-for","hyper:pr-request","hyper:pr-fix-yolo","hyper:pr-fix-carefully","meta:prompt-opt","commit-commands:clean_gone","commit-commands:commit-push-pr","commit-commands:commit","frontend-design:frontend-design","compact","context","cost","init","pr-comments","release-notes","review","security-review"],"apiKeySource":"none","claude_code_version":"2.0.76","output_style":"default","agents":["general-purpose","statusline-setup","Explore","Plan","research-expert","data-scientist","debugger","react-state-manager","react-component-architect","nix-configuration-expert","rust-wasm-expert","rust-backend-expert","nodejs-backend-expert","documentation-specialist","performance-optimizer","code-archaeologist","code-reviewer","react-video-conference-specialist","real-time-protocol-architect","rust-wasm-uniffi-bridge-expert","clickhouse-analytics-expert","workspace-auth-security-expert","rust-media-streaming-expert","nix-devops-optimization-expert","video-performance-metrics-analyst"],"skills":["frontend-design:frontend-design"],"plugins":[{"name":"frontend-design","path":"/home/robert/.claude/plugins/cache/claude-code-plugins/frontend-design/1.0.0"},{"name":"commit-commands","path":"/home/robert/.claude/plugins/cache/claude-code-plugins/commit-commands/1.0.0"}],"uuid":"22708868-2f89-4356-a5f2-702364a2d64b"}
{"type":"assistant","message":{"model":"claude-opus-4-5-20251101","id":"msg_01EztgVtf54JXHWGisPkxWY5","type":"message","role":"assistant","content":[{"type":"text","text":"I'll create the `claude_loop.py` script based on the requirements in the document."}],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":3,"cache_creation_input_tokens":28891,"cache_read_input_tokens":0,"cache_creation":{"ephemeral_5m_input_tokens":28891,"ephemeral_1h_input_tokens":0},"output_tokens":4,"service_tier":"standard"},"context_management":null},"parent_tool_use_id":null,"session_id":"707c48df-3786-4b9f-ac05-a93054f0a542","uuid":"82f50fe8-d229-4a0e-bb85-9dff2a4537e7"}
{"type":"assistant","message":{"model":"claude-opus-4-5-20251101","id":"msg_01EztgVtf54JXHWGisPkxWY5","type":"message","role":"assistant","content":[{"type":"tool_use","id":"toolu_01EMZ7HHnpN129XphFhXDwPq","name":"Write","input":{"file_path":"/home/robert/projects/ai/2026-01-07-prompts/2026-01-07-claude-loop/claude_loop.py","content":"#!/usr/bin/env python\n\"\"\"\nClaude Loop Script - Runs Claude CLI in a loop to process PRD phases.\n\nUsage:\n    python claude_loop.py <iterations> <prd_file> <prompt_file>\n\nArguments:\n    iterations  - Maximum number of iterations to run\n    prd_file    - Path to PRD.jsonc or PRD.json file\n    prompt_file - Path to PROMPT.md file\n\"\"\"\n\nimport argparse\nimport re\nimport subprocess\nimport sys\nfrom pathlib import Path\n\n\ndef parse_args() -> argparse.Namespace:\n    parser = argparse.ArgumentParser(\n        description=\"Run Claude CLI in a loop to process PRD phases\"\n    )\n    parser.add_argument(\n        \"iterations\",\n        type=int,\n        help=\"Maximum number of iterations to run\",\n    )\n    parser.add_argument(\n        \"prd_file\",\n        type=Path,\n        help=\"Path to PRD.jsonc or PRD.json file\",\n    )\n    parser.add_argument(\n        \"prompt_file\",\n        type=Path,\n        help=\"Path to PROMPT.md file\",\n    )\n    return parser.parse_args()\n\n\ndef run_claude(prompt_file: Path) -> tuple[int, str]:\n    \"\"\"\n    Run claude CLI and stream output while capturing it.\n    Returns (exit_code, captured_output).\n    \"\"\"\n    cmd = [\n        \"claude\",\n        \"--dangerously-skip-permissions\",\n        \"--print\",\n        \"--verbose\",\n        \"--output-format=stream-json\",\n        \"--chrome\",\n        f\"@{prompt_file}\",\n    ]\n\n    captured_output = []\n\n    process = subprocess.Popen(\n        cmd,\n        stdout=subprocess.PIPE,\n        stderr=subprocess.STDOUT,\n        text=True,\n        bufsize=1,\n    )\n\n    for line in process.stdout:\n        print(line, end=\"\", flush=True)\n        captured_output.append(line)\n\n    process.wait()\n    return process.returncode, \"\".join(captured_output)\n\n\ndef check_output(output: str) -> tuple[str, str | None]:\n    \"\"\"\n    Check output for DONE or BLOCKED tags.\n    Returns (status, explanation) where status is 'done', 'blocked', or 'continue'.\n    \"\"\"\n    done_match = re.search(r\"<CLAUDE>DONE</CLAUDE>\", output)\n    if done_match:\n        return \"done\", None\n\n    blocked_match = re.search(r\"<CLAUDE>BLOCKED:\\s*(.+?)</CLAUDE>\", output, re.DOTALL)\n    if blocked_match:\n        return \"blocked\", blocked_match.group(1).strip()\n\n    return \"continue\", None\n\n\ndef main() -> int:\n    args = parse_args()\n\n    # Validate files exist\n    if not args.prd_file.exists():\n        print(f\"Error: PRD file not found: {args.prd_file}\", file=sys.stderr)\n        return 1\n\n    if not args.prompt_file.exists():\n        print(f\"Error: Prompt file not found: {args.prompt_file}\", file=sys.stderr)\n        return 1\n\n    if args.iterations < 1:\n        print(\"Error: Iterations must be at least 1\", file=sys.stderr)\n        return 1\n\n    for iteration in range(1, args.iterations + 1):\n        print(f\"\\n{'='*60}\")\n        print(f\"Iteration {iteration}/{args.iterations}\")\n        print(f\"{'='*60}\\n\")\n\n        exit_code, output = run_claude(args.prompt_file)\n\n        if exit_code != 0:\n            print(f\"\\nError: Claude exited with code {exit_code}\", file=sys.stderr)\n            return 1\n\n        status, explanation = check_output(output)\n\n        if status == \"done\":\n            print(\"\\n\" + \"=\" * 60)\n            print(\"SUCCESS: All phases completed\")\n            print(\"=\" * 60)\n            return 0\n\n        if status == \"blocked\":\n            print(\"\\n\" + \"=\" * 60)\n            print(f\"BLOCKED: {explanation}\")\n            print(\"=\" * 60)\n            return 1\n\n        # status == \"continue\" - loop continues\n\n    print(\"\\n\" + \"=\" * 60)\n    print(f\"FAILED: Maximum iterations ({args.iterations}) reached without completion\")\n    print(\"=\" * 60)\n    return 1\n\n\nif __name__ == \"__main__\":\n    sys.exit(main())\n"}}],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":3,"cache_creation_input_tokens":28891,"cache_read_input_tokens":0,"cache_creation":{"ephemeral_5m_input_tokens":28891,"ephemeral_1h_input_tokens":0},"output_tokens":1237,"service_tier":"standard"},"context_management":null},"parent_tool_use_id":null,"session_id":"707c48df-3786-4b9f-ac05-a93054f0a542","uuid":"bb8fc59e-0f44-43ca-88eb-9a5d88f506f6"}
{"type":"user","message":{"role":"user","content":[{"tool_use_id":"toolu_01EMZ7HHnpN129XphFhXDwPq","type":"tool_result","content":"File created successfully at: /home/robert/projects/ai/2026-01-07-prompts/2026-01-07-claude-loop/claude_loop.py"}]},"parent_tool_use_id":null,"session_id":"707c48df-3786-4b9f-ac05-a93054f0a542","uuid":"910b176f-9062-46b8-be54-40e1ead0cdab","tool_use_result":{"type":"create","filePath":"/home/robert/projects/ai/2026-01-07-prompts/2026-01-07-claude-loop/claude_loop.py","content":"#!/usr/bin/env python\n\"\"\"\nClaude Loop Script - Runs Claude CLI in a loop to process PRD phases.\n\nUsage:\n    python claude_loop.py <iterations> <prd_file> <prompt_file>\n\nArguments:\n    iterations  - Maximum number of iterations to run\n    prd_file    - Path to PRD.jsonc or PRD.json file\n    prompt_file - Path to PROMPT.md file\n\"\"\"\n\nimport argparse\nimport re\nimport subprocess\nimport sys\nfrom pathlib import Path\n\n\ndef parse_args() -> argparse.Namespace:\n    parser = argparse.ArgumentParser(\n        description=\"Run Claude CLI in a loop to process PRD phases\"\n    )\n    parser.add_argument(\n        \"iterations\",\n        type=int,\n        help=\"Maximum number of iterations to run\",\n    )\n    parser.add_argument(\n        \"prd_file\",\n        type=Path,\n        help=\"Path to PRD.jsonc or PRD.json file\",\n    )\n    parser.add_argument(\n        \"prompt_file\",\n        type=Path,\n        help=\"Path to PROMPT.md file\",\n    )\n    return parser.parse_args()\n\n\ndef run_claude(prompt_file: Path) -> tuple[int, str]:\n    \"\"\"\n    Run claude CLI and stream output while capturing it.\n    Returns (exit_code, captured_output).\n    \"\"\"\n    cmd = [\n        \"claude\",\n        \"--dangerously-skip-permissions\",\n        \"--print\",\n        \"--verbose\",\n        \"--output-format=stream-json\",\n        \"--chrome\",\n        f\"@{prompt_file}\",\n    ]\n\n    captured_output = []\n\n    process = subprocess.Popen(\n        cmd,\n        stdout=subprocess.PIPE,\n        stderr=subprocess.STDOUT,\n        text=True,\n        bufsize=1,\n    )\n\n    for line in process.stdout:\n        print(line, end=\"\", flush=True)\n        captured_output.append(line)\n\n    process.wait()\n    return process.returncode, \"\".join(captured_output)\n\n\ndef check_output(output: str) -> tuple[str, str | None]:\n    \"\"\"\n    Check output for DONE or BLOCKED tags.\n    Returns (status, explanation) where status is 'done', 'blocked', or 'continue'.\n    \"\"\"\n    done_match = re.search(r\"<CLAUDE>DONE</CLAUDE>\", output)\n    if done_match:\n        return \"done\", None\n\n    blocked_match = re.search(r\"<CLAUDE>BLOCKED:\\s*(.+?)</CLAUDE>\", output, re.DOTALL)\n    if blocked_match:\n        return \"blocked\", blocked_match.group(1).strip()\n\n    return \"continue\", None\n\n\ndef main() -> int:\n    args = parse_args()\n\n    # Validate files exist\n    if not args.prd_file.exists():\n        print(f\"Error: PRD file not found: {args.prd_file}\", file=sys.stderr)\n        return 1\n\n    if not args.prompt_file.exists():\n        print(f\"Error: Prompt file not found: {args.prompt_file}\", file=sys.stderr)\n        return 1\n\n    if args.iterations < 1:\n        print(\"Error: Iterations must be at least 1\", file=sys.stderr)\n        return 1\n\n    for iteration in range(1, args.iterations + 1):\n        print(f\"\\n{'='*60}\")\n        print(f\"Iteration {iteration}/{args.iterations}\")\n        print(f\"{'='*60}\\n\")\n\n        exit_code, output = run_claude(args.prompt_file)\n\n        if exit_code != 0:\n            print(f\"\\nError: Claude exited with code {exit_code}\", file=sys.stderr)\n            return 1\n\n        status, explanation = check_output(output)\n\n        if status == \"done\":\n            print(\"\\n\" + \"=\" * 60)\n            print(\"SUCCESS: All phases completed\")\n            print(\"=\" * 60)\n            return 0\n\n        if status == \"blocked\":\n            print(\"\\n\" + \"=\" * 60)\n            print(f\"BLOCKED: {explanation}\")\n            print(\"=\" * 60)\n            return 1\n\n        # status == \"continue\" - loop continues\n\n    print(\"\\n\" + \"=\" * 60)\n    print(f\"FAILED: Maximum iterations ({args.iterations}) reached without completion\")\n    print(\"=\" * 60)\n    return 1\n\n\nif __name__ == \"__main__\":\n    sys.exit(main())\n","structuredPatch":[],"originalFile":null}}
{"type":"assistant","message":{"model":"claude-opus-4-5-20251101","id":"msg_01WLmQV8JjaWHUdiQ5Df38Yq","type":"message","role":"assistant","content":[{"type":"tool_use","id":"toolu_01CdWibtKmAW5EsETzqxgSE6","name":"Bash","input":{"command":"chmod +x /home/robert/projects/ai/2026-01-07-prompts/2026-01-07-claude-loop/claude_loop.py","description":"Make script executable"}}],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":1,"cache_creation_input_tokens":1291,"cache_read_input_tokens":28891,"cache_creation":{"ephemeral_5m_input_tokens":1291,"ephemeral_1h_input_tokens":0},"output_tokens":23,"service_tier":"standard"},"context_management":null},"parent_tool_use_id":null,"session_id":"707c48df-3786-4b9f-ac05-a93054f0a542","uuid":"d1e3eb32-0366-4872-aa6f-89cb29642b08"}
{"type":"user","message":{"role":"user","content":[{"tool_use_id":"toolu_01CdWibtKmAW5EsETzqxgSE6","type":"tool_result","content":"","is_error":false}]},"parent_tool_use_id":null,"session_id":"707c48df-3786-4b9f-ac05-a93054f0a542","uuid":"be2418db-c050-46e7-9b10-3a15517b11c3","tool_use_result":{"stdout":"","stderr":"","interrupted":false,"isImage":false}}
{"type":"assistant","message":{"model":"claude-opus-4-5-20251101","id":"msg_01DXfY6fmh35xTLk7CiVHyZd","type":"message","role":"assistant","content":[{"type":"text","text":"Created `claude_loop.py` with the following features:\n\n- **Arguments**: Takes 3 positional args - iteration count, PRD file path, and prompt file path\n- **Validation**: Checks that both files exist and iteration count is ≥ 1\n- **Execution**: Runs `claude --dangerously-skip-permissions --print --verbose --output-format=stream-json --chrome \"@PROMPT.md\"`\n- **Streaming**: Streams stdout/stderr in real-time while capturing for parsing\n- **Tag detection**: Checks for `<CLAUDE>DONE</CLAUDE>` or `<CLAUDE>BLOCKED: [explanation]</CLAUDE>`\n- **Exit conditions**:\n  - `DONE` tag → exit 0 (success)\n  - `BLOCKED` tag → print explanation, exit 1 (failure)\n  - Non-zero claude exit → exit 1 (failure)\n  - Max iterations reached → exit 1 (failure)\n- **Progress display**: Shows current iteration number before each run"}],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":1,"cache_creation_input_tokens":134,"cache_read_input_tokens":30182,"cache_creation":{"ephemeral_5m_input_tokens":134,"ephemeral_1h_input_tokens":0},"output_tokens":1,"service_tier":"standard"},"context_management":null},"parent_tool_use_id":null,"session_id":"707c48df-3786-4b9f-ac05-a93054f0a542","uuid":"78587d0c-911f-41a5-8d7d-cf01b15bbecf"}
{"type":"result","subtype":"success","is_error":false,"duration_ms":30702,"duration_api_ms":37048,"num_turns":3,"result":"Created `claude_loop.py` with the following features:\n\n- **Arguments**: Takes 3 positional args - iteration count, PRD file path, and prompt file path\n- **Validation**: Checks that both files exist and iteration count is ≥ 1\n- **Execution**: Runs `claude --dangerously-skip-permissions --print --verbose --output-format=stream-json --chrome \"@PROMPT.md\"`\n- **Streaming**: Streams stdout/stderr in real-time while capturing for parsing\n- **Tag detection**: Checks for `<CLAUDE>DONE</CLAUDE>` or `<CLAUDE>BLOCKED: [explanation]</CLAUDE>`\n- **Exit conditions**:\n  - `DONE` tag → exit 0 (success)\n  - `BLOCKED` tag → print explanation, exit 1 (failure)\n  - Non-zero claude exit → exit 1 (failure)\n  - Max iterations reached → exit 1 (failure)\n- **Progress display**: Shows current iteration number before each run","session_id":"707c48df-3786-4b9f-ac05-a93054f0a542","total_cost_usd":0.26288449999999997,"usage":{"input_tokens":5,"cache_creation_input_tokens":30316,"cache_read_input_tokens":59073,"output_tokens":1587,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":30316}},"modelUsage":{"claude-haiku-4-5-20251001":{"inputTokens":2823,"outputTokens":270,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0.004173,"contextWindow":200000},"claude-opus-4-5-20251101":{"inputTokens":5,"outputTokens":1587,"cacheReadInputTokens":59073,"cacheCreationInputTokens":30316,"webSearchRequests":0,"costUSD":0.2587115,"contextWindow":200000}},"permission_denials":[],"uuid":"8c3330c7-fd46-4c5a-a871-f61865d7c398"}
```

If done, it should exit with success. If blocked, it should print the explanation and exit with failure. If the claude process exits with a non-zero exit code, stop the loop and exit with failure. If neither tag is present, it should increment the iteration count and repeat until the maximum iteration count is reached. If the maximum is reached without being done or blocked, it should exit with failure.

Create this script as a Python file named `claude_loop.py`. Use `python` as the shebang and make the file executable.
