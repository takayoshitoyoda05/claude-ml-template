# verdict: 20260820-session-monitor

判定日: 2026-08-20(spec-auditor 監査 NG 7件を受けて証拠を再検証・作り直し)
参照設計書: docs/archive/20260820_20260820-session-monitor.md
参照計画: .claude/plans/20260820-session-monitor.md
参照監査: .claude/spec/audit-20260820-session-monitor.md
再検証ログ: logs/runs/20260820_174854-session-monitor-verdict-remake.log

注記: 実装は変更していない(監査は「機能は全件再現済み」と確認済み)。
本改訂は verdict の実測件数と file:line 証拠の記載精度のみを修正する。
`-k` は部分文字列一致のため、キーワードが他のテスト名の一部にも一致する
場合は該当する全テストがヒットする。以下の表ではヒットしたテスト名を
根拠列に明記する。

| ID | 判定 | 実行コマンド | 実測値 | 証拠(file:line) |
|---|---|---|---|---|
| R-001 | PASS | `uv run --with pytest python -m pytest tests/test_session_monitor.py -q -k gate_off` | 1 passed, 21 deselected | tests/test_session_monitor.py:116(`test_gate_off_no_warning`)。`test_gate_zero_no_warning`(135)は "gate_off" を含まないためヒットしない |
| R-002 | PASS | 同上 `-k below_warn` | 1 passed, 21 deselected | tests/test_session_monitor.py:147(`test_below_warn_threshold_silent`) |
| R-003 | PASS | 同上 `-k warn_level` | 2 passed, 20 deselected | tests/test_session_monitor.py:157(`test_warn_level_at_boundary_warns`), 164(`test_warn_level_multiple_assistant_lines_uses_last`) |
| R-004 | PASS | 同上 `-k high_level` | 1 passed, 21 deselected | tests/test_session_monitor.py:186(`test_high_level_at_boundary_warns_with_high_word`) |
| R-005 | PASS | 同上 `-k dedup_silent` | 1 passed, 21 deselected | tests/test_session_monitor.py:198(`test_dedup_silent_below_ten_percent`) |
| R-006 | PASS | 同上 `-k dedup_rewarns` | 1 passed, 21 deselected | tests/test_session_monitor.py:214(`test_dedup_rewarns_above_ten_percent`) |
| R-007 | PASS | 同上 `-k compact_count` | 4 passed, 18 deselected | "compact_count" が `test_compact_counter_hook_*` の前方一致でもヒットするため4件: tests/test_session_monitor.py:230(`test_compact_count_warns_once_then_silent`), 379(`test_compact_counter_hook_increments_on_auto`), 396(`test_compact_counter_hook_ignores_manual`), 412(`test_compact_counter_hook_fail_open_corrupted_state`) |
| R-008 | PASS | 同上 `-k fail_open` | 6 passed, 16 deselected | tests/test_session_monitor.py:256(`test_fail_open_missing_transcript_path`), 265(`test_fail_open_unreadable_transcript_path`), 278(`test_fail_open_no_usage_key`), 292(`test_fail_open_empty_jsonl`), 305(`test_fail_open_corrupted_state_values`), 412(`test_compact_counter_hook_fail_open_corrupted_state`。"fail_open" を含むためヒット) |
| R-009 | PASS | 同上 `-k threshold_env` | 1 passed, 21 deselected | tests/test_session_monitor.py:326(`test_threshold_env_override`) |
| R-010 | PASS | 同上 `-k never_blocks`(設計書記載の検証方法)。加えて破損値状態ファイル(`{'sess-x': {'compact_count': 'oops'}}`)を与えて session_monitor.py と checkpoint_before_compact.py(trigger=auto)を再現実行 | `-k never_blocks`: 3 passed, 19 deselected(tests/test_session_monitor.py:342 `test_never_blocks_malformed_json_stdin`, 347 `test_never_blocks_empty_stdin`, 352 `test_never_blocks_usage_as_string`)。手動再現: 両フックとも returncode=0(トレースバックなし) | .claude/hooks/session_monitor.py:62(`_as_int` 定義), 198・200(`_as_int` の適用箇所: `compact_count`・`last_warned_tokens` の変換); .claude/hooks/checkpoint_before_compact.py:46-49(try/except による int 変換の fail-open); tests/test_session_monitor.py:342,347,352,305,412; logs/runs/20260820_174854-session-monitor-verdict-remake.log |
| R-011 | PASS | 同上 `-k compact_counter_hook` | 3 passed, 19 deselected | tests/test_session_monitor.py:379(`test_compact_counter_hook_increments_on_auto`), 396(`test_compact_counter_hook_ignores_manual`), 412(`test_compact_counter_hook_fail_open_corrupted_state`) |
| R-012 | PASS | 同上 `-k staging_idempotent` | 1 passed, 21 deselected | tests/test_session_monitor.py:442(`test_staging_idempotent_apply_twice`) |
| R-013 | PASS | `diff <(grep -oE '"CLAUDE_[A-Z_]+\|' claude-init.sh \| tr -d '"\|' \| sort -u) <(grep -oE '"CLAUDE_[A-Z_]+"' claude-init.ps1 \| tr -d '"' \| sort -u)` | exit 0。生: sh=11 / ps1=12(ps1 の1件は claude-init.ps1:142 の比較コード `-eq "CLAUDE_CROSS_REVIEW"` への一致で、機能定義ではない。`sort -u` で吸収)。一意: 両方11件で一致(監査指摘に基づきリーダーが実測訂正 2026-08-20) | claude-init.sh:136(`CLAUDE_SESSION_MONITOR`); claude-init.ps1:128(`CLAUDE_SESSION_MONITOR`) |
| R-014 | PASS | `grep -q '"CLAUDE_SESSION_MONITOR": "0"' templates/settings.local.json.template` | exit 0 | templates/settings.local.json.template:10 |
| R-015 | PASS | `uv run --with pytest python -m pytest tests/ -q` | 178 passed | logs/runs/20260820_174854-session-monitor-verdict-remake.log |
