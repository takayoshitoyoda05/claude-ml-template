# 敵対的レビューを Claude Security プラグイン統合に置き換える

**参照設計書**: `/home/toyod/claude-ml-template/docs/drafts/adversarial-final-gate-spec_final.md`
(docs/ は .gitignore 済み・git 管理外。この spec は標準の「## 受け入れ条件」6列テーブルを持つ
設計書ではなく、テンプレート自体のリファクタ指示書。親エージェントが受け入れ条件を
明示提示しているため差し戻さず計画化する。spec の削除はユーザー承認後に通常の `rm` で行う
= `git rm` は不能)。

## 目的
自作の敵対的レビュー(adversarial-reviewer + CLAUDE_ADVERSARIAL + リーダー1人の検証パス)を
Anthropic 公式の Claude Security プラグイン統合(CLAUDE_SECURITY_SCAN)に置き換える。
final-gate(第3層)は既存のまま、「読むもの」に CLAUDE-SECURITY-RESULTS.md を1行追記するだけ。

## 現状分析
- 確認済み: 実ファイルの手順番号は設計書の想定(5.6/5.9)とズレている。実番号は
  **6.6(敵対的レビュー)/ 6.7(リファクタリング・パス)/ 6.8(Fable 最終ゲート)**。
  置換対象は 6.6、final-gate 言及更新は 6.8。飛び先も現番号に合わせる。
- 確認済み: `CLAUDE_ADVERSARIAL` の出現箇所を grep で網羅した。
  - **置換対象(実運用ファイル)**:
    - README.md: L18(mermaid AD ノード), L203(環境変数表), L381(ワークフロー手順9),
      L580(エージェント表), L881(3.16 3層レビュー節), L963(スモークテスト手順)
    - .claude/commands/ml-pipeline.md: L176(手順6.6 本文)
    - .claude/skills/config-explain/SKILL.md: L26
    - .claude/skills/config-set/SKILL.md: L33(JSON雛形), L56(説明表)
    - templates/settings.local.json.template: L15
    - .claude/agents/adversarial-reviewer.md: L3(ファイルごと削除)
  - **履歴的記録(書き換え禁止)**:
    - CHANGELOG.md: L42(Added(2026-07-23) の過去エントリ。過去記録として保持)
    - .claude/checkpoints/*.jsonl(会話トランスクリプト。触らない)
    - .claude/plans/*(過去計画。本計画自身も CLAUDE_ADVERSARIAL を含むため grep 対象から除外)
- 確認済み: config-set / config-explain は両方 CLAUDE_ADVERSARIAL に言及あり
  → 同期更新が必要(過去に config-set の同期漏れが問題化した経緯を踏まえる)。
- 確認済み: .claude/hooks/ 配下に CLAUDE_ADVERSARIAL 参照は無い(フック変更不要)。
- 確認済み: .claude/settings.json に CLAUDE_ADVERSARIAL は無い(内容変更不要。検証で JSON 妥当性のみ確認)。
- 確認済み: README のワークフロー mermaid 図に AD(敵対的レビュー)ノードがある(L18,21,23)。
  設計書は図に未言及だが、6.6 置換に伴い図も更新しないと齟齬が出るため最小変更する。
- 確認済み: final-gate.md L9 の散文「3段階のレビュー(Spec / Standards / 敵対的)」は
  エージェント自身の前提説明であり、敵対的レビュー廃止後は誤りになる
  → Step 3 で「敵対的」を「セキュリティスキャン」に同期更新する(Codexレビュー指摘の採用)。
- 確認済み(Codexレビュー指摘の採用): README L1032 のファイル一覧ツリーに
  adversarial-reviewer.md の行がある → Step 7 で削除する。
- 確認済み(Web検証 2026-07-23): security-guidance / claude-security 両プラグインは
  実在する(anthropics/claude-plugins-official)。claude-security はベータで
  `/claude-security` コマンドに「Scan changes」モードあり。設計書の記述と整合。
- 確認済み: docs/adr/ が存在し(0001-multi-seed-design.md)、リポジトリは ADR 運用実績あり。
  本件は「自作 → 公式プラグイン」という後戻りしづらいトレードオフ決定のため ADR を1本追加する。

## 変更対象
| ファイル | 変更内容 |
|---------|---------|
| .claude/agents/adversarial-reviewer.md | ファイル削除(役割を公式プラグインに委譲) |
| .claude/commands/ml-pipeline.md | 6.6 を「セキュリティスキャン」へ全体置換(飛び先を現番号6.7/手順5へ補正)、6.8 の渡すもの文言更新 |
| .claude/agents/final-gate.md | 「読むもの」項目3に CLAUDE-SECURITY-RESULTS.md を追記 |
| .claude/skills/security-review/SKILL.md | 見出し直後に「用途aは公式プラグイン優先」の注記を追加 |
| templates/settings.local.json.template | CLAUDE_ADVERSARIAL 行を CLAUDE_SECURITY_SCAN に置換 |
| .claude/skills/config-set/SKILL.md | JSON雛形 L33 と説明表 L56 を CLAUDE_SECURITY_SCAN に同期 |
| .claude/skills/config-explain/SKILL.md | 確認項目表 L26 を CLAUDE_SECURITY_SCAN に同期 |
| README.md | L18/21/23(図)・L203(表)・L381(手順9)・L580(エージェント表)・L881(3.16節)・L963(スモーク)を更新+セットアップ末尾に「セキュリティプラグインの導入(推奨)」節を追加 |
| CHANGELOG.md | [Unreleased] に Changed(2026-07-23)を新規追加(過去エントリは触らない) |
| docs/adr/0002-security-plugin-replacement.md | ADR を新規作成(トレードオフ決定の記録。docs/ は git 管理外) |

## 実装手順
| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 0 | 受け入れ検証の空振り確認: 置換前に「検証方法」の grep/verify-hooks を実行し、現状の CLAUDE_ADVERSARIAL 出現(置換対象のみ)を基準として記録 | (検証コマンドのみ) | なし | A |
| 1 | adversarial-reviewer.md を削除 | .claude/agents/adversarial-reviewer.md | なし | A |
| 2 | 6.6 見出し・本文を「### 6.6. セキュリティスキャン(条件分岐)」に全体置換(設計書セクション2の文面を採用)。スキップ先を「手順6.7へ」、(c)の差し戻し先を「手順5に戻る」、0件時を「手順6.7へ進む」に補正。さらに 6.8 の「各レビュー(evaluator / evaluator-standards / 敵対的レビュー)の結果要約」を「…/ セキュリティスキャン)の結果要約」に更新 | .claude/commands/ml-pipeline.md | なし | A |
| 3 | 「読むもの」項目3を設計書セクション3の文面に置換(CLAUDE-SECURITY-RESULTS.md を追加)。あわせて冒頭散文の「(Spec / Standards / 敵対的)」を「(Spec / Standards / セキュリティスキャン)」に同期。frontmatter・観点・出力形式は不変 | .claude/agents/final-gate.md | なし | A |
| 4 | 「# セキュリティレビュー」見出し直後に設計書セクション4の注記ブロックを挿入(用途aは公式プラグイン優先、用途bは本スキル継続) | .claude/skills/security-review/SKILL.md | なし | A |
| 5 | env ブロックの "CLAUDE_ADVERSARIAL": "0" を "CLAUDE_SECURITY_SCAN": "0" に置換(CLAUDE_FINAL_GATE は残す) | templates/settings.local.json.template | なし | A |
| 6 | config-set の JSON雛形 L33 と説明表 L56、config-explain の確認表 L26 を CLAUDE_SECURITY_SCAN に同期(説明文は「`1` でclaude-securityプラグインによる差分スキャンを2軸レビュー後に実行(既定 `0`)」) | .claude/skills/config-set/SKILL.md, .claude/skills/config-explain/SKILL.md | なし | A |
| 7 | README を更新: 図L18ノード名→「セキュリティスキャン<br>※CLAUDE_SECURITY_SCAN=1時のみ」、L21 "ADVERSARIAL無効時"→"SECURITY_SCAN無効時"、L23 エッジ"実在する問題あり"→"verifiedな指摘あり"; L203環境変数表を設計書の CLAUDE_SECURITY_SCAN 行に置換; L381手順9を差分スキャン版に書換; L580 adversarial-reviewer 行を削除; L881〜の3.16節を設計書セクション6の「3層レビュー」文面に全体置換(見出しは "### 3.16 3層レビュー(セキュリティスキャンと最終ゲート)" として節番号を維持); L963 の CLAUDE_ADVERSARIAL→CLAUDE_SECURITY_SCAN; L1032 のファイル一覧ツリーから adversarial-reviewer.md の行を削除; セットアップ節末尾(L338 の直後、L339 "---" の前)に設計書セクション6の「セキュリティプラグインの導入(推奨)」節を追加(導入コマンドに「Marketplace未登録なら `/plugin marketplace add anthropics/claude-plugins-official`」の注記を1行添える) | README.md | なし | B |
| 8 | [Unreleased] に "### Changed(2026-07-23)" を新設し1項目追加(敵対的レビュー/CLAUDE_ADVERSARIAL を Claude Security プラグイン統合/CLAUDE_SECURITY_SCAN に置き換え、security-review スキルはフォールバックに降格)。過去の Added(2026-07-23) エントリは変更しない | CHANGELOG.md | なし | B |
| 9 | ADR を新規作成(決定・背景・代替案・影響を各数行)。docs/adr/ 既存の書式に合わせる。docs/ は git 管理外のためコミットは作らない(0001 と同じ扱い) | docs/adr/0002-security-plugin-replacement.md | Step 1-8 | B |
| 10 | 全検証を実行(下記「検証方法」)。全 PASS を確認 | (検証コマンドのみ) | Step 1-9 | - |

注意(Step 2): 設計書の (c) は「手順4へ」「手順5.7へ」と書くが、これは spec 想定の旧番号。
現行ファイルでは generator 差し戻し=「手順5に戻る」、スキップ先=「手順6.7へ」。必ず現番号へ補正すること。
飛び先の取り違えはパイプラインの分岐を壊すため、置換後に 6.6 本文の「手順」参照を目視確認する。

注意(Step 7): README は本ブランチ(main 基点)で編集。multi-seed 等の他セクションには触れない。
CLAUDE_ADVERSARIAL を含む6箇所と新規2節「以外」は編集しない(将来のマージ衝突を最小化)。
環境変数表・config-set/config-explain・設計書の文言表現(「2軸レビュー後に実行」等)を一致させる。

## 並列化判定
**逐次のみ**。
- グループ分割案の検討: A=.claude/ 配下(agents/commands/skills/templates)、B=README+CHANGELOG+ADR。
  対象ファイル集合は完全に分離しており、依存関係も無いため理論上は並列化可能。
- 不採用理由: (1) 全変更が「CLAUDE_ADVERSARIAL→CLAUDE_SECURITY_SCAN」の一貫置換で、
  環境変数の説明文言が README(表)/config-set(表)/config-explain(表)/settings テンプレートで
  相互に一致する必要があり、A/B を別々に実装すると文言ドリフト(整合リスク)が生じる。
  (2) 各変更は Markdown/JSON の数行編集で1ファイル当たり数分、総量が小さく、
  worktree 分離+統合マージのオーバーヘッドが並列の時間短縮を上回る。
- 迷ったら逐次(保守的判定)の原則に従い逐次実行とする。所要差は数分未満で、整合リスク回避の価値が勝る。

## 検証方法
設計書セクション7の検証群を、履歴ファイルの偽陽性を除くよう修正して実行する。
すべて PASS すれば受け入れ完了。

```bash
cd /home/toyod/claude-ml-template

# (1) adversarial-reviewer が削除されている
test ! -f .claude/agents/adversarial-reviewer.md && echo "OK: deleted"

# (2) ml-pipeline.md に置換後の文言がある
grep -l "CLAUDE_SECURITY_SCAN" .claude/commands/ml-pipeline.md

# (3) 旧環境変数・旧エージェント参照が実運用ファイルに残っていない
#     ※ .claude/checkpoints/(トランスクリプト)/ .claude/plans/(過去+本計画)/ CHANGELOG.md(過去エントリ)
#       は履歴的記録のため grep 対象から除外している(設計書の元コマンドの偽陽性を修正)
! grep -rn "CLAUDE_ADVERSARIAL\|adversarial-reviewer" \
    .claude/agents/ .claude/commands/ .claude/skills/ .claude/hooks/ \
    templates/ README.md \
  && echo "OK: no leftover in operational files"

# (4) 置換後の環境変数が README / config 系 / テンプレートの全4ファイルに揃っている
#     (grep -rl は1ファイルでも exit 0 になるため、ファイルごとに個別判定する)
for f in README.md templates/settings.local.json.template \
         .claude/skills/config-set/SKILL.md .claude/skills/config-explain/SKILL.md; do
  grep -q "CLAUDE_SECURITY_SCAN" "$f" && echo "OK: $f" || { echo "MISSING: $f"; exit 1; }
done

# (5) settings.json が妥当な JSON
python -c "import json; json.load(open('.claude/settings.json'))"

# (6) テンプレートも妥当な JSON
python -c "import json; json.load(open('templates/settings.local.json.template'))"

# (7) フックテスト全 PASS(verify-hooks.sh は実行ビット無し(644)のため bash 経由で呼ぶ)
bash ./verify-hooks.sh
```

期待結果:
- (1) `OK: deleted`
- (2) パス出力(`.claude/commands/ml-pipeline.md`)
- (3) grep がヒット0(exit 1)で `OK: no leftover in operational files` が出る
- (4) 4ファイル全てに `OK:` が出て exit 0(1つでも欠ければ `MISSING:` で exit 1)
- (5)(6) 例外なく終了(exit 0)
- (7) verify-hooks.sh が全項目 PASS

## リスク
- **手順番号の飛び先ミス**(Step 2): 設計書の「手順4/5.7」を鵜呑みにすると分岐が壊れる。
  現番号(手順5/6.7)へ補正する。置換後に 6.6 内の「手順」参照を目視確認して回避。
- **文言ドリフト**(逐次採用の根拠): README 環境変数表・config-set/config-explain・
  settings テンプレートで CLAUDE_SECURITY_SCAN の説明が食い違うと利用者が混乱する。
  逐次で1つの文言を横展開して防ぐ。
- **grep 偽陽性**(検証コマンド): 設計書の元コマンドは .claude/checkpoints/ のトランスクリプトや
  過去計画・本計画を拾って偽陽性になる。検証(3)を実運用ディレクトリに絞って回避済み。
- **README マージ衝突**: multi-seed の未マージ変更が別ブランチにある。CLAUDE_ADVERSARIAL の6箇所と
  新規2節以外に触れないことで衝突面を最小化。
- **一部未確認の仮定**: プラグインの実在・導入コマンド・「Scan changes」モードは Web で確認済み
  (2026-07-23)。ただし内部詳細(6フェーズ名・Panel quorum 2/3・CLAUDE-SECURITY-RESULTS.md の
  verification.status 形式)は設計書の記述をそのまま採用。未導入環境では 6.6(a) が graceful skip
  するため実行不能にはならないが、初回実走時に結果ファイル名・形式の実態確認を推奨(README に注記不要、運用で確認)。
- **検討した代替案(不採用)**:
  - 案X: A/B 並列(worktree 分離)。→ 上記「文言ドリフト」と小規模ゆえのオーバーヘッド超過で不採用。
  - 案Y: 全変更を1コミットに集約(設計書の元方針)。→ リポジトリ慣例の feat/refactor(step N) 粒度と
    レビュー容易性を優先し、ファイル単位のステップ別コミットに分割して不採用。

## コミット分割方針(feat/refactor(step N) 形式)
リポジトリ慣例に合わせ、ステップ単位で分割する。文書リファクタは refactor、記録系は docs。

| Step | コミットメッセージ案 |
|------|---------------------|
| 1 | `refactor(step 1): adversarial-reviewer を削除し役割を公式プラグインへ委譲` |
| 2 | `refactor(step 2): ml-pipeline 6.6 をセキュリティスキャンへ置換し 6.8 の渡すもの文言を更新` |
| 3 | `refactor(step 3): final-gate の読むものに CLAUDE-SECURITY-RESULTS.md を追加` |
| 4 | `refactor(step 4): security-review スキルに公式プラグイン優先の注記を追加` |
| 5 | `refactor(step 5): settings テンプレートを CLAUDE_SECURITY_SCAN に置換` |
| 6 | `refactor(step 6): config-set/config-explain を CLAUDE_SECURITY_SCAN に同期` |
| 7 | `refactor(step 7): README の敵対的レビュー記述をセキュリティスキャン版に置換し導入手順を追加` |
| 8 | `docs(step 8): CHANGELOG に Claude Security 置換を Changed として記録` |
| 9 | (コミットなし — docs/ は git 管理外のため ADR はローカル成果物として作成のみ) |

- Step 6 は2ファイルだが同期という単一意図なので1コミットにまとめる。
- 各コミット前に「検証方法」の該当項目を回し、最終 Step 10 で全項目を通す。
- git push とマージはユーザーの明示指示があるまで行わない(設計書の「push まで」記述には従わない)。
- 設計書ファイルの削除(通常の `rm docs/drafts/adversarial-final-gate-spec_final.md`)は
  全実装・検証完了後、ユーザーの承認を得てから行う(git 管理外のため `git rm` は不能)。

## 知識スタックの確認結果
- (a) 用語 → CONTEXT.md: リポジトリ直下に CONTEXT.md は存在しない。新規作成は本タスクのスコープ外
  かつ肥大化回避のため見送る(追記対象ゼロ)。
- (b) トレードオフ決定 → ADR: 「自作の敵対的レビュー → 公式 Claude Security プラグイン」は
  後戻りしづらい選択。Step 9 で docs/adr/0002-security-plugin-replacement.md を作成して記録する。
- (c) 実験の再現条件 → EXPERIMENT_LOG: 数値・シード・データセット等の確定情報は無いため追記なし。

## 作業ログ(実装完了 2026-07-23)

Step 0〜10 を計画通り逐次実行し、全て完了した。

- **Step 0**: 置換前 grep 基準を記録。実運用ディレクトリ
  (`.claude/agents/ commands/ skills/ hooks/ templates/ README.md`)で
  `CLAUDE_ADVERSARIAL|adversarial-reviewer` が15件ヒット(想定通り)。
- **Step 1**: `.claude/agents/adversarial-reviewer.md` を `git rm` で削除。
- **Step 2**: `.claude/commands/ml-pipeline.md` の「### 6.6. 敵対的レビュー(条件分岐)」を
  「### 6.6. セキュリティスキャン(条件分岐)」に全体置換。飛び先は設計書の
  旧番号(手順4/5.7)ではなく現番号に補正: スキップ先「手順6.7へ」、差し戻し先
  「手順5に戻る」、0件時「手順6.7へ進む」。6.8 の「各レビュー(evaluator /
  evaluator-standards / 敵対的レビュー)の結果要約」は
  「…/ セキュリティスキャン)の結果要約」に更新。
- **Step 3**: `.claude/agents/final-gate.md` の「読むもの」項目3に
  CLAUDE-SECURITY-RESULTS.md 参照を追記。冒頭散文「(Spec / Standards / 敵対的)」を
  「(Spec / Standards / セキュリティスキャン)」に同期(Codexレビュー指摘の採用分)。
- **Step 4**: `.claude/skills/security-review/SKILL.md` の見出し直後に
  公式プラグイン優先の注記ブロックを追加。
- **Step 5**: `templates/settings.local.json.template` の
  `CLAUDE_ADVERSARIAL` を `CLAUDE_SECURITY_SCAN` に置換。JSON妥当性を確認。
- **Step 6**: `.claude/skills/config-set/SKILL.md`(JSON雛形+説明表)と
  `.claude/skills/config-explain/SKILL.md`(確認表)を `CLAUDE_SECURITY_SCAN` に同期。
  説明文言は README と完全一致させた。
- **Step 7**: README.md を計画列挙箇所のみ更新
  (図L18/21/23、環境変数表、手順9、エージェント表、3.16節全体、スモーク手順、
  ファイル一覧ツリー、セットアップ末尾の新節)。新節に
  「Marketplace未登録なら `/plugin marketplace add anthropics/claude-plugins-official`」を
  1行添えた。`git diff --stat` で他セクション(multi-seed 等)への影響がないことを確認済み。
- **Step 8**: CHANGELOG.md の [Unreleased] に「### Changed(2026-07-23)」を新設。
  過去の Added(2026-07-23) エントリは無変更のまま維持(diff で確認)。
- **Step 9**: `docs/adr/0002-security-plugin-replacement.md` を新規作成
  (docs/ は .gitignore 対象のためコミットなし。0001 と同じ書式)。
- **Step 10**: 検証(1)〜(7)を全て実行、全 PASS。詳細は完了報告を参照。

### 逸脱点
なし。計画の全ステップ・補正指示(6.6/6.8の飛び先補正、README編集範囲、
文言統一、Step 9のコミットなし)を計画通りに実行した。

### 変更ファイル一覧
- 削除: `.claude/agents/adversarial-reviewer.md`
- 変更: `.claude/commands/ml-pipeline.md`, `.claude/agents/final-gate.md`,
  `.claude/skills/security-review/SKILL.md`,
  `templates/settings.local.json.template`,
  `.claude/skills/config-set/SKILL.md`, `.claude/skills/config-explain/SKILL.md`,
  `README.md`, `CHANGELOG.md`
- 新規(git管理外): `docs/adr/0002-security-plugin-replacement.md`
