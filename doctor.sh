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

echo ""
echo "=== リモート運用(Remote Control)==="

if command -v claude >/dev/null 2>&1; then
  CLAUDE_VER=$(claude --version 2>/dev/null | head -1 | grep -oE '^[0-9]+\.[0-9]+\.[0-9]+')
  if [ -n "$CLAUDE_VER" ]; then
    # sort -V は GNU coreutils 拡張で macOS/BSD の sort には無いため、POSIX awk で比較する
    if awk -v a="$CLAUDE_VER" -v b="2.1.51" 'BEGIN{split(a,x,".");split(b,y,".");for(i=1;i<=3;i++){if((x[i]+0)>(y[i]+0))exit 0;if((x[i]+0)<(y[i]+0))exit 1}exit 0}'; then
      echo "OK: claude $CLAUDE_VER (Remote Control 対応、v2.1.51 以降で利用可)"
    else
      echo "警告: claude $CLAUDE_VER は古いバージョンです。Remote Control は v2.1.51 以降が必要です"
    fi
  else
    echo "情報: claude のバージョンを取得できませんでした(Remote Control は v2.1.51 以降で利用可)"
  fi
else
  echo "情報: claude コマンドが見つかりません(Remote Control は v2.1.51 以降で利用可)"
fi

if [ -f "claude-remote.sh" ]; then
  echo "OK: claude-remote.sh があります(./claude-remote.sh で起動)"
else
  echo "情報: claude-remote.sh がありません。claude-update で取得できます。"
fi

if command -v tmux >/dev/null 2>&1; then
  echo "OK: tmux があります(ターミナルを閉じてもセッション継続可)"
else
  echo "情報: tmux がありません(sudo apt install tmux で導入可)"
fi

echo "確認: /config の「Enable Remote Control for all sessions」が true か"
echo "      (マシン単位の設定。未設定なら毎回 /remote-control が必要です)"

echo ""
echo "=== データ保護(Data Protection)==="

if [ -d "data" ]; then
  if [ -d "data/raw" ] && [ -w "data/raw" ]; then
    echo "警告: [DATA-RAW-WRITABLE] data/raw が書き込み可能です。chmod -w data/raw を検討してください。"
  fi
  if [ -d "data/processed" ] && [ ! -w "data/processed" ]; then
    echo "警告: [DATA-PROCESSED-READONLY] data/processed が書き込み不可です。再生成できない場合は権限を確認してください。"
  fi
  if [ ! -f "data/DATA_LOG.md" ]; then
    echo "警告: [DATA-LOG-MISSING] data/DATA_LOG.md がありません。templates/DATA_LOG.md.template から作成してください。"
  fi
else
  : # data/ が無いプロジェクトでは何も出力しない
fi
