# Changelog

このプロジェクトの主な変更点を記録する。形式は [Keep a Changelog](https://keepachangelog.com/) に緩く準拠。

## [Unreleased]
### Added
- regression-suite スキル: 実装後に影響範囲を広くカバーするテストを任意生成
- config-explain スキル: スコープ・評価強制設定の可視化
- GitHub Actions CI: push/PR時に verify-hooks を自動実行
- LICENSE(MIT)
- doctor.ps1 / doctor.sh: テンプレートとの差分検知(sync-check)
- examples/toy-project: パイプラインお試し用のサンプルプロジェクト

## 過去の主な変更(遡及記録)
- Planner / Generator / Evaluator の3分離パターンを構築
- evaluator を Spec軸(evaluator) / Standards軸(evaluator-standards) に分割
- スコープ制約とフック(guard_scope, guard_bash)による物理ガードを導入
- design-interview, brainstorm, diagnosing-bugs, tdd, adr, handoff,
  architecture-check の各スキルを追加
- 秘密情報ガード、実験ログ自動記録、Golden Baseline、Explore事前調査を追加
- CONTEXT.md によるドメイン用語共有を導入
- コンテキスト圧縮対策(checkpoint_before_compact, reinject_after_compact)を追加
- claude-update による差分反映、.gitignore自動設定を追加
