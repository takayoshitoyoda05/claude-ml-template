## 検索の衛生

- リポジトリ横断の grep / 検索では `.claude/checkpoints/`・`logs/`・
  `CLAUDE-SECURITY-*/`・`tests_scratch/` を除外する(未追跡の転写・実行ログが
  数十MB規模で存在し、ヒットすると文脈を大量に消費するため)
- rg(ripgrep)があれば優先する(gitignore を尊重しつつ未追跡ファイルも検索できる)。
  git grep は追跡済みファイルしか見ないため、未追跡の新規ファイルを見落とすことに
  注意する。素の grep を使う場合は上記ディレクトリを明示的に除外する
