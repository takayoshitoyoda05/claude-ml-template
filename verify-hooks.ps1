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
Test-Hook "guard_bash: cp overwrite hook is blocked" '{"tool_input":{"command":"cp evil.py .claude/hooks/guard_scope.py"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: rm hook (non -rf) is blocked" '{"tool_input":{"command":"rm .claude/hooks/guard_bash.py"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: >| redirect to settings is blocked" '{"tool_input":{"command":"echo x >| .claude/settings.json"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: rm -rf brace-HOME is blocked" '{"tool_input":{"command":"rm -rf ${HOME}/x"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: cp within scope passes" '{"tool_input":{"command":"cp src/a.py src/b.py"}}' ".claude\hooks\guard_bash.py" 0
Test-Hook "guard_bash: exec hook passes" '{"tool_input":{"command":"uv run python .claude/hooks/guard_scope.py"}}' ".claude\hooks\guard_bash.py" 0
Test-Hook "guard_bash: exec spec_approve is blocked" '{"tool_input":{"command":"uv run python .claude/hooks/spec_approve.py R-003"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: copied spec_approve is blocked" '{"tool_input":{"command":"python /tmp/spec_approve.py R-003"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: redirect to last_spec_pass.txt is blocked" '{"tool_input":{"command":"echo deadbeef > .claude/spec/last_spec_pass.txt"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_scope: last_spec_pass.txt write is blocked" '{"tool_input":{"file_path":".claude/spec/last_spec_pass.txt","content":"deadbeef"}}' ".claude\hooks\guard_scope.py" 2
Test-Hook "guard_scope: design_hashes.txt write is blocked" '{"tool_input":{"file_path":".claude/spec/design_hashes.txt","content":"design deadbeef"}}' ".claude\hooks\guard_scope.py" 2
Test-Hook "guard_bash: redirect to last_eval_pass.txt is blocked" '{"tool_input":{"command":"echo deadbeef > .claude/checkpoints/last_eval_pass.txt"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_scope: last_eval_pass.txt write is blocked" '{"tool_input":{"file_path":".claude/checkpoints/last_eval_pass.txt","content":"deadbeef"}}' ".claude\hooks\guard_scope.py" 2
Test-Hook "guard_bash: redirect to last_quality_pass.txt is blocked" '{"tool_input":{"command":"echo deadbeef > .claude/checkpoints/last_quality_pass.txt"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_scope: last_quality_pass.txt write is blocked" '{"tool_input":{"file_path":".claude/checkpoints/last_quality_pass.txt","content":"deadbeef"}}' ".claude\hooks\guard_scope.py" 2

# --- PowerShellネイティブコマンドの検知(クロスOS対応) ---
Test-Hook "guard_bash: Remove-Item hooks dir is blocked" '{"tool_input":{"command":"Remove-Item -Recurse -Force .claude/hooks"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: Remove-Item hooks dir no trailing slash is blocked" '{"tool_input":{"command":"rm -rf .claude/hooks"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: Set-Content settings.json is blocked" '{"tool_input":{"command":"Set-Content -Path .claude/settings.json -Value data"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: Copy-Item overwrite hook is blocked" '{"tool_input":{"command":"Copy-Item evil.py .claude/hooks/guard_bash.py -Force"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: Remove-Item -Recurse -Force drive root is blocked" '{"tool_input":{"command":"Remove-Item -Recurse -Force C:\\Users\\foo"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: Remove-Item -Recurse -Force scoped dir passes" '{"tool_input":{"command":"Remove-Item -Recurse -Force build"}}' ".claude\hooks\guard_bash.py" 0
Test-Hook "guard_bash: git add -u is blocked" '{"tool_input":{"command":"git add -u"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: Anthropic-style key is blocked" '{"tool_input":{"command":"echo sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789-AbCdEfGh"}}' ".claude\hooks\guard_bash.py" 2

# --- guard_bash: 誤検知抑制とスコープ外削除(security-hardening) ---
Test-Hook "guard_bash: grep spec_approve passes" '{"tool_input":{"command":"grep -n spec_approve README.md"}}' ".claude\hooks\guard_bash.py" 0
Test-Hook "guard_bash: sed -n read on hook passes" '{"tool_input":{"command":"sed -n 1,5p .claude/hooks/auto_format.py"}}' ".claude\hooks\guard_bash.py" 0
Test-Hook "guard_bash: sed -i on hook is blocked" '{"tool_input":{"command":"sed -i s/a/b/ .claude/hooks/auto_format.py"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: rm -rf relative out-of-scope is blocked" '{"tool_input":{"command":"rm -rf ../other-project"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: touch settings.json is blocked" '{"tool_input":{"command":"touch .claude/settings.json"}}' ".claude\hooks\guard_bash.py" 2

Test-Hook "enforce_eval: no flag passes" '{}' ".claude\hooks\enforce_eval.py" 0
# セッションが CLAUDE_QUALITY_GATE=1 を注入していても素の状態をテストできるよう明示的に外す
$savedQualityGate = $env:CLAUDE_QUALITY_GATE
Remove-Item Env:CLAUDE_QUALITY_GATE -ErrorAction SilentlyContinue
'{}' | uv run python ".claude\hooks\quality_gate.py" *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK: quality_gate: off when flag not set (exit 0)"
} else {
    Write-Host "NG: quality_gate: off when flag not set (expected 0)"
    $script:failed++
}
if ($null -ne $savedQualityGate) { $env:CLAUDE_QUALITY_GATE = $savedQualityGate }
# セッションが CLAUDE_CROSS_REVIEW=1 を注入していても素の状態をテストできるよう明示的に外す
$savedCrossReview = $env:CLAUDE_CROSS_REVIEW
Remove-Item Env:CLAUDE_CROSS_REVIEW -ErrorAction SilentlyContinue
'{}' | uv run python ".claude\hooks\codex_gate.py" *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK: codex_gate: off when flag not set (exit 0)"
} else {
    Write-Host "NG: codex_gate: off when flag not set (expected 0)"
    $script:failed++
}
if ($null -ne $savedCrossReview) { $env:CLAUDE_CROSS_REVIEW = $savedCrossReview }

# --- codex_gate: HEAD束縛センチネル(独立の一時リポジトリで検証。
#     dirty-tree ケースを実リポジトリを汚さずテストするため) ---
$AbsCodexGate = (Resolve-Path ".claude\hooks\codex_gate.py").Path
$CgTmp = Join-Path ([System.IO.Path]::GetTempPath()) ("codex-gate-test-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $CgTmp | Out-Null
Push-Location $CgTmp
git init -q .
git config user.email test@test
git config user.name test
"x" | Out-File -FilePath "f.txt" -Encoding utf8
".claude/checkpoints/" | Out-File -FilePath ".gitignore" -Encoding ascii
git add f.txt .gitignore
git commit -qm init
New-Item -ItemType Directory -Path ".claude\checkpoints" -Force | Out-Null
Pop-Location
$CgSentinel = Join-Path $CgTmp ".claude\checkpoints\codex_review_done.txt"

function Test-CodexGate {
    param([string]$Description, [int]$ExpectedExit)
    $env:CLAUDE_CROSS_REVIEW = "1"
    Push-Location $CgTmp
    '{}' | uv run python $AbsCodexGate *> $null
    $actual = $LASTEXITCODE
    Pop-Location
    Remove-Item Env:CLAUDE_CROSS_REVIEW -ErrorAction SilentlyContinue
    if ($actual -eq $ExpectedExit) {
        Write-Host "OK: $Description (exit $actual)"
    } else {
        Write-Host "NG: $Description (expected $ExpectedExit, got $actual)"
        $script:failed++
    }
}

Test-CodexGate "codex_gate: no sentinel is blocked" 2
git -C $CgTmp rev-parse HEAD | Out-File -FilePath $CgSentinel -Encoding utf8
Test-CodexGate "codex_gate: matching HEAD + clean tree passes" 0
if (Test-Path $CgSentinel) {
    Write-Host "OK: codex_gate: sentinel persists while HEAD unchanged"
} else {
    Write-Host "NG: codex_gate: sentinel persists while HEAD unchanged (deleted)"
    $script:failed++
}
"modified" | Add-Content -Path (Join-Path $CgTmp "f.txt")
Test-CodexGate "codex_gate: uncommitted tracked change is blocked" 2
git -C $CgTmp checkout -- f.txt
Test-CodexGate "codex_gate: clean again passes" 0
"new" | Out-File -FilePath (Join-Path $CgTmp "untracked.txt") -Encoding utf8
Test-CodexGate "codex_gate: untracked file is blocked" 2
git -C $CgTmp config status.showUntrackedFiles no
Test-CodexGate "codex_gate: untracked blocked even with showUntrackedFiles=no" 2
git -C $CgTmp config --unset status.showUntrackedFiles
Remove-Item (Join-Path $CgTmp "untracked.txt")
"staged" | Add-Content -Path (Join-Path $CgTmp "f.txt")
git -C $CgTmp add f.txt
Test-CodexGate "codex_gate: staged change is blocked" 2
git -C $CgTmp commit -qm staged
Test-CodexGate "codex_gate: stale HEAD after commit is blocked" 2
if (-not (Test-Path $CgSentinel)) {
    Write-Host "OK: codex_gate: stale sentinel is discarded"
} else {
    Write-Host "NG: codex_gate: stale sentinel is discarded (still present)"
    $script:failed++
}
Remove-Item -Path $CgTmp -Recurse -Force

# --- spec-compliance (spec_gate / spec_approve / guard_scope連携) ---
$SpecGate = ".claude\hooks\spec_gate.py"
$SpecApprove = ".claude\hooks\spec_approve.py"
$AbsSpecGate = (Resolve-Path $SpecGate).Path
$AbsSpecApprove = (Resolve-Path $SpecApprove).Path
    $SpecFixture = Join-Path $env:TEMP ([System.Guid]::NewGuid().ToString())
    New-Item -ItemType Directory -Path $SpecFixture | Out-Null
    New-Item -ItemType Directory -Path "$SpecFixture\docs" -Force | Out-Null
    New-Item -ItemType Directory -Path "$SpecFixture\spec" -Force | Out-Null
    New-Item -ItemType Directory -Path "$SpecFixture\docs_bad" -Force | Out-Null

    try {
        @'
# フィクスチャ設計書

## 受け入れ条件

| ID | 要件 | 検証方法 | 期待結果 | 種別 | 対象 |
|---|---|---|---|---|---|
| R-001 | ダミー要件1 | python -c "import sys; sys.exit(0)" | exit 0 | auto | |
| R-002 | ダミー要件2(目視) | (目視) | 人間承認 | manual | |
| R-003 | ダミー要件3 | python -c "import sys; sys.exit(0)" | exit 0 | auto | |
'@ | Out-File -FilePath "$SpecFixture\docs\design.md" -Encoding utf8

        @'
# フィクスチャ設計書(壊れたテーブル)

## 受け入れ条件

| ID | 要件 | 検証方法 | 期待結果 | 種別 |
|---|---|---|---|---|
| R-001 | ダミー要件1 | python -c "pass" | exit 0 | auto |
'@ | Out-File -FilePath "$SpecFixture\docs_bad\design.md" -Encoding utf8

        @'
| ID | 判定 | 実行コマンド | 実測値 | 証拠 |
|---|---|---|---|---|
| R-001 | PASS | python -c "..." | 0 | test.py:1 |
| R-002 | PASS | (目視) | - | test.py:2 |
| R-003 | PASS | python -c "..." | 0 | test.py:3 |
'@ | Out-File -FilePath "$SpecFixture\spec\verdict-design.md" -Encoding utf8

        @'
| ID | 結果 | 備考 |
|---|---|---|
| R-001 | OK | ok |
| R-002 | OK | ok |
| R-003 | OK | ok |
'@ | Out-File -FilePath "$SpecFixture\spec\audit-design.md" -Encoding utf8

        function Test-SpecGate {
            param(
                [string]$Description,
                [int]$ExpectedExit,
                [string]$DocsDir,
                [string]$SpecDir,
                [hashtable]$Env = @{}
            )
            $prevEAP = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            foreach ($key in $Env.Keys) {
                Set-Item -Path "env:$key" -Value $Env[$key]
            }
            '{}' | uv run python $AbsSpecGate --docs $DocsDir --spec-dir $SpecDir *> "$SpecFixture\last_out.txt"
            $actual = $LASTEXITCODE
            foreach ($key in $Env.Keys) {
                Remove-Item -Path "env:$key" -ErrorAction SilentlyContinue
            }
            $ErrorActionPreference = $prevEAP
            if ($actual -eq $ExpectedExit) {
                Write-Host "OK: $Description (exit $actual)"
            } else {
                Write-Host "NG: $Description (expected $ExpectedExit, got $actual)"
                $script:failed++
            }
        }

        # R-104: manual要件が未承認ならブロック
        Test-SpecGate "spec_gate R-104: manual未承認はブロック" 2 "$SpecFixture\docs" "$SpecFixture\spec" @{ CLAUDE_SPEC_CHECK = "1" }

        # R-105: spec_approve 実行後は R-104 のケースが通過する
        uv run python $AbsSpecApprove R-002 --docs "$SpecFixture\docs" --spec-dir "$SpecFixture\spec" *> $null
        Test-SpecGate "spec_approve後: R-105/R-101 全要件PASSで通過" 0 "$SpecFixture\docs" "$SpecFixture\spec" @{ CLAUDE_SPEC_CHECK = "1" }

        # 設計書ハッシュ: verdict/audit/approvals が揃っていても design_hashes.txt が
        # 無ければブロック(計画承認の強制)
        New-Item -ItemType Directory -Path "$SpecFixture\spec_nohash" -Force | Out-Null
        Copy-Item "$SpecFixture\spec\verdict-design.md" "$SpecFixture\spec_nohash\verdict-design.md"
        Copy-Item "$SpecFixture\spec\audit-design.md" "$SpecFixture\spec_nohash\audit-design.md"
        "design R-002 2026-01-01T00:00:00" | Out-File -FilePath "$SpecFixture\spec_nohash\approvals.txt" -Encoding utf8
        Test-SpecGate "spec_gate 設計書ハッシュ: 計画承認記録なしはブロック" 2 "$SpecFixture\docs" "$SpecFixture\spec_nohash" @{ CLAUDE_SPEC_CHECK = "1" }

        # 設計書ハッシュ: 承認後に設計書が改変されたらブロック
        New-Item -ItemType Directory -Path "$SpecFixture\docs_tamper" -Force | Out-Null
        New-Item -ItemType Directory -Path "$SpecFixture\spec_tamper" -Force | Out-Null
        Copy-Item "$SpecFixture\docs\design.md" "$SpecFixture\docs_tamper\design.md"
        Copy-Item "$SpecFixture\spec\verdict-design.md" "$SpecFixture\spec_tamper\verdict-design.md"
        Copy-Item "$SpecFixture\spec\audit-design.md" "$SpecFixture\spec_tamper\audit-design.md"
        uv run python $AbsSpecApprove R-002 --docs "$SpecFixture\docs_tamper" --spec-dir "$SpecFixture\spec_tamper" *> $null
        Test-SpecGate "spec_gate 設計書ハッシュ: 承認直後は通過" 0 "$SpecFixture\docs_tamper" "$SpecFixture\spec_tamper" @{ CLAUDE_SPEC_CHECK = "1" }
        Add-Content -Path "$SpecFixture\docs_tamper\design.md" -Value "`n(tampered after approval)"
        Test-SpecGate "spec_gate 設計書ハッシュ: 承認後の改変はブロック" 2 "$SpecFixture\docs_tamper" "$SpecFixture\spec_tamper" @{ CLAUDE_SPEC_CHECK = "1" }
        uv run python $AbsSpecApprove --design design --docs "$SpecFixture\docs_tamper" --spec-dir "$SpecFixture\spec_tamper" *> $null
        Test-SpecGate "spec_gate 設計書ハッシュ: --design 再承認で通過" 0 "$SpecFixture\docs_tamper" "$SpecFixture\spec_tamper" @{ CLAUDE_SPEC_CHECK = "1" }

        # R-108: CLAUDE_SPEC_RECHECK_N=all で auto要件が全件再実行される(ログに全ID)
        $env:CLAUDE_SPEC_CHECK = "1"
        $env:CLAUDE_SPEC_RECHECK_N = "all"
        '{}' | uv run python $AbsSpecGate --docs "$SpecFixture\docs" --spec-dir "$SpecFixture\spec" *> "$SpecFixture\recheck_all.txt"
        Remove-Item -Path env:CLAUDE_SPEC_CHECK -ErrorAction SilentlyContinue
        Remove-Item -Path env:CLAUDE_SPEC_RECHECK_N -ErrorAction SilentlyContinue
        $recheckLog = Get-Content "$SpecFixture\recheck_all.txt" -Raw
        if ($recheckLog -match "R-001" -and $recheckLog -match "R-003") {
            Write-Host "OK: spec_gate R-108: RECHECK_N=all で全auto ID(R-001,R-003)が実行ログに出現"
        } else {
            Write-Host "NG: spec_gate R-108: RECHECK_N=all の実行ログに全IDが出現しない"
            $script:failed++
        }

        # R-112: CLAUDE_SPEC_CHECK未設定なら何もしない
        Test-SpecGate "spec_gate R-112: CLAUDE_SPEC_CHECK未設定は素通り" 0 "$SpecFixture\docs" "$SpecFixture\spec"

        # R-101: 全要件PASS+承認済み+監査OKの設計書で通過する(再掲・独立確認)
        Test-SpecGate "spec_gate R-101: 全要件PASS+承認済み+監査OKで通過" 0 "$SpecFixture\docs" "$SpecFixture\spec" @{ CLAUDE_SPEC_CHECK = "1" }

        # R-102: FAIL要件が1つでもあれば完了ブロック
        New-Item -ItemType Directory -Path "$SpecFixture\spec_fail" -Force | Out-Null
        @'
| ID | 判定 | 実行コマンド | 実測値 | 証拠 |
|---|---|---|---|---|
| R-001 | FAIL | python -c "..." | 1 | test.py:1 |
| R-002 | PASS | (目視) | - | test.py:2 |
| R-003 | PASS | python -c "..." | 0 | test.py:3 |
'@ | Out-File -FilePath "$SpecFixture\spec_fail\verdict-design.md" -Encoding utf8
        Copy-Item "$SpecFixture\spec\audit-design.md" "$SpecFixture\spec_fail\audit-design.md"
        "design R-002 2026-01-01T00:00:00" | Out-File -FilePath "$SpecFixture\spec_fail\approvals.txt" -Encoding utf8
        Test-SpecGate "spec_gate R-102: FAIL要件があればブロック" 2 "$SpecFixture\docs" "$SpecFixture\spec_fail" @{ CLAUDE_SPEC_CHECK = "1" }

        # R-103: verdict ファイルに要件IDの欠けがあればブロック
        New-Item -ItemType Directory -Path "$SpecFixture\spec_missing" -Force | Out-Null
        @'
| ID | 判定 | 実行コマンド | 実測値 | 証拠 |
|---|---|---|---|---|
| R-001 | PASS | python -c "..." | 0 | test.py:1 |
| R-002 | PASS | (目視) | - | test.py:2 |
'@ | Out-File -FilePath "$SpecFixture\spec_missing\verdict-design.md" -Encoding utf8
        Copy-Item "$SpecFixture\spec\audit-design.md" "$SpecFixture\spec_missing\audit-design.md"
        "design R-002 2026-01-01T00:00:00" | Out-File -FilePath "$SpecFixture\spec_missing\approvals.txt" -Encoding utf8
        Test-SpecGate "spec_gate R-103: verdictにID欠けがあればブロック" 2 "$SpecFixture\docs" "$SpecFixture\spec_missing" @{ CLAUDE_SPEC_CHECK = "1" }

        # R-107: テーブルが崩れている(列不足)場合は安全側に倒してブロック
        Test-SpecGate "spec_gate R-107: テーブル列不足はブロック" 2 "$SpecFixture\docs_bad" "$SpecFixture\spec" @{ CLAUDE_SPEC_CHECK = "1" }

        # R-106: approvals.txt への Claude 経由書き込みは guard_scope がブロック
        Test-Hook "guard_scope R-106: approvals.txtへの書き込みはブロック" '{"tool_input":{"file_path":".claude/spec/approvals.txt","content":"fake R-002"}}' ".claude\hooks\guard_scope.py" 2

        # R-109: 対象列のある要件で対象モジュールが未実行なら coverage 検査で落ちる
        $prevEAP2 = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        uv run python -c "import coverage" *> $null
        $coverageAvailable = ($LASTEXITCODE -eq 0)
        $ErrorActionPreference = $prevEAP2
        if ($coverageAvailable) {
            New-Item -ItemType Directory -Path "$SpecFixture\covdir" -Force | Out-Null
            New-Item -ItemType Directory -Path "$SpecFixture\docs_cov" -Force | Out-Null
            New-Item -ItemType Directory -Path "$SpecFixture\spec_cov" -Force | Out-Null
            'print("decoy")' | Out-File -FilePath "$SpecFixture\covdir\decoy.py" -Encoding utf8
            Push-Location "$SpecFixture\covdir"
            uv run coverage run --data-file=.coverage decoy.py *> $null
            Pop-Location
            @"
# フィクスチャ設計書(対象列あり)

## 受け入れ条件

| ID | 要件 | 検証方法 | 期待結果 | 種別 | 対象 |
|---|---|---|---|---|---|
| R-001 | ダミー要件1 | python -c "import sys; sys.exit(0)" | exit 0 | auto | $SpecFixture\covdir\other_module.py |
"@ | Out-File -FilePath "$SpecFixture\docs_cov\design.md" -Encoding utf8
            @'
| ID | 判定 | 実行コマンド | 実測値 | 証拠 |
|---|---|---|---|---|
| R-001 | PASS | python -c "..." | 0 | test.py:1 |
'@ | Out-File -FilePath "$SpecFixture\spec_cov\verdict-design.md" -Encoding utf8
            @'
| ID | 結果 | 備考 |
|---|---|---|
| R-001 | OK | ok |
'@ | Out-File -FilePath "$SpecFixture\spec_cov\audit-design.md" -Encoding utf8

            Push-Location "$SpecFixture\covdir"
            $env:CLAUDE_SPEC_CHECK = "1"
            '{}' | uv run python $AbsSpecGate --docs "$SpecFixture\docs_cov" --spec-dir "$SpecFixture\spec_cov" *> "out_cov.txt"
            $actualCov = $LASTEXITCODE
            Remove-Item -Path env:CLAUDE_SPEC_CHECK -ErrorAction SilentlyContinue
            Pop-Location
            if ($actualCov -eq 2) {
                Write-Host "OK: spec_gate R-109: 対象モジュール未実行はcoverage検査でブロック (exit $actualCov)"
            } else {
                Write-Host "NG: spec_gate R-109: 対象モジュール未実行 (expected 2, got $actualCov)"
                $script:failed++
            }
        } else {
            Write-Host "SKIP: spec_gate R-109: coverage が未導入のため対象列検査をスキップします"
        }

        # --ci: verdict/audit/approvals が無くても auto再実行(+coverage)のみで判定する(CI用)
        New-Item -ItemType Directory -Path "$SpecFixture\spec_empty" -Force | Out-Null
        $prevEAPci = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        uv run python $AbsSpecGate --ci --docs "$SpecFixture\docs" --spec-dir "$SpecFixture\spec_empty" *> $null
        $actualCi = $LASTEXITCODE
        $ErrorActionPreference = $prevEAPci
        if ($actualCi -eq 0) {
            Write-Host "OK: spec_gate --ci: verdict/audit無しでもauto再実行のみで通過 (exit $actualCi)"
        } else {
            Write-Host "NG: spec_gate --ci: verdict/audit無し (expected 0, got $actualCi)"
            $script:failed++
        }

        # キャッシュ: PASS後に状態が変わっていなければ auto再実行をスキップする
        # (マーカーファイル自身が署名に混入してキャッシュが失効しないことの確認)
        $prevEAPcache = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $env:CLAUDE_SPEC_CHECK = "1"
        '{}' | uv run python $AbsSpecGate --docs "$SpecFixture\docs" --spec-dir "$SpecFixture\spec" *> $null
        '{}' | uv run python $AbsSpecGate --docs "$SpecFixture\docs" --spec-dir "$SpecFixture\spec" *> "$SpecFixture\cache2.txt"
        $actualCache = $LASTEXITCODE
        Remove-Item -Path env:CLAUDE_SPEC_CHECK -ErrorAction SilentlyContinue
        $ErrorActionPreference = $prevEAPcache
        # 再実行ログの検出はエンコーディング非依存のASCII部分で行う
        # (Windows では Python の stderr が cp932 になり日本語の照合が不安定なため)
        # Get-Content -Raw は空ファイル(0バイト)に対して $null を返すことがあり、
        # $null -notmatch は環境によって真偽値ではなく $null を返すことがあるため
        # [string] キャストで空文字列に正規化してから比較する
        $cacheLog = [string](Get-Content "$SpecFixture\cache2.txt" -Raw -ErrorAction SilentlyContinue)
        if ($actualCache -eq 0 -and $cacheLog -notmatch "spec_gate\] auto") {
            Write-Host "OK: spec_gate キャッシュ: 状態不変ならauto再実行をスキップ (exit $actualCache)"
        } else {
            Write-Host "NG: spec_gate キャッシュ: 状態不変でも再実行された、または exit != 0 (got $actualCache)"
            $script:failed++
        }
    } finally {
        Remove-Item -Path $SpecFixture -Recurse -Force -ErrorAction SilentlyContinue
    }

Write-Host ""
if ($script:failed -gt 0) {
    Write-Host "$($script:failed) 件のテストが失敗しました"
    exit 1
} else {
    Write-Host "全テストPASS"
    exit 0
}
