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
_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----"
)

# END 行が無い秘密鍵(出力が途中で切れた場合など)。ブロック用パターンは
# 終端が無いと一致しないので、BEGIN に続く base64 らしき文字を食い切る。
# `\\` を含めるのは JSONL 内で改行が `\n` とエスケープされているため
_PRIVATE_KEY_HEADER_ONLY = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----[A-Za-z0-9+/=\s\\]*"
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
_KEYVALUE_PATTERN = re.compile(
    r"([\"']?)([A-Za-z0-9_-]{1,64})\1(\s*[=:]\s*)([\"']?)([^\s\"']{8,})\4"
)

# キー名がこれを含むとき、その値を秘密情報とみなす
_SECRET_KEY_WORDS = re.compile(
    r"api[_-]?key|token|secret|password|passwd|credential", re.IGNORECASE
)


def _mask_keyvalue(m: "re.Match[str]") -> str:
    """key=value / "key": "value" の値だけを伏せる(キー名は残す)。"""
    key_quote, key, separator, value_quote, _value = m.groups()
    if not _SECRET_KEY_WORDS.search(key):
        return m.group(0)
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
    masked = _PRIVATE_KEY_HEADER_ONLY.sub("[MASKED PRIVATE KEY]", masked)
    masked = _URL_CREDENTIALS.sub(r"\1[MASKED]\2", masked)
    for pat in _SIMPLE_PATTERNS:
        masked = pat.sub("[MASKED]", masked)
    # key=value / JSON 形式は値だけマスクする
    masked = _KEYVALUE_PATTERN.sub(_mask_keyvalue, masked)
    return masked
