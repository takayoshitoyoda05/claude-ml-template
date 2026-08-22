# Verdict: 研究データ保護 Phase 2(最終判定・マージ後再検証)

参照設計書: `docs/active/20260821-data-protection-phase2.md`(R-001〜R-028)
参照計画: `.claude/plans/20260821-data-protection-p2.md`(PC-1〜PC-28)

対象: ブランチ `pipeline/20260821-data-protection-p2`(HEAD、5グループ全マージ済み
+ Step 15 のユーザー `!` staging 適用〔コミット `cd65721`〕+ テスト fixture 修正
〔コミット `25a9ed4`〕まで反映済み)。

## 総合判定: PASS(最終)

マージ前レビュー(`e0d5450`)で UNVERIFIABLE だった R-014・R-025・R-026・R-028 は、
以下の経緯で全て解消・実測確認済み。

- R-026: ユーザーが `! uv run python _staging_data_protection_p2.py` を実行し
  (計画 Step 15)、data_gate 本体・`_mask.py` の辞書対応・settings.json 登録が
  実リポジトリに適用された(コミット `cd65721`)。適用後、staging 依存で skip
  していた R-006〜R-010・R-012〜R-014・R-027 が全て実行され PASS した。
- R-025: 統合ブランチで `tests/ -q` を再実行し、`227 passed, 2 skipped` で
  失敗0(下記「全体回帰」参照)。
- R-014: staging 適用後は `test_reportgen_sanitize_evidence` が skip されず実行され
  PASS(`-k reportgen_sanitize` → `1 passed, 36 deselected`)。
- R-028: scripts/ 8ファイルがコミットされ HEAD に載ったことで、
  `test_scripts_distributed_e2e_files_exist`(git clone 方式の E2E)が skip されずに
  実行され PASS。3テスト全て PASS(`3 passed, 34 deselected`)。

実装欠陥は検出されなかった。

## 全体回帰(手順4・R-025)

`uv run --with pytest python -m pytest tests/ -q`
(`logs/runs/p2-final-full-20260822-125724.log`): **227 passed, 2 skipped**。

skip の内訳(いずれも Phase 2 と無関係、環境条件による正常な skip):

| skip テスト | 理由 | 判定 |
|---|---|---|
| `tests/test_data_protection_phase1.py:365` | `_staging_data_protection_p1.py が存在しない(未作成 or 既に削除済み)`。Phase 1 の staging は適用済みで冪等スクリプト自体が既に削除されているため、対象ファイルが無く skip する設計(staging 適用後は消える一時ファイル) | 想定内 |
| `tests/test_session_monitor.py:441` | `_staging_session_monitor.py が存在しない(未作成 or 既に削除済み)`。同上(別計画の staging が適用済みで削除済み) | 想定内 |

Phase 2 のテストファイル自体は skip 0 件(`tests/test_data_protection_phase2.py -q`
→ `37 passed`、`logs/runs/p2-final-phase2-20260822-125724.log`)。

## Phase 2 受け入れテスト(手順4)

`uv run --with pytest python -m pytest tests/test_data_protection_phase2.py -q`
→ **37 passed**(`logs/runs/p2-final-phase2-20260822-125724.log`)。staging 適用済みのため
skip は0件(マージ前レビュー時は `19 failed, 2 passed, 16 skipped`)。

## R-ID 別実測(-k クエリ、`logs/runs/p2-final-perR-20260822-125724.log`)

37テスト中、以下の -k クエリで全27件を分類。selected/deselected の合計が常に
37 になることを確認済み(例: 1 passed + 36 deselected、2 passed + 35 deselected 等)。

| -k クエリ | 対応 R-ID | 実測 |
|---|---|---|
| `lock_update` | R-001 | 1 passed, 36 deselected |
| `lock_check_detects` | R-002 | 1 passed, 36 deselected |
| `lock_check_clean` | R-003 | 1 passed, 36 deselected |
| `doctor_lock_mismatch` | R-004 | 1 passed, 36 deselected |
| `doctor_backup` | R-005 | 2 passed, 35 deselected |
| `gate_blocks_upload` | R-006 | 1 passed, 36 deselected |
| `gate_blocks_pipe` | R-007 | 1 passed, 36 deselected |
| `gate_allows_exports` | R-008 | 1 passed, 36 deselected |
| `gate_off` | R-009 | 1 passed, 36 deselected |
| `gate_fail_open_input` | R-010 | 1 passed, 36 deselected |
| `dictionary_generate` | R-011 | 2 passed, 35 deselected |
| `mask_uses_dictionary` | R-012 | 1 passed, 36 deselected |
| `mask_without_dictionary` | R-013 | 4 passed(missing/broken_json/empty/object_not_list), 33 deselected |
| `reportgen_sanitize` | R-014 | 1 passed, 36 deselected |
| `export_check` | R-015 | 1 passed, 36 deselected |
| `data_scan_diff` | R-016 | 1 passed, 36 deselected |
| `crossreview_quarantine_doc` | R-017 | 1 passed, 36 deselected |
| `precommit_detects` | R-018 | 3 passed, 34 deselected |
| `precommit_clean_fast` | R-019 | 1 passed, 36 deselected |
| `doctor_precommit_off` | R-020 | 1 passed, 36 deselected |
| `doctor_parity_p2` | R-021 | 1 passed, 36 deselected |
| `history_scan` | R-022 | 1 passed, 36 deselected |
| `standards_synthetic` | R-023 | 1 passed, 36 deselected |
| `docs_conventions` | R-024 | 1 passed, 36 deselected |
| `staging_idempotent` | R-027 | 1 passed, 36 deselected |
| `scripts_distributed` | R-028 | 3 passed, 34 deselected |
| `mask_loader_selfcontained` | R-012/R-013 の付帯(PC-26) | 1 passed, 36 deselected |

R-025・R-026 はテスト1本に対応しないため上表になく、全体回帰(前節)とユーザーの
`!` 実行(コミット `cd65721`)でそれぞれ検証。

## doctor 1対1(R-021)

`diff <(grep -oE '\[DATA-[A-Z-]+\]' doctor.sh | sort -u) <(grep -oE '\[DATA-[A-Z-]+\]' doctor.ps1 | sort -u)`
→ 差分無し。raw sh=12/uniq sh=7、raw ps1=12/uniq ps1=7。マーカー定義:
`doctor.sh:176`(`[DATA-LOCK-MISMATCH]`)、`doctor.sh:188`/`197`(`[DATA-BACKUP-UNKNOWN]`)、
`doctor.sh:193`(`[DATA-BACKUP-STALE]`)、`doctor.sh:203`(`[DATA-PRECOMMIT-OFF]`)、
`doctor.ps1:222`(`[DATA-PRECOMMIT-OFF]`)。

## インストーラ1対1(R-028)

`diff <(grep -oE 'scripts/[A-Za-z0-9_./-]+' claude-init.sh | sort -u) <(... claude-init.ps1)`
→ raw=10/uniq=10 双方、差分無し。同様に claude-update.sh/.ps1 も raw=10/uniq=10、
差分無し。配布ファイルリスト: `claude-init.sh:107-109`(9ファイル+`env_fingerprint.py`)。
個別ファイル配布(ディレクトリ再帰コピーなし)を `claude-init.sh:279-300`
(MARKER保護つき配置ロジック)で確認。

## data_gate 実測(R-006〜R-010、実リポジトリの本番フック)

サンドボックスではなく実際に適用された `.claude/hooks/data_gate.py` を直接実行。

| ケース | 期待 | 実測exit |
|---|---|---|
| `CLAUDE_DATA_GATE` 未設定 + upload コマンド | exit 0 | 0 |
| `CLAUDE_DATA_GATE=1` + upload コマンド(data/raw) | exit 2 | 2(stderr: `.claude/hooks/data_gate.py:82` の BLOCKED メッセージに"exports"含む) |

オプトイン判定: `.claude/hooks/data_gate.py:66`(`if os.environ.get("CLAUDE_DATA_GATE") != "1"` で即 return）。
exports 除外判定: `.claude/hooks/data_gate.py:38`(`_EXPORTS_PREFIX`)、`:49-52`(`_has_raw_data_ref`)。

settings.json 登録は1件のみ(重複なし): `grep -c "data_gate" .claude/settings.json` → `1`
(`.claude/settings.json:62`)。

## `_mask.py` 辞書対応の自己完結性(R-012・R-013・PC-26)

`grep -rn "scripts" .claude/hooks/` → **0件**(`logs/runs/p2-final-selfcontain-20260822-125724.log`)。
`.claude/hooks/_mask.py` は `scripts/` を import しない。辞書ロード・適用は
`.claude/hooks/_mask.py:185`(`_load_dictionary_patterns`、fail-open）、`:211`
(`_mask_dictionary_patterns`）、`mask()` 内 `:227` で自己完結。

## PC-27 staging 冪等性(R-027)

`test_staging_idempotent_apply_twice_p2`(`tests/test_data_protection_phase2.py:1067-1129`)
が2回適用後の `settings.json`/`_mask.py`/`data_gate.py` のバイト一致と
`data_gate_hooks` の重複登録なし(`len == 1`)を検査。PASS。

## verify-hooks / verify-installers(手順4)

- `bash verify-hooks.sh` → 全テストPASS(`logs/runs/p2-final-verifyhooks-20260822-125724.log`)。
- `bash verify-installers.sh` → 全テストPASS(`logs/runs/p2-final-verifyinstallers-20260822-125724.log`)。

## mypy

`uv run mypy --version` → `Failed to spawn: mypy`(プロジェクト未導入のため手順5対象外)。

## 問題点(要修正)

なし。実装欠陥は検出されなかった。

- [重大度: LOW] group-Bの初回完了報告に「ruff check PASS」という誤った記述が
  あった(実際は9件、baseline同一。マージ前レビューで訂正済み)。判定への影響は
  無い(ruffはSpec受け入れ条件の対象外)。

## goal との突き合わせ

本計画に `goal` ブロックは無い(experiment: false、機械化スクリプト・文書追加のみ)。
target/guard_metricsの突き合わせは対象外。

## 受け入れ条件(R-001〜R-028・最終)

| ID | 判定 | 実行コマンド | 実測値 | 証拠(file:line) |
|---|---|---|---|---|
| R-001 | PASS | `pytest tests/test_data_protection_phase2.py -q -k lock_update` | 1 passed, 36 deselected | `scripts/data_lock.py:75`(update, exports除外) |
| R-002 | PASS | 同 `-k lock_check_detects` | 1 passed, 36 deselected | `scripts/data_lock.py:99`(check） |
| R-003 | PASS | 同 `-k lock_check_clean` | 1 passed, 36 deselected | `scripts/data_lock.py:99` |
| R-004 | PASS | 同 `-k doctor_lock_mismatch` | 1 passed, 36 deselected | `doctor.sh:176` |
| R-005 | PASS | 同 `-k doctor_backup` | 2 passed, 35 deselected | `doctor.sh:188,193,197` |
| R-006 | PASS | 同 `-k gate_blocks_upload` + 手動実測(本番フック) | 1 passed, 36 deselected / exit=2 | `.claude/hooks/data_gate.py:57`(`_has_upload_cmd`）、`:82`(BLOCKEDメッセージ） |
| R-007 | PASS | 同 `-k gate_blocks_pipe` | 1 passed, 36 deselected | `.claude/hooks/data_gate.py:41`(`_segment_head`） |
| R-008 | PASS | 同 `-k gate_allows_exports` | 1 passed, 36 deselected | `.claude/hooks/data_gate.py:38`(`_EXPORTS_PREFIX`） |
| R-009 | PASS | 同 `-k gate_off` + 手動実測 | 1 passed, 36 deselected / exit=0(未設定） | `.claude/hooks/data_gate.py:66`(オプトイン判定） |
| R-010 | PASS | 同 `-k gate_fail_open_input` | 1 passed, 36 deselected | `.claude/hooks/data_gate.py:65`(`main`） |
| R-011 | PASS | 同 `-k dictionary_generate` | 2 passed, 35 deselected | `scripts/data_dictionary.py:100`(`main`） |
| R-012 | PASS | 同 `-k mask_uses_dictionary` | 1 passed, 36 deselected | `.claude/hooks/_mask.py:211`(`_mask_dictionary_patterns`） |
| R-013 | PASS | 同 `-k mask_without_dictionary` | 4 passed(missing/broken_json/empty/object_not_list), 33 deselected | `.claude/hooks/_mask.py:185-207`(`_load_dictionary_patterns`, fail-open) |
| R-014 | PASS | 同 `-k reportgen_sanitize` | 1 passed, 36 deselected(staging適用によりskip解消) | `.claude/hooks/_mask.py:227`(`mask()` 内） |
| R-015 | PASS | 同 `-k export_check` | 1 passed, 36 deselected | `scripts/export_check.py:21`(`main`） |
| R-016 | PASS | 同 `-k data_scan_diff` | 1 passed, 36 deselected | `scripts/data_scan.py:19`(`main`） |
| R-017 | PASS | 同 `-k crossreview_quarantine_doc` | 1 passed, 36 deselected | `.claude/skills/cross-review/SKILL.md:30`（`data_scan.py` 言及） |
| R-018 | PASS | 同 `-k precommit_detects` | 3 passed, 34 deselected | `scripts/precommit_data_check.py:94`(`main`） |
| R-019 | PASS | 同 `-k precommit_clean_fast` | 1 passed, 36 deselected | `scripts/precommit_data_check.py:94` |
| R-020 | PASS | 同 `-k doctor_precommit_off` | 1 passed, 36 deselected | `doctor.sh:203` |
| R-021 | PASS | `diff <(grep [DATA-...] doctor.sh\|sort -u) <(... doctor.ps1)` | raw12/12 uniq7/7 diff無し | `doctor.sh`(raw12/uniq7), `doctor.ps1`(raw12/uniq7) |
| R-022 | PASS | 同 `-k history_scan` | 1 passed, 36 deselected | `scripts/history_scan.py:90`(`main`） |
| R-023 | PASS | 同 `-k standards_synthetic` | 1 passed, 36 deselected | `.claude/skills/python-standards/SKILL.md:23-25` |
| R-024 | PASS | 同 `-k docs_conventions` | 1 passed, 36 deselected | `templates/EXPERIMENT_LOG.md.template:3-4`, `.claude/agents/evaluator.md:151` |
| R-025 | PASS | `pytest tests/ -q`(統合ブランチ・マージ後） | 227 passed, 2 skipped(Phase 2 と無関係の2件、いずれも別計画staging適用済みによる想定内skip) | `logs/runs/p2-final-full-20260822-125724.log` |
| R-026 | PASS | ユーザーの `!` 実行(コミット `cd65721`）＋依存テスト再実行 | staging適用完了、skip解消（R-006〜R-014, R-027 が全てPASSへ移行） | `.claude/plans/20260821-data-protection-p2.md:212`(Step15)、コミット `cd6572199f73d9bc20dc37775b0d23df095a731c` |
| R-027 | PASS | 同 `-k staging_idempotent` | 1 passed, 36 deselected | `tests/test_data_protection_phase2.py:1067-1129`（バイト一致・重複登録なし検査） |
| R-028 | PASS | 同 `-k scripts_distributed` | 3 passed, 34 deselected（sh_ps1_parity・e2e_files_exist・doctor_diff_detects 全PASS） | `claude-init.sh:107-109,279-300`, `tests/test_data_protection_phase2.py:1172-1219`(e2e), `tests/test_data_protection_phase2.py:1226-1260`(doctor_diff) |

## ベースライン比較(手順4.5)

手順4の評価コマンドはすべてPASSしたため、ベースライン比較(worktree作成)は
実施していない。

## 完了時の追加手順について

本 verdict は最終判定(PASS)である。設計書 `docs/active/20260821-data-protection-phase2.md`
のアーカイブ移動・`docs/EXPERIMENT_LOG.md` への記録・baselines/history.md への追記可否確認・
radon 複雑度計測・mlflow 記録は、evaluator の完了報告内で別途実施する。
