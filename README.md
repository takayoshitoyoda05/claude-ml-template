@'
# claude-ml-template

Claude Code用のPlanner/Generator/Evaluator 3分離パターンのテンプレート。

## 使い方
新しいプロジェクトのルートで:

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/<あなた>/claude-ml-template/main/claude-init.ps1" -OutFile "claude-init.ps1"
.\claude-init.ps1
```
'@ | Out-File -FilePath "README.md" -Encoding utf8
