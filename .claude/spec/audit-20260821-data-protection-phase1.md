# 監査結果: 研究データ保護 Phase 1(設計書: docs/active/20260821-data-protection-phase1.md)

監査日: 2026-08-21
監査対象: verdict-20260821-data-protection-phase1.md(全15件 PASS 主張、コミット 5be83ad 時点)
監査方法: 記載の auto コマンドを独立に再実行(uv run pytest -k 各件、tests/ 全体、doctor.sh/ps1 の
diff)、証拠 file:line を Read で直接確認、R-015 は git show ac8aa8a --stat で実在確認、
git diff/log で main ブランチとの差分をスコープ外変更の有無について確認。

## 監査結果

| ID | 結果 | 備考 |
|---|---|---|
| R-001 | OK | 再実行: `-k invariants_principles` → `1 passed, 13 deselected`(verdict一致)。証拠 .claude/improvements/invariants.md:33-35 実在(raw不可侵/スクリプト前処理/DATA_LOG唯一の真実の3行)。tests/test_data_protection_phase1.py:117 に test_invariants_principles 実在。 |
| R-002 | OK | 再実行: `-k invariants_egress` → `1 passed, 13 deselected`(verdict一致)。証拠 invariants.md:38 に「集計値・図・ハッシュ」実在。tests/test_data_protection_phase1.py:129 に test_invariants_egress 実在。 |
| R-003 | OK | 再実行: `-k invariants_check_mapping` → `1 passed, 13 deselected`(verdict一致)。invariants.md:33-35,38 各行に doctorマーカー名(`[DATA-RAW-WRITABLE]`等)または「Phase 2 の data_gate」の対応表記を確認。tests/test_data_protection_phase1.py:139 に test_invariants_check_mapping 実在。 |
| R-004 | OK | 再実行: `-k datalog_template` → `1 passed, 13 deselected`(verdict一致)。templates/DATA_LOG.md.template:6 に7列ヘッダ(データセット名/入手元/入手日/ライセンス/sha256/前処理コマンド/識別子列)を確認。 |
| R-005 | OK | 再実行: `-k doctor_raw_writable` → `1 passed, 13 deselected`(verdict一致)。doctor.sh:114 に `[DATA-RAW-WRITABLE]` の警告出力を確認。 |
| R-006 | OK | 再実行: `-k doctor_processed_readonly` → `1 passed, 13 deselected`(verdict一致)。doctor.sh:117 に `[DATA-PROCESSED-READONLY]` の警告出力を確認。 |
| R-007 | OK | 再実行: `-k doctor_datalog_missing` → `1 passed, 13 deselected`(verdict一致)。doctor.sh:120 に `[DATA-LOG-MISSING]` の警告出力を確認。 |
| R-008 | OK | 再実行: `-k doctor_no_data_dir` → `1 passed, 13 deselected`(verdict一致)。doctor.sh:106-121 は `if [ -d "data" ]` で全体を囲んでおり、data/ 不在時は何も出力しない分岐を確認。 |
| R-009 | OK | 再実行: `-k doctor_parity` → `1 passed, 13 deselected`(verdict一致)。`diff <(grep -oE '\[DATA-[A-Z-]+\]' doctor.sh \| sort -u) <(...doctor.ps1...)` を独立実行し、sh 生3件/一意3件、ps1 生3件/一意3件、diff exit=0(差分なし)を確認(verdict実測値と一致)。証拠 doctor.sh:114,117,120 / doctor.ps1:132,136,139 実在を確認。 |
| R-010 | OK | 再実行: `-k handoff_checklist` → `1 passed, 13 deselected`(verdict一致)。.claude/skills/handoff/SKILL.md:23-33 にチェックリスト見出しと7項目(git履歴/notebook出力/テストfixture/ログ/レポート・evidence/MLflow/exports予定物)を確認。 |
| R-011 | OK | 再実行: `-k paper_checklist` → `1 passed, 13 deselected`(verdict一致)。.claude/skills/paper-writing/SKILL.md:54-64 に handoff と同一文言の7項目を確認。 |
| R-012 | OK | 再実行: `-k readme_data_convention` → `1 passed, 13 deselected`(verdict一致)。README.md:1422 に「### 3.21 データディレクトリの運用規約(data/)」節、raw/processed/synthetic/exports の役割表、raw更新手順(chmod +w→更新→DATA_LOG追記→chmod -w)を確認。 |
| R-013 | OK | 再実行: `-k staging_idempotent` → `1 passed, 13 deselected`(verdict一致)。_staging_data_protection_p1.py は .gitignore(`/_staging_*`)対象でリポジトリ非コミットだが実ファイルとして存在を確認。tests/test_data_protection_phase1.py:366 に test_staging_idempotent_apply_twice 実在。 |
| R-014 | OK | 再実行: `uv run --with pytest python -m pytest tests/ -q` → `192 passed`, exit 0(verdict実測値「192 passed」と一致)。 |
| R-015 | OK | `git show ac8aa8a --stat` を再実行し、コミット ac8aa8a(`.claude/improvements/invariants.md \| 10 ++++++++++`、1 file changed, 10 insertions)の実在を確認。現在の作業ブランチに含まれる(`git branch --contains ac8aa8a` で確認)。invariants.md:30 に「### 研究データ保護」節の実在を確認。 |

## スコープ外変更

なし。`git diff --stat main...HEAD` で確認した変更ファイルは以下の10件で、いずれも受け入れ条件テーブルの
いずれかのIDに対応する(design doc・plan・verdict 等の作業成果物含む):
- `.claude/improvements/invariants.md`(R-001〜003, R-015)
- `.claude/plans/20260821-data-protection-p1.md`(計画文書、実装対象外の作業記録)
- `.claude/skills/handoff/SKILL.md`(R-010)
- `.claude/skills/paper-writing/SKILL.md`(R-011)
- `.claude/spec/verdict-20260821-data-protection-phase1.md`(検証記録)
- `README.md`(R-012)
- `doctor.ps1` / `doctor.sh`(R-005〜009)
- `templates/DATA_LOG.md.template`(R-004)
- `tests/test_data_protection_phase1.py`(全ID共通のテスト実装)

作業ツリーに未コミット差分なし(`git status` clean)。`docs/active/20260821-data-protection-phase1.md` は
リポジトリ全体で `docs/` が .gitignore 対象のためどのコミットにも含まれないが、これは本テンプレートの
既存規約(設計書はローカル管理・非コミット)であり、本Phaseで新たに追加された挙動ではない。
