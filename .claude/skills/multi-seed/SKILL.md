---
name: multi-seed
description: 同じ実験を複数のseedで回して平均±標準偏差を出したいとき、または「seedを振って」「マルチシードで回して」「seed 42-46で実験して」と言われたときに必ず使う。長時間ジョブはバックグラウンドで走り、セッションを閉じても継続する。
---

# マルチシード実験(worktree 並列)

同一コミットのコードを seed 違いで N 本実行し、MLflow に記録して
平均±標準偏差まで自動集計する。コード実装用の worktree 分離基盤を
実験の分離(生成物の上書き防止)に転用する。

## 前提条件
- 実験スクリプトが `--seed <N>`(または同等の方法)で seed を受け取れること
- mlflow が導入済みであること(無ければ mlflow-log スキルの前提に従い、
  ユーザーに確認してから `uv add --dev mlflow` で導入)
- 実験スクリプトが MLflow 記録を持たない場合は、先に mlflow-log スキルの
  用途1に従って記録コードの追加を提案する(最小diffで)

## 進め方

### 1. 実験条件の確定
- seed: 「seed 42-46」(範囲)や「seed 7,13,42」(リスト)を受け付ける。
  未指定なら既定5本(42〜46)を提示し、開始確認を1回取る
  (計算資源を使う長時間ジョブを黙って起動しない)
- 実行コマンド(例: `uv run python train.py --seed {SEED}`)と
  experiment 名(CONTEXT.md の用語に合わせる)を確認する

### 2. 並列度の決定(自動キュー化)
- `nvidia-smi -L` で GPU 数を検出する。GPU 実験なら並列度 = GPU 数
  (seed ごとに `CUDA_VISIBLE_DEVICES` を割り当て)
- GPU が1枚、または検出不能なら**キュー実行**(並列度1で順次)に
  フォールバックする。その旨を報告してから起動する
- CPU 実験なら並列度は物理コア数を目安に保守的に決める
- ユーザーが「並列度 N で」と明示したらそれを優先する

### 3. worktree の作成(--detach)
現在の HEAD から seed ごとに作成する。ブランチは作らない:

```
git worktree add --detach .worktrees/seed-42
git worktree add --detach .worktrees/seed-43
...
```

(`.worktrees/` は gitignore 済み。作業ツリーが dirty な場合は
先にコミットを促す — 実験は再現可能なコミットに対して行う)

### 4. バックグラウンド起動(nohup、セッション非依存)
起動時にバッチIDを1つ決める(例: `BATCH=$(date +%Y%m%d-%H%M%S)`)。
並列度に応じてジョブ列を組み、worktree ごとに nohup で起動する。
キュー実行(並列度1)の例:

```
BATCH=$(date +%Y%m%d-%H%M%S)
nohup bash -c '
  for SEED in 42 43 44 45 46; do
    cd <メインリポジトリ絶対パス>/.worktrees/seed-$SEED
    MLFLOW_TRACKING_URI=file:<メインリポジトリ絶対パス>/mlruns \
      BATCH='"$BATCH"' \
      uv run python train.py --seed $SEED \
      > run.log 2>&1 || echo "FAILED" > run.failed
  done
' > /dev/null 2>&1 &
```

- **MLFLOW_TRACKING_URI は必ずメインリポジトリの絶対パス**にする
  (相対だと mlruns が worktree ごとに分散する)
- 各 run は `seed`・`git_commit`(worktree の HEAD)・`batch`(起動時に決めた
  共通バッチID)を必須 log_param とする。`mlflow.log_param("batch", "<バッチID>")`
  は全 run で必ず記録する
- MLflow の run 名は `seed-<N>` 形式にする(例: seed-42)
- PID とログの場所をユーザーに報告し、いったん手を離す
  (CLAUDE_NOTIFY=1 なら完了時にデスクトップ通知が出る)

### 5. 回収と集計(後続セッションでも可)
- 完了確認: 各 worktree の run.log 末尾と run.failed の有無、
  MLflow の run 状態を見る
- mlflow.search_runs の結果を **`params.batch == <バッチID>` で絞ってから**
  集計する(experiment 全体を集計すると過去の実験や再実行分が混入し
  平均±標準偏差が誤るため)
- 表(run名 / seed / 主要指標)+**平均±標準偏差**を提示する
- **部分集計**: 失敗 seed があっても完走分で集計してよい。ただし
  「5本中4本完走。seed 44 は失敗(run.log 末尾: ...)」を表に必ず明記する
- 失敗 seed の再実行は自動では行わない(ユーザーが指示したら該当 seed のみ)

### 6. 後片付け
- 成功 seed: run.log を `mlflow.log_artifact` で**batch と seed で一意に
  特定した run**に保存してから `git worktree remove` する(ログは MLflow
  側に残る。同一コミット・同一seedの再実行があっても batch で区別できる)
- 失敗 seed: worktree を**残す**(デバッグの現場保存)。ユーザーが
  原因を確認した後「片付けて」で削除する

## EXPERIMENT_LOG.md への記録
集計表の提示後、ユーザーの承認を得てから docs/EXPERIMENT_LOG.md に
要約(experiment名・seed本数・平均±std・コミット)を追記する。
自動では追記しない(evaluator の記録経路と混線させないため)。

## 注意
- 実行コマンドの組み立て以外でコードを変更しない(記録コード追加の
  提案は mlflow-log スキル経由)
- GPU 1枚での「並列」は VRAM を食い合って逆効果。キュー化の判断を
  勝手に覆さない
- 書き捨ての実験には使わない(worktree N 個分のディスクを使うため、
  論文・報告に載せる本実験向け)
