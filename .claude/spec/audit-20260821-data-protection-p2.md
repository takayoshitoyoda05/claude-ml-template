# 監査結果: 研究データ保護 Phase 2

対象設計書: `docs/archive/20260822_20260821-data-protection-phase2.md`(R-001〜R-028)
対象verdict: `.claude/spec/verdict-20260821-data-protection-p2.md`
監査対象ブランチ: `pipeline/20260821-data-protection-p2`(監査時 HEAD、working tree clean)

## 監査方法
- 全 auto 要件(R-001〜R-025, R-027, R-028)を `-k` クエリで独立に再実行し、
  passed/deselected件数を verdict の記載と突合
- `tests/ -q` 全体回帰を再実行
- doctor.sh/ps1、claude-init/update.sh/.ps1 の1対1 diff を再実行
- 実リポジトリの `.claude/hooks/data_gate.py` を直接実行(CLAUDE_DATA_GATE 有無の2ケース)
- `.claude/settings.json` の data_gate 登録件数、`.claude/hooks/` の `scripts` 参照有無を grep で再確認
- verdict に記載された全 file:line を `Read`/`sed -n` で直接確認
- R-026 は該当コミット `cd6572199f73d9bc20dc37775b0d23df095a731c` の実在とdiff内容を確認
- `git diff`/`git log main..HEAD` でスコープ外変更の有無を確認

## 監査結果

| ID | 結果 | 備考 |
|---|---|---|
| R-001 | OK | 再実行 `-k lock_update` → `1 passed, 36 deselected`(verdict一致)。`scripts/data_lock.py:75`(`update`関数）証拠確認済み |
| R-002 | OK | 再実行 `-k lock_check_detects` → `1 passed, 36 deselected`(一致)。`scripts/data_lock.py:99`(`check`関数）証拠確認済み |
| R-003 | OK | 再実行 `-k lock_check_clean` → `1 passed, 36 deselected`(一致)。証拠同上 |
| R-004 | OK | 再実行 `-k doctor_lock_mismatch` → `1 passed, 36 deselected`(一致)。`doctor.sh:176` の `[DATA-LOCK-MISMATCH]` 警告文を確認済み |
| R-005 | OK | 再実行 `-k doctor_backup` → `2 passed, 35 deselected`(一致)。`doctor.sh:188,193,197` の3警告文を確認済み |
| R-006 | OK | 再実行 `-k gate_blocks_upload` → `1 passed, 36 deselected`(一致)。実フック手動実行(`CLAUDE_DATA_GATE=1` + upload コマンド)で `exit=2`(verdict記載どおり）。`.claude/hooks/data_gate.py:57`(`_has_upload_cmd`）、`:82`(BLOCKEDメッセージ)確認済み |
| R-007 | OK | 再実行 `-k gate_blocks_pipe` → `1 passed, 36 deselected`(一致)。`.claude/hooks/data_gate.py:41`(`_segment_head`)確認済み |
| R-008 | OK | 再実行 `-k gate_allows_exports` → `1 passed, 36 deselected`(一致)。`.claude/hooks/data_gate.py:38`(`_EXPORTS_PREFIX`)確認済み |
| R-009 | OK | 再実行 `-k gate_off` → `1 passed, 36 deselected`(一致)。実フック手動実行(env未設定 + upload コマンド)で `exit=0`(verdict記載どおり）。`.claude/hooks/data_gate.py:66`確認済み |
| R-010 | OK | 再実行 `-k gate_fail_open_input` → `1 passed, 36 deselected`(一致)。`.claude/hooks/data_gate.py:65`(`main`)確認済み |
| R-011 | OK | 再実行 `-k dictionary_generate` → `2 passed, 35 deselected`(一致)。`scripts/data_dictionary.py:100`(`main`)確認済み |
| R-012 | OK | 再実行 `-k mask_uses_dictionary` → `1 passed, 36 deselected`(一致)。`.claude/hooks/_mask.py:211`(`_mask_dictionary_patterns`)確認済み |
| R-013 | OK | 再実行 `-k mask_without_dictionary` → `4 passed, 33 deselected`(一致)。`.claude/hooks/_mask.py:185-207`(`_load_dictionary_patterns`、fail-open)確認済み |
| R-014 | OK | 再実行 `-k reportgen_sanitize` → `1 passed, 36 deselected`(一致、staging適用によりskip解消)。`.claude/hooks/_mask.py:227`(`mask()`内)確認済み |
| R-015 | OK | 再実行 `-k export_check` → `1 passed, 36 deselected`(一致)。`scripts/export_check.py:21`(`main`)確認済み |
| R-016 | OK | 再実行 `-k data_scan_diff` → `1 passed, 36 deselected`(一致)。`scripts/data_scan.py:19`(`main`)確認済み |
| R-017 | OK | 再実行 `-k crossreview_quarantine_doc` → `1 passed, 36 deselected`(一致)。`.claude/skills/cross-review/SKILL.md:30` に `data_scan.py` 言及を確認済み |
| R-018 | OK | 再実行 `-k precommit_detects` → `3 passed, 34 deselected`(一致)。`scripts/precommit_data_check.py:94`(`main`)確認済み |
| R-019 | OK | 再実行 `-k precommit_clean_fast` → `1 passed, 36 deselected`(一致)。証拠同上 |
| R-020 | OK | 再実行 `-k doctor_precommit_off` → `1 passed, 36 deselected`(一致)。`doctor.sh:203` 確認済み |
| R-021 | OK | `diff <([DATA-...] doctor.sh) <(... doctor.ps1)` を再実行 → 差分無し、raw12/uniq7 双方(verdict一致)。`doctor.ps1:222`(`[DATA-PRECOMMIT-OFF]`)も確認済み |
| R-022 | OK | 再実行 `-k history_scan` → `1 passed, 36 deselected`(一致)。`scripts/history_scan.py:90`(`main`)確認済み |
| R-023 | OK | 再実行 `-k standards_synthetic` → `1 passed, 36 deselected`(一致)。`.claude/skills/python-standards/SKILL.md:23-25` の合成データ・ログ規約を確認済み |
| R-024 | OK | 再実行 `-k docs_conventions` → `1 passed, 36 deselected`(一致)。`templates/EXPERIMENT_LOG.md.template:3-4`、`.claude/agents/evaluator.md:151` 確認済み。テスト本体(`tests/test_data_protection_phase2.py:993-1007`)は README.md の `export_check`/`BFG`/`filter-repo`/`core.hooksPath` 記載も検査しており実装済みを確認(verdict証拠列にREADME行番号の明記は無いが、実装漏れではなくテストでカバー済み) |
| R-025 | OK | `pytest tests/ -q` を再実行 → `227 passed, 2 skipped`(verdict一致)。skip2件はPhase1/session-monitorのstaging適用済みによる想定内skipであることをテスト名から確認 |
| R-026 | OK | コミット `cd6572199f73d9bc20dc37775b0d23df095a731c` の実在を確認(`git cat-file -t` → `commit`)。差分は `.claude/hooks/_mask.py`(+43）、`.claude/hooks/data_gate.py`(+95、新規）、`.claude/settings.json`(+4）の3ファイルのみで、設計書該当項目(2. data_gateフック新設、5. _mask.py辞書対応)と整合。`settings.json` の `data_gate` 登録は `grep -c` で1件のみ(重複なし)を実測確認 |
| R-027 | OK | 再実行 `-k staging_idempotent` → `1 passed, 36 deselected`(一致)。`tests/test_data_protection_phase2.py:1067-1129` に2回適用のバイト一致・重複登録なし(`len(data_gate_hooks) == 1`)検査を確認済み |
| R-028 | OK | 再実行 `-k scripts_distributed` → `3 passed, 34 deselected`(一致)。claude-init.sh/.ps1、claude-update.sh/.ps1 の `scripts/...` 参照 diff を再実行 → 4ファイルとも raw10/uniq10 で差分無し(verdict一致)。`claude-init.sh:107-109`(配布ファイルリスト)、`:279-300`(MARKER保護つき配置ロジック)確認済み |

## スコープ外変更
`git diff --stat main...HEAD` で26ファイル変更を確認。全て設計書スコープ1〜10
(data_lock/doctor/data_gate/export_check/data_scan/data_dictionary/_mask/
EXPERIMENT_LOG/precommit/scripts配布)に対応するファイルであり、`.claude/plans/`
と `.claude/spec/verdict-*.md` はパイプライン手順の付随成果物(計画書・判定書)。
コードスコープ外の混入なし。

**なし**
