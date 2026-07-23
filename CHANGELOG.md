# Changelog

このプロジェクトの主な変更点を記録する。形式は [Keep a Changelog](https://keepachangelog.com/) に緩く準拠。

## [Unreleased]

### Added(2026-07-22)
- **Codex CLI 連携**: agents/shared/(共有規約)から AGENTS.md を自動生成、
  .codex/(config.toml・skills コピー)を claude-init/update が配置。
  cross-review スキル+ codex_gate フックで、別モデル(OpenAI)視点のレビューを
  `CLAUDE_CROSS_REVIEW=1` で必須ゲート化(センチネルは HEAD ハッシュ束縛+
  作業ツリークリーン必須。同一コミット上では再レビューを要求しない)
- **機械的品質強制(quality-gate)**: quality_gate フックが `CLAUDE_QUALITY_GATE=1` で
  ruff / radon(複雑度 C+)/ mypy を Stop 時に強制。状態キャッシュ付き。
  evaluator に mypy 検証と複雑度の経時トラッキング(docs/baselines/)を追加
- **パイプライン高度化**: 作業ブランチ自動作成+マージ確認(main は無傷)、
  plan-reviewer による計画の自動承認(`CLAUDE_AUTO_APPROVE=1`、7条件)、
  並列化判定とサブブランチ並列実装(原子性保証、tmux 環境で有効)、
  リファクタリング・パス(両軸 PASS 後の磨き工程、失敗時は磨き分のみ破棄)
- **常時有効ルール(.claude/rules/)**: python-style / minimal-diff / secret-safety /
  taste(美しさの個人辞書。純スタイルに限り一般原則より優先)
- **自己改善ループ**: evaluator 系の差し戻し・計画却下を feedback.md に記録し、
  retrospective スキルで分析 → improvement-reviewer が invariants.md に照らして
  審査・適用(テスト失敗時は自動 revert)
- 新スキル: cross-review / fix-ci / retrospective / mutation-test(mutmut による
  テストの質検証)

### Added(2026-07-23)
- **Codex高度運用**(前回マージ分の記録漏れ): MCP経由でのCodex登録用テンプレート
  (`templates/mcp.json.template`)、独立タスクの委譲用スキル codex-delegate、
  レート制限時の退避先としての委譲運用、Codexとevaluator系の指摘一致で
  重大度を1段引き上げる優先度ルール
- **プラグインマニフェストと完了通知フック**: `.claude-plugin/plugin.json` を追加
  (現行のプラグイン仕様確認結果に基づく暫定対応。コンポーネントの読み込みは
  プラグインルート直下が前提のため未対応。フル機能は引き続き claude-init を使用)。
  `notify.py`(Stop)が `CLAUDE_NOTIFY=1` のとき、全ゲート通過後の実際の停止時に
  デスクトップ通知(Windows/macOS/Linux対応)
- **研究ワークフロー**: mlflow-log / literature-review / paper-writing スキルを追加し、
  arXiv MCP の推奨設定雛形を用意。evaluator が PASS 時に指標を MLflow へ自動記録
- **3層レビュー**: adversarial-reviewer(攻撃的レビュー+リーダーによる検証パスで
  偽陽性除外)と final-gate(Fable 5によるマージ承認の三択判断)を追加。
  `CLAUDE_ADVERSARIAL` / `CLAUDE_FINAL_GATE` で有効化

### Changed(2026-07-22)
- ml-pipeline を14手順に再構成(ブランチ作成〜マージ確認)。差し戻しは新規
  generator に指摘全文を渡す・再レビューは失敗軸のみ、のトークン節約規律を明文化
- CLAUDE.md.template の共有指示インポートを commit-style のみに削減
  (.claude/rules/ との毎セッション二重ロードを解消)
- claude-init/update の agents/shared・.codex/skills 配布を「配布ファイルの個別
  上書き」方式に変更(ユーザー独自ファイルを消さない)。doctor の比較対象に
  rules / agents/shared を追加
- plan-reviewer のモデルを opus から sonnet に(機械的な7条件チェックに opus は過剰)

### Fixed(2026-07-22)
- guard_bash の誤検知を解消: `sed -n` 等の読み取りは通し `-i` 付きのみブロック、
  spec_approve は grep/cat 等の読み取り専用コマンドなら許可
- guard_bash に相対パスによる作業スコープ外への再帰削除ブロックと
  touch / New-Item の保護パス検査を追加
- repo_state_signature を内容ベースに強化(dirty 状態での再編集・日本語等の
  クォート対象パスの変更を確実に検知。enforce_eval / spec_gate / quality_gate 共通)
- quality_gate のツール欠落判定を uv の実エラー文言に対応(設計時のままだと
  mypy 未導入プロジェクトで常時ブロックされるバグ)。radon 判定を stdout に
  限定し uv の stderr ノイズによる誤ブロックを防止

### Security(2026-07-22)
- permissions.allow の `Bash(uv run *)` を pytest / uv lock / uv sync の具体形に
  絞り込み(無確認の任意コード実行が保護パスの迂回路になるのを防ぐ)
- キャッシュマーカー(last_quality_pass.txt)を保護パスに追加(偽装防止)
- README の「物理的にブロック」表現を実態(補助線・既知の迂回あり)に是正

### Fixed(整合性監査 2026-07-07)
- claude-init.sh の UTF-8 BOM を除去(Linux で `./claude-init.sh` の exec が失敗する問題。
  README 自身が警告していた規約への違反だった)
- claude-init / doctor が `output-styles` を配布・比較していなかったのを修正
  (claude-update とは対象が揃い、新規プロジェクトにも fable-like.md が配布される)。
  claude-update 内コメントと README の対象列挙も実態(+ skills / output-styles)に合わせた
- スキル(adr / design-interview / config-set)が配布先プロジェクトに存在しない
  `templates/` を参照していたのを、雛形のインライン化で解消
- 環境変数リストの4箇所同期: config-explain に CLAUDE_SPEC_CHECK / CLAUDE_SPEC_RECHECK_N を
  追加し settings.local.json の場所の記述を修正、settings.local.json.template に
  CLAUDE_COMMIT_STEP_RULE を追加
- spec-gate.yml.template / README に CLAUDE_WORK_SCOPE 運用時の CLAUDE_SPEC_DOCS 設定を明記
  (未設定だと CI はリポジトリ直下の docs/active しか見ず、何も検査せずに通る)
- README 6節のファイル一覧に欠けていた5スキル(security-review / pre-mortem /
  leakage-check / python-standards / property-test)と output-styles/ を追記
- トークン節約: CLAUDE.md.template の「生成日」セクションを削除(全セッション常駐で
  行動に影響しない情報のため。init の {{INIT_DATE}} 置換も撤去)、README 4節の
  重複していた更新手順を1節への参照に統合

### Security(整合性監査 2026-07-07)
- enforce_eval のキャッシュマーカー `.claude/checkpoints/last_eval_pass.txt` を
  PROTECTED_PATH_PATTERNS に追加(spec 側 last_spec_pass.txt と同じ理由:
  決定的な署名計算で書ければ評価強制をスキップ偽装できるため)。
  verify-hooks(.sh / .ps1)に guard_bash / guard_scope のテストを追加

### Security
- spec-compliance の3つの迂回経路を修正(セルフ監査での指摘対応)
  - guard_bash: エージェントの Bash/PowerShell 経由での `spec_approve.py` 実行をブロック
    (承認はユーザーの `!` 手動実行のみ。`!` は PreToolUse を通らないため影響しない)
  - `_common.py`: `.claude/spec/last_spec_pass.txt`(spec_gate のキャッシュマーカー)と
    `.claude/spec/design_hashes.txt` を PROTECTED_PATH_PATTERNS に追加
    (決定的な署名計算によるキャッシュ偽装・承認記録偽装を防止)
  - spec_gate/spec_approve: 計画承認時に設計書のハッシュを `design_hashes.txt` に記録し、
    Stop 時に照合。「唯一の要件ソース」である設計書(docs/active/)自体の改変・
    検証コマンドの無害化を検知してブロック(`--design <設計書名>` で再承認)

### Added
- spec-compliance(設計書適合チェック): 設計書(docs/active/)の「## 受け入れ条件」テーブルを
  唯一の要件ソースとして、Stop フックと CI で全要件PASS・承認・独立監査を機械検査する仕組みを追加
  - `.claude/hooks/spec_gate.py`: `CLAUDE_SPEC_CHECK=1` のとき、verdict/audit/approvals
    を検査し欠けがあれば完了をブロック。`--ci` でCIモード、`--docs`/`--spec-dir` でテスト用の
    ディレクトリ上書きに対応
  - `.claude/hooks/spec_approve.py`: ユーザーの `!` 実行でmanual要件を
    `.claude/spec/approvals.txt` に承認記録(Claude 経由の書き込みは保護パスでブロック)
  - `.claude/agents/spec-auditor.md` 新規: evaluator の判定を独立コンテキストで再検証し、
    スコープ外変更を列挙する監査エージェント
  - evaluator.md: 完了時に `.claude/spec/verdict-*.md`(要件IDごとの機械可読判定)を出力
  - planner.md: 受け入れ条件テーブルの無い設計書を差し戻し、テストファーストのステップと
    要件ID⇔実装ステップ対応を必須化
  - design-interview/SKILL.md: 完了時に受け入れ条件テーブル生成を必須化
  - ml-pipeline.md: spec-auditor を evaluator×2 の後に追加、CLAUDE_SPEC_CHECK を案内
  - `templates/spec-gate.yml.template`: PR/push時に `spec_gate.py --ci` を実行するCIワークフロー雛形
  - claude-init/update: `.github/workflows/spec-gate.yml` の自動配置、`.claude/spec/` の
    .gitignore追加
  - verify-hooks: spec-compliance のテストケース(R-101〜R-109, R-112)を追加
- regression-suite スキル: 実装後に影響範囲を広くカバーするテストを任意生成
- config-explain スキル: スコープ・評価強制設定の可視化
- GitHub Actions CI: push/PR時に verify-hooks を自動実行
- LICENSE(MIT)
- doctor.ps1 / doctor.sh: テンプレートとの差分検知(sync-check)
- examples/toy-project: パイプラインお試し用のサンプルプロジェクト
- スキル設計のリファクタ: 全スキルの description をトリガー条件のみに絞り、Claudeがdescriptionだけで行動する誤動作を減らした
- スキル間の連鎖強制: design-interview / planner がトレードオフを伴う決定を解消したら、adr スキルの使用を必須化
- 設計書からの知識自動スタック: design-interview と planner が、設計書・計画に含まれる用語をCONTEXT.md、設計判断をdocs/adr/、実験再現条件をEXPERIMENT_LOG.mdに自動追記

### Fixed
- spec_gate `--ci` が verdict/audit/approvals(gitignore対象でCIに存在しない)まで要求し、
  設計書があるとCIが必ず失敗する問題を修正。CIモードは auto要件の全件再実行+coverage検査のみで判定
- spec_gate のキャッシュがマーカーファイル自身を署名に含めていて毎回失効していた問題を修正
- `.claude/spec/` の .gitignore パターンを `**/.claude/spec/` に変更
  (CLAUDE_WORK_SCOPE 設定時に使われる作業スコープ配下の `.claude/spec/` も除外されるように)
- evaluator / spec-auditor に Write/Edit ツールを追加(verdict/audit ファイルの出力を
  Bash リダイレクト頼みにしない)。verdict/audit の出力先が作業スコープ配下であることを明記
- ml-pipeline.md が README の存在しない節(7.5)を参照し、環境変数の設定方法として
  古いシェル方式を案内していたのを settings.local.json 方式に修正
- repo_state_signature の重複実装(enforce_eval.py / spec_gate.py)を _common.py に一元化

### Security
- ガードの自己書き換え防止を強化: これまで Edit/Write とリダイレクト/tee しか塞げず、
  `cp`/`mv`/`sed -i`/`install`/`truncate`/単純 `rm`/`git rm` 等で保護パス(フック・設定・
  承認記録)を書き換え/削除できる穴があったのを塞いだ。リダイレクト検出を `>\|`(noclobber強制)や
  `1>`/`2>>`(fd指定)にも対応、危険 rm の対象判定を `${HOME}` 等の展開形にも拡張。
  併せて、これらが任意コード実行(`python -c`)を封じる完全な境界ではなく多層防御である旨を
  README に明記
- ガードの自己書き換え防止: .claude/hooks/ と settings.json / settings.local.json への Edit/Write・リダイレクト・tee をブロック(PROTECTED_PATH_PATTERNS)
- guard_scope のスコープ判定を修正: 前方一致による兄弟ディレクトリ(例: proj と proj-evil)の誤許可を解消、Windows の大文字小文字差異にも対応
- guard_bash の rm 検知をフラグ解析に変更: -fr / -r -f 等の表記ゆれも検知
- git push の強制push別記法(+refspec)をブロック
- git add の一括ステージ(. / -A / --all / *)をブロックし、パス限定を促す。拡張子・ファイル名の検知を境界一致にして誤検知(例: foo.key.md)を解消
- フックの matcher を拡張: PowerShell / NotebookEdit も guard 対象に
- checkpoint のバックアップ(会話ログ含む)を直近10世代のみ保持するよう掃除を追加

### Changed
- トークン節約: 全スキルの description を圧縮(全セッション常駐分)、planner.md をルール維持のまま文言圧縮

## 過去の主な変更(遡及記録)
- Planner / Generator / Evaluator の3分離パターンを構築
- evaluator を Spec軸(evaluator) / Standards軸(evaluator-standards) に分割
- スコープ制約とフック(guard_scope, guard_bash)による物理ガードを導入
- design-interview, brainstorm, diagnosing-bugs, tdd, adr, handoff,
  architecture-check の各スキルを追加
- 秘密情報ガード、実験ログ自動記録、Golden Baseline、Explore事前調査を追加
- CONTEXT.md によるドメイン用語共有を導入
- コンテキスト圧縮対策(checkpoint_before_compact, reinject_after_compact)を追加
- claude-update による差分反映、.gitignore自動設定を追加
