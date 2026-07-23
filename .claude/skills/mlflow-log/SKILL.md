---
name: mlflow-log
description: 実験の結果をMLflowに記録したいとき、過去の実験を比較・検索したいとき、または「実験を記録して」「実験AとBを比較して」「MLflowで確認して」と言われたときに必ず使う。
---

# MLflow 実験管理

docs/EXPERIMENT_LOG.md(人間が読む要約)と MLflow(機械が比較する詳細データ)を
併用する。MLflow は既定ではローカルの mlruns/ に保存される。ただし
MLFLOW_TRACKING_URI が設定された環境では外部サーバーに送信されるため、
ローカル保存を保証したい場合は記録コードの先頭で明示的に固定する。

## 前提条件
- mlflow がインストールされていること。無ければ `uv add --dev mlflow` で追加する
- 記録データは作業スコープ直下の mlruns/ に保存される(デフォルト)

## 用途1: 実験の記録
実験実行後、以下の項目を記録する。

```python
import mlflow

mlflow.set_tracking_uri("file:./mlruns")  # ローカル保存を明示(環境変数による外部送信を防ぐ)
mlflow.set_experiment("<実験グループ名>")  # 例: "attention-comparison"
with mlflow.start_run(run_name="<この実行の名前>"):
    # ハイパーパラメータ
    mlflow.log_param("seed", 42)
    mlflow.log_param("batch_size", 8)
    mlflow.log_param("model_version", "v3")
    # 結果指標
    mlflow.log_metric("mae", 0.123)
    mlflow.log_metric("rmse", 0.456)
    # 成果物(図など)
    mlflow.log_artifact("outputs/attention_map.png")
```

既存の実験スクリプトに記録コードを追加する場合は、最小diff規律に従い
記録に必要な行だけを追加する。

## 用途2: 実験の比較・検索
「実験AとBを比較して」と言われたら、MlflowClient で過去の run を取得して
表形式で比較する。

```python
import mlflow

mlflow.set_tracking_uri("file:./mlruns")  # ローカル保存を明示(環境変数による外部送信を防ぐ)
runs = mlflow.search_runs(experiment_names=["<実験グループ名>"])
# runs は DataFrame。params.*, metrics.* 列で比較できる
```

比較結果は表(run名 / 主要パラメータ / 主要指標)で提示する。

## 用途3: ブラウザUIの案内
ユーザーが視覚的に確認したい場合は、以下を案内する。

```
MLFLOW_TRACKING_URI=file:./mlruns uv run mlflow ui
```

ローカルの mlruns/ を確実に参照するため、環境変数で明示する。

http://localhost:5000 でダッシュボードが開く。

## EXPERIMENT_LOG.md との住み分け
| | EXPERIMENT_LOG.md | MLflow |
|---|---|---|
| 役割 | 人間が読む変更履歴の要約 | 機械が比較する詳細データ |
| 記録者 | evaluator が PASS 時に自動 | このスキル or 実験スクリプト内 |
| 粒度 | 1変更につき1エントリ | 1実行につき1run(seed違いも全部) |

## 注意
- mlruns/ は容量が大きくなるため .gitignore に追加することを提案する
  (実験の再現はコード+seed から可能なため、mlruns/ 自体のコミットは不要)
- 実験グループ名・run名は CONTEXT.md の用語に合わせる
