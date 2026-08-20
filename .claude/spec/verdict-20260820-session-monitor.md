# verdict: 20260820-session-monitor

判定日: 2026-08-20
参照設計書: docs/active/20260820-session-monitor.md
参照計画: .claude/plans/20260820-session-monitor.md

| ID | 判定 | 実行コマンド | 実測値 | 証拠(file:line) |
|---|---|---|---|---|
| R-001 | PASS | `uv run --with pytest python -m pytest tests/test_session_monitor.py -q -k gate_off` | 2 passed | tests/test_session_monitor.py:116,135; logs/runs/20260820-session-monitor-test1.log |
| R-002 | PASS | 同上 `-k below_warn` | 1 passed | tests/test_session_monitor.py:147 |
| R-003 | PASS | 同上 `-k warn_level` | 2 passed | tests/test_session_monitor.py:157,164; logs/runs/20260820-session-monitor-thresholds.log |
| R-004 | PASS | 同上 `-k high_level` | 1 passed | tests/test_session_monitor.py:186 |
| R-005 | PASS | 同上 `-k dedup_silent` | 1 passed | tests/test_session_monitor.py:198 |
| R-006 | PASS | 同上 `-k dedup_rewarns` | 1 passed | tests/test_session_monitor.py:214 |
| R-007 | PASS | 同上 `-k compact_count` | 1 passed | tests/test_session_monitor.py:230 |
| R-008 | PASS | 同上 `-k fail_open` | 4 passed | tests/test_session_monitor.py:256,265,278,292 |
| R-009 | PASS | 同上 `-k threshold_env` | 1 passed | tests/test_session_monitor.py:302; logs/runs/20260820-session-monitor-thresholds.log |
| R-010 | FAIL | `python3 .claude/hooks/session_monitor.py`(compact_count が非数値文字列の状態ファイルを与えて再現) | returncode=1、`ValueError: invalid literal for int() with base 10: 'oops'` の未捕捉トレースバック | .claude/hooks/session_monitor.py:177,179(int(...)がtry/except外) |
| R-011 | PASS | 同上 `-k compact_counter_hook` | 2 passed | tests/test_session_monitor.py:355,372 |
| R-012 | PASS | 同上 `-k staging_idempotent` | 1 passed | tests/test_session_monitor.py:396 |
| R-013 | PASS | `diff <(...) <(...)` in `.worktrees/group-B` | exit 0、両方11件(生・一意とも一致) | claude-init.sh:136; claude-init.ps1:128 |
| R-014 | PASS | `grep -q '"CLAUDE_SESSION_MONITOR": "0"' templates/settings.local.json.template` | exit 0 | templates/settings.local.json.template:10 |
| R-015 | PASS | `uv run --with pytest python -m pytest tests/ -q` | 176 passed | logs/runs/20260820-session-monitor-full.log |
