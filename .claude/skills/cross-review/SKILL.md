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
   センチネルファイルだけ作成して終了する。

2. `git diff` で直近の変更を取得する(作業スコープに限定)。

3. 以下のコマンドでCodexにレビューを依頼する。
   環境変数 CODEX_MODEL が設定されていれば --model で上書きする。
   未設定なら .codex/config.toml のモデルが使われる。

   CODEX_MODEL が設定されている場合:
   ```
   git diff HEAD~1 -- <作業スコープ> | codex --model $CODEX_MODEL exec "以下のdiffをレビューし、
   問題点を重大度(CRITICAL/HIGH/MEDIUM/LOW)付きで報告してください。
   ファイルパスと行番号を含めてください。"
   ```

   未設定の場合:
   ```
   git diff HEAD~1 -- <作業スコープ> | codex exec "以下のdiffをレビューし、
   問題点を重大度(CRITICAL/HIGH/MEDIUM/LOW)付きで報告してください。
   ファイルパスと行番号を含めてください。"
   ```

4. Codexの出力を整形してレポートにまとめる。

5. レポートをユーザーに提示する(evaluator への参考情報として渡す)。

6. 完了したらセンチネルファイルを作成する。
   PowerShell: `New-Item -Path "$env:TEMP\.claude-codex-review-done" -Force`
   bash: `touch /tmp/.claude-codex-review-done`

## 注意
- Codex のレビュー結果は参考情報。最終判定は evaluator が行う。
- Codex が問題なしでも evaluator の NEEDS_REVISION は覆さない。
