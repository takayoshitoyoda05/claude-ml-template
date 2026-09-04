# Verdict: 20260904-skill-state-spec

評価対象: `docs/active/20260904-skill-state-spec.md` の受け入れ条件(R-001〜R-017)
計画: `.claude/plans/20260904-skill-state.md`

評価時点: `pipeline/20260904-skill-state` ブランチ、staging 適用済み(コミット
`68d4882`)。全体テストは `uv run --with pytest python -m pytest tests/ -q` で
**298 passed, 16 skipped**(`logs/runs/eval_full_regression.log`)。失敗0。

| ID | 判定 | 実行コマンド | 実測値 | 証拠(file:line) |
|---|---|---|---|---|
| R-001 | PASS | `grep -n 'state/' .claude/commands/ml-pipeline.md` | 143行目「ブランチ作成後、`.claude/state/<slug>.json` に初期状態を作成する」がヒット | `.claude/commands/ml-pipeline.md:143` |
| R-002 | PASS | `grep -c 'current_step' .claude/commands/ml-pipeline.md` | 2 | `.claude/commands/ml-pipeline.md:146, 280` |
| R-003 | PASS | `uv run --with pytest python -m pytest tests/test_state_gate.py -q -k valid` | 13 passed, 10 deselected(`logs/runs/eval_state_gate_k_valid.log`) | `.claude/hooks/state_gate.py:189-198`、`tests/test_state_gate.py:93` |
| R-004 | PASS | 同 `-k invalid` | 5 passed, 18 deselected(`logs/runs/eval_state_gate_k_invalid.log`) | `.claude/hooks/state_gate.py:97-139`、`tests/test_state_gate.py:194` |
| R-005 | PASS | 同 `-k unknown_key` | 2 passed, 21 deselected(`logs/runs/eval_state_gate_k_unknown_key.log`) | `.claude/hooks/state_gate.py:90-92`、`tests/test_state_gate.py:258` |
| R-006 | PASS | 同 `-k notes_limit` | 2 passed, 21 deselected(`logs/runs/eval_state_gate_k_notes_limit.log`) | `.claude/hooks/state_gate.py:104-105`、`tests/test_state_gate.py:284` |
| R-007 | PASS | 同 `-k fail_open` | 2 passed, 21 deselected(`logs/runs/eval_state_gate_k_fail_open.log`) | `.claude/hooks/state_gate.py:216-221`、`tests/test_state_gate.py:304` |
| R-008 | PASS | `uv run --with pytest python -m pytest tests/test_reinject_state.py -q -k compact` | 5 passed, 5 deselected(`logs/runs/eval_reinject_k_compact.log`) | `.claude/hooks/reinject_after_compact.py:25, 92-94`、`tests/test_reinject_state.py:101`(出現順まで検査) |
| R-009 | PASS | 同 `-k startup` | 5 passed, 5 deselected(`logs/runs/eval_reinject_k_startup.log`) | `.claude/hooks/resume_session_state.py:28, 92-100` |
| R-010 | PASS | 同 `-k broken` | 6 passed, 4 deselected(`logs/runs/eval_reinject_k_broken.log`) | `.claude/hooks/reinject_after_compact.py:46-76`(3分岐: ok/broken/missing_with_plan/silent)、`.claude/hooks/resume_session_state.py:57-89`(同3分岐) |
| R-011 | PASS | `uv run --with pytest python -m pytest tests/test_state_freshness.py -q` | 6 passed(`logs/runs/eval_freshness.log`) | `.claude/hooks/record_session_state.py:250-296`(`_age_minutes`/`_freshness_warning`)、`tests/test_state_freshness.py:109, 121, 131` |
| R-012 | PASS | `grep -n '実行状態スナップショット' .claude/skills/handoff/SKILL.md` | 19, 57行目にヒット | `.claude/skills/handoff/SKILL.md:19` |
| R-013 | PASS | `grep -n 'state/' .claude/commands/ml-pipeline.md`(手順9節) | 750行目「マージ後、サブブランチを削除する。また `.claude/state/<slug>.json` を削除する」 | `.claude/commands/ml-pipeline.md:750` |
| R-014 | PASS | `grep -l 'from plan_gate import _slug_from_branch' .claude/hooks/state_gate.py .claude/hooks/reinject_after_compact.py .claude/hooks/resume_session_state.py` | 3ファイル全てヒット。`grep -n '\-group\-' <同3ファイル>` は0件(exit 1) | `.claude/hooks/state_gate.py:27`、`.claude/hooks/reinject_after_compact.py:23`、`.claude/hooks/resume_session_state.py:23` |
| R-015 | PASS | `git check-ignore .claude/state/dummy.json` | exit 0(`.claude/state/dummy.json` を出力) | `.gitignore:2-3` |
| R-016 | PASS | `grep -c 'state_gate' .claude/settings.json` | 1(二重登録なし)。`uv run python -m json.tool .claude/settings.json` → exit 0 | `.claude/settings.json:53`(matcher `Edit\|Write\|NotebookEdit` 配下) |
| R-017 | UNVERIFIABLE | (目視・manual) | ユーザー承認は未実施(計画の作業ログでも「Step 9: R-017目視確認は保留」と明記)。evaluator は承認しない | `.claude/plans/20260904-skill-state.md:228`(計画ステップ対応表 Step 9 の備考) |

## 補足検証

- 回帰: `uv run --with pytest python -m pytest tests/ -q` → 298 passed, 16 skipped、失敗0
  (`logs/runs/eval_full_regression.log`)。skip はいずれも本変更と無関係な既存の環境系skip。
- mypy: `uv run mypy --version` がエラー(未導入)のためスキップ。
- 計画の PC-13(`_staging_skill_state.py` の冪等性)について、計画の「検証方法」表が
  指定する `uv run python -m pytest tests/test_state_gate.py -q -k idempotent` を実行した
  ところ `23 deselected` で **exit 5**(該当テストが1件も存在しない)。設計書の
  受け入れ条件表(R-001〜R-017)自体には冪等性の独立ID(R-016は配線件数のみを要求)は
  無いため R-016 判定はPASSとしたが、計画が自ら約束した検証コマンドが実行不能である点は
  「問題点」に HIGH として記載した(下記)。

## 判定: NEEDS_REVISION

R-001〜R-016 は PASS、R-017 は manual 未承認のため UNVERIFIABLE。設計書の受け入れ条件
そのものは実測値と一致しているが、計画自身の PC-13(冪等性)・検証方法表「冪等性」行を
満たす自動テストが存在せず、計画の宣言と実装が食い違っているため NEEDS_REVISION とする
(詳細は完了報告参照)。
