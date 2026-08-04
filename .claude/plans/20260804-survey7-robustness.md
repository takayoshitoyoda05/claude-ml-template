# サーベイ優先候補7件の一括実装(計画・レビュー堅牢化 第2弾)

参照要件ソース: `literature/ai-dev-plan-review-robustness/summary.md` §3 優先候補(7行の表)
関連: `docs/drafts/20260804-next-robustness-todo.md`(保留メモ)、`literature/ai-dev-plan-review-robustness/notes/{planning,review,verification,industry}.md`
前提ブランチ: `pipeline/20260804-survey7-robustness`

**受け入れ条件テーブルについて**: 要件ソースに `## 受け入れ条件` テーブルは無い。前回の同種計画(`.claude/plans/20260804-robustness-5proposals.md`)と同じ扱いとし、**summary.md §3 の優先候補表(7行・ID つき)を要件ソースとみなし**、その文献ID(V6 / R3 / P10 / R9 / I5 / V10 / R1)をそのまま要件IDとしてトレーサビリティ表を構成する。

## 目的

現行パイプラインは「計画作成時」と「実装完了後」に検証が集中し、承認後〜実装中・レビュー指摘の品質管理・判定の不確実性・レビュー強度の配分に空白がある。サーベイで抽出した優先候補7件を、既存思想(機械的強制 > 自己申告 / opt-in / fail-closed / 最小diff)に沿った最小の追加で一括して埋める。

## 現状分析

確認済み(すべて実ファイルを読んで裏取り済み):

- **注入ポイント**: `.claude/commands/ml-pipeline.md`(644行)の手順0は62-79行で規模(S/M/L)のみ。手順5は221-295行。手順6は305-333行(feedback.md 注入はあるが接地検証なし)。手順6.5/6.6/6.7/6.8 が既に存在し、**6.1〜6.4 は空き番**。失敗遷移表は515-530行で6種別・HUMAN_REVIEW 相当の出口なし。
- **router.md**(28行)は判定基準がS/M/Lの3行のみ。出力形式は「判定 / 理由」の2行。リスク軸は存在しない。
- **evaluator.md** 69行の指摘形式は「ファイルパスと行番号つき」を要求するが、**行が実在するかは誰も確認しない**。185-190行に「Codex と同箇所なら重大度+1」(合意方向)がある。**判定は PASS / NEEDS_REVISION / FAIL の3値**で、97-101行に goal 三値からの写像表がある。
- **確認済み(重要)**: `docs/adr/0003-control-level-and-failure-transitions.md` の決定#2 が「三値 vs PASS/NEEDS_REVISION/FAIL は写像表で解決し、**既存表記と verdict の語彙は変更しない**」と明記している。R9 で evaluator に4値目を足す案がこの ADR と正面衝突することを確認した。
- **確認済み**: `NEEDS_REVISION` を機械的に解釈するフック・スクリプトは存在しない(`rg --hidden 'NEEDS_REVISION' .claude/hooks/*.py scripts/*.py tests/*.py` → 0件)。参照は README / ml-pipeline / evaluator×2 / cross-review / retrospective の**記述のみ**。
- **確認済み**: `scripts/` はインストーラの配布対象外。`claude-init.sh` 38-44行 / `claude-update.sh` 25-30行は `.claude/{agents,commands,hooks,skills,output-styles,rules}` + `settings.json` + `agents/shared/` + `templates/*.template` + `.github/workflows/` のみを配る。したがって**新規スクリプトを `scripts/` に置いても導入先プロジェクトに届かない**。
- **確認済み**: `.claude/skills/` 配下にスクリプトを置いた前例は無い(`find .claude/skills -type f -not -name SKILL.md` → 0件。27スキル=27ファイル)。
- **確認済み**: `.claude/hooks/` と `settings.json` / `settings.local.json` は `_common.py` 63-81行の `PROTECTED_PATH_PATTERNS` により Claude から Write/Edit 不可(新規ファイルも含めディレクトリ全体)。**本計画はフックを一切変更しないため、staging + ユーザー `cp` 工程は発生しない**。
- **確認済み**: エージェント追加にインストーラ変更は不要(`agents` ディレクトリごとコピー)。**新しい環境変数だけ**が `templates/settings.local.json.template` と `claude-init.sh` 125-133行 / `claude-init.ps1` 117-126行の変更を要する。`enable_feature()` は該当キーを `"1"` に書き換える実装なので、雛形にキーが無いと警告して失敗する。
- **確認済み**: `verify-installers.sh` は配布ペイロードを**リポジトリの HEAD から `file://` でローカル clone** する(6-9行のコメントと 39-46行 `place_installers`)。したがって雛形への新フラグ追加は**コミット後でないと検査に反映されない**。`.ps1` 版はこの環境(pwsh 無し)では実行できない(11行)。
- **確認済み**: テンプレート本体にテンソルを受け渡す公開関数は無い(`grep -rn "Tensor" scripts tests` → 0件)。`scripts/env_fingerprint.py` の torch は版数取得の try-import のみ(80-84行)。よって V6 は**規約の追加**で完結し、テンプレート自身のテストに影響しない。
- **確認済み**: このリポジトリに `pyproject.toml` は無く pytest も未導入。
  `uv run python -m pytest tests/ -q` は `No module named pytest` で失敗し、
  正しい起動形式は `uv run --with pytest python -m pytest tests/ -q`(実測 118 passed)。
  README.md 1192行がこの形式を正としている。計画・報告に書くテストコマンドは
  この形式で統一する。
- **確認済み**: `.claude/settings.json` の `permissions.allow` に `sed` は無い
  (`grep -c "sed" .claude/settings.json` → 0)。既存の定義ファイルにも `sed` の
  使用実績が無いため、手順6.2 の証拠確認は**リーダーの Read ツールを第一手段**とし、
  読み取り専用コマンド(`grep -n`)は行番号ズレ時の補助に限定する。
- **確認済み**: `CLAUDE_REFUTE_PASS` / `refuter` は既存のどこにも存在しない(`grep -rn CLAUDE_REFUTE .claude templates claude-init.sh claude-init.ps1 README.md` → 0件、`ls .claude/agents/refuter.md` → 不在)。
- **確認済み**: `plan-reviewer.md` の条件は8個で「上記8条件は固定」と明記(74行)。条件数を変える変更は README 含む複数箇所に波及する。
- **確認済み**: `docs/` は `.gitignore` 対象(6行目 `docs/`)。要件ソースの TODO メモも本計画の実装成果もコミット対象にならない。
- **整合更新が必要な README 箇所**(行番号は実装で前後する。Generator は grep で再特定する): 12-30行(mermaid)、234-253行(環境変数表)、529-566行(2.1 パイプライン手順の番号付きリスト)、594-716行(2.3 個別エージェント。`@plan-premortem` の項の書式が新設 `@refuter` の手本)、797-814行(3.1 エージェント一覧表)、815-851行(3.2 スキル表)、1194-1225行(3.17 3層レビューの図)、1340行(3.20 失敗遷移表)、1348行(router の説明)、1478-1505行(6章ディレクトリツリー)。
- **CHANGELOG**: `[Unreleased]` に `### Added(2026-08-04)` が既に存在する(103行)。同一日付の見出しを重複させず、そのブロックにバレットを追加する。
- **文献の確認状態**(要件ごとに設計判断へ反映する): 本文確認済み = **R3 / P10 / R1**、abstract のみ = **V6 / R9 / I5 / V10**。abstract のみの4件は文献の数値・手順詳細に依存させず、設計自体で正当化できる保守形にする(具体的な縮退内容は各ステップの補足に記載)。

## 変更対象

| ファイル | 対象 | 変更内容 |
|---|---|---|
| `.claude/agents/router.md` | 判定基準、出力形式 | リスク階層(高/中/低)の判定基準と2行の出力追加(I5) |
| `.claude/commands/ml-pipeline.md` | 手順0 | リスク階層による経路強化(強める方向のみ)(I5) |
| `.claude/commands/ml-pipeline.md` | 手順5 | 計画ステップ対応表の要求とリーダーの照合(P10) |
| `.claude/commands/ml-pipeline.md` | 手順6.2(新設) | レビュー指摘の接地検証(必須・軽量)(R3) |
| `.claude/commands/ml-pipeline.md` | 手順6.3(新設) | 反証濾過パス(opt-in)(R1) |
| `.claude/commands/ml-pipeline.md` | 手順7の既存分岐(502-505行)・失敗遷移表 | 既存 NEEDS_REVISION 分岐の書き換え、HUMAN_REVIEW 出口と遷移表1行(R9) |
| `.claude/agents/refuter.md` | 新規 | 反証専任エージェント(sonnet)(R1) |
| `.claude/agents/evaluator.md` / `evaluator-standards.md` | レポート形式 | HIGH/MEDIUM 指摘への証拠添付を必須化(R3) |
| `.claude/skills/cross-review/SKILL.md` | 手順3 の Codex 指示文(2箇所) | HIGH/MEDIUM 指摘への証拠添付を要求(R3) |
| `.claude/agents/evaluator-standards.md` | 評価基準「型安全性」 | shape 注釈の有無を観点に追加(V6) |
| `.claude/skills/python-standards/SKILL.md` | 型ヒント節の直後 | テンソル shape 注釈の規約節を新設(V6) |
| `.claude/agents/planner.md` | 計画フォーマット表 | 「事後条件」欄の追加(V10) |
| `.claude/skills/tdd/SKILL.md` | 進め方の直後 | 「事後条件は実装より先に固定する」節(V10) |
| `.claude/skills/spec-checklist/SKILL.md` | 測定可能性の行 | 事後条件欄の検査を追加(V10) |
| `.claude/agents/generator.md` | 作業手順、自己チェック | 事後条件のテストファースト(V10)/ shape 自己チェック(V6)/ 計画ステップ対応表(P10) |
| `templates/settings.local.json.template` | env | `CLAUDE_REFUTE_PASS` を追加(R1) |
| `claude-init.sh` / `claude-init.ps1` | OPTIONAL_FEATURES | 新フラグを任意機能の質問に追加(R1) |
| `verify-installers.sh` | init 新規導入ブロック | 雛形フラグの回帰アサーション1件(R1) |
| `README.md` | 上記10箇所 | 実装の実物に合わせた整合更新 |
| `CHANGELOG.md` | `### Added(2026-08-04)` | バレット追加(見出しは新設しない) |

## 事後条件(V10 の書式のドッグフーディング)

本計画はコード変更を含まない定義ファイルの変更だが、導入する書式を自ら守る。

| ID | 対象 | 入力 | 満たすべき条件 |
|---|---|---|---|
| PC-1 | `bash verify-installers.sh` | 引数なし(フラグ追加のコミット後) | 標準出力に `NG:` が0件、新規アサーション `CLAUDE_REFUTE_PASS` が `OK:` で出る |
| PC-2 | `bash verify-hooks.sh` | 引数なし | 全テスト PASS(フック未変更なので既存と同一結果) |
| PC-3 | `uv run --with pytest python -m pytest tests/ -q` | 引数なし | 118件が全 PASS(件数が減っていない) |
| PC-4 | `diff <(grep -oE 'CLAUDE_[A-Z_]+' claude-init.sh \| sort -u) <(grep -oE 'CLAUDE_[A-Z_]+' claude-init.ps1 \| sort -u)` | — | 差分0行 |

期待値はいずれも既存の検証手段の出力形式から導いており、実装後の出力を写したものではない。
行 ID を素の連番にしないのは、手順5 の計画遵守の照合(`grep -cE '^\| [0-9]+ \|'`)が
実装手順の行だけを数えられるようにするため(Step 12 で planner.md に規定する)。

## 実装手順

| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 1 | router にリスク階層(高/中/低)の判定基準と出力2行を追加(I5 対応) | `.claude/agents/router.md` | なし | A |
| 2 | 手順0 にリスク階層による経路強化を追加(I5 対応) | `.claude/commands/ml-pipeline.md` | Step 1 | A |
| 3 | 反証専任エージェント refuter を新設(R1 対応) | `.claude/agents/refuter.md` | なし | A |
| 4 | 手順6.2「レビュー指摘の接地検証」を新設(R3 対応) | `.claude/commands/ml-pipeline.md` | Step 2(同一ファイル) | A |
| 5 | 手順6.3「反証濾過パス」を新設(R1 対応) | `.claude/commands/ml-pipeline.md` | Step 3, 4 | A |
| 6 | 手順7 の既存 NEEDS_REVISION 分岐を書き換え、HUMAN_REVIEW 出口と失敗遷移表1行を追加(R9 対応) | `.claude/commands/ml-pipeline.md` | Step 4, 5 | A |
| 7 | 手順5 に「計画遵守の照合」と generator への共通指示を追加(P10 対応) | `.claude/commands/ml-pipeline.md` | Step 2(同一ファイル) | A |
| 8 | 両 evaluator の指摘に証拠添付を必須化(R3 対応) | `.claude/agents/evaluator.md`, `.claude/agents/evaluator-standards.md` | なし | B |
| 9 | cross-review の Codex 指示文2箇所に HIGH/MEDIUM 指摘の証拠添付を要求(R3 対応) | `.claude/skills/cross-review/SKILL.md` | なし | B |
| 10 | evaluator-standards の「型安全性」に shape 注釈観点を追加(V6 対応) | `.claude/agents/evaluator-standards.md` | Step 8(同一ファイル) | B |
| 11 | python-standards にテンソル shape 注釈の規約節を新設(V6 対応) | `.claude/skills/python-standards/SKILL.md` | なし | B |
| 12 | planner の計画フォーマットに「事後条件」欄(`PC-n` 形式)を追加(V10 対応) | `.claude/agents/planner.md` | なし | B |
| 13 | tdd スキルに「事後条件は実装より先に固定する」節を追加(V10 対応) | `.claude/skills/tdd/SKILL.md` | なし | B |
| 14 | spec-checklist の測定可能性に事後条件の検査を追加(V10 対応) | `.claude/skills/spec-checklist/SKILL.md` | Step 12 | B |
| 15 | generator に事後条件のテストファースト・shape 自己チェック・計画ステップ対応表を追加(V10 / V6 / P10 対応) | `.claude/agents/generator.md` | Step 11, 12 | B |
| 16 | `CLAUDE_REFUTE_PASS` の回帰アサーションを**実装前に**書き RED を確認(R1 対応) | `verify-installers.sh` | なし | C |
| 17 | 雛形とインストーラ sh/ps1 に `CLAUDE_REFUTE_PASS` を追加しコミット後に GREEN を確認(R1 対応) | `templates/settings.local.json.template`, `claude-init.sh`, `claude-init.ps1` | Step 16 | C |
| 18 | README / CHANGELOG を**実装済みの実物を grep で確認してから**更新(全ID 対応) | `README.md`, `CHANGELOG.md` | Step 1〜17 すべて + A〜C の統合ブランチへのマージ完了 | D(逐次・worktree を作らない) |

### 各ステップの補足

**Step 1**(`router.md`、I5・abstract のみ)
既存の「## 判定基準」テーブルの直後に「## リスク階層の判定基準(規模と直交)」を新設する。文献は具体的閾値を持たないので、**このテンプレートで実際に脆い領域の列挙**だけで定義する。

| 階層 | 該当条件(いずれかに一致) |
|---|---|
| 高 | `.claude/hooks/` / settings 系 / ガード・ゲートの挙動、`invariants.md`、`data/` 配下とデータ分割・前処理、秘密情報・認証、依存の追加/更新、インストーラ(`claude-init` / `claude-update`)・CI ワークフロー、公開インターフェースの破壊的変更、不可逆操作(削除・上書き・外部公開) |
| 低 | ドキュメント・コメント・ログ文言のみで、実行される挙動を変えない |
| 中 | 上記のどちらにも確実に一致しない場合(判断がつかない場合も中) |

**注意**: ルール節に「**高は上の列挙に一致する場合だけ**。迷ったら中にする」と明記する。規模判定の「迷ったら L」と同じ調子で「迷ったら高」にすると全依頼が格上げされ、傾斜配分という目的が消える(この失敗は実装時に起きやすい)。出力形式は既存の2行に `リスク階層: <高 / 中 / 低>` と `リスク理由: <1文>` を足した4行にする。

**Step 2**(`ml-pipeline.md` 手順0、I5)
S/M/L の3項目の直後に小節を1つ足す(30行以内)。

- リスク階層は router が同時に返す。**計画の「リスク」セクション(plan-reviewer 条件2)とは別の軸**であることを1行で明記する(同名の概念が2つできるため)。
- 作用は表1つ: 高 → 規模判定を1段上げる(S→M、M→L、L はそのまま)+ 手順6.3(反証濾過)を実行しない。中/低 → 現状どおり。
- 「リスク軸は**強める方向にのみ**作用させる。低リスクでも既存工程を省略しない」と明記する(summary の「低リスクは省力化」を保守的に縮退。理由は下記リスク欄)。
- 自律度 L1 では規模とリスク階層の両方をユーザーに提示して確認する(既存の L1 規約の拡張)。

**Step 3**(`.claude/agents/refuter.md` 新規、R1・本文確認済み)
既存 `.claude/agents/plan-premortem.md` の見出し構成(frontmatter → 導入文 → スコープ制約 → 基準テーブル → 作業手順 → 出力形式 → 重要なルール)に倣う。frontmatter は `model: sonnet` / `tools: Read, Grep, Glob, Bash`。

- 導入文: 「渡された各指摘について『この指摘は成り立たない』ことを示すことだけを試みる。擁護・改善案・新しい指摘は書かない」。
- **反証として認める根拠**(テーブル): 事実の不在(名指しされた関数・行・設定が実在しない)/ 経路の不成立(前提の呼び出し経路・入力が発生しない)/ 既存の防御(別の層で既に防がれている)/ 反例の実行(指摘どおりなら失敗するはずのコマンドが成功する)。いずれも**実行コマンドの出力か file:line の引用を必須**にする。
- **反証として認めない根拠**: 「軽微だ」「実務上問題にならない」等の価値判断、根拠を伴わない主張、言い換え・部分的同意。これらしか出せない場合は**反証失敗**とする(fail-closed。潰せなければ指摘は生き残る)。
- 出力形式: 指摘ごとに `判定: 反証成功 / 反証失敗` + `根拠: (コマンドと出力、または file:line)`。
- 重要なルール: 反証は指摘ごとに独立して行い、ある指摘を潰せたことを他の指摘の根拠にしない / PASS・NEEDS_REVISION などの判定を出さない / コードを変更しない / 迷ったら反証失敗。

**Step 4**(`ml-pipeline.md` 手順6.2 新設、R3・本文確認済み)
手順6 と手順6.5 の間に挿入する(6.1〜6.4 は空き番であることを確認済み)。**必須・常時実行だが、実行されるのは読み取り専用の単発コマンド数本**なのでトークン増は小さい。

- 対象は evaluator / evaluator-standards /(渡されていれば)cross-review の指摘のうち**重大度 HIGH と MEDIUM**(LOW は差し戻し根拠にならないので対象外。evaluator-standards の「HIGH/MEDIUM が無ければ基本 PASS」規約と整合)。
- 証拠の型ごとに検証手順を書く。(1) **file:line 形式**: **リーダーの Read ツールで該当ファイルの当該行付近(前後5行)を読み**、指摘が名指ししたシンボルがその範囲に現れることを確認する。Read は許可プロンプトを伴わないため、必須・常時実行の工程を止めない(`.claude/settings.json` の allow に `sed` は無く〔実測0件〕、既存の定義ファイルにも `sed` の使用実績が無いので第一手段にしない)。行番号の範囲外・ファイル不在は Read の失敗で判別する。**行番号がズレている場合は補助手段として `grep -n '<シンボル>' <path>` にフォールバック**し(grep は手順6 の feedback.md 注入で既に使われている)、ヒットすれば接地とみなして行番号の相違をレポートに記録する(差し戻し修正後は行がずれるため、フォールバックが無いと正しい指摘を大量に落とす)。(2) **再現コマンド形式**(「実装が存在しない」等、行を指せない指摘): 添えられたコマンドを実行し、報告された出力・終了コードが再現するか確認。**副作用のあるコマンド(書き込み・削除・学習ジョブ)は実行せず「検証不能」**とする。
- 結果の反映(表): 接地 → 従来どおり根拠にする / 未接地・検証不能の **MEDIUM** → 根拠にせず手順8.5 のレポートに「未接地の指摘」として記載 / 未接地・検証不能の **HIGH** → **破棄せず**手順7 の HUMAN_REVIEW 条件1に該当させる。
- 「**判定そのもの(PASS / NEEDS_REVISION / FAIL)は書き換えない**。この工程が絞るのは差し戻しに使う指摘の集合だけ」と明記する(2軸独立レビューの判定をリーダーが上書きしないため)。
- 並列実装ではグループごとに実施する。
- **適用範囲**: 手順6(2軸レビュー)を通る全経路に適用する。手順0 の **M 短縮経路**(planner を省略し generator → evaluator で回す経路)でも evaluator の指摘は差し戻しに使われるため、同じく適用する。**S 経路は evaluator を省略する**ため対象外。

**Step 5**(`ml-pipeline.md` 手順6.3 新設、R1)
既存の条件分岐節(手順5.5・6.6・6.8)と同じ書式にする。

- 発火条件: `CLAUDE_REFUTE_PASS=1` **かつ** 手順0のリスク階層が「高」でない **かつ** 手順6.2 を通過した HIGH 指摘が1件以上。それ以外はスキップして手順6.5へ。
- refuter に接地済み HIGH 指摘の全文と変更ファイル一覧を渡す。
- 反映: 反証成功 → 差し戻し根拠から外し、レポートに「反証により棄却された指摘」として反証根拠つきで記載 / 反証失敗 → 差し戻し根拠に昇格 / **指摘の根拠と反証が同じ file:line または同じコマンドについて正面から矛盾** → 手順7 の HUMAN_REVIEW 条件3に該当。
- 「この工程は指摘を**減らす**方向にしか働かないため、リスク階層が高の依頼では実行しない」と理由つきで明記する。
- 既存の「Codex 同箇所指摘で重大度+1」(evaluator.md 185-190行、合意方向)は**変更しない**。昇格は反証で、重大度は合意で決めるという併用関係を1行で注記する。

**Step 6**(`ml-pipeline.md` 手順7、R9・abstract のみ)
文献は「verbalized confidence は過信で較正が要る」としか言えないため、**自己申告の確信度を一切使わない設計に縮退する**。リーダーが機械的に観測できる条件だけを列挙する。

- **既存の即時分岐を先に書き換える**(これを忘れると新設した HUMAN_REVIEW 条件1・2 が参照されずに終わる)。ml-pipeline.md 502-505行の3項目のうち2つ目を、次のように改める。
  before: `- どちらかが NEEDS_REVISION: 指摘をまとめて generator に差し戻す(手順5に戻る)`
  after : `- どちらかが NEEDS_REVISION: 手順6.2・6.3 を経て残った差し戻し根拠を確認し、下記 HUMAN_REVIEW の条件に該当しなければ、その根拠だけをまとめて generator に差し戻す(手順5に戻る)`
  1つ目(両 PASS → 手順7.5)と3つ目(FAIL 3回連続 → planner)は変更しない。
- 「**HUMAN_REVIEW(判定不確実の出口)**」小節を手順7 の失敗遷移表の直前に置き、条件を表で3件固定する。(1) HIGH 指摘が手順6.2 で未接地・検証不能のまま残った(観測: 手順6.2 の結果表)/ (2) 軸の判定が NEEDS_REVISION なのに手順6.2・6.3 を経て残った差し戻し根拠が0件(観測: 指摘集合の件数)/ (3) 指摘の根拠と手順6.3 の反証が同じ file:line・同じコマンドについて正面から矛盾(観測: 両者の実行ログ)。
- 提示するもの: 該当条件 / 当該指摘の全文 / 接地・反証で実行したコマンドと出力 / 選択肢(差し戻す・この指摘を採用せず進む・計画に戻る)。
- 失敗遷移表に1行追加: `| 判定不確実(上記3条件のいずれか) | 0回 | 停止・人間へ(HUMAN_REVIEW) |`。
- feedback.md への記録は既存規約と同形式(`## YYYY-MM-DD [失敗: 判定不確実]`)。
- **注意**: evaluator の判定語彙(PASS / NEEDS_REVISION / FAIL)と verdict の語彙(PASS / FAIL / UNVERIFIABLE)は**変更しない**。ADR 0003 決定#2 に明示された方針であり、破ると README・retrospective・cross-review・spec_gate 側へ連鎖する。

**Step 7**(`ml-pipeline.md` 手順5、P10・本文確認済み)
「generator への共通指示」の箇条書きに2項目を足し、その下に「**計画遵守の照合(必須)**」を新設する。

- 共通指示への追加: (a) 各ステップに着手する直前に計画ファイルの該当ステップ行を読み直し、対象ファイル・依存・並列グループを確認してから作業する(P10 の「定期リマインド」の最小形)。(b) 完了報告と計画ファイル末尾の作業ログの**両方**に「計画ステップ対応表」(`| 計画ステップ# | 実施内容 | 変更ファイル | 検証コマンドと結果 | コミットID |`)を含める。計画に無い変更はステップ# を「計画外」とし理由を1文添える。
- リーダーの照合: 計画の実装手順のステップ数を `grep -cE '^\| [0-9]+ \|' <計画ファイル>` で数え、対応表が全ステップ番号を覆うことを確認する。**並列実装ではグループごとの表を合算して**全ステップを覆うことを確認する。
- 欠落時: generator に未実施の理由を確認し、「計画の前提が誤っていた」なら手順3(計画の見直し)へ、単なる実施漏れなら手順5に差し戻す。確認は1回まで、2回目はユーザーへ。「計画外」行がある場合は変更内容をユーザーに提示して続行可否を確認する。

**Step 8**(`evaluator.md` / `evaluator-standards.md`、R3)
両ファイルのレポート形式の指摘行の直後に、**同一の文面**で追加する(片方だけの追加は接地検証を半分無効にする)。

```
- HIGH / MEDIUM の指摘には次のどちらかの証拠を必ず添える(手順6.2 の接地検証が
  これを機械的に確認する)。証拠を添えられない指摘は LOW とし、差し戻しの根拠にしない。
  1. `<ファイルパス>:<行番号>` と、その行に実在するシンボル名
  2. 再現コマンドとその出力(「実装が存在しない」等、行を指せない指摘の場合)
```

**Step 9**(`cross-review/SKILL.md`、R3)
手順6.2 の接地検証は Codex の指摘も対象にするため、Codex 側に証拠を要求していないと「行を指せない指摘」が系統的に未接地に落ちる。手順3 の Codex 指示文に1文を足す。

- 対象は **CODEX_MODEL 設定時と未設定時の2箇所**(現行 41-51行)。**両方に同一の文面で追記する**(片方だけの追記は `.claude/rules/consistency.md` の対になる記述の違反であり、どちらの経路を通ったかで指摘の質が変わる)。
- 追記する文面: 「HIGH / MEDIUM の指摘には、ファイルパスと行番号、またはその指摘を再現するコマンドを必ず添えてください。」既存の「ファイルパスと行番号を含めてください。」の直後に続ける形にし、既存文は消さない(最小diff)。
- 手順4(レポート整形)には手を入れない(Codex の出力をそのまま整形する既存方針を維持する)。

**Step 10**(`evaluator-standards.md`、V6・abstract のみ)
評価基準テーブルの「型安全性」行に「テンソルを受け渡す公開関数に shape/dtype 注釈(jaxtyping 等)、または docstring の Shape 節 + shape assert があるか」を追記する。既存セルの記述は消さない(最小diff)。

**Step 11**(`python-standards/SKILL.md`、V6)
「## 型ヒント」節(23-28行)の直後に「## テンソルの shape 注釈(ML コードのみ)」を新設する。**文献は abstract のみ確認**なので、ライブラリの具体的な API 名・有効化関数名を断定して書かない。

- 動機を1文: mypy は `Tensor` の中身(次元・dtype)を検査できないため、shape の食い違いは型チェックを素通りする。
- 対象: テンソルを受け渡す**公開関数**(モデルの forward、collate_fn、前処理、損失、評価指標)。
- 手段1: jaxtyping の注釈(`Float[Tensor, "batch instance dim"]` のように次元名まで書き、次元名は関数をまたいで一貫させ CONTEXT.md の用語に合わせる)。導入は `uv add --dev jaxtyping beartype`。**実行時検査はテスト実行時にだけ有効化し、有効化の具体的な記述は jaxtyping の公式ドキュメントに従う**(conftest.py に置き、本番実行のオーバーヘッドを増やさない)。
- 手段2(依存を増やせない場合の代替): docstring に Shape 節(入力・出力の次元)を書き、テストで `assert x.shape == (...)` を1つ以上置く。
- どちらも無いテンソル受け渡し関数は evaluator-standards の「型安全性」で指摘対象になる、と締める(Step 10 との対応)。
- **注意**: テンプレート本体に対象コードは無い(確認済み)ので、この節は導入先プロジェクト向けの規約である旨を1行添える。

**Step 12**(`planner.md`、V10・abstract のみ)
「## 計画フォーマット」の表に行を1つ足す。

| 事後条件(postconditions) | 実装を見る前に固定できる、機械照合可能な条件を列挙する。**表の行 ID は `PC-1` `PC-2` … の形式にし、素の連番を使わない**(手順5 の計画遵守の照合 `grep -cE '^\| [0-9]+ \|'` が実装手順の行だけを数えられるようにするため)。1件ごとに「対象(関数・スクリプト・コマンド)/ 入力 / 満たすべき条件」を書く。期待値は設計書の受け入れ条件・計画の目的から導き、**既存実装の出力を写さない**。設計書がある場合は R-ID と対応づける。コード変更を含まない計画では「なし(理由)」と明記する |

制約の箇条書きに2行:
- 「事後条件は Generator が実装前にテスト化する(generator.md の作業手順)。実装後に書くと実装の挙動をなぞるだけのテストになり検出力が無くなる」。
- 「**実装手順テーブル以外の表で、行頭セルを素の連番(`| 1 |` 等)にしない**。手順5 の計画遵守の照合が実装手順の行数を誤って数える」。事後条件表だけでなく将来追加される表にも効かせるため、planner.md 側の一般規約として書く。

**Step 13**(`tdd/SKILL.md`、V10)
「## 進め方(1振る舞いにつき)」の直後に「## 事後条件は実装より先に固定する」を新設する(既存の「## 適用範囲の判断」「## 注意」の粒度・文体に合わせる)。

- テストの期待値は**仕様**から取る。実装や実行結果から逆算した期待値(現在の出力をそのまま assert する)はバグを固定化するだけで検出力にならない。
- 計画に「事後条件」欄がある場合はそれをそのまま Red のテストにする。
- バグ修正では修正前の出力を期待値にしない。「本来どうあるべきか」を設計書・計画から決めてから Red を書く。
- 期待値の出所(設計書の R-ID、計画の事後条件、仕様の該当箇所)をテストの docstring かコメントに1行書く。

**Step 14**(`spec-checklist/SKILL.md`、V10)
検査の5次元テーブルの「測定可能性」行の検査内容に「計画に『事後条件』欄があり、各事後条件が実行コマンドで機械照合できる形か(実装を見る前に固定できる内容になっているか)」を追記し、例セルに1件足す。**次元は増やさない**(5次元の構造は README・ml-pipeline 手順3.3 の記述と結びついているため)。

**Step 15**(`generator.md`、V10 / V6 / P10)
1ファイルに3候補ぶんを追加する。**挿入で番号がずれるため、編集対象は番号でなく内容で特定し、下記の順序で編集する**(先に末尾側を編集し、最後に番号がずれる挿入を行う)。

編集順序:
1. **自己チェック項目**(「## 自己チェック項目」節)に1行追加: 「テンソルを受け渡す公開関数に shape 注釈(または Shape 節 + shape assert)を付けたか」(V6)。番号なしのチェックリストなのでずれの影響を受けない。
2. **完了報告を規定する項目**(現行の作業手順7番。本文が「完了したら作業ログを計画ファイル末尾に追記し、完了報告に変更したファイルの一覧を含める」で始まる項目)に、「計画ステップ対応表」の要求と、各ステップ着手前に計画の該当行を読み直す規律を追記する(P10)。**表の列は Step 7 と同一にする**。
3. **最後に**、作業手順の「計画の各ステップを順番に実装する」項目(現行4番)の**直前**に新項目を挿入する: 「計画に『事後条件』がある場合、実装より先に事後条件をテストとして書き、実装前に実行して FAIL することを確認する。期待値は計画・設計書の仕様から取り、既存実装の出力を写さない」(V10)。挿入後、以降の項目番号を1つずつ繰り下げる。

**注意**: 挿入を先に行うと、上記2で「作業手順7」を番号で探した場合に別項目(ログ保存の項目)を書き換えてしまう。番号での参照は避け、必ず本文の書き出しで特定する。編集後、`grep -n "^[0-9]\." .claude/agents/generator.md` で番号が連番になっていること(飛び・重複が無いこと)を確認する。

**Step 16**(`verify-installers.sh`、テストファースト)
サンドボックス A(新規導入)のアサーション群(90行付近の「任意機能は既定では無効のまま」の隣)に既存の `assert` 書式で1件追加する。

```
assert "init: CLAUDE_REFUTE_PASS が雛形に含まれる(既定無効)" grep -q '"CLAUDE_REFUTE_PASS": "0"' "$A/.claude/settings.local.json"
```

**この時点で `bash verify-installers.sh` を実行し、この1件が NG になること(RED)を確認して報告に含める**。既存アサーションが NG になっていないことも同時に確認する。

**Step 17**(雛形とインストーラ)
- `templates/settings.local.json.template` の `CLAUDE_FINAL_GATE` の直後に `"CLAUDE_REFUTE_PASS": "0"` を追加する(`enable_feature()` は雛形にキーが無いと警告して失敗するため必須)。
- `claude-init.sh` の `OPTIONAL_FEATURES`(125-133行)と `claude-init.ps1` の `$OptionalFeatures`(117-126行)に同一の説明文で1件追加する。説明文は「レビュー指摘の反証濾過(HIGH 指摘を refuter が潰し、生き残った指摘だけ差し戻しに使う)」。
- **注意**: `verify-installers.sh` は配布ペイロードを HEAD から clone するため、**この変更をコミットするまで Step 16 のアサーションは GREEN にならない**。コミット後に再実行して GREEN を確認し、その順序を報告に書く。
- 閾値変数は導入しない(二値フラグのみ。`enable_feature()` が `"1"` を書き込むため閾値変数を質問リストに載せてはならない、という既存規約に従う)。

**Step 18**(README / CHANGELOG、逐次・最後。worktree を作らない)
**このステップは A〜C の並列グループが統合ブランチへマージされ、統合テストが
通った後に、統合ブランチ上で単独の generator を起動して実行する**。
D のための worktree・サブブランチは作らない(マージ前の状態から分岐すると
以下の現物確認が成立しないため)。
**このステップの最初に、Step 1〜17 で実際に書かれた内容を Read と grep で現物確認してから書く**(README を実装と別グループで書いたことが `patterns.md` パターン1・21件の主因)。行番号は実装でずれるので grep で再特定する。更新箇所:

- mermaid 図: 手順6.2(接地検証)と HUMAN_REVIEW 出口を反映(**増やすノードは2つまで**。図の可読性を優先する)
- 環境変数表: `CLAUDE_REFUTE_PASS` を1行(既存行の書式・語調に合わせる)
- 2.1 パイプライン手順の番号付きリスト: 手順0のリスク階層、手順6.2 / 6.3、HUMAN_REVIEW を反映し、以降の番号を繰り下げる
- 2.3 個別エージェント: `@refuter` の項を新設(既存 `@plan-premortem` の項の見出し構成・呼び出し例・「渡すもの/すること/出力」の3点構成に倣う)、`@router` の項にリスク階層を追記
- 3.1 エージェント一覧表: `refuter` 行を追加、`router` 行にリスク階層を追記
- 3.2 スキル表: `python-standards` / `tdd` / `spec-checklist` の説明に今回の追加を反映(必要な範囲だけ)
- 3.17 3層レビューの図: 第1層と第2層の間に「接地検証(必須)/ 反証濾過(opt-in)」を追記
- 3.20 失敗遷移表(1340行付近): HUMAN_REVIEW 行を追加。router の説明(1348行付近)にリスク階層を追記
- 6章ディレクトリツリー: `refuter.md` の行を追加(既存の1行説明の書式に合わせる)
- `CHANGELOG.md`: `[Unreleased]` の**既存の** `### Added(2026-08-04)` ブロックにバレットを追加する(同一日付・同一種別の見出しを新設しない。前回の実績と同じ扱い)

## 並列化判定

**並列化可能(グループ A / B / C の3つ。D は並列グループではない)**。

- **A / B / C**: 対象ファイルが完全に分離し依存も無いため、手順5 の規約どおり
  worktree 分離付きのサブブランチで並列実装する。**グループ B は8ファイル・8ステップ
  (Step 8〜15)と最も大きい**が、V6 / V10 は複数ファイルにまたがるため同一グループに
  置く必要がある(分割すると文面の食い違いが出る)。
- **D(README / CHANGELOG)**: **並列グループとして worktree を作らない**。
  A〜C のサブブランチを統合ブランチへマージし(手順6.5)、統合テストが通った後に、
  リーダーが**統合ブランチ上で逐次 generator を起動する後続ステップ**として実行する。
  D の worktree を A〜C と同時に作ると、A〜C のマージ前状態から分岐するため
  「実物を grep で確認してから README を書く」が原理的に成立せず、
  防ごうとしている記述と実装の乖離(`patterns.md` パターン1・21件)が再発する。
  この方式は前回計画 `.claude/plans/20260804-robustness-5proposals.md` のグループE で
  実績がある。
- 手順5 は全グループの worktree を一括作成し、手順6.5 は全 PASS 後の一括マージだけを
  規定しているため、**この「D はマージ後に逐次」という運用はリーダーが明示的に守る**
  (現行の ml-pipeline にはグループ間依存を表す語彙が無い)。

グループをまたぐ候補(R3 は A と B、P10 は A と B、R1 は A と C)があるため、**両側が一致すべき文面はこの計画で固定してある**(証拠添付の2形式・計画ステップ対応表の列・環境変数名)。Generator は自グループの担当ファイルだけを触り、相手側の文面を勝手に言い換えないこと。食い違いは検証方法1の grep で検出する。

## 検証方法

1. **記述と実装の整合(grep。すべて実行してヒット数を報告する)**
   - `grep -n "手順6.2" .claude/commands/ml-pipeline.md` → 見出しと参照で**2箇所以上**
   - `grep -n "手順6.3" .claude/commands/ml-pipeline.md` → **2箇所以上**
   - `grep -n "HUMAN_REVIEW" .claude/commands/ml-pipeline.md` → 条件表・出口・失敗遷移表で**3箇所以上**
   - `grep -rln "refuter" .claude/agents/refuter.md .claude/commands/ml-pipeline.md README.md` → **3ファイル全て**
   - `grep -rln "CLAUDE_REFUTE_PASS" templates/settings.local.json.template claude-init.sh claude-init.ps1 README.md .claude/commands/ml-pipeline.md` → **5ファイル全て**
   - `grep -rln "リスク階層" .claude/agents/router.md .claude/commands/ml-pipeline.md README.md` → **3ファイル全て**
   - `grep -rln "事後条件" .claude/agents/planner.md .claude/skills/tdd/SKILL.md .claude/skills/spec-checklist/SKILL.md .claude/agents/generator.md` → **4ファイル全て**
   - `grep -rln "jaxtyping" .claude/skills/python-standards/SKILL.md .claude/agents/generator.md .claude/agents/evaluator-standards.md` → **3ファイル全て**
   - `grep -rln "計画ステップ対応表" .claude/agents/generator.md .claude/commands/ml-pipeline.md` → **2ファイル全て**
   - `grep -c "再現コマンド" .claude/agents/evaluator.md .claude/agents/evaluator-standards.md` → **両方1以上**(片側だけの追加を検出)
   - `grep -c "再現" .claude/skills/cross-review/SKILL.md` → **2以上**(CODEX_MODEL 設定時・未設定時の両プロンプトに証拠要求が入っていること)
   - `grep -n "残った差し戻し根拠" .claude/commands/ml-pipeline.md` → **1件以上**(手順7 の既存分岐が書き換わっていること)
2. **インストーラ sh / ps1 の1対1対応**(`.claude/rules/consistency.md` の標準形)
   ```
   diff <(grep -oE 'CLAUDE_[A-Z_]+' claude-init.sh | sort -u) \
        <(grep -oE 'CLAUDE_[A-Z_]+' claude-init.ps1 | sort -u)
   ```
   → 差分なし。**件数(生・一意)と diff の3点**を報告する。
3. **インストーラ回帰**: `bash verify-installers.sh` → `NG:` 0件。新規アサーションが `OK:` で出る。**Step 16 の時点では NG(RED)、Step 17 のコミット後に OK(GREEN)** の両方を報告する。
4. **フック回帰**: `bash verify-hooks.sh` → 全テスト PASS(本計画はフックを変更しないため、既存と同一の結果になることの確認)。
5. **単体テスト**: `uv run --with pytest python -m pytest tests/ -q` → **118 passed**(件数が減っていないこと)。
   このリポジトリには pyproject.toml が無く pytest も未導入のため、`--with pytest` を
   省略すると `No module named pytest` で実行できない(README.md 3.16節の
   env_fingerprint 受け入れ検証と同じ起動形式に合わせる)。
6. **接地検証の実挙動(複数・混在・0件・ズレを必ず含める)**: 一時ファイルに手作りの指摘リストを置き、手順6.2 の手順どおり実行して仕様どおりかを確認する。
   - 指摘0件 → 何も除外されず素通りする
   - HIGH×1(実在する file:line)+ MEDIUM×1(存在しない行番号) → 前者は根拠に残り、後者は「未接地」に落ちる
   - HIGH×1 が未接地 → 破棄されず HUMAN_REVIEW 条件1に該当する
   - **同一ファイルの複数行を指す指摘3件 + 再現コマンド形式1件の混在** → 4件が個別に判定される
   - **行番号が±10ズレていてシンボルは一致** → `grep -n` フォールバックで接地と判定され、行番号の相違が記録される
   確認後、一時ファイルを削除する。
7. **反証濾過の実挙動**: `@refuter` を手作りの HIGH 指摘3件で起動する。(a) 実在する明白な問題 → 反証失敗(昇格)/ (b) 実在しない関数を名指しした主張 → 反証成功(棄却、根拠に grep 出力がある)/ (c) 事実は正しいが「軽微だから問題ない」としか反証できないもの → **反証失敗**(価値判断は反証と認めない)。出力が定義した形式(判定 + 根拠)を守り、新しい指摘・改善案が含まれていないこと。
8. **リスク階層の判定**: `@router` に3パターンを渡す。(a) `.claude/hooks/` を触る依頼 → 高 / (b) 単一モジュールのロジック変更 → 中 / (c) README の typo 修正 → 低。手順0 の格上げ規則どおりの経路が導かれること(高では1段格上げされ、低でも工程が省略されないこと)。
9. **計画遵守の照合(複数・入れ子)**: 本計画の実装後、generator の完了報告が計画ステップ対応表を含み、`grep -cE '^\| [0-9]+ \|' .claude/plans/20260804-survey7-robustness.md` が **18** を返し、対応表の行数と一致すること。**事後条件表を `PC-n` 形式にしたことで実装手順の行だけが数えられる**(素の連番のままだと 18 + 4 = 22 と誤カウントする。修正前の本計画で実測 21)。**並列実装した場合はグループごとの表を合算して18ステップ全てを覆うこと**(入れ子ケース)。
10. **ml-pipeline の肥大化の確認**: `wc -l .claude/commands/ml-pipeline.md` → 実装後に **800行未満**(新設4箇所の合計増分が約150行に収まっていること)。

## リスク

- **既存動作との非互換**: 手順6.2(接地検証)は必須・常時実行になるため、全パイプラインでレビュー後に読み取りコマンドが数本増える。証拠を添えられない指摘は LOW に落ちるので、**移行期は差し戻しの件数が減る**(意図した強化だが、指摘が消えたように見える)。手順6.3 は opt-in なので既定の動作は変わらない。
- **接地検証が正しい指摘を落とす(false negative)**: 行番号ズレ・複数箇所にまたがる指摘で起きうる。シンボル grep フォールバックと「HIGH は破棄せず HUMAN_REVIEW へ」で二重に緩和するが、MEDIUM の取りこぼしは残る。実運用で誤除外が出たら feedback.md 経由で規約を見直す。
- **リスク階層でコストが跳ねる**: 全依頼が「高」判定されると常に L 経路になりトークンが増える。「高は列挙一致のみ、迷ったら中」「格上げは1段のみ」で抑えるが、判定の当たり外れは実走してみないと分からない。
- **ml-pipeline.md の肥大化**: 644行 → 約780行。長すぎるとリーダーが手順を端折る。新設節は各30行以内に抑え、詳細規約は refuter.md 側に置く(検証方法10 で機械的に確認)。
- **1ファイルに複数候補が集中する**: `ml-pipeline.md`(5候補)と `generator.md`(3候補)は同一グループ内で順に編集する必要があり、番号付き手順・自己チェックの連番を壊しやすい。
- **abstract のみの候補の限界**: V6 / R9 / I5 / V10 は本文未確認のため、文献の数値・具体手順に依存しない形に縮退してある(V6: ライブラリ API を断定せず公式ドキュメント参照に留める / R9: 自己申告の確信度を使わず観測可能な3条件に固定 / I5: 強める方向のみ / V10: 書式と出所の規律のみで自動生成はしない)。効果は前回同様 feedback.md の実データで検証する。
- 検討した代替案と不採用理由:
  - **R9 で evaluator の判定を4値にする案** — 不採用。ADR 0003 決定#2「既存表記と verdict の語彙は変更しない」と正面衝突し、README / retrospective / cross-review へ連鎖する。不確実性の3条件はすべてリーダーが観測できるため、リーダー側の出口で足りる。
  - **R3 を軽量エージェント(haiku)に判定させる案** — 不採用。「判定の接地」を再び LLM に判定させると同じ問題が再帰する。file:line の実在確認は grep / sed で決定論的に行える。
  - **R3 / P10 の機械検査を新規スクリプト(`scripts/`)にする案** — 不採用。`scripts/` はインストーラの配布対象外(確認済み)で導入先に届かず、`.claude/skills/` 配下にスクリプトを置いた前例も無い。単発の読み取りコマンドで足りる範囲に留めた。
  - **V6 を quality_gate(Stop フック)に組み込む案** — 不採用。jaxtyping / beartype は**実行時**検査でテスト実行時に発火するため、静的解析ゲートに置く必然性が無い。加えてフックは Claude から編集不可で、ユーザーの手動 `cp` 工程が必要になる(本計画はフック変更ゼロで完結する)。
  - **V10 を plan-reviewer の条件9にする案** — 不採用。「8条件は固定」の記述が README を含む複数箇所にあり波及が大きい。計画の書き方の品質は手順3.3 で必ず走る spec-checklist の担当で、測定可能性次元に自然に収まる。
  - **R1 を常時実行にする案** — 不採用。HIGH 指摘のたびにエージェント起動が増える。opt-in + 高リスク時は無効(指摘を落とさない)が保守的。
  - **R1 で「全件反証成功なら判定を PASS に戻す」案** — 不採用。リーダーが2軸レビューの判定を書き換えることになり、独立レビューの前提が壊れる。判定は据え置き、根拠0件の状態は HUMAN_REVIEW 条件2として人間に渡す。
  - **I5 で低リスク時にレビュー工程を省略する案**(summary の「低リスクは省力化」) — **保守的に縮退して不採用**。誤 PASS のコストが読めず、既定は現状維持という思想にも反する。省力化は feedback.md の採択率データが貯まってから別途検討する(この縮退が summary の記述との唯一の意図的な乖離)。
  - **P10 の「定期リマインド」を実行中の監視エージェント(R10 系)で行う案** — 不採用。常時監視は重く本計画の範囲を超える。ステップ着手前の計画再読と完了時の対応表照合で、承認後の空白の主要部分は埋まる。
- 未確認の仮定:
  - 未確認の仮定: `claude-init.ps1` への変更はこの環境(pwsh 無し)では実行検証できず、sh 版との文字列一致でしか担保できない / 検証: `grep -n "pwsh" verify-installers.sh` / 期待: 1件ヒットし、ps1 は対象外である旨のコメントが表示される
  - 未確認の仮定: 新設4節を足しても `ml-pipeline.md` は1回で読み切れる長さに収まる / 検証: `wc -l .claude/commands/ml-pipeline.md` / 期待: 実装前の値が `644` で、増分150行を足しても800行未満に収まること

## トレーサビリティ

要件ソースに受け入れ条件テーブルが無いため、`summary.md` §3 優先候補表の文献ID を要件IDとして使う。

| ID | 候補 | 文献の確認状態 | 対応ステップ | 検証方法 |
|---|---|---|---|---|
| V6 | jaxtyping + beartype による shape 検査 | abstract のみ | Step 10, 11, 15, 18 | 検証方法1の `jaxtyping` grep が3ファイル全てヒット |
| R3 | レビュー指摘の接地検証 | 本文確認済み | Step 4, 8, 9, 18 | 検証方法6(0件/混在/ズレ/未接地HIGH の4ケース)+ 検証方法1の `手順6.2` / `再現コマンド` grep(cross-review 2箇所を含む) |
| P10 | 計画遵守の検証 | 本文確認済み | Step 7, 15, 18 | 検証方法9(ステップ数18・並列合算)+ 検証方法1の `計画ステップ対応表` grep |
| R9 | HUMAN_REVIEW 出口 | abstract のみ | Step 6, 18 | 検証方法1の `HUMAN_REVIEW` grep が3箇所以上、`残った差し戻し根拠` grep が1件以上 + 検証方法6の未接地HIGHケース |
| I5 | リスク階層ゲート | abstract のみ | Step 1, 2, 18 | 検証方法8(高/中/低の3パターン)+ 検証方法1の `リスク階層` grep |
| V10 | 事後条件の事前固定 | abstract のみ | Step 12, 13, 14, 15, 18 | 検証方法1の `事後条件` grep が4ファイル全てヒット + 検証方法9(`PC-n` 化により18が返る) |
| R1 | 反証濾過パス | 本文確認済み | Step 3, 5, 16, 17, 18 | 検証方法7(反証成功/失敗/価値判断の3ケース)+ 検証方法2, 3 |

対応ステップの無い ID は無い。Step 18 は単独ではどの ID にも属さないが、`.claude/rules/consistency.md` の「記述と実装の整合」を満たすため全 ID に対応する。

## コスト見積もり(cost_estimate)

学習ジョブ・実験を含まない定義ファイルのみの変更のため、plan_gate の検査対象外とする。

```yaml
experiment: false
```

参考値(学習ジョブが無いため全て0。並列実装のグループ数は `cost_estimate.parallel_jobs`(学習ジョブの並列度)とは別概念):

```yaml
cost_estimate:
  train_minutes: 0
  epochs: 0
  dataset_gb: 0
  parallel_jobs: 0
```

## 作業ログ(並列グループC: Step 16〜17)

計画ステップ対応表:

| 計画ステップ# | 実施内容 | 変更ファイル | 検証コマンドと結果 | コミットID |
|---|---|---|---|---|
| 16 | サンドボックスA のアサーション群に `CLAUDE_REFUTE_PASS` 雛形回帰アサーションを1件追加(テストファースト)。コミット前に `bash verify-installers.sh` を実行し、新規1件のみ NG(RED)・既存94件は OK であることを確認 | `verify-installers.sh` | `bash verify-installers.sh` → RED: `OK:` 94件 / `NG:` 1件(`NG: init: CLAUDE_REFUTE_PASS が雛形に含まれる(既定無効)`のみ) | 71debf5 |
| 17 | `templates/settings.local.json.template` の `CLAUDE_FINAL_GATE` 直後に `"CLAUDE_REFUTE_PASS": "0"` を追加、`claude-init.sh` の `OPTIONAL_FEATURES` と `claude-init.ps1` の `$OptionalFeatures` に同一説明文で1件追加。コミット後に `bash verify-installers.sh` を再実行し GREEN を確認 | `templates/settings.local.json.template`, `claude-init.sh`, `claude-init.ps1` | `bash verify-installers.sh` → GREEN: `OK:` 95件 / `NG:` 0件(新規アサーションも `OK:`) | 9a1deb7 |

実行順序: Step16 のアサーション追加 → `bash verify-installers.sh`(RED確認、コミット前)→ コミット71debf5 → Step17 の3ファイル編集 → コミット9a1deb7 → `bash verify-installers.sh`(GREEN確認、コミット後。`verify-installers.sh` は HEAD から clone するためコミット前の再実行では反映されない)。

sh/ps1 の1対1対応(`.claude/rules/consistency.md` 標準形):
```
diff <(grep -oE 'CLAUDE_[A-Z_]+' claude-init.sh | sort -u) \
     <(grep -oE 'CLAUDE_[A-Z_]+' claude-init.ps1 | sort -u)
```
→ sh: raw 20件 / unique 12件、ps1: raw 20件 / unique 12件、diff 差分なし(exit 0)。

閾値変数は導入せず二値フラグ(`"0"`/`"1"`)のみとした(`enable_feature()` / `Enable-Feature` が `"1"` を書き込む既存規約に従う)。手順6.3 本体(`CLAUDE_REFUTE_PASS` を参照するロジック)はグループAの担当のため未実装。

変更ファイル一覧: `verify-installers.sh`, `templates/settings.local.json.template`, `claude-init.sh`, `claude-init.ps1`

コミット: 71debf5(test, Step16), 9a1deb7(feat, Step17)
