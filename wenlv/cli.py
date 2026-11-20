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
    parser.add_argument("--issue", help="只检视指定案由，如 private_lending.principal")
    parser.add_argument("--list", action="store_true", help="列出全部案由")
    args = parser.parse_args(argv)

    available = load_all()
    if not available:
        print("没有找到检视清单（issues/*.yaml）。")
        return 1

    if args.list:
        for issue in available:
            print(f"{issue.id:32} {issue.claim}（{len(issue.elements)} 项要件事实）")
        return 0

    if args.issue:
        chosen = [i for i in available if i.id == args.issue]
        if not chosen:
            print(f"没有这个案由：{args.issue}\n")
            for issue in available:
                print(f"  {issue.id:32} {issue.claim}")
            return 1
    elif len(available) == 1:
        chosen = available
    else:
        # 一次只检视一个案由：把互不相干的问题混着问，等于什么都没问清
        print("请先用 --issue 选定案由：\n")
        for issue in available:
            print(f"  {issue.id:32} {issue.claim}")
        print("\n例：wenlv --issue private_lending.principal")
        return 1

    case = CaseFile()
    for issue in chosen:
        case.add(issue)

    session = IntakeSession(case)
    total = sum(len(i.elements) for i in chosen)
    print(f"检视：{chosen[0].claim}")
    print(f"共 {total} 项要件事实，回答以「是 / 否 / 不清楚」开头，可在后面补充细节。\n")

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
