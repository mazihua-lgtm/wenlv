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

_DIGITS = "零一二三四五六七八九"
_UNITS = ["", "十", "百", "千"]


def to_chinese_number(n: int) -> str:
    """把阿拉伯数字转成法条里的中文写法：667 -> 六百六十七。

    官方正文一律用中文数字，清单里写「第667条」方便人读，
    转换这一步是硬需求，转错了整条引用就核不上。
    """
    if n <= 0:
        raise ValueError(f"条号必须是正整数：{n}")

    groups: list[int] = []
    while n:
        groups.append(n % 10)
        n //= 10
    if len(groups) > 4:
        raise ValueError("暂不支持万以上的条号")

    out: list[str] = []
    zero_pending = False
    for pos in range(len(groups) - 1, -1, -1):
        digit = groups[pos]
        if digit == 0:
            zero_pending = bool(out)
            continue
        if zero_pending:
            out.append("零")
            zero_pending = False
        out.append(_DIGITS[digit] + _UNITS[pos])

    text = "".join(out)
    # 十一、十二 这类不写「一十」
    return text[1:] if text.startswith("一十") else text


_BASIS_RE = re.compile(r"^(?P<law>.*?)第(?P<num>\d+)条$")


def parse_citation(ref: str, anchor: str = "", quote: str = "") -> Citation:
    """解析一条引用，如「民法典第667条」或「民法典第六百六十七条」。

    anchor 是条文里的特征词，用来让官方检索稳定命中——官方按条号检索
    会漏条（命中窗口按数字切碎），按特征词检索一次就中。
    """
    raw = ref.strip()
    match = _BASIS_RE.match(raw)
    if not match:
        raise ValueError(f"引用格式应为「法规名第N条」：{ref!r}")

    law = match.group("law").strip()
    if not law.startswith("中华人民共和国"):
        law = "中华人民共和国" + law
    article = f"第{to_chinese_number(int(match.group('num')))}条"
    return Citation(law=law, article=article, anchor=anchor.strip(), text=quote.strip())


def parse_basis(basis: str) -> Citation:
    """兼容旧写法的简写入口。"""
    return parse_citation(basis)


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
    anchor: str = ""  # 条文特征词，用于稳定检索，可空

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

    # 检索顺序：特征词 > 声称的原文 > 条号。
    # 特征词最稳；用声称的原文搜是有意的——编造的句子在官方库里根本不存在，
    # 一定会搜空；条号兜底最弱，官方按条号检索会漏条。
    queries = [q for q in (citation.anchor.strip(), citation.text.strip(), citation.article) if q]

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
