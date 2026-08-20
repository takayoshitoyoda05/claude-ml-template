# 調査スコープ

```yaml
テーマ: AI駆動開発パイプラインの「計画」と「レビュー」を堅牢化する手法の網羅的サーベイ
必須キーワード: [LLM agent planning, LLM code review, plan verification, LLM-as-judge,
  multi-agent debate, spec-driven development, test oracle, self-consistency,
  agentic coding pipeline]
除外条件: |
  既にこのテンプレートに存在する仕組み、および 2026-08-04 の会話で提案済みの
  以下7案と実質同一のもの:
  1. 仮定の機械検証(計画の未確認仮定に検証コマンドを義務付けて実行)
  2. 計画プレモーテム(独立コンテキストでの敵対的計画レビュー)
  3. diff カバレッジゲート(+変更ファイル限定ミューテーションゲート)
  4. ベースライン比較実行(分岐元とブランチで同一テストを実行し差分判定)
  5. feedback.md の頻出失敗パターンをレビュー指示に自動注入
  6. 複数 planner の独立生成+judge panel
  7. 並列グループの teammate 相互レビュー(アイデア帳 C-14 既出)
  既存機構: spec-checklist / plan-reviewer / plan_gate / cross-review(Codex) /
  evaluator×2 / spec-auditor / final-gate / security scan / retrospective ループ /
  scouts / property-test / mutation-test / regression-suite / leakage-check / pre-mortem
期間: 2022年以降を中心(古典的手法でも AI パイプラインへの転用が新しければ採用)
目的: 手法の比較検討(/ml-pipeline の計画・レビュー段への追加候補の発掘。
  学術文献に限定せず、業界プラクティス・OSS エージェントの実装パターンも対象)
```

調査方法: arXiv MCP 未接続のため WebSearch を使用。4領域
(計画の堅牢化 / レビューの堅牢化 / 検証・テストオラクル / 業界プラクティス)に
分けて並列調査し、search-log.md にクエリを記録する。
