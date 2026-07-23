# 実装計画: 設計書と Planner のリッチ化(SDD工程の移植)

参照設計書: `/home/toyod/claude-ml-template/docs/drafts/planner-rich-spec.md`
作業スコープ: `/home/toyod/claude-ml-template`(テンプレート自体の改修)

## 目的
SDD(仕様駆動開発)の実装前3工程 — 曖昧性タクソノミー(clarify)+EARS記法、
設計書品質検査(spec-checklist、必須ゲート)、トレーサビリティ表(analyze)—
を外部ツールなしで既存構成に組み込み、設計密度を上げて手戻りを減らす。

## 現状分析(確認済みの事実)
- 確認済み: ml-pipeline.md の計画セクションは実際には **「### 3. 計画の作成」(L50)** と
  **「### 3.5. 計画の承認判定」(L54)**。設計書の「2.3/2.5」は誤り。挿入は **### 3.3** とし、
  全ファイル横断で `2.3→3.3` / `2.5→3.5` に読み替える。
- 確認済み: design-interview SKILL.md の受け入れ条件テーブルは **ID/要件/検証方法/期待結果/種別/対象**
  の6列(L24-32)。設計書テンプレの `状態` 列は誤りで、**対象** に合わせる(planner.md L14・README L218 も同表記)。
- 確認済み: design-interview「## 進め方」は 1〜8 の番号ステップ+「## 完了時」の 9。
  「## 知識の自動スタック(手順8の直後に…)」の見出しは 受け入れ条件生成ステップ(現8)を指す。
- 確認済み: planner.md に「## 計画フォーマット」(L53-62 のテーブル)/「## 計画の実装手順の出力例」(L74-83)/
  「## 制約」(L64-72)が実在。挿入位置はいずれも末尾追記で成立する。
- 確認済み: claude-init.sh / claude-update.sh は `.claude/{agents,commands,hooks,skills,output-styles,rules}` を
  `cp -r` で丸ごと配布(L38-40)する一方、`templates/` は**個別ファイルのみ**を特定の宛先へコピー
  (codex-config / settings.local.json / spec-gate.yml / CLAUDE.md)。`templates/ADR.md.template` や
  `templates/CONTEXT.md.template` は配布対象外=**参照専用テンプレの前例**。
  → 新規 `.claude/skills/spec-checklist/` は既存の丸ごと配布で自動的に downstream へ届く。
  → 新規 `templates/design-doc.md.template` は配布されない=README が案内するパスが downstream で
     参照不能になる(Codexレビュー指摘の採用)。設計書セクション5の指示どおり、init/update の4スクリプトに
     `templates/*.template` を取得先プロジェクトの `templates/` へコピーする処理を追加する
     (ADR/CONTEXT テンプレの参照も同時に解決される)。.ps1 は既存の Copy-Item 行の書式を踏襲した
     最小追加とし、本機で構文検証不能な点はリスク欄に記録(既知の受容済みリスク)。
- 確認済み: README のスキル表は **4列**(名前 / いつ使うか / 呼び出し方(例) / 出力、L606-631)。
  設計書のスキル表追記例(3列)は4列に補う。design-interview 行は L609。
- 確認済み: README 冒頭のワークフロー mermaid(L7-30)に `B[Planner…] --> C{計画の承認…}` があり、
  3.3 の必須ゲートは B→C 間に位置するため、図に反映しないと齟齬が出る(最小1ノード挿入で対応)。
- 確認済み: 「### 2.4 典型的な流れ(スキルとの組み合わせ)」は L535、直後(「### 実例」L559 の前)が SDD 新節の挿入点。
- 確認済み: verify-hooks.sh は実行ビット無し → 検証は `bash ./verify-hooks.sh`。
- 確認済み: docs/ は .gitignore 済み(L6)。設計書は git 管理外。末尾の「git rm + push」は実行不能かつ
  push はユーザー明示指示まで行わない。設計書の移動(drafts→active)もしない(本タスクは通常の実装指示であり、
  この spec は R-ID 形式の受け入れ条件テーブルを持たない実装仕様書。受け入れ条件は親タスク指示が供給する)。

## 変更対象

| ファイル | 種別 | 変更内容の要点 | 群 |
|---------|------|--------------|----|
| `.claude/skills/spec-checklist/SKILL.md` | NEW | 設計書品質を5次元検査。description/本文の `手順2.3`→`3.3` | A |
| `.claude/skills/design-interview/SKILL.md` | MOD | 曖昧性タクソノミー(step挿入)、EARS記法(受け入れ条件step)、pipeline連携step、番号再付番 | A |
| `.claude/agents/planner.md` | MOD | 計画フォーマットにトレーサビリティ行、出力例に表、制約に事前確認 | A |
| `.claude/commands/ml-pipeline.md` | MOD | `### 3.3. 設計書・計画の品質ゲート(必須)` を 3 と 3.5 の間に挿入 | A |
| `templates/design-doc.md.template` | NEW | 設計書構造テンプレ。受け入れ条件は6列(…/種別/対象) | B |
| `README.md` | MOD | スキル表に spec-checklist 行+design-interview 行更新、SDD 新節、冒頭mermaidに3.3ゲート | B |
| `CHANGELOG.md` | MOD | [Unreleased] Added(2026-07-23) に1項目追加 | B |
| `claude-init.sh/.ps1`, `claude-update.sh/.ps1` | MOD | `templates/*.template` を取得先の `templates/` へコピーする処理を追加(各1〜3行、既存書式踏襲) | B |

## 実装手順

| # | 内容 | 対象ファイル | 依存 | 並列群 |
|---|------|-------------|------|-------|
| 1 | spec-checklist SKILL 新規作成(設計書の全文をコピー、`手順2.3`→`3.3` を description・本文L159/L206の3箇所すべてで置換) | `.claude/skills/spec-checklist/SKILL.md` | なし | A |
| 2 | design-interview 強化(下記3挿入+再付番) | `.claude/skills/design-interview/SKILL.md` | なし | A |
| 3 | planner 強化(トレーサビリティ表 必須化+事前確認) | `.claude/agents/planner.md` | なし | A |
| 4 | ml-pipeline に `### 3.3` 必須ゲート挿入 | `.claude/commands/ml-pipeline.md` | なし | A |
| 5 | design-doc テンプレ新規作成(受け入れ条件6列=…/種別/対象) | `templates/design-doc.md.template` | なし | B |
| 6 | README 追記(スキル表2行・SDD新節・冒頭mermaid) | `README.md` | Step 1,4 の文言確定後 | B |
| 7 | CHANGELOG に1項目追記 | `CHANGELOG.md` | なし | B |
| 8 | init/update に `templates/*.template` の配布処理を追加(.sh は cp、.ps1 は Copy-Item。既存のテンプレコピー行の直後に挿入) | claude-init.sh/.ps1, claude-update.sh/.ps1 | なし | B |
| 9 | 検証コマンド群+`bash ./verify-hooks.sh` を全実行 | (検証) | 1-8 | - |

### Step 1 詳細(spec-checklist SKILL 新規)
- 設計書セクション2の Markdown をそのまま新規ファイルに書き出す。ただし
  `手順2.3` の表記は description 内(「/ml-pipeline の手順2.3(Planner後)で必ず自動実行」)、
  本文「必ず自動実行される(手順2.3)」、末尾「後続処理は /ml-pipeline の手順2.3 が制御する」
  の**計3箇所すべてを `3.3` に修正**する。
- 検証: `test -f .claude/skills/spec-checklist/SKILL.md && grep -c "3\.3" .claude/skills/spec-checklist/SKILL.md`(1以上)、`! grep -q "2\.3" .claude/skills/spec-checklist/SKILL.md`
- コミット: `feat(step 1): spec-checklist スキルを追加(設計書品質の5次元検査・3.3ゲート)`

### Step 2 詳細(design-interview 強化)— 番号再付番に注意
挿入後の「## 進め方」最終番号を以下に固定する(Generator はこの番号列に一致させる):
```
1 CONTEXT.md / 2 対象設計書読込 / 3 決定木を1枝ずつ辿る
4 [挿入=変更1] 曖昧性タクソノミー(境界値/例外系/状態・順序/データ/非機能/スコープ境界
  ＋研究系: 仮説/変数/ベースライン/成功基準/再現性)
5 質問は1問ずつ(旧4) / 6 推奨案を添える(旧5) / 7 コードで分かる質問は先に調査(旧6)
8 回答を待つ(旧7)
9 受け入れ条件テーブル生成(旧8)＝ここに [挿入=変更2] EARS記法の説明+5型テーブルを
  6列(列/意味)定義テーブルの直後・「曖昧で検証コマンド化できない決定は…」の直前に入れる
10 [挿入=変更3] /ml-pipeline の spec-checklist ゲート(手順3.3)から NEEDS_WORK で呼ばれた場合の
  差分インタビュー挙動(設計書文中の「手順2.3」は 3.3 に読み替え済みで記載)。
  **設計書の有無で分岐を追記する(Codexレビュー指摘の採用)**: 設計書がある場合は設計書を
  更新して制御を返す(設計書原文どおり)。設計書が無い場合は解消した回答を ml-pipeline に返し、
  planner の計画修正に使わせる(ml-pipeline 3.3 側の「設計書が無い場合は解消した内容を planner に
  渡して計画を修正させる」と対応させる)
```
- **注意(自己批判由来)**: 「## 知識の自動スタック(手順8の直後に必ず実施する)」の見出しは
  受け入れ条件生成ステップを指す。再付番でそれが 9 になるため、見出しを **「手順9の直後」** に更新する
  (更新漏れが最も起きやすい箇所)。「## 完了時」の 9 は 11 に付番し直す。
- 変更1・変更2・変更3の本文 Markdown は設計書セクション1の該当ブロックをそのまま使う。
- 検証: `grep -q "EARS" .claude/skills/design-interview/SKILL.md && grep -q "境界値" .claude/skills/design-interview/SKILL.md`、番号の連番性を目視。
- コミット: `feat(step 2): design-interview に曖昧性タクソノミーとEARS記法を追加`

### Step 3 詳細(planner 強化)
- 「## 計画フォーマット」テーブル(L53-62)の最終行(リスク行)の後にトレーサビリティ行を追加(設計書 変更1)。
- 「## 計画の実装手順の出力例」(L74-83)の末尾にトレーサビリティ表の例を追記(設計書 変更2)。
- 「## 制約」(L64-72)の末尾に設計書品質の事前確認ルールを追記(設計書 変更3)。
- 検証: `grep -q "トレーサビリティ" .claude/agents/planner.md`
- コミット: `feat(step 3): planner にトレーサビリティ表の必須化と設計書品質の事前確認を追加`

### Step 4 詳細(ml-pipeline に 3.3 ゲート)
- 「### 3. 計画の作成」ブロック(L50-52)の直後、「### 3.5. 計画の承認判定」(L54)の直前に、
  設計書セクション3.5 の本文を `### 3.3. 設計書・計画の品質ゲート(必須)` として挿入する。
- 本文中の参照を読み替え: 「手順2.5(計画の承認判定)へ進む」→ **3.5**、
  「再度 手順2.3 の spec-checklist を実行」→ **3.3**、見出しの `2.3`→`3.3`。
- feedback.md 追記フォーマット(`## YYYY-MM-DD [spec-checklist: NEEDS_WORK]`)はそのまま含める。
- **目視整合確認(受け入れ条件)**: 挿入後、3.3→3.5 への遷移(READY 時)、NEEDS_WORK ループ(最大2周)、
  design-interview 必須実行、feedback.md 追記の各参照が矛盾なく繋がること。
- 検証: `grep -q "3\.3" .claude/commands/ml-pipeline.md && grep -q "spec-checklist" .claude/commands/ml-pipeline.md`
- コミット: `feat(step 4): ml-pipeline に spec-checklist 必須ゲート(手順3.3)を追加`

### Step 5 詳細(design-doc テンプレ)
- 設計書セクション4の Markdown を新規作成。ただし **§7 受け入れ条件テーブルの列を
  `| ID | 要件 | 検証方法 | 期待結果 | 種別 | 対象 |`** とし、例行を `| R-001 | | | | auto/manual | |` にする
  (設計書の `状態/未検証` は既存 design-interview の列定義に合わせて `対象` へ差し替え)。
- 検証: `test -f templates/design-doc.md.template && grep -q "| ID | 要件 | 検証方法 | 期待結果 | 種別 | 対象 |" templates/design-doc.md.template`
- コミット: `feat(step 5): design-doc テンプレートを追加(EARS/研究/受け入れ条件6列)`

### Step 6 詳細(README)
- スキル表(L606-631、4列)に spec-checklist 行を **design-interview 行の直後**へ4列で追加:
  `| spec-checklist | 設計書の品質(完全性・明確性・一貫性・測定可能性・カバレッジ)を実装前に検査 | 「設計書をチェックして」「spec-checklistして」 | READY / NEEDS_WORK のレポート |`
- design-interview 行(L609)を4列で更新(いつ使うか列に「曖昧性タクソノミーで聞き尽くし、要件を EARS 記法で記述」、
  出力列に「+ 受け入れ条件テーブル」を追記。呼び出し方列は既存を保持)。
- 「### 2.4 典型的な流れ」の直後(「### 実例」L559 の前)に新節 `### 設計書ワークフロー(仕様駆動)` を挿入
  (設計書セクション6の本文。内部のASCIIフロー図はコードフェンスで保持)。
- 冒頭ワークフロー mermaid(L7-30)を最小修正: `B --> C` を
  `B --> SC{spec-checklist<br>品質ゲート 手順3.3}` / `SC -->|READY| C` /
  `SC -->|NEEDS_WORK 最大2周| DI[design-interview<br>指摘箇所を解消]` / `DI --> B` に置換
  (NEEDS_WORK は design-interview 経由で Planner に戻る — 本文の必須実行と一致させる。Codexレビュー指摘の採用)。
- 検証: `grep -q "spec-checklist" README.md && grep -q "設計書ワークフロー(仕様駆動)" README.md`
- コミット: `feat(step 6): README に spec-checklist/EARS/設計書ワークフローを追記`

### Step 7 詳細(CHANGELOG)
- `### Added(2026-07-23)` ブロック末尾(multi-seed 項目 L43-44 の後、`### Changed(2026-07-22)` L46 の前)に1項目追加:
  設計書リッチ化(曖昧性タクソノミー/EARS/spec-checklist必須ゲート/トレーサビリティ表/design-docテンプレ)。
- 日付見出しは種別ごと(Added内・Changed内)に 2026-07-22 → 2026-07-23 の昇順、という既存慣習に既に適合している。
- コミット: `feat(step 7): CHANGELOG に設計書リッチ化を記録`

### Step 8 詳細(init/update に templates 配布を追加)— Codexレビュー指摘の採用
- claude-init.sh / claude-update.sh: 既存の settings.local.json.template コピー処理の近傍に、
  `mkdir -p templates && cp "$TMP"/templates/*.template templates/` 相当を追加
  (取得先プロジェクトに `templates/` を作り参照用テンプレを丸ごと届ける)。
  update 側は既存ファイルの上書き方針を既存テンプレ処理(settings は上書きしない等)と矛盾させない:
  参照専用テンプレは常に最新で上書きしてよい。
- claude-init.ps1 / claude-update.ps1: 同じ位置に `New-Item -ItemType Directory -Force templates` +
  `Copy-Item (Join-Path $Tmp "templates\*.template") "templates\"` を既存 Copy-Item 行の書式踏襲で追加。
- 検証: `bash -n claude-init.sh claude-update.sh`(構文チェック)。.ps1 は本機で構文検証不能(既知の受容済みリスク、
  変更は既存行の書式踏襲の最小追加に留める)。
- コミット: `feat(step 8): init/update に templates/*.template の配布を追加`

## 並列化判定
**逐次のみ(推奨)。**
- ファイル集合は A(.claude/ の skills×2・planner・ml-pipeline)と B(templates+README+CHANGELOG)に
  完全分離可能で、コンパイル依存もない(全て Markdown)。技術的には A/B 並列は成立する。
- しかし「手順3.3」の表記と spec-checklist の説明文言が **A(ml-pipeline・spec-checklist SKILL)と
  B(README 新節)に跨って一致必須**。並列だと2人の書き手で文言ドリフト(例: 「手順3.3」vs「手順3.3(Planner後)」)の
  整合リスクが生じる。Step 6(README)は Step 1・4 の確定文言に論理依存する。
- ドキュメント編集は書き込みが速く並列の実時間短縮は小さい一方、整合検証コストは非ゼロ。
  planner 規律「迷ったら逐次のみ」に従い、単一の書き手が Step 1→4→6 の順で文言を確定させて逐次実装する。
  (群 A/B は表記の追跡用に付与。真の独立ではないため並列実行はしない。)

## 検証方法(セクション7を上記修正で反映。全PASSで完了)
```bash
cd /home/toyod/claude-ml-template
set -e                                                # fail-fast(途中の失敗を握り潰さない)
test -f .claude/skills/spec-checklist/SKILL.md && echo "OK: spec-checklist"
test -f templates/design-doc.md.template && echo "OK: design-doc template"
grep -l "EARS" .claude/skills/design-interview/SKILL.md
grep -l "境界値" .claude/skills/design-interview/SKILL.md
grep -l "トレーサビリティ" .claude/agents/planner.md
grep -l "3\.3" .claude/commands/ml-pipeline.md      # 設計書の "2\.3" を 3\.3 に修正
grep -l "spec-checklist" .claude/commands/ml-pipeline.md
# 読み替え漏れが変更対象のどこにも無いこと(spec-checklist 1ファイルに限定しない)
! grep -rn "手順2\.3\|手順2\.5" \
    .claude/skills/spec-checklist/ .claude/skills/design-interview/ \
    .claude/agents/planner.md .claude/commands/ml-pipeline.md \
    templates/design-doc.md.template README.md
grep -q "| ID | 要件 | 検証方法 | 期待結果 | 種別 | 対象 |" templates/design-doc.md.template && echo "OK: 6列(対象)"
bash -n claude-init.sh claude-update.sh               # Step 8 の構文チェック
bash ./verify-hooks.sh                                # 実行ビット無しのため bash 経由
```
期待: 各 echo が OK を出力、grep -l が該当ファイルパスを表示、`! grep` が真(exit 0)、
`bash ./verify-hooks.sh` が全 PASS。
加えて **目視**: ml-pipeline.md の 3.3→3.5 遷移・NEEDS_WORK ループ(最大2周)・design-interview 必須実行・
feedback.md 追記の参照整合、および design-interview の番号連番性(手順4=タクソノミー挿入、手順9=受け入れ条件+EARS、
手順10=ゲート連携、「手順9の直後」見出し)を確認。

## コミット分割方針
`feat(step N)` 形式で Step 1〜8 を各1コミット(Step 9 は検証のみでコミットなし)。
本ブランチ `pipeline/20260723-planner-rich` 上で継続(main へはコミットしない)。push はユーザー明示指示まで行わない。
設計書 planner-rich-spec.md の削除(git rm + push)は docs/ が gitignore 済みで対象外・かつ push 不可のため**実行しない**。

## リスク
- **番号再付番の漏れ**(design-interview): 「## 知識の自動スタック(手順8の直後…)」見出しの `8→9` 更新漏れが
  最も起きやすい。Step 2 の注意書きで明示済み。検証は目視で連番性を確認。
- **A/B 横断の文言ドリフト**: 「手順3.3」表記の不一致。→ 逐次実装+`grep -q "手順2\.3"` が偽であることの確認で防止。
- **受け入れ条件テーブルの列取り違え**: 設計書は `状態` だが正は `対象`。Step 5 で明示置換。取り違えると
  design-interview/planner/README(いずれも「…/種別/対象」)と不整合になる。
- **検討した代替案1(A/B 並列実装)**: 実時間短縮が小さくドリフト整合コストが上回るため不採用。
- **検討した代替案2(design-doc テンプレを参照専用扱いにして init/update を変更しない)**: 当初案だったが、
  README が案内するパスが downstream で参照不能になる実害(Codexレビュー指摘)と設計書セクション5の明示指示を
  優先して撤回。`templates/*.template` の配布を Step 8 で追加する(.ps1 は構文検証不能な点を受容リスクとして記録)。
- **未確認の仮定**: verify-hooks.sh が spec-checklist スキルの存在や新規テンプレの内容を検査対象にしていない
  (=Markdown 追加で PASS を壊さない)こと。Step 9 の実行で裏取りする。

## 作業ログ(実装完了 2026-07-23)

Step 1〜9 を計画どおり逐次実装し、全コミットをブランチ
`pipeline/20260723-planner-rich` 上に作成した(push なし、main 未変更)。

コミット一覧:
- `c0c52f1` feat(step 1): spec-checklist スキルを追加(設計書品質の5次元検査・3.3ゲート)
- `dc6f90a` feat(step 2): design-interview に曖昧性タクソノミーとEARS記法を追加
- `11dc271` feat(step 3): planner にトレーサビリティ表の必須化と設計書品質の事前確認を追加
- `a80f906` feat(step 4): ml-pipeline に spec-checklist 必須ゲート(手順3.3)を追加
- `f74c0d8` feat(step 5): design-doc テンプレートを追加(EARS/研究/受け入れ条件6列)
- `3855adf` feat(step 6): README に spec-checklist/EARS/設計書ワークフローを追記
- `171dda1` feat(step 7): CHANGELOG に設計書リッチ化を記録
- `8df3ced` feat(step 8): init/update に templates/*.template の配布を追加

変更ファイル一覧:
- `.claude/skills/spec-checklist/SKILL.md`(新規)
- `.claude/skills/design-interview/SKILL.md`
- `.claude/agents/planner.md`
- `.claude/commands/ml-pipeline.md`
- `templates/design-doc.md.template`(新規)
- `README.md`
- `CHANGELOG.md`
- `claude-init.sh` / `claude-update.sh` / `claude-init.ps1` / `claude-update.ps1`

Step 9 検証: 検証方法ブロック(`set -e` 付き)を全実行し、
`OK: spec-checklist` / `OK: design-doc template` / `OK: 6列(対象)` の各 echo、
5件の `grep -l` の該当ファイルパス表示、`! grep -rn "手順2\.3\|手順2\.5" ...` の
真(exit 0、読み替え漏れ無し)、`bash -n claude-init.sh claude-update.sh` の構文OK、
`bash ./verify-hooks.sh` の「全テストPASS」を確認した(生出力で確認済み)。

目視確認:
- design-interview: 手順1〜11の連番が欠番・重複なく振られ、手順4=曖昧性タクソノミー、
  手順9=受け入れ条件テーブル生成(6列+EARS記法埋め込み)、手順10=spec-checklistゲート
  連携(設計書有無の分岐込み)、見出しが「手順9の直後」「## 完了時」11、に一致することを確認。
- ml-pipeline: 3.3(品質ゲート)→READYで3.5→NEEDS_WORKでdesign-interview必須実行
  →設計書の有無で分岐(設計書更新 or planner差し戻し)→再度3.3、最大2周、
  feedback.md追記(コードフェンス書式で既存の却下時追記と統一)の各参照が矛盾なく
  繋がることを確認。

計画からの逸脱(いずれも実装上の必要による軽微な補正、設計・内容自体は計画どおり):
- README冒頭mermaidで、計画の記述例 `SC -->|READY| C`(ラベル無し)のままだと
  ノードCのラベル定義(元は `B --> C{...}` の1箇所のみ)が失われ図が壊れるため、
  ラベルを `SC -->|READY| C{計画の承認<br>...}` に付け替えて保持した
  (矢印の追加・分岐構造自体は計画どおり)。
- ml-pipeline 3.3節の見出し直下は元々「### 3. 計画の作成」「### 3.5」がすでに
  3.x 番号だったため(現状分析の確認済み事実どおり)、2.3→3.3の文字列置換自体は
  この挿入ブロック内でのみ発生し、既存本文側の読み替えは不要だった。
