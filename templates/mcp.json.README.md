# mcp.json.template について

このファイルを `.mcp.json` としてプロジェクトルートに置くと、MCPサーバーを登録できる。

## codex エントリについて

Codex CLI を MCP サーバーとして登録すると、Claude Code の会話中に
「codex を使って〜」と自然に依頼できるようになる。

前提:
- `codex --version` が通ること(Codex CLI インストール済み)
- Codex の認証が済んでいること(ターミナルで `codex` を単体起動して確認)

トラブルシューティング:
- MCP経由で失敗するがターミナル単体では動く場合、環境変数の継承の問題が多い
- `codex mcp-server` は実験的仕様のため、バージョンアップで挙動が変わることがある。
  動かない場合、cross-review / codex-delegate は自動的に `codex exec` 方式に
  フォールバックする

## arxiv エントリについて

プロジェクトで arXiv MCP を使う場合:

1. mcpServers 内の "arxiv" エントリを .mcp.json にマージする
2. "comment" キーは説明用なので削除する
3. claude セッションを再起動し、/mcp で接続状態を確認する

arXiv MCP が接続されていると、literature-review スキルが
web検索より優先して arXiv を直接検索するようになる。

サプライチェーン上の注意: `uvx arxiv-mcp-server` は実行のたびに外部パッケージの
最新版を取得する。バージョンを固定したい場合は args を
`["arxiv-mcp-server==<バージョン>"]` の形にする(信頼できる版を確認してから固定する)。
