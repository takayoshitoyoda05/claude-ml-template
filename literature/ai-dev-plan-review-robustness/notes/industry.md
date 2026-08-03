# 領域4: 業界プラクティス(採用11件。計画遵守は領域1の P10 に統合)

各項目の形式: 書誌情報 / 1行要約 / 要点 / 本パイプラインとの関係 / 確認レベル

## I1. spec-kit の成果物間整合分析(/speckit.analyze)+ constitution
- 書誌: https://github.com/github/spec-kit
- 要約: spec / plan / tasks の3成果物間の整合性・カバレッジを実装前に機械横断チェックする専用コマンドを持つ。
- 要点: /speckit.constitution でプロジェクト不変原則を定義し全計画が従う。/speckit.converge は実装後にコードを spec に照らして残作業をタスク化。
- 関係: spec-checklist(単一文書の品質)の後段に「設計書↔計画↔受け入れ条件テーブル間の相互整合検査」を追加できる。軸が異なる(良く書けているか vs 食い違っていないか)。
- 確認レベル: page_read

## I2. Kiro の EARS 記法(受け入れ条件の強制フォーマット)
- 書誌: https://kiro.dev/docs/specs/
- 要約: 受け入れ条件を「WHEN [条件] THE SYSTEM SHALL [挙動]」で構造化し、task→requirement の逆リンクを維持。
- 要点: 記法の強制により検証可能性・曖昧さ検出が容易になる。
- 関係: 受け入れ条件テーブルの各行に EARS 形式を必須化し、spec-checklist に準拠 lint を追加。トレーサビリティ自体は既存で、記法標準化+lint が追加要素。
- 確認レベル: abstract_only

## I3. OpenHands 軌跡クリティック(本番シグナルで学習したスコアラ)
- 書誌: https://openhands.dev/blog/20260305-learning-to-verify-ai-generated-code
- 要約: エージェントの全軌跡を小型モデルでスコアリング。ベンチ学習は本番で AUC 0.45–0.48(ランダム以下)、PR マージ/コード生存シグナル学習で 0.69。
- 要点: Best@8 選択 73.8% vs ランダム 57.9%。閾値超えで早期終了(平均1.35試行)。
- 関係: evaluator 前に「軌跡スコアで再試行か通過かを決める早期終了」層。学習不要版として retrospective の差し戻し率ログを閾値校正に使える。「作業過程を採点する」点が成果物レビューと異なる。
- 確認レベル: page_read

## I4. Agentic Rubrics(リポジトリ探索によるタスク固有ルーブリック生成)
- 書誌: https://arxiv.org/abs/2601.04171
- 要約: 専門エージェントがリポジトリを探索してタスク固有のルーブリックを生成し、候補パッチをテスト実行なしで採点。
- 要点: SWE-Bench Verified で効果確認。ルーブリックスコアは真のテスト結果と整合しつつ追加の問題も検出。
- 関係: planner 直後に「このタスク専用のレビュールーブリック」を生成させ、evaluator / spec-auditor の採点基準に注入(固定観点→タスク固有観点)。
- 確認レベル: page_read

## I5. リスクスコアによる段階的レビューゲート
- 書誌: https://blog.codacy.com/ai-code-review-is-not-enough-how-engineering-leaders-should-gate-ai-generated-code
- 要約: 全 PR のベースラインゲートと、高リスク分類(認証/決済/データ境界/依存変更/大規模構造変更)での人間必須+閾値強化を組み合わせる。
- 要点: レビュー資源をリスクに応じて傾斜配分する。
- 関係: router の S/M/L(規模)に「触れたファイル種別によるリスク軸」を直交追加し、高リスクのみクロスレビュー・独立監査・final-gate をフル起動、低リスクは軽量経路。
- 確認レベル: abstract_only

## I6. シャドーモード運用(新ゲートの効力なし試走→昇格)
- 書誌: https://brightlume.ai/blog/shadow-mode-rollouts-ai-agents-pilot-production(関連: Microsoft Dynamics 365 blog 2026-07)
- 要約: 新しい自動ゲートはまず判定をログするだけで効力を持たせず、人間判断との合意率(80–85%目安)を経てから enforcement に昇格。
- 要点: 不一致ログのレビューを昇格条件にする。
- 関係: plan-reviewer 自動承認や final-gate のルール変更時に shadow で数サイクル走らせてから enforce に切替(retrospective の改善案適用の安全弁)。既存 fail-closed は常時効力で、導入プロトコルが新規。
- 確認レベル: abstract_only

## I7. OPA/Rego による policy-as-code(ゲート条件の宣言化)
- 書誌: https://www.openpolicyagent.org/docs/cicd(関連: codilime.com)
- 要約: ゲート条件を Rego で宣言的に記述し、単一 enforcement point で評価。ポリシー自体をテスト・バージョン管理できる。
- 要点: 判定ロジックのコード外部化。
- 関係: フックに散在する許可/禁止条件を宣言的ポリシー1枚に集約し、フックは評価のみに。ポリシーの単体テストが書ける構成パターン。
- 確認レベル: abstract_only

## I8. Google のレビューコメント自動解決(指摘→修正案ペアリング)
- 書誌: https://research.google/blog/resolving-code-review-comments-with-ml/(ICSE-SEIP 2024)
- 要約: レビューコメントから修正編集を ML 生成。実運用で全コメントの 7.5% が提案編集の適用で解決。
- 要点: コメント対応は著者1変更あたり平均約60分かかる。
- 関係: evaluator / Codex の指摘に generator が修正案 diff を自動添付し、差し戻し往復を削減する。既存は指摘を出すまで。
- 確認レベル: abstract_only

## I9. Anthropic 公式の階層化検証(ターン粒度 goal condition・反証サブエージェント)
- 書誌: https://code.claude.com/docs/en/best-practices
- 要約: 検証を軽→厳に階層化(プロンプト内→毎ターンの goal condition→Stop hook→反証サブエージェント)し、成功主張でなく証拠提示を要求。
- 要点: goal condition は毎ターン別評価器が再検査する。
- 関係: evaluator を待たず generator の各ターン終了時に受け入れ条件サブセットを Stop hook で再検査する「ターン粒度検査」+完了報告への証拠添付必須化。既存ゲートはフェーズ境界のみ。
- 確認レベル: abstract_only

## I10. Factory のマイルストーン・チェックポイント検証
- 書誌: https://factory.ai/news/code-droid-technical-report
- 要約: 大タスクをマイルストーンに分割し、各末尾に必ず検証フェーズ(レビュー・テスト・回帰・統合確認)を置く。
- 要点: 人間の調停は非自明な不一致に限定する。
- 関係: L 規模で「計画→全実装→レビュー」を「マイルストーンごとに小実装+検証」に分割し、失敗遷移表の巻き戻し単位をマイルストーン粒度にする。既存は1タスク=1レビューサイクル。
- 確認レベル: abstract_only

## I11. エージェント頻度に耐える再試行上限(マージキュー DoS の教訓)
- 書誌: https://tianpan.co/blog/2026-07-02-the-merge-queue-is-the-new-bottleneck
- 要約: 「マージさせろ」と指示されたエージェントは同一変更を再キューし続け CI を DoS 化する。
- 要点: エージェント頻度では再試行回数上限と失敗時の原因修正強制が必要。
- 関係: 失敗遷移表に「同一ゲートへの再挑戦回数上限(超過で人間へ)」を明記し、フックに再試行カウンタを追加。既存資源上限はトークン/時間系で、再試行回数軸は未導入。
- 確認レベル: abstract_only
