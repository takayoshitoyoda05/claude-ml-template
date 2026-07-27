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
# 中核語をパターンの先頭アンカーにする。任意のキー名に一致させると、
# `{"command": "export API_KEY=abc"}` のような入力で外側の `"command": "..."`
# が値ごと一致して走査位置を進めてしまい、値の中の `API_KEY=abc` が検査
# されないまま素通りする(action_log は json.dumps の結果をマスクするので、
# 実運用の入力はこの形になる)。秘密語で始まる形にすれば飲み込みが起きない。
# `AWS_SECRET_ACCESS_KEY` のような接頭辞付きは、`SECRET_ACCESS_KEY` の位置から
# 一致が始まり `AWS_` はそのまま残るだけなので、値のマスクは正しく効く。
#
# 中核語の前に `[A-Za-z0-9_-]*` を置かないことがそのまま ReDoS 対策にもなる
# (その形は一致しない長い識別子で総当たりが起き、処理時間が入力長の2乗に伸びる)。
_SECRET_KEY_WORDS_SRC = r"api[_-]?key|token|secret|password|passwd|credential"

# 値は4通り。JSON 文字列の中でエスケープされた引用符に囲まれた形
# (`API_KEY=\"my secret\"`)を最初に見るのは、裸の値として先に食われると
# 空白の手前で切れてしまうため。引用符の中では `\<任意の1文字>` を1単位として
# 読み飛ばし、エスケープ済みの引用符を終端と誤認しないようにする。
# 値の長さに下限は設けない(パターンが秘密語アンカーなので、`password="1234"`
# のような短い値まで拾って問題ない)。
# 中核語の後に続けてよいのは複数形の `s` と、`_`/`-` 区切りで始まる残りだけ。
# 任意の英数字を許すと `tokenizer = AutoTokenizer...` のような ML コードで
# 頻出する語を誤爆し、ログが読めなくなる(`token` + `izer` に一致するため)。
_KEYVALUE_PATTERN = re.compile(
    r"((?:" + _SECRET_KEY_WORDS_SRC + r")s?(?:[_-][A-Za-z0-9_-]{0,32})?"
    r"[\"']?\s*[=:]\s*)"
    r"(?:"
    r"\\+\"((?:[^\"\\]|\\.)*?)\\+\""
    r"|\"((?:[^\"\\]|\\.)+)\""
    r"|'((?:[^'\\]|\\.)+)'"
    r"|([^\s,;}\)\]]+)"
    r")",
    re.IGNORECASE,
)


def _mask_keyvalue(m: "re.Match[str]") -> str:
    """key=value / "key": "value" の値だけを伏せる(キー名と区切りは残す)。

    値は4通りのどれか1つだけが一致する(JSON 内のエスケープされた引用符 /
    ダブルクォート / シングルクォート / 引用符なし)。どれが一致したかで、
    復元する引用符を決める。
    """
    prefix = m.group(1)
    if m.group(2) is not None:
        return f'{prefix}\\"[MASKED]\\"'
    if m.group(3) is not None:
        return f'{prefix}"[MASKED]"'
    if m.group(4) is not None:
        return f"{prefix}'[MASKED]'"
    return f"{prefix}[MASKED]"


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
