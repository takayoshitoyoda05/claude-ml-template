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
    foreach ($item in @("agents", "commands", "hooks", "skills", "output-styles", "rules")) {
        $srcItem = Join-Path $Tmp ".claude\$item"
        if (Test-Path $srcItem) {
            Copy-Item -Path $srcItem -Destination ".claude\" -Recurse -Force
        }
    }
    Copy-Item -Path (Join-Path $Tmp ".claude\settings.json") -Destination ".claude\settings.json" -Force
    Write-Host "OK: .claude/ を展開しました"

    # agents/shared/ を配置(配布元にあるファイルを個別にコピー。claude-update.ps1 と同じ方式)
    $sharedSrc = Join-Path $Tmp "agents\shared"
    if (Test-Path $sharedSrc) {
        New-Item -ItemType Directory -Path "agents\shared" -Force | Out-Null
        Get-ChildItem -Path $sharedSrc -File | ForEach-Object {
            Copy-Item $_.FullName -Destination "agents\shared\" -Force
        }
        Write-Host "OK: agents/shared/ を配置しました"
    }

    # agents/shared/ から AGENTS.md を生成(Codex CLI 用。自動生成マーカーの無い
    # 既存 AGENTS.md はプロジェクト独自のファイルとみなして保持する)
    if (Test-Path "agents\shared") {
        if ((Test-Path "AGENTS.md") -and -not (Select-String -Path "AGENTS.md" -Pattern "<!-- claude-ml-template" -Quiet)) {
            Write-Host "警告: AGENTS.md は独自ファイルのため保持しました(自動生成版に切り替えるには AGENTS.md を退避してから再実行してください)"
        } else {
            $agentsLines = @("# AGENTS.md", "",
                "<!-- claude-ml-template により自動生成。編集は agents/shared/ で行い claude-update で再生成 -->", "")
            Get-ChildItem -Path "agents\shared" -Filter "*.md" | ForEach-Object {
                $agentsLines += (Get-Content $_.FullName -Encoding UTF8)
                $agentsLines += ""
            }
            $agentsLines -join "`n" | Out-File -FilePath "AGENTS.md" -Encoding utf8
            Write-Host "OK: AGENTS.md を生成しました(Codex CLI 用)"
        }
    }

    # スキルを .codex/skills/ にもコピー(Codex CLI 用。配布元にあるスキルディレクトリだけを
    # 個別に上書きし、ユーザー独自のスキルは残す)
    $skillsSrc = Join-Path $Tmp ".claude\skills"
    if (Test-Path $skillsSrc) {
        New-Item -ItemType Directory -Path ".codex\skills" -Force | Out-Null
        Get-ChildItem -Path $skillsSrc -Directory | ForEach-Object {
            $dest = Join-Path ".codex\skills" $_.Name
            if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
            Copy-Item $_.FullName $dest -Recurse
        }
        Write-Host "OK: .codex/skills/ にスキルをコピーしました"
    }

    # .codex/config.toml がなければテンプレートからコピー
    $codexConfig = ".codex\config.toml"
    $codexTemplate = Join-Path $Tmp "templates\codex-config.toml.template"
    if ((-not (Test-Path $codexConfig)) -and (Test-Path $codexTemplate)) {
        New-Item -ItemType Directory -Path ".codex" -Force | Out-Null
        Copy-Item $codexTemplate $codexConfig
        Write-Host "OK: .codex/config.toml を生成しました"
    }
    # .gitignore に除外エントリを追加(冪等。既存の .gitignore は上書きせず追記のみ)
    $gitignorePath = ".gitignore"
    $ignoreEntries = @(".claude/checkpoints/", ".claude/settings.local.json", "**/.claude/spec/", "/.worktrees/")
    # CLAUDE_TEMPLATE_GITIGNORE_ALL=1 なら、テンプレートが配布・生成する一式を
    # 導入先の git 管理外にする(テンプレートのファイルをリポジトリに載せたくない場合)
    if ($env:CLAUDE_TEMPLATE_GITIGNORE_ALL -eq "1") {
        $ignoreEntries += @(".claude/", ".codex/", "agents/shared/", "templates/*.template",
            "AGENTS.md", "CLAUDE.md", ".github/workflows/spec-gate.yml",
            "claude-update.sh", "claude-update.ps1", "claude-remote.sh", "claude-remote.ps1",
            "doctor.sh", "doctor.ps1")
    }
    foreach ($ignoreEntry in $ignoreEntries) {
        if (-not (Test-Path $gitignorePath)) {
            $ignoreEntry | Out-File -FilePath $gitignorePath -Encoding utf8
            Write-Host "OK: .gitignore を作成しました($ignoreEntry)"
        } else {
            $existing = Get-Content $gitignorePath -Raw -ErrorAction SilentlyContinue
            # 行全体の一致で判定する(部分一致だと .claude/checkpoints/ の存在だけで
            # .claude/ が「既にある」と誤判定されて追記されない)
            if ($existing -notmatch ("(?m)^" + [regex]::Escape($ignoreEntry) + "\r?$")) {
                Add-Content $gitignorePath "`n$ignoreEntry"
                Write-Host "OK: .gitignore に $ignoreEntry を追加しました"
            } else {
                Write-Host "OK: .gitignore は既に設定済みです($ignoreEntry)"
            }
        }
    }
    # 任意機能(既定では無効)の一覧: 変数名 → 質問に添える説明
    $OptionalFeatures = [ordered]@{
        "CLAUDE_CROSS_REVIEW"   = "Codex クロスレビュー(要 Codex CLI。実装を別モデル視点で必須レビュー)"
        "CLAUDE_REFACTOR_SWARM" = "haiku スカウト隊(ml-pipeline のリファクタリング偵察を並列実行)"
        "CLAUDE_QUALITY_GATE"   = "機械的品質ゲート(ruff / radon / mypy を停止時に強制)"
        "CLAUDE_DIFF_COVERAGE"  = "変更行カバレッジゲート(pytest-cov + diff-cover。既定閾値80%、CLAUDE_DIFF_COVERAGE_MIN で変更可)"
        "CLAUDE_AUTO_APPROVE"   = "計画の自動承認(plan-reviewer が安全な計画を人手なしで通す)"
        "CLAUDE_NOTIFY"         = "完了時のデスクトップ通知"
        "CLAUDE_FINAL_GATE"     = "マージ前の最終判定(final-gate)"
        "CLAUDE_SECURITY_SCAN"  = "パイプライン実行内のセキュリティスキャン"
    }

    # settings.local.json の該当フラグを "1" に書き換える
    function Enable-Feature([string]$var) {
        $path = ".claude\settings.local.json"
        $json = Get-Content $path -Raw -Encoding UTF8
        $json = $json -replace ('"' + $var + '": "[^"]*"'), ('"' + $var + '": "1"')
        $json | Out-File -FilePath $path -Encoding utf8 -NoNewline
        if (Select-String -Path $path -Pattern ('"' + $var + '": "1"') -SimpleMatch -Quiet) {
            Write-Host "OK: $var=1 を設定しました"
        } else {
            Write-Host "警告: $var を設定できませんでした(settings.local.json に項目がありません)"
        }
        if ($var -eq "CLAUDE_CROSS_REVIEW" -and -not (Get-Command codex -ErrorAction SilentlyContinue)) {
            Write-Host "警告: Codex CLI が見つかりません。クロスレビューには codex のインストールと codex login が必要です"
        }
    }

    # フック用環境変数の雛形(既存なら保持)
    if (Test-Path ".claude\settings.local.json") {
        Write-Host "OK: .claude/settings.local.json は既存のものを保持します"
    } else {
        Copy-Item (Join-Path $Tmp "templates\settings.local.json.template") ".claude\settings.local.json"
        Write-Host "OK: .claude/settings.local.json を生成しました(env の値を記入するとフックが有効になります)"
        # 任意機能の初期セットアップ(雛形を新規生成したときだけ)。優先順:
        #   1) CLAUDE_TEMPLATE_FEATURES(非対話用。"none" か、有効化するフラグ名の
        #      カンマ区切り。例: CLAUDE_TEMPLATE_FEATURES=CLAUDE_CROSS_REVIEW,CLAUDE_NOTIFY)
        #   2) 対話で1機能ずつ質問する(入力できない環境では既定値のまま進む)
        if ($env:CLAUDE_TEMPLATE_FEATURES) {
            if ($env:CLAUDE_TEMPLATE_FEATURES -ne "none") {
                foreach ($req in ($env:CLAUDE_TEMPLATE_FEATURES -split ",")) {
                    if ($OptionalFeatures.Contains($req)) {
                        Enable-Feature $req
                    } else {
                        Write-Host "警告: 不明な機能フラグ $req は無視しました"
                    }
                }
            }
        } else {
            Write-Host ""
            Write-Host "任意機能の初期セットアップを行います(後から .claude/settings.local.json で変更できます)"
            foreach ($var in @($OptionalFeatures.Keys)) {
                try {
                    $ans = Read-Host "  $($OptionalFeatures[$var]) を有効にしますか? [y/N]"
                    if ($ans -match "^[Yy]$") { Enable-Feature $var }
                } catch {
                    Write-Host "情報: 対話入力できないため残りの任意機能は既定(無効)のままにします"
                    break
                }
            }
        }
    }
    # 参照専用テンプレ(templates/*.template)を配布(既存ファイルは保持)
    New-Item -ItemType Directory -Path "templates" -Force | Out-Null
    Get-ChildItem -Path (Join-Path $Tmp "templates") -Filter "*.template" | ForEach-Object {
        $dest = Join-Path "templates" $_.Name
        if (Test-Path $dest) {
            Write-Host "OK: templates/$($_.Name) は既存のものを保持します"
        } else {
            Copy-Item $_.FullName -Destination $dest
            Write-Host "OK: templates/$($_.Name) を配布しました"
        }
    }
    # GitHub Actions ワークフロー(spec-gate)の配置(既存なら保持)
    if (Test-Path ".github/workflows/spec-gate.yml") {
        Write-Host "OK: .github/workflows/spec-gate.yml は既存のものを保持します"
    } else {
        New-Item -ItemType Directory -Path ".github/workflows" -Force | Out-Null
        Copy-Item (Join-Path $Tmp "templates\spec-gate.yml.template") ".github/workflows/spec-gate.yml"
        Write-Host "OK: .github/workflows/spec-gate.yml を配置しました"
    }

    # 運用スクリプト(claude-remote.ps1 / claude-update.ps1 / doctor.ps1)を配置
    # (この環境で使う ps1 版のみ。Linux / macOS / WSL へは claude-init.sh が
    # sh 版を配置するため、使わない側の形式は持ち込まない。
    # テンプレート由来のファイルだけを上書きし、同名の独自ファイルは保持する。
    # 配布元にマーカーが無いファイル(claude-remote.ps1)は識別できないため従来どおり
    # 常に上書き。claude- 接頭辞のため独自ファイルとの衝突リスクは低い)
    $marker = "takayoshitoyoda05/claude-ml-template"
    foreach ($f in @("claude-remote.ps1", "claude-update.ps1", "doctor.ps1")) {
        $src = Join-Path $Tmp $f
        if (Test-Path $src) {
            # ディレクトリは独自ファイル判定(Select-String)がエラーになるため先に
            # 処理する。ディレクトリへのリンクはリンク自体を除去し、実ディレクトリは
            # 警告してスキップする
            $existing = Get-Item $f -Force -ErrorAction SilentlyContinue
            if (Test-Path $f -PathType Container) {
                if ($existing -and $existing.LinkType) {
                    $existing.Delete()
                } else {
                    Write-Host "警告: $f はディレクトリのため配置をスキップしました"
                    continue
                }
            }
            if ((Select-String -Path $src -Pattern $marker -Quiet) -and (Test-Path $f) -and -not (Select-String -Path $f -Pattern $marker -Quiet)) {
                Write-Host "警告: $f は独自ファイルのため保持しました(テンプレート版が必要なら $f を退避してから再実行してください)"
                continue
            }
            # Copy-Item は既存の $f がシンボリックリンクだとリンク先に書き込んで
            # しまうため、リンク自体を除去し、一時ファイル+Move-Item で置き換える
            $existing = Get-Item $f -Force -ErrorAction SilentlyContinue
            if ($existing -and $existing.LinkType) { $existing.Delete() }
            $tmpf = "$f." + [System.IO.Path]::GetRandomFileName()
            Copy-Item $src $tmpf
            Move-Item $tmpf $f -Force
            $tmpf = $null
            Write-Host "OK: $f を配置しました"
        } else {
            Write-Host "警告: 配布元に $f が見つかりません(コピーされませんでした)"
        }
    }

    if (Test-Path "CLAUDE.md") {
        Write-Host "OK: CLAUDE.md は既存のものを保持します"
    } else {
        Copy-Item (Join-Path $Tmp "templates\CLAUDE.md.template") "CLAUDE.md"
        Write-Host "OK: CLAUDE.md を生成しました"
    }

    Write-Host ""
    Write-Host "完了。claude を起動してサブエージェントが認識されているか確認できます"
}
finally {
    Remove-Item -Path $Tmp -Recurse -Force
    if ($tmpf -and (Test-Path $tmpf)) { Remove-Item $tmpf -Force }
}
