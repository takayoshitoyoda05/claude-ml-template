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
- Planner の計画はユーザー承認なしに実装に進めない
- retrospective / improvement-reviewer 自身の不変条件を変更する改善案は却下する

### スコープ
- 1回の改善で変更するファイルは1つだけ
- エージェント定義のfrontmatter(model, tools, permissionMode)は変更しない
- フック(.claude/hooks/*.py)のロジック変更は却下する(プロンプトの改善のみ許可)

## 変えてよいこと
- エージェント定義の本文(プロンプト部分)への追記・修正
- スキルの本文への追記・修正
- python-standards スキルへの規約追加
- CONTEXT.md.template への用語追加
