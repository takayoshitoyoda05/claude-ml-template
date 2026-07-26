# 適用済みの改善(improvement-reviewer の記録)

## 2026-07-26 審査(対象: patterns.md 2026-07-26 の6パターン)

### 適用(全12件。各コミット後に verify-hooks.sh を実行し全テストPASSを確認)

| コミット | パターン | 変更ファイル | 内容 |
|---|---|---|---|
| 3cd0773 | 1 | .claude/rules/consistency.md(新規) | 記述を書いたら指す先を grep で確認し、コマンドと結果を報告に含める |
| b579a23 | 3 | .claude/rules/consistency.md | 対になるファイル(sh/ps1、init/update)の整合確認 |
| cec8390 | 3 | .claude/rules/consistency.md | 1対1対応を検証するコマンドの標準形(diff + 件数3点) |
| f0ec344 | 1 | .claude/commands/ml-pipeline.md | 手順5の generator 共通指示に grep 確認を追加 |
| dc5c5b5 | 5 | .claude/commands/ml-pipeline.md | 手順5に「追加テストが修正前実装で FAIL すること」の確認を追加 |
| 4399780 | 1 | .claude/agents/evaluator-standards.md | 記述と実態の一致を最多の指摘源として優先確認 |
| fed7a54 | 2 | .claude/rules/python-style.md | フック・ゲートの捕捉例外((OSError, UnicodeError) 等) |
| bc095ea | 2 | .claude/rules/python-style.md | 値読み取り正規表現の行末固定(誤読の防止) |
| 9aa87d9 | 2 | .claude/agents/evaluator.md | Spec 軸に「契約」(宣言が全経路で成立するか)を追加 |
| cf24df5 | 4 | .claude/agents/generator.md | 新規追加前に同種の既存要素を2つ読み書式を踏襲 |
| c68a460 | 4 | .claude/agents/planner.md | 新規追加ステップに「倣う既存要素」を明記させる |
| 01c1c09 | 5 | .claude/agents/planner.md | 検証方法に「複数ある場合」「入れ子の場合」を含めさせる |

### 却下

- **パターン5-3(mutation-test をフック・ゲートに適用)**: mutmut は対象ソースを
  その場で書き換える。`.claude/hooks/` は保護パスであり、guard_bash はこの実行を
  ブロックしない(実測 exit 0)。中断時にガード本体が変異したまま残りうるため、
  invariants「安全ガード」節の趣旨に反する。検出力の担保は 5-1(dc5c5b5)で代替。
- **パターン6-1(.gitignore に verdict/audit を追加)**: 前提が誤り。README L253-259 は
  除外が**下流プロジェクト向け**であり、テンプレート本体では verdict を開発記録として
  意図的にコミットすると既に明記している。適用するとパターン1(記述と実装の食い違い)を
  自ら増やす。
- **パターン6-2(codex_gate.py の除外)/ 6-3(guard_bash のヒアドキュメント除外)**:
  invariants「フックのロジック変更は却下」、6-3 はさらに「ブロック条件を緩める変更は却下」。
- **パターン6-4(verify-hooks の out-of-scope テスト)**: verify-hooks.sh:118 と
  verify-hooks.ps1:94 の両方の変更が必要で、invariants「1回の改善で変更するファイルは1つ」に
  抵触する。ユーザー判断に委ねる。

### 未着手(1ファイル制約のため見送り)

- README 3.8 のルール表・末尾のディレクトリ一覧に consistency.md の行が無い
  (taste.md も 3.8 表に無い前例があり矛盾は生じていない)。
