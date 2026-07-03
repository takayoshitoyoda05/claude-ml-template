"""guard_scope.py / guard_bash.py で共有する定数。

片方だけ更新されて検知パターンがズレる事故を防ぐため、
秘密情報・生成物の定義はここに一元化する。
"""

# 秘密情報らしき文字列(書き込み内容・コマンド文字列の両方に適用)
SECRET_CONTENT_PATTERNS = [
    r"AKIA[0-9A-Z]{16}",
    r"sk-[A-Za-z0-9]{20,}",
    r"AIza[0-9A-Za-z\-_]{35}",
    r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    r"xox[baprs]-[0-9A-Za-z-]{10,}",
]

# 秘密情報ファイル(ファイル名完全一致)
BLOCKED_FILENAMES = {
    ".env", "credentials.json", "id_rsa", "id_ed25519", "id_ecdsa",
}

# 秘密情報ファイル(拡張子)
BLOCKED_EXTENSIONS = {".pem", ".key", ".p12", ".pfx"}

# 大容量な学習生成物(拡張子)
ARTIFACT_EXTENSIONS = {".pth", ".pt", ".ckpt", ".safetensors"}

# 生成物ディレクトリ(パスに含まれていたらブロック)
ARTIFACT_DIR_PATTERNS = [
    "/checkpoints/", "/outputs/", "/runs/", "/.venv/",
    "/_trash_candidates/",
]
