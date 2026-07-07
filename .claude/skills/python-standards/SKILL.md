---
name: python-standards
description: このプロジェクトのPythonコーディング規約(パッケージ管理・テスト・型ヒント等)を確認・適用したいとき、または新しいPythonファイルを作成するとき、evaluator-standardsがレビューの基準を確認するときに参照する。
---

# Python プロジェクト標準

プロジェクト全体で統一するPythonの規約。CONTEXT.md(ドメイン用語)とは別に、
コーディング規約をここに固定する。

## パッケージ管理
- パッケージマネージャ: uv
- Python バージョン: 3.12
- 依存の追加: `uv add <パッケージ>` (pyproject.toml に記録される)
- 開発用依存: `uv add --dev <パッケージ>`

## テスト
- フレームワーク: pytest
- 実行: `uv run python -m pytest tests/ -q`
- fixture を活用し、テスト間でデータを共有する場合は conftest.py に置く
- カバレッジ目標: 特に定めないが、公開する関数には最低1テストを書く

## 型ヒント
- 公開する関数・メソッドには型ヒントを必ず付ける
- 内部のヘルパー関数は省略可
- `Any` の使用は最小限に。使う場合はコメントで理由を添える
- Python 3.10+ の型構文(`list[str]`, `X | None`)を使う。
  `typing.List`, `typing.Optional` は使わない

## docstring
- スタイル: Google スタイル
- 公開する関数・クラスには必ず付ける。Args / Returns / Raises を書く
- 内部のヘルパーは1行docstringで可

## フォーマット / リント
- ruff format + ruff check(設定は pyproject.toml に記載)
- auto_format.py フックで .py 編集後に自動実行される

## import の順序
- 標準ライブラリ → サードパーティ → プロジェクト内
- ruff の isort 互換ルールに任せる(手動で並べ替えない)

## このスキルの使い方
- Generator がコードを書くとき: この規約に沿っているか自己チェックする
- evaluator-standards がレビューするとき: この規約を基準に判定する
- 新しいプロジェクトで規約を変えたい場合: このファイルをコピーして
  プロジェクト直下に置き、内容を編集する
