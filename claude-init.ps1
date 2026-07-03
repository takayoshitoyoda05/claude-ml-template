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

    Copy-Item -Path (Join-Path $Tmp ".claude") -Destination "." -Recurse -Force
    Write-Host "OK: .claude/ を展開しました"
    # .gitignore に .claude/checkpoints/ を追加(冪等)
    $gitignorePath = ".gitignore"
    $ignoreEntry = ".claude/checkpoints/"
    if (-not (Test-Path $gitignorePath)) {
        $ignoreEntry | Out-File -FilePath $gitignorePath -Encoding utf8
        Write-Host "OK: .gitignore を作成しました"
    } else {
        $existing = Get-Content $gitignorePath -Raw -ErrorAction SilentlyContinue
        if ($existing -notmatch [regex]::Escape($ignoreEntry)) {
            Add-Content $gitignorePath "`n$ignoreEntry"
            Write-Host "OK: .gitignore に $ignoreEntry を追加しました"
        } else {
            Write-Host "OK: .gitignore は既に設定済みです"
        }
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
