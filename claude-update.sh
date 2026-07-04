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
  # .gitignore に除外エントリを追加(冪等)
  for IGNORE_ENTRY in ".claude/checkpoints/" ".claude/settings.local.json" ".claude/spec/"; do
    if [ ! -f ".gitignore" ]; then
      echo "$IGNORE_ENTRY" > .gitignore
      echo "OK: .gitignore を作成しました($IGNORE_ENTRY)"
    else
      if ! grep -qF "$IGNORE_ENTRY" .gitignore; then
        printf "\n%s\n" "$IGNORE_ENTRY" >> .gitignore
        echo "OK: .gitignore に $IGNORE_ENTRY を追加しました"
      else
        echo "OK: .gitignore は既に設定済みです($IGNORE_ENTRY)"
      fi
    fi
  done
fi

# フック用環境変数の雛形(既存なら保持)
if [ -f ".claude/settings.local.json" ]; then
  echo "OK: .claude/settings.local.json は既存のものを保持します"
else
  cp "$TMP/templates/settings.local.json.template" .claude/settings.local.json
  echo "OK: .claude/settings.local.json を生成しました(env の値を記入するとフックが有効になります)"
fi

# GitHub Actions ワークフロー(spec-gate)の配置(既存なら保持)
if [ -f ".github/workflows/spec-gate.yml" ]; then
  echo "OK: .github/workflows/spec-gate.yml は既存のものを保持します"
else
  mkdir -p .github/workflows
  cp "$TMP/templates/spec-gate.yml.template" .github/workflows/spec-gate.yml
  echo "OK: .github/workflows/spec-gate.yml を配置しました"
fi

echo ""
echo "更新完了(.claude/plans/ と CLAUDE.md は変更されていません)"
