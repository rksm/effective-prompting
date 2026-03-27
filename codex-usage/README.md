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

Multiple Codex accounts:

```bash
python codex-usage/codex-usage.py \
  --codex-home ~/.codex-work \
  --codex-home ~/.codex-personal \
  --pretty --no-raw
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

### Multiple Accounts

When multiple `--codex-home` directories are provided, the output includes separate entries for each account. The `status_info.account` field indicates the account name and type (e.g., Pro, Free) for each snapshot.

```shell
python codex-usage/codex-usage.py --pretty --no-raw --watch 60 --codex-home ~/.codex --codex-home ~/.codex-private
```

## Notes

- Parses rendered terminal output from the interactive `codex` process.
- Works well for non-interactive scheduled checks (cron/systemd timers).
- `--codex-home DIR` is repeatable. Each directory should be a full `CODEX_HOME` containing at least `auth.json`.
- `--watch N` emits one snapshot every `N` seconds until interrupted.
- `--pretty` emits a compact single-line human-readable summary per snapshot.
- `--ndjson` forces one compact JSON object per line.
- Disables the `chrome-devtools` MCP server for polling runs by default.
- Replies to Codex terminal capability/color probes inside the PTY to reduce automation startup latency.
- It is intentionally light and independent: no extra dependencies.
