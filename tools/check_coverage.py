"""体检：把 issues/ 里所有引用逐条回官方源核一遍，报通过率。

用法：
    python tools/check_coverage.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wenlv.corpus.flk import FlkClient
from wenlv.intake.issue_loader import load_all
from wenlv.verify.citation import parse_basis, verify


def main() -> int:
    client = FlkClient(timeout=30)
    basis_list: list[str] = []
    for issue in load_all():
        for b in [*issue.basis, *(b for e in issue.elements for b in e.basis)]:
            if b not in basis_list:
                basis_list.append(b)

    passed = 0
    for b in basis_list:
        try:
            result = verify(parse_basis(b), client)
        except Exception as exc:
            print(f"  ✗ {b}  解析/核验异常: {exc}")
            continue
        mark = "✓" if result.safe else "✗"
        passed += result.safe
        print(f"  {mark} {b:16} -> {result.verdict.value:14} {result.detail}")
        if result.safe and result.official_text:
            print(f"      官方: {result.official_text[:60]}")

    print(f"\n通过 {passed}/{len(basis_list)}")
    return 0 if passed == len(basis_list) else 1


if __name__ == "__main__":
    sys.exit(main())
