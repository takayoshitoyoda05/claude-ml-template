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
