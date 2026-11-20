"""命令行入口：先把事实问清，再核依据，最后才谈法律。

回答方式：以"是 / 否 / 不清楚"开头，后面可以随便补细节。
"""

from __future__ import annotations

import argparse
import sys

from wenlv.corpus.flk import FlkClient
from wenlv.intake.issue_loader import load_all
from wenlv.intake.session import IntakeSession
from wenlv.model import CaseFile
from wenlv.verify import stage


def run_intake(session: IntakeSession, total: int) -> None:
    while (prompt := session.next_prompt()) is not None:
        settled, _ = session.progress()
        print(f"[{prompt.tag} · {settled}/{total}] {prompt.text}")
        print(f"    为什么问：{prompt.fact.why}")
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if raw in {"quit", "exit", "退出"}:
            break
        session.record(prompt, raw)
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wenlv", description="先把事实问清，再谈法律"
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="跳过法条核验（离线调试用，跳过时不会给出结论）",
    )
    args = parser.parse_args(argv)

    issues = load_all()
    if not issues:
        print("没有找到检视清单（issues/*.yaml）。")
        return 1

    case = CaseFile()
    for issue in issues:
        case.add(issue)

    session = IntakeSession(case)
    total = sum(len(i.elements) for i in issues)
    print(f"按 {len(issues)} 个请求权基础检视，共 {total} 项要件事实。")
    print("回答以「是 / 否 / 不清楚」开头，可在后面补充细节。\n")

    run_intake(session, total)

    settled, total = session.progress()
    print("=" * 60)
    print(f"已查明 {settled}/{total} 项。")

    if not session.ready:
        print("事实还不够，以下缺口必须先补，否则任何结论都不可靠：")
        for gap in session.gaps():
            print(f"  - {gap}")
        return 2

    print("事实已经够了，进入法条核验。\n")
    if args.no_verify:
        print("已跳过核验，本次不给出结论。")
        return 0

    results = stage.verify_case(case, FlkClient())
    print(stage.report(results))

    if not stage.all_safe(results):
        return 3

    print("\n下一步：依据成立，可以进入行动清单和律师介入时机的判断。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
