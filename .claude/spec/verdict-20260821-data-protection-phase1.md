# Verdict: 研究データ保護 Phase 1(設計書: docs/active/20260821-data-protection-phase1.md)

検証日: 2026-08-21
検証範囲: 統合ブランチ pipeline/20260821-data-protection-p1 + サブブランチ
group-B/D/E/F(worktree)+ メイン untracked _staging_data_protection_p1.py(group C)。
サブブランチは統合ブランチへ未マージのため、R-004〜R-012 はグループ別 worktree 内で検証した
(タスク指示の「グループ別検証が正」に従う)。

| ID | 判定 | 実行コマンド | 実測値 | 証拠(file:line) |
|---|---|---|---|---|
| R-001 | UNVERIFIABLE | `uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k invariants_principles`(main, skip)/ 手動 `--root` 適用テストによるロジック検証 | main では invariants.md 未適用のため3件 skip(`logs/runs/20260821-main-data-protection-phase1.log`)。ロジックは `_staging_data_protection_p1.py` の SECTION_TEXT を静的確認し、`test_staging_idempotent_apply_twice`(1 passed, `logs/runs/20260821-main-staging-idempotent.log`)で適用結果が正しく生成されることを確認済み。R-015(ユーザーの `!` 実行)待ち | _staging_data_protection_p1.py:28-30(SECTION_TEXT の三原則), tests/test_data_protection_phase1.py:117(test_invariants_principles) |
| R-002 | UNVERIFIABLE | 同上 -k invariants_egress | 同上(skip、R-015待ち)。SECTION_TEXT に「集計値・図・ハッシュ」を静的確認 | _staging_data_protection_p1.py:33, tests/test_data_protection_phase1.py:129 |
| R-003 | UNVERIFIABLE | 同上 -k invariants_check_mapping | 同上(skip、R-015待ち)。全箇条書きに `[DATA-XXX]` または `Phase 2` の検査名併記を静的確認 | _staging_data_protection_p1.py:28-33, tests/test_data_protection_phase1.py:139 |
| R-004 | PASS | `cd .worktrees/group-B && uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k datalog_template` | 1 passed, 13 deselected(`logs/runs/20260821-group-B-datalog_template.log`) | .worktrees/group-B/templates/DATA_LOG.md.template:6(7列ヘッダ) |
| R-005 | PASS | `cd .worktrees/group-D && ... -k doctor_raw_writable` | group-D 全体で6 passed, 8 deselected, 0.89s(`logs/runs/20260821-group-D-doctor.log`) | .worktrees/group-D/doctor.sh:114 |
| R-006 | PASS | 同上 -k doctor_processed_readonly | 同上ログに含まれる(6 passed に含む) | .worktrees/group-D/doctor.sh:117 |
| R-007 | PASS | 同上 -k doctor_datalog_missing | 同上 | .worktrees/group-D/doctor.sh:120 |
| R-008 | PASS | 同上 -k doctor_no_data_dir | 同上 | .worktrees/group-D/doctor.sh:106-121(data無し時は何も出力しない分岐) |
| R-009 | PASS | 同上 -k doctor_parity、および `diff <(grep -oE '\[DATA-[A-Z-]+\]' doctor.sh \| sort -u) <(grep -oE '\[DATA-[A-Z-]+\]' doctor.ps1 \| sort -u)` | pytest: 6 passed に含む。diff: 生3件/一意3件が両ファイルで一致、diff exit=0(差分なし) | .worktrees/group-D/doctor.sh:114,117,120 / doctor.ps1:132,136,139 |
| R-010 | PASS | `cd .worktrees/group-E && ... -k "handoff_checklist or paper_checklist"` | 2 passed, 12 deselected(`logs/runs/20260821-group-E-checklists.log`) | .worktrees/group-E/.claude/skills/handoff/SKILL.md:27-33(7項目) |
| R-011 | PASS | 同上 | 同上ログに含む | .worktrees/group-E/.claude/skills/paper-writing/SKILL.md:58-64(7項目、handoffと同一文言) |
| R-012 | PASS | `cd .worktrees/group-F && ... -k readme_data_convention` | 1 passed, 13 deselected(`logs/runs/20260821-group-F-readme.log`) | .worktrees/group-F/README.md:1422-1438(3.21節、raw更新手順) |
| R-013 | PASS | `cd /home/toyod/claude-ml-template && uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k staging_idempotent` | 1 passed, 13 deselected(`logs/runs/20260821-main-staging-idempotent.log`) | tests/test_data_protection_phase1.py:366(test_staging_idempotent_apply_twice), _staging_data_protection_p1.py:41-45(SKIP分岐) |
| R-014 | UNVERIFIABLE | `uv run --with pytest python -m pytest tests/ -q`(統合ブランチ、未マージ状態) | 9 failed, 180 passed, 3 skipped(`logs/runs/20260821-main-full-tests.log`)。FAIL 9件はすべて group-B/D/E/F 未マージに起因(datalog_template/doctor系5件/handoff・paper/readme)で、各グループ内では全PASSを確認済み。既存178件(baseline: main で177 passed+1 skipped、`logs/runs/20260821-baseline-main-full-tests.log`)は退行なし(180 passed = 178既存のうち177+新規2件、skip 1件は既存skip)。マージ後の統合テストで exit 0 の再検証が必要 | logs/runs/20260821-main-full-tests.log, logs/runs/20260821-baseline-main-full-tests.log |
| R-015 | UNVERIFIABLE | (目視)`grep -n "研究データ保護" .claude/improvements/invariants.md` | 該当なし(未適用)。ユーザーの `! uv run python _staging_data_protection_p1.py` 実行待ち(manual) | .claude/improvements/invariants.md(該当節なし、2026-08-21時点) |

## 補足
- R-001〜R-003, R-014, R-015 は「サブブランチ未マージ」「invariants.md 未承認」という
  設計上の意図的な待機状態であり、実装の欠陥ではない(計画のトレーサビリティ表・
  検証方法表に明記された想定シーケンスと一致)。
- 承認後(R-015 実行後)および全グループのマージ後に、本ファイルの R-001〜R-003, R-014
  を再検証すること。
