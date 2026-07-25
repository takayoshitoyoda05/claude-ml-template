# verdict: control-patterns-spec.md (セクション12 / plan_gate 検査精度)

対象計画: `.claude/plans/20260726-plan-gate-precision.md`
検証環境: NEW_SOURCE を `/tmp/.../scratchpad/new_plan_gate.py` に書き出し、
`tests/test_plan_gate.py` のコピーの `PLAN_GATE_PATH` のみをそこへ向けて実行
(`.claude/hooks/plan_gate.py` 本体には一切書き込んでいない)。

| ID | 判定 | 実行コマンド | 実測値 | 証拠(file:line) |
|---|---|---|---|---|
| R-001 | PASS | `uv run --with pytest python -m pytest <scratch>/test_plan_gate_new.py -v`(NEW_SOURCE 経由) | T-09, T-10 含め32件全PASS(`32 passed in 1.02s`) | tests/test_plan_gate.py:249-273(T-09/T-10)、_staging_plan_gate_precision.py:320-333(C1/C2実装) |
| R-002 | PASS | 同上 | T-11(`1e3`)/T-12(`-5`,`"45"`,`1.2.3`)exit 2、T-13(`100.`/`.5`)exit 0。全PASS | tests/test_plan_gate.py:276-324、_staging_plan_gate_precision.py:39(`_NUMBER`正規表現)、261-286(`_read_number`) |
| R-003 | PASS | 同上 | T-14(invariants `1e3`)exit 2、T-15(resourcesブロック無し)exit 0、T-16(999>120)exit 2、T-25(invariants読めない+計画完備)exit 0、T-26(同+goal欠落)exit 2。全PASS | tests/test_plan_gate.py:327-363,494-516、_staging_plan_gate_precision.py:380-403(invariants別tryでOSError捕捉、C9/C10) |
| R-004 | PASS | 同上 | T-17(ブロック外に5キー、配下空)exit 2、T-18(ブロック外の`target: 999`等は無視)exit 0。全PASS | tests/test_plan_gate.py:366-404、_staging_plan_gate_precision.py:335-345(goal_blockに限定した検索) |
| R-005 | PASS | 同上 | T-19(guard_metrics無し)exit 2、T-20(`[]`)exit 0、T-21(`- name:`1件)exit 0、T-22(`direction: down`)exit 2。全PASS | tests/test_plan_gate.py:407-467、_staging_plan_gate_precision.py:350-378(guard_metrics/direction検査) |
| R-006 | PASS | 同上 | T-01〜T-03,T-07 exit 0、T-04〜T-06 exit 2、T-08 exit 0、T-27(`20260726-extra-foo.md`誤マッチ回避)exit 0、T-28(直接一致優先)exit 2。全PASS | tests/test_plan_gate.py:158-247,519-544、_staging_plan_gate_precision.py:197-227(`_slug_from_branch`/`_select_plan_path`、`stem[9:] == slug`完全一致) |
| R-007 | PASS | 統合ブランチ+group-C/D/Eをマージした一時clone上でNEW_SOURCEを適用し `bash verify-hooks.sh` を実行。加えて `grep -cE '"plan_gate: [^"]+"'` をsh/ps1双方に実行 | plan_gate 区間6ケース全OK(`passes when .claude/plans directory is absent`〜`blocks when train_minutes exceeds the resource limit`)。sh/ps1とも生件数6・一意件数6。全体は無関係な1件(`rm -rf relative out-of-scope`)のみNGだったが、本リポジトリ単体(未マージ)で再実行すると同ケースはPASSし、対象4ブランチいずれも guard_bash.py を変更していないため、この1件はクローン環境依存のノイズであり本要件の判定には影響しない | logs(本レポート内引用): verify-hooks.sh実行ログ(plan_gateの6行はすべてOK)、verify-hooks.sh:118(該当NG行の定義。今回のdiff対象外) |
| R-008 | PASS | `diff <(grep -oE '"plan_gate: [^"]+"' verify-hooks.sh \| sort -u) <(同 verify-hooks.ps1 \| sort -u)`(group-Cブランチの内容に対して実行) | diff結果は空(1対1対応)。sh/ps1とも一意件数6 | verify-hooks.sh(group-C):新設 `test_plan_gate` 関数呼び出し6件、verify-hooks.ps1(group-C):新設 `Test-PlanGate` 関数呼び出し6件(説明文字列がsh/ps1で一致) |
| R-009 | UNVERIFIABLE | Windows機での `.\verify-hooks.ps1` 実行(WSLにpwsh無し) | 未実施(計画自身がR-009をmanual・本機実施不可と明記) | .claude/plans/20260726-plan-gate-precision.md:298-303(申し送り事項として明記) |
| R-010 | PASS | `grep` 6件を group-D branch の planner.md に対して実行 | 6個すべて一致し "OK: planner.md 規約6件" 相当を確認 | .claude/agents/planner.md(group-D差分):29-33(ブランチ名の最終セグメント), 63-67(4キーをすべて数値で書く/guard_metrics: []/指数表記/ブロックは計画中に1つだけ), 135-138(行末に説明を続けない) |
| R-011 | PASS | `grep` 2件を group-E branch の README.md に対して実行 | 2個すべて一致し "OK: README 2件" 相当を確認 | README.md(group-E差分):731行(ブランチ名に対応する), 1146行(fail-closed) |
| R-012 | PASS | `uv run --with pytest python -m pytest <scratch>/test_plan_gate_new.py -v`(NEW_SOURCE 経由) | T-23(`experiment: falsehood`)exit 2、T-24(`experiment: false   # コード変更のみ`)exit 0。全PASS | tests/test_plan_gate.py:470-491、_staging_plan_gate_precision.py:164(行末固定の正規表現 `^\s*experiment\s*:\s*false\s*(?:#.*)?$`) |

## 補足

- 現行 `.claude/hooks/plan_gate.py`(未適用・旧実装)に対して `tests/test_plan_gate.py` を実行すると
  `17 failed, 15 passed`(実測)。適用前は FAIL するのが正しい状態であり、この結果は計画の想定と一致する。
- `_staging_plan_gate_precision.py` の `OLD_SOURCE` は現行 `.claude/hooks/plan_gate.py` と
  バイト完全一致(sha256 `e04152f8...b7470` で一致確認済み)。適用スクリプトの sha256 一致検査は
  期待どおり機能する状態にある。
