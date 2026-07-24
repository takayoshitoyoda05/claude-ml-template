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
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),  # GitHub PAT
    re.compile(r"gho_[A-Za-z0-9]{20,}"),  # GitHub OAuth
]

_KEYVALUE_PATTERN = re.compile(
    r"((?:api[_-]?key|token|secret|password|passwd)\s*[=:]\s*)"
    r"(['\"]?)([^\s'\"]{8,})(\2)",
    re.IGNORECASE,
)


def mask(text: str) -> str:
    """既知の秘密情報パターンを [MASKED] に置換して返す。"""
    if not text:
        return text
    masked = text
    for pat in _SIMPLE_PATTERNS:
        masked = pat.sub("[MASKED]", masked)
    # key=value 形式は値だけマスクする
    masked = _KEYVALUE_PATTERN.sub(r"\1\2[MASKED]\4", masked)
    return masked
