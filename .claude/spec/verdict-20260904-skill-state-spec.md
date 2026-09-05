# Verdict: 20260904-skill-state-spec

評価対象: `docs/active/20260904-skill-state-spec.md` の受け入れ条件(R-001〜R-017)
計画: `.claude/plans/20260904-skill-state.md`
差し戻し2回目の再評価。前回 NEEDS_REVISION の唯一の HIGH 指摘
(PC-13冪等性テスト `-k idempotent` が0件・exit 5)の解消を確認する。

評価時点: `pipeline/20260904-skill-state` ブランチ、staging 再適用済み
(コミット `6de1a82`。冪等性テスト追加は `ca7e2d0`)。全体テストは
`uv run --with pytest python -m pytest tests/ -q` で **299 passed, 16 skipped**
(`logs/runs/eval_skillstate_20260905_160315.log`)。失敗0。

| ID | 判定 | 実行コマンド | 実測値 | 証拠(file:line) |
|---|---|---|---|---|
| R-001 | PASS | `grep -n 'state/' .claude/commands/ml-pipeline.md` | 143行目「ブランチ作成後、`.claude/state/<slug>.json` に初期状態を作成する」がヒット | `.claude/commands/ml-pipeline.md:143` |
| R-002 | PASS | `grep -c 'current_step' .claude/commands/ml-pipeline.md` | 2 | `.claude/commands/ml-pipeline.md:280` |
| R-003 | PASS | `uv run --with pytest python -m pytest tests/test_state_gate.py -q -k valid` | 13 passed, 11 deselected(`logs/runs/eval_skillstate_20260905_160315.log`) | `.claude/hooks/state_gate.py:56`(`_slug_from_branch` 呼び出し)、`tests/test_state_gate.py` |
| R-004 | PASS | 同 `-k invalid` | 5 passed, 19 deselected(同ログ) | `.claude/hooks/state_gate.py` |
| R-005 | PASS | 同 `-k unknown_key` | 2 passed, 22 deselected(同ログ) | `.claude/hooks/state_gate.py` |
| R-006 | PASS | 同 `-k notes_limit` | 2 passed, 22 deselected(同ログ) | `.claude/hooks/state_gate.py` |
| R-007 | PASS | 同 `-k fail_open` | 2 passed, 22 deselected(同ログ) | `.claude/hooks/state_gate.py:202`(`except Exception:` fail-open 分岐) |
| R-008 | PASS | `uv run --with pytest python -m pytest tests/test_reinject_state.py -q -k compact` | 5 passed, 5 deselected(同ログ) | `.claude/hooks/reinject_after_compact.py:29`(`_state_section` 関数、`_state_common` 実装を共有) |
| R-009 | PASS | 同 `-k startup` | 5 passed, 5 deselected(同ログ) | `.claude/hooks/resume_session_state.py:38`(`_state_section` 関数) |
| R-010 | PASS | 同 `-k broken` | 6 passed, 4 deselected(同ログ) | `.claude/hooks/reinject_after_compact.py`・`.claude/hooks/resume_session_state.py`(3分岐: ok/broken/missing_with_plan/silent、リファクタ後も維持) |
| R-011 | PASS | `uv run --with pytest python -m pytest tests/test_state_freshness.py -q` | 6 passed(同ログ) | `.claude/hooks/record_session_state.py:250`(`_age_minutes`)、`:265`(`_freshness_warning`)、`:20`(`from datetime import datetime` — `timezone` 未使用importは除去済み) |
| R-012 | PASS | `grep -n '実行状態スナップショット' .claude/skills/handoff/SKILL.md` | 19, 57行目にヒット | `.claude/skills/handoff/SKILL.md:19` |
| R-013 | PASS | `grep -n 'state/' .claude/commands/ml-pipeline.md`(手順9節) | 750行目「マージ後、サブブランチを削除する。また `.claude/state/<slug>.json` を削除する」 | `.claude/commands/ml-pipeline.md:750` |
| R-014 | PASS | `grep -l 'from plan_gate import _slug_from_branch' .claude/hooks/state_gate.py .claude/hooks/reinject_after_compact.py .claude/hooks/resume_session_state.py` | 3ファイル全てヒット。`grep -n '\-group\-' <同3ファイル>` は0件(exit 1) | `.claude/hooks/state_gate.py:28`、`.claude/hooks/reinject_after_compact.py:25`、`.claude/hooks/resume_session_state.py:22` |
| R-015 | PASS | `git check-ignore .claude/state/dummy.json` | exit 0(`.claude/state/dummy.json` を出力) | `.gitignore:19` |
| R-016 | PASS | `grep -c 'state_gate' .claude/settings.json` | 1(二重登録なし)。`uv run python -m json.tool .claude/settings.json` → exit 0。PC-13冪等性: `uv run --with pytest python -m pytest tests/test_state_gate.py -q -k idempotent` → **1 passed, 23 deselected**(exit 0、前回の exit 5 から解消) | `.claude/settings.json`(matcher `Edit\|Write\|NotebookEdit` 配下)、`_staging_skill_state.py:838`(`already = any(...)` 重複チェック)、`tests/test_state_gate.py::test_staging_idempotent_apply_twice` |
| R-017 | UNVERIFIABLE | (目視・manual) | ユーザー承認は未実施(前回同様、保留中)。evaluator は承認しない | `.claude/plans/20260904-skill-state.md:339`(計画ステップ対応表、Step 8/9 未実施) |

## 補足検証

- 回帰: `uv run --with pytest python -m pytest tests/ -q` → 299 passed, 16 skipped、失敗0
  (`logs/runs/eval_skillstate_20260905_160315.log`)。skip はいずれも本変更と無関係な
  既存の環境系skip。
- 前回 HIGH 指摘(PC-13冪等性テスト欠落・`-k idempotent` が0件・exit 5)の解消を確認:
  `tests/test_state_gate.py::test_staging_idempotent_apply_twice`(コミット `ca7e2d0` で追加)
  が `-k idempotent` で選択され、1 passed で exit 0(`logs/runs/eval_skillstate_20260905_160315.log`)。
- リファクタ(`_state_common.py` への `_current_branch`/`_state_section` 集約、
  コミット `6de1a82`)後も R-008〜R-011 の該当テストが全て PASS することを確認済み
  (上表参照)。挙動変化なし。
- F401(`timezone` 未使用import)は `.claude/hooks/record_session_state.py:20` で
  `from datetime import datetime` のみとなっており解消を確認
  (`uv run ruff check .claude/hooks/` → `All checks passed!`、
  `logs/runs/eval_skillstate_grep_20260905_160344.log`)。
- mypy: `uv run mypy --version` がエラー(未導入)のためスキップ。
- grep系検証(slug複製禁止・settings.json配線件数・ml-pipeline/handoff見出し)は全て
  計画の「検証方法」表どおりの結果(`logs/runs/eval_skillstate_grep_20260905_160344.log`)。

## 判定: PASS

R-001〜R-016 は PASS、R-017 は manual 未承認のため UNVERIFIABLE(変更なし)。
前回差し戻しの唯一の HIGH 根拠(PC-13冪等性テスト欠落)は解消を実測で確認した。
新たな HIGH/MEDIUM 指摘は無い。
