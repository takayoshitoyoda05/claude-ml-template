# CONTEXT.md — このリポジトリの用語集

claude-ml-template 自体の開発で繰り返し使う用語。実装詳細ではなく概念のみ載せる。

## 用語一覧

| 用語 | 意味 |
|---|---|
| spec-compliance | 設計書適合チェックの仕組み全体の呼称(A:要件ID化 + B:フック強制 + C:テスト還元 + D:独立監査) |
| 受け入れ条件テーブル | 設計書の「## 受け入れ条件」に置く必須テーブル。ID / 要件 / 検証方法 / 期待結果 / 種別(auto・manual) / 対象 の6列 |
| spec_gate | Stop フック。CLAUDE_SPEC_CHECK=1 のとき全要件の達成を機械検査し、欠けがあれば完了をブロックする |
| verdict ファイル | evaluator が出力する要件IDごとの判定(.claude/spec/verdict-*.md) |
| audit ファイル | spec-auditor が出力する証拠検証+スコープ外変更の監査結果(.claude/spec/audit-*.md) |
| approvals.txt | manual要件の人間承認記録(.claude/spec/approvals.txt)。保護パスで Claude は書き込めず、ユーザーが spec_approve.py で追記する |
| 保護パス | ガードの自己書き換え防止のため Claude 経由の書き込みを禁止するパス群(_common.py の PROTECTED_PATH_PATTERNS) |
| スコープ外変更 | 設計書に記載がないのに実装された変更。spec-auditor が diff との突き合わせで検出する |
