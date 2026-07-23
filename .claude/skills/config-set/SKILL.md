---
name: config-set
description: 作業スコープや評価強制などを「〜に設定して」「settings.local.jsonの中身を作って」と言われたときに使う。settings.local.json はガードにより Claude からの直接書き込みができないため、貼り付け用のJSON下書きを提示するだけに留める。
---

# settings.local.json の下書き生成

`.claude/settings.local.json` は guard_scope.py の保護対象(PROTECTED_PATH_PATTERNS)で、
Claude からの Edit/Write は常にブロックされる。これは事故ではなく、Claude が自分自身の
作業スコープや評価強制を書き換えて制約を自己解除できないようにするための意図的な制限
(README 3.6節)。このスキルは値を書き込まず、ユーザーが手動で貼り付けるための
完成形JSONを提示するだけにとどめる。

## 進め方
1. `.claude/settings.local.json` が存在すれば Read で読み、既存値を確認する
   (存在しなければ以下の雛形を土台にする)。

   ```json
   {
     "env": {
       "PYTHONUTF8": "1",
       "CLAUDE_WORK_SCOPE": "",
       "CLAUDE_ENFORCE_EVAL": "",
       "CLAUDE_EVAL_CMD": "",
       "CLAUDE_COMMIT_STEP_RULE": "",
       "CLAUDE_SPEC_CHECK": "",
       "CLAUDE_SPEC_RECHECK_N": "",
       "CLAUDE_CROSS_REVIEW": "0",
       "CODEX_MODEL": "",
       "CLAUDE_AUTO_APPROVE": "0",
       "CLAUDE_QUALITY_GATE": "0",
       "CLAUDE_NOTIFY": "0",
       "CLAUDE_ADVERSARIAL": "0",
       "CLAUDE_FINAL_GATE": "0"
     }
   }
   ```
2. ユーザーの発言から対象キーの値を聞き取る。言及されていない項目は
   既存値のまま残す。既存ファイルが無い場合、未指定のキーは上記雛形の
   既定値に合わせる(フラグ系は `"0"`、CLAUDE_WORK_SCOPE / CLAUDE_EVAL_CMD /
   CODEX_MODEL 等の文字列系は空文字)。勝手に推測して埋めない。

   | 変数 | 意味 |
   |---|---|
   | CLAUDE_WORK_SCOPE | 書き込みを許可する範囲 |
   | CLAUDE_ENFORCE_EVAL | `1` で Stop 時の評価強制ON |
   | CLAUDE_EVAL_CMD | 評価強制で実行するコマンド |
   | CLAUDE_COMMIT_STEP_RULE | `1` でコミットメッセージにステップ番号(数字)を強制 |
   | CLAUDE_SPEC_CHECK | `1` で Stop 時に設計書の受け入れ条件を機械検査(spec-compliance) |
   | CLAUDE_SPEC_RECHECK_N | spec-compliance の再実行件数。`all` で全件(未指定時 `3`) |
   | CLAUDE_CROSS_REVIEW | `1` でCodexクロスレビューをevaluator前に必須にする(既定 `0`) |
   | CODEX_MODEL | Codexのモデルを一時的に上書き(空なら.codex/config.tomlの設定) |
   | CLAUDE_AUTO_APPROVE | `1` で plan-reviewer による計画の自動承認を有効にする(既定 `0`) |
   | CLAUDE_QUALITY_GATE | `1` でruff/radon/mypyの機械的品質チェックをStopフックで強制する(既定 `0`) |
   | CLAUDE_NOTIFY | `1` でセッション停止時にデスクトップ通知を出す(既定 `0`) |
   | CLAUDE_ADVERSARIAL | `1` で敵対的レビュー(攻撃+偽陽性除外)を2軸レビュー後に実行(既定 `0`) |
   | CLAUDE_FINAL_GATE | `1` でFableによる最終ゲート判断をリファクタパス後に実行(既定 `0`) |

3. 完成形の JSON 全文をコードブロックで提示する。Edit/Write は呼ばない
   (呼んでもガードにブロックされるだけなので試みない)。
4. 「`.claude/settings.local.json` に貼り付けて保存し、`claude` を再起動すると
   反映されます」と案内する。

## 注意
- このスキルはファイルを書き換えない。書き換えの実行は常にユーザー自身が行う。
- 既存キーで言及されなかったものは変更前の値をそのまま残し、意図しない上書きをしない。
