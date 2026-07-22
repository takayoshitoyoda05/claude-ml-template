#!/bin/bash
set -uo pipefail

for tool in uv git; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "エラー: '$tool' が見つかりません。"
    exit 1
  fi
done

if [ ! -d ".claude" ]; then
  echo "エラー: .claude が見つかりません。claude-init で展開してから使ってください。"
  exit 1
fi

TEMPLATE_REPO="https://github.com/takayoshitoyoda05/claude-ml-template.git"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "最新テンプレートを取得中..."
git clone --depth 1 --quiet "$TEMPLATE_REPO" "$TMP"

diff_count=0
for item in agents commands hooks skills output-styles rules; do
  local_dir=".claude/$item"
  remote_dir="$TMP/.claude/$item"
  [ -d "$remote_dir" ] || continue

  while IFS= read -r -d '' rf; do
    rel_path="${rf#$remote_dir/}"
    local_file="$local_dir/$rel_path"
    if [ ! -f "$local_file" ]; then
      echo "NEW: $item/$rel_path (テンプレートにあるがローカルに無い)"
      diff_count=$((diff_count+1))
      continue
    fi
    if ! diff -q "$rf" "$local_file" >/dev/null 2>&1; then
      echo "DIFF: $item/$rel_path (内容が異なる)"
      diff_count=$((diff_count+1))
    fi
  done < <(find "$remote_dir" -type f -print0)
done

# agents/shared/(リポジトリ直下。Codex CLI 共有指示の配布元)も比較する
if [ -d "$TMP/agents/shared" ]; then
  while IFS= read -r -d '' rf; do
    rel_path="${rf#$TMP/agents/shared/}"
    local_file="agents/shared/$rel_path"
    if [ ! -f "$local_file" ]; then
      echo "NEW: agents/shared/$rel_path (テンプレートにあるがローカルに無い)"
      diff_count=$((diff_count+1))
      continue
    fi
    if ! diff -q "$rf" "$local_file" >/dev/null 2>&1; then
      echo "DIFF: agents/shared/$rel_path (内容が異なる)"
      diff_count=$((diff_count+1))
    fi
  done < <(find "$TMP/agents/shared" -type f -print0)
fi

if [ -f ".claude/settings.json" ] && [ -f "$TMP/.claude/settings.json" ]; then
  if ! diff -q ".claude/settings.json" "$TMP/.claude/settings.json" >/dev/null 2>&1; then
    echo "DIFF: settings.json (内容が異なる)"
    diff_count=$((diff_count+1))
  fi
fi

echo ""
if [ "$diff_count" -eq 0 ]; then
  echo "最新です。差分はありません。"
else
  echo "$diff_count 件の差分があります。claude-update の実行を検討してください。"
fi
