param()
$ErrorActionPreference = "Stop"
$script:failed = 0

function Test-Hook {
    param(
        [string]$Description,
        [string]$JsonInput,
        [string]$Script,
        [int]$ExpectedExit
    )
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $JsonInput | uv run python $Script *> $null
    $ErrorActionPreference = $prevEAP
    $actual = $LASTEXITCODE
    if ($actual -eq $ExpectedExit) {
        Write-Host "OK: $Description (exit $actual)"
    } else {
        Write-Host "NG: $Description (expected $ExpectedExit, got $actual)"
        $script:failed++
    }
}

Test-Hook "guard_scope: .pth is blocked" '{"tool_input":{"file_path":"model.pth"}}' ".claude\hooks\guard_scope.py" 2
Test-Hook "guard_scope: .py passes" '{"tool_input":{"file_path":"src/train.py"}}' ".claude\hooks\guard_scope.py" 0
Test-Hook "guard_scope: .env is blocked" '{"tool_input":{"file_path":".env"}}' ".claude\hooks\guard_scope.py" 2
Test-Hook "guard_scope: secret content is blocked" '{"tool_input":{"file_path":"config.py","content":"KEY=sk-abcdefghijklmnopqrstuvwxyz"}}' ".claude\hooks\guard_scope.py" 2
Test-Hook "guard_scope: hook self-edit is blocked" '{"tool_input":{"file_path":".claude/hooks/guard_bash.py","new_string":"pass"}}' ".claude\hooks\guard_scope.py" 2
Test-Hook "guard_scope: settings.local.json is blocked" '{"tool_input":{"file_path":".claude/settings.local.json","content":"{}"}}' ".claude\hooks\guard_scope.py" 2
Test-Hook "guard_scope: notebook in outputs/ is blocked" '{"tool_input":{"notebook_path":"outputs/nb.ipynb"}}' ".claude\hooks\guard_scope.py" 2
Test-Hook "guard_bash: rm -rf / is blocked" '{"tool_input":{"command":"rm -rf /"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: rm -fr / is blocked" '{"tool_input":{"command":"rm -fr /"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: rm -r -f ~/data is blocked" '{"tool_input":{"command":"rm -r -f ~/data"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: rm -rf build/ passes" '{"tool_input":{"command":"rm -rf build/"}}' ".claude\hooks\guard_bash.py" 0
Test-Hook "guard_bash: git push +ref is blocked" '{"tool_input":{"command":"git push origin +main"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: ls -la passes" '{"tool_input":{"command":"ls -la"}}' ".claude\hooks\guard_bash.py" 0
Test-Hook "guard_bash: git add .env is blocked" '{"tool_input":{"command":"git add .env"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: git add . is blocked" '{"tool_input":{"command":"git add ."}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: git add -A is blocked" '{"tool_input":{"command":"git add -A"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: git add foo.key.md passes" '{"tool_input":{"command":"git add foo.key.md"}}' ".claude\hooks\guard_bash.py" 0
Test-Hook "guard_bash: redirect to settings.json is blocked" '{"tool_input":{"command":"echo x > .claude/settings.json"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: tee to hooks is blocked" '{"tool_input":{"command":"echo x | tee .claude/hooks/guard_bash.py"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: redirect to .env is blocked" '{"tool_input":{"command":"echo KEY=x > .env"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: redirect to /dev/null passes" '{"tool_input":{"command":"pytest -q > /dev/null 2>&1"}}' ".claude\hooks\guard_bash.py" 0
Test-Hook "guard_bash: commit without digit passes when rule off" '{"tool_input":{"command":"git commit -m \"fix typo\""}}' ".claude\hooks\guard_bash.py" 0
Test-Hook "enforce_eval: no flag passes" '{}' ".claude\hooks\enforce_eval.py" 0

Write-Host ""
if ($script:failed -gt 0) {
    Write-Host "$($script:failed) 件のテストが失敗しました"
    exit 1
} else {
    Write-Host "全テストPASS"
    exit 0
}
