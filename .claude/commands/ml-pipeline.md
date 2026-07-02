# MLパイプライン修正フロー

3エージェントでモデル/評価コードの修正を実行します。

## 事前準備(重要: claude 起動前にシェルで設定)
フック(スコープ制限・評価強制)を有効にするには、claude 起動前に
環境変数を設定します。

PowerShell (Windows):
$env:CLAUDE_WORK_SCOPE = "projects/Deep_MIL"
$env:CLAUDE_ENFORCE_EVAL = "1"
$env:CLAUDE_EVAL_CMD = "uv run python -m pytest projects/Deep_MIL/tests/ -q"
claude

bash (Linux/Mac):
export CLAUDE_WORK_SCOPE="projects/Deep_MIL"
export CLAUDE_ENFORCE_EVAL="1"
export CLAUDE_EVAL_CMD="uv run python -m pytest projects/Deep_MIL/tests/ -q"
claude

設定しない場合でも動作するが、スコープ制限はカレントディレクトリ基準になり、
評価強制は無効になる(Evaluatorのプロンプトによる確認のみ)。

## 前提: 作業スコープの確定
- $ARGUMENTS の冒頭で作業ディレクトリ(例: projects/Deep_MIL)が指定されていれば、それを作業スコープとする。
- 指定がなければ、着手前にユーザーに「どのプロジェクトディレクトリで作業するか」を必ず確認する。
- 以降、全エージェントはこの作業スコープ配下のファイルのみを対象とする。
  papers/ や slides/ など他ディレクトリは読み書きしない。
- `git diff` や `git commit` は必ず作業スコープにパスを限定する
  (例: `git diff -- projects/Deep_MIL/`、`git add projects/Deep_MIL/`)。

## 手順
1. 作業スコープを確定する(上記参照)。
2. planner に「やりたいこと」を渡し、作業スコープ内を調査させて実装計画を作成させる。
3. 計画をユーザーに提示し、承認されるまで進めない。
4. generator に計画ファイルのパスを渡し、作業スコープ内で実装させる。
5. evaluator に計画ファイルのパスと差分範囲を渡し、評価スクリプトを実行させて検証させる。
6. evaluatorの判定:
   - PASS: 完了レポートを出力
   - NEEDS_REVISION: 指摘を整理して generator に差し戻す
   - FAIL(3回連続): planner からやり直すことを提案
7. 最大3イテレーションで収束しなければユーザーに判断を仰ぐ。

$ARGUMENTS を「作業スコープ + やりたいこと」として解釈する。
