param(
    [string]$Name = ""
)
$ErrorActionPreference = "Stop"

# セッション名は未指定ならカレントディレクトリ名
if ([string]::IsNullOrWhiteSpace($Name)) {
    $Name = Split-Path -Leaf (Get-Location)
}

if (-not (Get-Command "claude" -ErrorAction SilentlyContinue)) {
    Write-Host "エラー: claude コマンドが見つかりません。"
    exit 1
}

Write-Host "=== リモート運用の起動チェック ==="

# 1. スリープ設定の確認(スリープするとセッションが切れる)
try {
    $acTimeout = (powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE 2>$null |
        Select-String "現在の AC 電源設定|Current AC Power Setting" |
        Select-Object -First 1)
    if ($acTimeout -match "0x00000000") {
        Write-Host "OK: スリープは無効です。"
    } else {
        Write-Host "警告: PC がスリープするとリモートセッションが切れます。"
        Write-Host "      無効化するには管理者権限で: powercfg /change standby-timeout-ac 0"
    }
} catch {
    Write-Host "情報: スリープ設定を確認できませんでした(手動で確認してください)。"
}

# 2. Remote Control の自動有効化についての案内(初回のみ必要)
$NoticeMarker = $null
try {
    $NoticeMarker = Join-Path $env:LOCALAPPDATA "claude-remote\notice-shown"
} catch {}
if ($NoticeMarker -and (Test-Path $NoticeMarker -ErrorAction SilentlyContinue)) {
    Write-Host "ヒント: 初回のみ必要な設定(/config →「Enable Remote Control for all sessions」)がまだなら実施してください。"
} else {
    Write-Host ""
    Write-Host "初回のみ必要な設定:"
    Write-Host "  claude 起動後に /config を実行し、"
    Write-Host "  「Enable Remote Control for all sessions」を true にしてください。"
    Write-Host "  (この設定はマシン単位。1度設定すれば以降は不要です)"
    Write-Host ""
    if ($NoticeMarker) {
        try {
            New-Item -ItemType Directory -Force -Path (Split-Path $NoticeMarker) | Out-Null
            New-Item -ItemType File -Force -Path $NoticeMarker | Out-Null
        } catch {}
    }
}

# 3. 起動
Write-Host "=== Claude Code を起動します(セッション名: $Name) ==="
Write-Host "スマホからの接続: Claude アプリ → Code タブ → 緑ドットのセッションを選択"
Write-Host "外出時はこのウィンドウを閉じずに最小化してください。"
Write-Host ""

claude remote-control --name "$Name"
