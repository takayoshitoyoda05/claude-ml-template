param()
$ErrorActionPreference = "Stop"

foreach ($tool in @("uv", "git")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host "エラー: '$tool' が見つかりません。"
        exit 1
    }
}

if (-not (Test-Path ".claude")) {
    Write-Host "エラー: .claude が見つかりません。claude-init で展開してから使ってください。"
    exit 1
}

$TemplateRepo = "https://github.com/takayoshitoyoda05/claude-ml-template.git"
$Tmp = Join-Path $env:TEMP ([System.Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $Tmp | Out-Null

try {
    Write-Host "最新テンプレートを取得中..."
    git clone --depth 1 --quiet $TemplateRepo $Tmp

    $diffCount = 0
    foreach ($item in @("agents", "commands", "hooks", "skills", "output-styles")) {
        $localDir = Join-Path ".claude" $item
        $remoteDir = Join-Path $Tmp ".claude\$item"
        if (-not (Test-Path $remoteDir)) { continue }

        $remoteFiles = Get-ChildItem -Path $remoteDir -Recurse -File
        foreach ($rf in $remoteFiles) {
            $relPath = $rf.FullName.Substring($remoteDir.Length).TrimStart("\")
            $localFile = Join-Path $localDir $relPath
            if (-not (Test-Path $localFile)) {
                Write-Host "NEW: $item/$relPath (テンプレートにあるがローカルに無い)"
                $diffCount++
                continue
            }
            $remoteHash = (Get-FileHash -Path $rf.FullName -Algorithm SHA256).Hash
            $localHash = (Get-FileHash -Path $localFile -Algorithm SHA256).Hash
            if ($remoteHash -ne $localHash) {
                Write-Host "DIFF: $item/$relPath (内容が異なる)"
                $diffCount++
            }
        }
    }

    $localSettings = ".claude\settings.json"
    $remoteSettings = Join-Path $Tmp ".claude\settings.json"
    if ((Test-Path $localSettings) -and (Test-Path $remoteSettings)) {
        $rh = (Get-FileHash -Path $remoteSettings -Algorithm SHA256).Hash
        $lh = (Get-FileHash -Path $localSettings -Algorithm SHA256).Hash
        if ($rh -ne $lh) {
            Write-Host "DIFF: settings.json (内容が異なる)"
            $diffCount++
        }
    }

    Write-Host ""
    if ($diffCount -eq 0) {
        Write-Host "最新です。差分はありません。"
    } else {
        Write-Host "$diffCount 件の差分があります。claude-update の実行を検討してください。"
    }
}
finally {
    Remove-Item -Path $Tmp -Recurse -Force
}
