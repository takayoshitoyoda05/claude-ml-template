#!/usr/bin/env python3
"""Stop (または --ci): 設計書(docs/active/)の「## 受け入れ条件」テーブルを
唯一の要件ソースとして、実装が全要件を満たしているかを機械検査する。

CLAUDE_SPEC_CHECK=1 のときだけ Stop フックとして動作する(R-112)。
`--ci` を付けると CLAUDE_SPEC_CHECK に関わらず、CIモード(auto要件を全件
再実行、キャッシュ無効)で動作する。

検査項目(1つでも欠ければ exit 2):
  (a) verdict-*.md が全要件IDを網羅し全て PASS か
  (b) auto要件から CLAUDE_SPEC_RECHECK_N 件(既定3、all で全件)を
      抽出して検証コマンドを再実行し、期待結果と照合
  (c) 「対象」列のある要件は coverage で対象モジュールの実行有無を確認
      (coverage 未インストール、または計測データなしなら fail open でスキップ)
  (d) manual要件が approvals.txt で「設計書名 要件ID」として承認済みか
  (e) audit-*.md が存在し全件 OK か

テスト容易性のため、対象ディレクトリは --docs <dir> / 環境変数
CLAUDE_SPEC_DOCS で、内部状態ディレクトリ(verdict/audit/approvals/キャッシュの
置き場)は --spec-dir <dir> / 環境変数 CLAUDE_SPEC_DIR で上書きできる。
"""
import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path

from _common import (
    AcceptanceTableError,
    is_separator_row,
    parse_acceptance_table,
    resolve_docs_dir,
    resolve_spec_dir,
    split_table_row,
)


def parse_id_table(text):
    """先頭列がID(R-連番)の単純なMarkdownテーブルを {ID: [cell, ...]} で返す。

    verdict-*.md / audit-*.md のような内部管理ファイル用の緩いパーサ。
    テーブルが見つからなくても例外にせず空dictを返す(存在チェックは
    呼び出し側で別途行う)。
    """
    lines = [line for line in text.splitlines() if line.strip().startswith("|")]
    result = {}
    if len(lines) < 2:
        return result
    if not is_separator_row(split_table_row(lines[1])):
        return result
    for line in lines[2:]:
        cells = split_table_row(line)
        if not cells:
            continue
        rid = cells[0].strip()
        if re.fullmatch(r"R-\d+", rid):
            result[rid] = cells
    return result


def repo_state_signature(extra):
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


def _files_signature(paths):
    """ファイル群の path:mtime:size を連結した文字列を返す(キャッシュキー用)。

    存在しない・stat失敗のパスは無視する(呼び出し側は事前に対象を絞ってよい)。
    """
    parts = []
    for p in paths:
        try:
            stat = p.stat()
            parts.append(f"{p}:{stat.st_mtime_ns}:{stat.st_size}")
        except OSError:
            continue
    return "|".join(parts)


def spec_dir_signature(spec_dir):
    if not spec_dir.exists():
        return ""
    return _files_signature(sorted(p for p in spec_dir.rglob("*") if p.is_file()))


def docs_dir_signature(design_files):
    return _files_signature(design_files)


def check_verdict(all_rows, spec_dir):
    verdict_map = {}
    for vf in sorted(spec_dir.glob("verdict-*.md")):
        try:
            verdict_map.update(parse_id_table(vf.read_text(encoding="utf-8")))
        except Exception:
            continue
    reasons = []
    for _design_name, row in all_rows:
        rid = row["id"]
        entry = verdict_map.get(rid)
        if entry is None:
            reasons.append(f"{rid}: verdict ファイルに判定がありません")
            continue
        judgement = entry[1].strip().upper() if len(entry) > 1 else ""
        if judgement != "PASS":
            reasons.append(f"{rid}: 判定が PASS ではありません(実際: {judgement or '(空)'})")
    return reasons


def check_manual_approvals(all_rows, spec_dir):
    approvals_file = spec_dir / "approvals.txt"
    lines = []
    if approvals_file.exists():
        lines = approvals_file.read_text(encoding="utf-8").splitlines()
    approved = set()
    for line in lines:
        parts = line.split()
        if len(parts) >= 2:
            approved.add((parts[0], parts[1]))
    reasons = []
    for design_name, row in all_rows:
        if row["type"].strip().lower() != "manual":
            continue
        if (design_name, row["id"]) not in approved:
            reasons.append(f"{row['id']}: manual要件が承認されていません({design_name})")
    return reasons


def check_audit(all_rows, spec_dir):
    audit_map = {}
    for af in sorted(spec_dir.glob("audit-*.md")):
        try:
            audit_map.update(parse_id_table(af.read_text(encoding="utf-8")))
        except Exception:
            continue
    if not audit_map:
        return ["監査ファイル(.claude/spec/audit-*.md)が見つかりません"]
    reasons = []
    for _design_name, row in all_rows:
        rid = row["id"]
        entry = audit_map.get(rid)
        if entry is None:
            reasons.append(f"{rid}: 監査ファイルに結果がありません")
            continue
        result = entry[1].strip().upper() if len(entry) > 1 else ""
        if result != "OK":
            reasons.append(f"{rid}: 監査結果が OK ではありません(実際: {result or '(空)'})")
    return reasons


def check_auto_recheck(all_rows, recheck_n, ci_mode):
    """auto要件を抽出・再実行し、(reasons, ログ文字列) を返す。

    他の check_* と同様に印字はせず戻り値のみで報告する(呼び出し側の main が
    ログ出力する)。ログ文字列には R-108 が検証する実行済みIDの一覧を含める。
    """
    auto_rows = [(d, r) for d, r in all_rows if r["type"].strip().lower() == "auto"]
    if not auto_rows:
        return [], "[spec_gate] auto要件の再実行ID: (対象なし)"

    if ci_mode or str(recheck_n).strip().lower() == "all":
        targets = list(auto_rows)
    else:
        try:
            n = int(recheck_n)
        except ValueError:
            n = 3
        n = max(0, min(n, len(auto_rows)))
        targets = random.sample(auto_rows, n)

    reasons = []
    executed_ids = []
    for _design_name, row in targets:
        rid = row["id"]
        executed_ids.append(rid)
        cmd = row["verify"].strip()
        expected = row["expected"].strip()
        if not cmd:
            continue
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=600,
            )
        except Exception as e:
            reasons.append(f"{rid}: 検証コマンド実行エラー: {e}")
            continue
        m = re.fullmatch(r"exit\s+(\d+)", expected, flags=re.IGNORECASE)
        if m:
            expected_code = int(m.group(1))
            if result.returncode != expected_code:
                reasons.append(
                    f"{rid}: 期待exitコード{expected_code}に対し実際{result.returncode}"
                )
        elif result.returncode != 0:
            reasons.append(f"{rid}: 検証コマンドが失敗しました(exit {result.returncode})")

    log_line = f"[spec_gate] auto要件の再実行ID: {', '.join(executed_ids)}"
    return reasons, log_line


def check_coverage_targets(all_rows):
    targeted = [(d, r) for d, r in all_rows if r.get("target", "").strip()]
    if not targeted:
        return []

    try:
        import coverage
    except ImportError:
        print(
            "[spec_gate] 警告: coverage が未インストールのため対象列の検査をスキップします"
            "(fail open)。",
            file=sys.stderr,
        )
        return []

    cov_file = Path(".coverage")
    if not cov_file.exists():
        print(
            "[spec_gate] 警告: .coverage が見つからないため対象列の検査をスキップします"
            "(fail open)。",
            file=sys.stderr,
        )
        return []

    try:
        cov = coverage.Coverage(data_file=str(cov_file))
        cov.load()
        data = cov.get_data()
        measured = {os.path.normpath(os.path.abspath(f)) for f in data.measured_files()}
    except Exception as e:
        print(
            f"[spec_gate] 警告: coverage データの読み込みに失敗したため対象列の検査を"
            f"スキップします(fail open): {e}",
            file=sys.stderr,
        )
        return []

    reasons = []
    for _design_name, row in targeted:
        target = row["target"].strip()
        target_abs = os.path.normpath(os.path.abspath(target))
        if target_abs not in measured:
            reasons.append(f"{row['id']}: 対象モジュールが実行されていません({target})")
    return reasons


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--docs")
    parser.add_argument("--spec-dir")
    args, _unknown = parser.parse_known_args()

    if not args.ci:
        try:
            data = json.load(sys.stdin)
        except Exception:
            data = {}
        if data.get("stop_hook_active"):
            sys.exit(0)
        if os.environ.get("CLAUDE_SPEC_CHECK", "") != "1":
            sys.exit(0)

    docs_dir = resolve_docs_dir(args.docs)
    spec_dir = resolve_spec_dir(args.spec_dir)

    if not docs_dir.exists():
        sys.exit(0)  # 設計書ディレクトリ不在なら過剰ブロックしない

    design_files = sorted(docs_dir.glob("*.md"))
    if not design_files:
        sys.exit(0)  # 対象設計書0件なら過剰ブロックしない

    recheck_n = os.environ.get("CLAUDE_SPEC_RECHECK_N", "3")

    marker = spec_dir / "last_spec_pass.txt"
    sig = None
    if not args.ci:
        extra = f"{recheck_n}\n{docs_dir_signature(design_files)}\n{spec_dir_signature(spec_dir)}"
        sig = repo_state_signature(extra)
        if sig and marker.exists():
            try:
                if marker.read_text(encoding="utf-8").strip() == sig:
                    sys.exit(0)  # 前回PASSから状態が変わっていない
            except Exception:
                pass

    all_rows = []  # [(design_name, row_dict), ...]
    for f in design_files:
        text = f.read_text(encoding="utf-8")
        try:
            rows = parse_acceptance_table(text)
        except AcceptanceTableError as e:
            print(
                f"[spec_gate] BLOCKED: 受け入れ条件テーブルの異常です({f.name}): {e}",
                file=sys.stderr,
            )
            sys.exit(2)
        design_name = f.stem
        for row in rows:
            all_rows.append((design_name, row))

    reasons = []
    reasons += check_verdict(all_rows, spec_dir)
    auto_reasons, auto_log_line = check_auto_recheck(all_rows, recheck_n, args.ci)
    print(auto_log_line, file=sys.stderr)
    reasons += auto_reasons
    reasons += check_coverage_targets(all_rows)
    reasons += check_manual_approvals(all_rows, spec_dir)
    reasons += check_audit(all_rows, spec_dir)

    if reasons:
        print("[spec_gate] BLOCKED: 以下の受け入れ条件を満たしていません:", file=sys.stderr)
        for r in reasons:
            print(f"  - {r}", file=sys.stderr)
        sys.exit(2)

    if sig:
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(sig, encoding="utf-8")
        except Exception:
            pass

    sys.exit(0)


if __name__ == "__main__":
    main()
