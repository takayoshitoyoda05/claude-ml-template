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
    foreach ($item in @("agents", "commands", "hooks", "skills", "output-styles", "rules")) {
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

    # agents/shared/(リポジトリ直下。Codex CLI 共有指示の配布元)も比較する
    $remoteShared = Join-Path $Tmp "agents\shared"
    if (Test-Path $remoteShared) {
        $sharedFiles = Get-ChildItem -Path $remoteShared -Recurse -File
        foreach ($rf in $sharedFiles) {
            $relPath = $rf.FullName.Substring($remoteShared.Length).TrimStart("\")
            $localFile = Join-Path "agents\shared" $relPath
            if (-not (Test-Path $localFile)) {
                Write-Host "NEW: agents/shared/$relPath (テンプレートにあるがローカルに無い)"
                $diffCount++
                continue
            }
            $remoteHash = (Get-FileHash -Path $rf.FullName -Algorithm SHA256).Hash
            $localHash = (Get-FileHash -Path $localFile -Algorithm SHA256).Hash
            if ($remoteHash -ne $localHash) {
                Write-Host "DIFF: agents/shared/$relPath (内容が異なる)"
                $diffCount++
            }
        }
    }

    # scripts/(リポジトリ直下。個別ファイル配布のためこの foreach ($item) ループには
    # 足さない。.claude\$item を前提とする既存ループに "scripts" を足すと
    # .claude\scripts が無く continue で無言の no-op になるため、別ブロックにする)
    $remoteScripts = Join-Path $Tmp "scripts"
    if (Test-Path $remoteScripts) {
        $scriptFiles = Get-ChildItem -Path $remoteScripts -Recurse -File
        foreach ($rf in $scriptFiles) {
            $relPath = $rf.FullName.Substring($remoteScripts.Length).TrimStart("\")
            $localFile = Join-Path "scripts" $relPath
            if (-not (Test-Path $localFile)) {
                Write-Host "NEW: scripts/$relPath (テンプレートにあるがローカルに無い)"
                $diffCount++
                continue
            }
            $remoteHash = (Get-FileHash -Path $rf.FullName -Algorithm SHA256).Hash
            $localHash = (Get-FileHash -Path $localFile -Algorithm SHA256).Hash
            if ($remoteHash -ne $localHash) {
                Write-Host "DIFF: scripts/$relPath (内容が異なる)"
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

Write-Host ""
Write-Host "=== リモート運用(Remote Control)==="

# claude のバージョン確認(Remote Control は v2.1.51 以降)
if (Get-Command "claude" -ErrorAction SilentlyContinue) {
    $verLine = (claude --version 2>$null | Select-Object -First 1)
    $verMatch = if ($verLine) { [regex]::Match($verLine, '^\d+\.\d+\.\d+') } else { $null }
    $parsedVer = $null
    # 正規表現に一致しても各要素が [version](Int32 範囲)を超えるとキャストが例外を投げるため保護する
    if ($verMatch -and $verMatch.Success -and [version]::TryParse($verMatch.Value, [ref]$parsedVer)) {
        $claudeVer = $verMatch.Value
        if ($parsedVer -ge [version]"2.1.51") {
            Write-Host "OK: claude $claudeVer (Remote Control 対応、v2.1.51 以降で利用可)"
        } else {
            Write-Host "警告: claude $claudeVer は古いバージョンです。Remote Control は v2.1.51 以降が必要です"
        }
    } else {
        Write-Host "情報: claude のバージョンを取得できませんでした(Remote Control は v2.1.51 以降で利用可)"
    }
} else {
    Write-Host "情報: claude コマンドが見つかりません(Remote Control は v2.1.51 以降で利用可)"
}

# 起動スクリプトの有無
if (Test-Path "claude-remote.ps1") {
    Write-Host "OK: claude-remote.ps1 があります(.\claude-remote.ps1 で起動)"
} else {
    Write-Host "情報: claude-remote.ps1 がありません。claude-update で取得できます。"
}

Write-Host "確認: /config の「Enable Remote Control for all sessions」が true か"
Write-Host "      (マシン単位の設定。未設定なら毎回 /remote-control が必要です)"

Write-Host ""
Write-Host "=== データ保護(Data Protection)==="

# 判定はWindows実態(ReadOnly属性)に基づく。Unixのパーミッションビットとは
# 意味が異なり(NTFSのReadOnly属性はACLと独立)、厳密な一致は保証しない。
if (Test-Path "data") {
    $rawDir = "data\raw"
    if ((Test-Path $rawDir) -and (-not (Get-Item $rawDir).Attributes.HasFlag([System.IO.FileAttributes]::ReadOnly))) {
        Write-Host "警告: [DATA-RAW-WRITABLE] data/raw が書き込み可能です。ReadOnly属性の付与を検討してください。"
    }
    $processedDir = "data\processed"
    if ((Test-Path $processedDir) -and (Get-Item $processedDir).Attributes.HasFlag([System.IO.FileAttributes]::ReadOnly)) {
        Write-Host "警告: [DATA-PROCESSED-READONLY] data/processed が書き込み不可です。再生成できない場合は権限を確認してください。"
    }
    if (-not (Test-Path "data\DATA_LOG.md")) {
        Write-Host "警告: [DATA-LOG-MISSING] data/DATA_LOG.md がありません。templates/DATA_LOG.md.template から作成してください。"
    }

    # [DATA-LOCK-MISMATCH] data/data.lock と実データの照合。
    # sh版はuv run pythonでJSONスキーマ(algorithm/files[].sha256/files[].size)を
    # 検証するが、ps1は既存のGet-FileHash方式に合わせConvertFrom-Json +
    # Get-FileHashでネイティブに照合する(外部プロセス起動を増やさないため)。
    $lockPath = "data\data.lock"
    if (Test-Path $lockPath) {
        $lockMismatch = $false
        try {
            $lockJson = Get-Content -Path $lockPath -Raw | ConvertFrom-Json
            foreach ($rel in $lockJson.files.PSObject.Properties.Name) {
                $entry = $lockJson.files.$rel
                $filePath = Join-Path "data" $rel
                if (-not (Test-Path $filePath)) {
                    $lockMismatch = $true
                    break
                }
                $actualHash = (Get-FileHash -Path $filePath -Algorithm SHA256).Hash
                $actualSize = (Get-Item $filePath).Length
                if ($actualHash -ne $entry.sha256.ToUpper() -or $actualSize -ne $entry.size) {
                    $lockMismatch = $true
                    break
                }
            }
        } catch {
            $lockMismatch = $true
        }
        if ($lockMismatch) {
            Write-Host "警告: [DATA-LOCK-MISMATCH] data/data.lock と実データが一致しません。scripts/data_lock.py --update で更新してください。"
        }
    }

    # [DATA-BACKUP-UNKNOWN] / [DATA-BACKUP-STALE] data/.backup_stamp(YYYY-MM-DD 1行)
    $backupStampPath = "data\.backup_stamp"
    if (Test-Path $backupStampPath) {
        $stamp = (Get-Content -Path $backupStampPath -TotalCount 1).Trim()
        $parsedDate = [DateTime]::MinValue
        $isValidDate = [DateTime]::TryParseExact(
            $stamp, "yyyy-MM-dd",
            [System.Globalization.CultureInfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::None,
            [ref]$parsedDate
        )
        if ($isValidDate) {
            $ageDays = (Get-Date).Date.Subtract($parsedDate.Date).Days
            if ($ageDays -gt 30) {
                Write-Host "警告: [DATA-BACKUP-STALE] data/.backup_stamp が30日を超えています(${ageDays}日前)。バックアップを取り直して更新してください。"
            }
        } else {
            Write-Host "警告: [DATA-BACKUP-UNKNOWN] data/.backup_stamp の日付を解釈できません。YYYY-MM-DD 形式で記録してください。"
        }
    } else {
        Write-Host "警告: [DATA-BACKUP-UNKNOWN] data/.backup_stamp がありません。バックアップ実施日を記録してください。"
    }

    # [DATA-PRECOMMIT-OFF] git hooks が scripts/githooks 経由で有効化されているか
    $hooksPath = (git config --get core.hooksPath 2>$null)
    if ($hooksPath -ne "scripts/githooks") {
        Write-Host "警告: [DATA-PRECOMMIT-OFF] core.hooksPath が scripts/githooks に設定されていません。git config core.hooksPath scripts/githooks で有効化してください。"
    }

    # [DATA-KEY-RECIPIENTS-MISSING] .claude/backup_recipients.txt が無い、または鍵が2未満
    $recipientsPath = ".claude\backup_recipients.txt"
    if (-not (Test-Path $recipientsPath)) {
        Write-Host "警告: [DATA-KEY-RECIPIENTS-MISSING] .claude/backup_recipients.txt がありません。バックアップ暗号化の受信者公開鍵を2件以上登録してください。"
    } else {
        $keyCount = @(Get-Content -Path $recipientsPath | Where-Object { $_.Trim() -ne "" }).Count
        if ($keyCount -lt 2) {
            Write-Host "警告: [DATA-KEY-RECIPIENTS-MISSING] .claude/backup_recipients.txt の鍵が2件未満です(${keyCount}件)。受信者公開鍵を2件以上登録してください。"
        }
    }

    # [DATA-AGE-MISSING] age(暗号化ツール)が未導入
    if (-not (Get-Command age -ErrorAction SilentlyContinue)) {
        Write-Host "警告: [DATA-AGE-MISSING] age が見つかりません。バックアップ暗号化には age の導入が必要です。"
    }

    # [DATA-PROFILE-UNSET] data/DATA_LOG.md にデータ行があるのにプロファイル実効が無効
    $datalogPath = "data\DATA_LOG.md"
    if (Test-Path $datalogPath) {
        $hasDataRow = $false
        $headerSeen = $false
        foreach ($line in (Get-Content -Path $datalogPath)) {
            if ($line -notmatch '^\|(.+)\|\s*$') { continue }
            $inner = $Matches[1]
            if ($inner -match '^[\s|:-]+$') { continue }
            if (-not $headerSeen) {
                $headerSeen = $true
                continue
            }
            $hasDataRow = $true
        }

        # プロファイル実効判定(個別変数が非空かつ"0"以外なら優先、空ならプロファイルに委ねる)
        $noReadEffective = $false
        $gateEffective = $false
        $noReadVar = $env:CLAUDE_DATA_NO_READ
        $gateVar = $env:CLAUDE_DATA_GATE
        $profileVar = $env:CLAUDE_DATA_PROFILE
        if ($noReadVar -and $noReadVar -ne "0") {
            $noReadEffective = $true
        } elseif ((-not $noReadVar) -and $profileVar -eq "sensitive") {
            $noReadEffective = $true
        }
        if ($gateVar -and $gateVar -ne "0") {
            $gateEffective = $true
        } elseif ((-not $gateVar) -and ($profileVar -eq "sensitive" -or $profileVar -eq "internal")) {
            $gateEffective = $true
        }

        if ($hasDataRow -and (-not $noReadEffective) -and (-not $gateEffective)) {
            Write-Host "警告: [DATA-PROFILE-UNSET] data/DATA_LOG.md にデータがありますが、CLAUDE_DATA_PROFILE 等の保護が無効です。機密度に応じて CLAUDE_DATA_PROFILE を設定してください。"
        }
    }
}
