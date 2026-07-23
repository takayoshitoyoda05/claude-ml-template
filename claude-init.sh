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
  # curl | bash 実行時は stdin がスクリプト本文のため、確認入力は必ず端末
  # (/dev/tty)から受ける。端末が無い(CI等の非対話)場合は安全側に倒して中止する
  if read -r -p ".claude が既に存在します。上書きしますか? [y/N] " ans 2>/dev/null < /dev/tty; then
    [[ "$ans" =~ ^[Yy]$ ]] || { echo "中止しました"; exit 1; }
  else
    echo ".claude が既に存在します。対話端末が無いため上書きせず中止しました"
    exit 1
  fi
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
echo "テンプレートを取得中..."
git clone --depth 1 --quiet "$TEMPLATE_REPO" "$TMP"

# plans/ はプロジェクト固有・実行履歴なので展開しない(claude-update.shと同じ対象)
mkdir -p .claude
for item in agents commands hooks skills output-styles rules; do
  if [ -d "$TMP/.claude/$item" ]; then
    cp -r "$TMP/.claude/$item" .claude/
  fi
done
cp "$TMP/.claude/settings.json" .claude/settings.json
echo "OK: .claude/ を展開しました"

# agents/shared/ を配置(配布元にあるファイルを個別にコピー。claude-update.sh と同じ方式)
SHARED_SRC="$TMP/agents/shared"
if [ -d "$SHARED_SRC" ]; then
  mkdir -p agents/shared
  for f in "$SHARED_SRC"/*; do
    [ -f "$f" ] && cp "$f" agents/shared/
  done
  echo "OK: agents/shared/ を配置しました"
fi

# agents/shared/ から AGENTS.md を生成(Codex CLI 用)
if [ -d "agents/shared" ]; then
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

# .gitignore に除外エントリを追加(冪等)
for IGNORE_ENTRY in ".claude/checkpoints/" ".claude/settings.local.json" "**/.claude/spec/" "/.worktrees/"; do
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

if [ -f CLAUDE.md ]; then
  echo "OK: CLAUDE.md は既存のものを保持します"
else
  cp "$TMP/templates/CLAUDE.md.template" CLAUDE.md
  echo "OK: CLAUDE.md を生成しました"
fi

echo ""
echo "完了。claude を起動してサブエージェントが認識されているか確認できます"
