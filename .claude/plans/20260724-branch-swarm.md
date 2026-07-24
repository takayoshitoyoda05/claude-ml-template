# 実装計画: branch-naming 自動検出スキル + Haiku スカウト隊7体

参照設計書: /home/toyod/claude-ml-template/docs/drafts/branch-swarm-spec.md
（本設計書は「## 受け入れ条件」テーブルを持たない実装仕様書だが、セクション7に
機械照合可能な検証コマンド群を持ち、各ファイル変更を逐語的に確定している。
本計画はセクション7 + 各セクションを要件ソースとし、R-ID を導出してトレースする。）

作業スコープ: /home/toyod/claude-ml-template（リポジトリ全体）
ブランチ: pipeline/20260724-branch-swarm（チェックアウト済み）

## 目的
プロジェクトのブランチ命名規則を自動検出する branch-naming スキルと、
リファクタ検出を観点別 Haiku 7体で並列化するスカウト隊を追加する。
検出は多角並列・実装は常に1人（フランケンシュタイン効果の回避）。

## 現状分析（確認済み事項）
- 確認済み: ml-pipeline.md の作業ブランチ作成は「### 1.5.」（本文 L31-41、固定名 `git checkout -b pipeline/YYYYMMDD-<トピック>`）。
- 確認済み: リファクタリング・パスは設計書の言う「5.7」ではなく実際は「### 6.7.」（L267-311）。
  L268「evaluator と evaluator-standards が両方 PASS した場合のみ実行する。」の直後（L270-272）に
  **前提（クリーンツリー）段落が既に存在**し、その後 L274「generator に以下を指示して…」が続く。
  制約ブロックは L290-294。
- 確認済み: 既存エージェントの frontmatter tools 行は `tools: Read, Grep, Glob`（読取専用系）/`model:` 別行。
  スカウトの `tools: Read, Grep, Glob` / `model: haiku` はこの書式と整合。
- 確認済み: README の挿入先見出しは「### 作業ブランチと原子性」（L305、L343「### セキュリティプラグイン…」の直前で終わる）と
  「### 3.12 リファクタリング・パス（磨きの工程）」（L869、L887「### 3.13」の直前で終わる）。
  エージェント表は3列（名前/model/役割, L624）、スキル表は4列（名前/いつ使うか/呼び出し方/出力, L639）、
  環境変数表は3列（変数/意味/未設定時, L193）。
- 確認済み: README の個別エージェント呼び出しは `@planner` / `@generator` 等の表記（L49,452,468）。
  スカウトの「@scout-<名前> で見て」はこの UX と整合。
- 確認済み: docs/ は .gitignore 対象（L6 `docs/`）。docs/branch-convention.md も docs/reports/ も
  **git 管理外のローカルキャッシュ/ローカル生成物**。設計書 docs/drafts/branch-swarm-spec.md も未追跡。
- 確認済み: settings.local.json.template の env は既存15キー。CLAUDE_REFACTOR_SWARM は未定義。
- 確認済み: CHANGELOG に `### Added（2026-07-24）` 節が既存（L53-61）。末尾に1項目追記する。
- 確認済み: 現在ブランチ pipeline/20260724-branch-swarm、docs/branch-convention.md は不在。

## 既知の乖離への対応（設計書からの明示的な逸脱）
1. 設計書の「手順5.7」表記は、実際に作成/改修するファイル内では全て **6.7** に読み替える
   （scout description・scout 本文の呼ばれ方・refactor-scout の比較表・ml-pipeline 改修対象見出し）。
   設計書の目的/前提/図中の 5.7（メタ説明）は成果物ではないため対象外。
2. 並列条件は tmux ではなく「エージェントチーム機能が使える場合」に統一
   （tmux は表示用であり並列の必須条件ではない: 検証済み 2026-07-22）。
   対象: ml-pipeline 6.7 偵察フェーズの条件文、refactor-scout の並列/逐次分岐、
   README 環境変数表「(tmux必要)」→「(エージェントチーム機能が必要)」、
   README 新節「(+ tmux 環境)」「tmux が無い環境では」→ 同趣旨のチーム機能表記。
3. 検証コマンド `! grep -l "Edit\|Write" .claude/agents/scout-*.md` は散文にヒットし偽陽性。
   frontmatter の tools 行だけを検査する形に修正（検証方法セクション参照）。
4. push・設計書削除は行わない（ユーザー明示指示まで）。設計書 L11-12/セクション7の
   git rm/push 手順は計画に含めない。CHANGELOG [Unreleased] Added(2026-07-24) 末尾に1項目追記。
5. docs/branch-convention.md は docs/ 配下（git 管理外）のローカルキャッシュである旨を、
   branch-naming スキル文面と README 新節に一言添える。
6. 8.5 完全レポート生成を最終工程に置く（docs/reports/ はローカル生成のみ・コミットしない）。

## 命名対照表（全グループ共通の契約。A/B/C 横断で一致必須）
| ファイル (name) | 短レンズ名（description・本文用） | README 表レンズ表記 |
|---|---|---|
| scout-naming | 命名 | 命名の磨き |
| scout-duplication | 重複 | 重複と切り出し候補 |
| scout-complexity | 複雑度 | ネスト・長さ・簡潔化 |
| scout-comments | コメント | what コメントのコード化 |
| scout-symmetry | 対称性 | 対称性・音読テスト |
| scout-docstring | docstring | docstring と実装の整合 |
| scout-deadcode | デッドコード | 未使用・到達不能コード |

## 変更対象
| ファイル | 種別 | 変更内容 |
|---|---|---|
| .claude/agents/scout-{naming,duplication,complexity,comments,symmetry,docstring,deadcode}.md | NEW×7 | 共通テンプレート + 各レンズ定義。tools: Read, Grep, Glob / model: haiku。description の「手順5.7」→6.7 |
| .claude/skills/branch-naming/SKILL.md | NEW | ブランチ命名規則の探索・決定。docs/ 配下キャッシュがローカル管理外である旨を追記 |
| .claude/skills/refactor-scout/SKILL.md | NEW | スカウト隊の単独実行。並列条件を tmux→チーム機能に修正、比較表の 5.7→6.7 |
| .claude/commands/ml-pipeline.md | MOD | 1.5 を branch-naming 連携に置換／6.7 に偵察フェーズ挿入 + 制約1行追記 |
| templates/settings.local.json.template | MOD | env に `"CLAUDE_REFACTOR_SWARM": "0"` 追加 |
| README.md | MOD | エージェント表/スキル表/環境変数表に追記、新節2つ（tmux条件は排除） |
| CHANGELOG.md | MOD | Added(2026-07-24) 末尾に1項目 |

## 実装手順
| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 1 | 検証スクリプト（セクション7の修正版コマンド一式）を先に用意し、現時点で「未作成のため失敗する」ことを確認（テストファースト） | scratchpad/verify_swarm.sh（scope 内の一時ファイル） | なし | S(先行) |
| 2 | scout 7体を共通テンプレート+各レンズで作成。frontmatter は `tools: Read, Grep, Glob` / `model: haiku`。description は命名対照表の短レンズ名を使い「ml-pipeline の手順6.7（CLAUDE_REFACTOR_SWARM=1）から並列」「@scout-<名前> で見て」を含める。本文の呼ばれ方も「手順6.7」 | .claude/agents/scout-*.md（7新規） | Step1 | A |
| 3 | branch-naming/SKILL.md 作成（探索手順0-6・生成ルール・キャッシュ保存）。docs/branch-convention.md が docs/ 配下=git 管理外のローカルキャッシュである旨を明記 | .claude/skills/branch-naming/SKILL.md | Step1 | B |
| 4 | refactor-scout/SKILL.md 作成。並列条件を「エージェントチーム機能が使える場合は並列、無ければ逐次」に、比較表の「手順5.7(自動)」を「手順6.7(自動)」に修正 | .claude/skills/refactor-scout/SKILL.md | Step1 | B |
| 5 | ml-pipeline 1.5 本文（L31-41）を branch-naming 連携版に置換（見出し「### 1.5.」は保持）。サブブランチは決定した親名の配下に作る注記を含める | .claude/commands/ml-pipeline.md | Step4 | B |
| 6 | ml-pipeline 6.7：**前提（クリーンツリー）段落の直後・「generator に以下を指示して」の直前**に偵察フェーズ block を挿入（条件は tmux でなくチーム機能）。既存「制約:」ブロック末尾に「- スカウトの提案を採用する場合も、動作不変の制約は変わらない」を追記 | .claude/commands/ml-pipeline.md | Step5 | B |
| 7 | settings.local.json.template の env に `"CLAUDE_REFACTOR_SWARM": "0"` を追加（既存キーは不変、JSON 妥当を維持） | templates/settings.local.json.template | Step1 | C |
| 8 | README：エージェント表に scout 行、スキル表に branch-naming/refactor-scout 行、環境変数表に CLAUDE_REFACTOR_SWARM 行（(tmux必要)→(エージェントチーム機能が必要)）を追記 | README.md | Step1 | C |
| 9 | README「### 作業ブランチと原子性」節の直後（L342 と L343 の間）に「### ブランチ命名規則の自動検出」新節を追記（docs/ キャッシュがローカル管理外の旨を含める） | README.md | Step8 | C |
| 10 | README「### 3.12 リファクタリング・パス（磨きの工程）」節の直後（L885 と L887 の間）に「### Haiku スカウト隊」新節を追記。tmux 条件文は「エージェントチーム機能」に置換 | README.md | Step9 | C |
| 11 | CHANGELOG Added(2026-07-24)（L61 の後）に1項目追記 | CHANGELOG.md | Step1 | C |
| 12 | Step1 の検証スクリプト（修正版）+ verify-hooks.sh + JSON 妥当性を実行し全 PASS を確認 | （実行のみ） | Step2-11 | V(最終) |
| 13 | 手順8.5 完全レポートを docs/reports/<日時>/ にローカル生成（コミットしない） | docs/reports/（git 管理外） | Step12 | V(最終) |

コミット案（各グループ完了時、feat(step N) 形式）:
- Step2 完了 → `feat(step 2): Haikuスカウト隊7体（観点別リファクタ偵察・提案のみ）を追加`
- Step3-6 完了 → `feat(step 6): branch-naming/refactor-scoutスキルとml-pipeline 1.5/6.7改修`
- Step7-11 完了 → `feat(step 11): README/settingsテンプレ/CHANGELOGにスカウト隊・命名検出を反映`
（push はしない。設計書削除もしない。）

## 並列化判定
並列化可能（グループ A=scout7体 / B=スキル2本+ml-pipeline / C=README+テンプレ+CHANGELOG）。
理由: 3グループの対象ファイル集合は完全に分離しており、スカウト名・レンズ名の
唯一の契約は設計書（逐語確定）+ 本計画の命名対照表にあるため、各グループは
出力の相互参照なしに独立実装できる。ただし7体は共通テンプレートからの機械展開で
整合が命なので、グループ A 内は1人が7体まとめて書く（Step2 は分割しない）。
最終の Step12/13 は全グループ完了に依存する逐次工程。
注: 保守的判断として、B 内で ml-pipeline を触る Step5→6 と README を触る
Step8→9→10 は同一ファイルのため各グループ内で逐次にする。

## 検証方法（セクション7の修正反映 + fail-fast）
以下を上から実行し、いずれかで失敗したら即停止（fail-fast）。全 PASS で合格。
```bash
set -e
# スカウト7体の存在
for s in naming duplication complexity comments symmetry docstring deadcode; do
  test -f .claude/agents/scout-$s.md
done
# 全スカウトが model: haiku（7）
test "$(grep -l '^model: haiku$' .claude/agents/scout-*.md | wc -l)" -eq 7
# 【修正3】frontmatter tools 行だけを検査: 正しい tools 行がちょうど7
test "$(grep -c '^tools: Read, Grep, Glob$' .claude/agents/scout-*.md | grep -c ':1$')" -eq 7
# 【修正3】tools 行に Edit/Write が無いこと（散文は対象外）
! grep -E '^tools:.*(Edit|Write)' .claude/agents/scout-*.md
# 【修正1】作成物に「手順5.7」「5.7.」が残っていないこと
! grep -rn '手順5\.7\|5\.7\.' .claude/agents/scout-*.md .claude/skills/refactor-scout/SKILL.md
# 2スキルの存在
test -f .claude/skills/branch-naming/SKILL.md
test -f .claude/skills/refactor-scout/SKILL.md
# ml-pipeline 改修
grep -q 'branch-naming' .claude/commands/ml-pipeline.md
grep -q 'CLAUDE_REFACTOR_SWARM' .claude/commands/ml-pipeline.md
# settings テンプレの追加 + JSON 妥当
grep -q 'CLAUDE_REFACTOR_SWARM' templates/settings.local.json.template
python -c "import json; json.load(open('templates/settings.local.json.template'))"
python -c "import json; json.load(open('.claude/settings.json'))"
# README 追記
grep -q 'ブランチ命名規則の自動検出' README.md
grep -q 'Haiku スカウト隊' README.md
grep -q 'CLAUDE_REFACTOR_SWARM' README.md
# 【修正2】README・スキルに並列条件としての tmux 必須表現が残っていないこと
! grep -n 'tmux必要\|tmux が無い環境では逐次\|かつ tmux 環境' README.md .claude/commands/ml-pipeline.md .claude/skills/refactor-scout/SKILL.md
echo "ALL PASS"
```
続けてフック検証:
```bash
./verify-hooks.sh   # PowerShell 環境なら .\verify-hooks.ps1
```
期待結果: 上記スクリプトが `ALL PASS` を出力し、verify-hooks が全項目 PASS。

## リスク
- 【採用案=A/B/C 3並列】代替案1: 完全逐次。整合は最も安全だが、対象ファイルが
  完全分離しているため並列の整合リスクは命名対照表で吸収でき、逐次にする利得が薄い→不採用。
  代替案2: 7体を7ステップに分割し scout も並列化。共通テンプレートの機械展開で
  1人が書く方が整合的（設計原理そのもの）→ scout はグループ内単一ステップに集約。
- 失敗シナリオ1: スカウト名/レンズ名が A/B/C で食い違う → 命名対照表を単一契約とし
  検証で grep 照合（Step12 で README とエージェント名の突合を目視/grep 確認）。
- 失敗シナリオ2: 6.7 偵察フェーズの挿入位置を「PASS 直後（前提段落より前）」に置くと、
  クリーンツリー・ゲートより先に偵察が走る文面になり整合が崩れる → **前提段落の直後**に
  挿入する（Step6 の注記）。偵察は実装フェーズの検出方式設定、前提は実行可否ゲートで層が異なる。
- 失敗シナリオ3: settings テンプレ追記で末尾カンマ/JSON 破損 → Step12 で json.load 検証。
- 未確認の仮定: なし（挿入境界・見出し・表列数・frontmatter 書式・gitignore・CHANGELOG 節は
  全て本調査で裏取り済み）。
- 非互換: 既存キー・既存本文は変更しない（1.5 は本文置換だが見出し保持、6.7 は追記のみ）。
  guard_bash がリダイレクト書き込みをブロックする可能性があるが、対象は作業スコープ内・
  非保護ファイルのため許可される想定（.claude/settings.json 等の保護ファイルは触らない）。

## トレーサビリティ
要件ソース = 設計書の各セクション + セクション7検証コマンド（本計画で R-ID 化）。
| ID | 要件 | 対応ステップ | 検証方法 |
|---|---|---|---|
| R-01 | branch-naming スキル新規（探索0-6/生成/キャッシュ） | Step3 | test -f .claude/skills/branch-naming/SKILL.md |
| R-02 | ml-pipeline 1.5 が branch-naming 連携 | Step5 | grep -q 'branch-naming' ml-pipeline.md |
| R-03 | scout 7体新規・model haiku・tools 読取専用・description 6.7 | Step2 | 存在7 / grep -c '^model: haiku$'=7 / tools 行検査 |
| R-04 | refactor-scout スキル新規（単独実行・レンズ選択） | Step4 | test -f .claude/skills/refactor-scout/SKILL.md |
| R-05 | ml-pipeline 6.7 偵察フェーズ + 制約1行 | Step6 | grep -q 'CLAUDE_REFACTOR_SWARM' ml-pipeline.md |
| R-06 | settings テンプレに CLAUDE_REFACTOR_SWARM=0 | Step7 | grep + json.load(template) |
| R-07 | README エージェント表/スキル表/環境変数表 追記 | Step8 | grep 'CLAUDE_REFACTOR_SWARM' README.md |
| R-08 | README「ブランチ命名規則の自動検出」新節 | Step9 | grep 'ブランチ命名規則の自動検出' README.md |
| R-09 | README「Haiku スカウト隊」新節 | Step10 | grep 'Haiku スカウト隊' README.md |
| R-10 | 手順5.7→6.7 読み替えを全成果物に反映 | Step2,4,6 | ! grep '手順5\.7\|5\.7\.' 成果物 |
| R-11 | 並列条件を tmux→エージェントチーム機能に統一 | Step4,6,8,10 | ! grep 'tmux必要\|かつ tmux 環境\|tmux が無い環境では逐次' |
| R-12 | 検証はフロントマター tools 行のみ検査（偽陽性排除） | Step1,12 | grep -c '^tools: Read, Grep, Glob$'=7 かつ ! grep -E '^tools:.*(Edit|Write)' |
| R-13 | CHANGELOG に1項目追記 | Step11 | grep で追記行を確認（目視） |
| R-14 | docs/ キャッシュがローカル管理外の旨を明記 | Step3,9 | grep で該当文言確認（目視） |
| R-15 | push・設計書削除を行わない | 全体（含めない） | git log にレポート/削除コミット無し（目視） |
| R-16 | 8.5 完全レポートをローカル生成・非コミット | Step13 | docs/reports/<日時>/report.md 生成、git status に未追跡（docs/ は無視される） |
