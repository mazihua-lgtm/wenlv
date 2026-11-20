"""法条核验器：引用必须回官方源踩实，踩不实就不许说。

核验不看模型说了什么，只看官方库里有什么。三道关：
1. 法规本身存在，且处于有效状态；
2. 条号能在官方正文里定位到；
3. 声称的条文原文与官方原文逐字一致。

任何一关不过，这条引用就不能进结论。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from wenlv.corpus.flk import LawRecord, Source

# 条号后面必须跟空白才算新的一条开始。
# 这样"依照本法第六百七十五条的规定"这类引用不会被误切成新条。
_ARTICLE_MARK = re.compile(r"第[一二三四五六七八九十百千零]+条[\u3000 \n]")

_WS = re.compile(r"[\s\u3000]+")


def normalize(text: str) -> str:
    """去掉所有空白再比，避免因换行、全角空格判成不一致。"""
    return _WS.sub("", text or "")


def split_articles(text: str) -> dict[str, str]:
    """把一段连续正文切成 条号 -> 该条正文。"""
    marks = list(_ARTICLE_MARK.finditer(text or ""))
    out: dict[str, str] = {}
    for i, mark in enumerate(marks):
        key = mark.group(0).strip()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[mark.end():end].strip()
        # 同一段里同一条可能出现两次（命中重叠），留正文更全的那份
        if len(body) > len(out.get(key, "")):
            out[key] = body
    return out


class Verdict(str, Enum):
    VERIFIED = "verified"        # 条号对上，原文逐字对上
    EXISTS = "exists"            # 条号对上，但没给原文，已补官方原文
    MISMATCH = "mismatch"        # 条号对上，原文对不上
    NOT_FOUND = "not_found"      # 官方库里定位不到这一条
    LAW_MISSING = "law_missing"  # 找不到这部法规
    LAW_OUTDATED = "law_outdated"  # 法规已废止或已修改
    ERROR = "error"              # 源站异常，不能据此下结论


@dataclass
class Citation:
    law: str          # 如「中华人民共和国民法典」
    article: str      # 如「第六百七十五条」
    text: str = ""    # 声称的条文原文，可空

    def __str__(self) -> str:
        return f"{self.law}{self.article}"


@dataclass
class Result:
    citation: Citation
    verdict: Verdict
    detail: str
    official_text: str = ""
    law: LawRecord | None = None

    @property
    def safe(self) -> bool:
        """能不能拿这条引用去支撑结论。

        只有正文来自官方原文才算数——MISMATCH 意味着模型编了或记错了，
        NOT_FOUND 意味着查无此条，两者都不能用。
        """
        return self.verdict in {Verdict.VERIFIED, Verdict.EXISTS}


def resolve_law(source: Source, name: str) -> LawRecord | None:
    """把法规名匹配到一条官方记录，优先完全同名。"""
    records = source.search_laws(name)
    if not records:
        return None
    for record in records:
        if record.title == name:
            return record
    for record in records:
        if name in record.title or record.title in name:
            return record
    # 检索会返回模糊结果，抓不到同名或包含关系的就一律当查无此法。
    # 接受第一条无关法规，等于拿别的法去核这条引用，是更隐蔽的错误。
    return None


def verify(citation: Citation, source: Source, pages: int = 2) -> Result:
    law = resolve_law(source, citation.law)
    if law is None:
        return Result(citation, Verdict.LAW_MISSING, f"官方库中检索不到《{citation.law}》")

    if not law.effective:
        return Result(
            citation,
            Verdict.LAW_OUTDATED,
            f"《{law.title}》当前状态为「{law.status_label}」，不能作为现行法引用",
            law=law,
        )

    # 先用声称的原文去搜；没有原文就退回用条号搜。
    # 用原文搜是有意的：编造的句子在官方库里根本不存在，一定会搜空。
    queries = [citation.text.strip()] if citation.text.strip() else []
    queries.append(citation.article)

    try:
        chunks: list[str] = []
        for query in queries:
            chunks.extend(source.fetch_hits(law.bbbs, query, pages=pages))
            if _find_article(chunks, citation.article):
                break
    except Exception as exc:  # 源站不可用时的兜底，不能让程序崩在核验上
        return Result(citation, Verdict.ERROR, f"核验源站不可用：{exc}", law=law)

    body = _find_article(chunks, citation.article)
    if body is None:
        return Result(
            citation,
            Verdict.NOT_FOUND,
            f"在《{law.title}》官方正文中定位不到{citation.article}",
            law=law,
        )

    if not citation.text.strip():
        return Result(citation, Verdict.EXISTS, "条号已定位，引用未附原文，以官方原文为准", body, law)

    if normalize(citation.text) in normalize(body):
        return Result(citation, Verdict.VERIFIED, "与官方原文一致", body, law)

    return Result(citation, Verdict.MISMATCH, "声称的原文与官方原文不一致", body, law)


def _find_article(chunks: list[str], article: str) -> str | None:
    for chunk in chunks:
        found = split_articles(chunk).get(article)
        if found:
            return found
    return None
