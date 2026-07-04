param()

$ErrorActionPreference = "Stop"

# 前提ツールの確認
foreach ($tool in @("uv", "git")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host "エラー: '$tool' が見つかりません。インストールしてから再実行してください。"
        exit 1
    }
}

$TemplateRepo = "https://github.com/takayoshitoyoda05/claude-ml-template.git"

if (Test-Path ".claude") {
    $ans = Read-Host ".claude が既に存在します。上書きしますか? [y/N]"
    if ($ans -notmatch "^[Yy]$") {
        Write-Host "中止しました"
        exit 1
    }
}

$Tmp = Join-Path $env:TEMP ([System.Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $Tmp | Out-Null

try {
    Write-Host "テンプレートを取得中..."
    git clone --depth 1 --quiet $TemplateRepo $Tmp

    # plans/ はプロジェクト固有・実行履歴なので展開しない(claude-update.ps1と同じ対象)
    New-Item -ItemType Directory -Path ".claude" -Force | Out-Null
    foreach ($item in @("agents", "commands", "hooks", "skills")) {
        $srcItem = Join-Path $Tmp ".claude\$item"
        if (Test-Path $srcItem) {
            Copy-Item -Path $srcItem -Destination ".claude\" -Recurse -Force
        }
    }
    Copy-Item -Path (Join-Path $Tmp ".claude\settings.json") -Destination ".claude\settings.json" -Force
    Write-Host "OK: .claude/ を展開しました"
    # .gitignore に除外エントリを追加(冪等)
    $gitignorePath = ".gitignore"
    foreach ($ignoreEntry in @(".claude/checkpoints/", ".claude/settings.local.json", ".claude/spec/")) {
        if (-not (Test-Path $gitignorePath)) {
            $ignoreEntry | Out-File -FilePath $gitignorePath -Encoding utf8
            Write-Host "OK: .gitignore を作成しました($ignoreEntry)"
        } else {
            $existing = Get-Content $gitignorePath -Raw -ErrorAction SilentlyContinue
            if ($existing -notmatch [regex]::Escape($ignoreEntry)) {
                Add-Content $gitignorePath "`n$ignoreEntry"
                Write-Host "OK: .gitignore に $ignoreEntry を追加しました"
            } else {
                Write-Host "OK: .gitignore は既に設定済みです($ignoreEntry)"
            }
        }
    }
    # フック用環境変数の雛形(既存なら保持)
    if (Test-Path ".claude\settings.local.json") {
        Write-Host "OK: .claude/settings.local.json は既存のものを保持します"
    } else {
        Copy-Item (Join-Path $Tmp "templates\settings.local.json.template") ".claude\settings.local.json"
        Write-Host "OK: .claude/settings.local.json を生成しました(env の値を記入するとフックが有効になります)"
    }
    # GitHub Actions ワークフロー(spec-gate)の配置(既存なら保持)
    if (Test-Path ".github/workflows/spec-gate.yml") {
        Write-Host "OK: .github/workflows/spec-gate.yml は既存のものを保持します"
    } else {
        New-Item -ItemType Directory -Path ".github/workflows" -Force | Out-Null
        Copy-Item (Join-Path $Tmp "templates\spec-gate.yml.template") ".github/workflows/spec-gate.yml"
        Write-Host "OK: .github/workflows/spec-gate.yml を配置しました"
    }

    if (Test-Path "CLAUDE.md") {
        Write-Host "OK: CLAUDE.md は既存のものを保持します"
    } else {
        $InitDate = Get-Date -Format "yyyy-MM-dd"
        $templatePath = Join-Path $Tmp "templates\CLAUDE.md.template"
        (Get-Content $templatePath -Raw) `
            -replace "\{\{INIT_DATE\}\}", $InitDate `
            | Out-File -FilePath "CLAUDE.md" -Encoding utf8
        Write-Host "OK: CLAUDE.md を生成しました"
    }

    Write-Host ""
    Write-Host "完了。claude を起動してサブエージェントが認識されているか確認できます"
}
finally {
    Remove-Item -Path $Tmp -Recurse -Force
}
