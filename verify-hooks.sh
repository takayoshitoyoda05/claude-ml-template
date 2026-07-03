#!/bin/bash
set -u
failed=0

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

test_hook "guard_scope: .pth is blocked" '{"tool_input":{"file_path":"model.pth"}}' ".claude/hooks/guard_scope.py" 2
test_hook "guard_scope: .py passes" '{"tool_input":{"file_path":"src/train.py"}}' ".claude/hooks/guard_scope.py" 0
test_hook "guard_scope: .env is blocked" '{"tool_input":{"file_path":".env"}}' ".claude/hooks/guard_scope.py" 2
test_hook "guard_scope: secret content is blocked" '{"tool_input":{"file_path":"config.py","content":"KEY=sk-abcdefghijklmnopqrstuvwxyz"}}' ".claude/hooks/guard_scope.py" 2
test_hook "guard_bash: rm -rf / is blocked" '{"tool_input":{"command":"rm -rf /"}}' ".claude/hooks/guard_bash.py" 2
test_hook "guard_bash: ls -la passes" '{"tool_input":{"command":"ls -la"}}' ".claude/hooks/guard_bash.py" 0
test_hook "guard_bash: git add .env is blocked" '{"tool_input":{"command":"git add .env"}}' ".claude/hooks/guard_bash.py" 2
test_hook "enforce_eval: no flag passes" '{}' ".claude/hooks/enforce_eval.py" 0

echo ""
if [ "$failed" -gt 0 ]; then
  echo "$failed 件のテストが失敗しました"
  exit 1
else
  echo "全テストPASS"
  exit 0
fi
