"""命令行入口：先问清事实，再核依据，最后给意见。

回答方式：以"是 / 否 / 不清楚"开头，后面可以随便补细节。
"""

from __future__ import annotations

import argparse
import sys

from wenlv.corpus.flk import FlkClient
from wenlv.intake import router
from wenlv.intake.issue_loader import load_all
from wenlv.intake.session import IntakeSession
from wenlv.model import CaseFile, Issue
from wenlv.report import limitation as lim
from wenlv.report import opinion
from wenlv.verify import stage


def list_issues(issues: list[Issue]) -> None:
    for issue in issues:
        print(f"  {issue.id:32} {issue.claim}（{len(issue.elements)} 项要件事实）")


def pick_issue(issues: list[Issue], args) -> Issue | None:
    if args.issue:
        for issue in issues:
            if issue.id == args.issue:
                return issue
        print(f"没有这个案由：{args.issue}\n")
        list_issues(issues)
        return None

    if args.describe:
        text = args.describe
    elif len(issues) == 1:
        return issues[0]
    else:
        print("先说一句你的情况（例如：朋友借钱不还，有借条）：")
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None

    match = router.best(text, issues)
    if match is None:
        print("\n没匹配到确定的案由，请从下面选一个：\n")
        list_issues(issues)
        print("\n例：wenlv --issue private_lending.principal")
        return None

    print(f"匹配到案由：{match.issue.claim}（命中：{'、'.join(match.hits)}）\n")
    return match.issue


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


def ask_limitation(issue: Issue) -> lim.Assessment | None:
    if not issue.limitation:
        return None
    print(f"\n[时效] {issue.limitation.start_prompt or '从哪一天起算？'}")
    print("    （写 2026-05-01 这种格式；不确定就回车跳过，但这一项跳过后意见不完整）")
    try:
        raw = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if not raw:
        return None
    start = lim.parse_date(raw)
    if start is None:
        print("   日期没看懂，已跳过时效计算。")
        return None
    return lim.assess(start, issue.limitation.years)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wenlv",
        description=(
            "先把事实问清，再谈法律。\n\n"
            "说一句案情 → 匹配案由 → 逐项追问 → 事实没查清不出结论\n"
            "→ 法条回国家法律法规数据库核验 → 算时效 → 出意见。"
        ),
        epilog=(
            "示例：\n"
            "  wenlv --describe \"朋友借钱不还，有借条\"\n"
            "  wenlv --issue private_lending.principal\n"
            "  wenlv --list\n\n"
            "回答方式：以「是 / 否 / 不清楚」开头，后面可补充细节。\n"
            "答「不清楚」会继续追问，不会被当成「否」。\n\n"
            "退出码：0 依据成立｜2 事实不够｜3 引用核不实｜4 必备要件不成立"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--no-verify", action="store_true", help="跳过法条核验（跳过时不出结论）")
    parser.add_argument("--issue", help="只检视指定案由，如 private_lending.principal")
    parser.add_argument("--describe", help="用一句话描述案情，自动匹配案由")
    parser.add_argument("--list", action="store_true", help="列出全部案由")
    args = parser.parse_args(argv)

    issues = load_all()
    if not issues:
        print("没有找到检视清单（issues/*.yaml）。")
        return 1

    if args.list:
        list_issues(issues)
        return 0

    issue = pick_issue(issues, args)
    if issue is None:
        return 1

    case = CaseFile()
    case.add(issue)

    session = IntakeSession(case)
    total = len(issue.elements)
    print(f"检视：{issue.claim}")
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

    if issue.denials():
        print()
        print(opinion.build_rejected(issue))
        return 4

    assessment = ask_limitation(issue)

    print("\n进入法条核验。\n")
    if args.no_verify:
        print("已跳过核验，本次不出结论。")
        return 0

    results = stage.verify_case(case, FlkClient())
    print(stage.report(results))

    if not stage.all_safe(results):
        return 3

    print()
    print(opinion.build(case, results, assessment))
    return 0


if __name__ == "__main__":
    sys.exit(main())
