param()
$ErrorActionPreference = "Stop"
$script:failed = 0

# 各テストはスコープ=リポジトリルートを前提に期待値を組むため、外部セッションの
# CLAUDE_WORK_SCOPE(別プロジェクト等)に影響されないようスクリプト全体で固定する
$SavedWorkScope = $env:CLAUDE_WORK_SCOPE
$env:CLAUDE_WORK_SCOPE = (Get-Location).Path

# PowerShell 5.1 の Out-File -Encoding utf8 は BOM を付け、Set-Content の既定は
# システムの ANSI コードページ(日本語環境では Shift-JIS)になる。どちらも
# Python 側のフックが encoding="utf-8" で読めない(BOM は先頭に \ufeff が残り、
# Shift-JIS は UnicodeDecodeError)。テストのフィクスチャは BOM なし UTF-8 で書く。
function Write-Utf8NoBom {
    param(
        [Parameter(ValueFromPipeline = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Path,
        [switch]$NoNewline
    )
    begin { $chunks = New-Object System.Collections.Generic.List[string] }
    process { $chunks.Add($Text) }
    end {
        # process ブロックで受けないと、複数オブジェクトを流したときに最後の1件しか
        # 書かれない(Out-File との非互換になる)。改行は Out-File と同じく
        # プラットフォーム既定に合わせる(Windows は CRLF、Linux/pwsh7 は LF)
        $body = [string]::Join([Environment]::NewLine, $chunks)
        if (-not $NoNewline -and -not $body.EndsWith("`n")) { $body += [Environment]::NewLine }
        [System.IO.File]::WriteAllText($Path, $body, (New-Object System.Text.UTF8Encoding($false)))
    }
}

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

# ブロック時の stderr メッセージに期待文字列が含まれるかを、exit code と
# 同一実行で検査する。data/ ブロックに「フック/設定への書き込み」と表示して
# いた誤メッセージの回帰防止(exit code だけでは検出できない。メッセージ
# だけの検査では「期待文字列を出すが exit 0 で許可する」実装を見逃す)
function Test-HookMsg {
    param(
        [string]$Description,
        [string]$JsonInput,
        [string]$Script,
        [string]$Pattern,
        [int]$ExpectedExit
    )
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $msg = $JsonInput | uv run python $Script 2>&1 | Out-String
    $ErrorActionPreference = $prevEAP
    $actual = $LASTEXITCODE
    if (($actual -eq $ExpectedExit) -and ($msg -match [regex]::Escape($Pattern))) {
        Write-Host "OK: $Description (exit $actual)"
    } else {
        Write-Host "NG: $Description (expected exit $ExpectedExit + message '$Pattern', got exit $actual)"
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
# codex_review_done.txt は他のゲートマーカーと違い「エージェント自身が書く」設計
# (cross-review スキル手順6 / ml-pipeline 手順9)。保護パスに入れると cross-review を
# 完了できず codex_gate が永久にブロックするデッドロックになるため、あえて保護しない。
# 将来この判断が覆されたら気づけるよう、正規コマンドが通ることを検査する
Test-Hook "guard_bash: cross-review sentinel write passes" '{"tool_input":{"command":"git rev-parse HEAD > .claude/checkpoints/codex_review_done.txt"}}' ".claude\hooks\guard_bash.py" 0

# --- data/ 保護(データセットの上書き・削除防止) ---
Test-Hook "guard_scope: data/ write is blocked" '{"tool_input":{"file_path":"data/train.csv","content":"a,b"}}' ".claude\hooks\guard_scope.py" 2
Test-Hook "guard_scope: nested data/ write is blocked" '{"tool_input":{"file_path":"src/data/train.csv","content":"a,b"}}' ".claude\hooks\guard_scope.py" 2
Test-Hook "guard_scope: database/ write passes" '{"tool_input":{"file_path":"src/database/models.py","content":"pass"}}' ".claude\hooks\guard_scope.py" 0
Test-Hook "guard_bash: rm -rf data is blocked" '{"tool_input":{"command":"rm -rf data"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: cp into data/ is blocked" '{"tool_input":{"command":"cp evil.csv data/train.csv"}}' ".claude\hooks\guard_bash.py" 2
Test-Hook "guard_bash: redirect to data/ is blocked" '{"tool_input":{"command":"echo x > data/train.csv"}}' ".claude\hooks\guard_bash.py" 2
Test-HookMsg "guard_scope: data/ block message names dataset" '{"tool_input":{"file_path":"data/train.csv","content":"a,b"}}' ".claude\hooks\guard_scope.py" "データセット" 2
Test-HookMsg "guard_bash: data/ block message names dataset" '{"tool_input":{"command":"cp evil.csv data/train.csv"}}' ".claude\hooks\guard_bash.py" "データセット" 2
Test-HookMsg "guard_scope: hooks block message stays hook-specific" '{"tool_input":{"file_path":".claude/hooks/guard_scope.py","content":"x"}}' ".claude\hooks\guard_scope.py" "フック/設定" 2
# symlink 迂回(dlink -> data 経由の書き込み)も realpath 照合でブロックする。
# 中断残りの fixture(symlink)は削除してから作り直す(残骸を「symlink を
# 作れない環境」と誤認して恒久スキップしないため)。symlink 以外が同名で
# 存在する場合は誤削除を避けて NG にする(スキップで隠さない)。
# Windows のシンボリックリンク作成には開発者モード/管理者権限が必要なため、
# 作れない環境ではスキップする
$dlinkExisting = Get-Item "verify_dlink_fixture" -Force -ErrorAction SilentlyContinue
if ($dlinkExisting -and -not $dlinkExisting.LinkType) {
    Write-Host "NG: verify_dlink_fixture の位置に symlink 以外のファイルが存在します(手動で退避してください)"
    $script:failed++
} else {
    Remove-Item "verify_dlink_fixture" -Force -ErrorAction SilentlyContinue
    if (Get-Item "verify_dlink_fixture" -Force -ErrorAction SilentlyContinue) {
        # 削除に失敗した残骸を「symlink を作れない環境」と誤認して SKIP しない
        Write-Host "NG: verify_dlink_fixture の残骸を削除できません(手動で削除してください)"
        $script:failed++
    } else {
        $dlink = New-Item -ItemType SymbolicLink -Path "verify_dlink_fixture" -Target "data" -ErrorAction SilentlyContinue
        if ($dlink) {
            try {
                Test-Hook "guard_scope: symlinked data/ write is blocked" '{"tool_input":{"file_path":"verify_dlink_fixture/train.csv","content":"a,b"}}' ".claude\hooks\guard_scope.py" 2
                Test-Hook "guard_bash: cp via symlinked data/ is blocked" '{"tool_input":{"command":"cp evil.csv verify_dlink_fixture/train.csv"}}' ".claude\hooks\guard_bash.py" 2
            } finally {
                Remove-Item "verify_dlink_fixture" -Force -ErrorAction SilentlyContinue
            }
        } else {
            Write-Host "SKIP: symlink を作成できないため symlink 迂回テストをスキップします"
        }
    }
}

# --- guard_scope: worktree封じ込め(cwdベース。$RP はテスト実行時のリポジトリ絶対パス) ---
$RP = (Get-Location).Path
$RPJson = $RP.Replace('\', '\\')
Test-Hook "guard_scope: worktree封じ込め - 同worktree内は許可" "{`"cwd`":`"$RPJson/.worktrees/group-A`",`"tool_input`":{`"file_path`":`"$RPJson/.worktrees/group-A/src/foo.py`"}}" ".claude\hooks\guard_scope.py" 0
Test-Hook "guard_scope: worktree封じ込め - worktree→メインはブロック" "{`"cwd`":`"$RPJson/.worktrees/group-A`",`"tool_input`":{`"file_path`":`"$RPJson/src/train.py`"}}" ".claude\hooks\guard_scope.py" 2
Test-Hook "guard_scope: worktree封じ込め - メイン→worktreeは現状維持で許可" "{`"cwd`":`"$RPJson`",`"tool_input`":{`"file_path`":`"$RPJson/.worktrees/group-A/src/foo.py`"}}" ".claude\hooks\guard_scope.py" 0
Test-Hook "guard_scope: worktree封じ込め - 前方一致の隣接名(group-AB)はブロック" "{`"cwd`":`"$RPJson/.worktrees/group-A`",`"tool_input`":{`"file_path`":`"$RPJson/.worktrees/group-AB/src/foo.py`"}}" ".claude\hooks\guard_scope.py" 2
Test-Hook "guard_scope: worktree封じ込め - worktree内サブディレクトリcwdでもブロック" "{`"cwd`":`"$RPJson/.worktrees/group-A/src`",`"tool_input`":{`"file_path`":`"$RPJson/src/train.py`"}}" ".claude\hooks\guard_scope.py" 2
Test-Hook "guard_scope: worktree封じ込め - 不正cwd型(数値)はフォールバックで許可" "{`"cwd`":12345,`"tool_input`":{`"file_path`":`"$RPJson/src/train.py`"}}" ".claude\hooks\guard_scope.py" 0
Test-Hook "guard_scope: worktree封じ込め - 相対パスはペイロードcwd基準で解決し許可" "{`"cwd`":`"$RPJson/.worktrees/group-A`",`"tool_input`":{`"file_path`":`"src/foo.py`"}}" ".claude\hooks\guard_scope.py" 0
Test-Hook "guard_scope: worktree封じ込め - 相対パスでのworktree脱出はブロック" "{`"cwd`":`"$RPJson/.worktrees/group-A`",`"tool_input`":{`"file_path`":`"../../src/train.py`"}}" ".claude\hooks\guard_scope.py" 2

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
# guard_bash はスコープ判定に tempfile.gettempdir() の例外を持つため、リポジトリが
# 一時ディレクトリ配下にあると ../other-project も「許可」と判定されてこのケースだけ
# 必ず落ちる(実測)。テスト側の環境依存なので、その場合はスキップする。
# 末尾に区切り文字を付けて比較する。付けないと Temp が C:\Temp のとき
# C:\Temporary\repo までスキップ扱いになる(sh 側の "$TMP_ROOT"/* は
# 区切りを要求するため、付けないと1対1対応が崩れる)
$TmpRoot = [System.IO.Path]::GetTempPath().TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
if (((Get-Location).Path.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar).StartsWith($TmpRoot, [StringComparison]::OrdinalIgnoreCase)) {
    Write-Host "SKIP: guard_bash: rm -rf relative out-of-scope is blocked(リポジトリが一時ディレクトリ配下のため)"
} else {
    Test-Hook "guard_bash: rm -rf relative out-of-scope is blocked" '{"tool_input":{"command":"rm -rf ../other-project"}}' ".claude\hooks\guard_bash.py" 2
}
Test-Hook "guard_bash: touch settings.json is blocked" '{"tool_input":{"command":"touch .claude/settings.json"}}' ".claude\hooks\guard_bash.py" 2

Test-Hook "enforce_eval: no flag passes" '{}' ".claude\hooks\enforce_eval.py" 0
# セッションが CLAUDE_QUALITY_GATE=1 を注入していても素の状態をテストできるよう明示的に外す
$savedQualityGate = $env:CLAUDE_QUALITY_GATE
Remove-Item Env:CLAUDE_QUALITY_GATE -ErrorAction SilentlyContinue
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
'{}' | uv run python ".claude\hooks\quality_gate.py" *> $null
$ErrorActionPreference = $prevEAP
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK: quality_gate: off when flag not set (exit 0)"
} else {
    Write-Host "NG: quality_gate: off when flag not set (expected 0)"
    $script:failed++
}
if ($null -ne $savedQualityGate) { $env:CLAUDE_QUALITY_GATE = $savedQualityGate }
# --- quality_gate: diff カバレッジ検査(一時 git リポジトリを CLAUDE_WORK_SCOPE に向けて検証。
#     リポジトリ本体を対象にすると既存コードの lint 結果でテストが揺れるため) ---
$AbsQualityGate = (Resolve-Path ".claude\hooks\quality_gate.py").Path
$QgTmp = Join-Path ([System.IO.Path]::GetTempPath()) ("quality-gate-test-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $QgTmp | Out-Null
Push-Location $QgTmp
git init -q -b main .
git config user.email test@test
git config user.name test
git commit -q --allow-empty -m init
Pop-Location
$OrigWorkScope = $env:CLAUDE_WORK_SCOPE
$env:CLAUDE_WORK_SCOPE = $QgTmp

# セッションが CLAUDE_QUALITY_GATE=1 / CLAUDE_DIFF_COVERAGE=1 を注入していても
# 素の状態からテストできるよう、直前ブロック(202-215行)と同じ save→restore パターンで退避する
$savedQualityGate = $env:CLAUDE_QUALITY_GATE
$savedDiffCoverage = $env:CLAUDE_DIFF_COVERAGE
$env:CLAUDE_QUALITY_GATE = "1"
Remove-Item Env:CLAUDE_DIFF_COVERAGE -ErrorAction SilentlyContinue
Remove-Item Env:CLAUDE_DIFF_COVERAGE_MIN -ErrorAction SilentlyContinue
Push-Location $QgTmp
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
'{}' | uv run python $AbsQualityGate *> $null
$ErrorActionPreference = $prevEAP
$actual = $LASTEXITCODE
Pop-Location
if ($actual -eq 0) {
    Write-Host "OK: quality_gate: diff coverage off when CLAUDE_DIFF_COVERAGE is unset (exit 0)"
} else {
    Write-Host "NG: quality_gate: diff coverage off when CLAUDE_DIFF_COVERAGE is unset (expected 0)"
    $script:failed++
}

$env:CLAUDE_DIFF_COVERAGE = "1"
Remove-Item Env:CLAUDE_DIFF_COVERAGE_MIN -ErrorAction SilentlyContinue
Push-Location $QgTmp
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
'{}' | uv run python $AbsQualityGate *> $null
$ErrorActionPreference = $prevEAP
$actual = $LASTEXITCODE
Pop-Location
if ($actual -eq 0) {
    Write-Host "OK: quality_gate: diff coverage skips when tools are missing (exit 0)"
} else {
    Write-Host "NG: quality_gate: diff coverage skips when tools are missing (expected 0)"
    $script:failed++
}

$env:CLAUDE_WORK_SCOPE = $OrigWorkScope
$env:CLAUDE_QUALITY_GATE = $savedQualityGate
$env:CLAUDE_DIFF_COVERAGE = $savedDiffCoverage
Remove-Item -Recurse -Force $QgTmp
# セッションが CLAUDE_NOTIFY=1 を注入していても素の状態をテストできるよう明示的に外す
# (CLAUDE_CONTROL_LEVEL=L3 も通知ONと解釈されるため同様に外す)
$savedNotify = $env:CLAUDE_NOTIFY
$savedControlLevel = $env:CLAUDE_CONTROL_LEVEL
Remove-Item Env:CLAUDE_NOTIFY -ErrorAction SilentlyContinue
Remove-Item Env:CLAUDE_CONTROL_LEVEL -ErrorAction SilentlyContinue
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
'{}' | uv run python ".claude\hooks\notify.py" *> $null
$ErrorActionPreference = $prevEAP
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK: notify: off when flag not set (exit 0)"
} else {
    Write-Host "NG: notify: off when flag not set (expected 0)"
    $script:failed++
}
if ($null -ne $savedNotify) { $env:CLAUDE_NOTIFY = $savedNotify }
if ($null -ne $savedControlLevel) { $env:CLAUDE_CONTROL_LEVEL = $savedControlLevel }
# セッションが CLAUDE_CROSS_REVIEW=1 を注入していても素の状態をテストできるよう明示的に外す
$savedCrossReview = $env:CLAUDE_CROSS_REVIEW
Remove-Item Env:CLAUDE_CROSS_REVIEW -ErrorAction SilentlyContinue
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
'{}' | uv run python ".claude\hooks\codex_gate.py" *> $null
$ErrorActionPreference = $prevEAP
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
    # PowerShell 5.1 は $ErrorActionPreference = "Stop" の下でネイティブコマンドが
    # stderr に出力すると終了エラーに変換する。codex_gate はブロック時に stderr へ
    # 出すため、Test-Hook(L17-20)と同じく一時的に Continue へ落とす
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    '{}' | uv run python $AbsCodexGate *> $null
    $ErrorActionPreference = $prevEAP
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
'@ | Write-Utf8NoBom -Path "$SpecFixture\docs\design.md"

        @'
# フィクスチャ設計書(壊れたテーブル)

## 受け入れ条件

| ID | 要件 | 検証方法 | 期待結果 | 種別 |
|---|---|---|---|---|
| R-001 | ダミー要件1 | python -c "pass" | exit 0 | auto |
'@ | Write-Utf8NoBom -Path "$SpecFixture\docs_bad\design.md"

        @'
| ID | 判定 | 実行コマンド | 実測値 | 証拠 |
|---|---|---|---|---|
| R-001 | PASS | python -c "..." | 0 | test.py:1 |
| R-002 | PASS | (目視) | - | test.py:2 |
| R-003 | PASS | python -c "..." | 0 | test.py:3 |
'@ | Write-Utf8NoBom -Path "$SpecFixture\spec\verdict-design.md"

        @'
| ID | 結果 | 備考 |
|---|---|---|
| R-001 | OK | ok |
| R-002 | OK | ok |
| R-003 | OK | ok |
'@ | Write-Utf8NoBom -Path "$SpecFixture\spec\audit-design.md"

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
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        uv run python $AbsSpecApprove R-002 --docs "$SpecFixture\docs" --spec-dir "$SpecFixture\spec" *> $null
        $ErrorActionPreference = $prevEAP
        Test-SpecGate "spec_approve後: R-105/R-101 全要件PASSで通過" 0 "$SpecFixture\docs" "$SpecFixture\spec" @{ CLAUDE_SPEC_CHECK = "1" }

        # 設計書ハッシュ: verdict/audit/approvals が揃っていても design_hashes.txt が
        # 無ければブロック(計画承認の強制)
        New-Item -ItemType Directory -Path "$SpecFixture\spec_nohash" -Force | Out-Null
        Copy-Item "$SpecFixture\spec\verdict-design.md" "$SpecFixture\spec_nohash\verdict-design.md"
        Copy-Item "$SpecFixture\spec\audit-design.md" "$SpecFixture\spec_nohash\audit-design.md"
        "design R-002 2026-01-01T00:00:00" | Write-Utf8NoBom -Path "$SpecFixture\spec_nohash\approvals.txt"
        Test-SpecGate "spec_gate 設計書ハッシュ: 計画承認記録なしはブロック" 2 "$SpecFixture\docs" "$SpecFixture\spec_nohash" @{ CLAUDE_SPEC_CHECK = "1" }

        # 設計書ハッシュ: 承認後に設計書が改変されたらブロック
        New-Item -ItemType Directory -Path "$SpecFixture\docs_tamper" -Force | Out-Null
        New-Item -ItemType Directory -Path "$SpecFixture\spec_tamper" -Force | Out-Null
        Copy-Item "$SpecFixture\docs\design.md" "$SpecFixture\docs_tamper\design.md"
        Copy-Item "$SpecFixture\spec\verdict-design.md" "$SpecFixture\spec_tamper\verdict-design.md"
        Copy-Item "$SpecFixture\spec\audit-design.md" "$SpecFixture\spec_tamper\audit-design.md"
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        uv run python $AbsSpecApprove R-002 --docs "$SpecFixture\docs_tamper" --spec-dir "$SpecFixture\spec_tamper" *> $null
        $ErrorActionPreference = $prevEAP
        Test-SpecGate "spec_gate 設計書ハッシュ: 承認直後は通過" 0 "$SpecFixture\docs_tamper" "$SpecFixture\spec_tamper" @{ CLAUDE_SPEC_CHECK = "1" }
        Add-Content -Path "$SpecFixture\docs_tamper\design.md" -Value "`n(tampered after approval)"
        Test-SpecGate "spec_gate 設計書ハッシュ: 承認後の改変はブロック" 2 "$SpecFixture\docs_tamper" "$SpecFixture\spec_tamper" @{ CLAUDE_SPEC_CHECK = "1" }
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        uv run python $AbsSpecApprove --design design --docs "$SpecFixture\docs_tamper" --spec-dir "$SpecFixture\spec_tamper" *> $null
        $ErrorActionPreference = $prevEAP
        Test-SpecGate "spec_gate 設計書ハッシュ: --design 再承認で通過" 0 "$SpecFixture\docs_tamper" "$SpecFixture\spec_tamper" @{ CLAUDE_SPEC_CHECK = "1" }

        # R-108: CLAUDE_SPEC_RECHECK_N=all で auto要件が全件再実行される(ログに全ID)
        $env:CLAUDE_SPEC_CHECK = "1"
        $env:CLAUDE_SPEC_RECHECK_N = "all"
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        '{}' | uv run python $AbsSpecGate --docs "$SpecFixture\docs" --spec-dir "$SpecFixture\spec" *> "$SpecFixture\recheck_all.txt"
        $ErrorActionPreference = $prevEAP
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
'@ | Write-Utf8NoBom -Path "$SpecFixture\spec_fail\verdict-design.md"
        Copy-Item "$SpecFixture\spec\audit-design.md" "$SpecFixture\spec_fail\audit-design.md"
        "design R-002 2026-01-01T00:00:00" | Write-Utf8NoBom -Path "$SpecFixture\spec_fail\approvals.txt"
        Test-SpecGate "spec_gate R-102: FAIL要件があればブロック" 2 "$SpecFixture\docs" "$SpecFixture\spec_fail" @{ CLAUDE_SPEC_CHECK = "1" }

        # R-103: verdict ファイルに要件IDの欠けがあればブロック
        New-Item -ItemType Directory -Path "$SpecFixture\spec_missing" -Force | Out-Null
        @'
| ID | 判定 | 実行コマンド | 実測値 | 証拠 |
|---|---|---|---|---|
| R-001 | PASS | python -c "..." | 0 | test.py:1 |
| R-002 | PASS | (目視) | - | test.py:2 |
'@ | Write-Utf8NoBom -Path "$SpecFixture\spec_missing\verdict-design.md"
        Copy-Item "$SpecFixture\spec\audit-design.md" "$SpecFixture\spec_missing\audit-design.md"
        "design R-002 2026-01-01T00:00:00" | Write-Utf8NoBom -Path "$SpecFixture\spec_missing\approvals.txt"
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
"@ | Write-Utf8NoBom -Path "$SpecFixture\docs_cov\design.md"
            @'
| ID | 判定 | 実行コマンド | 実測値 | 証拠 |
|---|---|---|---|---|
| R-001 | PASS | python -c "..." | 0 | test.py:1 |
'@ | Write-Utf8NoBom -Path "$SpecFixture\spec_cov\verdict-design.md"
            @'
| ID | 結果 | 備考 |
|---|---|---|
| R-001 | OK | ok |
'@ | Write-Utf8NoBom -Path "$SpecFixture\spec_cov\audit-design.md"

            Push-Location "$SpecFixture\covdir"
            $env:CLAUDE_SPEC_CHECK = "1"
            $prevEAP = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            '{}' | uv run python $AbsSpecGate --docs "$SpecFixture\docs_cov" --spec-dir "$SpecFixture\spec_cov" *> "out_cov.txt"
            $ErrorActionPreference = $prevEAP
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

# --- action_log / agent_log: 空ペイロードでも exit 0(記録失敗で作業を止めない) ---
Test-Hook "action_log: exits 0 on empty payload" '{}' ".claude\hooks\action_log.py" 0
Test-Hook "agent_log: exits 0 on empty payload" '{}' ".claude\hooks\agent_log.py" 0

# --- plan_gate: 一時ディレクトリで検証(検査対象がブランチ名から決まる新仕様に合わせ、
#     各ケースを git リポジトリ + ブランチ名に対応する計画ファイルで組み立てる)。
# $ErrorActionPreference = "Stop" が有効なため、途中の例外でも Pop-Location /
# 一時ディレクトリ削除に必ず到達するよう try/finally で保護する。
$AbsPlanGate = Join-Path (Get-Location).Path ".claude\hooks\plan_gate.py"

function Test-PlanGate {
    param(
        [string]$Description,
        [string]$Branch,
        [string]$PlanName,
        [string]$PlanText,
        [string]$InvText,
        [int]$ExpectedExit
    )
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("plan-gate-case-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        git -C $tmp init -q -b $Branch
        if ($PlanName -ne "") {
            $cl = Join-Path $tmp ".claude"
            $pl = Join-Path $cl "plans"
            New-Item -ItemType Directory -Path $pl -Force | Out-Null
            $PlanText | Write-Utf8NoBom -Path (Join-Path $pl $PlanName) -NoNewline
            if ($InvText -ne "") {
                $inv = Join-Path $cl "improvements"
                New-Item -ItemType Directory -Path $inv -Force | Out-Null
                $InvText | Write-Utf8NoBom -Path (Join-Path $inv "invariants.md") -NoNewline
            }
        }
        Push-Location $tmp
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        '{}' | uv run python $AbsPlanGate *> $null
        $actual = $LASTEXITCODE
        $ErrorActionPreference = $prevEAP
        Pop-Location
    } finally {
        Remove-Item -Path $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($actual -eq $ExpectedExit) {
        Write-Host "OK: $Description (exit $actual)"
    } else {
        Write-Host "NG: $Description (expected $ExpectedExit, got $actual)"
        $script:failed++
    }
}

Test-PlanGate "plan_gate: passes when .claude/plans directory is absent" `
    "pipeline/20260726-vh-a" "" "" "" 0

Test-PlanGate "plan_gate: passes when no plan file matches the branch" `
    "pipeline/20260726-vh-b" "20260726-other.md" "別ブランチ向けの計画メモ。`n" "" 0

Test-PlanGate "plan_gate: passes when experiment: false is declared" `
    "pipeline/20260726-vh-c" "20260726-vh-c.md" "experiment: false`n" "" 0

Test-PlanGate "plan_gate: blocks when experimental language is present but goal is undefined" `
    "pipeline/20260726-vh-d" "20260726-vh-d.md" "学習ジョブを新しいデータセットで実行する。`n" "" 2

$PgEText = "cost_estimate:`n  train_minutes: 1e3`n  epochs: 30`n  dataset_gb: 2.4`n  parallel_jobs: 1`ngoal:`n  metric: rmse`n  target: 0.15`n  direction: minimize`n  baseline: 0.21`n  guard_metrics: []`n"
Test-PlanGate "plan_gate: blocks when train_minutes is unreadable as a decimal (1e3)" `
    "pipeline/20260726-vh-e" "20260726-vh-e.md" $PgEText "" 2

$PgFText = "cost_estimate:`n  train_minutes: 999`n  epochs: 30`n  dataset_gb: 2.4`n  parallel_jobs: 1`ngoal:`n  metric: rmse`n  target: 0.15`n  direction: minimize`n  baseline: 0.21`n  guard_metrics: []`n"
$PgFInv = "resources:`n  max_train_minutes: 120`n  max_epochs: 100`n  max_dataset_gb: 10`n  max_parallel_jobs: 1`n"
Test-PlanGate "plan_gate: blocks when train_minutes exceeds the resource limit" `
    "pipeline/20260726-vh-f" "20260726-vh-f.md" $PgFText $PgFInv 2

# --- tdd: テスト改変ゲート(CLAUDE_TDD_GATE)。R-002〜R-012・R-016・R-017 ---
# 実物は叩かず、一時ディレクトリの .claude\hooks\ に写しを置いて実行する
# (パス解決がフック自身の配置基準のため、実物を叩くと実リポジトリの
# .claude\checkpoints\ を汚す。PC-19 の番人)。写し元は2経路:
# staging(_staging_tdd_gate.py --root --hooks-only)があればそれを適用し、
# 無ければ追跡済み .claude\hooks\tdd_*.py を写す。どちらも無ければ SKIP する。
$TddStaging = Join-Path (Get-Location) "_staging_tdd_gate.py"
$TddTrackedGateHook = Join-Path (Get-Location) ".claude\hooks\tdd_gate.py"
$TddTmp = Join-Path ([System.IO.Path]::GetTempPath()) ("tdd-gate-test-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path (Join-Path $TddTmp ".claude\hooks") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $TddTmp ".claude\checkpoints") -Force | Out-Null
$TddAvailable = $false
# $ErrorActionPreference = "Stop" が有効なため、tdd 区間内の Move-Item/Copy-Item 等が
# 途中で失敗しても Pop-Location・一時ディレクトリ削除・失敗集計への到達を保証するよう
# 区間全体を try/finally で保護する(前例: SpecFixture 区間・Test-PlanGate)。
try {
if (Test-Path $TddStaging) {
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    uv run python $TddStaging --root $TddTmp --hooks-only *> $null
    $TddStagingExit = $LASTEXITCODE
    $ErrorActionPreference = $prevEAP
    if ($TddStagingExit -eq 0) { $TddAvailable = $true }
} elseif (Test-Path $TddTrackedGateHook) {
    $TddSrcHooksDir = Join-Path (Get-Location) ".claude\hooks"
    foreach ($name in @("tdd_red.py", "tdd_gate.py", "tdd_unlock.py")) {
        Copy-Item (Join-Path $TddSrcHooksDir $name) (Join-Path $TddTmp ".claude\hooks\$name")
    }
    $TddAvailable = $true
}

if (-not $TddAvailable) {
    Write-Host "SKIP: tdd テスト改変ゲート(staging も追跡済みフックも無いためスキップ)"
} else {
    $TddRed = Join-Path $TddTmp ".claude\hooks\tdd_red.py"
    $TddGate = Join-Path $TddTmp ".claude\hooks\tdd_gate.py"
    $TddUnlock = Join-Path $TddTmp ".claude\hooks\tdd_unlock.py"
    $TddBlocksLog = Join-Path $TddTmp ".claude\checkpoints\tdd_gate_blocks.log"
    $TddSentinel = Join-Path $TddTmp ".claude\checkpoints\tdd_red.json"
    New-Item -ItemType Directory -Path (Join-Path $TddTmp "tests") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $TddTmp "src") -Force | Out-Null
    "def test_x():`n    assert False`n" | Write-Utf8NoBom -Path (Join-Path $TddTmp "tests\test_x.py") -NoNewline
    "def test_y():`n    assert True`n" | Write-Utf8NoBom -Path (Join-Path $TddTmp "tests\test_y.py") -NoNewline
    "x = 1`n" | Write-Utf8NoBom -Path (Join-Path $TddTmp "src\train.py") -NoNewline

    function Set-TddCommand {
        param([string]$NewCmd)
        $pyScript = @'
import json
import sys

path, newcmd = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as f:
    data = json.load(f)
data["test_command"] = newcmd
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f)
'@
        $tmpPy = Join-Path $TddTmp "_set_tdd_command.py"
        $pyScript | Write-Utf8NoBom -Path $tmpPy
        uv run python $tmpPy $TddSentinel $NewCmd | Out-Null
        Remove-Item $tmpPy -ErrorAction SilentlyContinue
    }

    function Test-TddGate {
        param([string]$Description, [string]$JsonInput, [int]$ExpectedExit, [string]$GateEnv)
        Push-Location $TddTmp
        if ($GateEnv -eq "") {
            $env:CLAUDE_TDD_GATE = ""
        } else {
            $env:CLAUDE_TDD_GATE = $GateEnv
        }
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $JsonInput | uv run python $TddGate *> $null
        $ErrorActionPreference = $prevEAP
        $actual = $LASTEXITCODE
        Remove-Item Env:CLAUDE_TDD_GATE -ErrorAction SilentlyContinue
        Pop-Location
        if ($actual -eq $ExpectedExit) {
            Write-Host "OK: $Description (exit $actual)"
        } else {
            Write-Host "NG: $Description (expected $ExpectedExit, got $actual)"
            $script:failed++
        }
    }

    # R-002: 失敗するコマンドで記録するとセンチネル・失敗ログができる
    Push-Location $TddTmp
    uv run python $TddRed --cmd 'uv run python -c "import sys; sys.exit(1)"' --files tests/test_x.py | Out-Null
    Pop-Location
    if (Test-Path $TddSentinel) {
        Write-Host "OK: tdd_red: 失敗コマンドでセンチネルを記録する"
    } else {
        Write-Host "NG: tdd_red: 失敗コマンドでセンチネルを記録する"
        $script:failed++
    }

    # R-003: 緑コマンドはセンチネルを作らない(既存センチネルは退避してから確認)
    $TddSentinelBak = "$TddSentinel.bak"
    Move-Item $TddSentinel $TddSentinelBak
    Push-Location $TddTmp
    uv run python $TddRed --cmd 'uv run python -c "import sys; sys.exit(0)"' --files tests/test_x.py | Out-Null
    Pop-Location
    if (-not (Test-Path $TddSentinel)) {
        Write-Host "OK: tdd_red: 緑コマンドはセンチネルを作らない"
    } else {
        Write-Host "NG: tdd_red: 緑コマンドはセンチネルを作らない"
        $script:failed++
    }
    Move-Item $TddSentinelBak $TddSentinel -Force

    # R-004: --files 省略は非0終了
    Push-Location $TddTmp
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    uv run python $TddRed --cmd 'uv run python -c "import sys; sys.exit(1)"' *> $null
    $TddRedExit = $LASTEXITCODE
    $ErrorActionPreference = $prevEAP
    Pop-Location
    if ($TddRedExit -ne 0) {
        Write-Host "OK: tdd_red: --files 省略は非0終了"
    } else {
        Write-Host "NG: tdd_red: --files 省略は非0終了"
        $script:failed++
    }

    # R-005: ゲート有効+記録済みテストファイル(file_path・notebook_path とも)はブロック
    Test-TddGate "tdd_gate: recorded test file is blocked" '{"tool_input":{"file_path":"tests/test_x.py"}}' 2 "1"
    Test-TddGate "tdd_gate: recorded test via notebook_path is blocked" '{"tool_input":{"notebook_path":"tests/test_x.py"}}' 2 "1"
    # 過剰ブロック無し: 無関係ソース・記録に無いテストは通す
    Test-TddGate "tdd_gate: unrelated source passes" '{"tool_input":{"file_path":"src/train.py"}}' 0 "1"
    Test-TddGate "tdd_gate: unrecorded test file passes" '{"tool_input":{"file_path":"tests/test_y.py"}}' 0 "1"
    # R-007: env off は常に素通り
    Test-TddGate "tdd_gate: env empty string passes" '{"tool_input":{"file_path":"tests/test_x.py"}}' 0 ""
    Test-TddGate "tdd_gate: env=0 passes" '{"tool_input":{"file_path":"tests/test_x.py"}}' 0 "0"
    # R-006: 表記変形(絶対パス・冗長表記)でも判定不変
    $TddAbsJson = '{"tool_input":{"file_path":"' + ($TddTmp -replace '\\', '/') + '/tests/test_x.py"}}'
    Test-TddGate "tdd_gate: absolute path is blocked" $TddAbsJson 2 "1"
    Test-TddGate "tdd_gate: redundant notation is blocked" '{"tool_input":{"file_path":"./tests/../tests/test_x.py"}}' 2 "1"
    # symlink 迂回(既存の symlink ケースと同じ書式: 残骸検査つき)
    $TddLinkPath = Join-Path $TddTmp "tests_link"
    if ((Test-Path $TddLinkPath) -and -not ((Get-Item $TddLinkPath).LinkType)) {
        Write-Host "NG: tdd_gate: tests_link の位置に symlink 以外のファイルが存在します(手動で退避してください)"
        $script:failed++
    } else {
        Remove-Item $TddLinkPath -Force -ErrorAction SilentlyContinue
        $TddLinkCreated = $false
        try {
            New-Item -ItemType SymbolicLink -Path $TddLinkPath -Target (Join-Path $TddTmp "tests") -ErrorAction Stop | Out-Null
            $TddLinkCreated = $true
        } catch {
            $TddLinkCreated = $false
        }
        if ($TddLinkCreated) {
            Test-TddGate "tdd_gate: symlinked path to recorded test is blocked" '{"tool_input":{"file_path":"tests_link/test_x.py"}}' 2 "1"
            Remove-Item $TddLinkPath -Force -ErrorAction SilentlyContinue
        } else {
            Write-Host "SKIP: tdd symlink 迂回テストをスキップします(symlink を作成できない環境)"
        }
    }

    # R-009: 壊れたセンチネル(不正JSON)は fail-closed で無関係ソースも含め全編集ブロック
    Copy-Item $TddSentinel $TddSentinelBak -Force
    "{not json" | Write-Utf8NoBom -Path $TddSentinel -NoNewline
    Test-TddGate "tdd_gate: broken sentinel (invalid json) blocks unrelated source too" '{"tool_input":{"file_path":"src/train.py"}}' 2 "1"
    Push-Location $TddTmp
    $env:CLAUDE_TDD_GATE = "1"
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $TddBrokenMsg = '{"tool_input":{"file_path":"src/train.py"}}' | uv run python $TddGate 2>&1
    $ErrorActionPreference = $prevEAP
    Remove-Item Env:CLAUDE_TDD_GATE -ErrorAction SilentlyContinue
    Pop-Location
    $TddBrokenMsgText = ($TddBrokenMsg | Out-String)
    if ($TddBrokenMsgText -match "全編集を停止中" -and $TddBrokenMsgText -notmatch "Traceback") {
        Write-Host "OK: tdd_gate: 壊れたセンチネルの案内文に脱出路が含まれ traceback が無い"
    } else {
        Write-Host "NG: tdd_gate: 壊れたセンチネルの案内文に脱出路が含まれ traceback が無い"
        $script:failed++
    }
    Move-Item $TddSentinelBak $TddSentinel -Force

    # R-010: blocks.log がブロックのたびに増える
    $TddBeforeLines = 0
    if (Test-Path $TddBlocksLog) { $TddBeforeLines = (Get-Content $TddBlocksLog).Count }
    Push-Location $TddTmp
    $env:CLAUDE_TDD_GATE = "1"
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    '{"tool_input":{"file_path":"tests/test_x.py"}}' | uv run python $TddGate *> $null
    $ErrorActionPreference = $prevEAP
    Remove-Item Env:CLAUDE_TDD_GATE -ErrorAction SilentlyContinue
    Pop-Location
    $TddAfterLines = (Get-Content $TddBlocksLog).Count
    if ($TddAfterLines -eq ($TddBeforeLines + 1)) {
        Write-Host "OK: tdd_gate: ブロックのたびに blocks.log が1行増える"
    } else {
        Write-Host "NG: tdd_gate: ブロックのたびに blocks.log が1行増える(before=$TddBeforeLines after=$TddAfterLines)"
        $script:failed++
    }

    # R-011: 検証つき解除(赤のままは非0でセンチネル保持、緑になれば0で削除)
    Push-Location $TddTmp
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    uv run python $TddUnlock *> $null
    $TddUnlockExit = $LASTEXITCODE
    $ErrorActionPreference = $prevEAP
    Pop-Location
    if ($TddUnlockExit -ne 0 -and (Test-Path $TddSentinel)) {
        Write-Host "OK: tdd_unlock: 赤のままは非0終了でセンチネルを保持する"
    } else {
        Write-Host "NG: tdd_unlock: 赤のままは非0終了でセンチネルを保持する"
        $script:failed++
    }
    Set-TddCommand 'uv run python -c "import sys; sys.exit(0)"'
    Push-Location $TddTmp
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    uv run python $TddUnlock *> $null
    $TddUnlockExit2 = $LASTEXITCODE
    $ErrorActionPreference = $prevEAP
    Pop-Location
    if ($TddUnlockExit2 -eq 0 -and -not (Test-Path $TddSentinel)) {
        Write-Host "OK: tdd_unlock: 緑になれば解除してセンチネルを削除する"
    } else {
        Write-Host "NG: tdd_unlock: 緑になれば解除してセンチネルを削除する"
        $script:failed++
    }

    # 記録 cwd での解除(sub ディレクトリで記録し、リポジトリルートから解除しても
    # 記録された cwd(sub)で再実行される)
    $TddSubDir = Join-Path $TddTmp "sub"
    New-Item -ItemType Directory -Path (Join-Path $TddSubDir "tests") -Force | Out-Null
    "def test_rel():`n    assert False`n" | Write-Utf8NoBom -Path (Join-Path $TddSubDir "tests\test_rel.py") -NoNewline
    Push-Location $TddSubDir
    uv run python $TddRed --cmd 'uv run python -c "import sys; sys.exit(1)"' --files tests/test_rel.py | Out-Null
    Pop-Location
    # cmd.exe/sh どちらの shell=True でも解釈できるよう、cwd 依存の判定は
    # basename 文字列処理ではなく相対パスの存在確認にする(record 時の
    # ディレクトリでのみ tests/test_rel.py が解決できる)
    Set-TddCommand 'uv run python -c "import os,sys; sys.exit(0 if os.path.exists(''tests/test_rel.py'') else 1)"'
    Push-Location $TddTmp
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    uv run python $TddUnlock *> $null
    $TddUnlockExit3 = $LASTEXITCODE
    $ErrorActionPreference = $prevEAP
    Pop-Location
    if ($TddUnlockExit3 -eq 0 -and -not (Test-Path $TddSentinel)) {
        Write-Host "OK: tdd_unlock: 記録された実行ディレクトリ(recorded_cwd)で再実行される"
    } else {
        Write-Host "NG: tdd_unlock: 記録された実行ディレクトリ(recorded_cwd)で再実行される"
        $script:failed++
    }

    # サブディレクトリ起動でも同一センチネルを参照する(ルート直下にしか
    # .claude\checkpoints\ が作られない)
    $TddSrcSub = Join-Path $TddTmp "src_sub"
    New-Item -ItemType Directory -Path $TddSrcSub -Force | Out-Null
    Push-Location $TddSrcSub
    uv run python $TddRed --cmd 'uv run python -c "import sys; sys.exit(1)"' --files ../tests/test_x.py | Out-Null
    Pop-Location
    if ((Test-Path $TddSentinel) -and -not (Test-Path (Join-Path $TddSrcSub ".claude"))) {
        Write-Host "OK: tdd_red: サブディレクトリ起動でもリポジトリルート直下のセンチネルを参照する"
    } else {
        Write-Host "NG: tdd_red: サブディレクトリ起動でもリポジトリルート直下のセンチネルを参照する"
        $script:failed++
    }

    # R-012: --rearm はセンチネルを削除し blocks.log に rearm を記録する
    $TddBeforeLines2 = (Get-Content $TddBlocksLog).Count
    Push-Location $TddTmp
    uv run python $TddRed --rearm | Out-Null
    Pop-Location
    $TddAfterLines2 = (Get-Content $TddBlocksLog).Count
    $TddLastLine = (Get-Content $TddBlocksLog)[-1]
    if (-not (Test-Path $TddSentinel) -and ($TddAfterLines2 -eq ($TddBeforeLines2 + 1)) -and ($TddLastLine -match "rearm")) {
        Write-Host "OK: tdd_red: --rearm はセンチネルを削除し rearm を記録する"
    } else {
        Write-Host "NG: tdd_red: --rearm はセンチネルを削除し rearm を記録する"
        $script:failed++
    }
}
} finally {
    Remove-Item -Path $TddTmp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
$env:CLAUDE_WORK_SCOPE = $SavedWorkScope
if ($script:failed -gt 0) {
    Write-Host "$($script:failed) 件のテストが失敗しました"
    exit 1
} else {
    Write-Host "全テストPASS"
    exit 0
}
