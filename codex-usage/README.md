# codex-usage

Small utility to pull the Codex `/status` usage card without interactive work and emit JSON or compact text.

## Usage

```bash
python codex-usage/codex-usage.py --pretty
```

Watch mode:

```bash
python codex-usage/codex-usage.py --watch 60 --pretty --no-raw
```

NDJSON stream mode:

```bash
python codex-usage/codex-usage.py --watch 60 --ndjson --no-raw
```

Pretty output example:

```text
2026-03-27T10:00:00Z | global: 5h=100% reset=16:07, Weekly=100% reset=12:07 on 3 Apr | GPT-5.3-Codex-Spark: 5h=97% reset=16:08, Weekly=98% reset=12:08 on 3 Apr
```

JSON output example (trimmed):

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
- `--watch N` emits one snapshot every `N` seconds until interrupted.
- `--pretty` emits a compact single-line human-readable summary per snapshot.
- `--ndjson` forces one compact JSON object per line.
- It is intentionally light and independent: no extra dependencies.
