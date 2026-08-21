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

## 合成データとログ出力
- テストは合成データのみを使う。`data/raw` 等の実データをテストの入力・fixture に含めない
- ログ・標準出力には shape / hash / 統計量のみを書き、個票(レコード単位の生の値)を
  print しない(データの静かな漏洩を防ぐ)

## 型ヒント
- 公開する関数・メソッドには型ヒントを必ず付ける
- 内部のヘルパー関数は省略可
- `Any` の使用は最小限に。使う場合はコメントで理由を添える
- Python 3.10+ の型構文(`list[str]`, `X | None`)を使う。
  `typing.List`, `typing.Optional` は使わない

## テンソルの shape/dtype 注釈(ML コードのみ)
- 動機: mypy は `Tensor` の中身(次元・dtype)を検査できないため、
  shape/dtype の食い違いは型チェックを素通りする。
- 対象: テンソルを受け渡す**公開関数**(モデルの forward、collate_fn、
  前処理、損失、評価指標)。
- 手段1: jaxtyping の注釈(`Float[Tensor, "batch instance dim"]` のように
  dtype(`Float` 等)と次元名まで書き、次元名は関数をまたいで一貫させ
  CONTEXT.md の用語に合わせる)。
  導入は `uv add --dev jaxtyping beartype`。**実行時検査はテスト実行時にだけ
  有効化し**、有効化の具体的な記述は jaxtyping の公式ドキュメントに従う
  (conftest.py に置き、本番実行のオーバーヘッドを増やさない)。
- 手段2(依存を増やせない場合の代替): docstring に Shape/dtype 節(入力・出力の
  次元・dtype)を書き、テストで `assert x.shape == (...)` と dtype の assert を
  1つ以上置く。
- どちらも無いテンソル受け渡し関数は evaluator-standards の「型安全性」で
  指摘対象になる。
- **注意**: このテンプレート本体に対象コードは無い。この節は導入先
  プロジェクト向けの規約である。

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
