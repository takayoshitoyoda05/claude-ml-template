"""guard_scope.py / guard_bash.py / spec_gate.py / spec_approve.py で共有する定数・関数。

片方だけ更新されて検知パターンがズレる事故を防ぐため、
秘密情報・生成物・保護パスの定義はここに一元化する。
受け入れ条件テーブルのパーサも spec_gate.py と verify-hooks から共通で使えるよう
ここに置く(stdlib の re のみ使用)。
spec_gate.py / spec_approve.py が共有する対象ディレクトリ解決ロジック
(resolve_docs_dir / resolve_spec_dir)と、enforce_eval.py / spec_gate.py が
共有するリポジトリ状態ハッシュ(repo_state_signature)もここに一元化する。
"""
import hashlib
import os
import re
import subprocess
from pathlib import Path

# 秘密情報らしき文字列(書き込み内容・コマンド文字列の両方に適用)
SECRET_CONTENT_PATTERNS = [
    r"AKIA[0-9A-Z]{16}",
    r"sk-[A-Za-z0-9]{20,}",
    # sk-[A-Za-z0-9]{20,} は連続英数字のOpenAI形式のみ拾う。Anthropic形式
    # (sk-ant-api03-... のようにハイフン/アンダースコアで区切られる)は
    # 連続20文字に届かないためすり抜ける。別パターンで拾う。
    r"sk-ant-[A-Za-z0-9_-]{20,}",
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

# ガード自身とフック設定・spec-compliance の承認記録(エージェントによる
# 自己書き換え・承認偽装を防ぐ。正規化済み絶対パスに含まれていたらブロック。
# 変更はユーザーが手動で行う)
PROTECTED_PATH_PATTERNS = [
    "/.claude/hooks/",
    "/.claude/settings.json",
    "/.claude/settings.local.json",
    "/.claude/spec/approvals.txt",
]


class AcceptanceTableError(Exception):
    """受け入れ条件テーブルのパースに失敗したことを表す例外。

    テーブル不在・列数不一致・列名不正・ID形式不正・ID重複・ID欠番の
    いずれかで送出される。呼び出し側は安全側に倒し、これを検知したら
    ブロック(exit 2)すること。
    """


# 受け入れ条件テーブルの列名(日本語ヘッダー) -> 内部キー
_HEADER_ALIASES = {
    "ID": "id",
    "要件": "requirement",
    "検証方法": "verify",
    "期待結果": "expected",
    "種別": "type",
    "対象": "target",
}


def split_table_row(line):
    """Markdownテーブルの1行をセルのリストに分割する。

    先頭・末尾の `|` を取り除き、エスケープされた `\\|` はセル内の
    文字として扱う(分割区切りにしない)。各セルは前後の空白を除去する。
    """
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    placeholder = "\x00"
    escaped = line.replace("\\|", placeholder)
    cells = escaped.split("|")
    return [c.replace(placeholder, "|").strip() for c in cells]


def is_separator_row(cells):
    """Markdownテーブルの区切り行(`---`, `:--`, `--:`, `:-:` 等)かどうか。"""
    non_empty = [c.strip() for c in cells if c.strip() != ""]
    if not non_empty:
        return False
    return all(re.fullmatch(r":?-{1,}:?", c) for c in non_empty)


def parse_acceptance_table(design_text):
    """設計書テキストから「## 受け入れ条件」直下のMarkdownテーブルを抽出する。

    戻り値: [{"id":..., "requirement":..., "verify":..., "expected":...,
              "type":..., "target":...}, ...]

    安全側の異常検知(テーブル不在・列数不一致・列名不正・ID形式不正・
    ID重複・ID欠番)はいずれも AcceptanceTableError を送出する。
    """
    m = re.search(r"^##\s*受け入れ条件\s*$", design_text, flags=re.MULTILINE)
    if not m:
        raise AcceptanceTableError("「## 受け入れ条件」セクションが見つかりません")

    rest = design_text[m.end():]
    next_heading = re.search(r"^#{1,6}\s+\S", rest, flags=re.MULTILINE)
    section = rest[: next_heading.start()] if next_heading else rest

    lines = [line for line in section.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        raise AcceptanceTableError("受け入れ条件テーブルが見つかりません")

    header_cells = split_table_row(lines[0])
    if not is_separator_row(split_table_row(lines[1])):
        raise AcceptanceTableError("受け入れ条件テーブルの区切り行(|---|)がありません")

    if len(header_cells) != 6:
        raise AcceptanceTableError(
            f"受け入れ条件テーブルの列数が6ではありません(実測: {len(header_cells)})"
        )

    keys = []
    for h in header_cells:
        key = _HEADER_ALIASES.get(h.strip())
        if key is None:
            raise AcceptanceTableError(f"受け入れ条件テーブルの列名が不正です: {h!r}")
        keys.append(key)

    rows = []
    seen_ids = set()
    for line in lines[2:]:
        cells = split_table_row(line)
        if len(cells) != 6:
            raise AcceptanceTableError(
                f"受け入れ条件テーブルの列数が行ごとに一致しません: {line!r}"
            )
        row = dict(zip(keys, cells))
        rid = row["id"].strip()
        if not re.fullmatch(r"R-\d+", rid):
            raise AcceptanceTableError(
                f"IDの形式が不正です(R-連番形式が必要): {rid!r}"
            )
        if rid in seen_ids:
            raise AcceptanceTableError(f"IDが重複しています: {rid}")
        seen_ids.add(rid)
        row["id"] = rid
        rows.append(row)

    if not rows:
        raise AcceptanceTableError("受け入れ条件テーブルにデータ行がありません")

    nums = sorted(int(r["id"].split("-", 1)[1]) for r in rows)
    if nums[-1] - nums[0] + 1 != len(nums):
        raise AcceptanceTableError("受け入れ条件テーブルのIDに欠番があります")

    return rows


def resolve_docs_dir(explicit=None):
    """設計書ディレクトリを解決する(spec_gate.py / spec_approve.py で共通)。

    優先順位: 明示引数(--docs) > 環境変数 CLAUDE_SPEC_DOCS(テスト用上書き) >
    CLAUDE_WORK_SCOPE 配下の docs/active > カレントディレクトリの docs/active。
    """
    if explicit:
        return Path(explicit)
    env_docs = os.environ.get("CLAUDE_SPEC_DOCS", "").strip()
    if env_docs:
        return Path(env_docs)
    work_scope = os.environ.get("CLAUDE_WORK_SCOPE", "").strip()
    if work_scope:
        return Path(work_scope) / "docs" / "active"
    return Path("docs") / "active"


def resolve_spec_dir(explicit=None):
    """内部状態ディレクトリ(verdict/audit/approvals/キャッシュ置き場)を解決する。

    優先順位: 明示引数(--spec-dir) > 環境変数 CLAUDE_SPEC_DIR(テスト用上書き) >
    CLAUDE_WORK_SCOPE 配下の .claude/spec > カレントディレクトリの .claude/spec。
    """
    if explicit:
        return Path(explicit)
    env_spec = os.environ.get("CLAUDE_SPEC_DIR", "").strip()
    if env_spec:
        return Path(env_spec)
    work_scope = os.environ.get("CLAUDE_WORK_SCOPE", "").strip()
    if work_scope:
        return Path(work_scope) / ".claude" / "spec"
    return Path(".claude") / "spec"


def repo_state_signature(extra):
    """リポジトリ状態(HEAD + 作業ツリー)を表すハッシュを返す。

    enforce_eval.py / spec_gate.py が「前回PASSから状態が変わっていなければ
    重い再実行をスキップする」キャッシュのキーとして共用する。
    extra にはコマンド文字列など、状態以外にキャッシュを無効化したい
    要素を渡す。git が使えなければ None(キャッシュ無効)。
    """
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, timeout=10,
        ).stdout
    except Exception:
        return None
    if not head:
        return None
    raw = f"{extra}\n{head}\n{status}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
