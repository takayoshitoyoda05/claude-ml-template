# 計画: リモート運用(Remote Control)のテンプレート組み込み

- 設計書: `docs/drafts/remote-ops-spec.md`(366行。docs/active/ へは移動しない。理由は現状分析)
- ブランチ: pipeline/20260726-remote-ops
- 作業スコープ: /home/toyod/claude-ml-template(リポジトリ直下・テンプレート本体)

experiment: false
<!-- 本実装はコード・ドキュメント変更のみで学習・実験を伴わないため plan_gate の
     チェック対象外。箇条書きにすると `^\s*experiment\s*:\s*false$` に一致しないので
     必ず独立した行に書く -->

## 目的

Remote Control(PC のローカルセッションにスマホ・ブラウザから接続する Claude Code
公式機能)の起動を、どのプロジェクトでも同じ1コマンドに縮める。起動スクリプト
2本を新規追加し、doctor での前提チェックと init/update での配布を通す。

## 現状分析

### 事実確認(すべて実測済み)

- **確認済み: 設計書の起動コマンド `claude remote-control --name "<名前>"` は正しい。そのまま実装する。**
  実測(claude 2.1.220):
  - `claude remote-control --help` → exit 0。`Remote Control - Control local sessions from
    claude.ai/code or the Claude mobile app` / `USAGE  claude remote-control [options]` /
    `OPTIONS  --name <name>  Name for the session (shown in claude.ai/code)` を出力する。
    `--spawn <mode>`(same-dir / worktree / session)・`--capacity <N>` も持つ。
  - `claude remote-control --name probe-test --help` → exit 0(`Unknown argument` は出ない)。
  - ヘルプの DESCRIPTION が `Run this command in the directory you want to work in, then
    connect from your phone or a browser` と書いており、設計書の意図(起動して最小化し
    スマホから接続する)に一致する。
- **確認済み(初版の誤判定の記録。再発防止のため残す)**: 本計画の初版は「`remote-control`
  サブコマンドは存在しない」と判定し、`claude --remote-control "<名前>"` への訂正を
  逸脱 D-1 として指示していた。根拠は `claude --help` の `Commands:` 一覧に
  `remote-control` が無いこと(実測: `agents / auth / auto-mode / doctor / gateway /
  install / mcp / plugin / project / setup-token / ultrareview / update` のみ。
  `claude --help | grep -c "^  remote-control"` は 0)。しかし **`remote-control` は
  主ヘルプに載らない隠しサブコマンド**であり、**Commands 一覧の不在は「存在しない」ことの
  証拠にならない**。→ **サブコマンドの有無は `<コマンド> <サブコマンド> --help` を実行して
  確かめる。一覧の不在だけで否定しない**(Codex クロスレビューの指摘により撤回)。
- 確認済み: 2つの形式は**別機能**であり混同してはならない。
  `claude --remote-control [name]`(メインコマンドのフラグ)は Remote Control 有効の
  **対話セッションを1つ起動**する。`claude remote-control --name <name>`(サブコマンド)は
  claude.ai/code・モバイルから**ローカルセッション群を制御するモード**で `--spawn` /
  `--capacity` を持つ。設計書が使うのは後者。
- **確認済み(設計書セクション4の前提が事実と異なる): 4つのインストーラは doctor も
  verify-hooks も配布していない。** `grep -rn "verify-hooks\|doctor" claude-init.sh
  claude-update.sh claude-init.ps1 claude-update.ps1` は**0件**。したがって設計書 L225
  「既存の doctor / verify-hooks を配布している処理と同じ場所に、同じ方式で追加する」の
  「同じ方式」は**存在しない**。**ルート直下ファイルを配布する処理を新設する**(D-2)。
- 確認済み: 既存の配布処理は4方式に分類できる。(1) `.claude/<item>` のディレクトリ丸ごと
  コピー(agents/commands/hooks/skills/output-styles/rules)、(2) `agents/shared/` の
  ファイル単位上書き、(3) `.codex/skills/` のディレクトリ単位置換、(4) `templates/*.template`
  と `.github/workflows/spec-gate.yml` の**既存優先(あれば保持)**。
  ルート直下の単体ファイルを配布する既存処理は無い。
- 確認済み: `git ls-files -s '*.sh' '*.ps1'` の結果、既存の .sh 4本(claude-init.sh /
  claude-update.sh / doctor.sh / verify-hooks.sh)は全て **100644(実行権限なし)**。
  README L153-154 は `chmod +x claude-update.sh && ./claude-update.sh` と、ユーザーに
  chmod させる導線になっている。`git config core.filemode` は `true`。
- 確認済み: .ps1 4本(claude-init / claude-update / doctor / verify-hooks)は**全て BOM 付き**
  (`head -c 3 <f> | xxd -p` が全て `efbbbf`)。コミット b57fc32 で付与済み。
- 確認済み: WSL から Windows PowerShell 5.1 の構文検査が動く。`powershell.exe -NoProfile
  -Command '...Parser::ParseFile(...)'` を `doctor.ps1` に対して実行し `0`(エラー0件)を得た。
  → **.ps1 は「Linux 上で検証不能」ではない。構文検査を検証方法に必ず含める。**
- 確認済み: `.gitattributes` は `*.sh text eol=lf` / `*.py text eol=lf` のみ。.ps1 の改行は未固定。
- 確認済み: guard_scope は本計画の全対象ファイル(claude-remote.sh/.ps1、doctor.*、
  claude-init.*、claude-update.*、README.md)に対し **exit 0**(書き込み可)。保護パスではない。
  guard_bash は `chmod +x claude-remote.sh` を通す(exit 0)。
- 確認済み: 設計書に「## 受け入れ条件」テーブルは**無い**。`docs/active/` へ移すと
  `_common.parse_acceptance_table` が `AcceptanceTableError` を出し `spec_gate.py` が exit 2 で
  全体をブロックする。現状 `docs/active/` は空で、同種の仕様書12本は全て `docs/drafts/` に
  残置されている。**本計画も drafts 据え置き**とし、トレーサビリティは
  **設計書のセクション番号 S1〜S6 を要件IDの代用**とする(前計画 20260725-control-patterns と同じ扱い)。
- 確認済み: `.gitignore` L7 に `docs/` があり `git ls-files docs/` は空。設計書 L362 の
  `git rm docs/drafts/remote-ops-spec.md` は**実行できない**
  (`fatal: pathspec did not match any files`)。仕様書の削除は実装範囲に含めない。
- 確認済み: 設計書 L354 の一括ステージ指示(`git add` に `-A` を付ける形)は guard_bash が
  ブロックする(guard_bash.py L385-387。`. / -A / -u / --all / --update` を禁止)。
  **パスを明示した `git add <path> <path> ...` に読み替える**。
- 確認済み: README の該当箇所。挿入先は 1節の末尾で、`### セキュリティプラグインの導入(推奨)`
  (L373)の本文が L390 で終わり、L392 が `---`、L394 が `## 2. 使い方`。`####` 見出しは
  README 内で既に32回使われており、設計書 S5 の `####` 構成はそのまま使える。
  ファイル一覧(6節)は L1386-1390 でルート直下スクリプト4組を**全て**掲載している
  (claude-init / claude-update / verify-hooks / doctor)。
- 確認済み: `CLAUDE_CONTROL_LEVEL` は `.claude/commands/ml-pipeline.md` と
  `.claude/hooks/notify.py` に実装済みだが、**README には1箇所も出てこない**。
  設計書 S5 の注意点表は `CLAUDE_CONTROL_LEVEL=L2` / `L3` を前提に書かれているため、
  読者が定義に辿り着けるよう参照先を1行添える(D-5)。
- 確認済み: `docs/reports/` の README 表記は `docs/reports/<実行日時>/`(L1114)。
  設計書 S5 の `<日時>` はこれに合わせる(D-6)。
- 確認済み: CHANGELOG は `## [Unreleased]` 配下に `### Added(日付)` 形式。最新は
  `### Added(2026-07-24)`(L53)。`### Added(2026-07-26)` は未作成。
- 確認済み: `verify-hooks.sh` / `.ps1` はルート直下スクリプト(doctor 等)を一切参照しない
  (`grep -n "doctor\|claude-init\|claude-update" verify-hooks.sh` が0件)。
  claude-remote はフックではないため **verify-hooks へのテスト追加は行わない**(最小diff)。
- 確認済み: `.ps1` の BOM 正規化コマンドは冪等かつ非破壊。`doctor.ps1` のコピーに対し
  `p.write_text(p.read_text(encoding='utf-8-sig'), encoding='utf-8-sig')` を2回実行しても
  先頭3バイトは `efbbbf` のままで、原本と `cmp` が一致した。
- 確認済み: 計画ファイル名 `20260726-remote-ops.md` は plan_gate の
  `_slug_from_branch("pipeline/20260726-remote-ops")` = `20260726-remote-ops` に直接一致する。

## 設計書からの逸脱(確定。Generator はここを設計書より優先する)

| ID | 設計書の記述 | 実装する内容 | 理由 |
|----|------------|------------|------|
| D-1 | ~~`claude remote-control --name "$Name"`(L106/146/152)~~ | **撤回。設計書のまま実装する** | 初版は「`remote-control` サブコマンドは無い」と誤判定した(根拠は主ヘルプ `Commands:` 一覧の不在)。実測で隠しサブコマンドとして実在することを確認したため撤回。番号は詰めず誤判定の記録として残す。経緯は現状分析を参照 |
| D-2 | 「既存の doctor / verify-hooks を配布している処理と同じ方式で」(L225) | ルート直下ファイルの配布ブロックを**新設**し、4スクリプトの `.github/workflows` ブロックの直後に同じ形で置く | その既存処理は存在しない(grep 0件) |
| D-3 | doctor.ps1 のバージョン確認を try/catch で行う(L169-176) | `if (Get-Command "claude" -ErrorAction SilentlyContinue) { ... }` に変更 | doctor.sh 側は `command -v claude` で判定しており、対になるファイルの構造を揃える。doctor.ps1 は `$ErrorActionPreference = "Stop"` のため未インストール時に例外が飛ぶのを Get-Command で確実に避ける |
| D-4 | `Write-Host "=== リモート運用(Remote Control)===";`(L166、行末セミコロン) | 行末のセミコロンを付けない | doctor.ps1 の既存行に行末セミコロンは1つも無い |
| D-5 | 注意点表で `CLAUDE_CONTROL_LEVEL=L2`/`L3` を参照(L304) | 表の直後に定義の参照先(`/ml-pipeline` の「自律度レベル」節)を1行添える | README には CLAUDE_CONTROL_LEVEL の定義が無く、読者が意味に辿り着けない |
| D-6 | `docs/reports/<日時>/report.md`(L313) | `docs/reports/<実行日時>/report.md` | README L1114 の既存表記に合わせる |
| D-7 | 一括ステージ(L354)/ `git rm docs/drafts/remote-ops-spec.md`(L362) | 実装範囲に含めない(「完了後のユーザー操作」参照) | 前者は guard_bash がブロック、後者は docs/ が git 管理外で実行不能 |

## 共通文字列の固定(全群が同一文字列を書く。並列実行時のドリフト防止)

以下は複数ファイルにまたがって現れる。**一字一句この通りに書く**(検証で機械照合する)。

| 用途 | 固定文字列 |
|------|-----------|
| 起動コマンド(sh 直接) | `exec claude remote-control --name "$NAME"` |
| 起動コマンド(sh・tmux 経由) | `exec tmux new -s "$SESSION" "claude remote-control --name '$NAME'"` |
| 起動コマンド(ps1) | `claude remote-control --name "$Name"` |
| doctor の見出し | `=== リモート運用(Remote Control)===` |
| doctor の確認行 | `確認: /config の「Enable Remote Control for all sessions」が true か` |
| init のコピー成功メッセージ | `OK: <ファイル名> を配置しました` |
| update のコピー成功メッセージ | `OK: <ファイル名> を更新しました` |
| 配布対象の並び | `claude-remote.ps1` → `claude-remote.sh` の順(設計書 L229 / L242 に合わせる) |

## 変更対象

| ファイル | 区分 | 変更内容 |
|---------|------|---------|
| claude-remote.sh | NEW | 設計書 S2 のスクリプトをそのまま実装。実行権限を付ける |
| claude-remote.ps1 | NEW | 設計書 S1 のスクリプトをそのまま実装。**UTF-8 BOM 付き** |
| doctor.sh | MOD | 末尾にリモート運用チェックを追記(S3) |
| doctor.ps1 | MOD | try/finally の**外側**・ファイル末尾に同(S3、D-3/D-4 適用) |
| claude-update.sh | MOD | ルート直下スクリプト配布ブロックを新設(S4、D-2) |
| claude-update.ps1 | MOD | 同上 |
| claude-init.sh | MOD | 同上 |
| claude-init.ps1 | MOD | 同上 |
| README.md | MOD | 1節末尾に `### リモート運用(スマホ・ブラウザから操作)`(S5)。6節ファイル一覧に1行 |
| CHANGELOG.md | MOD | `### Added(2026-07-26)` を新設し1項目(慣習) |

## 実装手順

**全 .ps1 編集ステップ共通の後処理(必須)**: Write/Edit ツールは BOM を保存しないことがある。
.ps1 を作成・編集したステップの直後に必ず次を実行し、`head -c 3 <file> | xxd -p` が
`efbbbf` になることを確認する(冪等・非破壊であることを実測済み)。

```bash
uv run python -c "import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.write_text(p.read_text(encoding='utf-8-sig'), encoding='utf-8-sig')" <file>
```

| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 1 | 設計書 S2 の内容で新規作成(起動コマンドは設計書のまま `claude remote-control --name`)。既存の `claude-init.sh` / `doctor.sh` の書式(シバン、`set -euo pipefail`、日本語 echo、`command -v` 判定)に倣う。作成後 `chmod +x claude-remote.sh` を実行し LF 改行を保つ | claude-remote.sh | なし | A |
| 2 | 設計書 S1 の内容で新規作成(起動コマンドは設計書のまま `claude remote-control --name`)。既存の `doctor.ps1` / `claude-update.ps1` の書式(`param()`、`$ErrorActionPreference = "Stop"`、日本語 `Write-Host`、`Get-Command ... -ErrorAction SilentlyContinue`)に倣う。**作成後に BOM 正規化コマンドを実行**(未実施だと Windows PowerShell 5.1 が Shift-JIS として読み構文エラーで起動不能になる) | claude-remote.ps1 | なし | A |
| 3 | ファイル末尾(L73 の後)にリモート運用チェックを追記(S3 の sh 版そのまま) | doctor.sh | なし | B |
| 4 | **`finally { ... }` の閉じ括弧より後・ファイル末尾**にリモート運用チェックを追記(S3 の ps1 版に D-3/D-4 を適用)。try の内側に入れると `$Tmp` 削除より前に走り doctor.sh の追記位置(末尾)とズレる。編集後に BOM 正規化コマンドを実行 | doctor.ps1 | なし | B |
| 5 | `.github/workflows` ブロック(L119-125)の**直後**にルート直下スクリプト配布ブロックを新設(設計書 L242-248 の形。メッセージは `OK: <f> を更新しました`、末尾に `chmod +x claude-remote.sh 2>/dev/null \|\| true`)。ループ・`[ -f ... ]` 判定・`echo "OK: ..."` の書式は同ファイル既存の `templates/*.template` ループ(L107-116)に倣う | claude-update.sh | なし | C |
| 6 | 同じ位置(L129 の `.github/workflows` ブロック直後)に ps1 版を追加(設計書 L229-235 の形。メッセージは `OK: <f> を更新しました`)。**chmod 相当は書かない**(Windows に実行権限の概念が無いため)。編集後に BOM 正規化コマンドを実行 | claude-update.ps1 | なし | C |
| 7 | `.github/workflows` ブロック(L128-135)の直後に Step 5 と同一構造のブロックを追加。メッセージのみ `OK: <f> を配置しました`(init の既存語彙。L114 の「を配布しました」ではなく L53 の「を配置しました」に合わせる) | claude-init.sh | Step 5 | C |
| 8 | `.github/workflows` ブロック(L118-125)の直後に Step 6 と同一構造のブロックを追加。メッセージは `OK: <f> を配置しました`。編集後に BOM 正規化コマンドを実行 | claude-init.ps1 | Step 6 | C |
| 9 | (配置先はユーザー承認済み: 1節末尾)L390 の直後・L392 の `---` の**前**に `### リモート運用(スマホ・ブラウザから操作)` を追加(設計書 S5 の markdown に D-5/D-6 を適用)。見出し階層は同節の既存 `###`+`####` に倣う。設計書のコードブロックは**外側のフェンスを外して**本文として書く | README.md | なし | D |
| 10 | (実施はユーザー承認済み)6節ファイル一覧 L1390(`doctor.ps1 / .sh`)の直後に `claude-remote.ps1 / .sh` の1行を追加(説明の桁位置は既存行に揃える)。あわせて CHANGELOG の `### Added(2026-07-24)` ブロックの直後に `### Added(2026-07-26)` を新設し1項目追記 | README.md, CHANGELOG.md | Step 9 | D |
| 11 | 「検証方法」の全コマンドを実行し、結果を報告に貼る | (なし) | Step 1-10 | 統合(逐次) |

備考: Step 10 はどの設計書セクションにも対応しない。README 6節がルート直下スクリプト4組を
全て掲載しており、追加分だけ欠けると一覧の意味が壊れるため(慣習に基づく最小追記)。

## 並列化判定

**並列化可能**(グループ A / B / C / D)。理由: 4群の対象ファイルは完全に分離しており
(A=新規2本、B=doctor 2本、C=インストーラ4本、D=README+CHANGELOG)、群間に実行順の依存が無い。
sh / ps1 の対を別群に割らないことで、対になるファイルの文言ドリフトを構造的に防ぐ。
群をまたいで共有される文字列は「共通文字列の固定」表で確定済み。Step 11 は全群完了後の逐次。

推奨コミット(CLAUDE_COMMIT_STEP_RULE 対応でステップ番号を含める):

- A: `feat(step 1-2): リモート運用の起動スクリプト claude-remote.sh/.ps1 を追加`
- B: `feat(step 3-4): doctor にリモート運用の前提チェックを追加`
- C: `feat(step 5-8): claude-init/update で claude-remote.* を配布`
- D: `docs(step 9-10): README にリモート運用の節・ファイル一覧・CHANGELOG を追記`

## 検証方法

すべてリポジトリ直下で実行する。期待結果と異なれば FAIL。

```bash
# 1. 新規ファイルの存在と実行権限(期待: 3行の OK と 755)
test -f claude-remote.ps1 && echo "OK: claude-remote.ps1"
test -f claude-remote.sh && echo "OK: claude-remote.sh"
test -x claude-remote.sh && echo "OK: 実行権限あり"
stat -c '%a %n' claude-remote.sh   # 期待: 755(既存 .sh 4本は 644。実測で確認済み)
# 次の1行は git add した後にのみ意味がある(未ステージだと出力が空)。
# ステージ済みなら実行する。期待: 先頭が 100755
git ls-files -s claude-remote.sh

# 2. bash 構文 — 変更する .sh 全4本(期待: 4行すべて OK)
#    ps1 側が検証4で5本すべてを Parser にかけるのと対にする。
#    (実測: 変更前の doctor.sh / claude-init.sh / claude-update.sh は 3本とも OK)
for f in claude-remote.sh doctor.sh claude-init.sh claude-update.sh; do printf "%s: " "$f"; bash -n "$f" && echo "OK"; done

# 3. 改行コード(期待: 0)
grep -c $'\r' claude-remote.sh || true

# 4. PowerShell 5.1 構文チェック(期待: 5ファイルすべて 0)
( cd /mnt/c && for f in claude-remote.ps1 doctor.ps1 claude-init.ps1 claude-update.ps1 verify-hooks.ps1; do \
  printf "%s: " "$f"; powershell.exe -NoProfile -Command \
  "\$e=\$null; [void][System.Management.Automation.Language.Parser]::ParseFile('\\\\wsl.localhost\\Ubuntu\\home\\toyod\\claude-ml-template\\$f', [ref]\$null, [ref]\$e); if(\$e){\$e.Count}else{'0'}"; done )

# 5. BOM(期待: 5行すべて efbbbf)
for f in claude-remote.ps1 doctor.ps1 claude-init.ps1 claude-update.ps1 verify-hooks.ps1; do printf "%s: " "$f"; head -c 3 "$f" | xxd -p; done

# 6. 起動コマンドが設計書どおりのサブコマンド形であること
#    (期待: 前半は claude-remote.sh に2件・claude-remote.ps1 に1件、後半は OK 行)
grep -nE "claude remote-control --name" claude-remote.sh claude-remote.ps1
# フラグ形(claude --remote-control)は別機能なので使っていないこと(期待: OK 行)
! grep -nE "claude[[:space:]]+--remote-control" claude-remote.sh claude-remote.ps1 doctor.sh doctor.ps1 README.md && echo "OK: フラグ形は使っていない"

# 7. doctor の追記(期待: 2ファイルとも1件以上、diff は空)
grep -c "Remote Control" doctor.sh doctor.ps1
diff <(grep -oE '=== リモート運用\(Remote Control\)===' doctor.sh | sort -u) \
     <(grep -oE '=== リモート運用\(Remote Control\)===' doctor.ps1 | sort -u) && echo "OK: doctor 対の見出し一致"
diff <(grep -oE '確認: /config の「Enable Remote Control for all sessions」が true か' doctor.sh | sort -u) \
     <(grep -oE '確認: /config の「Enable Remote Control for all sessions」が true か' doctor.ps1 | sort -u) && echo "OK: doctor 対の確認行一致"

# 8. 配布対象(期待: 4ファイルとも uniq=2、対の diff は空)
for f in claude-init.sh claude-init.ps1 claude-update.sh claude-update.ps1; do printf "%s raw=%s uniq=%s\n" "$f" "$(grep -oE 'claude-remote\.(sh|ps1)' "$f" | wc -l)" "$(grep -oE 'claude-remote\.(sh|ps1)' "$f" | sort -u | wc -l)"; done
diff <(grep -oE 'claude-remote\.(sh|ps1)' claude-init.sh | sort -u) <(grep -oE 'claude-remote\.(sh|ps1)' claude-init.ps1 | sort -u) && echo "OK: init 対一致"
diff <(grep -oE 'claude-remote\.(sh|ps1)' claude-update.sh | sort -u) <(grep -oE 'claude-remote\.(sh|ps1)' claude-update.ps1 | sort -u) && echo "OK: update 対一致"

# 9a. 配布ブロックの実動作 / sh 版
#     claude-update.sh に実際に書いたブロックを**そのまま貼って**実行する(下記は雛形)。
SB=$(mktemp -d); mkdir -p "$SB/proj" "$SB/tmpl"
printf '#!/usr/bin/env bash\n' > "$SB/tmpl/claude-remote.sh"; printf 'x\n' > "$SB/tmpl/claude-remote.ps1"
# (i) 両方ある場合(期待: OK 行が2本、claude-remote.sh が -rwx)
( cd "$SB/proj" && TMP="$SB/tmpl" bash -c 'for f in claude-remote.ps1 claude-remote.sh; do if [ -f "$TMP/$f" ]; then cp "$TMP/$f" "$f"; echo "OK: $f を更新しました"; fi; done; chmod +x claude-remote.sh 2>/dev/null || true'; ls -l )
# (ii) 片方だけ存在する場合(期待: 1。エラー終了しない)
rm -f "$SB/proj/claude-remote.ps1" "$SB/proj/claude-remote.sh" "$SB/tmpl/claude-remote.ps1"
( cd "$SB/proj" && TMP="$SB/tmpl" bash -c 'for f in claude-remote.ps1 claude-remote.sh; do if [ -f "$TMP/$f" ]; then cp "$TMP/$f" "$f"; echo "OK: $f を更新しました"; fi; done' | grep -c '^OK:' )
# 後始末は不要($(mktemp -d) 配下)。`rm -rf` は guard_bash に止められることがあるので使わない。

# 9b. 配布ブロックの実動作 / ps1 版(9a と対。claude-update.ps1 のブロックを Windows PowerShell で実行する)
#     サンドボックスは WSL 側に置き、UNC パス \\wsl.localhost\Ubuntu\... で Windows から参照する。
#     PS_BLOCK は claude-update.ps1 に実際に書いたブロックと同一にすること($Tmp 変数名も合わせる)。
#     [Console]::OutputEncoding の指定は**必須**。無いと出力が CP932 になり、
#     WSL 側の grep が件数を返さない(実測で確認済み)。
SB2=$(mktemp -d); mkdir -p "$SB2/proj" "$SB2/tmpl"
printf 'x\n' > "$SB2/tmpl/claude-remote.ps1"; printf 'x\n' > "$SB2/tmpl/claude-remote.sh"
WIN_SB="\\\\wsl.localhost\\Ubuntu${SB2//\//\\}"
PS_BLOCK="foreach (\$f in @('claude-remote.ps1','claude-remote.sh')) { \$src = Join-Path \$Tmp \$f; if (Test-Path \$src) { Copy-Item \$src \$f -Force; Write-Host \"OK: \$f を更新しました\" } }"
PS_HEAD="[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Set-Location '$WIN_SB\\proj'; \$Tmp='$WIN_SB\\tmpl'; "
# (i) 両方ある場合(期待: 2)
powershell.exe -NoProfile -Command "$PS_HEAD$PS_BLOCK" 2>&1 | grep -c '^OK:'
# (ii) 片方だけ存在する場合(期待: 1)
rm -f "$SB2/proj/claude-remote.ps1" "$SB2/proj/claude-remote.sh" "$SB2/tmpl/claude-remote.ps1"
powershell.exe -NoProfile -Command "$PS_HEAD$PS_BLOCK" 2>&1 | grep -c '^OK:'
ls -1 "$SB2/proj"   # 期待: claude-remote.sh のみ

# 10. README / CHANGELOG(期待: すべて1件以上)
grep -n "Enable Remote Control for all sessions" README.md
grep -n "^### リモート運用(スマホ・ブラウザから操作)" README.md
grep -n "claude-remote.ps1 / .sh" README.md
grep -n "^### Added(2026-07-26)" CHANGELOG.md

# 11. 既存テストの全PASS(期待: 失敗0)
./verify-hooks.sh
```

**複数・入れ子のケース**(取りこぼし検出のため必ず確認する):

- 配布ループは**2ファイル**(.ps1 と .sh)を回す。片方しかコピーされない実装になっていないかを
  検証9a(i) / 9b(i)(OK 行が2本出るか)で見る。**片方だけ存在する場合**でも `[ -f ]` /
  `Test-Path` 判定で落ちずに残り1本を処理することを検証9a(ii) / 9b(ii)(期待: 1)で確認する。
  **sh 版と ps1 版の両方を実行すること**(片方だけの検証は、この計画が最も重視する
  sh/ps1 対称性を検証側で崩す)。
- `claude-remote.sh` の分岐は **tmux あり(既存セッションに attach / 新規作成)/ tmux なし**の3経路。
  `bash -n` は全経路を構文検査する。実起動はリモートセッションが立ち上がるため行わず、
  ユーザー確認事項とする。
- 4スクリプトへの追加は**同一ブロックの4重複**になる。検証8の raw / uniq 件数で、
  1ファイルだけ書き漏れ・重複貼りが無いことを確認する(期待: 全ファイル uniq=2)。

## リスク

- **未確認の仮定: 実セッションの起動までは確認していない。** `claude remote-control --name <名前>` は
  `claude remote-control --help` の記載と、`--name probe-test --help` を付けた実行が
  exit 0 で引数を受理することまで確認済み(claude 2.1.220)。ただし **実際に
  Remote Control サーバーが起動しスマホから見える**ところまでは検証していない
  (実行すると常駐セッションが立ち上がるため)。最終確認はユーザーの手元操作に委ねる。
- **未確認の仮定: `powercfg` の出力文言**(設計書 L80 の `現在の AC 電源設定|Current AC Power Setting`)は
  Windows の言語設定に依存する。一致しなければ警告側に倒れるだけで起動は妨げない。
- **配布は push 後に効く**。claude-init / claude-update は GitHub の公開リポジトリを clone するため、
  本ブランチを main にマージ・push するまで各プロジェクトには配布されない。
- **実行権限(確定: `claude-remote.sh` を 100755 でコミットする。ユーザー承認済み)**。既存 .sh 4本は 100644 だが、
  それらは README で `chmod +x` 付きの curl 導線が案内されている。claude-remote.sh は README と
  doctor の案内が `./claude-remote.sh` であり、clone 直後に動かないと導線が壊れる。
  あわせてインストーラ側にも `chmod +x` を残し(mode が落ちる取得経路の保険)、二重に担保する。
  - 検討した代替案: 既存に合わせ 100644 とし README を `bash claude-remote.sh` にする → 不採用。
    設計書 S3/S5 が `./claude-remote.sh` を明示しており、doctor の案内文と README の両方を
    書き換える差分の方が大きい。
- **配布方式の代替案(不採用)**:
  - `templates/*.template` 方式に寄せる(`claude-remote.sh.template` を配る)→ 不採用。
    templates/ は「既存があれば保持」のため、テンプレート側で起動スクリプトを直しても
    配布先へ永久に伝わらない。起動スクリプトはテンプレート所有物であり上書き更新が正しい。
  - `.claude/scripts/` 等に置き既存のディレクトリコピーに相乗りする → 不採用。設計書 S1/S2/S5 が
    リポジトリ直下(`./claude-remote.sh`)を前提にしており、doctor の `Test-Path "claude-remote.ps1"`
    とも整合しない。
  - 「既存なら保持」にする → 不採用。プロジェクト固有の内容を持たないファイルであり、
    保持すると不具合が凍結される(`.claude/` や `agents/shared/` と同じ上書き方針を採る)。
- **doctor.ps1 の追記位置**。try/finally の外に置くため、`.claude` 未検出などの早期 `exit 1` 経路では
  リモート運用チェックが出ない。doctor.sh も同じ挙動(末尾追記)であり、対の非対称は生まない。
- **BOM の消失**。.ps1 を Edit ツールで編集すると BOM が落ちる可能性がある。落ちると
  Windows PowerShell 5.1 が Shift-JIS として解釈し**構文エラーで起動不能**になる(本日実測)。
  各 .ps1 編集ステップの直後に正規化コマンドを実行し、検証5で全ファイルを再確認する。
- **設計書と実装の食い違いを残さない**。逸脱 D-2〜D-7 は設計書本文には反映されないが、
  設計書は git 管理外の drafts であり、実装後は本計画の「設計書からの逸脱」表が正となる。
- **一覧に無いことを「存在しない」と読まない**(D-1 撤回の教訓)。CLI・API・設定キーの有無を
  判定するときは、一覧の不在ではなく**その対象を直接叩いた結果**を根拠にする。

## トレーサビリティ

設計書に受け入れ条件テーブルが無いため、セクション番号 S1〜S6 を要件IDの代用とする。

| ID | 内容 | 対応ステップ | 検証方法 |
|----|------|------------|---------|
| S1 | claude-remote.ps1 の新規作成 | Step 2 | 検証1(存在)/ 検証4(構文0件)/ 検証5(BOM)/ 検証6(`remote-control --name`) |
| S2 | claude-remote.sh の新規作成 | Step 1 | 検証1(存在・`stat` で 755)/ 検証2(`bash -n` 4本)/ 検証3(LF)/ 検証6 |
| S3 | doctor へのリモート運用チェック追加 | Step 3, 4 | 検証7(件数と対の文言一致)/ 検証2(doctor.sh の `bash -n`)/ 検証4・5(doctor.ps1) |
| S4 | claude-init / claude-update への配布追加 | Step 5, 6, 7, 8 | 検証8(4ファイル・対一致・件数)/ 検証9a(sh ブロックの実動作)/ 検証9b(ps1 ブロックの実動作)/ 検証2(sh の `bash -n`)/ 検証4・5(ps1) |
| S5 | README へのリモート運用セクション追加 | Step 9 | 検証10(見出し・キーフレーズ)/ 検証6(誤コマンド0件) |
| S6 | 完了後の検証 | Step 11 | 検証1〜11 の全実行。コミット/push/仕様書削除は「完了後のユーザー操作」へ |
| (慣習) | README ファイル一覧・CHANGELOG | Step 10 | 検証10 |

全 S-ID に対応ステップがある。どの S-ID にも対応しないステップは Step 10 のみで、理由は実装手順の備考に記載。

## 完了後のユーザー操作(本計画では実行しない)

- **ステージは明示パスで行う**。設計書 L354 の一括ステージ形式は guard_bash がブロックする(実測)。
  例: `git add claude-remote.sh claude-remote.ps1 doctor.sh doctor.ps1 claude-init.sh claude-init.ps1 claude-update.sh claude-update.ps1 README.md CHANGELOG.md`
- **`git push` / main へのマージ**は ml-pipeline 手順9 のマージ判断でユーザーが決める。
- **仕様書 `docs/drafts/remote-ops-spec.md` の削除は計画に含めない**。理由1: 設計書 L9-10 が削除の前提を
  「verify-hooks 全PASS かつ git push 完了後」としており、push がユーザー承認事項であるため。
  理由2: `docs/` は .gitignore 対象で `git ls-files docs/` は空。`git rm` は
  `fatal: pathspec did not match any files` になる。削除したい場合は通常の
  `rm docs/drafts/remote-ops-spec.md` であり、コミットも push も発生しない。
- **マシンごとに1回の手動設定**: `claude` 起動 → `/config` →
  「Enable Remote Control for all sessions」を true。テンプレートからは配布できない(設計書 L24-30)。

## 確定事項(ユーザー回答済み。2026-07-26)

未確定事項3点はユーザーの回答で確定した。いずれも planner の既定どおりで、計画本文は
この確定内容で書かれている。**Generator は以下を選択肢としてではなく確定仕様として扱う**。

| # | 論点 | 確定内容 | 反映先 |
|---|------|---------|--------|
| 1 | README の配置 | **1節(セットアップ)の末尾**(セキュリティプラグイン節の後、L392 の `---` の前) | Step 9 |
| 2 | `claude-remote.sh` の実行権限 | **100755 でコミットする**(既存 .sh 4本の 644 とは意図的に変える。理由はリスク節と ADR 0005) | Step 1、検証1 |
| 3 | 慣習的な追記 | **両方行う**(README 6節のファイル一覧 + CHANGELOG の `### Added(2026-07-26)`) | Step 10、検証10 |

## 知識の自動スタック(確認結果)

- (a) CONTEXT.md: リポジトリ直下に CONTEXT.md は存在しない(テンプレート本体のため)。追記対象なし。
- (b) ADR: **作成対象あり** — 「ルート直下スクリプトの配布方式の新設」(上書き更新・配置位置・
  実行権限の扱い)は複数案から選んだ後戻りしにくい決定のため
  `docs/adr/0005-root-script-distribution.md` に記録する(既存 0001〜0004 の書式に倣う)。
  D-1(起動コマンドの「訂正」)は撤回されたため ADR の対象ではない。
- (c) EXPERIMENT_LOG: 学習・実験を伴わない(`experiment: false`)。追記対象なし。
