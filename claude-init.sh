#!/bin/bash
set -euo pipefail

for tool in uv git; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "エラー: '$tool' が見つかりません。インストールしてから再実行してください。"
    exit 1
  fi
done

TEMPLATE_REPO="https://github.com/takayoshitoyoda05/claude-ml-template.git"

if [ -d ".claude" ]; then
  read -p ".claude が既に存在します。上書きしますか? [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]] || { echo "中止しました"; exit 1; }
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
echo "テンプレートを取得中..."
git clone --depth 1 --quiet "$TEMPLATE_REPO" "$TMP"

cp -r "$TMP/.claude" ./
echo "OK: .claude/ を展開しました"

# .gitignore に .claude/checkpoints/ を追加(冪等)
IGNORE_ENTRY=".claude/checkpoints/"
if [ ! -f ".gitignore" ]; then
  echo "$IGNORE_ENTRY" > .gitignore
  echo "OK: .gitignore を作成しました"
else
  if ! grep -qF "$IGNORE_ENTRY" .gitignore; then
    printf "\n%s\n" "$IGNORE_ENTRY" >> .gitignore
    echo "OK: .gitignore に $IGNORE_ENTRY を追加しました"
  else
    echo "OK: .gitignore は既に設定済みです"
  fi
fi

if [ -f CLAUDE.md ]; then
  echo "OK: CLAUDE.md は既存のものを保持します"
else
  INIT_DATE=$(date +%Y-%m-%d)
  sed -e "s|{{INIT_DATE}}|$INIT_DATE|g" \
      "$TMP/templates/CLAUDE.md.template" > CLAUDE.md
  echo "OK: CLAUDE.md を生成しました"
fi

echo ""
echo "完了。claude を起動してサブエージェントが認識されているか確認できます"
