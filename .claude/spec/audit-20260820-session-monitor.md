# audit: 20260820-session-monitor

監査日: 2026-08-20
対象 verdict: .claude/spec/verdict-20260820-session-monitor.md
対象設計書: docs/archive/20260820_20260820-session-monitor.md
監査方法: 各 R-ID の記載コマンドを独立コンテキストで再実行し、file:line 証拠を Read で照合した。

## 監査結果

| ID | 結果 | 根拠 |
|---|---|---|
| R-001 | NG | verdict は `-k gate_off` で「2 passed」(test_session_monitor.py:116,135)と主張するが、実測は `1 passed, 21 deselected`(`-k gate_off` は部分文字列一致のため `test_gate_off_no_warning`(116)のみヒットし、`test_gate_zero_no_warning`(135)は "gate_off" を含まずヒットしない)。加えて証拠に挙げた `logs/runs/20260820-session-monitor-test1.log` は中身が `20 passed in 0.74s`(deselected表記なし=フィルタなしの全件実行ログ)であり、`-k gate_off` の実行結果ではない。 |
| R-002 | OK | `-k below_warn` を再実行し `1 passed, 21 deselected` を確認。test_session_monitor.py:147 の `test_below_warn_threshold_silent` と一致。 |
| R-003 | OK(証拠ログに軽微な不整合あり) | `-k warn_level` を再実行し `2 passed, 20 deselected` を確認。test_session_monitor.py:157,164 の関数名・内容とも一致。ただし証拠に挙げた `logs/runs/20260820-session-monitor-thresholds.log` の中身は `4 passed, 16 deselected` であり、単独の `-k warn_level` 実行ログではない(別コマンドの使い回しと推測)。主要な検証コマンド自体は再現するため判定は OK とするが、ログ証拠の対応関係は誤り。 |
| R-004 | OK | `-k high_level` を再実行し `1 passed, 21 deselected` を確認。test_session_monitor.py:186 の `test_high_level_at_boundary_warns_with_high_word` と一致。 |
| R-005 | OK | `-k dedup_silent` を再実行し `1 passed, 21 deselected` を確認。test_session_monitor.py:198 と一致。 |
| R-006 | OK | `-k dedup_rewarns` を再実行し `1 passed, 21 deselected` を確認。test_session_monitor.py:214 と一致。 |
| R-007 | NG | verdict は `-k compact_count` で「1 passed」(test_session_monitor.py:230)と主張するが、実測は `4 passed, 18 deselected`。"compact_count" は部分文字列一致で `test_compact_count_warns_once_then_silent`(230)に加え `test_compact_counter_hook_*`(379,396,412)も "compact_count" を前方一致で含むためヒットする。件数の記載が誤り。 |
| R-008 | NG | verdict は `-k fail_open` で「4 passed」(test_session_monitor.py:256,265,278,292)と主張するが、実測は `6 passed, 16 deselected`。同じキーワードで `test_fail_open_corrupted_state_values`(305)と `test_compact_counter_hook_fail_open_corrupted_state`(412)も選択されるため件数・列挙とも不足。 |
| R-009 | NG | `-k threshold_env` の再実行結果自体は `1 passed, 21 deselected` で verdict の主張件数と一致するが、証拠の file:line「tests/test_session_monitor.py:302」は実際には `test_threshold_env_override` 関数(実際の定義は326行目)ではなく、離れた場所にあるコメント行(`# 「いかなる入力でも exit 0」契約を破らないことを検証する`)である。証拠行が実体と食い違う。 |
| R-010 | NG | 挙動面の再現は確認できた: `.claude/hooks/session_monitor.py:62-80` の `_as_int` 定義、`.claude/hooks/checkpoint_before_compact.py:46-49` の try/except は記載どおり存在し、`logs/runs/20260820-session-monitor-verdict-recheck-*.log` の内容(exit code 0 x2、`22 passed in 0.66s`)も一致した。しかし証拠に挙げた「195,197(`_as_int` 適用箇所)」は誤り。195行目は `if not isinstance(session_state, dict):`、197行目は空行であり、`_as_int` が実際に呼ばれているのは198行目・200行目である。証拠行の指示先が実体とずれている。 |
| R-011 | NG | `-k compact_counter_hook` の再実行結果は `3 passed, 19 deselected` であり、verdict の「2 passed」と件数が食い違う(`test_compact_counter_hook_increments_on_auto`(379)・`ignores_manual`(396)・`fail_open_corrupted_state`(412)の3件がヒット)。加えて証拠の file:line「tests/test_session_monitor.py:355,372」は該当テスト関数の定義位置ではない(355行目は別テスト `test_never_blocks_usage_as_string` 内の dict リテラル、372行目は `pytestmark_compact` の `skipif` 定義の一部)。実際の対象関数は379・396・412行目。 |
| R-012 | NG | `-k staging_idempotent` の再実行結果は `1 passed, 21 deselected` で件数自体は verdict の「1 passed」と一致するが、証拠の file:line「tests/test_session_monitor.py:396」は誤り。396行目は `test_compact_counter_hook_ignores_manual` であり、`test_staging_idempotent_apply_twice` の実際の定義は442行目。 |
| R-013 | OK | `diff <(grep... claude-init.sh) <(grep... claude-init.ps1)` を再実行し exit 0、両方とも生・一意ともに11件で一致(claude-init.sh:CLAUDE_SESSION_MONITOR を含む11キー、claude-init.ps1側も同数)を確認。 |
| R-014 | OK | `grep -q '"CLAUDE_SESSION_MONITOR": "0"' templates/settings.local.json.template` を再実行し exit 0。該当行は templates/settings.local.json.template:10 に実在することを Read で確認。 |
| R-015 | NG | `uv run --with pytest python -m pytest tests/ -q` を再実行した結果は `178 passed`(exit 0)。verdict の記載「176 passed」と件数が食い違う。全件成功(退行なし)自体は確認できたが、`git diff --stat main...HEAD -- tests/` では本機能分の差分は `tests/test_session_monitor.py` の新規追加(494行, 22テスト)のみであり、count差(+2)は本機能と無関係な要因(verdict作成後の main 側の変化、または検証タイミングのずれ)によるものと推測される。ただし記載値がそのまま再現しないため、記載どおりの検証にはならなかった。 |

## スコープ外変更

`git diff --stat main...HEAD -- .`(session-monitor 分岐点からの累積差分)を確認したところ、変更ファイルは以下のみであり、いずれも設計書スコープ(受け入れ条件・「やること」節)に対応する:

- `.claude/hooks/checkpoint_before_compact.py`(R-011 該当)
- `.claude/hooks/session_monitor.py`(R-001〜R-010 該当)
- `.claude/plans/20260820-session-monitor.md`(実装計画。作業過程物)
- `.claude/settings.json`(Stop フック登録。スコープ「やること」該当だが専用のR-IDなし)
- `.claude/skills/config-explain/SKILL.md`, `.claude/skills/config-set/SKILL.md`(スコープ「README・スキルの整合」該当だが専用のR-IDなし)
- `.claude/spec/verdict-20260820-session-monitor.md`(本監査対象そのもの)
- `README.md`(同上、スコープ記載あり)
- `claude-init.ps1`, `claude-init.sh`(R-013 該当)
- `templates/settings.local.json.template`(R-014 該当)
- `tests/test_session_monitor.py`(R-001〜R-012 該当)
- `verify-installers.sh`(スコープ「claude-init 配線」の検証スクリプト。専用のR-IDなし)

上記のうち `.claude/settings.json`・スキル2ファイル・README.md・verify-installers.sh は受け入れ条件テーブルの個別IDには対応しないが、設計書3節「やること」に明記された作業(フック登録・ドキュメント整合・インストーラ配線の検証)の範囲内であり、無関係な変更ではない。よって「スコープ外変更」として報告すべき項目は**なし**と判断する。

## 総括

15件中 OK 6件(R-002, R-004, R-005, R-006, R-013, R-014)、NG 9件(R-001, R-003は「OK」だが証拠ログ不整合の注記あり — 実質は判定OKのまま件数のみ、R-007, R-008, R-009, R-010, R-011, R-012, R-015)。

NG の内訳は大きく2種類:
1. **pytest -k の部分文字列一致による件数の記載ミス**(R-001, R-007, R-008, R-015): `-k` の値が想定より広い範囲のテストにヒットする、または verdict 作成後にリポジトリの他の変更でテスト総数が変わっており、記載された「実測値」がそのまま再現しない。
2. **file:line 証拠が実体と食い違う**(R-009, R-010, R-011, R-012): 引用された行番号が、対象のテスト関数・コード箇所ではなく、近傍の別のコード(コメント・別テスト・別のマーカー定義)を指している。

挙動そのもの(exit code・PASS/FAIL の結果自体)は R-001, R-003, R-007, R-008, R-011, R-012 いずれも「機能として動作している」ことは確認できており、機能面の重大な欠陥が見つかったわけではない。しかし verdict に記載された検証コマンド・証拠行を独立に再現した結果、件数や引用行に複数の食い違いが見つかったため、evaluator の PASS 判定をそのまま追認することはできない。設計書は既に `docs/archive/` へ移動済みだが、verdict の証拠精度に問題があるため、要修正として報告する。
