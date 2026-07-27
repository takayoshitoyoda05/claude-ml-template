#!/bin/bash
set -u
failed=0

# 各テストはスコープ=リポジトリルートを前提に期待値を組むため、外部セッションの
# CLAUDE_WORK_SCOPE(別プロジェクト等)に影響されないようスクリプト全体で固定する
if [ "${CLAUDE_WORK_SCOPE+set}" = "set" ]; then
  _saved_work_scope="$CLAUDE_WORK_SCOPE"
  _had_work_scope=1
else
  _had_work_scope=0
fi
export CLAUDE_WORK_SCOPE="$(pwd)"
restore_work_scope() {
  if [ "$_had_work_scope" -eq 1 ]; then
    export CLAUDE_WORK_SCOPE="$_saved_work_scope"
  else
    unset CLAUDE_WORK_SCOPE
  fi
}
trap restore_work_scope EXIT

test_hook() {
  local description="$1"
  local json_input="$2"
  local script="$3"
  local expected_exit="$4"

  echo "$json_input" | uv run python "$script" >/dev/null 2>&1
  local actual=$?
  if [ "$actual" -eq "$expected_exit" ]; then
    echo "OK: $description (exit $actual)"
  else
    echo "NG: $description (expected $expected_exit, got $actual)"
    failed=$((failed+1))
  fi
}

# ブロック時の stderr メッセージに期待文字列が含まれるかを、exit code と
# 同一実行で検査する。data/ ブロックに「フック/設定への書き込み」と表示して
# いた誤メッセージの回帰防止(exit code だけでは検出できない。メッセージ
# だけの検査では「期待文字列を出すが exit 0 で許可する」実装を見逃す)
test_hook_msg() {
  local description="$1"
  local json_input="$2"
  local script="$3"
  local pattern="$4"
  local expected_exit="$5"

  local msg actual
  msg=$(echo "$json_input" | uv run python "$script" 2>&1 >/dev/null)
  actual=$?
  if [ "$actual" -eq "$expected_exit" ] && echo "$msg" | grep -q "$pattern"; then
    echo "OK: $description (exit $actual)"
  else
    echo "NG: $description (expected exit $expected_exit + message '$pattern', got exit $actual)"
    failed=$((failed+1))
  fi
}

test_hook "guard_scope: .pth is blocked" '{"tool_input":{"file_path":"model.pth"}}' ".claude/hooks/guard_scope.py" 2
test_hook "guard_scope: .py passes" '{"tool_input":{"file_path":"src/train.py"}}' ".claude/hooks/guard_scope.py" 0
test_hook "guard_scope: .env is blocked" '{"tool_input":{"file_path":".env"}}' ".claude/hooks/guard_scope.py" 2
test_hook "guard_scope: secret content is blocked" '{"tool_input":{"file_path":"config.py","content":"KEY=sk-abcdefghijklmnopqrstuvwxyz"}}' ".claude/hooks/guard_scope.py" 2
test_hook "guard_scope: hook self-edit is blocked" '{"tool_input":{"file_path":".claude/hooks/guard_bash.py","new_string":"pass"}}' ".claude/hooks/guard_scope.py" 2
test_hook "guard_scope: settings.local.json is blocked" '{"tool_input":{"file_path":".claude/settings.local.json","content":"{}"}}' ".claude/hooks/guard_scope.py" 2
test_hook "guard_scope: notebook in outputs/ is blocked" '{"tool_input":{"notebook_path":"outputs/nb.ipynb"}}' ".claude/hooks/guard_scope.py" 2
test_hook "guard_bash: rm -rf / is blocked" '{"tool_input":{"command":"rm -rf /"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: rm -fr / is blocked" '{"tool_input":{"command":"rm -fr /"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: rm -r -f ~/data is blocked" '{"tool_input":{"command":"rm -r -f ~/data"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: rm -rf build/ passes" '{"tool_input":{"command":"rm -rf build/"}}' ".claude/hooks/guard_bash.py" 0
test_hook "guard_bash: git push +ref is blocked" '{"tool_input":{"command":"git push origin +main"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: ls -la passes" '{"tool_input":{"command":"ls -la"}}' ".claude/hooks/guard_bash.py" 0
test_hook "guard_bash: git add .env is blocked" '{"tool_input":{"command":"git add .env"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: git add . is blocked" '{"tool_input":{"command":"git add ."}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: git add -A is blocked" '{"tool_input":{"command":"git add -A"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: git add foo.key.md passes" '{"tool_input":{"command":"git add foo.key.md"}}' ".claude/hooks/guard_bash.py" 0
test_hook "guard_bash: redirect to settings.json is blocked" '{"tool_input":{"command":"echo x > .claude/settings.json"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: tee to hooks is blocked" '{"tool_input":{"command":"echo x | tee .claude/hooks/guard_bash.py"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: redirect to .env is blocked" '{"tool_input":{"command":"echo KEY=x > .env"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: redirect to /dev/null passes" '{"tool_input":{"command":"pytest -q > /dev/null 2>&1"}}' ".claude/hooks/guard_bash.py" 0
test_hook "guard_bash: commit without digit passes when rule off" '{"tool_input":{"command":"git commit -m \"fix typo\""}}' ".claude/hooks/guard_bash.py" 0
test_hook "guard_bash: cp overwrite hook is blocked" '{"tool_input":{"command":"cp evil.py .claude/hooks/guard_scope.py"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: rm hook (non -rf) is blocked" '{"tool_input":{"command":"rm .claude/hooks/guard_bash.py"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: >| redirect to settings is blocked" '{"tool_input":{"command":"echo x >| .claude/settings.json"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: rm -rf brace-HOME is blocked" '{"tool_input":{"command":"rm -rf ${HOME}/x"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: cp within scope passes" '{"tool_input":{"command":"cp src/a.py src/b.py"}}' ".claude/hooks/guard_bash.py" 0
test_hook "guard_bash: exec hook passes" '{"tool_input":{"command":"uv run python .claude/hooks/guard_scope.py"}}' ".claude/hooks/guard_bash.py" 0
test_hook "guard_bash: exec spec_approve is blocked" '{"tool_input":{"command":"uv run python .claude/hooks/spec_approve.py R-003"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: copied spec_approve is blocked" '{"tool_input":{"command":"python /tmp/spec_approve.py R-003"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: redirect to last_spec_pass.txt is blocked" '{"tool_input":{"command":"echo deadbeef > .claude/spec/last_spec_pass.txt"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_scope: last_spec_pass.txt write is blocked" '{"tool_input":{"file_path":".claude/spec/last_spec_pass.txt","content":"deadbeef"}}' ".claude/hooks/guard_scope.py" 2
test_hook "guard_scope: design_hashes.txt write is blocked" '{"tool_input":{"file_path":".claude/spec/design_hashes.txt","content":"design deadbeef"}}' ".claude/hooks/guard_scope.py" 2
test_hook "guard_bash: redirect to last_eval_pass.txt is blocked" '{"tool_input":{"command":"echo deadbeef > .claude/checkpoints/last_eval_pass.txt"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_scope: last_eval_pass.txt write is blocked" '{"tool_input":{"file_path":".claude/checkpoints/last_eval_pass.txt","content":"deadbeef"}}' ".claude/hooks/guard_scope.py" 2
test_hook "guard_bash: redirect to last_quality_pass.txt is blocked" '{"tool_input":{"command":"echo deadbeef > .claude/checkpoints/last_quality_pass.txt"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_scope: last_quality_pass.txt write is blocked" '{"tool_input":{"file_path":".claude/checkpoints/last_quality_pass.txt","content":"deadbeef"}}' ".claude/hooks/guard_scope.py" 2
# codex_review_done.txt は他のゲートマーカーと違い「エージェント自身が書く」設計
# (cross-review スキル手順6 / ml-pipeline 手順9)。保護パスに入れると cross-review を
# 完了できず codex_gate が永久にブロックするデッドロックになるため、あえて保護しない。
# 将来この判断が覆されたら気づけるよう、正規コマンドが通ることを検査する
test_hook "guard_bash: cross-review sentinel write passes" '{"tool_input":{"command":"git rev-parse HEAD > .claude/checkpoints/codex_review_done.txt"}}' ".claude/hooks/guard_bash.py" 0

# --- data/ 保護(データセットの上書き・削除防止) ---
test_hook "guard_scope: data/ write is blocked" '{"tool_input":{"file_path":"data/train.csv","content":"a,b"}}' ".claude/hooks/guard_scope.py" 2
test_hook "guard_scope: nested data/ write is blocked" '{"tool_input":{"file_path":"src/data/train.csv","content":"a,b"}}' ".claude/hooks/guard_scope.py" 2
test_hook "guard_scope: database/ write passes" '{"tool_input":{"file_path":"src/database/models.py","content":"pass"}}' ".claude/hooks/guard_scope.py" 0
test_hook "guard_bash: rm -rf data is blocked" '{"tool_input":{"command":"rm -rf data"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: cp into data/ is blocked" '{"tool_input":{"command":"cp evil.csv data/train.csv"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: redirect to data/ is blocked" '{"tool_input":{"command":"echo x > data/train.csv"}}' ".claude/hooks/guard_bash.py" 2
test_hook_msg "guard_scope: data/ block message names dataset" '{"tool_input":{"file_path":"data/train.csv","content":"a,b"}}' ".claude/hooks/guard_scope.py" "データセット" 2
test_hook_msg "guard_bash: data/ block message names dataset" '{"tool_input":{"command":"cp evil.csv data/train.csv"}}' ".claude/hooks/guard_bash.py" "データセット" 2
test_hook_msg "guard_scope: hooks block message stays hook-specific" '{"tool_input":{"file_path":".claude/hooks/guard_scope.py","content":"x"}}' ".claude/hooks/guard_scope.py" "フック/設定" 2
# symlink 迂回(ln -s data dlink 経由の書き込み)も realpath 照合でブロックする。
# 中断残りの fixture(symlink)は削除してから作り直す(残骸を「symlink を
# 作れない環境」と誤認して恒久スキップしないため)。symlink 以外が同名で
# 存在する場合は誤削除を避けて NG にする(スキップで隠さない)
if [ -e verify_dlink_fixture ] && [ ! -L verify_dlink_fixture ]; then
  echo "NG: verify_dlink_fixture の位置に symlink 以外のファイルが存在します(手動で退避してください)"
  failed=$((failed+1))
else
  rm -f verify_dlink_fixture
  if [ -L verify_dlink_fixture ] || [ -e verify_dlink_fixture ]; then
    # 削除に失敗した残骸を「symlink を作れない環境」と誤認して SKIP しない
    echo "NG: verify_dlink_fixture の残骸を削除できません(手動で削除してください)"
    failed=$((failed+1))
  elif ln -s data verify_dlink_fixture 2>/dev/null; then
    test_hook "guard_scope: symlinked data/ write is blocked" '{"tool_input":{"file_path":"verify_dlink_fixture/train.csv","content":"a,b"}}' ".claude/hooks/guard_scope.py" 2
    test_hook "guard_bash: cp via symlinked data/ is blocked" '{"tool_input":{"command":"cp evil.csv verify_dlink_fixture/train.csv"}}' ".claude/hooks/guard_bash.py" 2
    rm -f verify_dlink_fixture
  else
    echo "SKIP: symlink を作成できないため symlink 迂回テストをスキップします"
  fi
fi

# --- guard_scope: worktree封じ込め(cwdベース。$RP はテスト実行時のリポジトリ絶対パス) ---
RP="$(pwd)"
test_hook "guard_scope: worktree封じ込め - 同worktree内は許可" \
  "{\"cwd\":\"$RP/.worktrees/group-A\",\"tool_input\":{\"file_path\":\"$RP/.worktrees/group-A/src/foo.py\"}}" \
  ".claude/hooks/guard_scope.py" 0
test_hook "guard_scope: worktree封じ込め - worktree→メインはブロック" \
  "{\"cwd\":\"$RP/.worktrees/group-A\",\"tool_input\":{\"file_path\":\"$RP/src/train.py\"}}" \
  ".claude/hooks/guard_scope.py" 2
test_hook "guard_scope: worktree封じ込め - メイン→worktreeは現状維持で許可" \
  "{\"cwd\":\"$RP\",\"tool_input\":{\"file_path\":\"$RP/.worktrees/group-A/src/foo.py\"}}" \
  ".claude/hooks/guard_scope.py" 0
test_hook "guard_scope: worktree封じ込め - 前方一致の隣接名(group-AB)はブロック" \
  "{\"cwd\":\"$RP/.worktrees/group-A\",\"tool_input\":{\"file_path\":\"$RP/.worktrees/group-AB/src/foo.py\"}}" \
  ".claude/hooks/guard_scope.py" 2
test_hook "guard_scope: worktree封じ込め - worktree内サブディレクトリcwdでもブロック" \
  "{\"cwd\":\"$RP/.worktrees/group-A/src\",\"tool_input\":{\"file_path\":\"$RP/src/train.py\"}}" \
  ".claude/hooks/guard_scope.py" 2
test_hook "guard_scope: worktree封じ込め - 不正cwd型(数値)はフォールバックで許可" \
  "{\"cwd\":12345,\"tool_input\":{\"file_path\":\"$RP/src/train.py\"}}" \
  ".claude/hooks/guard_scope.py" 0
test_hook "guard_scope: worktree封じ込め - 相対パスはペイロードcwd基準で解決し許可" \
  "{\"cwd\":\"$RP/.worktrees/group-A\",\"tool_input\":{\"file_path\":\"src/foo.py\"}}" \
  ".claude/hooks/guard_scope.py" 0
test_hook "guard_scope: worktree封じ込め - 相対パスでのworktree脱出はブロック" \
  "{\"cwd\":\"$RP/.worktrees/group-A\",\"tool_input\":{\"file_path\":\"../../src/train.py\"}}" \
  ".claude/hooks/guard_scope.py" 2

# --- PowerShellネイティブコマンドの検知(クロスOS対応) ---
test_hook "guard_bash: Remove-Item hooks dir is blocked" '{"tool_input":{"command":"Remove-Item -Recurse -Force .claude/hooks"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: Remove-Item hooks dir no trailing slash is blocked" '{"tool_input":{"command":"rm -rf .claude/hooks"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: Set-Content settings.json is blocked" '{"tool_input":{"command":"Set-Content -Path .claude/settings.json -Value data"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: Copy-Item overwrite hook is blocked" '{"tool_input":{"command":"Copy-Item evil.py .claude/hooks/guard_bash.py -Force"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: Remove-Item -Recurse -Force drive root is blocked" '{"tool_input":{"command":"Remove-Item -Recurse -Force C:\\\\Users\\\\foo"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: Remove-Item -Recurse -Force scoped dir passes" '{"tool_input":{"command":"Remove-Item -Recurse -Force build"}}' ".claude/hooks/guard_bash.py" 0
test_hook "guard_bash: git add -u is blocked" '{"tool_input":{"command":"git add -u"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: Anthropic-style key is blocked" '{"tool_input":{"command":"echo sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789-AbCdEfGh"}}' ".claude/hooks/guard_bash.py" 2

# --- guard_bash: 誤検知抑制とスコープ外削除(security-hardening) ---
test_hook "guard_bash: grep spec_approve passes" '{"tool_input":{"command":"grep -n spec_approve README.md"}}' ".claude/hooks/guard_bash.py" 0
test_hook "guard_bash: sed -n read on hook passes" '{"tool_input":{"command":"sed -n 1,5p .claude/hooks/auto_format.py"}}' ".claude/hooks/guard_bash.py" 0
test_hook "guard_bash: sed -i on hook is blocked" '{"tool_input":{"command":"sed -i s/a/b/ .claude/hooks/auto_format.py"}}' ".claude/hooks/guard_bash.py" 2
# guard_bash はスコープ判定に tempfile.gettempdir() の例外を持つため、リポジトリが
# 一時ディレクトリ配下にあると ../other-project も「許可」と判定されてこのケースだけ
# 必ず落ちる(実測。evaluator が /tmp 配下のクローンで verify-hooks を回して発覚)。
# テスト側の環境依存なので、その場合はスキップする。
TMP_ROOT=$(python3 -c "import tempfile; print(tempfile.gettempdir())" 2>/dev/null || echo "/tmp")
case "$(pwd)/" in
  "$TMP_ROOT"/*)
    echo "SKIP: guard_bash: rm -rf relative out-of-scope is blocked(リポジトリが一時ディレクトリ配下のため)"
    ;;
  *)
    test_hook "guard_bash: rm -rf relative out-of-scope is blocked" '{"tool_input":{"command":"rm -rf ../other-project"}}' ".claude/hooks/guard_bash.py" 2
    ;;
esac
test_hook "guard_bash: touch settings.json is blocked" '{"tool_input":{"command":"touch .claude/settings.json"}}' ".claude/hooks/guard_bash.py" 2

test_hook "enforce_eval: no flag passes" '{}' ".claude/hooks/enforce_eval.py" 0
# セッションが CLAUDE_QUALITY_GATE=1 を注入していても素の状態をテストできるよう明示的に外す
echo '{}' | env -u CLAUDE_QUALITY_GATE uv run python ".claude/hooks/quality_gate.py" >/dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "OK: quality_gate: off when flag not set (exit 0)"
else
  echo "NG: quality_gate: off when flag not set (expected 0)"
  failed=$((failed+1))
fi
# セッションが CLAUDE_NOTIFY=1 を注入していても素の状態をテストできるよう明示的に外す
# (CLAUDE_CONTROL_LEVEL=L3 も通知ONと解釈されるため同様に外す)
echo '{}' | env -u CLAUDE_NOTIFY -u CLAUDE_CONTROL_LEVEL uv run python ".claude/hooks/notify.py" >/dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "OK: notify: off when flag not set (exit 0)"
else
  echo "NG: notify: off when flag not set (expected 0)"
  failed=$((failed+1))
fi
# セッションが CLAUDE_CROSS_REVIEW=1 を注入していても素の状態をテストできるよう明示的に外す
echo '{}' | env -u CLAUDE_CROSS_REVIEW uv run python ".claude/hooks/codex_gate.py" >/dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "OK: codex_gate: off when flag not set (exit 0)"
else
  echo "NG: codex_gate: off when flag not set (expected 0)"
  failed=$((failed+1))
fi

# --- codex_gate: HEAD束縛センチネル(独立の一時リポジトリで検証。
#     dirty-tree ケースを実リポジトリを汚さずテストするため) ---
ABS_CODEX_GATE="$(pwd)/.claude/hooks/codex_gate.py"
CG_TMP=$(mktemp -d)
CG_SENTINEL="$CG_TMP/.claude/checkpoints/codex_review_done.txt"
(
  cd "$CG_TMP" && git init -q . \
    && git config user.email test@test && git config user.name test \
    && echo x > f.txt \
    && echo ".claude/checkpoints/" > .gitignore \
    && git add f.txt .gitignore && git commit -qm init \
    && mkdir -p .claude/checkpoints
)

test_codex_gate() {
  local description="$1"
  local expected_exit="$2"
  ( cd "$CG_TMP" && echo '{}' | CLAUDE_CROSS_REVIEW=1 uv run python "$ABS_CODEX_GATE" >/dev/null 2>&1 )
  local actual=$?
  if [ "$actual" -eq "$expected_exit" ]; then
    echo "OK: $description (exit $actual)"
  else
    echo "NG: $description (expected $expected_exit, got $actual)"
    failed=$((failed+1))
  fi
}

test_codex_gate "codex_gate: no sentinel is blocked" 2
git -C "$CG_TMP" rev-parse HEAD > "$CG_SENTINEL"
test_codex_gate "codex_gate: matching HEAD + clean tree passes" 0
if [ -f "$CG_SENTINEL" ]; then
  echo "OK: codex_gate: sentinel persists while HEAD unchanged"
else
  echo "NG: codex_gate: sentinel persists while HEAD unchanged (deleted)"
  failed=$((failed+1))
fi
echo modified >> "$CG_TMP/f.txt"
test_codex_gate "codex_gate: uncommitted tracked change is blocked" 2
git -C "$CG_TMP" checkout -- f.txt
test_codex_gate "codex_gate: clean again passes" 0
echo new > "$CG_TMP/untracked.txt"
test_codex_gate "codex_gate: untracked file is blocked" 2
git -C "$CG_TMP" config status.showUntrackedFiles no
test_codex_gate "codex_gate: untracked blocked even with showUntrackedFiles=no" 2
git -C "$CG_TMP" config --unset status.showUntrackedFiles
rm "$CG_TMP/untracked.txt"
echo staged >> "$CG_TMP/f.txt"
git -C "$CG_TMP" add f.txt
test_codex_gate "codex_gate: staged change is blocked" 2
git -C "$CG_TMP" commit -qm staged
test_codex_gate "codex_gate: stale HEAD after commit is blocked" 2
if [ ! -f "$CG_SENTINEL" ]; then
  echo "OK: codex_gate: stale sentinel is discarded"
else
  echo "NG: codex_gate: stale sentinel is discarded (still present)"
  failed=$((failed+1))
fi
rm -rf "$CG_TMP"

# --- spec-compliance (spec_gate / spec_approve / guard_scope連携) ---
SPEC_GATE=".claude/hooks/spec_gate.py"
SPEC_APPROVE=".claude/hooks/spec_approve.py"
ABS_SPEC_GATE="$(pwd)/$SPEC_GATE"
ABS_SPEC_APPROVE="$(pwd)/$SPEC_APPROVE"
  SPEC_FIXTURE=$(mktemp -d)
  trap 'rm -rf "$SPEC_FIXTURE"' EXIT

  mkdir -p "$SPEC_FIXTURE/docs" "$SPEC_FIXTURE/spec" "$SPEC_FIXTURE/docs_bad"

  cat > "$SPEC_FIXTURE/docs/design.md" <<'EOF'
# フィクスチャ設計書

## 受け入れ条件

| ID | 要件 | 検証方法 | 期待結果 | 種別 | 対象 |
|---|---|---|---|---|---|
| R-001 | ダミー要件1 | python -c "import sys; sys.exit(0)" | exit 0 | auto | |
| R-002 | ダミー要件2(目視) | (目視) | 人間承認 | manual | |
| R-003 | ダミー要件3 | python -c "import sys; sys.exit(0)" | exit 0 | auto | |
EOF

  cat > "$SPEC_FIXTURE/docs_bad/design.md" <<'EOF'
# フィクスチャ設計書(壊れたテーブル)

## 受け入れ条件

| ID | 要件 | 検証方法 | 期待結果 | 種別 |
|---|---|---|---|---|
| R-001 | ダミー要件1 | python -c "pass" | exit 0 | auto |
EOF

  cat > "$SPEC_FIXTURE/spec/verdict-design.md" <<'EOF'
| ID | 判定 | 実行コマンド | 実測値 | 証拠 |
|---|---|---|---|---|
| R-001 | PASS | python -c "..." | 0 | test.py:1 |
| R-002 | PASS | (目視) | - | test.py:2 |
| R-003 | PASS | python -c "..." | 0 | test.py:3 |
EOF

  cat > "$SPEC_FIXTURE/spec/audit-design.md" <<'EOF'
| ID | 結果 | 備考 |
|---|---|---|
| R-001 | OK | ok |
| R-002 | OK | ok |
| R-003 | OK | ok |
EOF

  test_spec_gate() {
    local description="$1"
    local expected_exit="$2"
    local docs_dir="$3"
    local spec_dir="$4"
    shift 4
    echo '{}' | env "$@" uv run python "$ABS_SPEC_GATE" --docs "$docs_dir" --spec-dir "$spec_dir" \
      >"$SPEC_FIXTURE/last_out.txt" 2>&1
    local actual=$?
    if [ "$actual" -eq "$expected_exit" ]; then
      echo "OK: $description (exit $actual)"
    else
      echo "NG: $description (expected $expected_exit, got $actual)"
      failed=$((failed+1))
    fi
  }

  # R-104: manual要件が未承認ならブロック
  test_spec_gate "spec_gate R-104: manual未承認はブロック" 2 \
    "$SPEC_FIXTURE/docs" "$SPEC_FIXTURE/spec" CLAUDE_SPEC_CHECK=1

  # R-105: spec_approve 実行後は R-104 のケースが通過する
  uv run python "$ABS_SPEC_APPROVE" R-002 --docs "$SPEC_FIXTURE/docs" --spec-dir "$SPEC_FIXTURE/spec" >/dev/null 2>&1
  test_spec_gate "spec_approve後: R-105/R-101 全要件PASSで通過" 0 \
    "$SPEC_FIXTURE/docs" "$SPEC_FIXTURE/spec" CLAUDE_SPEC_CHECK=1

  # 設計書ハッシュ: verdict/audit/approvals が揃っていても design_hashes.txt が
  # 無ければブロック(計画承認の強制)
  mkdir -p "$SPEC_FIXTURE/spec_nohash"
  cp "$SPEC_FIXTURE/spec/verdict-design.md" "$SPEC_FIXTURE/spec_nohash/verdict-design.md"
  cp "$SPEC_FIXTURE/spec/audit-design.md" "$SPEC_FIXTURE/spec_nohash/audit-design.md"
  echo "design R-002 2026-01-01T00:00:00" > "$SPEC_FIXTURE/spec_nohash/approvals.txt"
  test_spec_gate "spec_gate 設計書ハッシュ: 計画承認記録なしはブロック" 2 \
    "$SPEC_FIXTURE/docs" "$SPEC_FIXTURE/spec_nohash" CLAUDE_SPEC_CHECK=1

  # 設計書ハッシュ: 承認後に設計書が改変されたらブロック
  mkdir -p "$SPEC_FIXTURE/docs_tamper" "$SPEC_FIXTURE/spec_tamper"
  cp "$SPEC_FIXTURE/docs/design.md" "$SPEC_FIXTURE/docs_tamper/design.md"
  cp "$SPEC_FIXTURE/spec/verdict-design.md" "$SPEC_FIXTURE/spec_tamper/verdict-design.md"
  cp "$SPEC_FIXTURE/spec/audit-design.md" "$SPEC_FIXTURE/spec_tamper/audit-design.md"
  uv run python "$ABS_SPEC_APPROVE" R-002 --docs "$SPEC_FIXTURE/docs_tamper" --spec-dir "$SPEC_FIXTURE/spec_tamper" >/dev/null 2>&1
  test_spec_gate "spec_gate 設計書ハッシュ: 承認直後は通過" 0 \
    "$SPEC_FIXTURE/docs_tamper" "$SPEC_FIXTURE/spec_tamper" CLAUDE_SPEC_CHECK=1
  printf '\n(tampered after approval)\n' >> "$SPEC_FIXTURE/docs_tamper/design.md"
  test_spec_gate "spec_gate 設計書ハッシュ: 承認後の改変はブロック" 2 \
    "$SPEC_FIXTURE/docs_tamper" "$SPEC_FIXTURE/spec_tamper" CLAUDE_SPEC_CHECK=1
  uv run python "$ABS_SPEC_APPROVE" --design design --docs "$SPEC_FIXTURE/docs_tamper" --spec-dir "$SPEC_FIXTURE/spec_tamper" >/dev/null 2>&1
  test_spec_gate "spec_gate 設計書ハッシュ: --design 再承認で通過" 0 \
    "$SPEC_FIXTURE/docs_tamper" "$SPEC_FIXTURE/spec_tamper" CLAUDE_SPEC_CHECK=1

  # R-108: CLAUDE_SPEC_RECHECK_N=all で auto要件が全件再実行される(ログに全ID)
  echo '{}' | CLAUDE_SPEC_CHECK=1 CLAUDE_SPEC_RECHECK_N=all uv run python "$ABS_SPEC_GATE" \
    --docs "$SPEC_FIXTURE/docs" --spec-dir "$SPEC_FIXTURE/spec" >"$SPEC_FIXTURE/recheck_all.txt" 2>&1
  if grep -q "R-001" "$SPEC_FIXTURE/recheck_all.txt" && grep -q "R-003" "$SPEC_FIXTURE/recheck_all.txt"; then
    echo "OK: spec_gate R-108: RECHECK_N=all で全auto ID(R-001,R-003)が実行ログに出現"
  else
    echo "NG: spec_gate R-108: RECHECK_N=all の実行ログに全IDが出現しない"
    failed=$((failed+1))
  fi

  # R-112: CLAUDE_SPEC_CHECK未設定なら何もしない
  test_spec_gate "spec_gate R-112: CLAUDE_SPEC_CHECK未設定は素通り" 0 \
    "$SPEC_FIXTURE/docs" "$SPEC_FIXTURE/spec"

  # R-101: 全要件PASS+承認済み+監査OKの設計書で通過する(再掲・独立確認)
  test_spec_gate "spec_gate R-101: 全要件PASS+承認済み+監査OKで通過" 0 \
    "$SPEC_FIXTURE/docs" "$SPEC_FIXTURE/spec" CLAUDE_SPEC_CHECK=1

  # R-102: FAIL要件が1つでもあれば完了ブロック
  mkdir -p "$SPEC_FIXTURE/spec_fail"
  cat > "$SPEC_FIXTURE/spec_fail/verdict-design.md" <<'EOF'
| ID | 判定 | 実行コマンド | 実測値 | 証拠 |
|---|---|---|---|---|
| R-001 | FAIL | python -c "..." | 1 | test.py:1 |
| R-002 | PASS | (目視) | - | test.py:2 |
| R-003 | PASS | python -c "..." | 0 | test.py:3 |
EOF
  cp "$SPEC_FIXTURE/spec/audit-design.md" "$SPEC_FIXTURE/spec_fail/audit-design.md"
  echo "design R-002 2026-01-01T00:00:00" > "$SPEC_FIXTURE/spec_fail/approvals.txt"
  test_spec_gate "spec_gate R-102: FAIL要件があればブロック" 2 \
    "$SPEC_FIXTURE/docs" "$SPEC_FIXTURE/spec_fail" CLAUDE_SPEC_CHECK=1

  # R-103: verdict ファイルに要件IDの欠けがあればブロック
  mkdir -p "$SPEC_FIXTURE/spec_missing"
  cat > "$SPEC_FIXTURE/spec_missing/verdict-design.md" <<'EOF'
| ID | 判定 | 実行コマンド | 実測値 | 証拠 |
|---|---|---|---|---|
| R-001 | PASS | python -c "..." | 0 | test.py:1 |
| R-002 | PASS | (目視) | - | test.py:2 |
EOF
  cp "$SPEC_FIXTURE/spec/audit-design.md" "$SPEC_FIXTURE/spec_missing/audit-design.md"
  echo "design R-002 2026-01-01T00:00:00" > "$SPEC_FIXTURE/spec_missing/approvals.txt"
  test_spec_gate "spec_gate R-103: verdictにID欠けがあればブロック" 2 \
    "$SPEC_FIXTURE/docs" "$SPEC_FIXTURE/spec_missing" CLAUDE_SPEC_CHECK=1

  # R-107: テーブルが崩れている(列不足)場合は安全側に倒してブロック
  test_spec_gate "spec_gate R-107: テーブル列不足はブロック" 2 \
    "$SPEC_FIXTURE/docs_bad" "$SPEC_FIXTURE/spec" CLAUDE_SPEC_CHECK=1

  # R-106: approvals.txt への Claude 経由書き込みは guard_scope がブロック
  test_hook "guard_scope R-106: approvals.txtへの書き込みはブロック" \
    '{"tool_input":{"file_path":".claude/spec/approvals.txt","content":"fake R-002"}}' \
    ".claude/hooks/guard_scope.py" 2

  # R-109: 対象列のある要件で対象モジュールが未実行なら coverage 検査で落ちる
  if uv run python -c "import coverage" >/dev/null 2>&1; then
    mkdir -p "$SPEC_FIXTURE/covdir" "$SPEC_FIXTURE/docs_cov" "$SPEC_FIXTURE/spec_cov"
    echo 'print("decoy")' > "$SPEC_FIXTURE/covdir/decoy.py"
    (cd "$SPEC_FIXTURE/covdir" && uv run coverage run --data-file=.coverage decoy.py >/dev/null 2>&1)
    cat > "$SPEC_FIXTURE/docs_cov/design.md" <<EOF
# フィクスチャ設計書(対象列あり)

## 受け入れ条件

| ID | 要件 | 検証方法 | 期待結果 | 種別 | 対象 |
|---|---|---|---|---|---|
| R-001 | ダミー要件1 | python -c "import sys; sys.exit(0)" | exit 0 | auto | $SPEC_FIXTURE/covdir/other_module.py |
EOF
    cat > "$SPEC_FIXTURE/spec_cov/verdict-design.md" <<'EOF'
| ID | 判定 | 実行コマンド | 実測値 | 証拠 |
|---|---|---|---|---|
| R-001 | PASS | python -c "..." | 0 | test.py:1 |
EOF
    cat > "$SPEC_FIXTURE/spec_cov/audit-design.md" <<'EOF'
| ID | 結果 | 備考 |
|---|---|---|
| R-001 | OK | ok |
EOF
    (
      cd "$SPEC_FIXTURE/covdir" && \
      echo '{}' | CLAUDE_SPEC_CHECK=1 uv run python "$ABS_SPEC_GATE" \
        --docs "$SPEC_FIXTURE/docs_cov" --spec-dir "$SPEC_FIXTURE/spec_cov" >out_cov.txt 2>&1
    )
    actual_cov=$?
    if [ "$actual_cov" -eq 2 ]; then
      echo "OK: spec_gate R-109: 対象モジュール未実行はcoverage検査でブロック (exit $actual_cov)"
    else
      echo "NG: spec_gate R-109: 対象モジュール未実行 (expected 2, got $actual_cov)"
      failed=$((failed+1))
    fi
  else
    echo "SKIP: spec_gate R-109: coverage が未導入のため対象列検査をスキップします"
  fi

  # --ci: verdict/audit/approvals が無くても auto再実行(+coverage)のみで判定する(CI用)
  mkdir -p "$SPEC_FIXTURE/spec_empty"
  uv run python "$ABS_SPEC_GATE" --ci --docs "$SPEC_FIXTURE/docs" --spec-dir "$SPEC_FIXTURE/spec_empty" >/dev/null 2>&1
  actual_ci=$?
  if [ "$actual_ci" -eq 0 ]; then
    echo "OK: spec_gate --ci: verdict/audit無しでもauto再実行のみで通過 (exit $actual_ci)"
  else
    echo "NG: spec_gate --ci: verdict/audit無し (expected 0, got $actual_ci)"
    failed=$((failed+1))
  fi

  # キャッシュ: PASS後に状態が変わっていなければ auto再実行をスキップする
  # (マーカーファイル自身が署名に混入してキャッシュが失効しないことの確認)
  echo '{}' | CLAUDE_SPEC_CHECK=1 uv run python "$ABS_SPEC_GATE" --docs "$SPEC_FIXTURE/docs" --spec-dir "$SPEC_FIXTURE/spec" >/dev/null 2>&1
  echo '{}' | CLAUDE_SPEC_CHECK=1 uv run python "$ABS_SPEC_GATE" --docs "$SPEC_FIXTURE/docs" --spec-dir "$SPEC_FIXTURE/spec" >"$SPEC_FIXTURE/cache2.txt" 2>&1
  actual_cache=$?
  # 再実行ログの検出はエンコーディング非依存のASCII部分で行う
  # (Windows では Python の stderr が cp932 になり日本語が UTF-8 と一致しない)
  if [ "$actual_cache" -eq 0 ] && ! grep -q "spec_gate] auto" "$SPEC_FIXTURE/cache2.txt"; then
    echo "OK: spec_gate キャッシュ: 状態不変ならauto再実行をスキップ (exit $actual_cache)"
  else
    echo "NG: spec_gate キャッシュ: 状態不変でも再実行された、または exit != 0 (got $actual_cache)"
    failed=$((failed+1))
  fi

  rm -rf "$SPEC_FIXTURE"
  trap - EXIT

# --- action_log / agent_log: 空ペイロードでも exit 0(記録失敗で作業を止めない) ---
test_hook "action_log: exits 0 on empty payload" '{}' ".claude/hooks/action_log.py" 0
test_hook "agent_log: exits 0 on empty payload" '{}' ".claude/hooks/agent_log.py" 0

# --- plan_gate: 一時ディレクトリで検証(検査対象がブランチ名から決まる新仕様に合わせ、
#     各ケースを git リポジトリ + ブランチ名に対応する計画ファイルで組み立てる) ---
# 注意: trap は張らない(スクリプト末尾で EXIT トラップは既に解除済みのため、
# ここで再設定すると既存の後始末規約を壊す)。後始末は各ケースで rm -rf を明示実行する。
ABS_PLAN_GATE="$(pwd)/.claude/hooks/plan_gate.py"

test_plan_gate() {
  local description="$1"
  local branch="$2"
  local plan_name="$3"
  local plan_text="$4"
  local inv_text="$5"
  local expected_exit="$6"

  local tmp; tmp=$(mktemp -d)
  git -C "$tmp" init -q -b "$branch"
  if [ -n "$plan_name" ]; then
    local cl="$tmp/.claude"
    local pl="$cl/plans"
    mkdir -p "$pl"
    printf '%s' "$plan_text" > "$pl/$plan_name"
    if [ -n "$inv_text" ]; then
      local inv="$cl/improvements"
      mkdir -p "$inv"
      printf '%s' "$inv_text" > "$inv/invariants.md"
    fi
  fi
  local actual
  actual=$(cd "$tmp" && echo '{}' | uv run python "$ABS_PLAN_GATE" >/dev/null 2>&1; echo $?)
  rm -rf "$tmp"
  if [ "$actual" -eq "$expected_exit" ]; then
    echo "OK: $description (exit $actual)"
  else
    echo "NG: $description (expected $expected_exit, got $actual)"
    failed=$((failed+1))
  fi
}

test_plan_gate "plan_gate: passes when .claude/plans directory is absent" \
  "pipeline/20260726-vh-a" "" "" "" 0

PG_B_TEXT=$'別ブランチ向けの計画メモ。\n'
test_plan_gate "plan_gate: passes when no plan file matches the branch" \
  "pipeline/20260726-vh-b" "20260726-other.md" "$PG_B_TEXT" "" 0

PG_C_TEXT=$'experiment: false\n'
test_plan_gate "plan_gate: passes when experiment: false is declared" \
  "pipeline/20260726-vh-c" "20260726-vh-c.md" "$PG_C_TEXT" "" 0

PG_D_TEXT=$'学習ジョブを新しいデータセットで実行する。\n'
test_plan_gate "plan_gate: blocks when experimental language is present but goal is undefined" \
  "pipeline/20260726-vh-d" "20260726-vh-d.md" "$PG_D_TEXT" "" 2

PG_E_TEXT=$'cost_estimate:\n  train_minutes: 1e3\n  epochs: 30\n  dataset_gb: 2.4\n  parallel_jobs: 1\ngoal:\n  metric: rmse\n  target: 0.15\n  direction: minimize\n  baseline: 0.21\n  guard_metrics: []\n'
test_plan_gate "plan_gate: blocks when train_minutes is unreadable as a decimal (1e3)" \
  "pipeline/20260726-vh-e" "20260726-vh-e.md" "$PG_E_TEXT" "" 2

PG_F_TEXT=$'cost_estimate:\n  train_minutes: 999\n  epochs: 30\n  dataset_gb: 2.4\n  parallel_jobs: 1\ngoal:\n  metric: rmse\n  target: 0.15\n  direction: minimize\n  baseline: 0.21\n  guard_metrics: []\n'
PG_F_INV=$'resources:\n  max_train_minutes: 120\n  max_epochs: 100\n  max_dataset_gb: 10\n  max_parallel_jobs: 1\n'
test_plan_gate "plan_gate: blocks when train_minutes exceeds the resource limit" \
  "pipeline/20260726-vh-f" "20260726-vh-f.md" "$PG_F_TEXT" "$PG_F_INV" 2

echo ""
if [ "$failed" -gt 0 ]; then
  echo "$failed 件のテストが失敗しました"
  exit 1
else
  echo "全テストPASS"
  exit 0
fi
