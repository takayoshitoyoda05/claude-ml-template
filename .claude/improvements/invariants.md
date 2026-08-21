# テンプレートの不変条件

improvement-reviewer がこのファイルを基準に改善案を審査する。
以下に反する改善案は、どれだけ合理的に見えても自動では適用しない。

## 絶対に変えてはいけないこと

### 役割分離
- Planner はコードを書かない
- Generator はレビュー判定をしない
- Evaluator / evaluator-standards はコードを変更しない
- evaluator(Spec)と evaluator-standards(Standards)の観点を混ぜない

### 安全ガード
- guard_scope.py / guard_bash.py のブロック条件を緩める変更は却下する
- 秘密情報の検知パターンを削除・無効化する変更は却下する
- permissions.allow に危険なコマンドを追加する変更は却下する

### 人間の介入ポイント
- Planner の計画はユーザー承認なしに実装に進めない。ただし、ユーザー自身が
  CLAUDE_AUTO_APPROVE=1 または CLAUDE_CONTROL_LEVEL=L3 を設定し、plan-reviewer が
  「自動承認OK」と判定した場合は除く(設定行為自体がユーザーの事前承認となる)
- retrospective / improvement-reviewer 自身の不変条件を変更する改善案は却下する

### スコープ
- 1回の改善で変更するファイルは1つだけ
- エージェント定義のfrontmatter(model, tools, permissionMode)は変更しない
- フック(.claude/hooks/*.py)のロジック変更は却下する(プロンプトの改善のみ許可)

### 研究データ保護

データ三原則(来歴管理の基盤):
- raw データは不可侵(書き込み不可が既定)。逸脱の検知: doctorマーカー `[DATA-RAW-WRITABLE]`
- 前処理は必ずスクリプトを通し、手動編集しない。処理結果が誤って書き込み不可すぎる場合の検知: doctorマーカー `[DATA-PROCESSED-READONLY]`
- DATA_LOG.md が来歴の唯一の真実である。台帳不在の検知: doctorマーカー `[DATA-LOG-MISSING]`

持ち出し規制:
- 外部に出してよいのは集計値・図・ハッシュのみ(生データそのものは出さない)。検知: Phase 2 の data_gate(予定)

## 変えてよいこと
- エージェント定義の本文(プロンプト部分)への追記・修正
- スキルの本文への追記・修正
- python-standards スキルへの規約追加
- CONTEXT.md.template への用語追加

## リソース上限(resources)

Planner はこの上限内に収まる計画だけを作る。超える場合は計画を分割するか、
ユーザーに上限の引き上げを相談する(勝手に超えない)。
plan_gate.py がこの値を読み、超過計画をブロックする。

```yaml
resources:
  max_train_minutes: 120     # 1回の学習ジョブの上限(分)
  max_epochs: 100
  max_dataset_gb: 10
  max_parallel_jobs: 1
```

## 人間の承認が必須の操作(HITL)

以下の操作は、自律度レベル(CLAUDE_CONTROL_LEVEL)に関わらず、
実行直前に必ずユーザーの承認を得る。承認の提示は3点のみ:
**実行内容・推定コスト(時間/計算資源)・不可逆かどうか**。

- 30分を超える学習ジョブの開始
- データセットの削除・上書き(permissions.deny でも機械的に防ぐ)
- invariants.md 自体の変更
- 外部への成果物公開(パッケージ公開、外部リポジトリへの push 等)
