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
from wenlv.model import CaseFile
from wenlv.verify import stage


def main() -> int:
    client = FlkClient(timeout=30)
    case = CaseFile()
    for issue in load_all():
        case.add(issue)

    basis_list = stage.collect_basis(case)
    results = stage.verify_case(case, client)

    for basis, result in zip(basis_list, results):
        mark = "✓" if result.safe else "✗"
        print(f"  {mark} {basis['ref']:14} -> {result.verdict.value:14} {result.detail}")
        if result.safe and result.official_text:
            print(f"      官方: {result.official_text[:60]}")

    passed = sum(r.safe for r in results)
    print(f"\n通过 {passed}/{len(results)}")
    return 0 if stage.all_safe(results) else 1


if __name__ == "__main__":
    sys.exit(main())
