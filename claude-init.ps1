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
    # .gitignore に除外エントリを追加(冪等)
    $gitignorePath = ".gitignore"
    foreach ($ignoreEntry in @(".claude/checkpoints/", ".claude/settings.local.json", "**/.claude/spec/", "/.worktrees/")) {
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

    # 運用スクリプト(claude-remote.* / claude-update.* / doctor.*)を配置
    # (テンプレート由来のファイルだけを上書きし、同名の独自ファイルは保持する。
    # 配布元にマーカーが無いファイル(claude-remote.*)は識別できないため従来どおり
    # 常に上書き。claude- 接頭辞のため独自ファイルとの衝突リスクは低い)
    $marker = "takayoshitoyoda05/claude-ml-template"
    foreach ($f in @("claude-remote.ps1", "claude-remote.sh", "claude-update.ps1", "claude-update.sh", "doctor.ps1", "doctor.sh")) {
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
