"""追问状态机。

规则只有一条：要件事实没查明，就不出意见。
追问只在用户表示"不清楚"时展开；展开完仍不明，如实留作缺口，
既不替用户假设，也不因此跳过。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from wenlv.model import CaseFile, Certainty, Fact, parse_status


@dataclass
class Prompt:
    kind: Literal["fact", "probe"]
    issue_id: str
    fact: Fact
    text: str

    @property
    def tag(self) -> str:
        return "补充追问" if self.kind == "probe" else "待查事实"


class IntakeSession:
    def __init__(self, case: CaseFile):
        self.case = case
        self._probe_cursor: dict[str, int] = {}
        self._exhausted: set[str] = set()

    @staticmethod
    def _key(issue_id: str, fact: Fact) -> str:
        return f"{issue_id}/{fact.key}"

    # ---------- 出题 ----------

    def next_prompt(self) -> Prompt | None:
        """优先把已展开的补充追问问完，再推进下一项要件事实。"""
        for issue in self.case.issues:
            for fact in issue.elements:
                if fact.settled:
                    continue
                cursor = self._probe_cursor.get(self._key(issue.id, fact))
                if cursor is not None and cursor < len(fact.probe):
                    return Prompt("probe", issue.id, fact, fact.probe[cursor])
        for issue in self.case.issues:
            for fact in issue.elements:
                if fact.settled or self._key(issue.id, fact) in self._exhausted:
                    continue
                return Prompt("fact", issue.id, fact, fact.question)
        return None

    # ---------- 收答案 ----------

    def record(self, prompt: Prompt, raw: str, note: str = "") -> None:
        key = self._key(prompt.issue_id, prompt.fact)
        status = parse_status(raw)

        if status is not Certainty.UNKNOWN:
            prompt.fact.record(status, note or raw)
            self._probe_cursor.pop(key, None)
            self._exhausted.discard(key)
            return

        cursor = self._probe_cursor.get(key, 0)
        if prompt.kind == "probe":
            cursor += 1
        if cursor < len(prompt.fact.probe):
            self._probe_cursor[key] = cursor
        else:
            self._exhausted.add(key)
            self._probe_cursor.pop(key, None)

    # ---------- 汇总 ----------

    @property
    def ready(self) -> bool:
        return self.case.ready

    def gaps(self) -> list[str]:
        """未查明的事实，连同"问到哪一步了"一起交出去。"""
        out: list[str] = []
        for issue in self.case.issues:
            for fact in issue.unsettled():
                state = (
                    "已追问到底仍未明确"
                    if self._key(issue.id, fact) in self._exhausted
                    else "尚未询问"
                )
                out.append(f"{issue.claim}｜{fact.question}［{state}］")
        return out

    def progress(self) -> tuple[int, int]:
        total = sum(len(i.elements) for i in self.case.issues)
        settled = sum(1 for i in self.case.issues for f in i.elements if f.settled)
        return settled, total
