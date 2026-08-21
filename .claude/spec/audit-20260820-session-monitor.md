# audit: 20260820-session-monitor(再監査)

監査日: 2026-08-20
対象 verdict: .claude/spec/verdict-20260820-session-monitor.md(コミット 2a578b3 で作り直し)
対象設計書: docs/archive/20260820_20260820-session-monitor.md
監査方法: 各 R-ID の記載コマンドを再実行し、記載の実測件数(-k の deselected 込み)・
file:line 証拠を Read で照合した。前回監査(NG 7件: R-001, R-007, R-008, R-009,
R-010, R-011, R-012)の指摘が解消したかを重点確認した。

## 監査結果

| ID | 結果 | 備考 |
|---|---|---|
| R-001 | OK | `-k gate_off` を再実行し `1 passed, 21 deselected` を確認。verdict の主張と一致。証拠 tests/test_session_monitor.py:116 の `test_gate_off_no_warning` を Read で確認済み。前回NG(2 passed 誤記)は解消。 |
| R-002 | OK | `-k below_warn` を再実行し `1 passed, 21 deselected` を確認。tests/test_session_monitor.py:147 `test_below_warn_threshold_silent` と一致。証拠確認済み。 |
| R-003 | OK | `-k warn_level` を再実行し `2 passed, 20 deselected` を確認。tests/test_session_monitor.py:157, 164 の関数名と一致。証拠確認済み。 |
| R-004 | OK | `-k high_level` を再実行し `1 passed, 21 deselected` を確認。tests/test_session_monitor.py:186 と一致。証拠確認済み。 |
| R-005 | OK | `-k dedup_silent` を再実行し `1 passed, 21 deselected` を確認。tests/test_session_monitor.py:198 と一致。証拠確認済み。 |
| R-006 | OK | `-k dedup_rewarns` を再実行し `1 passed, 21 deselected` を確認。tests/test_session_monitor.py:214 と一致。証拠確認済み。 |
| R-007 | OK | `-k compact_count` を再実行し `4 passed, 18 deselected` を確認。verdict の主張(4件、部分文字列一致による前方一致ヒットの説明含む)と一致。tests/test_session_monitor.py:230, 379, 396, 412 を Read で確認済み。前回NG(1 passed 誤記)は解消。 |
| R-008 | OK | `-k fail_open` を再実行し `6 passed, 16 deselected` を確認。verdict の主張と一致。tests/test_session_monitor.py:256, 265, 278, 292, 305, 412 を Read で確認済み。前回NG(4 passed 誤記)は解消。 |
| R-009 | OK | `-k threshold_env` を再実行し `1 passed, 21 deselected` を確認。証拠 tests/test_session_monitor.py:326 の `test_threshold_env_override` を Read で確認(前回NGだった行番号302の誤引用は326に修正済み)。 |
| R-010 | OK | `-k never_blocks` を再実行し `3 passed, 19 deselected` を確認(tests/test_session_monitor.py:342, 347, 352)。証拠に挙げた `.claude/hooks/session_monitor.py:62`(`_as_int` 定義)、`198・200`(`_as_int` の適用箇所)、`.claude/hooks/checkpoint_before_compact.py:46-49`(try/except fail-open)を Read で確認し、記載どおりの内容と一致(前回NGだった195/197誤引用は198/200に修正済み)。破損状態ファイルでの手動再現は、同一シナリオを検証する tests/test_session_monitor.py:412 `test_compact_counter_hook_fail_open_corrupted_state`(returncode==0 を assert)がリポジトリ内テストとして既に合格しており、記載内容と矛盾しない。 |
| R-011 | OK | `-k compact_counter_hook` を再実行し `3 passed, 19 deselected` を確認。verdict の主張と一致。tests/test_session_monitor.py:379, 396, 412 を Read で確認済み(前回NGだった355/372誤引用・2 passed誤記は解消)。 |
| R-012 | OK | `-k staging_idempotent` を再実行し `1 passed, 21 deselected` を確認。証拠 tests/test_session_monitor.py:442 の `test_staging_idempotent_apply_twice` を Read で確認(前回NGだった396誤引用は442に修正済み)。 |
| R-013 | NG | `diff <(...) <(...)` 自体は exit 0 で再現し、unique集合ベースでは claude-init.sh・claude-init.ps1 とも11件で一致する(機能面は問題なし)。しかし verdict の実測値記載「両方とも生・一意ともに11件で一致」は誤り。実測すると claude-init.ps1 側の生(raw)ヒット数は **12件**(`CLAUDE_CROSS_REVIEW` が settings hashtable 定義(118行目)に加え、無関係なコード行(142行目の `if ($var -eq "CLAUDE_CROSS_REVIEW" ...)`)にも一致してしまうため)であり、claude-init.sh 側の生11件と一致しない。`.claude/rules/consistency.md` が要求する「生・一意ともに報告」の趣旨に照らすと、verdict の生カウント記載(11件)は実測(12件)と食い違う。 |
| R-014 | OK | `grep -q '"CLAUDE_SESSION_MONITOR": "0"' templates/settings.local.json.template` を再実行し exit 0。該当行 templates/settings.local.json.template:10 を Read で確認済み(記載どおり)。 |
| R-015 | OK | `uv run --with pytest python -m pytest tests/ -q` を再実行し `178 passed`(exit 0)を確認。verdict の主張と一致。前回NG(176 passed 誤記)は解消。 |

## 前回NG(7件)の解消状況

| 前回NGのID | 前回の指摘内容 | 今回の結果 |
|---|---|---|
| R-001 | 件数誤記(2 passed→実測1 passed) | 解消(1 passed, 21 deselected で一致) |
| R-007 | 件数誤記(1 passed→実測4 passed) | 解消(4 passed, 18 deselected で一致) |
| R-008 | 件数誤記(4 passed→実測6 passed) | 解消(6 passed, 16 deselected で一致) |
| R-009 | file:line誤引用(302→実際は326) | 解消(326に修正済み) |
| R-010 | file:line誤引用(195/197→実際は198/200) | 解消(198/200に修正済み) |
| R-011 | 件数誤記(2 passed→実測3 passed)・file:line誤引用(355/372) | 解消(3 passed, 19 deselected・379/396/412に修正済み) |
| R-012 | file:line誤引用(396→実際は442) | 解消(442に修正済み) |

7件全て解消を確認した。ただし今回の再検証で**新規に** R-013 に生カウントの誤記(12件を11件と記載)を検出した(前回監査ではこの誤記は指摘されていなかった)。

## スコープ外変更

`git diff --stat main...HEAD -- .` を再確認したところ、変更ファイル一覧は前回監査時と同一であり、
新規のスコープ外変更は無い。

- `.claude/hooks/checkpoint_before_compact.py`(R-011 該当)
- `.claude/hooks/session_monitor.py`(R-001〜R-010 該当)
- `.claude/plans/20260820-session-monitor.md`(実装計画。作業過程物)
- `.claude/settings.json`(Stop フック登録。スコープ「やること」該当だが専用のR-IDなし)
- `.claude/skills/config-explain/SKILL.md`, `.claude/skills/config-set/SKILL.md`(スコープ「README・スキルの整合」該当だが専用のR-IDなし)
- `.claude/spec/audit-20260820-session-monitor.md`(前回監査結果。本監査で上書き)
- `.claude/spec/verdict-20260820-session-monitor.md`(本再監査対象そのもの)
- `README.md`(スコープ記載あり)
- `claude-init.ps1`, `claude-init.sh`(R-013 該当)
- `templates/settings.local.json.template`(R-014 該当)
- `tests/test_session_monitor.py`(R-001〜R-012 該当)
- `verify-installers.sh`(スコープ「claude-init 配線」の検証スクリプト。専用のR-IDなし)

いずれも設計書3節「やること」に明記された作業の範囲内であり、無関係な変更は無い。
「スコープ外変更」として報告すべき項目は**なし**。

## 総括

15件中 OK 14件(R-001〜R-012, R-014, R-015)、NG 1件(R-013)。

前回監査で指摘した記載精度NG 7件(R-001, R-007, R-008, R-009, R-010, R-011, R-012)は
全て解消を確認した。件数(-k の deselected 込み)・file:line 証拠とも、今回再実行・
Read で照合した限り記載どおりであった。

新規に検出した問題は R-013 のみ: verdict は「生・一意ともに11件で一致」と記載しているが、
実測すると claude-init.ps1 側の生ヒット数は12件(設定用ハッシュテーブルの定義行に加え、
機能とは無関係なコード行 `if ($var -eq "CLAUDE_CROSS_REVIEW" ...)` にも grep パターンが
一致するため)であり、claude-init.sh 側の11件と食い違う。unique集合ベースの比較
(実質的な1対1対応チェック)自体は exit 0 で通っており機能上の欠陥ではないが、
`.claude/rules/consistency.md` が要求する「生・一意ともに報告」の趣旨に照らすと、
verdict に記載された実測値(生11件)がそのまま再現しないため NG とする。

機能そのもの(exit code・PASS/FAIL の結果自体)は R-001〜R-015 いずれも問題なく、
挙動面の重大な欠陥は見つかっていない。R-013 の是正(生カウントの正確な記載への
訂正、または grep パターンをコード無関係行に一致しないよう絞る対応の要否検討)を
evaluator に差し戻すことを推奨する。
