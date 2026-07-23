---
name: cross-review
description: Codex CLI(OpenAIモデル)でClaude実装を別モデル視点でレビューする。CLAUDE_CROSS_REVIEW=1 のときevaluator実行前に必須。「クロスレビューして」と言われたときにも使う。
---

# Codex クロスレビュー

Claude(Sonnet)が実装したコードを、Codex CLI(OpenAIモデル)に独立レビューさせる。

## 前提条件
- Codex CLI がインストールされていること(`codex --version` で確認)
- AGENTS.md がプロジェクトルートにあること
- .codex/config.toml でモデルが固定されていること

## 進め方
1. Codex CLI が使えるか確認する。使えなければ
   「Codex CLI が見つかりません。スキップします」と報告し、
   手順6のセンチネルファイルだけ作成して終了する。

2. レビュー対象の diff を取得する(作業スコープに限定)。
   作業ブランチ上ならブランチ全体を対象にする(コミットが複数でも漏らさない):
   ```
   git diff main...HEAD -- <作業スコープ>
   ```
   main が無い、または main 上で作業している場合は `git diff HEAD~1 -- <作業スコープ>`。

2.5. 呼び出し方法の選択
   MCP(codex)が接続されていれば(/mcp で確認できる)、MCP 経由で
   レビューを依頼する(会話の文脈を保ったまま依頼できるため優先)。
   接続されていない、または MCP 呼び出しが失敗した場合は、
   従来の codex exec 方式にフォールバックする(以下のステップ3)。

3. 以下のコマンドでCodexにレビューを依頼する(手順2の diff をパイプで渡す)。
   環境変数 CODEX_MODEL が設定されていれば --model で上書きする。
   未設定なら .codex/config.toml のモデルが使われる。

   CODEX_MODEL が設定されている場合:
   ```
   <手順2のdiffコマンド> | codex --model $CODEX_MODEL exec "以下のdiffをレビューし、
   問題点を重大度(CRITICAL/HIGH/MEDIUM/LOW)付きで報告してください。
   ファイルパスと行番号を含めてください。"
   ```

   未設定の場合:
   ```
   <手順2のdiffコマンド> | codex exec "以下のdiffをレビューし、
   問題点を重大度(CRITICAL/HIGH/MEDIUM/LOW)付きで報告してください。
   ファイルパスと行番号を含めてください。"
   ```

4. Codexの出力を整形してレポートにまとめる。

5. レポートをユーザーに提示する(evaluator への参考情報として渡す)。

6. 完了したらセンチネルファイルを作成する。中身は「レビューした時点の
   HEAD ハッシュ」であることが必須(codex_gate が現在の HEAD と照合し、
   レビュー後にコミットが進んでいたらブロックする)。
   bash:
   ```
   mkdir -p .claude/checkpoints && git rev-parse HEAD > .claude/checkpoints/codex_review_done.txt
   ```
   PowerShell:
   ```
   New-Item -ItemType Directory -Path ".claude\checkpoints" -Force | Out-Null
   git rev-parse HEAD | Out-File -FilePath ".claude\checkpoints\codex_review_done.txt" -Encoding utf8
   ```

## 注意
- Codex のレビュー結果は参考情報。最終判定は evaluator が行う。
- Codex が問題なしでも evaluator の NEEDS_REVISION は覆さない。
- センチネルはレビューを実際に実行(またはCodex不在を確認)した後にのみ作成する。
  レビューを省略してセンチネルだけ作ることはゲートの意味を失わせるので行わない。
