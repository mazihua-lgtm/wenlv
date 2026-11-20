"""核心数据模型。

本项目的判断链条是：请求权基础 -> 构成要件 -> 要件事实 -> 证据。
任何一层没坐实，就不往下给结论。模型只用这三个对象表达，不做别的。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Certainty(str, Enum):
    """一项要件事实的查明状态。

    只有 CONFIRMED / DENIED 算查明；UNKNOWN 一律视为未查明，
    未查明的事实数量直接决定能不能出意见。
    """

    CONFIRMED = "confirmed"
    DENIED = "denied"
    UNKNOWN = "unknown"


# 「不清楚」必须优先于「不」被识别。
# 曾经因为只看开头一个字，把"不清楚"判成了"否"——那是把不知道当成否认，
# 这个项目里最不能犯的错误，保留这段注释防止再犯。
_UNKNOWN_MARKERS = (
    "不清楚",
    "不知道",
    "不确定",
    "记不清",
    "说不清",
    "说不准",
    "记不住",
    "无法确定",
    "无法判断",
    "不一定",
    "不明",
    "忘了",
    "记不得",
)

_SPLIT_CHARS = "，,、。；;.!！?？\n"


def parse_status(raw: str) -> Certainty:
    """把用户的一行回答解析成查明状态。

    只看回答的第一个分句（到标点为止），避免"是，但我不清楚细节"
    被后半句的"不清楚"带偏。任何拿不准的输入一律回 UNKNOWN，不猜。
    """
    text = raw.strip()
    if not text:
        return Certainty.UNKNOWN

    head = re.split(f"[{re.escape(_SPLIT_CHARS)}]", text, maxsplit=1)[0].strip().lower()
    if not head:
        return Certainty.UNKNOWN

    if any(m in head for m in _UNKNOWN_MARKERS):
        return Certainty.UNKNOWN
    if head.startswith(("是", "有", "对", "y", "yes")):
        return Certainty.CONFIRMED
    if head.startswith(("不", "没", "否", "无", "n", "no")):
        return Certainty.DENIED
    if any(m in text for m in _UNKNOWN_MARKERS):
        return Certainty.UNKNOWN
    return Certainty.UNKNOWN


@dataclass
class Fact:
    """一项要件事实。question 是必须问到用户的问题，why 是问它的理由。"""

    key: str
    question: str
    why: str
    basis: list[str] = field(default_factory=list)
    probe: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    essential: bool = True
    status: Certainty = Certainty.UNKNOWN
    answer: str = ""

    @property
    def settled(self) -> bool:
        return self.status is not Certainty.UNKNOWN

    def record(self, status: Certainty, answer: str = "") -> None:
        self.status = status
        self.answer = answer.strip()


@dataclass
class Limitation:
    """诉讼时效或仲裁时效。

    起算日必须由当事人给出，程序不替他估——起算点差一个月，
    结论就可能从"还来得及"变成"已过期"。
    """

    years: int
    fact_key: str
    start_prompt: str
    note: str = ""


@dataclass
class LawyerTrigger:
    """什么情况下必须找律师。条件写成对某项要件事实的回答。"""

    when: str
    fact_key: str = ""
    status: Certainty | None = None

    def matches(self, issue: "Issue") -> bool:
        if not self.fact_key:
            return False
        try:
            fact = issue.fact(self.fact_key)
        except KeyError:
            return False
        return fact.settled and fact.status is self.status


@dataclass
class Issue:
    """一个请求权基础的检视单元。

    例：出借人请求借款人返还借款本金，请求权基础是民法典第667、675条，
    构成要件拆成合意、交付、期限、时效等若干要件事实。
    """

    id: str
    claim: str
    basis: list[str]
    elements: list[Fact]
    limitation: Limitation | None = None
    lawyer_triggers: list[LawyerTrigger] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)

    def unsettled(self) -> list[Fact]:
        return [f for f in self.elements if not f.settled]

    def denials(self) -> list[Fact]:
        """被明确否掉的必备要件。

        要件不成立，请求权就不成立——这时候再核法条、再谈怎么起诉，
        都是把人往错路上带。
        """
        return [f for f in self.elements if f.essential and f.status is Certainty.DENIED]

    @property
    def ready(self) -> bool:
        return not self.unsettled()

    def fact(self, key: str) -> Fact:
        for f in self.elements:
            if f.key == key:
                return f
        raise KeyError(key)


@dataclass
class CaseFile:
    """一次咨询的全部材料。

    设计上刻意不存"结论"，只存查明的事实和检索到的依据——
    结论每次都从这两样东西重新推出来，避免把上一轮的错误结论当事实沿用。
    """

    issues: list[Issue] = field(default_factory=list)
    narrative: str = ""

    def add(self, issue: Issue) -> None:
        self.issues.append(issue)

    @property
    def ready(self) -> bool:
        return all(i.ready for i in self.issues)

    def gaps(self) -> list[tuple[str, Fact]]:
        return [(i.id, f) for i in self.issues for f in i.unsettled()]
