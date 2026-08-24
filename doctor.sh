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

# scripts/(リポジトリ直下。個別ファイル配布のためこの for item ループには
# 足さない。.claude/$item を前提とする既存ループに "scripts" を足すと
# .claude/scripts が無く continue で無言の no-op になるため、別ブロックにする)
if [ -d "$TMP/scripts" ]; then
  while IFS= read -r -d '' rf; do
    rel_path="${rf#$TMP/scripts/}"
    local_file="scripts/$rel_path"
    if [ ! -f "$local_file" ]; then
      echo "NEW: scripts/$rel_path (テンプレートにあるがローカルに無い)"
      diff_count=$((diff_count+1))
      continue
    fi
    if ! diff -q "$rf" "$local_file" >/dev/null 2>&1; then
      echo "DIFF: scripts/$rel_path (内容が異なる)"
      diff_count=$((diff_count+1))
    fi
  done < <(find "$TMP/scripts" -type f -print0)
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

  # [DATA-LOCK-MISMATCH] data/data.lock と実データの照合。
  # scripts/data_lock.py --check を呼ぶのが単一実装として望ましいが、この worktree
  # には group-B の scripts/data_lock.py が無いため、doctor 内で同じJSONスキーマ
  # (algorithm/files[].sha256/files[].size)を簡易照合する(計画Step8許容)。
  if [ -f "data/data.lock" ]; then
    lock_mismatch=1
    if uv run python - <<'PY' >/dev/null 2>&1
import hashlib
import json
import os
import sys

try:
    with open("data/data.lock", encoding="utf-8") as f:
        payload = json.load(f)
    mismatch = False
    for rel, info in payload.get("files", {}).items():
        path = os.path.join("data", rel)
        if not os.path.isfile(path):
            mismatch = True
            break
        with open(path, "rb") as fh:
            content = fh.read()
        if hashlib.sha256(content).hexdigest() != info.get("sha256") or len(content) != info.get("size"):
            mismatch = True
            break
    sys.exit(1 if mismatch else 0)
except Exception:
    sys.exit(1)
PY
    then
      lock_mismatch=0
    fi
    if [ "$lock_mismatch" -ne 0 ]; then
      echo "警告: [DATA-LOCK-MISMATCH] data/data.lock と実データが一致しません。scripts/data_lock.py --update で更新してください。"
    fi
  fi

  # [DATA-BACKUP-UNKNOWN] / [DATA-BACKUP-STALE] data/.backup_stamp(YYYY-MM-DD 1行)
  if [ -f "data/.backup_stamp" ]; then
    stamp=$(head -n1 "data/.backup_stamp" | tr -d '[:space:]')
    stamp_epoch=""
    if echo "$stamp" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
      stamp_epoch=$(date -d "$stamp" +%s 2>/dev/null)
    fi
    if [ -z "$stamp_epoch" ]; then
      echo "警告: [DATA-BACKUP-UNKNOWN] data/.backup_stamp の日付を解釈できません。YYYY-MM-DD 形式で記録してください。"
    else
      now_epoch=$(date +%s)
      age_days=$(( (now_epoch - stamp_epoch) / 86400 ))
      if [ "$age_days" -gt 30 ]; then
        echo "警告: [DATA-BACKUP-STALE] data/.backup_stamp が30日を超えています(${age_days}日前)。バックアップを取り直して更新してください。"
      fi
    fi
  else
    echo "警告: [DATA-BACKUP-UNKNOWN] data/.backup_stamp がありません。バックアップ実施日を記録してください。"
  fi

  # [DATA-PRECOMMIT-OFF] git hooks が scripts/githooks 経由で有効化されているか
  hooks_path=$(git config --get core.hooksPath 2>/dev/null)
  if [ "$hooks_path" != "scripts/githooks" ]; then
    echo "警告: [DATA-PRECOMMIT-OFF] core.hooksPath が scripts/githooks に設定されていません。git config core.hooksPath scripts/githooks で有効化してください。"
  fi

  # [DATA-KEY-RECIPIENTS-MISSING] .claude/backup_recipients.txt が無い、または鍵が2未満
  recipients_file=".claude/backup_recipients.txt"
  if [ ! -f "$recipients_file" ]; then
    echo "警告: [DATA-KEY-RECIPIENTS-MISSING] .claude/backup_recipients.txt がありません。バックアップ暗号化の受信者公開鍵を2件以上登録してください。"
  else
    key_count=$(grep -c . "$recipients_file" 2>/dev/null || echo 0)
    if [ "${key_count:-0}" -lt 2 ]; then
      echo "警告: [DATA-KEY-RECIPIENTS-MISSING] .claude/backup_recipients.txt の鍵が2件未満です(${key_count}件)。受信者公開鍵を2件以上登録してください。"
    fi
  fi

  # [DATA-AGE-MISSING] age(暗号化ツール)が未導入
  if ! command -v age >/dev/null 2>&1; then
    echo "警告: [DATA-AGE-MISSING] age が見つかりません。バックアップ暗号化には age の導入が必要です。"
  fi

  # [DATA-PROFILE-UNSET] data/DATA_LOG.md にデータ行があるのにプロファイル実効が無効
  if [ -f "data/DATA_LOG.md" ]; then
    has_data_row=0
    if uv run python - <<'PY' >/dev/null 2>&1
import re
import sys

text = open("data/DATA_LOG.md", encoding="utf-8").read()
row_re = re.compile(r"^\|(.+)\|\s*$")
sep_re = re.compile(r"^[\s|:-]+$")
rows = []
header_seen = False
for line in text.splitlines():
    m = row_re.match(line)
    if not m:
        continue
    if sep_re.match(m.group(1)):
        continue
    if not header_seen:
        header_seen = True
        continue
    rows.append(m.group(1))
sys.exit(0 if rows else 1)
PY
    then
      has_data_row=1
    fi

    # プロファイル実効判定(個別変数が非空かつ"0"以外なら優先、空ならプロファイルに委ねる)
    no_read_effective=0
    gate_effective=0
    if [ -n "${CLAUDE_DATA_NO_READ:-}" ] && [ "${CLAUDE_DATA_NO_READ:-}" != "0" ]; then
      no_read_effective=1
    elif [ -z "${CLAUDE_DATA_NO_READ:-}" ] && [ "${CLAUDE_DATA_PROFILE:-}" = "sensitive" ]; then
      no_read_effective=1
    fi
    if [ -n "${CLAUDE_DATA_GATE:-}" ] && [ "${CLAUDE_DATA_GATE:-}" != "0" ]; then
      gate_effective=1
    elif [ -z "${CLAUDE_DATA_GATE:-}" ] && { [ "${CLAUDE_DATA_PROFILE:-}" = "sensitive" ] || [ "${CLAUDE_DATA_PROFILE:-}" = "internal" ]; }; then
      gate_effective=1
    fi

    if [ "$has_data_row" -eq 1 ] && [ "$no_read_effective" -eq 0 ] && [ "$gate_effective" -eq 0 ]; then
      echo "警告: [DATA-PROFILE-UNSET] data/DATA_LOG.md にデータがありますが、CLAUDE_DATA_PROFILE 等の保護が無効です。機密度に応じて CLAUDE_DATA_PROFILE を設定してください。"
    fi
  fi
fi
