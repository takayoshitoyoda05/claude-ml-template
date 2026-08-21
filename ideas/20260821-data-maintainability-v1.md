# データ保守性の向上(研究用プロジェクト化)発散 v1

日付: 2026-08-21
文脈: テンプレートを研究用プロジェクトの基盤にするにあたり、実験データ・
データセット・成果物の保全、来歴(provenance)、再現性、破損・消失対策を
強化したい。絞り込みは design-interview で行う。

## 既存装備(空白地帯の特定)
- 破壊防止: guard_scope の data/ 書き込みブロック
- 実験記録: EXPERIMENT_LOG.md、mlflow-log / leakage-check / multi-seed、
  logs/runs の tee、report_gen の evidence バンドル
- 空白地帯: **データ自身の来歴・完全性検証・復元**

## 発散した案

### G1: 不変性・破壊防止系
1. コンテンツアドレス格納: data/objects/<sha256> の不変格納+manifest 参照。
   上書き事故が構造的に不可能になる
2. raw の物理 read-only 化: data/raw/ を取得後 chmod -w。guard_scope
   (エージェント対策)を OS 権限(人間の事故対策)で二重化
3. 三原則の invariants 昇格: 「raw 不可侵/前処理は必ずスクリプト/
   manifest がパスの唯一の真実」を invariants.md に明文化

### G2: 来歴・台帳系
4. DATA_LOG.md(データ台帳): append-only で入手元・入手日・ライセンス・
   ハッシュ・前処理コマンドを記録。EXPERIMENT_LOG の姉妹ファイル
5. EXPERIMENT_LOG × provenance: 実験エントリに使用データのハッシュ列を
   必須化し、spec_gate 式に機械検査
6. run manifest: 成果物(重み・図表)に config+データハッシュ+git commit+
   seed を自動同梱(report_gen の evidence 思想の成果物版)

### G3: 完全性検証・ゲート系
7. data.lock(lockfile 類推): 各ファイルの sha256・サイズ・行数。実験実行時に
   自動照合(uv.lock と同じ思想)
8. データ版 spec_gate: manifest に無いデータでの実験・ハッシュ不一致での
   完了をフックでブロック
9. 定期 fsck: ハッシュ照合を cron / doctor で定期実行し bit rot を早期検知
10. Stop フック検知(session_monitor 路線): 実験後に data.lock と実測の差分を
    警告(警告のみ・fail-open。防止をすり抜けた変化の検知)

### G4: バージョン管理・再構築系
11. DVC / git-annex / git-lfs によるデータの世代管理
12. データマイグレーション: 前処理・スキーマ変更を data/migrations/ に
    番号付きスクリプトで積み、raw から任意版を再構築可能に
13. 1コマンド完全再現: make reproduce RUN=xxx(データ復元→コード checkout→
    seed 固定→再実行)

### G5: 最小運用系
14. doctor にバックアップ検査: 最終バックアップからの日数・バックアップ先の
    生存確認(3-2-1 ルール)
15. 台帳1ファイルだけの最小導入(DATA_LOG.md のみ。運用コストほぼゼロ)

## 軽い評価

| グループ | 新規性 | 実現性 | インパクト | 検証しやすさ |
|---|---|---|---|---|
| G1 不変性 | 中 | 高(chmod・invariants は即日) | 高 | 高 |
| G2 来歴・台帳 | 中 | 高(既存装備の延長) | 高(論文・査読で効く) | 中 |
| G3 検証・ゲート | 高 | 高(フック様式の前例あり) | 中〜高 | 高 |
| G4 バージョン管理 | 中 | 中(外部ツール依存) | 高 | 中 |
| G5 最小運用 | 低 | 極高 | 低〜中 | 高 |

関係: G5 ⊂ G2 ⊂ G3 ⊂ G4 の積み上げ。G1 は独立(いつでも入れられる)。
テンプレートの既存思想(フック機械検査・fail-open・staging 配布)に最も
素直に乗るのは G3、G2 と組むと「来歴+完全性」が揃う。

## 次のステップ
方向性を選んだら design-interview で仕様を固める(対象ディレクトリ構成・
lock の粒度・ゲートの強度(警告/ブロック)・既存 guard_scope との責務分担)。
