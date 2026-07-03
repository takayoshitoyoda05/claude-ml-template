#!/bin/bash
set -euo pipefail

for tool in uv git; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "エラー: '$tool' が見つかりません。インストールしてから再実行してください。"
    exit 1
  fi
done

TEMPLATE_REPO="https://github.com/takayoshitoyoda05/claude-ml-template.git"

if [ ! -d ".claude" ]; then
  echo "エラー: .claude が見つかりません。先に claude-init.sh で初回展開してください。"
  exit 1
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
echo "最新テンプレートを取得中..."
git clone --depth 1 --quiet "$TEMPLATE_REPO" "$TMP"

# 更新対象: agents / commands / hooks / settings.json
# plans/ と CLAUDE.md はプロジェクト固有・実行履歴なので触らない
for item in agents commands hooks skills; do
  if [ -d "$TMP/.claude/$item" ]; then
    cp -r "$TMP/.claude/$item" .claude/
    echo "OK: .claude/$item を更新しました"
  fi
done

if [ -f "$TMP/.claude/settings.json" ]; then
  cp "$TMP/.claude/settings.json" .claude/settings.json
  echo "OK: .claude/settings.json を更新しました"
fi

echo ""
echo "更新完了(.claude/plans/ と CLAUDE.md は変更されていません)"
