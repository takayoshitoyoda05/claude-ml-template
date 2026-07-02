#!/bin/bash
set -euo pipefail

TEMPLATE_REPO="https://github.com/<あなたのユーザー名>/claude-ml-template.git"

if [ -d ".claude" ]; then
  read -p ".claude が既に存在します。上書きしますか? [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]] || { echo "中止しました"; exit 1; }
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
echo "テンプレートを取得中..."
git clone --depth 1 --quiet "$TEMPLATE_REPO" "$TMP"

cp -r "$TMP/.claude" ./
echo "✓ .claude/ を展開しました"

if [ -f CLAUDE.md ]; then
  echo "✓ CLAUDE.md は既存のものを保持します"
else
  PROJECT_NAME=$(basename "$PWD")
  read -p "評価スクリプトの実行コマンド [uv run python -m src.eval.eval]: " EVAL_CMD
  EVAL_CMD=${EVAL_CMD:-"uv run python -m src.eval.eval"}
  read -p "主要モデル定義の場所 [src/models/]: " MODEL_PATH
  MODEL_PATH=${MODEL_PATH:-"src/models/"}
  INIT_DATE=$(date +%Y-%m-%d)

  sed -e "s|{{PROJECT_NAME}}|$PROJECT_NAME|g" \
      -e "s|{{EVAL_CMD}}|$EVAL_CMD|g" \
      -e "s|{{MODEL_PATH}}|$MODEL_PATH|g" \
      -e "s|{{INIT_DATE}}|$INIT_DATE|g" \
      "$TMP/templates/CLAUDE.md.template" > CLAUDE.md
  echo "✓ CLAUDE.md を生成しました"
fi

echo ""
echo "完了！ claude を起動して /agents で確認できます"
