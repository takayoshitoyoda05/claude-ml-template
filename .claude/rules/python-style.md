---
description: Pythonファイルのコーディング規約。.pyファイルを編集するときに自動適用される。
paths:
  - "**/*.py"
---

## Python コーディング規約

- パッケージ管理: uv
- テスト: pytest (`uv run python -m pytest tests/ -q`)
- 公開する関数・メソッドには型ヒントを必ず付ける
- Python 3.10+ の型構文(`list[str]`, `X | None`)を使う
- docstring は Google スタイル。公開する関数・クラスに必ず付ける
- import の順序: 標準ライブラリ → サードパーティ → プロジェクト内(ruff に任せる)
- コメントには「なぜ(why)」を書く。「何をしているか(what)」はコードに書かない
- 既存のロジック説明コメントを勝手に削除しない
