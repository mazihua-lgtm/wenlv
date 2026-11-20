"""命令行入口：先把事实问清，再谈法律。

回答方式：以"是 / 否 / 不清楚"开头，后面可以随便补细节。
"""

from __future__ import annotations

import sys

from wenlv.intake.issue_loader import load_all
from wenlv.intake.session import IntakeSession
from wenlv.model import CaseFile


def main() -> int:
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

    settled, total = session.progress()
    print("=" * 40)
    print(f"已查明 {settled}/{total} 项。")

    if session.ready:
        print("事实已经够了，可以进入法律检索和出具意见。")
        return 0

    print("事实还不够，以下缺口必须先补，否则任何结论都不可靠：")
    for gap in session.gaps():
        print(f"  - {gap}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
