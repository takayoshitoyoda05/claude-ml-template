# Verdict: 研究データ保護 Phase 2(並列5グループ・マージ前レビュー)

参照設計書: `docs/active/20260821-data-protection-phase2.md`(R-001〜R-028)
参照計画: `.claude/plans/20260821-data-protection-p2.md`(PC-1〜PC-28)

対象: 統合ブランチ `pipeline/20260821-data-protection-p2`(テストファイル+staging
untracked分)と並列4ワークツリー(group-B/D/E/F、いずれも未マージ)。

## 総合判定: PASS(マージ前レビューとして)

全5グループの変更は計画・設計書と一致し、各グループが担当するテストは
すべて GREEN。統合ブランチで検出された19件の FAIL はすべて「他グループの
成果物が未マージであること」で説明がつき、対応する担当グループのワークツリー内
テストは全件 PASS していることを確認した(下記マッピング表)。実装欠陥は
検出されなかった。ただし R-025(全体回帰)・R-028 の一部(E2E)・R-026(手動承認)
は設計上マージ後にしか検証できないため UNVERIFIABLE とし、Step 14/15 実行後の
再レビューを推奨する。

## 未マージFAILの担当グループ対応表(手順3)

`uv run --with pytest python -m pytest tests/test_data_protection_phase2.py -q`
を統合ブランチで実行(`logs/runs/p2-main-integration-*.log`): `19 failed, 2 passed,
16 skipped`。

| FAILしたテスト | 原因 | 担当ワークツリーでの結果 |
|---|---|---|
| test_lock_update_records_hashes_and_excludes_exports 他2件(lock_*) | scripts/data_lock.py 未マージ | group-B: PASS |
| test_doctor_lock_mismatch_warns | doctor.sh未マージ | group-D: PASS |
| test_doctor_backup_stamp_states 他1件(doctor_backup*) | doctor.sh未マージ | group-D: PASS |
| test_dictionary_generate_* 2件 | scripts/data_dictionary.py未マージ | group-B: PASS |
| test_export_check_detects_and_clean | scripts/export_check.py未マージ | group-B: PASS |
| test_data_scan_diff_detects_hit | scripts/data_scan.py未マージ | group-B: PASS |
| test_crossreview_quarantine_doc_mentions_data_scan | SKILL.md未マージ | group-E: PASS |
| test_precommit_detects_* 3件 + test_precommit_clean_fast | scripts/precommit_data_check.py未マージ | group-B: PASS |
| test_doctor_precommit_off_marker | doctor.sh未マージ | group-D: PASS |
| test_doctor_parity_p2_markers | doctor.sh/.ps1未マージ(3種のみ) | group-D: PASS(7種一致を確認) |
| test_history_scan_detects_commit_with_dictionary_hit | scripts/history_scan.py未マージ | group-B: PASS |
| test_standards_synthetic_data_convention | SKILL.md未マージ | group-E: PASS |
| test_docs_conventions_hash_and_readme | EXPERIMENT_LOG.md.template等未マージ | group-E: PASS |

`tests/ -q`(全体)は main で `192 passed, 19 failed(上記と同一), 18 skipped`
(`logs/runs/p2-main-full-*.log`)。Phase1個別確認は `13 passed, 1 skipped`
(`logs/runs/p2-main-phase1-*.log`)で退行なし。

## 要確認2点への回答

**(a) ruff「PASSと報告」vs「9 errors(baseline同一)」の食い違い**: 実測により
「9 errors」の追補報告が正しい。`uv run --with ruff ruff check scripts/_data_patterns.py
scripts/data_dictionary.py scripts/data_lock.py scripts/data_scan.py
scripts/export_check.py scripts/history_scan.py scripts/precommit_data_check.py`
(group-Bワークツリー)で `Found 9 errors`(`PLW1510`×3、`RUF100`×1、`BLE001`系は
env_fingerprint.py側)。この環境ではリポジトリに `pyproject.toml`/`ruff.toml` が
存在せず、`ruff 0.16.4` のデフォルトルールセットがpylint/banditの一部を含む広い
集合になっている(`--isolated` でも同じ415ルールが有効、`--isolated` 単体実行で
`data_lock.py` は `All checks passed!` = 元々エラーが無い)。既存
`scripts/env_fingerprint.py`(本PR対象外・main上のファイル)を同条件で実行しても
`Found 8 errors`(BLE001×6、S110×1、BLE001×1)であり、これが repo 全体の
ベースラインノイズであることを確認した。初回報告の「ruff check PASS」は誤りで、
追補報告が正確(Spec軸の受け入れ条件にruffは含まれないため判定への影響なし。
コード品質はevaluator-standards担当)。

**(b) group-BワークツリーでのtestS_doctor_lock_mismatch_warns / doctor_precommit_off_marker FAIL**:
group-Bワークツリーの `doctor.sh` は Phase 1 のまま(group-D の4マーカー追加が
未マージ)であるため、この2件のみFAILすることを確認した
(`.worktrees/group-B/doctor.sh` に `[DATA-LOCK-MISMATCH]` 等の文字列なし)。
group-Dワークツリーではこの2件を含む対象5件が全PASS。実装バグではなく、
並列開発時の依存未マージによる想定内の失敗。

## data_gate 主要経路の実測(手順4)

`_staging_data_protection_p2.py --root <sandbox>` を一時サンドボックスに適用し、
`.claude/hooks/data_gate.py` を直接実行して確認(scratchpad配下、実リポジトリの
保護パスは未変更):

| ケース | 期待 | 実測exit |
|---|---|---|
| PC-6: `CLAUDE_DATA_GATE=1` + curl アップロード(data/raw) | exit 2 | 2(BLOCKEDメッセージに"exports"含む) |
| PC-7: `cat data/raw/x.csv \| curl -d @- ...` | exit 2 | 2 |
| PC-8: 同送信コマンドで data/exports/summary.csv | exit 0 | 0 |
| PC-9: 環境変数未設定 | exit 0 | 0 |
| PC-9: `CLAUDE_DATA_GATE=0` | exit 0 | 0 |
| PC-10: 不正JSON | exit 0 | 0 |
| PC-10: `ls -la` | exit 0 | 0 |
| PC-10: 空stdin | exit 0 | 0 |

全件期待通り。

## staging `--root` 冪等性の実測(手順4)

同一サンドボックスに `_staging_data_protection_p2.py --root <dir>` を2回適用。
1回目: `DONE`×3。2回目: `SKIP`×3。`filecmp.cmp(..., shallow=False)` で
`settings.json` / `_mask.py` とも1回目適用後とバイト単位で一致(`True`)。PC-27成立。

## `_mask.py` 辞書対応の fail-open 実測(手順4 / PC-12・PC-13)

サンドボックスに `.claude/checkpoints/data_patterns.json` を配置しない/壊れた
JSON/空ファイル/`patterns`がオブジェクトの4ケースいずれも例外を投げず、辞書
ヒットは無視されるがクラッシュしない(fail-open)ことを確認。有効なJSON
(`{"patterns": ["S-\\d{5}"]}`)では `S-99999` が `[MASKED]` に置換されることを確認。

## doctor 1対1(手順2)

group-Dワークツリー: `\[DATA-[A-Z-]+\]` raw=12/12, uniq=7/7, diff無し(PC-21/R-021)。

## インストーラ1対1(手順2)

group-Fワークツリー: `scripts/[A-Za-z0-9_./-]+` (claude-init) raw=10/10 uniq=10/10
diff無し。(claude-update) raw=10/10 uniq=10/10 diff無し。IGNORE_ENTRIES・
MARKER保護・個別ファイル配布(ディレクトリ再帰コピーなし)を sh/ps1 双方で確認
(`claude-init.sh:106-108`, `claude-init.ps1:99-101`)。

## mypy

`uv run mypy --version` は spawn失敗(プロジェクトにmypy未導入のため対象外。
手順5により実施せず)。

## 問題点(要修正)

なし。実装欠陥は検出されなかった。

- [重大度: LOW] group-Bの初回完了報告に「ruff check PASS」という誤った記述が
  あった(実際は9件、baseline同一)。追補報告で訂正済みであり、判定への影響は
  無い(ruffはSpec受け入れ条件の対象外)。証拠: 上記「要確認2点(a)」の実測。

## goal との突き合わせ

本計画に `goal` ブロックは無い(experiment: false、機械化スクリプト・文書追加のみ)。
target/guard_metricsの突き合わせは対象外。

## 受け入れ条件(R-001〜R-028)

| ID | 判定 | 実行コマンド | 実測値 | 証拠(file:line) |
|---|---|---|---|---|
| R-001 | PASS | `pytest tests/test_data_protection_phase2.py -q -k lock_update`(group-B) | 1 passed | `.worktrees/group-B/scripts/data_lock.py:62-82`(update, exports除外) |
| R-002 | PASS | 同 `-k lock_check_detects`(group-B) | 1 passed | `.worktrees/group-B/scripts/data_lock.py:85-119` |
| R-003 | PASS | 同 `-k lock_check_clean`(group-B) | 1 passed | 同上 |
| R-004 | PASS | 同 `-k doctor_lock_mismatch`(group-D) | 1 passed | `.worktrees/group-D/doctor.sh:145-166` |
| R-005 | PASS | 同 `-k doctor_backup`(group-D) | 2 passed | `.worktrees/group-D/doctor.sh:168-186` |
| R-006 | PASS | 手動実測(HOOK_SOURCE適用サンドボックス) | exit=2 | `_staging_data_protection_p2.py:100-113`(HOOK_SOURCE内) |
| R-007 | PASS | 同上 | exit=2 | 同上 |
| R-008 | PASS | 同上 | exit=0 | 同上(`_EXPORTS_PREFIX`判定) |
| R-009 | PASS | 同上 | exit=0(未設定・0とも) | `_staging_data_protection_p2.py:88-89`(HOOK_SOURCE) |
| R-010 | PASS | 同上 | exit=0(不正JSON/無関係コマンド/空stdin) | 同上:91-98 |
| R-011 | PASS | `pytest ... -k dictionary_generate`(group-B) | 2 passed | `.worktrees/group-B/scripts/data_dictionary.py` |
| R-012 | PASS | 手動実測(有効data_patterns.json) | `S-99999`→`[MASKED]` | `_staging_data_protection_p2.py:168-172`(`_mask_dictionary_patterns`) |
| R-013 | PASS | 手動実測(不在/壊れたJSON/空/object) | 4ケースとも例外無し・元テキスト維持 | `_staging_data_protection_p2.py:142-165`(`_load_dictionary_patterns`) |
| R-014 | UNVERIFIABLE | `pytest ... -k reportgen_sanitize` | staging未適用(skip)。マージ後に要再検証 | pytestmark_staging(`tests/test_data_protection_phase2.py:119-123`) |
| R-015 | PASS | `pytest ... -k export_check`(group-B) | 1 passed | `.worktrees/group-B/scripts/export_check.py` |
| R-016 | PASS | 同 `-k data_scan_diff`(group-B) | 1 passed | `.worktrees/group-B/scripts/data_scan.py` |
| R-017 | PASS | 同 `-k crossreview_quarantine_doc`(group-E) | 1 passed | `.worktrees/group-E/.claude/skills/cross-review/SKILL.md:30` |
| R-018 | PASS | 同 `-k precommit_detects`(group-B) | 3 passed | `.worktrees/group-B/scripts/precommit_data_check.py` |
| R-019 | PASS | 同 `-k precommit_clean_fast`(group-B) | 1 passed | 同上 |
| R-020 | PASS | 同 `-k doctor_precommit_off`(group-D) | 1 passed | `.worktrees/group-D/doctor.sh:200-204` |
| R-021 | PASS | `diff <(grep [DATA-...] doctor.sh\|sort -u) <(... doctor.ps1)`(group-D) | raw12/12 uniq7/7 diff無し | `.worktrees/group-D/doctor.sh`, `doctor.ps1` |
| R-022 | PASS | `pytest ... -k history_scan`(group-B) | 1 passed | `.worktrees/group-B/scripts/history_scan.py` |
| R-023 | PASS | 同 `-k standards_synthetic`(group-E) | 1 passed | `.worktrees/group-E/.claude/skills/python-standards/SKILL.md:23-25` |
| R-024 | PASS | 同 `-k docs_conventions`(group-E) | 1 passed | `.worktrees/group-E/templates/EXPERIMENT_LOG.md.template`, `.claude/agents/evaluator.md:151` |
| R-025 | UNVERIFIABLE | `pytest tests/ -q`(統合ブランチ、B/D/E/F未マージ) | 192 passed/19 failed(全件未マージ起因、担当worktreeでは全PASS) | マージ後に再実行が必要 |
| R-026 | UNVERIFIABLE(manual) | ユーザーの `!` 実行待ち | 未実施 | `.claude/plans/20260821-data-protection-p2.md:212`(Step15) |
| R-027 | PASS | 手動実測(`--root`2回適用) | 2回目 `SKIP`×3、`filecmp.cmp`=True(settings.json/_mask.py) | `_staging_data_protection_p2.py:190-260` |
| R-028 | UNVERIFIABLE(一部PASS) | `pytest ... -k scripts_distributed`(group-F) | sh_ps1_parity: PASS / e2e_files_exist: skip(未コミットのため設計通り) / doctor_diff_detects: FAIL(group-D未マージのため) | `.worktrees/group-F/claude-init.sh:261-303`, `tests/test_data_protection_phase2.py:1175-1192`(skip条件) |

## ベースライン比較(手順4.5)

手順4の評価コマンドはすべてPASS(未マージに起因するFAILは担当グループへの
帰属を確認済みで「今回の変更が原因」に該当しない実装欠陥ではない)ため、
ベースライン比較(worktree作成)は実施していない。

## 完了時の追加手順について

本レビューは並列5グループの**マージ前**Spec検証であり、計画のStep14
(全体回帰の再確認)・Step15(R-026のユーザー承認)が未実施のため、
`docs/active/20260821-data-protection-phase2.md` のアーカイブ移動・
`docs/EXPERIMENT_LOG.md` への記録は行わない。マージ後にStep14/15を実行し、
`R-025`・`R-026`・`R-028`(doctor_diff_detects/e2e_files_exist)を再検証した上で
評価者が完了時手順を実施することを推奨する。radon/mlflow記録も同じ理由で保留。
