# verdict: tdd-gate-spec.md (グループA: tests/test_tdd_gate.py・_staging_tdd_gate.py・verify-hooks.sh/.ps1)

対象計画: `.claude/plans/20260911-tdd-gate.md`(PC-1〜PC-30)
設計書: `docs/active/tdd-gate-spec.md`(R-001〜R-021。R-020 は差し戻し後にリーダーが
「復元不能時は exit 3+手動復旧手順を出力し、フック実体は残す」旨へ更新済み)
検証環境: worktree `/home/toyod/claude-ml-template/.worktrees/group-A` 内で
`uv run --with pytest python -m pytest tests/test_tdd_gate.py -q -rs`・
`uv run --with pytest python -m pytest tests/ -q`・`bash verify-hooks.sh` を実行。
加えて、Codex クロスレビュー指摘・前回 FAIL 分の再現検証を `mktemp -d` サンドボックスで
再実施(実リポジトリの `.claude/checkpoints/` は未使用)。
R-001・R-015・R-021 は他グループ(B/C/D)担当ファイルで本 worktree に未統合のため UNVERIFIABLE。

## 2026-09-12 再レビュー(fix-A: コミット 90db09a・afe1d6e、`_staging_tdd_gate.py` 更新)

前回 FAIL とした R-009・R-011・R-020 を、前回と同じ再現コマンドで再検証した。
全て PASS に変わったことを確認(詳細は各行および末尾「再検証ログ」を参照)。
併せて MEDIUM 2件(非文字列 `file_path`・`verify-hooks.ps1` の `python3` 依存)の
修正も再現コマンドで確認済み。

| ID | 判定 | 実行コマンド | 実測値 | 証拠(file:line) |
|---|---|---|---|---|
| R-001 | UNVERIFIABLE | `pytest tests/test_tdd_gate.py -k skill_doc`(PC-17) | Group B 担当の `.claude/skills/tdd/SKILL.md` が本 worktree に未統合のため FAIL(RED)。想定内(計画の検証方法表に明記) | tests/test_tdd_gate.py:1005-1026(test_pc17) |
| R-002 | PASS | `pytest -k "red_records or invocation_from_subdirectory"` + `bash verify-hooks.sh` | pytest 50 passed中に含まれ失敗なし。verify-hooks: `OK: tdd_red: 失敗コマンドでセンチネルを記録する` | logs/runs/evalA_verify_hooks.log、_staging_tdd_gate.py:161-170(TDD_RED_SOURCE内センチネル書込み) |
| R-003 | PASS | 同上 `-k red_refuses_green` | verify-hooks: `OK: tdd_red: 緑コマンドはセンチネルを作らない` | logs/runs/evalA_verify_hooks.log、_staging_tdd_gate.py:142-148 |
| R-004 | PASS | 同上 `-k red_requires_files` | verify-hooks: `OK: tdd_red: --files 省略は非0終了` | logs/runs/evalA_verify_hooks.log、_staging_tdd_gate.py:122-124 |
| R-005 | PASS | 同上 `-k "gate_blocks or invocation_from_subdirectory"` | verify-hooks: `OK: tdd_gate: recorded test file is blocked (exit 2)` 他 | logs/runs/evalA_verify_hooks.log、_staging_tdd_gate.py:326-336 |
| R-006 | PASS | 同上 `-k path_identity` | verify-hooks: absolute/redundant/symlink 表記いずれも exit 2 で OK | logs/runs/evalA_verify_hooks.log、_staging_tdd_gate.py:326-329(`_path_for_match`+realpath 照合) |
| R-007 | PASS | 同上 `-k gate_off` | verify-hooks: `OK: tdd_gate: env empty string passes` `OK: tdd_gate: env=0 passes` | logs/runs/evalA_verify_hooks.log、_staging_tdd_gate.py:289-290 |
| R-008 | PASS | 同上 `-k gate_no_sentinel` | pytest 50 passed 中に含まれ失敗なし | _staging_tdd_gate.py:291-292 |
| R-009 | PASS(修正確認) | 前回と同じ再現コマンド(相対 `test_files` センチネル+cwd を変えた編集)を再実行 | `_validate_sentinel()` が `test_files` 各要素に `os.path.isabs(f)` を追加したため、相対要素センチネルはスキーマ不正と判定され fail-closed(exit 2、"照合不能のため全編集を停止中")に変化。以前の exit 0(素通り)は再現しない | _staging_tdd_gate.py:251-257(`test_files` の `isabs` チェック追加。tdd_gate/tdd_unlock 双方) |
| R-010 | PASS | 同上 `-k "blocks_log or broken_sentinel_logs_block"` | verify-hooks: `OK: tdd_gate: ブロックのたびに blocks.log が1行増える` | logs/runs/evalA_verify_hooks.log |
| R-011 | PASS(修正確認) | 前回と同じ再現コマンド2種(空文字列 `test_command`、TOCTOU 並行記録)を再実行 | (a) `test_command: ""` → `_validate_sentinel` が `value.strip()` を要求するため即スキーマ不正と判定、`tdd_unlock.py` はテストコマンドを実行せず exit 1・「センチネルの形式が不正です」・センチネル保持を確認(以前の exit 0 誤解除は再現しない)。(b) TOCTOU: `sleep 3` コマンド実行中に別プロセスが `tdd_red.py --files tests/test_b.py` で新センチネルを記録 → `tdd_unlock.py` は完了後に `read_bytes()` で再読込し実行前バイト列と不一致を検出、exit 1・「テスト実行中に Red が再記録されました」・**新センチネル(test_b.py を含む内容)がそのまま保持される**ことを確認(以前の無条件 unlink による破壊は再現しない) | _staging_tdd_gate.py:249-250(`value.strip()` 追加)、469-489(`tdd_unlock.py` の再読込+バイト比較によるTOCTOU対策) |
| R-012 | PASS | 同上 `-k rearm` | verify-hooks: `OK: tdd_red: --rearm はセンチネルを削除し rearm を記録する` | logs/runs/evalA_verify_hooks.log |
| R-013 | PASS | `pytest -k settings_registration`(PC-14) | pytest 50 passed 中(FAILED一覧に無し) | _staging_tdd_gate.py:684-694 |
| R-014 | PASS | `pytest -k staging_idempotent`(PC-15) | pytest 50 passed 中(FAILED一覧に無し) | _staging_tdd_gate.py:668(スキップ契約) |
| R-015 | UNVERIFIABLE | `grep -l "CLAUDE_TDD_GATE" templates/settings.local.json.template README.md` | Group C 担当ファイルが本 worktree に未統合のため PC-16 が FAIL(RED)。想定内 | tests/test_tdd_gate.py:984-1005(test_pc16) |
| R-016 | PASS | `.claude/rules/consistency.md` 標準形を tdd マーカーに適用(`test_pc18_verify_hooks_markers_match` と同一ロジック) | sh: raw=33/unique=33、ps1: raw=33/unique=33、差分0件(`sh_set - ps1_set = set()`、`ps1_set - sh_set = set()`)。pytest 側 `test_pc18_verify_hooks_markers_match` も PASS | tests/test_tdd_gate.py:1029-1066(`_tdd_markers`)、verify-hooks.sh:585-793、verify-hooks.ps1(tdd節) |
| R-017 | PASS | `bash verify-hooks.sh`(再検証: logs/runs/evalA2_verify_hooks.log) | exit 1・NG 1件のみで前回と同一(`codex_gate: untracked blocked even with showUntrackedFiles=no`、本diff無関係・既存環境問題)。tdd関連は `NG:` 0件・`SKIP: tdd` 0件(20ケース全OK、`python3`→`uv run python -c` 修正後の ps1 側は pwsh 不在のため本環境では未実行) | logs/runs/evalA2_verify_hooks.log:83(該当NG行)、verify-hooks.ps1(afe1d6e で `python3` 依存を全7箇所解消) |
| R-018 | PASS(自動化範囲) | verify-hooks の `env empty string` / `env=0` ケース(R-007と同一証跡) | 既定(env未設定相当)でブロックが起きないことを確認。ただし実リポジトリへの staging 適用(Step 7・ユーザーの `!` 実行)は本レビュー時点で未実施のため、本番環境での目視確認(R-018 の manual 部分)は未完了 | logs/runs/evalA_verify_hooks.log(`env empty string passes`) |
| R-019 | PASS | `pytest -k "staging_rejects_ambiguous_settings or staging_failure_is_atomic or hooks_only"` | pytest 50 passed 中(FAILED一覧に無し) | _staging_tdd_gate.py:606-648(前検証) |
| R-020 | PASS(修正確認・R-020改訂版に合致) | 前回と同じ二重失敗注入(settings.json 本体置換=実処理完了後に失敗、かつ復元(バックアップからの書き戻し)も実処理前に失敗)を importlib 経由で再実行 | `apply()` は **exit 3** を返し、stderr に「自動復旧できません。手動で復旧してください」+バックアップの実パス(`cp "<backup>" "<settings.json>"`)+`git checkout -- "<settings.json>"` を出力。バックアップファイル(`settings.json.tdd_gate_backup`)は消費されずディスクに残存(手動復旧が実際に可能)。`.claude/hooks/tdd_gate.py` 等3本のフック実体も削除されず残留(改訂 R-020 の「フック実体は残す」に合致)。settings.json 自体は tdd_gate.py 参照が残った状態(=復元不能なので当然、改訂 R-020 が許容する結果)。単一失敗(call_index 1〜5)のみを注入した場合は非0終了+適用前と完全一致(バックアップも消費されて残らない)を別途確認 | _staging_tdd_gate.py:636-647(docstring で exit 3/バックアップ/フック残置を明記)、712-784(`apply()` のバックアップ作成・復元・exit 3 分岐)。設計書更新: `docs/active/tdd-gate-spec.md:139`(R-020 改訂文) |
| R-021 | UNVERIFIABLE | `grep -c "ParseFile" .github/workflows/verify-hooks.yml` | Group D 担当ファイルが本 worktree に未統合のため PC-30 が FAIL(RED)。想定内 | tests/test_tdd_gate.py:1069-1087(test_pc30) |

## 補足(初回レビュー、2026-09-12 午前)

- 初回は R-009・R-011・R-020 を FAIL とした(下記「再検証ログ」参照)。計画自身が明示指定した
  検証コマンド(PC-10・PC-12/21・PC-29)では PASS していたが、設計書4節の EARS 要件そのもの
  (実体基準の照合不変条件・検証つき解除・書き込み失敗時の復元)を追加の境界値・並行更新・
  二重失敗で突いたところ違反が見つかった。
- R-002〜R-008・R-010・R-012〜R-014・R-016・R-017・R-019 は初回から問題なし。

## 再検証ログ(2026-09-12 再レビュー、コミット 90db09a・afe1d6e)

- `uv run --with pytest python -m pytest tests/test_tdd_gate.py -q -rs`:
  **3 failed, 59 passed, 37 skipped**(失敗は test_pc16/17/30 のみ = 想定内RED。新規追加テスト
  含め regressions なし)。ログ: logs/runs/evalA2_test_tdd_gate.log
- `uv run --with pytest python -m pytest tests/ -q`: **3 failed, 365 passed, 78 skipped**
  (同じ3件のみ、全体退行なし)。ログ: logs/runs/evalA2_test_all.log
- `bash verify-hooks.sh`: exit 1・NG 1件(codex_gate、既存・無関係)のみ、tdd関連0件。
  ログ: logs/runs/evalA2_verify_hooks.log
- R-009 再現(相対 `test_files` 要素): 修正後は fail-closed(exit 2)に変化。以前の exit 0
  (別 cwd からの絶対パス指定での素通り)は再現せず
- R-011(a) 再現(空文字列 `test_command`): 修正後は `tdd_unlock.py` が exit 1・「センチネルの
  形式が不正です」でテスト未実行のまま拒否。以前の exit 0 誤解除は再現せず
- R-011(b) 再現(TOCTOU、バックグラウンド `tdd_unlock.py` 実行中に別プロセスが `tdd_red.py`
  で再記録): 修正後は `tdd_unlock.py` が exit 1・再読込バイト列比較で不一致を検出し、新センチネル
  (test_b.py の内容)がそのまま保持される。以前の無条件 unlink による破壊は再現せず
- R-020 再現(settings.json 本体置換成功直後に失敗+復元も失敗の二重失敗): 修正後は `apply()` が
  exit 3、stderr にバックアップ実パス(`cp` コマンド)と `git checkout` の手動復旧手順を出力、
  バックアップファイルは消費されず残存、hooks 3本の実体も削除されず残置(改訂 R-020 の
  「フック実体は残す」に合致)。単一失敗(call_index 1〜5)注入では従来どおり exit 1 かつ
  適用前状態に完全復元(バックアップも消費されて残らない)ことも別途確認
- PC-28(実環境番人): `_staging_tdd_gate.py` を退避しクリーン checkout を模した状態で
  `pytest tests/test_tdd_gate.py -q -rs` を実行すると、新設の
  `test_pc28_guardian_real_checkout_has_at_least_one_source` が **FAIL**(以前は該当ケースが
  無く、全skipで「失敗0」になっていた)。結果: **4 failed, 2 passed, 93 skipped**
  (PC-16/17/30 に加えてこの新規番人がFAIL)。退避したファイルは
  `diff` でバイト一致を確認のうえ復元済み
- 非文字列 `file_path`(`{"tool_input":{"file_path":12345}}`): `tdd_gate.py` は exit 0・
  traceback なしで正常終了(以前の `TypeError` クラッシュは再現せず)
- `verify-hooks.ps1` の `python3` 依存: `grep -n "python3" verify-hooks.ps1` が0件
  (afe1d6e で7箇所すべて `uv run python -c` に置換)。tdd マーカー1対1対応も再確認
  (sh unique=33 / ps1 unique=33、差分0件)
