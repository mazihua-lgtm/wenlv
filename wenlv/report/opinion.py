"""把查明的事实、核验过的依据、时效计算，组织成一份能直接看的咨询意见。

只写三样东西：现在做什么、拿什么去证明、什么时候该找律师。
不写法律分析长篇——那不是当事人要的，也不是这个程序能保证的。
"""

from __future__ import annotations

from wenlv.model import CaseFile, Issue
from wenlv.report.limitation import Assessment
from wenlv.verify.citation import Result

DISCLAIMER = (
    "本意见由程序根据你自述的事实和公开法律文本生成，不构成法律意见，不能替代执业律师。\n"
    "程序无法核实证据真伪，也不了解当地裁判口径和案件全貌。据此作出的决定，风险由你自行承担。"
)

# 与案由无关、但每次都必须做的事
_COMMON_ACTIONS = [
    "把下面列的材料先凑齐、拍清楚、按时间顺序编号存好；拿不出的，记下为什么拿不出。",
    "所有和对方的沟通尽量走能留痕的渠道（微信、短信、邮件），电话沟通后补一条文字确认。",
    "不要在没想清楚之前签任何「和解协议」「放弃权利」类文件，签了很难翻回来。",
]


def _section(title: str) -> str:
    return f"\n【{title}】"


def _evidence_block(issue: Issue) -> list[str]:
    lines: list[str] = []
    for fact in issue.elements:
        if not fact.evidence:
            continue
        lines.append(f"· {fact.question.rstrip('？?')}")
        for item in fact.evidence:
            lines.append(f"    - {item}")
    return lines


def _lawyer_advice(issue: Issue, assessment: Assessment | None) -> list[str]:
    urgent: list[str] = []
    normal: list[str] = []

    if assessment is not None:
        if assessment.expired:
            urgent.append("时效可能已经过了。这件事不要再自己判断，尽快找律师看过错、中断事由和补救空间。")
        elif assessment.urgent:
            urgent.append(f"时效只剩 {assessment.days_left} 天。起诉或仲裁的准备至少要一个月，现在就该找律师。")

    for trigger in issue.lawyer_triggers:
        if trigger.matches(issue):
            urgent.append(trigger.when)

    if not urgent:
        normal.append(
            "目前看事实清楚、时效充裕，可以先按上面的清单自己准备。"
            "但只要对方提出反诉、申请鉴定，或者案子进到开庭阶段，就该找律师。"
        )

    normal.append(
        "以下情形出现任何一条，别拖，直接找律师：对方已经委托律师或已经起诉、"
        "涉及金额超过你能承受的损失、涉及人身自由、或者你反复被要求签看不懂的文件。"
    )
    return urgent + normal


def build_rejected(issue: Issue) -> str:
    """必备要件被否掉时出的意见：明确说这条路走不通，不给行动清单。

    在这种时候还列"怎么起诉"，等于把人往错路上推。
    """
    denials = issue.denials()
    out: list[str] = []
    out.append("=" * 60)
    out.append("咨询意见")
    out.append("=" * 60)
    out.append(_section("结论"))
    out.append(f"请求：{issue.claim}")
    out.append("不成立。以下必备要件已被明确否认，这个请求权基础走不通：")
    for fact in denials:
        out.append(f"  · {fact.question}")
        if fact.answer:
            out.append(f"      你的回答：{fact.answer}")
        out.append(f"      为什么这是硬伤：{fact.why}")

    out.append(_section("现在要做什么"))
    out.append("1. 先别再往这条路上投入时间和钱，尤其不要按这个请求去起诉。")
    out.append("2. 回头看同一件事有没有别的请求权基础可走（比如不是借款而是不当得利、不是违约而是侵权），"
               "这需要换一个案由重新检视。")
    out.append("3. 如果事实是记错了或者后来又想起新情况，把证据找出来再说，不要凭印象改口。")

    out.append(_section("什么时候请律师"))
    out.append("· 现在。要件不成立不等于你没救，往往意味着换错了请求路径，这属于专业判断，别自己试。")

    out.append(_section("免责声明"))
    out.append(DISCLAIMER)
    return "\n".join(out)


def build(
    case: CaseFile,
    results: list[Result],
    assessment: Assessment | None = None,
) -> str:
    issue = case.issues[0]
    ok = [r for r in results if r.safe]
    failed = [r for r in results if not r.safe]

    out: list[str] = []
    out.append("=" * 60)
    out.append("咨询意见")
    out.append("=" * 60)

    # ---- 结论 ----
    out.append(_section("结论"))
    out.append(f"请求：{issue.claim}")
    out.append(
        f"要件事实已查明 {len(issue.elements)}/{len(issue.elements)} 项；"
        f"法条依据 {len(ok)}/{len(results)} 条经官方源核验通过。"
    )
    if failed:
        out.append("以下依据核不实，本次不出结论：")
        for r in failed:
            out.append(f"  - {r.citation}：{r.detail}")
    else:
        out.append("依据部分成立，可以按下面的清单推进。")
        out.append("注意：依据成立不等于能赢。决定结果的是证据，不是法条。")

    # ---- 时效 ----
    out.append(_section("时效"))
    if assessment is None:
        if issue.limitation:
            out.append("你没有提供起算日，时效无法计算。这一项必须补上，它直接决定还来不来得及。")
        else:
            out.append("本类请求没有单独的特别时效，适用三年普通诉讼时效，以你主张的起算日为准。")
    else:
        out.append(assessment.describe())
        if issue.limitation and issue.limitation.note:
            out.append(issue.limitation.note)

    # ---- 现在做什么 ----
    out.append(_section("现在要做什么"))
    n = 0
    for action in issue.actions:
        n += 1
        out.append(f"{n}. {action}")
    for action in _COMMON_ACTIONS:
        n += 1
        out.append(f"{n}. {action}")

    # ---- 材料清单 ----
    out.append(_section("需要准备的材料"))
    evidence = _evidence_block(issue)
    if evidence:
        out.extend(evidence)
    else:
        out.append("（本案由未配置材料清单）")

    # ---- 律师时机 ----
    out.append(_section("什么时候请律师"))
    for line in _lawyer_advice(issue, assessment):
        out.append(f"· {line}")

    # ---- 免责 ----
    out.append(_section("免责声明"))
    out.append(DISCLAIMER)
    return "\n".join(out)
