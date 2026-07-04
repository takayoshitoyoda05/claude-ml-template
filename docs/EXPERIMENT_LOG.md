# EXPERIMENT_LOG

## 2026-07-04 実装計画: 設計書適合チェック(spec-compliance)
- 計画: .claude/plans/20260704-spec-compliance.md
- 変更内容: 設計書の受け入れ条件テーブルを唯一の要件ソースとし、Stop フック(spec_gate/spec_approve、
  spec_staging/ に完成形。適用はユーザー手動)・spec-auditor エージェント・CI(spec-gate.yml)・
  各エージェント/スキル/配置スクリプトへの組み込みを追加。フェーズ5(保護パスへの適用)は未実施。
- 指標の変化: verify-hooks.sh/.ps1 既存23ケース PASS(変化なし、回帰なし) → spec-compliance
  フィクスチャ(R-101〜R-105, R-107, R-108, R-112)全PASS(spec_staging を一時ディレクトリにコピーして検証、
  実運用は phase5 適用後に有効化)
