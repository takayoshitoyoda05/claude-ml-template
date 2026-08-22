# Verdict: 20260822-data-protection-phase3

評価対象: `docs/active/20260822-data-protection-phase3.md` の受け入れ条件(R-001〜R-024)
計画: `.claude/plans/20260822-data-protection-p3.md`

評価時点: 統合ブランチ `pipeline/20260822-data-protection-p3`(714d5df)
+ 未マージの並列グループ worktree(group-B/D/E/F)を個別に検証。
**この設計書のマージ(統合)自体はまだ完了していない**ため、
「メイン統合ブランチで `pytest tests/ -q` が全PASS」という完了条件は
未達(各グループworktreeでは個別PASS)。マージ後の再検証が必要。

| ID | 判定 | 実行コマンド | 実測値 | 証拠(file:line) |
|---|---|---|---|---|
| R-001 | PASS | サンドボックス直接実行(NO_READ=1, data/raw/x.csv Read) | exit 2、行動つき文言(data_summary/data_unlock双方言及)を含むstderr 実測 | `_staging_data_protection_p3.py:170-178`(main側のBLOCKEDメッセージ) |
| R-002 | PASS | サンドボックス直接実行(synthetic/exports/data.lock/.backup_stamp) | 4パス全て exit 0 実測 | `_staging_data_protection_p3.py:120-124`(`_is_excluded_data_rel`) |
| R-003 | PASS | サンドボックス直接実行(NO_READ=raw) | raw→exit 2, processed→exit 0 実測 | `_staging_data_protection_p3.py:127-134`(`_no_read_blocks_rel`) |
| R-004 | PASS | サンドボックス直接実行(未設定/`0`) | 両方 exit 0 実測 | `_staging_data_protection_p3.py:129`(`no_read_value in ("", "0")`) |
| R-005 | PASS | サンドボックス直接実行(非JSON/tool_input欠落/src/metadata) | 全て exit 0 実測 | `_staging_data_protection_p3.py:138-148` |
| R-006 | PASS | サンドボックス直接実行(cat/head/tail/less, NO_READ=1 vs GATE=1単独) | NO_READ=1で4種全exit 2、GATE=1単独(NO_READ/PROFILE空)ではcat exit 0(Phase2挙動不変) 実測 | `_staging_data_protection_p3.py:426-432`(main冒頭のプロファイル解決分岐) |
| R-007 | PASS | サンドボックス直接実行(窓口実行コマンド) | `uv run python scripts/data_summary.py data/raw/x.csv`(NO_READ=1) → exit 0 実測 | `_staging_data_protection_p3.py:410-411`(`_WINDOW_SCRIPT`) |
| R-008 | PASS | サンドボックス直接実行(未来/過去/非整数/空の記録) / `tests/test_data_protection_phase3.py -k unlock_window` | 未来→両フックexit 0+解除中stderr、過去/非整数/空→両フックexit 2 実測。`--minutes`境界値(30/240/241/0/-5)も想定通り(logs/runs/20260822-staging-apply1.log系で直接実測、記録参照) | `_staging_data_protection_p3.py:85-96, 355-370`, `.claude/hooks/data_unlock.py` 相当(staging生成物) |
| R-009 | PASS | サンドボックス直接実行(guard_bash)+ main `-k unlock_agent_blocked` | guard_bash直接実行: exec/copy→exit 2(案内文言あり)、grep参照→exit 0。加えて guard_scope の Write ブロック(`.claude/spec/data_unlock.txt`)も `-k unlock_agent_blocked_write_via_guard_scope` で1 passed(subprocess・returncode==2) | `_staging_data_protection_p3.py:577-592`(`data_unlock_execution`)、`tests/test_data_protection_phase3.py:459-477` |
| R-010 | PASS | group-B `-k summary_outputs` | 1 passed | `.worktrees/group-B/scripts/data_summary.py:149-180` |
| R-011 | PASS | group-B `-k summary_no_row_values` + 直接実行(ZZTOPSECRET*埋め込み) | 1 passed + 直接実行でstdout/stderrにセル値が0件(`grep -c ZZTOPSECRET` = 0) | `.worktrees/group-B/scripts/data_summary.py:8-10, 202-208` |
| R-012 | PASS | サンドボックス直接実行(sensitive/internal/public/空 全組み合わせ) | sensitive→両ブロック(read exit2/bash exit2)、internal→読みは許可・GATEのみ有効(catはegress対象外のためexit0)、public/空→exit0/exit0。両フック一致 実測 | `_staging_data_protection_p3.py:69-82, 330-352` |
| R-013 | PASS | サンドボックス直接実行(NO_READ=0+sensitive / GATE=0+sensitive) | 前者: Read exit 0、後者: curlアップロード exit 0(個別変数が優先) 実測 | `_staging_data_protection_p3.py:76-78, 337-339, 348-350` |
| R-014 | PASS(要マージ後再確認) | group-E `-k docs_phase3`(1 passed)/ `-k profile_wiring_docs` は単体worktreeでは失敗(E+F双方の変更が要る) | template/config-set/config-explainへの3変数配線はgroup-E側で確認済み、OPTIONAL_FEATURES(sh/ps1)へのフラグ系2変数追加・PROFILE非掲載はgroup-F側で確認済み。単体テストは分割されておらずマージ後に`-k profile_wiring_docs`で再検証要 | `templates/settings.local.json.template`(group-E diff)、`claude-init.sh:141-142`(group-F diff) |
| R-015 | PASS | group-B `-k backup_encrypt` + age不在直接実行 | 3 passed, 1 skipped(age実在時のみのテストは本環境age未導入のためskip)。直接実行でexit 1・data/内容不変(sha256一致)・出力ファイル未生成を確認 | `.worktrees/group-B/scripts/backup_encrypt.py:89-94` |
| R-016 | PASS | group-D `-k doctor_key_checks` | 1 passed | `.worktrees/group-D/doctor.sh:206-216` |
| R-017 | PASS | group-D `-k doctor_profile_unset` | 1 passed | `.worktrees/group-D/doctor.sh:228-263` |
| R-018 | PASS | group-E `-k docs_phase3` | 1 passed | `.worktrees/group-E/README.md`(diff: synthetic節、age復号手順、読み取り遮断/一時解除/Grep既知の限界、data_gate段落更新) |
| R-019 | PASS | group-F `-k scripts_distributed_p3` + `./verify-installers.sh` | 1 passed, 1 skipped(E2Eはstaging未適用のため一部skip)/ verify-installers.sh 全28件PASS(logs/runs/20260822-groupF-tests.log) | `.worktrees/group-F/claude-init.sh:107-109,141-142,277-282`, `claude-update.sh:98-99,203-204` |
| R-020 | PASS | group-D `-k doctor_parity_p3` + `diff <(grep -oE '\[DATA-[A-Z-]+\]' doctor.sh\|sort -u) <(同 doctor.ps1)` | 1 passed。マーカー: raw19件/一意10件(sh・ps1とも)、diff差分なし | `.worktrees/group-D/doctor.sh`, `doctor.ps1` |
| R-021 | PASS | mainサンドボックスで `_staging_data_protection_p3.py --root` を2回適用 | 2回とも exit 0、`.claude`配下バイト単位一致(`diff -r`で差分なし)、Read matcher件数=1 | `_staging_data_protection_p3.py:693-720`(`apply_settings`の冪等判定) |
| R-022 | PASS | main `-k hooks_selfcontained_p3` | 1 passed | `tests/test_data_protection_phase3.py:1100-1109` |
| R-023 | NEEDS_REVISION(マージ未完了。退行ではない) | `uv run --with pytest python -m pytest tests/ -q`(main統合ブランチ) | 8 failed, 215 passed, 32 skipped(`logs/runs/20260822-main-full.log`)。失敗8件は全てgroup-B/D/E/Fの担当範囲に1:1対応し、各worktree単体では該当テストがPASSすることを確認済み(未マージが原因) | `logs/runs/20260822-main-full.log` |
| R-024 | UNVERIFIABLE(manual・未実施) | (ユーザーの`!`実行待ち) | main上で `.claude/hooks/data_read_gate.py` が未配置であることを確認(staging未適用)。ユーザー承認・適用は本レビューの範囲外 | `_staging_data_protection_p3.py`(untracked, staging方式) |
