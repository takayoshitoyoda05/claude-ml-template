# セッション上限からの自動再開(常時チェックポイント + 起動時注入)

要件ソース: ユーザーの口頭要件(設計書なし)。要件 ID は本計画内で R-1〜R-6 として定義する。

experiment: false

## 目的

セッション上限は予告なく来るため「中断時に避難させる」方式は成立しない。各ターン終了時に進行状態を機械的に上書き記録し、次のセッション開始時に自動で文脈へ戻すことで、上限で切れた作業を人手の引き継ぎ操作なしに再開できるようにする。

## 要件(R-ID)

| ID | 要件 |
|---|---|
| R-1 | パイプライン進行状態(ブランチ・作業ツリー・対応する計画の手順表・直近の会話の末尾)を工程の節目ごとに機械的に記録し、常に最新1件が存在する |
| R-2 | 記録が残っていればセッション開始時に自動的に文脈へ注入し、再開を促す(自動続行はしない) |
| R-3 | 記録内容に秘密情報を平文で残さない(既存 `_mask.mask()` に準拠) |
| R-4 | 既存フックの配線と挙動を変えない。compact 用フック2本(`checkpoint_before_compact.py` / `reinject_after_compact.py`)は二重注入せず、`settings.json` の既存 Stop 6件・PreCompact・SessionStart(compact)エントリも順序・内容とも保存される |
| R-5 | 記録が無い・古い・壊れていてもセッション開始を妨げない(この機能に限り fail-open) |
| R-6 | 手動の handoff スキルと自動記録の責務境界をドキュメントで明示する |

## 現状分析

- 既存の状態保存は PreCompact 契機のみ。`checkpoint_before_compact.py` は圧縮直前にしか動かず、セッション上限では発火しない。
- `reinject_after_compact.py` は `source != "compact"` で即 `sys.exit(0)`(16-18行)。通常起動では何も注入しない。`.claude/settings.json` の SessionStart エントリも `"matcher": "compact"` 条件付き。つまり「起動時の自動再開」は現状ゼロ。
- `handoff` スキルは人手起動の要約文書(`.claude/handoffs/`、git 管理下、別マシン向け)。上限で突然切れる場面では起動する機会が無い。
- 確認済み: `.claude/hooks/` と `.claude/settings.json` は `_common.py` の `PROTECTED_PATH_PATTERNS`(63-81行)に含まれ、Claude からは Write/Edit も `cp`/リダイレクトも不可。
- 確認済み: `.claude/checkpoints/` 配下は、上記の保護とは**別系統**の `ARTIFACT_DIR_PATTERNS`(`_common.py` 47-53行に `/checkpoints/` を含む)により、`guard_scope.py` 176-182行で Write/Edit が**全面ブロック**される(実測: `.claude/checkpoints/settings.json.proposed` への Write で exit 2「生成物/大容量ファイルへの書き込みは禁止です」)。したがって Claude はこのディレクトリに一時ファイルを作れない。ブロックは `guard_scope`(PreToolUse: Edit/Write/NotebookEdit)のみで、`guard_bash` は `ARTIFACT_DIR_PATTERNS` を参照しない(実測: grep で guard_scope の2箇所のみ)。読み取り(Read)は対象外なので状態ファイルの閲覧はできる。
- 確認済み: 一方で**フックは PreToolUse を通らない別プロセス**であり、`.claude/checkpoints/` への書き込みは可能。根拠: 既存の `checkpoint_before_compact.py` が同ディレクトリに `latest.md` / `state-*.md` / `transcript-*.jsonl` を書いており、実物が14世代存在する(`ls .claude/checkpoints/`)。`codex_gate` のセンチネルも同ディレクトリ。よって**記録フックの出力先 `.claude/checkpoints/session_state.md` は設計変更不要**。受け入れテストのフィクスチャも pytest プロセスが `tmp_path` 配下に作るためガードの影響を受けない。
- 確認済み: `.gitignore` 15-17行に `/_staging_*.py` が「ガード保護ファイルの変更をユーザーに手動反映してもらうための一時ファイル」として定義されている。ただし `.py` 限定のため JSON を拾えない。`_staging` を参照するコード・インストーラは存在せず(`rg --hidden` で `.gitignore:17` のみ)、`_staging*` に一致する追跡ファイルも0件(`git ls-files`)。よってパターンを `/_staging_*` に広げても既存用途への影響はない。`.claude/checkpoints/` は `.gitignore` 1行目で除外済み。
- 確認済み: `git check-ignore -v .claude/checkpoints/session_state.md` → `.gitignore:1` に一致。かつ `_common.py:repo_state_signature()` の `git status --porcelain -z --untracked-files=all` は `--ignored` を付けないため、新しい状態ファイルを毎ターン書いても enforce_eval / spec_gate / quality_gate のキャッシュ署名を乱さない。
- 確認済み: `claude-init.sh` 39-44 行は `hooks` ディレクトリごと `cp -r` し、`settings.json` を丸ごと配る。よってフックを1本増やしてもインストーラ(sh/ps1)と `verify-installers.sh` の変更は不要。
- 確認済み: `verify-hooks.sh` / `.ps1` には compact 系フックのテストが無く、checkpoints への言及は guard 系のブロック検査のみ。よって本件のテストは pytest 側(`tests/`)に置き、sh/ps1 の対ファイルは変更しない。
- 確認済み: 環境フラグの登録先は `README.md` の env 表(254行付近)と `templates/settings.local.json.template` の2箇所のみ(`CLAUDE_ACTION_LOG` を grep して確認)。読み取り側の慣例は `os.environ.get("CLAUDE_ACTION_LOG", "1") == "0"`(action_log.py:28)。
- 確認済み: `plan_gate.py` はブランチ最終セグメントから `-group-<英数字>` を除いた slug で `.claude/plans/{slug}.md` → `*-{slug}.md`(日付8桁+`-`、完全一致、候補1件のみ採用)と計画を特定する(58-88行)。
- 確認済み: セッションのトランスクリプトは `~/.claude/projects/<encoded-cwd>/<session_id>.jsonl` に置かれ、実測で単一セッション 3.1 MB。全読みは毎ターンの Stop では重い。

### 設計判断(採用案)

1. **記録は Stop フック(同期)**: 「工程の節目」= 各ターン終了とみなす。パイプライン手順書に「状態を書け」と書く自己申告方式は、文脈圧縮後に最も守られなくなるため採らない(機械的強制 > 自己申告)。`async` にはしない(上限で殺される直前に書き込みが完了しない可能性があるため)。Stop 配列の**先頭**に置き、後続ゲートがブロックしても記録が残るようにする。
2. **保存先は `.claude/checkpoints/session_state.md` の単一ファイル(上書き)**。gitignore 対象=別クローン・別マシンでは復元できない。これは**仕様として割り切る**。理由: (a) 毎ターン更新される機械生成物を追跡ファイルにすると、作業ツリーが常時 dirty になり codex_gate の「未コミット変更が残っていれば再レビュー」と衝突する、(b) 生の会話末尾を含むため git 履歴に残すべきでない、(c) 別マシンへの引き継ぎは既存の handoff スキル(git 管理下)の担当であり、責務が分かれる。なお、この保存先に書けるのは記録フック(別プロセス)であって Claude の Write ツールではない。`guard_scope` の `ARTIFACT_DIR_PATTERNS` により Claude 自身はこのディレクトリを改変できず、状態記録の偽装ができない点はむしろ本方式に有利に働く。
3. **注入は新規 SessionStart フック(matcher `startup`)**。既存 `reinject_after_compact.py` を拡張せず新規に作ることで R-4 を構造的に満たす。新フックは自身でも `source == "startup"` を再判定し、matcher の解釈がどうであれ compact 時に二重注入しない。
4. **注入の抑制条件**: 記録されたブランチが現在ブランチと異なる、または記録の mtime が 72 時間より古い場合は注入しない(72h = 金曜に切れて月曜に再開する最短ケースを拾える値)。
5. **既定 ON + キルスイッチ** `CLAUDE_SESSION_RESUME=0`。ブロックしない情報系フック(PreCompact 系・action_log)と同じ扱いにする。opt-in にすると依頼者の環境でも既定オフになり要件を満たさないため、既定 ON とし無効化手段のみ用意する。
6. **この機能における fail-closed の解釈**: ブロック系ゲート(spec_gate 等)の fail-closed 方針は適用しない。阻止すべき危険行為が無く、止めることの害(セッションが始まらない)が大きいため、記録・注入の失敗は常に `exit 0` の fail-open とする。この解釈をフックの docstring と README に明記する。

## 変更対象

| ファイル | 種別 | 変更内容 |
|---|---|---|
| `tests/test_session_resume.py` | 新規 | PC-1〜PC-13 の受け入れテスト(`tests/test_plan_gate.py` の subprocess CLI 起動形式に倣う) |
| `_staging_record_session_state.py` | 新規(一時) | Stop 用記録フックの完成版全文。ユーザーが `.claude/hooks/record_session_state.py` へ `cp` |
| `_staging_resume_session_state.py` | 新規(一時) | SessionStart(startup)用注入フックの完成版全文。ユーザーが `.claude/hooks/resume_session_state.py` へ `cp` |
| `_staging_gen_settings.py` | 新規(一時) | `settings.json` を読み込んで2要素を挿入し `_staging_settings.json` を出力する使い捨てスクリプト。Step 7 で削除 |
| `_staging_settings.json` | 新規(一時) | 2ブロック挿入後の `settings.json` 全文(プログラム生成)。ユーザーが `cp` で適用後に削除 |
| `.gitignore` | 変更 | 17行目 `/_staging_*.py` → `/_staging_*`(拡張子限定を外し、JSON の staging を同じ仕組みに乗せる) |
| `README.md` | 変更 | フック表(908-922行)に2行、ディレクトリツリー(1596-1597行付近)に2行、`## 0. 迷ったら(エントリーポイントの選び方)`(47行)配下の表(50-62行)に1行、env 表(254行付近)に `CLAUDE_SESSION_RESUME` 1行 |
| `templates/settings.local.json.template` | 変更 | `"CLAUDE_SESSION_RESUME": "1"` を1行追加 |
| `.claude/skills/handoff/SKILL.md` | 変更 | 自動記録との責務境界を3行以内で追記 |
| `CHANGELOG.md` | 変更 | `[Unreleased]` に項目1件 |
| `.claude/hooks/record_session_state.py` | 新規(ユーザー適用) | 保護パス。Claude は書けない |
| `.claude/hooks/resume_session_state.py` | 新規(ユーザー適用) | 保護パス。Claude は書けない |
| `.claude/settings.json` | 変更(ユーザー適用) | Stop 配列の先頭に1要素、SessionStart 配列に `matcher: "startup"` のエントリを1つ追加。既存行は一切変更しない |

## 事後条件(postconditions)

PC-1〜PC-13 と PC-15 は `tests/test_session_resume.py` で、PC-14・PC-16・PC-17 は Step 8 の git / python コマンド(**適用直後・コミット前**に実行)で機械照合する。適用がユーザーの手動 `cp` である以上、適用結果の検証は pytest 内で完結しないため、後者は検証方法に実行コマンドとして明記する。「record」= `record_session_state.py`、「resume」= `resume_session_state.py`。pytest の各ケースは `tmp_path` に `git init` した一時リポジトリを作り `cwd` を移して実行する。

| ID | 対象 | 入力 | 満たすべき条件 | 要件 |
|---|---|---|---|---|
| PC-1 | record | 正常な Stop JSON(`transcript_path` あり)を stdin | exit 0。`.claude/checkpoints/session_state.md` が生成され、`## Git ブランチ:` 行に現在ブランチ名、`## git status --short` セクション、記録時刻(`YYYY-MM-DD`)を含む | R-1 |
| PC-2 | record | stdin が空 / 不正 JSON / 必須キー欠落 | exit 0、stdout 空、stderr にトレースバックを出さない | R-5 |
| PC-3 | record | `transcript_path` が存在しないパス / 読めないバイト列 | exit 0 かつ状態ファイルは生成され、会話セクションに「(取得不可)」相当の記載がある | R-5 |
| PC-4 | record | 同一リポジトリで2回実行(間に1秒以上) | `.claude/checkpoints/` 内の `session_state*` は1ファイルのみ(世代が増えない)。2回目の記録時刻が1回目と異なる | R-1 |
| PC-5 | record | transcript に `sk-` で始まる 40 文字級のキー様文字列を含む会話 | 状態ファイルに原文字列が含まれず `[MASKED]` を含む | R-3 |
| PC-6 | record | ブランチ `pipeline/20260805-foo-group-A`、`.claude/plans/20260805-foo.md`(実装手順表つき) | 状態ファイルに `20260805-foo.md` のパスと実装手順表の行(先頭20行以内)が含まれる | R-1 |
| PC-7 | record | (a) 記録フックのソース、(b) 20 MB のダミー transcript | (a) ソースに `.seek(` が含まれる(末尾シーク設計の直接検査)。(b) exit 0 かつ実行時間 5 秒未満。**時間だけでは検出力が無い**(実測: 20 MB の素朴な全読み+正規表現マスクでも 0.06〜0.09 秒で、閾値 5 秒を余裕で通る)ため、(a) を主検査、(b) を退行検知として併用する | R-1 |
| PC-8 | resume | `source="startup"`、同一ブランチ・mtime 現在の状態ファイル | exit 0。stdout に状態ファイル本文と「自動で続行せずユーザーに確認する」旨の再開指示を含む | R-2 |
| PC-9 | resume | `source="compact"` | stdout 空・exit 0(既存 reinject との二重注入なし) | R-4 |
| PC-10 | resume | 状態ファイルなし / 空 / 不正 UTF-8 バイト列 | stdout 空・exit 0、トレースバックなし | R-5 |
| PC-11 | resume | 状態ファイルの記録ブランチが現在ブランチと不一致 / mtime が 73 時間前 | それぞれ stdout 空・exit 0 | R-2 |
| PC-12 | 既存 `reinject_after_compact.py` | `source="compact"` + `latest.md` あり | 従来どおり `latest.md` 本文を stdout に出力・exit 0(回帰) | R-4 |
| PC-13 | record の slug 導出 | ブランチ名3種(`pipeline/20260805-foo`、`pipeline/20260805-foo-group-A`、`foo`) | `plan_gate._slug_from_branch()` と同じ文字列を返す(両モジュールを import して比較)。照合対象は slug 導出のみで、`plan_gate._select_plan_path()` の候補選定は**複製しない**ため parity の対象外(PC-15 が代替の安全条件を固定する) | R-1 |
| PC-14 | `.gitignore` | Step 4 適用後のリポジトリ | `git check-ignore -v _staging_settings.json` が `.gitignore:17:/_staging_*` を返し、かつ `git ls-files -i -c --exclude-standard` が**終了コード 0 かつ空出力**。`-i` は `-c` か `-o` との併用が必須で、`-c` を欠くと `fatal: ls-files -i must be used with either -o or -c`(exit 128)になり、出力が空になるため常に見かけ上パスしてしまう | R-1, R-2 の適用手段 |
| PC-15 | record の計画特定 | ブランチ `pipeline/foo`、`.claude/plans/` に `20260805-foo.md` のみ存在(直接一致 `foo.md` は無し)。別ケースとして `20260805-foo.md` と `20260806-foo.md` の2件が存在 | いずれの場合も状態ファイルに計画パスを書かず「該当なし」と記録する(誤ったパス・あいまい候補を記録しない)。直接一致 `.claude/plans/foo.md` を置いた場合のみそのパスを記録する | R-1 |
| PC-16 | 適用後の `.claude/settings.json` | Step 7 適用直後・**コミット前** | `git diff --numstat .claude/settings.json` の出力が `<追加行数>	0	.claude/settings.json`(削除行が 0)。既存エントリの欠落・順序変更・`"async": true` の消失はいずれも削除行として現れるため、0 でなければ FAIL | R-4 |
| PC-17 | 適用後の `.claude/settings.json` | 同上(`git show HEAD:.claude/settings.json` を適用前の版として使う) | (a) Stop 配列から先頭1要素(`record_session_state.py`)を除いた残りが適用前と**順序込みで完全一致**、(b) SessionStart の `matcher == "compact"` エントリが適用前と一致、(c) PreCompact の `"async": true` が残存、(d) 適用前に存在した全 command 文字列が適用後にも全件存在する | R-4 |

## 実装手順

| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 1 | PC-1〜PC-13 の受け入れテストを実装前に書く(この時点では対象フックが存在せず全 FAIL = RED が正しい状態。`tests/test_plan_gate.py` の冒頭 docstring と subprocess CLI 起動形式に倣い、RED である旨を docstring に明記する) | `tests/test_session_resume.py` | なし | A |
| 2 | 記録フックの完成版全文を作成(R-1/R-3/R-5) | `_staging_record_session_state.py` | Step 1 | A |
| 3 | 注入フックの完成版全文を作成(R-2/R-4/R-5) | `_staging_resume_session_state.py` | Step 1 | A |
| 4 | `.gitignore` 17行目を `/_staging_*` に広げ、**現行 `settings.json` を読み込んで2要素をプログラム的に挿入する生成スクリプトを書き、実行して** `_staging_settings.json` を出力する(R-1/R-2/R-4)。全文の手書き写しは禁止 | `.gitignore`, `_staging_gen_settings.py`, `_staging_settings.json` | Step 2, 3 | A |
| 5 | フック表(908-922行)・ディレクトリツリー(1596行付近)・`## 0. 迷ったら` の表(50-62行)・env 表(254行付近)を更新し、env フラグをテンプレートに登録(R-2/R-5)。既存の `checkpoint_before_compact.py` / `CLAUDE_ACTION_LOG` の行の書式に倣う | `README.md`, `templates/settings.local.json.template` | Step 2, 3 | A |
| 6 | handoff と自動記録の責務境界を追記、変更点を1項目記録(R-6) | `.claude/skills/handoff/SKILL.md`, `CHANGELOG.md` | Step 5 | A |
| 7 | ユーザーが下記3コマンドで適用し、`_staging_*` を削除する(保護パスのため Claude は実行不可)。適用後に**新フック2本と `.claude/settings.json` の3ファイルを** `git add <パス>` してコミットする(settings.json は追跡ファイルなので、add し忘れると modified のまま残り `codex_gate.worktree_clean()` に恒常的に抵触する) | `.claude/hooks/record_session_state.py`, `.claude/hooks/resume_session_state.py`, `.claude/settings.json` | Step 4, 6 | A |

Step 7 で提示する適用コマンド(完了報告にそのまま載せる):

```bash
cp _staging_record_session_state.py .claude/hooks/record_session_state.py
cp _staging_resume_session_state.py .claude/hooks/resume_session_state.py
cp _staging_settings.json .claude/settings.json
rm _staging_record_session_state.py _staging_resume_session_state.py _staging_settings.json _staging_gen_settings.py
```
| 8 | 適用後に GREEN 確認・JSON 妥当性確認・実セッションでの実地確認を行う(R-1/R-2/R-4) | (検証のみ) | Step 7 | A |

### Step 2 の要点(記録フック)

- 先頭で `os.environ.get("CLAUDE_SESSION_RESUME", "1") == "0"` なら即 `sys.exit(0)`(action_log.py:28 の書式に倣う)。
- 出力先は `.claude/checkpoints/session_state.md` 固定(上書き。世代管理・prune は行わない)。
- 記録内容(この順・全体 200 行以内):記録時刻 / ブランチ / HEAD 短縮ハッシュ+件名 / 直近コミット3件 / `git status --short`(40行超は `... 他 N 件` に切る。`checkpoint_before_compact.py` 53-57行と同じ切り詰め方) / 対応する計画ファイルのパスと実装手順表(`^\| \d+ \|` に一致する行を先頭20行、各行120文字で切る) / 直近の会話(最後のユーザー発話・最後のアシスタント本文を各800文字まで) / 直近に言及された手順番号(`手順\s*\d+(\.\d+)?` の最後の一致。「推定・要確認」と明示) / 再開時の注意(定型文)。
- **注意(PC-7 の失敗要因)**: transcript は全読みしない。ファイル末尾から 256 KB だけ seek して読み、先頭の不完全行を捨ててから末尾側へ走査する。この設計を守らないと毎ターン数十 MB を読み、Stop が体感で重くなる。
- **注意(会話抽出の落とし穴)**: JSONL の `user` 行にはツール実行結果も入る。`content` が文字列ならそのまま、リストなら `type == "text"` の要素のみを連結し、連結結果が空のエントリ(tool_result のみ)は「ユーザー発話」として採用しない。これを怠ると「最後のユーザー指示」欄にツール出力が入り、再開時の判断を誤らせる。
- 会話由来のテキストは必ず `_mask.mask()` を通してから書く(`checkpoint_before_compact.py` 77-87行と同じ方針)。
- 計画ファイルの特定は **`.claude/plans/{slug}.md` の直接一致のみ**とする(`slug` は `plan_gate._slug_from_branch()` と同じ規則=ブランチ最終セグメントから `-group-<英数字>` を1回除去)。`plan_gate.py` の日付つき glob フォールバック(`*-{slug}.md`)は**意図的に実装しない**。あいまい候補の解決を複製すると誤った計画を指しうるため、確実な一致か「該当なし」の二択にする。この意図をコードコメントに書く。
- 直接一致が無い場合、状態ファイルの計画セクションには「該当なし(`.claude/plans/{slug}.md` が存在しない。`.claude/plans/` を確認すること)」と書き、**推測したパスを書かない**。PC-15 が誤特定しないことを固定する。
- slug 導出だけは `plan_gate` と一致している必要があるため、PC-13 が両実装の parity を照合する。
- 例外方針: `main()` 全体を防御し、どの経路でも `sys.exit(0)`。ファイル読み取りは `(OSError, UnicodeError)`、subprocess は `(OSError, subprocess.TimeoutExpired, UnicodeError)` を捕捉する(python-style.md)。git 呼び出しは `timeout=5`、`git diff` は使わない。

### Step 3 の要点(注入フック)

- キルスイッチ判定 → `source == "startup"` 以外は即 `sys.exit(0)`(`compact` は既存フックの担当、`clear` はユーザーが意図的に消しているので注入しない)。
- 状態ファイルの mtime が 72 時間より古ければ何も出力しない。状態ファイル内の `## Git ブランチ:` 行と `git branch --show-current` が不一致なら何も出力しない。
- 出力は「状態ファイル本文 + 再開指示」。再開指示には (a) 自動で作業を続行せず計画ファイルを読み直してユーザーに再開可否を確認する、(b) 未コミット変更を `git status` で確認する、(c) 記録は前回ターン終了時点のもので、その後の作業は含まれない可能性がある、を含める。
- **注意**: 出力は `print()` による stdout(既存 `reinject_after_compact.py` 36行と同じ注入経路)。stderr や exit 2 を使わない(起動を妨げないため)。

### Step 4 の要点(settings.json)

- `.claude/checkpoints/` は `guard_scope` の `ARTIFACT_DIR_PATTERNS` で Write 不可(現状分析参照)。提案ファイルと生成スクリプトはリポジトリ直下の `_staging_*` に置き、`.gitignore` 17行目を `/_staging_*.py` → `/_staging_*` に1箇所だけ広げる(コメント行は `.py` に依存しないため変更不要)。
- **全文の書き写しは行わない**。`_staging_gen_settings.py` を書いて `uv run python _staging_gen_settings.py` で生成する(実測: guard_bash は当該コマンドを許可・exit 0)。処理は次の4手のみ:
  1. `json.loads(Path(".claude/settings.json").read_text(encoding="utf-8"))`
  2. `cfg["hooks"]["Stop"][0]["hooks"].insert(0, {"type": "command", "command": ...record_session_state.py})`(Stop は要素1個の配列で、その `hooks` に6件が並ぶ現行構造を前提とする)
  3. `cfg["hooks"]["SessionStart"].append({"matcher": "startup", "hooks": [{"type": "command", "command": ...resume_session_state.py}]})`
  4. `json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"` を `_staging_settings.json` に書く
- **確認済み**: 現行 `.claude/settings.json` はこの dump 設定で round-trip がバイト単位で一致する(3423 バイト、非 ASCII なし)。したがって生成物と現行版の差分は**挿入行のみ**になり、既存エントリの欠落・順序変更・`"async": true` の消失は `git diff` に削除行として必ず現れる(PC-16 が機械照合)。
- **注意(二重挿入)**: スクリプトは冒頭で既存 command 文字列に `record_session_state.py` が含まれるかを確認し、含まれていれば何もせず終了する(適用後に再実行してもエントリが2重にならないようにする)。
- **注意**: `.gitignore` のパターンを広げすぎて既存の追跡ファイルを無視しないこと。PC-14 が機械的に確認する。
- settings.json 側の変更は2箇所のみ: Stop 配列の**先頭**に `record_session_state.py` の要素を挿入(`"async"` は付けない)、SessionStart 配列に `{"matcher": "startup", ...}` のエントリを1つ追加。
- 適用手順(3つの `cp` と `_staging_*` の削除)を完了報告に明記する。

## 並列化判定

逐次のみ(グループ A のみ)。理由: 受け入れテスト(Step 1)と2本のフック実装(Step 2, 3)は同一の PC 表に対する実装と検証で、別エージェントが並行に書くと解釈のずれがそのまま検出漏れになる。文書(Step 5, 6)は確定した挙動を記述するため実装後にしか書けない。

## 検証方法

### 適用前(RED 確認)

```bash
uv run --with pytest python -m pytest tests/test_session_resume.py -q
```
PASS 条件: フック未適用のため失敗すること(Step 1 完了時点)。エラーが「対象ファイルが無い」以外の理由(テスト自体の構文エラー等)でないことを出力で確認する。

### 適用後(GREEN 確認)

```bash
uv run --with pytest python -m pytest tests/test_session_resume.py -q
```
PASS 条件: PC-1〜PC-13 が全て PASS(13件、failed 0)。

```bash
uv run --with pytest python -m pytest tests/ -q
```
PASS 条件: 既存テストに失敗が増えていないこと(適用前の結果と件数比較)。

```bash
bash verify-hooks.sh
```
PASS 条件: `NG:` 行が0件(guard 系の既存挙動が壊れていないこと)。

```bash
uv run python -c "import json,sys; json.load(open('.claude/settings.json')); print('ok')"
```
PASS 条件: `ok` が出力される(適用した JSON が壊れていない)。

```bash
git check-ignore -v _staging_settings.json
```
PASS 条件: `.gitignore:17:/_staging_*` を出力。`git check-ignore` はパス文字列に対するパターン判定なので、Step 7 で `_staging_settings.json` を削除した後に実行しても同じ結果を返す(実測確認済み)。

```bash
git ls-files -i -c --exclude-standard; echo "exit=$?"
```
PASS 条件: 出力が空**かつ** `exit=0`(`-c` 無しでは exit 128 で空出力になり検出力を失う)。PC-14。

```bash
git diff --numstat .claude/settings.json
```
PASS 条件: 削除行が `0`(2列目が 0)。1以上なら既存エントリを壊しているので適用をやり直す。PC-16。

```bash
uv run python -c "
import json,subprocess
old=json.loads(subprocess.run(['git','show','HEAD:.claude/settings.json'],capture_output=True,text=True,check=True).stdout)
new=json.loads(open('.claude/settings.json',encoding='utf-8').read())
o,n=old['hooks'],new['hooks']
assert n['Stop'][0]['hooks'][0]['command'].endswith('record_session_state.py'), 'Stop 先頭が新規フックでない'
assert n['Stop'][0]['hooks'][1:]==o['Stop'][0]['hooks'], 'Stop の既存エントリが順序込みで一致しない'
assert [e for e in n['SessionStart'] if e.get('matcher')=='compact']==[e for e in o['SessionStart'] if e.get('matcher')=='compact'], 'compact エントリが変化した'
assert n['PreCompact']==o['PreCompact'], 'PreCompact(async 含む)が変化した'
def cmds(h): return {c['command'] for v in h.values() for e in v for c in e['hooks']}
assert cmds(o) <= cmds(n), '適用前に存在した command が欠落している'
print('ok')
"
```
PASS 条件: `ok` が出力される(assert が1つでも落ちれば FAIL)。PC-17。

### フック単体の CLI 起動(手動確認)

```bash
echo '{"hook_event_name":"Stop","transcript_path":""}' | uv run python .claude/hooks/record_session_state.py; echo "exit=$?"
```
PASS 条件: `exit=0`、標準出力なし、`.claude/checkpoints/session_state.md` の更新時刻が現在時刻。

```bash
echo '{"source":"startup"}' | uv run python .claude/hooks/resume_session_state.py
```
PASS 条件: 状態ファイル本文と再開指示が出力される。

```bash
echo '{"source":"compact"}' | uv run python .claude/hooks/resume_session_state.py; echo "exit=$?"
```
PASS 条件: 出力なし・`exit=0`(既存 compact 用フックとの二重注入なし)。

### 状態が無い/壊れている場合

```bash
mv .claude/checkpoints/session_state.md .claude/checkpoints/session_state.md.bak && echo '{"source":"startup"}' | uv run python .claude/hooks/resume_session_state.py; echo "exit=$?"; mv .claude/checkpoints/session_state.md.bak .claude/checkpoints/session_state.md
```
PASS 条件: 出力なし・`exit=0`(起動を妨げない)。退避先をリポジトリ外(`/tmp`)にすると guard の作業スコープ判定に触れるため、同一ディレクトリ内でリネームする。万一 `guard_bash` にブロックされた場合はユーザーに実行を依頼する(この経路は PC-10 が自動でも検査済み)。壊れた UTF-8・空ファイル・別ブランチ名・73時間前の mtime も PC-10/PC-11 が自動で検査する。

### 入力の形が複数ある箇所(transcript の会話ブロック)

PC-1/PC-3/PC-5 のテストは、以下5パターンの transcript フィクスチャを個別ケースとして持つこと。1パターンだけの検証では取りこぼしを検出できない。

| ケース | 内容 | 期待 |
|---|---|---|
| 文字列 content | `"content": "テキスト"` | ユーザー発話として採用される |
| text ブロック1件 | `"content": [{"type":"text","text":"..."}]` | 採用される |
| text + tool_use の複数ブロック(入れ子) | text と tool_use が混在 | text 部分のみ連結して採用 |
| tool_result のみ | `"content": [{"type":"tool_result",...}]` | ユーザー発話として採用しない(その手前の実発話を採る) |
| 壊れた行の混在 | JSON として不正な行・空行を含む | 例外を出さず、解釈できた行だけで記録が完成する |

### 実地確認(Step 8、ユーザー適用後)

1. 本ブランチで1ターン会話を終える → `.claude/checkpoints/session_state.md` に今回の会話末尾とブランチ名が入っていること、`git status --porcelain` に当該ファイルが現れないこと(gitignore の確認)を目視する。
2. 新しいセッションを起動する → 起動直後の文脈に状態と再開指示が現れること、かつ Claude が自動で作業を続行せず確認を求めることを目視する。
3. 手動 `/compact` を実行する → 従来どおり compact 用の再注入だけが起き、起動時注入と重複しないことを目視する。

## リスク

- **Stop フックの追加でターン終了が遅くなる**: 既に6本ある Stop 配列に7本目を足す。git 呼び出し3〜4回(各 timeout 5秒)と transcript 末尾 256 KB 読みに抑え、PC-7 で 5 秒未満を機械的に固定する。
- **ターンの途中で上限に当たると、記録は直前のターン終了時点になる**: 本方式の原理的な限界。注入文に「記録以降の作業は含まれない可能性がある」と明記して誤認を防ぐ。
- **状態ファイルはリポジトリに残らない(別マシン・別クローンで復元不可)**: 仕様として割り切る(設計判断2)。別マシンへの引き継ぎは handoff スキルの担当であることを README と SKILL.md に書く(R-6)。
- **起動時注入のトークン消費**: 毎回の起動で最大200行程度が文脈に入る。ブランチ一致 + 72 時間の2条件で無関係な注入を抑え、`CLAUDE_SESSION_RESUME=0` で完全に止められるようにする。
- **既定 ON はテンプレートの opt-in 方針と一部食い違う**: ブロックしない情報系フック(PreCompact 系・action_log)と同じ扱いにするという判断。opt-in にすると `claude-init.sh` / `.ps1` / `verify-installers.sh` の任意機能リスト3箇所に手を入れることになり、最小 diff にも反する。
- **代替案1: 既存の2本を拡張して Stop / startup も処理させる** — 不採用。1ファイルが3イベントを分岐処理する形になり、PreCompact は async・Stop は同期という要件差も混ざる。既存の compact 動作を壊さない保証(R-4)を構造で担保できない。
- **代替案2: ml-pipeline.md の各手順末尾に「状態を書く」指示を足す** — 不採用。自己申告であり、文脈圧縮後・上限直前という最も必要な場面で最も守られない。手順書の diff も大きい。
- **代替案3: 状態を追跡ファイル(`docs/` や `.claude/handoffs/`)にコミットして別マシンでも復元可能にする** — 不採用。毎ターン更新される生成物を追跡すると作業ツリーが常時 dirty になり codex_gate の再レビュー要求と衝突する。会話末尾を git 履歴に残す点も望ましくない。
- **代替案4: 提案ファイルを `.claude/checkpoints/` に置く** — 不採用というより**実行不能**。`guard_scope` の `ARTIFACT_DIR_PATTERNS`(`/checkpoints/`)で Write が exit 2 になることを実測で確認した。
- **代替案5: 提案ファイルを `logs/` に置く(`.gitignore` 変更不要)** — 不採用。Write は通る(実測 exit 0)が、`.claude/rules/search-hygiene.md` が `logs/` を全検索から除外させる場所であり、ユーザーが適用すべき一時ファイルの置き場として発見性が低い。`_staging_` は既存の同目的の慣例であり、そちらに寄せる方が一貫する。
- **`settings.json` の既存配線を静かに壊す**: 全文を手で書き写す方式では、Stop の6エントリや `"async": true` を1つ落としても JSON としては妥当なままで、既存テスト(`verify-hooks.sh` / `tests/`)も settings.json の**内容**を一切検証していない(実測: `grep -rln "settings\.json" tests/ --include="*.py"` は0件)。このため Step 4 をプログラム的生成に変え、PC-16(削除行0)と PC-17(HEAD 版との構造比較)で適用結果を機械照合する。
- **計画パスが状態ファイルに載らないことがある**: 記録フックは直接一致(`.claude/plans/{slug}.md`)のみを採用するため、日付つき別名しか無いブランチでは「該当なし」と記録される。誤ったパスを記録するより安全側であり、注入文の「計画ファイルを読み直す」指示と `.claude/plans/` の確認で補える。plan_gate 側は従来どおり glob フォールバックを持つため、ゲートの挙動には影響しない。
- **`.gitignore` のパターン拡張による取りこぼし**: `/_staging_*` は `.py` 以外の `_staging_` 接頭辞ファイルも無視する。将来 `_staging_` で始まる追跡したいファイルを作ると silently 無視される。現時点で該当ファイル・参照コードは0件(実測)であり、既存コメントの意図(コミット対象にしない一時ファイル)とも一致するため許容する。PC-14 が巻き込みゼロを機械的に固定する。
- 未確認の仮定: Stop フックの JSON payload に `transcript_path` が含まれる(PreCompact では使用実績あり)。欠けても PC-3 のフォールバックで会話セクションが「(取得不可)」になるだけで機能は成立する / 検証: `rg -n "transcript_path" /home/toyod/claude-ml-template/.claude/hooks/checkpoint_before_compact.py` / 期待: 3行ヒット(36・77・82行)し、同名フィールドがフック payload の標準キーとして使われていることが確認できる
- 未確認の仮定: SessionStart の `matcher` に `startup` を指定でき、既存の `compact` エントリと独立に発火する。フック側で `source` を再判定するため、matcher が期待どおりに効かなくても二重注入は起きない / 検証: `grep -n "matcher" /home/toyod/claude-ml-template/.claude/settings.json` / 期待: `"matcher": "compact"` を含む行が1件だけ表示される(matcher に source 名を書く形式であること)
- 未確認の仮定: SessionStart フックの stdout がそのまま文脈へ注入される / 検証: `rg -n "^    print" /home/toyod/claude-ml-template/.claude/hooks/reinject_after_compact.py` / 期待: 1行ヒット(36行の `print("\n\n".join(parts))`。既存機能が stdout 経由で注入している証跡)

## トレーサビリティ

| ID | 対応ステップ | 検証方法 |
|---|---|---|
| R-1 | Step 1, 2, 4, 7, 8 | `uv run --with pytest python -m pytest tests/test_session_resume.py -q`(PC-1, PC-4, PC-6, PC-7, PC-13, PC-15)+ `git check-ignore -v _staging_settings.json` / `git ls-files -i -c --exclude-standard`(PC-14、適用手段)+ 実地確認1 |
| R-2 | Step 1, 3, 4, 5, 7, 8 | 同上(PC-8, PC-11, PC-14)+ 実地確認2 |
| R-3 | Step 1, 2 | 同上(PC-5) |
| R-4 | Step 1, 3, 4, 7, 8 | 同上(PC-9, PC-12)+ `git diff --numstat .claude/settings.json`(PC-16)+ HEAD 版との構造比較ワンライナー(PC-17)+ `bash verify-hooks.sh` + 実地確認3 |
| R-5 | Step 1, 2, 3, 5 | 同上(PC-2, PC-3, PC-10)+ 「状態が無い/壊れている場合」の手動確認 |
| R-6 | Step 5, 6 | (目視)`.claude/skills/handoff/SKILL.md` と README のフック表に責務境界の記述があること |

対応ステップの無い R-ID は無い。どの R-ID にも直接対応しないステップは無い。

## コスト見積もり

```yaml
experiment: false
```

```yaml
cost_estimate:
  train_minutes: 0
  epochs: 0
  dataset_gb: 0
  parallel_jobs: 0
```
