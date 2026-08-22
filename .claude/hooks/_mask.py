#!/usr/bin/env python3
"""ログ書き込み前の秘密情報マスキング。

エージェントのトレースにはプロンプト・ツール引数・コマンド出力が含まれ、
秘密情報が混入しうる。ログに書く前に既知パターンを伏せ字にする。
"""

import json
import re
from pathlib import Path

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
# スキーム部分に長さ上限を置く。上限が無いと `token=yyyy...` のような長い
# 英数字列に対してスキーム候補の総当たりが起き、処理時間が入力長の2乗に伸びる
# (実測: 20万文字で 26 秒)。実在のスキームは https / postgres / mongodb+srv 等
# なので 15 文字あれば足りる
_URL_CREDENTIALS = re.compile(
    r"([a-zA-Z][a-zA-Z0-9+.-]{0,15}://)[^\s/@]+(?::[^\s@]*)?(@)"
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

# キーと区切りまでを正規表現で見つけ、値の終端は `_scan_value` が文字単位で決める。
# 終端判定を正規表現1本でやろうとすると、引用符の内側のエスケープと JSON の
# 閉じ引用符を区別できず、「後半が漏れる」か「後続コマンドまで飲む」の
# どちらかが必ず起きる(可変長後読みが必要になるが Python の re では書けない)。
# 中核語の後に続けてよいのは複数形の `s` と、`_`/`-` 区切りで始まる残りだけ。
# 任意の英数字を許すと `tokenizer = AutoTokenizer...` のような ML コードで
# 頻出する語を誤爆し、ログが読めなくなる(`token` + `izer` に一致するため)。
_KEY_PREFIX_PATTERN = re.compile(
    r"(?:" + _SECRET_KEY_WORDS_SRC + r")s?(?:[_-][A-Za-z0-9_-]{0,32})?"
    r"[\"']?\s*[=:]\s*",
    re.IGNORECASE,
)

# 値の開始が引用符かどうかを見るときの候補。JSON 文字列の中では引用符が
# エスケープされる(`\"`)ので、2文字の形を先に試す
_QUOTE_FORMS = ('\\"', "\\'", '"', "'")

# 裸の値の終端になる文字(空白と、JSON/シェルの区切り)
_BARE_VALUE_STOP = set(" \t\r\n,;}])")


def _scan_value(text: str, start: int) -> tuple[int, str]:
    """`start` から始まる値の終端位置と、使われていた引用符を返す。

    Args:
        text: 走査対象の全文。
        start: 値の開始位置(区切りの直後)。

    Returns:
        (終端位置, 引用符). 終端位置は値の直後を指す(引用符があれば閉じ引用符を
        含む)。引用符は復元用で、引用符なしなら空文字列。
    """
    n = len(text)
    if start >= n:
        return start, ""

    for quote in _QUOTE_FORMS:
        if not text.startswith(quote, start):
            continue
        i = start + len(quote)
        while i < n:
            if text[i] == "\\":
                # バックスラッシュの連続数で「閉じ」と「値の中のエスケープ済み
                # 引用符」を見分ける
                run = i
                while run < n and text[run] == "\\":
                    run += 1
                if run < n and text[run] in "\"'":
                    if len(quote) == 2:
                        # JSON 文字列の中。値を囲む引用符は `\"`(1個+引用符)、
                        # 値の中の引用符は `\\\"`(3個+引用符)なので、連続数が
                        # 1のときだけ閉じとみなす
                        if run - i == 1 and text[run] == quote[1]:
                            return run + 1, quote
                    elif (run - i) % 2 == 0 and text[run] == quote:
                        # バックスラッシュが偶数個ならそれ自体がエスケープされた
                        # バックスラッシュなので、直後の引用符は生の閉じ引用符
                        return run + 1, quote
                    i = run + 1  # 値の一部として読み飛ばす
                    continue
                i = run
                continue
            if text.startswith(quote, i):
                return i + len(quote), quote
            i += 1
        return n, quote  # 閉じないまま終端(出力が切れた場合など)

    i = start
    while i < n:
        char = text[i]
        if char == "\\" and i + 1 < n:
            # バックスラッシュは後続1文字のエスケープとして読み飛ばす。
            # `\"` を JSON の閉じとみなして終端にすると
            # `TOKEN=abc\"SECRET_TAIL` の後半が漏れる。実際の JSON では閉じ
            # 引用符は素の `"` になる(json.dumps の出力は
            # `{"command": "export TOKEN=abc"}`)ので、下の条件で正しく止まる
            i += 2
            continue
        if char in _BARE_VALUE_STOP or char in "\"'":
            break
        i += 1
    return i, ""


def _mask_keyvalues(text: str) -> str:
    """秘密語を含むキーの値だけを伏せる(キー名と区切りは残す)。"""
    out = []
    pos = 0
    for m in _KEY_PREFIX_PATTERN.finditer(text):
        if m.start() < pos:
            continue  # 直前にマスクした値の内側にあるキーは飛ばす
        end, quote = _scan_value(text, m.end())
        if end <= m.end():
            continue  # 値が空。区切りだけの行などは触らない
        out.append(text[pos : m.end()])
        out.append(f"{quote}[MASKED]{quote}")
        pos = end
    out.append(text[pos:])
    return "".join(out)


# Phase 2 staging: 辞書パターンによるマスク(_staging_data_protection_p2.py 挿入)。
# .claude/checkpoints/data_patterns.json を読み、辞書ヒットも [MASKED] にする。
# 他モジュールを import せず、ここで読み込み・compile・置換を完結させる
# (共有エンジン側の loader と同じスキーマ解釈を保つ。PC-26)。
_MAX_DICTIONARY_PATTERNS = 100


def _load_dictionary_patterns() -> list[re.Pattern]:
    """data_patterns.json を読み、compile 済みパターンのリストを返す。

    壊れた JSON・想定外の型・compile 失敗は fail-open で無視する
    (毎ツール実行で走る秘密語マスクという保全系の性質上、辞書の破損で
    従来のマスクまで止めてはならない)。
    """
    path = Path.cwd() / ".claude" / "checkpoints" / "data_patterns.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return []
    patterns = payload.get("patterns") if isinstance(payload, dict) else None
    if not isinstance(patterns, list):
        return []
    compiled: list[re.Pattern] = []
    for raw in patterns[:_MAX_DICTIONARY_PATTERNS]:
        if not isinstance(raw, str):
            continue
        try:
            compiled.append(re.compile(raw))
        except re.error:
            continue
    return compiled


def _mask_dictionary_patterns(text: str) -> str:
    """辞書パターン(data_patterns.json)のヒットを [MASKED] に置換する(fail-open)。"""
    for pat in _load_dictionary_patterns():
        text = pat.sub("[MASKED]", text)
    return text


def mask(text: str) -> str:
    """既知の秘密情報パターンを [MASKED] に置換して返す。"""
    if not text:
        return text
    # 秘密鍵ブロックとURL認証情報は他パターンに先に食われると本体を取り逃すため先頭で処理する
    masked = _PRIVATE_KEY_BLOCK.sub("[MASKED PRIVATE KEY]", text)
    masked = _URL_CREDENTIALS.sub(r"\1[MASKED]\2", masked)
    for pat in _SIMPLE_PATTERNS:
        masked = pat.sub("[MASKED]", masked)
    masked = _mask_dictionary_patterns(masked)
    # key=value / JSON 形式は値だけマスクする
    masked = _mask_keyvalues(masked)
    return masked
