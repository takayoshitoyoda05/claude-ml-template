| ID | 判定 | 実行コマンド | 実測値 | 証拠(file:line) |
|---|---|---|---|---|
| R-001 | PASS | `git show pipeline/20260911-tdd-gate-group-B:.claude/skills/tdd/SKILL.md \| grep -c "失敗ログ"` 他3語 | 「失敗ログ」1、「先行コミット」1、`--rearm` 1、「mutation」1。既存見出し4節すべて残存 | .claude/skills/tdd/SKILL.md:12-16(失敗ログ・先行コミット), :17-21(--rearm), :50-51(mutation), 見出し行 10/25/35/41 |
| R-002 | UNVERIFIABLE | (group A の担当範囲。本レビューは B/C/D のみ) | 未検証 | - |
| R-003 | UNVERIFIABLE | (group A の担当範囲) | 未検証 | - |
| R-004 | UNVERIFIABLE | (group A の担当範囲) | 未検証 | - |
| R-005 | UNVERIFIABLE | (group A の担当範囲) | 未検証 | - |
| R-006 | UNVERIFIABLE | (group A の担当範囲) | 未検証 | - |
| R-007 | UNVERIFIABLE | (group A の担当範囲) | 未検証 | - |
| R-008 | UNVERIFIABLE | (group A の担当範囲) | 未検証 | - |
| R-009 | UNVERIFIABLE | (group A の担当範囲) | 未検証 | - |
| R-010 | UNVERIFIABLE | (group A の担当範囲) | 未検証 | - |
| R-011 | UNVERIFIABLE | (group A の担当範囲) | 未検証 | - |
| R-012 | UNVERIFIABLE | (group A の担当範囲) | 未検証 | - |
| R-013 | UNVERIFIABLE | (group A の担当範囲。settings.json 登録は staging 適用後のみ成立) | 未検証 | - |
| R-014 | UNVERIFIABLE | (group A の担当範囲) | 未検証 | - |
| R-015 | PASS | `git show pipeline/20260911-tdd-gate-group-C:templates/settings.local.json.template \| python3 -m json.tool`、`grep -n CLAUDE_TDD_GATE README.md` | template は `json.load` でパース可、`CLAUDE_TDD_GATE` は既定値 `"0"`、既存キーの消失なし(before/after のキー集合差分: lost=空集合)。README 環境変数表に1行、フック一覧表に tdd_gate.py の1行のみ(tdd_red.py/tdd_unlock.py は非掲載)、ファイルツリーに3本すべて掲載 | templates/settings.local.json.template:23, README.md:265(環境変数表), README.md:940(フック一覧表), README.md:1841-1843(ファイルツリー) |
| R-016 | UNVERIFIABLE | (group A の担当範囲。verify-hooks.sh/.ps1 の変更なし) | 未検証 | - |
| R-017 | UNVERIFIABLE | (group A の担当範囲) | 未検証 | - |
| R-018 | UNVERIFIABLE | (manual、group A 適用後にユーザー確認) | 未検証 | - |
| R-019 | UNVERIFIABLE | (group A の担当範囲) | 未検証 | - |
| R-020 | UNVERIFIABLE | (group A の担当範囲) | 未検証 | - |
| R-021 | PASS | `git show pipeline/20260911-tdd-gate-group-D:.github/workflows/verify-hooks.yml \| python3 -c "import yaml; yaml.safe_load(...)"`、`grep -c ParseFile` | YAML パース可、`ParseFile` 1件、既存4ステップ(checkout/setup-uv/verify-hooks.sh/verify-installers.sh)が順序も含め残存し、新ステップは末尾に追加 | .github/workflows/verify-hooks.yml:27-38(Check verify-hooks.ps1 syntax、`$path` は verify-hooks.ps1 を指す) |

備考: 本表は B/C/D グループ(ドキュメント/設定変更)のみを対象にレビューした結果。
R-002〜R-014, R-016〜R-020 は group A(フック3本・staging・verify-hooks 本体)の担当範囲であり、
本レビューでは実行・検証していない(UNVERIFIABLE=安全側。PASS 扱いにはしていない)。
group A の evaluator が該当行を上書きすること。
