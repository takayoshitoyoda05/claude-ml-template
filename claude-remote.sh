#!/bin/bash
set -euo pipefail

NAME="${1:-$(basename "$PWD")}"

if ! command -v claude >/dev/null 2>&1; then
  echo "エラー: claude コマンドが見つかりません。"
  exit 1
fi

echo "=== リモート運用の起動チェック ==="

NOTICE_MARKER="${XDG_STATE_HOME:-$HOME/.local/state}/claude-remote/notice-shown"
if [ -f "$NOTICE_MARKER" ]; then
  echo "ヒント: 初回のみ必要な設定(/config →「Enable Remote Control for all sessions」)がまだなら実施してください。"
else
  echo ""
  echo "初回のみ必要な設定:"
  echo "  claude 起動後に /config を実行し、"
  echo "  「Enable Remote Control for all sessions」を true にしてください。"
  echo "  (この設定はマシン単位。1度設定すれば以降は不要です)"
  echo ""
  mkdir -p "$(dirname "$NOTICE_MARKER")" 2>/dev/null && touch "$NOTICE_MARKER" 2>/dev/null || true
fi

if command -v tmux >/dev/null 2>&1; then
  SESSION="claude-${NAME}"
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "既存の tmux セッション '$SESSION' に接続します。"
    exec tmux attach -t "$SESSION"
  fi
  echo "=== tmux セッション '$SESSION' で起動します ==="
  echo "離脱: Ctrl-b を押してから d(ターミナルを閉じてもセッションは継続)"
  echo "復帰: tmux attach -t $SESSION"
  echo ""
  exec tmux new -s "$SESSION" claude remote-control --name "$NAME"
else
  echo "情報: tmux が見つかりません。ターミナルを閉じるとセッションが終了します。"
  echo "      継続させたい場合: sudo apt install tmux"
  echo ""
  echo "=== Claude Code を起動します(セッション名: $NAME) ==="
  exec claude remote-control --name "$NAME"
fi
