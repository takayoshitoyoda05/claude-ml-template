# MLパイプライン修正フロー

Planner/Generator に加え、Evaluator を2軸(Spec/Standards)に分けてレビューする。
フック制御用の環境変数(CLAUDE_WORK_SCOPE / CLAUDE_ENFORCE_EVAL / CLAUDE_EVAL_CMD)は
`.claude/settings.local.json` の `env` ブロックに設定する
(README「起動(フックの有効化)」の節を参照)。

対象に設計書(docs/active/)がある場合、`CLAUDE_SPEC_CHECK=1` を設定すると
Stop フックの `spec_gate` が「## 受け入れ条件」テーブルの全要件PASS・承認・監査OKを
機械検査し、欠けがあれば完了をブロックする。manual要件はユーザーが
`! uv run python .claude/hooks/spec_approve.py <要件ID>` で承認するまで通らない。

## 前提: 作業スコープの確定
- $ARGUMENTS の冒頭で作業ディレクトリ(例: projects/Deep_MIL)が指定されていれば、それを作業スコープとする。
- 指定がなければ、着手前にユーザーに「どのプロジェクトディレクトリで作業するか」を必ず確認する。
- 各エージェントへのタスク指示には作業スコープを必ず明記する。
  `git diff` / `git add` は作業スコープにパスを限定させる
  (例: `git diff -- projects/Deep_MIL/`、`git add projects/Deep_MIL/`)。

## 手順
1. 作業スコープを確定する(上記参照)。
2. 作業スコープ直下に CONTEXT.md があればここで一度だけ読み、用語の要点を
   以降の各エージェントへのタスク指示に含める(各エージェントに再読させない)。
3. 対象コードの範囲が広い場合は、planner を起動する前に Explore サブエージェント
   (Haiku)で大まかな下調べを行い、その要約を planner への指示に含める
   (Opus の調査トークンを節約するため)。
4. planner に「やりたいこと」+ CONTEXT要点 + Explore要約を渡し、実装計画を作成させる。
5. 計画をユーザーに提示し、承認されるまで進めない。
6. generator に計画ファイルのパスを渡して実装させ、完了報告から変更ファイルの一覧を受け取る。
7. 実装完了後、以下2つを独立に実行する(互いの判断が影響し合わないよう、
   それぞれ別の視点でレビューさせる)。両者には変更ファイル一覧を渡し、
   diff の確認範囲をそのパスに限定させる。
   - evaluator: 計画通りに動作するか(Spec)。評価スクリプトを実際に実行し数値で判定。
   - evaluator-standards: コーディング規約・可読性・型安全性・コードスメル(Standards)。
8. 両者の結果を集約する。
   - evaluator が PASS かつ evaluator-standards が PASS: 次の9に進む
   - どちらかが NEEDS_REVISION: 指摘をまとめて generator に差し戻す
   - evaluator が FAIL(3回連続): planner からやり直すことを提案
9. 対象に設計書(docs/active/)があり受け入れ条件テーブルがある場合、evaluator ×2 の後に
   spec-auditor を起動し、verdict ファイルの証拠を独立コンテキストで再検証させる。
   spec-auditor が NG を出した要件があれば generator に差し戻す。全件 OK なら完了レポートを出力する。
10. 最大3イテレーションで収束しなければユーザーに判断を仰ぐ。

$ARGUMENTS を「作業スコープ + やりたいこと」として解釈する。
