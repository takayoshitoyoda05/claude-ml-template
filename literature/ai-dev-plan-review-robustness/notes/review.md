# 領域2: レビューの堅牢化(採用12件)

各項目の形式: 書誌情報 / 1行要約 / 要点 / 本パイプラインとの関係 / 確認レベル

## R1. Refute-or-Promote(反証専任エージェントによる指摘の濾過)
- 書誌: Abhinav Agarwal, 2026. https://arxiv.org/abs/2604.19049
- 要約: 各レビュー指摘に「潰すこと」を任務とする敵対エージェントを当て、反証に生き残った指摘だけ昇格させる。
- 要点: 31日間の運用で候補指摘の約79%を開示前に排除。協調的 debate は説得力のある1エージェントに多数決が引きずられる脆弱性があると指摘。
- 関係: 手順6と6.8の間に refuter パスを挿入し、CRITICAL 指摘を再現コードか反例で潰せなければ昇格・潰せたら破棄。既存の「指摘一致で重大度引き上げ」(合意ベース)と逆方向の機構。
- 確認レベル: page_read

## R2. CriticGPT(レビュアー自身の検出能力の較正)
- 書誌: McAleese et al. (OpenAI), 2024. https://arxiv.org/abs/2407.00215
- 要約: 意図的に埋めたバグで訓練した批評専用モデル。nitpick と hallucinated bug の両方を抑制。
- 要点: 自然発生バグで人間批評より63%好まれる。網羅性と精度のトレードオフを制御可能。
- 関係: 「既知バグを注入した較正用 diff」で evaluator / Codex の検出率・虚偽指摘率を定期計測し、レビュープロンプトを校正する運用に転用できる(ミューテーションはテストの質、これはレビュアーの質)。
- 確認レベル: abstract_only

## R3. HalluJudge(レビュー指摘の接地検証)
- 書誌: Tantithamthavorn et al., 2026(FSE'26 Industry). https://arxiv.org/abs/2601.19072
- 要約: LLM 生成レビューコメントが実コード文脈に接地しているかを reference-free で判定。
- 要点: 企業実運用で F1=0.85、1判定 $0.009。
- 関係: evaluator / Codex の各指摘が diff の実在行・実在シンボルを参照しているかを final-gate 前に検証する軽量 grounding チェッカ。既存は指摘の「一致」のみで接地は未検証。
- 確認レベル: page_read

## R4. Agent-as-a-Judge(軌跡・中間成果物の要件単位照合)
- 書誌: Zhuge et al. (Meta AI), 2024. https://arxiv.org/abs/2410.10934
- 要約: 最終成果物でなくタスク解決の全軌跡を要件単位で検査して評価する枠組み。
- 要点: コード生成タスクで人間評価と高一致、LLM-as-a-Judge より安価。
- 関係: spec-auditor を「最終 diff の監査」から「要件×実行トレース照合(satisfied/unsatisfied+証拠パス)」へ拡張できる。
- 確認レベル: abstract_only

## R5. PoLL(小型モデル陪審による自己系統バイアス遮断)
- 書誌: Verga et al. (Cohere), 2024. https://arxiv.org/abs/2404.18796
- 要約: 単一大型ジャッジを異系統小型モデル複数の合議に置換すると人間との一致が上がりコストは 1/7 以下。
- 要点: intra-model bias(自己系統贔屓)が減る。
- 関係: goal 三値判定と final-gate の境界事例だけ、Claude+Codex+第三系統の3者多数決にする。既存2者の「一致で引き上げ」とは別の self-preference 対策。
- 確認レベル: abstract_only

## R6. Chain-of-Verification(判定の主張単位の自己検証)
- 書誌: Dhuliawala et al. (Meta AI), ACL 2024 Findings. https://arxiv.org/abs/2309.11495
- 要約: ドラフト→検証質問生成→元回答を見せず独立回答→最終回答の4段で hallucination を削減。
- 要点: 検証質問に「独立に」答えさせることがバイアス遮断の要。
- 関係: evaluator の verdict を2パス化し、判定文から抽出した検証質問に判定文を見せない新規コンテキストで(Bash 実行込みで)回答させ、矛盾なら保留に落とす。
- 確認レベル: abstract_only

## R7. AIDev(レビューボットの signal ratio 実測)
- 書誌: Chowdhury, Banik, Ferdous, Shamim, 2026. https://arxiv.org/abs/2604.03196
- 要約: 13種のレビューボット×3,109 PR の実証。全エージェントが signal ratio 平均60%未満=ノイズ過多。
- 要点: ボットのみの PR はマージ率が人間のみより23pt低い。ツール別実測値あり。
- 関係: 指摘ごとの採択/棄却を記録して signal ratio をレビュー軸別に常時計測し、閾値割れの観点を retrospective で降格する KPI 設計の根拠。
- 確認レベル: page_read

## R8. LLM-as-a-Judge のバイアス監査(順序・test-retest)
- 書誌: arXiv 2604.16790(2026)+ 関連 arXiv 2602.02219(rubric 順序バイアス)
- 要約: 固定 rubric でもコード評価の再現性が揺れ、選択肢の提示順だけでスコアが変わる。
- 要点: 順序シャッフルで position bias を緩和できる。
- 関係: evaluator-standards の rubric 項目順をシード固定でシャッフルし、境界スコアは順序を変えて2回評価、不一致なら人間へ。判定の再現性チェックは既存機構に無い。
- 確認レベル: abstract_only

## R9. 不確実性による選択的判定(HUMAN_REVIEW という第三の出口)
- 書誌: Xia et al., 2025(UQ サーベイ). https://arxiv.org/abs/2503.15850
- 要約: verbalized confidence は過信傾向で、較正を経て初めて棄権・エスカレーション閾値に使える。
- 要点: selective prediction =「自信がないときは判定しない」設計の総覧。
- 関係: evaluator / final-gate に判定一致率(同一入力 k 回)を持たせ、閾値未満なら PASS/FAIL でなく HUMAN_REVIEW を返す出口を失敗遷移表に追加。既存遷移表に不確実性で人間へ逃がす出口は無い。
- 確認レベル: abstract_only

## R10. SWE-PRM(実行途中の軌跡監視・介入)
- 書誌: "Act Like You're Paying for This" 2025. https://arxiv.org/html/2509.02360v1(関連: CodePRM, AgentPRM arXiv 2511.08325)
- 要約: inference-time PRM が実行中の堂々巡り・目的逸脱を検出して是正する。
- 要点: 成果物完成後でなく実行途中に介入する process 監視。
- 関係: 実装中に checkpoints のツール実行ログを軽量モデルで定期採点し、「進捗なしループ」「スコープ外編集」を検出したら停止・差し戻すウォッチドッグ。既存はすべて事後評価。
- 確認レベル: abstract_only

## R11. CodeX-Verify(検証観点の直交性という構成理論)
- 書誌: "Multi-Agent Code Verification via Information Theory", 2025. https://arxiv.org/abs/2511.16708
- 要約: 検出パターンが条件付き独立な検証エージェントの組合せは単一を必ず上回ることを情報理論で証明。
- 要点: 4種の専門エージェントでテスト実行なしに検証済みラベルの76.1%を検出。
- 関係: スカウト隊・評価軸を「観点の重複度」で見直し、相関の低い観点(資源リーク・並行性・数値安定性)を足す設計原理。何を並べるかの理論的指針。
- 確認レベル: abstract_only

## R12. APCA(テスト合格≠正しい: overfitting パッチ検査)
- 書誌: "Leveraging LLM for Automatic Patch Correctness Assessment" IEEE TSE 2024. https://www.computer.org/csdl/journal/ts/2024/11/10659742/1ZPPbcPcJA4(背景: arXiv 2405.01466)
- 要約: 「テスト全通過だが仕様的に誤り(症状隠し)」のパッチ検出は APR 分野の確立した研究領域。
- 要点: 根本原因修正か症状隠しかを静的+動的特徴で判定する系譜。
- 関係: バグ修正タスク限定で「修正が失敗テストの入力値に特化していないか(定数直書き・条件の特殊化)」の検査を evaluator に追加。テスト側でなくパッチ側の意味検査。
- 確認レベル: abstract_only

## 周辺情報源(採用見送り・実在確認済み)
- FindTheFlaws(https://arxiv.org/pdf/2503.22989): 批評モデル評価用の注釈付きデータセット
- CR-Bench(https://arxiv.org/html/2603.11078v1): AI レビューエージェントの実用性ベンチ
- Greptile benchmarks(https://www.greptile.com/benchmarks): レビューボットの precision-recall 実測比較
