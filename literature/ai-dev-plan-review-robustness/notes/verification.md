# 領域3: 検証・テストオラクル(採用12件)

各項目の形式: 書誌情報 / 1行要約 / 要点 / 本パイプラインとの関係 / 確認レベル

## V1. メタモルフィックテスティング(oracle 問題の回避)
- 書誌: Segura et al., 2016(サーベイ)+ ML 適用解説(giskard.ai)+ arXiv 2507.22610(SLR)
- 要約: 「入力を変換したとき出力がどう変わるべきか」の関係で正解不明でも検査する定番手法。
- 要点: 例: 特徴量の順序入替で精度不変、学習データ複製で予測不変、入力スケーリングで正規化後の損失不変。
- 関係: planner が goal とは別に「この変更が満たすべきメタモルフィック関係」を1〜2個列挙し、evaluator が pytest 化して照合。property-test(単一実行の不変条件)と直交する「2実行間の関係」。
- 確認レベル: abstract_only

## V2. TestGen-LLM 型の生成テスト採用フィルタ
- 書誌: Alshahwan, Harman, Marginean et al. (Meta), 2024. https://arxiv.org/abs/2402.09171
- 要約: 生成テストを「ビルド通過→反復実行でフレークなくパス→カバレッジ増加」の3段機械フィルタに通す。
- 要点: Meta 本番で 73% の提案が受理。ハルシネーションを機械的に排除。
- 関係: 生成テストの採用条件「N回連続パス+カバレッジ増分>0」を evaluator の機械チェックに追加。diff カバレッジ(提案済み)とはフィルタ構成(反復実行フレーク判定)が異なる。
- 確認レベル: page_read

## V3. LLM オラクルの「実装写経」問題(TOGLL / TOGA 評価)
- 書誌: Hossain & Dwyer 2024 (arXiv 2405.03786) / Liu et al. ESEC/FSE 2023 / arXiv 2410.21136
- 要約: LLM は assertion を人手より多く正しく生成できる一方、「期待挙動でなく現行実装の挙動」を assert してバグを固定化する傾向が実証されている。
- 要点: TOGA には誤分類24%・偽陽性47%超という否定的評価もある。
- 関係: 「生成 assertion が実装出力の写経になっていないか(仕様・goal 由来の値か)」のレビュー項目を追加する根拠。V10(仕様からの事前生成)と組み合わせると構造的に回避できる。
- 確認レベル: abstract_only

## V4. CrossHair(SMT 反例探索+新旧関数の差分検査)
- 書誌: https://github.com/pschanely/crosshair
- 要約: contract 付き Python 関数の反例をシンボリック実行+SMT で自動探索。`diffbehavior` は新旧2版の出力が食い違う入力を自動発見。
- 要点: リファクタ検証向け。torch テンソルには不向きで純 Python の数値ユーティリティ限定。
- 関係: 前処理・metric 計算等のリファクタ時に `crosshair diffbehavior 旧 新` を評価手順に挟む。ベースライン比較実行(具体値)と違い入力空間を記号的に探索する。
- 確認レベル: abstract_only

## V5. deal(design-by-contract)+ CrossHair 連携
- 書誌: https://github.com/life4/deal
- 要約: 事前・事後条件と許容例外をデコレータで宣言し、実行時検査・lint・contract からの自動テスト生成を得る。
- 要点: CrossHair 連携で contract 付き関数の反例探索も可能(安全な関数限定)。
- 関係: 「データ変換・metric 関数には contract を付ける」を generator 規約化すると、仕様が機械検査可能な形でコードに残る。pytest(外側からの検査)と別の、関数自体に仕様を埋める層。
- 確認レベル: page_read

## V6. jaxtyping + beartype(テンソル shape/dtype の型仕様)
- 書誌: Kidger. https://github.com/patrick-kidger/jaxtyping
- 要約: `Float[Tensor, "batch dim"]` 形式の注釈で shape・dtype を宣言し、実行時に機械検査する(JAX 非依存)。
- 要点: 関数間で次元名の整合まで検査される。shape バグは AI 生成 ML コードの典型不具合。
- 関係: python-standards / generator 規約に「モデル・collate・前処理のシグネチャは jaxtyping 注釈+pytest 時に beartype 有効化」を追加すると、テスト実行だけで shape バグが落ちる。mypy では shape は見えない。
- 確認レベル: abstract_only

## V7. FLASH(閾値と seed 分散の統計的妥当性検査)
- 書誌: Dutta et al., ISSTA 2020. https://mir.cs.illinois.edu/awshi2/publications/ISSTA2020-flash.pdf
- 要約: seed を振った反復実行の収束統計から「確率的変動に対して厳しすぎる/緩すぎる assertion」を検出。
- 要点: ランダム性をノイズでなく診断信号として使う。
- 関係: multi-seed の結果を流用し「goal の target / guard_metrics 閾値が seed 分散に対して妥当か(閾値±分散で判定が反転しないか)」を機械チェック。multi-seed(平均±SD 報告のみ)の先の検査。
- 確認レベル: page_read

## V8. データリーケージの静的検出パターン(Yang et al.)
- 書誌: Yang, Brower-Sinning, Lewis, Kästner, ASE 2022. https://arxiv.org/abs/2209.03345
- 要約: 分割前 fit・重複行・分割後の情報流入をデータフロー静的解析で検出。10万超ノートブックで蔓延を実証。
- 要点: preprocessing / overlap / multi-test leakage の分類を与える。
- 関係: 既存 leakage-check スキルの検査項目をこの分類で体系化し、「分割 API と fit 呼び出しの順序」を機械検査する強化材料。
- 確認レベル: abstract_only

## V9. CodeT(複数独立実装の実行合意による多数決オラクル)
- 書誌: Chen et al. (Microsoft), ICLR 2023. https://arxiv.org/abs/2207.10397
- 要約: 同一仕様から複数のコード候補とテストを生成し、コンセンサス集合のサイズで正解らしさを機械採点。
- 要点: HumanEval pass@1 を +18.8pt 改善。
- 関係: 損失関数・metric 実装など重要な単機能に限り、独立実装2つの出力一致を pytest で照合する self-consistency 差分テストとして軽量導入できる。
- 確認レベル: abstract_only

## V10. nl2postcond(仕様文→事後条件 assertion の事前固定)
- 書誌: Endres, Fakhoury, Chakraborty, Lahiri, FSE 2024. https://arxiv.org/abs/2310.01831
- 要約: 自然言語仕様から assertion 形式の事後条件を生成し、正しさと弁別力(誤実装を落とせるか)で評価する枠組み。
- 要点: 生成 postcondition が Defects4J の実バグ64件を検出。
- 関係: 設計書の仕様文から実装前に assertion を生成・固定してから generator に渡すと、オラクル写経問題(V3)を構造的に回避。tdd スキル(人手前提)の機械化版。
- 確認レベル: abstract_only

## V11. NeuraLint / TFCheck(DL 固有の訓練健全性ルール)
- 書誌: Nikanjam et al., TOSEM 2021. https://arxiv.org/abs/2105.08095(TFCheck: arXiv 1909.02562)
- 要約: DL プログラムをグラフ化し23ルール(パラメータ誤り・テンソル不整合・API 誤用)を静的検査。
- 要点: 実装は TF/Keras 対象で PyTorch 未対応。ツール直用は不可、ルールの移植のみ現実的。
- 関係: ルール集(初期損失≈期待値、勾配ノルムの消失/爆発、重み未更新レイヤ)を evaluator 用の PyTorch 訓練スモークテスト・チェックリストに移植する素材。ruff/mypy(汎用)には無い DL 意味論。
- 確認レベル: abstract_only

## V12. 決定論的実行の bit-identical 二重実行検査
- 書誌: PyTorch 公式 Reproducibility note の実践解説(dronelab.dev / medium)
- 要約: 決定論設定+seed 固定で少ステップ学習を2回実行し、重み・optimizer state のハッシュ一致を assert する定石。
- 要点: 非決定的 op はこの設定下で例外を投げるため検出も機械化できる。
- 関係: regression-suite に「N ステップ二重実行→state_dict ハッシュ一致」を1本追加すると、AI が持ち込む非決定性を CI で検出。multi-seed(seed 間分散)と直交する「同一 seed で bit 一致」検査。
- 確認レベル: abstract_only
