param()

$ErrorActionPreference = "Stop"

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

    if (Test-Path "CLAUDE.md") {
        Write-Host "OK: CLAUDE.md は既存のものを保持します"
    } else {
        $ProjectName = Split-Path -Leaf (Get-Location)
        $EvalCmd = Read-Host "評価スクリプトの実行コマンド [uv run python -m src.eval.eval]"
        if ([string]::IsNullOrWhiteSpace($EvalCmd)) { $EvalCmd = "uv run python -m src.eval.eval" }
        $ModelPath = Read-Host "主要モデル定義の場所 [src/models/]"
        if ([string]::IsNullOrWhiteSpace($ModelPath)) { $ModelPath = "src/models/" }
        $InitDate = Get-Date -Format "yyyy-MM-dd"

        $templatePath = Join-Path $Tmp "templates\CLAUDE.md.template"
        (Get-Content $templatePath -Raw) `
            -replace "\{\{PROJECT_NAME\}\}", $ProjectName `
            -replace "\{\{EVAL_CMD\}\}", $EvalCmd `
            -replace "\{\{MODEL_PATH\}\}", $ModelPath `
            -replace "\{\{INIT_DATE\}\}", $InitDate `
            | Out-File -FilePath "CLAUDE.md" -Encoding utf8

        Write-Host "OK: CLAUDE.md を生成しました"
    }

    Write-Host ""
    Write-Host "完了。claude を起動して /agents で確認できます"
}
finally {
    Remove-Item -Path $Tmp -Recurse -Force
}
