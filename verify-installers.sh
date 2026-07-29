#!/bin/bash
# インストーラ(claude-init.sh / claude-update.sh)の保護動作の回帰テスト。
# 対象: 独自ファイルの保持・テンプレート由来ファイルの上書き・symlink 対策・
# 自己更新の安全性。verify-hooks.sh と同じ OK/NG 形式で報告する。
#
# ネットワークには出ない: このリポジトリの HEAD を file:// でローカル clone して
# テンプレート取得を再現する(配布ペイロードは HEAD、インストーラ本体は作業
# ツリー版をテストする)。インストーラ自体は書き換えず、TEMPLATE_REPO を
# 差し替えたコピーをサンドボックスに置いて実行する。
#
# .ps1 版はこの環境(pwsh 無し)では実行できないため対象外。
# Windows での実機確認(README 4.6節)で担保する。
set -u

ROOT="$(cd "$(dirname "$0")" && pwd)"
failed=0

ok() { echo "OK: $1"; }
ng() { echo "NG: $1"; failed=$((failed+1)); }
assert() {
  # assert <説明> <コマンド...>  — コマンドが成功すれば OK
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then ok "$desc"; else ng "$desc"; fi
}
assert_not() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then ng "$desc"; else ok "$desc"; fi
}

SANDBOXES=""
cleanup() {
  for d in $SANDBOXES; do rm -rf "$d"; done
}
trap cleanup EXIT

# TEMPLATE_REPO をローカル参照に差し替えたインストーラのコピーを dir に置く
place_installers() {
  local dir="$1" f
  for f in claude-init.sh claude-update.sh; do
    sed "s|^TEMPLATE_REPO=.*|TEMPLATE_REPO=\"file://$ROOT\"|" "$ROOT/$f" > "$dir/$f"
    if ! grep -q "file://$ROOT" "$dir/$f"; then
      echo "FATAL: $f の TEMPLATE_REPO 差し替えに失敗しました(行の形式が変わった可能性)"
      exit 1
    fi
    chmod +x "$dir/$f"
  done
}

make_sandbox() {
  local d
  d=$(mktemp -d /tmp/verify-installers.XXXXXX)
  SANDBOXES="$SANDBOXES $d"
  place_installers "$d"
  echo "$d"
}

MARKER="takayoshitoyoda05/claude-ml-template"

# ============================================================
# claude-init.sh: 新規導入(フル展開)
# ============================================================
A=$(make_sandbox)
(cd "$A" && bash claude-init.sh >init.log 2>&1)
assert "init: 新規導入が exit 0 で完了" test "$?" -eq 0
assert "init: .claude/agents が展開される" test -f "$A/.claude/agents/planner.md"
assert "init: .claude/hooks が展開される" test -f "$A/.claude/hooks/guard_scope.py"
assert "init: settings.json が配置される" test -f "$A/.claude/settings.json"
assert "init: settings.local.json 雛形が生成される" test -f "$A/.claude/settings.local.json"
assert "init: AGENTS.md がマーカー付きで生成される" grep -q '<!-- claude-ml-template' "$A/AGENTS.md"
assert "init: .codex/skills にスキルがコピーされる" test -d "$A/.codex/skills/brainstorm"
assert "init: .codex/config.toml が生成される" test -f "$A/.codex/config.toml"
assert "init: templates/ が配布される" test -f "$A/templates/design-doc.md.template"
assert "init: spec-gate.yml が配置される" test -f "$A/.github/workflows/spec-gate.yml"
assert "init: CLAUDE.md が生成される" test -f "$A/CLAUDE.md"
assert "init: claude-update.sh が配布される" grep -q "$MARKER" "$A/claude-update.sh"
assert "init: doctor.sh が配布される" grep -q "$MARKER" "$A/doctor.sh"
assert "init: 配布された claude-update.sh に実行権限がある" test -x "$A/claude-update.sh"
for e in ".claude/checkpoints/" ".claude/settings.local.json" "**/.claude/spec/" "/.worktrees/"; do
  assert "init: .gitignore に $e が追加される" grep -qF "$e" "$A/.gitignore"
done

# 再実行(非対話): 端末が無ければ上書きせず中止する
if command -v setsid >/dev/null 2>&1; then
  (cd "$A" && setsid -w bash claude-init.sh </dev/null >reinit.log 2>&1)
  rc=$?
  if [ "$rc" -eq 1 ] && grep -q "上書きせず中止しました" "$A/reinit.log"; then
    ok "init: .claude 既存時、非対話環境では中止する (exit 1)"
  else
    ng "init: .claude 既存時、非対話環境では中止する (exit $rc)"
  fi
else
  echo "SKIP: setsid が無いため非対話中止の検査をスキップします"
fi

# ============================================================
# claude-init.sh: 独自ファイルの保持
# ============================================================
B=$(make_sandbox)
echo "CUSTOM_DOCTOR" > "$B/doctor.sh"
echo "# my own agents doc" > "$B/AGENTS.md"
echo "MY_CLAUDE_MD" > "$B/CLAUDE.md"
mkdir -p "$B/templates" "$B/.github/workflows"
echo "MY_TEMPLATE" > "$B/templates/ADR.md.template"
echo "MY_CI" > "$B/.github/workflows/spec-gate.yml"
printf '# 旧テンプレート版 %s\nOLD_VERSION\n' "$MARKER" > "$B/claude-update.ps1"
(cd "$B" && bash claude-init.sh >init.log 2>&1)
assert "init(保持): 独自 doctor.sh(マーカー無し)が保持される" grep -q "CUSTOM_DOCTOR" "$B/doctor.sh"
assert "init(保持): doctor.sh 保持の警告が出る" grep -q "doctor.sh は独自ファイルのため保持しました" "$B/init.log"
assert "init(保持): 独自 AGENTS.md(マーカー無し)が保持される" grep -q "my own agents doc" "$B/AGENTS.md"
assert "init(保持): 既存 CLAUDE.md が保持される" grep -q "MY_CLAUDE_MD" "$B/CLAUDE.md"
assert "init(保持): 既存 templates/*.template が保持される" grep -q "MY_TEMPLATE" "$B/templates/ADR.md.template"
assert "init(保持): 既存 spec-gate.yml が保持される" grep -q "MY_CI" "$B/.github/workflows/spec-gate.yml"
assert_not "init(上書き): マーカー付き旧 claude-update.ps1 は上書きされる" grep -q "OLD_VERSION" "$B/claude-update.ps1"
assert "init(上書き): 上書き後もテンプレート版マーカーを含む" grep -q "$MARKER" "$B/claude-update.ps1"

# ============================================================
# claude-init.sh: symlink 対策
# ============================================================
C=$(make_sandbox)
# リンク先にマーカーを持たせる(マーカー無しだと「独自ファイル保持」の判定が
# 先に効いてリンクごと保持されるため、置換経路のテストにならない)
printf '# %s\nVICTIM\n' "$MARKER" > "$C/victim.txt"
ln -s victim.txt "$C/doctor.sh"
mkdir -p "$C/target_dir"
ln -s target_dir "$C/doctor.ps1"
mkdir -p "$C/claude-remote.sh"
(cd "$C" && bash claude-init.sh >init.log 2>&1)
assert "init(symlink): ファイルへのリンクは実体ファイルに置き換わる" test -f "$C/doctor.sh" -a ! -L "$C/doctor.sh"
assert "init(symlink): リンク先のファイルは無傷" grep -q "VICTIM" "$C/victim.txt"
assert "init(symlink): ディレクトリへのリンクも除去して実体ファイルを配置" test -f "$C/doctor.ps1" -a ! -L "$C/doctor.ps1"
assert "init(symlink): リンク先ディレクトリの中に書き込まれない" test ! -e "$C/target_dir/doctor.ps1"
assert "init(symlink): 実ディレクトリはスキップして保持" test -d "$C/claude-remote.sh"
assert "init(symlink): ディレクトリスキップの警告が出る" grep -q "claude-remote.sh はディレクトリのため" "$C/init.log"

# ============================================================
# claude-update.sh: 前提チェックと更新・保持
# ============================================================
E=$(make_sandbox)
(cd "$E" && bash claude-update.sh >update.log 2>&1)
rc=$?
if [ "$rc" -eq 1 ] && grep -q "claude-init.sh で初回展開" "$E/update.log"; then
  ok "update: .claude が無ければ中止する (exit 1)"
else
  ng "update: .claude が無ければ中止する (exit $rc)"
fi

D=$(make_sandbox)
(cd "$D" && bash claude-init.sh >init.log 2>&1)
# init が claude-update.sh をテンプレート版(GitHub参照)で上書きするため、
# テスト用のローカル参照版を再配置してから update を検査する
place_installers "$D"
echo "BROKEN_HOOK" > "$D/.claude/hooks/guard_scope.py"
mkdir -p "$D/.claude/plans"
echo "MY_PLAN" > "$D/.claude/plans/20260729-test.md"
echo "MY_CLAUDE_MD" > "$D/CLAUDE.md"
echo "MY_LOCAL_SETTINGS" > "$D/.claude/settings.local.json"
mkdir -p "$D/.codex/skills/my-own-skill"
echo "MY_SKILL" > "$D/.codex/skills/my-own-skill/SKILL.md"
echo "BROKEN_SKILL" > "$D/.codex/skills/brainstorm/SKILL.md"
echo "MY_SHARED" > "$D/agents/shared/my-rules.md"
echo "BROKEN_SHARED" > "$D/agents/shared/coding-rules.md"
printf '# AGENTS.md\n<!-- claude-ml-template -->\nSTALE_CONTENT\n' > "$D/AGENTS.md"
echo "CUSTOM_DOCTOR" > "$D/doctor.sh"
(cd "$D" && bash claude-update.sh >update.log 2>&1)
assert "update: 更新が exit 0 で完了" test "$?" -eq 0
assert_not "update: .claude/hooks がテンプレート版に更新される" grep -q "BROKEN_HOOK" "$D/.claude/hooks/guard_scope.py"
assert "update(保持): .claude/plans/ は触らない" grep -q "MY_PLAN" "$D/.claude/plans/20260729-test.md"
assert "update(保持): CLAUDE.md は触らない" grep -q "MY_CLAUDE_MD" "$D/CLAUDE.md"
assert "update(保持): settings.local.json は保持される" grep -q "MY_LOCAL_SETTINGS" "$D/.claude/settings.local.json"
assert "update(保持): .codex/skills のユーザー独自スキルは残る" grep -q "MY_SKILL" "$D/.codex/skills/my-own-skill/SKILL.md"
assert_not "update: .codex/skills のテンプレート由来スキルは更新される" grep -q "BROKEN_SKILL" "$D/.codex/skills/brainstorm/SKILL.md"
assert "update(保持): agents/shared のユーザー独自ファイルは残る" grep -q "MY_SHARED" "$D/agents/shared/my-rules.md"
assert_not "update: agents/shared の配布ファイルは更新される" grep -q "BROKEN_SHARED" "$D/agents/shared/coding-rules.md"
assert_not "update: マーカー付き AGENTS.md は再生成される" grep -q "STALE_CONTENT" "$D/AGENTS.md"
assert "update(保持): 独自 doctor.sh(マーカー無し)が保持される" grep -q "CUSTOM_DOCTOR" "$D/doctor.sh"
assert "update(保持): doctor.sh 保持の警告が出る" grep -q "doctor.sh は独自ファイルのため保持しました" "$D/update.log"
# 自己更新: 実行中の claude-update.sh 自身がテンプレート版に置き換わる
assert "update(自己更新): 実行中の claude-update.sh がテンプレート版に置き換わる" grep -q "https://github.com" "$D/claude-update.sh"
# .gitignore の冪等性: 2回目の update で重複追加されない
place_installers "$D"
(cd "$D" && bash claude-update.sh >update2.log 2>&1)
n=$(grep -cF ".claude/checkpoints/" "$D/.gitignore")
if [ "$n" -eq 1 ]; then
  ok "update: .gitignore への追加は冪等(重複しない)"
else
  ng "update: .gitignore への追加は冪等(.claude/checkpoints/ が ${n}件)"
fi

# ============================================================
# claude-update.sh: symlink 対策
# ============================================================
F=$(make_sandbox)
(cd "$F" && bash claude-init.sh >init.log 2>&1)
place_installers "$F"
printf '# %s\nVICTIM\n' "$MARKER" > "$F/victim.txt"
rm -f "$F/claude-remote.sh"
ln -s victim.txt "$F/claude-remote.sh"
mkdir -p "$F/target_dir"
rm -f "$F/claude-remote.ps1"
ln -s target_dir "$F/claude-remote.ps1"
rm -f "$F/doctor.ps1"
mkdir -p "$F/doctor.ps1"
(cd "$F" && bash claude-update.sh >update.log 2>&1)
assert "update(symlink): ファイルへのリンクは実体ファイルに置き換わる" test -f "$F/claude-remote.sh" -a ! -L "$F/claude-remote.sh"
assert "update(symlink): リンク先のファイルは無傷" grep -q "VICTIM" "$F/victim.txt"
assert "update(symlink): ディレクトリへのリンクも除去して実体ファイルを配置" test -f "$F/claude-remote.ps1" -a ! -L "$F/claude-remote.ps1"
assert "update(symlink): リンク先ディレクトリの中に書き込まれない" test ! -e "$F/target_dir/claude-remote.ps1"
assert "update(symlink): 実ディレクトリはスキップして保持" test -d "$F/doctor.ps1"
assert "update(symlink): ディレクトリスキップの警告が出る" grep -q "doctor.ps1 はディレクトリのため" "$F/update.log"

echo ""
if [ "$failed" -eq 0 ]; then
  echo "全テストPASS"
else
  echo "${failed}件のテストが失敗しました"
  exit 1
fi
