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
   (存在しなければ `templates/settings.local.json.template` を土台にする)。
2. ユーザーの発言から対象キーの値を聞き取る。言及されていない項目は
   既存値(無ければ空文字)のまま残し、勝手に推測して埋めない。

   | 変数 | 意味 |
   |---|---|
   | CLAUDE_WORK_SCOPE | 書き込みを許可する範囲 |
   | CLAUDE_ENFORCE_EVAL | `1` で Stop 時の評価強制ON |
   | CLAUDE_EVAL_CMD | 評価強制で実行するコマンド |
   | CLAUDE_COMMIT_STEP_RULE | `1` でコミットメッセージにステップ番号(数字)を強制 |
   | CLAUDE_SPEC_CHECK | `1` で Stop 時に設計書の受け入れ条件を機械検査(spec-compliance) |
   | CLAUDE_SPEC_RECHECK_N | spec-compliance の再実行件数。`all` で全件(未指定時 `3`) |

3. 完成形の JSON 全文をコードブロックで提示する。Edit/Write は呼ばない
   (呼んでもガードにブロックされるだけなので試みない)。
4. 「`.claude/settings.local.json` に貼り付けて保存し、`claude` を再起動すると
   反映されます」と案内する。

## 注意
- このスキルはファイルを書き換えない。書き換えの実行は常にユーザー自身が行う。
- 既存キーで言及されなかったものは変更前の値をそのまま残し、意図しない上書きをしない。
