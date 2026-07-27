#!/usr/bin/env python3
"""ログ書き込み前の秘密情報マスキング。

エージェントのトレースにはプロンプト・ツール引数・コマンド出力が含まれ、
秘密情報が混入しうる。ログに書く前に既知パターンを伏せ字にする。
"""

import re

from _common import SECRET_CONTENT_PATTERNS

# 設計書からの逸脱(レビュー指摘採用): 検知パターンの二重管理によるドリフトを
# 避けるため、guard系と共有の _common.SECRET_CONTENT_PATTERNS を土台にする。
# マスキング専用の追加分(guard側に無いghp_/gho_)と、値だけを伏せるkey=value
# 形式(キャプチャ置換が必要なため _common のパターンとは別立て)のみここで持つ。
_SIMPLE_PATTERNS = [re.compile(p) for p in SECRET_CONTENT_PATTERNS] + [
    # GitHub のトークンは接頭辞が用途ごとに分かれる(pat=personal, oauth,
    # user-to-server, server-to-server, refresh)。ghp_/gho_ だけ塞いでも
    # 他形式が素通りするため、接頭辞をまとめて拾う
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    # AWS の一時認証(STS)のキーIDは ASIA 始まり。_common の AKIA だけでは漏れる
    re.compile(r"ASIA[0-9A-Z]{16}"),
    # Slack のアプリレベルトークン(xox* とは別系統)
    re.compile(r"xapp-[0-9A-Za-z-]{10,}"),
    # Authorization ヘッダ等の Bearer トークン(JWT を含む)
    re.compile(r"(?i:bearer)\s+[A-Za-z0-9._~+/-]{16,}=*"),
    # 素の JWT(header.payload.signature)
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+"),
]

# 秘密鍵は「ヘッダ行だけ」を伏せても base64 の本体が平文で残る。ブロック全体を
# 1つの塊として最初に潰す(_SIMPLE_PATTERNS がヘッダを [MASKED] に置き換えると
# ブロックの開始位置を見失うため、必ず他パターンより先に適用する)
# END 行があればそこまで、無ければ末尾まで伏せる。END が無い場合にどこで鍵が
# 終わるかは判定できず、base64 文字だけを食う書き方では暗号化 PEM の
# `Proc-Type:` / `DEK-Info:` ヘッダで停止して以降の鍵データが平文で残る。
# 鍵が出ている時点で異常事態なので、後続を残して漏らすより潰す方を選ぶ
_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----"
    r"[\s\S]*?(?:-----END [^-]*PRIVATE KEY-----|\Z)"
)

# URL に埋め込まれた認証情報(postgres://user:pw@host、https://user:pw@repo)。
# userinfo 全体(user:pass、および user だけの形)を伏せる。ユーザー名の位置に
# トークンを置く認証方式(https://<token>@github.com 等)があるため、パスワード
# だけ伏せる粒度では漏れる。スキームとホストは残すのでログから接続先は追える
_URL_CREDENTIALS = re.compile(
    r"([a-zA-Z][a-zA-Z0-9+.-]*://)[^\s/@]+(?::[^\s@]*)?(@)"
)

# キー名を「1回だけ」取り、中核語を含むかどうかは置換関数側で判定する。
# 中核語の前後に `[A-Za-z0-9_-]*` を置く書き方だと、一致しない長い識別子に
# 対して総当たりが起き、処理時間が入力長の2乗で伸びる(実測: 3201文字で
# 0.54秒、5万文字で約130秒)。action_log は毎ツール実行で走るため実害になる。
# キー名の引用符を任意にすることで、JSON の `{"api_key": "..."}` 形式にも
# 一致する(action_log は json.dumps の結果をマスクするので、実際のログは
# ほぼすべてこの形)。
# 値は引用符の有無で終端が変わる。引用符があれば閉じ引用符まで(空白を含む
# パスフレーズが切れないように)、無ければ空白や JSON の区切り文字まで。
# 否定文字クラス1つで書き、交替の繰り返しを避ける(バックトラックを抑えるため)。
# キー名側は前後に `[A-Za-z0-9_-]*` を置かない(その形は一致しない長い識別子で
# 総当たりが起き、処理時間が入力長の2乗に伸びる)。
_KEYVALUE_PATTERN = re.compile(
    r"([\"']?)([A-Za-z0-9_-]{1,64})\1(\s*[=:]\s*)"
    r"(?:\"([^\"]{6,})\"|'([^']{6,})'|([^\s,;}\)\]]{8,}))"
)

# キー名がこれを含むとき、その値を秘密情報とみなす
_SECRET_KEY_WORDS = re.compile(
    r"api[_-]?key|token|secret|password|passwd|credential", re.IGNORECASE
)


def _mask_keyvalue(m: "re.Match[str]") -> str:
    """key=value / "key": "value" の値だけを伏せる(キー名は残す)。

    値は3通りのどれか1つだけが一致する(ダブルクォート / シングルクォート /
    引用符なし)。どれが一致したかで、復元する引用符を決める。
    """
    key_quote, key, separator = m.group(1), m.group(2), m.group(3)
    if not _SECRET_KEY_WORDS.search(key):
        return m.group(0)
    if m.group(4) is not None:
        value_quote = '"'
    elif m.group(5) is not None:
        value_quote = "'"
    else:
        value_quote = ""
    return (
        f"{key_quote}{key}{key_quote}{separator}"
        f"{value_quote}[MASKED]{value_quote}"
    )


def mask(text: str) -> str:
    """既知の秘密情報パターンを [MASKED] に置換して返す。"""
    if not text:
        return text
    # 秘密鍵ブロックとURL認証情報は他パターンに先に食われると本体を取り逃すため先頭で処理する
    masked = _PRIVATE_KEY_BLOCK.sub("[MASKED PRIVATE KEY]", text)
    masked = _URL_CREDENTIALS.sub(r"\1[MASKED]\2", masked)
    for pat in _SIMPLE_PATTERNS:
        masked = pat.sub("[MASKED]", masked)
    # key=value / JSON 形式は値だけマスクする
    masked = _KEYVALUE_PATTERN.sub(_mask_keyvalue, masked)
    return masked
