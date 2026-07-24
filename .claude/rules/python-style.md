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
- 実行スクリプト(train / eval / 実験系)には print でなく logging を使う。
  logging.basicConfig の出力先は**コンソールのみ**とする(ファイルへの永続化は
  実行側の tee(logs/runs/)が一元的に担う — 二重ログを避ける責務分離。
  修正 2026-07-24)。
  進捗・ハイパーパラメータ・環境情報(seed, デバイス)は必ずログに残す
