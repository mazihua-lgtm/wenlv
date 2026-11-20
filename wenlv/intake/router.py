"""按用户描述匹配案由。

纯关键词打分，不调模型。理由很简单：路由错了，后面问的每一个问题都是错的；
这种环节必须可预测、可解释，不能交给概率。
"""

from __future__ import annotations

from dataclasses import dataclass

from wenlv.model import Issue


@dataclass
class Match:
    issue: Issue
    score: int
    hits: list[str]


def route(text: str, issues: list[Issue]) -> list[Match]:
    """按命中关键词数量排序，同分的保持原顺序。"""
    body = text or ""
    matches: list[Match] = []
    for issue in issues:
        hits = [k for k in issue.keywords if k and k in body]
        matches.append(Match(issue=issue, score=len(hits), hits=hits))
    return sorted(matches, key=lambda m: -m.score)


def best(text: str, issues: list[Issue]) -> Match | None:
    """唯一最高分才算匹配上；最高分并列或全零，一律返回 None，让用户自己选。"""
    ranked = route(text, issues)
    if not ranked or ranked[0].score == 0:
        return None
    if len(ranked) > 1 and ranked[1].score == ranked[0].score:
        return None
    return ranked[0]
