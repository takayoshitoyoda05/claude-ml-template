# Verdict: 20260906-skill-state-hardening-spec

評価対象: `docs/active/20260906-skill-state-hardening-spec.md` の受け入れ条件(R-001〜R-011)
計画: `.claude/plans/20260906-state-hardening.md`

評価時点: `pipeline/20260906-state-hardening` ブランチ、フック2本は staging スクリプト経由で
適用済み。加えて Codex クロスレビュー起因の追加修正5コミット
(`bf6a295`〜`7093e56`: cwd サブディレクトリ解決・symlink 2方向+連鎖・対象判定の realpath
実体一致化。`git log bf6a295^..7093e56 --oneline | wc -l` → 5)と追加テスト10件
(`git diff bf6a295^..7093e56 -- tests/ | grep -c '^+def test_'` → 10)を含む。全体テストは
`uv run --with pytest python -m pytest tests/ -q` で **321 passed, 16 skipped**
(`logs/runs/r010_full.log`)。失敗0。

| ID | 判定 | 実行コマンド | 実測値 | 証拠(file:line) |
|---|---|---|---|---|
| R-001 | PASS | `uv run --with pytest python -m pytest tests/test_state_gate.py -q -k type_mismatch` | 8 passed, 34 deselected, exit 0(`logs/runs/r001_type_mismatch.log`) | `.claude/hooks/_state_common.py:83`(`if not isinstance(obj["size"], str) or obj["size"] not in _SIZE_ENUM`)、`:99`(`gates` の値の型検査) |
| R-002 | PASS | `uv run --with pytest python -m pytest tests/test_state_gate.py -q -k cwd` | 6 passed, 36 deselected, exit 0(`logs/runs/r002_cwd.log`) | `.claude/hooks/state_gate.py:83`(`_effective_cwd`)、`:132`(`_run` 内 `effective_cwd = _effective_cwd(data)`) |
| R-003 | PASS | `uv run --with pytest python -m pytest tests/test_reinject_state.py -q -k schema_invalid` | 4 passed, 10 deselected, exit 0(`logs/runs/r003_schema_invalid.log`) | `.claude/hooks/_state_common.py:145`(`if _validate_state(obj) is not None: return "broken", None`) |
| R-004 | PASS | `uv run --with pytest python -m pytest tests/test_reinject_state.py -q` | 14 passed, exit 0(`logs/runs/r004_reinject_all.log`) | `.claude/hooks/_state_common.py:125`(`_state_section` 関数、ok分岐) |
| R-005 | PASS | `grep -rn 'def _validate_state' .claude/hooks/` | ヒット1件のみ | `.claude/hooks/_state_common.py:66` |
| R-006 | PASS | `grep -n '20260904-skill-state-spec' .claude/commands/ml-pipeline.md`(0件)+ `grep -n 'schema_version' .claude/commands/ml-pipeline.md` | 前者0件(exit 1)、後者150行目でヒット(`logs/runs/r006a_ref.log` 空、`r006b_schema.log`) | `.claude/commands/ml-pipeline.md:150` |
| R-007 | PASS | `grep -n '状態ファイル' .claude/commands/ml-pipeline.md` | 373行目、並列実装節内でヒット(`logs/runs/r007_leader.log`) | `.claude/commands/ml-pipeline.md:373`(「`.claude/state/<slug>.json`(状態ファイル)は統合ブランチ上のリーダー...のみが更新し」) |
| R-008 | PASS | `grep -l '\.claude/state/' claude-init.sh claude-update.sh claude-init.ps1 claude-update.ps1` | 4ファイル全ヒット(`logs/runs/r008_gitignore.log`) | `claude-init.sh`・`claude-update.sh`・`claude-init.ps1`・`claude-update.ps1`(各 IGNORE_ENTRIES / $ignoreEntries 基本リスト) |
| R-009 | PASS | consistency.md標準形diff(init対・update対、2回実行) | init対: 生29/29・一意29/29・diff 0件。update対: 生28/28・一意28/28・diff 0件(`logs/runs/r009_init_pair.log`, `r009_update_pair.log`) | `claude-init.sh`/`claude-init.ps1`、`claude-update.sh`/`claude-update.ps1` |
| R-010 | PASS | `uv run --with pytest python -m pytest tests/ -q` | 321 passed, 16 skipped, exit 0(`logs/runs/r010_full.log`) | (全体、既存契約40件を含み新規FAILなし) |
| R-011 | PASS | `uv run --with pytest python -m pytest tests/test_state_gate.py -q -k idempotent` | 1 passed, 41 deselected, exit 0(`logs/runs/r011_idempotent.log`) | `tests/test_state_gate.py::test_staging_idempotent_apply_twice`(matcher重複1件・state_gate登録1件のアサーション含む) |

## 補足検証

- Codexクロスレビュー起因の追加修正の回帰テスト:
  `uv run --with pytest python -m pytest tests/ -q -k "symlink or subdirectory"` →
  **10 passed**, exit 0(`logs/runs/codex_regression_symlink_subdir.log`)。
  cwdサブディレクトリ解決(`.claude/hooks/state_gate.py:42` `_repo_root`)、symlink双方向/連鎖、
  対象判定の realpath 一本化(`.claude/hooks/state_gate.py:140`
  `os.path.realpath(abs_path).replace("\\", "/") != expected`)の全ケースで検出漏れなし。
- コード確認: `.claude/hooks/_state_common.py:41`(`_current_branch(cwd: str | None = None)`)、
  `.claude/hooks/state_gate.py:68`(`_expected_state_path` が `_current_branch(effective_cwd)` と
  `_repo_root(effective_cwd)` を使用)で、計画の変更内容(ブランチ取得・状態パス導出・対象判定の
  実効cwd統一)と一致することを確認。
- 例外捕捉: `_current_branch`・`_repo_root` は `(OSError, subprocess.TimeoutExpired, UnicodeError)`、
  `_state_section` は `(OSError, UnicodeError, json.JSONDecodeError, ValueError)` を捕捉しており
  `python-style.md` の規約に準拠。
- mypy: `uv run mypy --version` がエラー(未導入)のためスキップ。
- ベースライン比較: 評価コマンドが全てPASSのため実施せず(手順4.5の実施条件に該当しない)。

## 判定: PASS

R-001〜R-011 は全件 PASS。新たな HIGH/MEDIUM 指摘は無い。
