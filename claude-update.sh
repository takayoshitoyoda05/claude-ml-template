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
TMPF=""
trap 'rm -rf "$TMP"; [ -n "$TMPF" ] && rm -f "$TMPF"' EXIT
echo "最新テンプレートを取得中..."
git clone --depth 1 --quiet "$TEMPLATE_REPO" "$TMP"

# 更新対象: agents / commands / hooks / skills / output-styles / rules / settings.json
# plans/ と CLAUDE.md はプロジェクト固有・実行履歴なので触らない
for item in agents commands hooks skills output-styles rules; do
  if [ -d "$TMP/.claude/$item" ]; then
    cp -r "$TMP/.claude/$item" .claude/
    echo "OK: .claude/$item を更新しました"
  fi
done

# agents/shared/ を更新(配布元にあるファイルだけを個別に上書きし、ユーザー独自のファイルは残す)
SHARED_SRC="$TMP/agents/shared"
if [ -d "$SHARED_SRC" ]; then
  mkdir -p agents/shared
  for f in "$SHARED_SRC"/*; do
    [ -f "$f" ] && cp "$f" agents/shared/
  done
  echo "OK: agents/shared/ を更新しました"
fi

# agents/shared/ から AGENTS.md を生成(Codex CLI 用。自動生成マーカーの無い
# 既存 AGENTS.md はプロジェクト独自のファイルとみなして保持する)
if [ -d "agents/shared" ]; then
  if [ -f AGENTS.md ] && ! grep -q '<!-- claude-ml-template' AGENTS.md; then
    echo "警告: AGENTS.md は独自ファイルのため保持しました(自動生成版に切り替えるには AGENTS.md を退避してから再実行してください)"
  else
    {
      echo "# AGENTS.md"
      echo ""
      echo "<!-- claude-ml-template により自動生成。編集は agents/shared/ で行い claude-update で再生成 -->"
      echo ""
      for f in agents/shared/*.md; do
        [ -f "$f" ] && cat "$f" && echo ""
      done
    } > AGENTS.md
    echo "OK: AGENTS.md を生成しました(Codex CLI 用)"
  fi
fi

# スキルを .codex/skills/ にもコピー(Codex CLI 用。配布元にあるスキルディレクトリだけを
# 個別に上書きし、ユーザー独自のスキルは残す)
SKILLS_SRC="$TMP/.claude/skills"
if [ -d "$SKILLS_SRC" ]; then
  mkdir -p .codex/skills
  for d in "$SKILLS_SRC"/*/; do
    [ -d "$d" ] || continue
    name=$(basename "$d")
    rm -rf ".codex/skills/$name"
    cp -r "$d" ".codex/skills/$name"
  done
  echo "OK: .codex/skills/ にスキルをコピーしました"
fi

# .codex/config.toml がなければテンプレートからコピー
CODEX_TEMPLATE="$TMP/templates/codex-config.toml.template"
if [ ! -f ".codex/config.toml" ] && [ -f "$CODEX_TEMPLATE" ]; then
  mkdir -p .codex
  cp "$CODEX_TEMPLATE" .codex/config.toml
  echo "OK: .codex/config.toml を生成しました"
fi

if [ -f "$TMP/.claude/settings.json" ]; then
  cp "$TMP/.claude/settings.json" .claude/settings.json
  echo "OK: .claude/settings.json を更新しました"
  # .gitignore に除外エントリを追加(冪等。既存の .gitignore は上書きせず追記のみ)
  IGNORE_ENTRIES=(".claude/checkpoints/" ".claude/settings.local.json" "**/.claude/spec/")
  # CLAUDE_TEMPLATE_GITIGNORE_ALL=1 なら、テンプレートが配布・生成する一式を
  # 導入先の git 管理外にする(テンプレートのファイルをリポジトリに載せたくない場合)
  if [ "${CLAUDE_TEMPLATE_GITIGNORE_ALL:-0}" = "1" ]; then
    IGNORE_ENTRIES+=(".claude/" ".codex/" "agents/shared/" "templates/*.template"
      "AGENTS.md" "CLAUDE.md" ".github/workflows/spec-gate.yml"
      "claude-update.sh" "claude-update.ps1" "claude-remote.sh" "claude-remote.ps1"
      "doctor.sh" "doctor.ps1"
      "scripts/_data_patterns.py" "scripts/data_lock.py" "scripts/data_dictionary.py"
      "scripts/export_check.py" "scripts/data_scan.py" "scripts/precommit_data_check.py"
      "scripts/history_scan.py" "scripts/env_fingerprint.py" "scripts/githooks/pre-commit")
  fi
  for IGNORE_ENTRY in "${IGNORE_ENTRIES[@]}"; do
    if [ ! -f ".gitignore" ]; then
      echo "$IGNORE_ENTRY" > .gitignore
      echo "OK: .gitignore を作成しました($IGNORE_ENTRY)"
    else
      # 行全体の一致で判定する(部分一致だと .claude/checkpoints/ の存在だけで
      # .claude/ が「既にある」と誤判定されて追記されない)
      if ! grep -qxF "$IGNORE_ENTRY" .gitignore; then
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

# 参照専用テンプレ(templates/*.template)を配布(既存ファイルは保持)
mkdir -p templates
for f in "$TMP"/templates/*.template; do
  [ -f "$f" ] || continue
  name=$(basename "$f")
  if [ -f "templates/$name" ]; then
    echo "OK: templates/$name は既存のものを保持します"
  else
    cp "$f" "templates/$name"
    echo "OK: templates/$name を配布しました"
  fi
done

# GitHub Actions ワークフロー(spec-gate)の配置(既存なら保持)
if [ -f ".github/workflows/spec-gate.yml" ]; then
  echo "OK: .github/workflows/spec-gate.yml は既存のものを保持します"
else
  mkdir -p .github/workflows
  cp "$TMP/templates/spec-gate.yml.template" .github/workflows/spec-gate.yml
  echo "OK: .github/workflows/spec-gate.yml を配置しました"
fi

# 運用スクリプト(claude-remote.sh / claude-update.sh / doctor.sh)を配布
# (この環境で使う sh 版のみ。Windows(PowerShell)へは claude-update.ps1 が
# ps1 版を配布するため、使わない側の形式は持ち込まない。
# テンプレート由来のファイルだけを上書きし、同名の独自ファイルは保持する。
# 配布元にマーカーが無いファイル(claude-remote.sh)は識別できないため従来どおり
# 常に上書き。claude- 接頭辞のため独自ファイルとの衝突リスクは低い)
# claude-update.sh は実行中の自分自身も更新対象になる。bash はスクリプトを
# 逐次読みするため cp で同じ inode に直接書くと実行中の本体が壊れる。
# 一時ファイルに書いてから mv で差し替えれば、実行中の bash は旧 inode を
# 読み続けるので安全
MARKER="takayoshitoyoda05/claude-ml-template"
for f in claude-remote.sh claude-update.sh doctor.sh; do
  if [ -f "$TMP/$f" ]; then
    if grep -q "$MARKER" "$TMP/$f" && [ -f "$f" ] && ! grep -q "$MARKER" "$f"; then
      echo "警告: $f は独自ファイルのため保持しました(テンプレート版が必要なら $f を退避してから再実行してください)"
      continue
    fi
    # ディレクトリへのリンクだと mv がリンク先の中へ移動してしまうため、
    # リンクはリンク自体を除去し、実ディレクトリはスキップする
    [ -L "$f" ] && rm -f -- "$f"
    if [ -d "$f" ]; then
      echo "警告: $f はディレクトリのため更新をスキップしました"
      continue
    fi
    # 固定名だと同名のユーザーファイルやシンボリックリンクを壊すため mktemp で一意にする
    TMPF=$(mktemp "$f.XXXXXX")
    cp "$TMP/$f" "$TMPF"
    chmod 644 "$TMPF"
    mv "$TMPF" "$f"
    TMPF=""
    echo "OK: $f を更新しました"
    case "$f" in
      *.sh) chmod +x "$f" 2>/dev/null || true ;;
    esac
  else
    echo "警告: 配布元に $f が見つかりません(コピーされませんでした)"
  fi
done

# Phase 2 データ保護スクリプト(scripts/ 配下)を更新。
# ディレクトリごとコピーすると DATA_LOG 雛形が参照する scripts/preprocess.py の
# ようなユーザー資産を壊すため、個別ファイル名を列挙する。上の運用スクリプトと
# 同じ MARKER 保護方式(配布元にマーカーがあり、ローカル同名ファイルに無ければ
# ユーザー自身のファイルとみなして上書きしない)。
mkdir -p scripts
SCRIPTS_FILES=(
  _data_patterns.py
  data_lock.py
  data_dictionary.py
  export_check.py
  data_scan.py
  precommit_data_check.py
  history_scan.py
  env_fingerprint.py
  githooks/pre-commit
)
for f in "${SCRIPTS_FILES[@]}"; do
  if [ -f "$TMP/scripts/$f" ]; then
    if grep -q "$MARKER" "$TMP/scripts/$f" && [ -f "scripts/$f" ] && ! grep -q "$MARKER" "scripts/$f"; then
      echo "警告: scripts/$f は独自ファイルのため保持しました(テンプレート版が必要なら scripts/$f を退避してから再実行してください)"
      continue
    fi
    [ -L "scripts/$f" ] && rm -f -- "scripts/$f"
    if [ -d "scripts/$f" ]; then
      echo "警告: scripts/$f はディレクトリのため更新をスキップしました"
      continue
    fi
    mkdir -p "scripts/$(dirname "$f")"
    TMPF=$(mktemp "scripts/$f.XXXXXX")
    cp "$TMP/scripts/$f" "$TMPF"
    chmod 644 "$TMPF"
    mv "$TMPF" "scripts/$f"
    TMPF=""
    echo "OK: scripts/$f を更新しました"
    case "$f" in
      githooks/pre-commit) chmod +x "scripts/$f" 2>/dev/null || true ;;
    esac
  else
    echo "警告: 配布元に scripts/$f が見つかりません(コピーされませんでした)"
  fi
done

echo ""
echo "更新完了(.claude/plans/ と CLAUDE.md は変更されていません)"
