# 研究データ保護 統合案 v1(保全軸+漏洩軸)

日付: 2026-08-21
元メモ: ideas/20260821-data-maintainability-v1.md(保全)、
ideas/20260821-data-leakage-prevention-v1.md(漏洩)

## 2軸の関係
- 保全(消えない・壊れない・来歴)と漏洩(外に出ない)は部品を共有する:
  manifest/lock は保全では破損検知、漏洩では diff 検疫・pre-commit 検知の
  パターン源になる
- 設計原則の非対称: 保全系フックは「警告のみ・fail-open」(session_monitor 側)、
  漏洩系ガードは「fail-closed」(guard_scope/guard_bash 側)

## 段階パッケージ

### Phase 1: 土台(規約と台帳。実装ほぼゼロ・即日)
1. invariants 明文化: raw 不可侵/前処理は必ずスクリプト/manifest が唯一の
   真実+「外部に出てよいのは集計値・図・ハッシュのみ。個票・生データ禁止」
2. DATA_LOG.md(append-only データ台帳): 入手元・日付・ライセンス・ハッシュ・
   前処理コマンド
3. raw の物理 read-only 化(chmod -w)+公開・共有前チェックリスト
   (handoff / paper-writing に追加)

### Phase 2: 機械化(フック様式に乗せる本命)
4. data.lock+完全性検証: 実験時の自動照合、doctor に fsck・バックアップ
   経過日数検査。差分は Stop フック警告(fail-open)
5. data_egress_gate: guard_bash 拡張。data/ パス×アップロード系コマンド、
   data/ 読み→外部コマンドへのパイプをブロック(fail-closed)
6. 外部送出前の diff 検疫: cross-review / claude-security の送信前スキャン
7. _mask.py データ識別子辞書拡張+report_gen sanitize+EXPERIMENT_LOG に
   使用データハッシュ列を必須化(provenance 機械照合)
8. git 混入防止: 内容ベース pre-commit 検知+nbstripout+「テストは合成
   データ・ログは shape/hash のみ」規約(python-standards 追記)

### Phase 3: 高機密オプション(データの機密度で選択)
9. CLAUDE_DATA_NO_READ: エージェントの data/ 読み取り遮断。LLM API に内容が
   渡る経路を塞げる唯一の手段。医療・個人情報なら必須級
10. DVC 世代管理/migrations/1コマンド再現/暗号化保管(必要になってから)

## 推奨
Phase 1+2 を実装対象とし、Phase 3 は扱うデータ確定時に判断。
理由: 1-2 は機密度によらず全研究に効き、既存装備(guard_bash・_mask.py・
doctor・フック様式・staging 配布)の延長で実装リスクが小さい。
3-9 は作業性への影響が大きく、データ確定後の導入が合理的。

## 次のステップ
design-interview で詰める論点: データ識別子辞書の定義方法(どこに置くか・
プロジェクト固有性)/data.lock の粒度と生成タイミング/egress の許可リスト
(集計値の出力は可、等)/既存 guard・_mask との責務分担/Phase 1 と 2 を
1回のパイプラインで流すか分けるか
