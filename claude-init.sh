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
  # (/dev/tty)から受ける。まず端末の有無だけを静かに判定し(判定とreadを
  # 分けるのは、readにまとめて2>/dev/nullを付けるとプロンプト表示まで
  # 消えてしまうため)、端末が無い非対話環境では安全側に倒して中止する
  if { : < /dev/tty; } 2>/dev/null; then
    if read -r -p ".claude が既に存在します。上書きしますか? [y/N] " ans < /dev/tty; then
      [[ "$ans" =~ ^[Yy]$ ]] || { echo "中止しました"; exit 1; }
    else
      echo "入力が中断されたため中止しました"
      exit 1
    fi
  else
    echo ".claude が既に存在します。対話端末が無いため上書きせず中止しました"
    exit 1
  fi
fi

TMP=$(mktemp -d)
TMPF=""
trap 'rm -rf "$TMP"; [ -n "$TMPF" ] && rm -f "$TMPF"' EXIT
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

# .gitignore に除外エントリを追加(冪等。既存の .gitignore は上書きせず追記のみ)
IGNORE_ENTRIES=(".claude/checkpoints/" ".claude/settings.local.json" "**/.claude/spec/" "/.worktrees/")
# CLAUDE_TEMPLATE_GITIGNORE_ALL=1 なら、テンプレートが配布・生成する一式を
# 導入先の git 管理外にする(テンプレートのファイルをリポジトリに載せたくない場合)
if [ "${CLAUDE_TEMPLATE_GITIGNORE_ALL:-0}" = "1" ]; then
  IGNORE_ENTRIES+=(".claude/" ".codex/" "agents/shared/" "templates/*.template"
    "AGENTS.md" "CLAUDE.md" ".github/workflows/spec-gate.yml"
    "claude-update.sh" "claude-update.ps1" "claude-remote.sh" "claude-remote.ps1"
    "doctor.sh" "doctor.ps1")
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

# 任意機能(既定では無効)の一覧。「変数名|質問に添える説明」の形式
OPTIONAL_FEATURES=(
  "CLAUDE_CROSS_REVIEW|Codex クロスレビュー(要 Codex CLI。実装を別モデル視点で必須レビュー)"
  "CLAUDE_REFACTOR_SWARM|haiku スカウト隊(ml-pipeline のリファクタリング偵察を並列実行)"
  "CLAUDE_QUALITY_GATE|機械的品質ゲート(ruff / radon / mypy を停止時に強制)"
  "CLAUDE_DIFF_COVERAGE|変更行カバレッジゲート(pytest-cov + diff-cover。既定閾値80%、CLAUDE_DIFF_COVERAGE_MIN で変更可)"
  "CLAUDE_AUTO_APPROVE|計画の自動承認(plan-reviewer が安全な計画を人手なしで通す)"
  "CLAUDE_NOTIFY|完了時のデスクトップ通知"
  "CLAUDE_FINAL_GATE|マージ前の最終判定(final-gate)"
  "CLAUDE_SECURITY_SCAN|パイプライン実行内のセキュリティスキャン"
  "CLAUDE_REFUTE_PASS|レビュー指摘の反証濾過(HIGH 指摘を refuter が潰し、生き残った指摘だけ差し戻しに使う)"
  "CLAUDE_REQUIREMENTS_GATE|要件定義の機械ゲート(受け入れ条件テーブル付き設計書が無いままの計画作成をブロック)"
)

# settings.local.json の該当フラグを "1" に書き換える(sed -i は BSD/GNU で
# 挙動が違うため一時ファイル+mv で置き換える)
enable_feature() {
  local var="$1" tmpjson
  tmpjson=$(mktemp)
  sed "s|\"$var\": \"[^\"]*\"|\"$var\": \"1\"|" .claude/settings.local.json > "$tmpjson"
  mv "$tmpjson" .claude/settings.local.json
  if grep -q "\"$var\": \"1\"" .claude/settings.local.json; then
    echo "OK: $var=1 を設定しました"
  else
    echo "警告: $var を設定できませんでした(settings.local.json に項目がありません)"
  fi
  if [ "$var" = "CLAUDE_CROSS_REVIEW" ] && ! command -v codex >/dev/null 2>&1; then
    echo "警告: Codex CLI が見つかりません。クロスレビューには codex のインストールと codex login が必要です"
  fi
}

# フック用環境変数の雛形(既存なら保持)
if [ -f ".claude/settings.local.json" ]; then
  echo "OK: .claude/settings.local.json は既存のものを保持します"
else
  cp "$TMP/templates/settings.local.json.template" .claude/settings.local.json
  echo "OK: .claude/settings.local.json を生成しました(env の値を記入するとフックが有効になります)"
  # 任意機能の初期セットアップ(雛形を新規生成したときだけ)。優先順:
  #   1) CLAUDE_TEMPLATE_FEATURES(非対話用。"none" か、有効化するフラグ名の
  #      カンマ区切り。例: CLAUDE_TEMPLATE_FEATURES=CLAUDE_CROSS_REVIEW,CLAUDE_NOTIFY)
  #   2) 対話端末があれば1機能ずつ質問する(curl | bash でも /dev/tty から受ける)
  #   3) どちらも無い非対話環境では既定値(すべて無効)のまま進む
  if [ -n "${CLAUDE_TEMPLATE_FEATURES:-}" ]; then
    if [ "$CLAUDE_TEMPLATE_FEATURES" != "none" ]; then
      IFS=',' read -ra REQUESTED <<< "$CLAUDE_TEMPLATE_FEATURES"
      for req in "${REQUESTED[@]}"; do
        found=0
        for entry in "${OPTIONAL_FEATURES[@]}"; do
          if [ "$req" = "${entry%%|*}" ]; then
            enable_feature "$req"
            found=1
          fi
        done
        [ "$found" -eq 0 ] && echo "警告: 不明な機能フラグ $req は無視しました"
      done
    fi
  elif { : < /dev/tty; } 2>/dev/null; then
    echo ""
    echo "任意機能の初期セットアップを行います(後から .claude/settings.local.json で変更できます)"
    for entry in "${OPTIONAL_FEATURES[@]}"; do
      var="${entry%%|*}"
      desc="${entry#*|}"
      if read -r -p "  $desc を有効にしますか? [y/N] " ans < /dev/tty; then
        [[ "$ans" =~ ^[Yy]$ ]] && enable_feature "$var"
      else
        echo "情報: 入力が中断されたため残りの任意機能は既定(無効)のままにします"
        break
      fi
    done
  else
    echo "情報: 対話端末が無いため任意機能はすべて既定(無効)のままにしました"
  fi
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

# 運用スクリプト(claude-remote.sh / claude-update.sh / doctor.sh)を配置
# (この環境で使う sh 版のみ。Windows(PowerShell)へは claude-init.ps1 が
# ps1 版を配置するため、使わない側の形式は持ち込まない。
# テンプレート由来のファイルだけを上書きし、同名の独自ファイルは保持する。
# 配布元にマーカーが無いファイル(claude-remote.sh)は識別できないため従来どおり
# 常に上書き。claude- 接頭辞のため独自ファイルとの衝突リスクは低い)
MARKER="takayoshitoyoda05/claude-ml-template"
for f in claude-remote.sh claude-update.sh doctor.sh; do
  if [ -f "$TMP/$f" ]; then
    if grep -q "$MARKER" "$TMP/$f" && [ -f "$f" ] && ! grep -q "$MARKER" "$f"; then
      echo "警告: $f は独自ファイルのため保持しました(テンプレート版が必要なら $f を退避してから再実行してください)"
      continue
    fi
    # cp は既存の $f がシンボリックリンクだとリンク先に書き込んでしまう
    # (悪意あるリポジトリが仕込んだリンク経由で無関係なファイルを破壊しうる)。
    # mktemp + mv ならリンク自体が実体ファイルに置き換わり、リンク先は無傷で済む。
    # ただしディレクトリへのリンクだと mv はリンク先の中へ移動してしまうため、
    # リンクはリンク自体を除去し、実ディレクトリはスキップする
    [ -L "$f" ] && rm -f -- "$f"
    if [ -d "$f" ]; then
      echo "警告: $f はディレクトリのため配置をスキップしました"
      continue
    fi
    TMPF=$(mktemp "$f.XXXXXX")
    cp "$TMP/$f" "$TMPF"
    chmod 644 "$TMPF"
    mv "$TMPF" "$f"
    TMPF=""
    echo "OK: $f を配置しました"
    case "$f" in
      *.sh) chmod +x "$f" 2>/dev/null || true ;;
    esac
  else
    echo "警告: 配布元に $f が見つかりません(コピーされませんでした)"
  fi
done

if [ -f CLAUDE.md ]; then
  echo "OK: CLAUDE.md は既存のものを保持します"
else
  cp "$TMP/templates/CLAUDE.md.template" CLAUDE.md
  echo "OK: CLAUDE.md を生成しました"
fi

echo ""
echo "完了。claude を起動してサブエージェントが認識されているか確認できます"
