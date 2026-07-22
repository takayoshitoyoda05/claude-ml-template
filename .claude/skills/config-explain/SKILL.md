---
name: config-explain
description: スコープ・評価強制の設定確認や意図しないブロックの切り分けをしたいとき、「今の設定を確認して」「なぜブロックされたか分からない」と言われたときに必ず使う。
---

# 設定の可視化

CLAUDE_WORK_SCOPE 等は settings.local.json とシェル環境変数の両方から
設定できるため、意図しない値が効いていて混乱することがある。現在の状態を
整理して見せる。

## 確認する項目
| 変数 | 確認方法 |
|---|---|
| CLAUDE_WORK_SCOPE | 環境変数と .claude/settings.local.json の env.CLAUDE_WORK_SCOPE を両方確認 |
| CLAUDE_ENFORCE_EVAL | 同上 |
| CLAUDE_EVAL_CMD | 同上 |
| CLAUDE_COMMIT_STEP_RULE | 同上 |
| CLAUDE_SPEC_CHECK | 同上 |
| CLAUDE_SPEC_RECHECK_N | 同上 |
| CLAUDE_CROSS_REVIEW | 同上 |
| CODEX_MODEL | 同上 |
| CLAUDE_AUTO_APPROVE | 同上 |

## 進め方
1. リポジトリ直下の .claude/settings.local.json を読む(無ければ「未設定」とする)。
   Claude Code が起動時に読むのはこの場所であり、作業スコープ配下ではない。
2. 各変数について、settings.local.json に値があるか確認する。
3. シェル環境変数側の値も(参照できる範囲で)確認する。
4. 以下の形式で報告する。

## 報告フォーマット
| 変数 | settings.local.json | シェル環境変数 | 実際に有効な値 | 由来 |
|---|---|---|---|---|
| CLAUDE_WORK_SCOPE | ... | ... | ... | settings.local.json / シェル / 未設定 |

settings.local.json にキーが存在する場合(値が空でも)、そちらが優先される
ことに注意し、意図と違う設定源が使われていそうであれば明示的に警告する。
