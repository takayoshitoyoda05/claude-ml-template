# 監査結果: docs/active/tdd-gate-spec.md (R-001〜R-021)

監査環境: リポジトリ直下、ブランチ `pipeline/20260911-tdd-gate`(コミット `e2ad223`、
`git status` clean)。全グループ(A/B/C/D)統合済みであることを確認したうえで、
verdict-tdd-gate-spec.md に記載の実行コマンド・file:line 証拠を独立に再実行・再読で確認した。

## 監査結果

| ID | 結果 | 備考 |
|---|---|---|
| R-001 | OK | `grep -c "失敗ログ" .claude/skills/tdd/SKILL.md` → 1(独立実測、verdictも同じ）。`pytest -k pc17` PASSED。verdictは統合前UNVERIFIABLEのまま残っていたため、本監査で再検証しPASSに更新済み |
| R-002 | OK | `pytest tests/test_tdd_gate.py -q -rs` 100 passed に含まれ失敗なし(独立実行)。`bash verify-hooks.sh` で `OK: tdd_red: 失敗コマンドでセンチネルを記録する` を確認。証拠 `_staging_tdd_gate.py:161-170` を読み、sentinel dict 構築+`SENTINEL_PATH.write_text` の記述と一致することを確認 |
| R-003 | OK | 同上、`_staging_tdd_gate.py:142-148` を読み、`result.returncode == 0` 時に「既に緑です」でexit 1する記述と一致 |
| R-004 | OK | `_staging_tdd_gate.py:122-124` を読み、`not args.cmd or not args.files` でexit 1する記述と一致 |
| R-005 | OK | `bash verify-hooks.sh` で `OK: tdd_gate: recorded test file is blocked (exit 2)` を確認。証拠範囲(`_staging_tdd_gate.py:326-336`)はブロック分岐の末尾寄りだが、実際のパス一致判定(332-342行)は同じ関数内の直後にあり記載内容と食い違わない |
| R-006 | OK | `bash verify-hooks.sh` で absolute/redundant/symlink 表記いずれも exit 2 を確認。`_path_for_match`+`os.path.realpath` によるパス正規化・照合は `_staging_tdd_gate.py:332-336` に実在(verdict引用の326-329は同一ブロックの数行前で、記述の趣旨と齟齬なし) |
| R-007 | OK | `_staging_tdd_gate.py:295-296`(`os.environ.get("CLAUDE_TDD_GATE","") != "1": sys.exit(0)`)を確認。verify-hooks.sh で `OK: tdd_gate: env empty string passes` `OK: tdd_gate: env=0 passes` |
| R-008 | OK | `_staging_tdd_gate.py:297-298`(`SENTINEL_PATH.exists()` 判定)を確認。pytest 100 passed に該当ケース含まれ失敗なし |
| R-009 | OK | `_staging_tdd_gate.py:246-263`(`_validate_sentinel`)に `os.path.isabs(f)` チェックを確認(verdict引用251-257と一致)。`pytest -k pc10` (fail_closed系10ケース×2パラメータ)全PASSEDを独立実行で確認 |
| R-010 | OK | verify-hooks.sh で `OK: tdd_gate: ブロックのたびに blocks.log が1行増える` を確認。`pytest -k pc25` PASSED |
| R-011 | OK | `pytest -k "pc12"` (`test_pc12_unlock_requires_green`・`test_pc12_unlock_toctou_preserves_reappeared_sentinel`)を独立実行し両方PASSEDを確認。ただし verdict の証拠引用(469-489は「再読込+バイト比較」の記述)は、その後のコミット `e2ad223`(`unlockのrename方式`)により実装が「原子的rename→比較→書き戻し/破棄」方式へ進化しており、verdict本文の機構説明は現在のコードと完全一致しない(挙動そのものはテストで再確認しPASS)。詳細は本監査の「スコープ外変更」節ではなく下記の注記を参照 |
| R-012 | OK | verify-hooks.sh で `OK: tdd_red: --rearm はセンチネルを削除し rearm を記録する`。`pytest -k pc13` PASSED |
| R-013 | OK | `grep -c "tdd_gate" .claude/settings.json` → 1。`json.load` でパースし、`PreToolUse` の `matcher: "Edit|Write|NotebookEdit"` エントリの `hooks[].command` に `tdd_gate.py` が含まれることを直接確認(単なる文字列一致でなく配線位置まで検証) |
| R-014 | OK | `pytest -k pc26`(`test_pc26_staging_hooks_only_skips_settings`)PASSED。1回適用・2回適用後の `_tree_manifest` がバイト単位一致することをテストが直接検証 |
| R-015 | OK | `grep -l "CLAUDE_TDD_GATE" templates/settings.local.json.template README.md` → 2ファイルとも一致(独立実測)。`pytest -k pc16` PASSED。verdictは統合前UNVERIFIABLEのまま残っていたため、本監査で再検証しPASSに更新済み |
| R-016 | OK | consistency.md 標準形の diff コマンドを独立に再実行: sh raw=33/unique=33、ps1 raw=33/unique=33、diff結果0行(完全一致)。`pytest -k pc18` PASSED。ただし verdict の証拠引用 `tests/test_tdd_gate.py:1029-1066` は誤り(統合後のマージで行がずれ、実際は `_tdd_markers` 関数は1231-1249行、テスト本体は1252-1268行)。`verify-hooks.sh:585-793` の引用は行番号どおり正確(tdd節の開始行〜ファイル末尾と一致) |
| R-017 | OK(留保付き) | `bash verify-hooks.sh` を独立実行 → exit 1、NG 1件のみ(`codex_gate: untracked blocked even with showUntrackedFiles=no`)、tdd関連は20件全OK・NG/SKIP 0件。設計書の期待結果は文字どおりには「exit 0」だが実測は exit 1。この食い違いが本diffと無関係の既存問題であることを、mainのmerge-base(9eb356d)のみをdetached worktreeでcheckoutし同一コマンドを実行して独立に確認(同じNGが同様に再現)。verdictの実測値の記載(NG1件・既存環境問題)と食い違いなし |
| R-018 | 承認待ち(manual) | verify-hooks.sh の `env empty string`/`env=0` ケースで自動化範囲は確認済み。ただし実リポジトリへの staging 適用(ユーザーの `!` 実行)後の目視確認は未実施のまま。ユーザー承認待ちの状態を維持 |
| R-019 | OK | `pytest -k pc23_pc24` の `test_pc23_pc24_staging_rejects_ambiguous_settings`(non_unique_matcher/matcher_absent/hooks_not_array)・`test_pc23_pc24_staging_rejects_invalid_json`・`test_pc23_pc24_staging_rejects_missing_settings_without_flag` を独立実行し全PASSED |
| R-020 | OK | `pytest -k pc29` の `test_pc29_staging_write_failure_restores`(単一失敗、call_index 1〜5、_write_tmp/_replace 各)と `test_pc29_staging_persistent_failure_prints_manual_recovery`(二重失敗)を独立実行し全PASSED。docstring(`_staging_tdd_gate.py:636-647`付近)に exit 3・バックアップ実パス・フック実体を残す旨の記載を確認 |
| R-021 | OK | `grep -c "ParseFile" .github/workflows/verify-hooks.yml` → 1(独立実測)。`pytest -k pc30` PASSED。verdictは統合前UNVERIFIABLEのまま残っていたため、本監査で再検証しPASSに更新済み |

全21件(自動20件+manual 1件)のうち、自動20件は全てOK。manual 1件(R-018)は設計どおり
ユーザー承認待ちのまま。

## スコープ外変更

`git diff --stat $(git merge-base main HEAD) HEAD` (checkpoints/logs/.worktrees/tests_scratch除外)で
変更ファイルを確認したところ、以下2件が受け入れ条件テーブルのどのIDにも直接対応しない:

- `CONTEXT.md`(+1行): 用語集に「テスト改変ゲート」の1行説明を追加。機能追加に伴う自然な
  ドキュメント整合(このリポジトリの `consistency.md` 規律に沿った動き)であり、コードや
  受け入れ条件そのものの変更ではない。実害的なスコープ逸脱ではないと判断するが、形式上は
  R-IDに対応しないため報告する
- `.claude/plans/20260911-tdd-gate.md`(新規374行)・`.claude/spec/verdict-tdd-gate-spec.md`
  (+83行、本監査で追加更新分含む): 本パイプラインの計画書・verdict自体であり、
  受け入れ条件の実装物ではなくプロセス成果物(他の過去verdict群と同じパターン)。
  R-IDには対応しないが、パイプラインの標準的な副産物であり実装スコープの逸脱ではない

上記以外(`.claude/hooks/tdd_*.py`・`.claude/settings.json`・`.claude/skills/tdd/SKILL.md`・
`.github/workflows/verify-hooks.yml`・`README.md`・`templates/settings.local.json.template`・
`tests/test_tdd_gate.py`・`verify-hooks.sh`・`verify-hooks.ps1`)は全て対応するR-IDを持つ
コード/テスト変更であり、スコープ外変更は無い。

なお `_staging_tdd_gate.py`(リポジトリ直下)は `.gitignore` の `/_staging_*` パターンにより
意図的に未追跡(git diff に現れない)。設計書3節に明記された想定どおりの挙動であり、
スコープ外変更ではない。

## 注記(evidenceの軽微な不整合)

- R-016: verdictの証拠行番号引用(`tests/test_tdd_gate.py:1029-1066`)は統合後のマージで
  実際のファイル内容と約200行ずれていた(現在の実位置は1231-1268行)。関数・テスト自体は
  実在し内容もverdictの説明と一致するため判定はOKとしたが、次回verdict更新時は行番号を
  現在の統合ブランチに合わせて再採番することを推奨する
- R-011: verdict本文が説明するtdd_unlock.pyのTOCTOU対策機構(「再読込+バイト比較」)は、
  その後のコミット `e2ad223`(2026-09-13、`unlockのrename方式・blocks.logのCR/LFエスケープ`)
  により「原子的rename→再読込比較→書き戻し/破棄」方式に置き換わっている。挙動としては
  該当pytestケースが引き続きPASSしており要件は満たされているが、verdictの機構説明文は
  最新コードと完全には一致しない
