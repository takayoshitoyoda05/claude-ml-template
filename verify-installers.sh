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

# 新しいサンドボックスを作り、パスを $SB に入れる。コマンド置換
# (d=$(make_sandbox))だとサブシェル実行になり SANDBOXES の更新が親に
# 反映されず cleanup が空振りするため、グローバル変数で返す
make_sandbox() {
  SB=$(mktemp -d /tmp/verify-installers.XXXXXX)
  SANDBOXES="$SANDBOXES $SB"
  place_installers "$SB"
}

MARKER="takayoshitoyoda05/claude-ml-template"

# 端末付きで実行しても init の任意機能質問に入らないよう既定値で固定する
# (機能セットアップ自体の検査は専用サンドボックスで env を上書きして行う)
export CLAUDE_TEMPLATE_FEATURES=none

# ============================================================
# claude-init.sh: 新規導入(フル展開)
# ============================================================
make_sandbox; A=$SB
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
for f in claude-remote.ps1 claude-update.ps1 doctor.ps1; do
  assert "init: ps1 版($f)は配置されない" test ! -e "$A/$f"
done
for e in ".claude/checkpoints/" ".claude/settings.local.json" "**/.claude/spec/" "/.worktrees/"; do
  assert "init: .gitignore に $e が追加される" grep -qF "$e" "$A/.gitignore"
done
assert_not "init: 既定では包括除外(.claude/)は追記されない" grep -qxF ".claude/" "$A/.gitignore"
assert "init: 任意機能は既定では無効のまま" grep -q '"CLAUDE_CROSS_REVIEW": "0"' "$A/.claude/settings.local.json"
assert "init: CLAUDE_REFUTE_PASS が雛形に含まれる(既定無効)" grep -q '"CLAUDE_REFUTE_PASS": "0"' "$A/.claude/settings.local.json"

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
make_sandbox; B=$SB
echo "CUSTOM_DOCTOR" > "$B/doctor.sh"
echo "# my own agents doc" > "$B/AGENTS.md"
echo "MY_CLAUDE_MD" > "$B/CLAUDE.md"
mkdir -p "$B/templates" "$B/.github/workflows"
echo "MY_TEMPLATE" > "$B/templates/ADR.md.template"
echo "MY_CI" > "$B/.github/workflows/spec-gate.yml"
# place_installers が置いたローカル参照版を旧テンプレート版に見立てて上書きし、
# マーカー付きファイルの上書き経路を検査する(B では update は実行しない)
printf '# 旧テンプレート版 %s\nOLD_VERSION\n' "$MARKER" > "$B/claude-update.sh"
printf '# 旧テンプレート版 %s\nOLD_PS1\n' "$MARKER" > "$B/claude-update.ps1"
(cd "$B" && bash claude-init.sh >init.log 2>&1)
assert "init(保持): 導入が exit 0 で完了" test "$?" -eq 0
assert "init(保持): 独自 doctor.sh(マーカー無し)が保持される" grep -q "CUSTOM_DOCTOR" "$B/doctor.sh"
assert "init(保持): doctor.sh 保持の警告が出る" grep -q "doctor.sh は独自ファイルのため保持しました" "$B/init.log"
assert "init(保持): 独自 AGENTS.md(マーカー無し)が保持される" grep -q "my own agents doc" "$B/AGENTS.md"
assert "init(保持): 既存 CLAUDE.md が保持される" grep -q "MY_CLAUDE_MD" "$B/CLAUDE.md"
assert "init(保持): 既存 templates/*.template が保持される" grep -q "MY_TEMPLATE" "$B/templates/ADR.md.template"
assert "init(保持): 既存 spec-gate.yml が保持される" grep -q "MY_CI" "$B/.github/workflows/spec-gate.yml"
assert_not "init(上書き): マーカー付き旧 claude-update.sh は上書きされる" grep -q "OLD_VERSION" "$B/claude-update.sh"
assert "init(上書き): 上書き後もテンプレート版マーカーを含む" grep -q "$MARKER" "$B/claude-update.sh"
assert "init(ps1): 既存の claude-update.ps1(マーカー付き)にも触らない" grep -q "OLD_PS1" "$B/claude-update.ps1"

# ============================================================
# claude-init.sh: symlink 対策
# ============================================================
make_sandbox; C=$SB
# リンク先にマーカーを持たせる(マーカー無しだと「独自ファイル保持」の判定が
# 先に効いてリンクごと保持されるため、置換経路のテストにならない)
printf '# %s\nVICTIM\n' "$MARKER" > "$C/victim.txt"
ln -s victim.txt "$C/doctor.sh"
mkdir -p "$C/target_dir"
rm -f "$C/claude-update.sh"
ln -s target_dir "$C/claude-update.sh"
mkdir -p "$C/claude-remote.sh"
(cd "$C" && bash claude-init.sh >init.log 2>&1)
assert "init(symlink): 導入が exit 0 で完了" test "$?" -eq 0
assert "init(symlink): ファイルへのリンクは実体ファイルに置き換わる" test -f "$C/doctor.sh" -a ! -L "$C/doctor.sh"
assert "init(symlink): リンク先のファイルは無傷" grep -q "VICTIM" "$C/victim.txt"
assert "init(symlink): ディレクトリへのリンクも除去して実体ファイルを配置" test -f "$C/claude-update.sh" -a ! -L "$C/claude-update.sh"
assert "init(symlink): リンク先ディレクトリの中に書き込まれない" test ! -e "$C/target_dir/claude-update.sh"
assert "init(symlink): 実ディレクトリはスキップして保持" test -d "$C/claude-remote.sh"
assert "init(symlink): ディレクトリスキップの警告が出る" grep -q "claude-remote.sh はディレクトリのため" "$C/init.log"

# ============================================================
# CLAUDE_TEMPLATE_GITIGNORE_ALL=1: テンプレート一式を導入先の git 管理外にする
# (既存 .gitignore は上書きせず追記のみ・冪等)
# ============================================================
make_sandbox; H=$SB
printf 'MY_IGNORE\n.claude/checkpoints/\n' > "$H/.gitignore"
(cd "$H" && CLAUDE_TEMPLATE_GITIGNORE_ALL=1 bash claude-init.sh >init.log 2>&1)
assert "init(ignore-all): 導入が exit 0 で完了" test "$?" -eq 0
assert "init(ignore-all): 既存 .gitignore の内容は保持される(追記のみ)" grep -qxF "MY_IGNORE" "$H/.gitignore"
for e in ".claude/" ".codex/" "agents/shared/" "templates/*.template" "AGENTS.md" "CLAUDE.md" \
         ".github/workflows/spec-gate.yml" "claude-update.sh" "doctor.ps1"; do
  assert "init(ignore-all): $e が .gitignore に追記される" grep -qxF "$e" "$H/.gitignore"
done
n=$(grep -cxF ".claude/checkpoints/" "$H/.gitignore")
if [ "$n" -eq 1 ]; then
  ok "init(ignore-all): 既存エントリは重複追加されない"
else
  ng "init(ignore-all): 既存エントリは重複追加されない(.claude/checkpoints/ が ${n}件)"
fi
# git が実際に無視するかを check-ignore で確認する
git -C "$H" init -q
assert "init(ignore-all): git が .claude/settings.json を無視する" git -C "$H" check-ignore -q .claude/settings.json
assert "init(ignore-all): git が CLAUDE.md を無視する" git -C "$H" check-ignore -q CLAUDE.md
# update も同じ集合を冪等に維持する
place_installers "$H"
(cd "$H" && CLAUDE_TEMPLATE_GITIGNORE_ALL=1 bash claude-update.sh >update.log 2>&1)
assert "update(ignore-all): 更新が exit 0 で完了" test "$?" -eq 0
n=$(grep -cxF ".claude/" "$H/.gitignore")
if [ "$n" -eq 1 ]; then
  ok "update(ignore-all): 包括除外エントリの追記は冪等(重複しない)"
else
  ng "update(ignore-all): 包括除外エントリの追記は冪等(.claude/ が ${n}件)"
fi

# ============================================================
# claude-init.sh: 任意機能の初期セットアップ(CLAUDE_TEMPLATE_FEATURES)
# ============================================================
make_sandbox; I=$SB
(cd "$I" && CLAUDE_TEMPLATE_FEATURES="CLAUDE_CROSS_REVIEW,CLAUDE_REFACTOR_SWARM,BOGUS_FLAG" \
  bash claude-init.sh >init.log 2>&1)
assert "init(features): 導入が exit 0 で完了" test "$?" -eq 0
assert "init(features): CLAUDE_CROSS_REVIEW が有効化される" grep -q '"CLAUDE_CROSS_REVIEW": "1"' "$I/.claude/settings.local.json"
assert "init(features): CLAUDE_REFACTOR_SWARM が有効化される" grep -q '"CLAUDE_REFACTOR_SWARM": "1"' "$I/.claude/settings.local.json"
assert "init(features): 指定しない機能は無効のまま" grep -q '"CLAUDE_QUALITY_GATE": "0"' "$I/.claude/settings.local.json"
assert "init(features): 不明なフラグは警告して無視する" grep -q "不明な機能フラグ BOGUS_FLAG" "$I/init.log"
if command -v python3 >/dev/null 2>&1; then
  assert "init(features): 書き換え後も妥当な JSON" python3 -c "import json; json.load(open('$I/.claude/settings.local.json'))"
else
  echo "SKIP: python3 が無いため JSON 妥当性の検査をスキップします"
fi

# 非対話環境(端末なし・CLAUDE_TEMPLATE_FEATURES 未指定)では既定値のまま進む
if command -v setsid >/dev/null 2>&1; then
  make_sandbox; J=$SB
  (cd "$J" && setsid -w env -u CLAUDE_TEMPLATE_FEATURES bash claude-init.sh </dev/null >init.log 2>&1)
  assert "init(features): 非対話では質問せず exit 0 で完了" test "$?" -eq 0
  assert "init(features): 非対話では既定値のまま" grep -q '"CLAUDE_CROSS_REVIEW": "0"' "$J/.claude/settings.local.json"
  assert "init(features): 既定値のままにした旨を表示する" grep -q "対話端末が無いため任意機能" "$J/init.log"
else
  echo "SKIP: setsid が無いため非対話の任意機能検査をスキップします"
fi

# ============================================================
# claude-update.sh: 前提チェックと更新・保持
# ============================================================
make_sandbox; E=$SB
(cd "$E" && bash claude-update.sh >update.log 2>&1)
rc=$?
if [ "$rc" -eq 1 ] && grep -q "claude-init.sh で初回展開" "$E/update.log"; then
  ok "update: .claude が無ければ中止する (exit 1)"
else
  ng "update: .claude が無ければ中止する (exit $rc)"
fi

make_sandbox; D=$SB
(cd "$D" && bash claude-init.sh >init.log 2>&1)
assert "update前提: init が exit 0 で完了" test "$?" -eq 0
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
# 過去に配置された ps1 版が残っているプロジェクトを想定(update は触らない)
printf '# 旧テンプレート版 %s\nOLD_PS1\n' "$MARKER" > "$D/doctor.ps1"
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
assert "update(ps1): 既存の doctor.ps1(マーカー付き)にも触らない" grep -q "OLD_PS1" "$D/doctor.ps1"
assert "update(ps1): ps1 版(claude-remote.ps1)は新たに配布されない" test ! -e "$D/claude-remote.ps1"
# 自己更新: 実行中の claude-update.sh 自身がテンプレート版に置き換わる
assert "update(自己更新): 実行中の claude-update.sh がテンプレート版に置き換わる" grep -q "https://github.com" "$D/claude-update.sh"
# .gitignore の冪等性: 2回目の update で重複追加されない
place_installers "$D"
(cd "$D" && bash claude-update.sh >update2.log 2>&1)
assert "update: 2回目の更新も exit 0 で完了" test "$?" -eq 0
n=$(grep -cF ".claude/checkpoints/" "$D/.gitignore")
if [ "$n" -eq 1 ]; then
  ok "update: .gitignore への追加は冪等(重複しない)"
else
  ng "update: .gitignore への追加は冪等(.claude/checkpoints/ が ${n}件)"
fi

# ============================================================
# claude-update.sh: symlink 対策
# ============================================================
make_sandbox; F=$SB
(cd "$F" && bash claude-init.sh >init.log 2>&1)
assert "update(symlink)前提: init が exit 0 で完了" test "$?" -eq 0
place_installers "$F"
printf '# %s\nVICTIM\n' "$MARKER" > "$F/victim.txt"
rm -f "$F/claude-remote.sh"
ln -s victim.txt "$F/claude-remote.sh"
mkdir -p "$F/target_dir"
rm -f "$F/doctor.sh"
ln -s target_dir "$F/doctor.sh"
(cd "$F" && bash claude-update.sh >update.log 2>&1)
assert "update(symlink): 更新が exit 0 で完了" test "$?" -eq 0
assert "update(symlink): ファイルへのリンクは実体ファイルに置き換わる" test -f "$F/claude-remote.sh" -a ! -L "$F/claude-remote.sh"
assert "update(symlink): リンク先のファイルは無傷" grep -q "VICTIM" "$F/victim.txt"
assert "update(symlink): ディレクトリへのリンクも除去して実体ファイルを配置" test -f "$F/doctor.sh" -a ! -L "$F/doctor.sh"
assert "update(symlink): リンク先ディレクトリの中に書き込まれない" test ! -e "$F/target_dir/doctor.sh"
# 実ディレクトリのスキップ(1回目の update で claude-remote.sh は実体ファイルに
# 戻っているため、ディレクトリに差し替えて2回目の update で検査する)
place_installers "$F"
rm -f "$F/claude-remote.sh"
mkdir -p "$F/claude-remote.sh"
(cd "$F" && bash claude-update.sh >update2.log 2>&1)
assert "update(symlink): 実ディレクトリ検査の更新が exit 0 で完了" test "$?" -eq 0
assert "update(symlink): 実ディレクトリはスキップして保持" test -d "$F/claude-remote.sh"
assert "update(symlink): ディレクトリスキップの警告が出る" grep -q "claude-remote.sh はディレクトリのため" "$F/update2.log"

echo ""
if [ "$failed" -eq 0 ]; then
  echo "全テストPASS"
else
  echo "${failed}件のテストが失敗しました"
  exit 1
fi
