# codex-usage

Small utility to pull the Codex `/status` usage card without interactive work and emit JSON.

## Usage

```bash
python codex-usage/codex-usage.py --pretty
```

Watch mode:

```bash
python codex-usage/codex-usage.py --watch 60 --no-raw
```

Example output (trimmed):

```json
{
  "retrieved_at": "2026-03-27T10:00:00Z",
  "status_info": {
    "model": "gpt-5.3-codex-spark",
    "directory": "~/projects/...",
    "account": "dev@... (Pro)"
  },
  "limits_by_scope": {
    "global": [
      {
        "window": "5h",
        "percent_left": 100,
        "resets": "16:07"
      }
    ],
    "gpt-5.3-Codex-Spark": [
      {
        "window": "5h",
        "percent_left": 97,
        "resets": "16:08"
      }
    ]
  }
}
```

## Notes

- Parses rendered terminal output from the interactive `codex` process.
- Works well for non-interactive scheduled checks (cron/systemd timers).
- `--watch N` emits one JSON snapshot every `N` seconds until interrupted.
- It is intentionally light and independent: no extra dependencies.
