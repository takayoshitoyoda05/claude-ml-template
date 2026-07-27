#!/bin/bash
set -euo pipefail

NAME="${1:-$(basename "$PWD")}"

# tmux はセッション起動時のコマンドを1本の文字列に連結してシェル経由で実行する
# ため、名前にメタ文字が含まれるとそのまま解釈される。名前は引数指定が無ければ
# カレントディレクトリ名から来るので、意図せず危険な文字が混じりうる。
# 安全な文字だけに正規化する(`.` と `:` は tmux のセッション/ウィンドウ指定で
# 特別な意味を持つので併せて除く)。
# PowerShell 版は tmux を介さず claude を直接起動し、引数も配列で渡るため
# この正規化は不要(sh 側だけの対処でよい)。
SAFE_NAME=$(printf '%s' "$NAME" | tr -c 'A-Za-z0-9_-' '_')
if [ "$SAFE_NAME" != "$NAME" ]; then
  # 置換後の名前だけを表示する。元の名前をそのまま出すと、改行や端末制御文字を
  # 含むディレクトリ名で表示が壊れる(端末側への注入経路になる)
  # 別々の名前が同じ結果に潰れる(`a.b` と `a:b` など)と、既存セッションの
  # 判定で別プロジェクトに誤接続しうるので、元の名前のハッシュを添える。
  # sha256 を優先し(cksum の CRC32 は衝突を作れる)、環境に無ければ POSIX の
  # cksum に落とす
  if command -v sha256sum >/dev/null 2>&1; then
    NAME_HASH=$(printf '%s' "$NAME" | sha256sum | cut -c1-12)
  elif command -v shasum >/dev/null 2>&1; then
    NAME_HASH=$(printf '%s' "$NAME" | shasum -a 256 | cut -c1-12)
  else
    NAME_HASH=$(printf '%s' "$NAME" | cksum | cut -d' ' -f1)
  fi
  NAME="${SAFE_NAME}_${NAME_HASH}"
  echo "情報: セッション名に使えない文字があったため '$NAME' を使います。"
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "エラー: claude コマンドが見つかりません。"
  exit 1
fi

echo "=== リモート運用の起動チェック ==="

# 状態ディレクトリの優先順: XDG_STATE_HOME > $HOME/.local/state > 決定不能(空)
if [ -n "${XDG_STATE_HOME:-}" ]; then
  NOTICE_STATE_DIR="$XDG_STATE_HOME"
elif [ -n "${HOME:-}" ]; then
  NOTICE_STATE_DIR="$HOME/.local/state"
else
  NOTICE_STATE_DIR=""
fi
NOTICE_MARKER="${NOTICE_STATE_DIR:+$NOTICE_STATE_DIR/claude-remote/notice-shown}"
if [ -n "$NOTICE_MARKER" ] && [ -f "$NOTICE_MARKER" ]; then
  echo "ヒント: 初回のみ必要な設定(/config →「Enable Remote Control for all sessions」)がまだなら実施してください。"
else
  echo ""
  echo "初回のみ必要な設定:"
  echo "  claude 起動後に /config を実行し、"
  echo "  「Enable Remote Control for all sessions」を true にしてください。"
  echo "  (この設定はマシン単位。1度設定すれば以降は不要です)"
  echo ""
  if [ -n "$NOTICE_MARKER" ]; then
    # ベストエフォート: 失敗しても起動は継続する
    mkdir -p "$(dirname "$NOTICE_MARKER")" 2>/dev/null && touch "$NOTICE_MARKER" 2>/dev/null || true
  fi
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
