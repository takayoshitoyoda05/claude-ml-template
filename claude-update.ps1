param()

$ErrorActionPreference = "Stop"

foreach ($tool in @("uv", "git")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host "エラー: '$tool' が見つかりません。インストールしてから再実行してください。"
        exit 1
    }
}

$TemplateRepo = "https://github.com/takayoshitoyoda05/claude-ml-template.git"

if (-not (Test-Path ".claude")) {
    Write-Host "エラー: .claude が見つかりません。先に claude-init.ps1 で初回展開してください。"
    exit 1
}

$Tmp = Join-Path $env:TEMP ([System.Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $Tmp | Out-Null

try {
    Write-Host "最新テンプレートを取得中..."
    git clone --depth 1 --quiet $TemplateRepo $Tmp

    # 更新対象: agents / commands / hooks / settings.json
    # plans/ と CLAUDE.md はプロジェクト固有・実行履歴なので触らない
    foreach ($item in @("agents", "commands", "hooks", "skills")) {
        $src = Join-Path $Tmp ".claude\$item"
        if (Test-Path $src) {
            Copy-Item -Path $src -Destination ".claude\" -Recurse -Force
            Write-Host "OK: .claude/$item を更新しました"
        }
    }

    $settingsSrc = Join-Path $Tmp ".claude\settings.json"
    if (Test-Path $settingsSrc) {
        Copy-Item -Path $settingsSrc -Destination ".claude\settings.json" -Force
        Write-Host "OK: .claude/settings.json を更新しました"
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

    Write-Host ""
    Write-Host "更新完了(.claude/plans/ と CLAUDE.md は変更されていません)"
}
finally {
    Remove-Item -Path $Tmp -Recurse -Force
}
