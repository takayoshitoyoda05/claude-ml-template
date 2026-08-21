# Verdict: 研究データ保護 Phase 1(設計書: docs/active/20260821-data-protection-phase1.md)

検証日: 2026-08-21(最終化)
検証範囲: 統合済みブランチ pipeline/20260821-data-protection-p1(HEAD 456a312)。
group-B/D/E/F は全てマージ済み。invariants.md はユーザーの `!` staging 適用
(コミット ac8aa8a)により研究データ保護節が反映済み。以下は全件、統合ブランチの
ワーキングツリーで直接再検証した(worktree 不要)。

| ID | 判定 | 実行コマンド | 実測値 | 証拠(file:line) |
|---|---|---|---|---|
| R-001 | PASS | `uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k invariants_principles` | 1 passed, 13 deselected(`logs/runs/20260821-final-data-protection-phase1-byid.log`) | .claude/improvements/invariants.md:33-35(データ三原則3項目), tests/test_data_protection_phase1.py:117(test_invariants_principles) |
| R-002 | PASS | 同上 `-k invariants_egress` | 1 passed, 13 deselected(同ログ) | .claude/improvements/invariants.md:38(持ち出し規制「集計値・図・ハッシュ」), tests/test_data_protection_phase1.py:129(test_invariants_egress) |
| R-003 | PASS | 同上 `-k invariants_check_mapping` | 1 passed, 13 deselected(同ログ) | .claude/improvements/invariants.md:33-35,38(各行に doctorマーカー名または `Phase 2 の data_gate` を併記), tests/test_data_protection_phase1.py:139(test_invariants_check_mapping) |
| R-004 | PASS | 同上 `-k datalog_template` | 1 passed, 13 deselected(同ログ) | templates/DATA_LOG.md.template:6(7列ヘッダ) |
| R-005 | PASS | 同上 `-k doctor_raw_writable` | 1 passed, 13 deselected(同ログ) | doctor.sh:114(`[DATA-RAW-WRITABLE]`) |
| R-006 | PASS | 同上 `-k doctor_processed_readonly` | 1 passed, 13 deselected(同ログ) | doctor.sh:117(`[DATA-PROCESSED-READONLY]`) |
| R-007 | PASS | 同上 `-k doctor_datalog_missing` | 1 passed, 13 deselected(同ログ) | doctor.sh:120(`[DATA-LOG-MISSING]`) |
| R-008 | PASS | 同上 `-k doctor_no_data_dir` | 1 passed, 13 deselected(同ログ) | doctor.sh:106-121(data 無し時は何も出力しない分岐) |
| R-009 | PASS | 同上 `-k doctor_parity`、および `diff <(grep -oE '\[DATA-[A-Z-]+\]' doctor.sh \| sort -u) <(grep -oE '\[DATA-[A-Z-]+\]' doctor.ps1 \| sort -u)` | pytest: 1 passed, 13 deselected(同ログ)。diff: sh 生3件/一意3件、ps1 生3件/一意3件、diff exit=0(差分なし、`logs/runs/20260821-final-doctor-parity-diff.log`) | doctor.sh:114,117,120 / doctor.ps1:132,136,139 |
| R-010 | PASS | 同上 `-k handoff_checklist` | 1 passed, 13 deselected(同ログ) | .claude/skills/handoff/SKILL.md:23-33(公開・共有前チェックリスト7項目) |
| R-011 | PASS | 同上 `-k paper_checklist` | 1 passed, 13 deselected(同ログ) | .claude/skills/paper-writing/SKILL.md:54-64(handoff と同一文言の7項目) |
| R-012 | PASS | 同上 `-k readme_data_convention` | 1 passed, 13 deselected(同ログ) | README.md:1422(3.21節、raw/processed/synthetic/exports の役割・raw更新手順) |
| R-013 | PASS | 同上 `-k staging_idempotent` | 1 passed, 13 deselected(同ログ) | _staging_data_protection_p1.py(冪等適用ロジック、gitignore 対象・非コミット), tests/test_data_protection_phase1.py:366(test_staging_idempotent_apply_twice) |
| R-014 | PASS | `uv run --with pytest python -m pytest tests/ -q` | 192 passed, exit 0(`logs/runs/20260821-final-full-tests.log`) | logs/runs/20260821-final-full-tests.log |
| R-015 | PASS | (目視・manual)`git show ac8aa8a --stat` / `grep -n "研究データ保護" .claude/improvements/invariants.md` | コミット ac8aa8a でユーザーが `! uv run python _staging_data_protection_p1.py` を実行し invariants.md に「### 研究データ保護」節(10行追加)が反映されたことを確認(`APPLIED` 相当の承認行為) | .claude/improvements/invariants.md:30(`### 研究データ保護`), git commit ac8aa8a |

## 補足
- 全14件(R-001〜R-015)が最終判定 PASS。UNVERIFIABLE は残っていない。
- R-001〜R-003 は前回レビュー時点で invariants.md 未適用のため skip(UNVERIFIABLE)
  だったが、ユーザーの staging `!` 適用(コミット ac8aa8a)により本文に反映され、
  再実行で PASS を確認した。
- R-014 は前回サブブランチ未マージのため `tests/` 全体で 9 failed, 180 passed, 3 skipped
  だった(`logs/runs/20260821-main-full-tests.log`)。group-B/D/E/F のマージ完了後は
  `tests/` 全体 192 passed, 0 failed, 0 skipped / exit 0 を確認した
  (`logs/runs/20260821-final-full-tests.log`)。旧 skip 3件が今回すべて PASS に転じ、
  旧 FAIL 9件も含めて 192 passed に収束しており退行はない。
- R-015 は manual 要件。承認そのものはユーザーの `!` 実行(コミット ac8aa8a)に委ねられており、
  本 verdict では実行事実の確認のみを行った。
