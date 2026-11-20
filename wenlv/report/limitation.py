"""时效计算。

这里只做加减法，不做判断——时效差一个月，结论就从"还来得及"变成"已过期"，
所以起算日必须由当事人自己给，程序不替他估。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

# 剩余不足这个天数就进入告急状态
URGENT_DAYS = 180

_DATE_PATTERNS = (
    re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$"),
    re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$"),
    re.compile(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})$"),
    re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日?$"),
    re.compile(r"^(\d{4})(\d{2})(\d{2})$"),
)


def parse_date(text: str) -> date | None:
    """解析常见的日期写法，认不出来就返回 None，不猜。"""
    raw = (text or "").strip()
    for pattern in _DATE_PATTERNS:
        match = pattern.match(raw)
        if not match:
            continue
        year, month, day = (int(g) for g in match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def add_years(start: date, years: int) -> date:
    """加年数。2 月 29 日遇到平年，落到 2 月 28 日。"""
    try:
        return start.replace(year=start.year + years)
    except ValueError:
        return start.replace(year=start.year + years, day=28)


@dataclass
class Assessment:
    start: date
    deadline: date
    days_left: int

    @property
    def expired(self) -> bool:
        return self.days_left < 0

    @property
    def urgent(self) -> bool:
        return not self.expired and self.days_left <= URGENT_DAYS

    @property
    def state(self) -> str:
        if self.expired:
            return "expired"
        return "urgent" if self.urgent else "normal"

    def describe(self) -> str:
        if self.expired:
            return (
                f"按你给的起算日 {self.start.isoformat()} 计算，"
                f"时效已于 {self.deadline.isoformat()} 届满（逾期 {-self.days_left} 天）。"
                "对方一旦提出时效抗辩，请求很可能被驳回——但时效中断事由、对方自愿履行都能改变结果，"
                "这件事必须尽快找律师看，不要自己下结论。"
            )
        if self.urgent:
            return (
                f"时效截止日 {self.deadline.isoformat()}，还剩 {self.days_left} 天。"
                "已经进入告急区，起诉或申请仲裁的准备至少需要一个月，现在就该动。"
            )
        return (
            f"时效截止日 {self.deadline.isoformat()}，还剩 {self.days_left} 天，时间还算充裕。"
        )


def assess(start: date, years: int, today: date | None = None) -> Assessment:
    deadline = add_years(start, years)
    now = today or date.today()
    return Assessment(start=start, deadline=deadline, days_left=(deadline - now).days)
