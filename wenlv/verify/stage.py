"""把核验接进主流程：事实齐了之后，逐条回官方源核引用。

结论能不能出，取决于这里有没有全过。没有"大部分通过所以差不多"这种说法。
"""

from __future__ import annotations

from wenlv.corpus.flk import Source
from wenlv.model import CaseFile
from wenlv.verify.citation import Citation, Result, Verdict, parse_citation, verify

Basis = dict[str, str] | str


def as_basis(raw: Basis) -> dict[str, str]:
    """统一 basis 写法：老版本写字符串，新版本写 {ref, anchor, quote}。"""
    if isinstance(raw, str):
        return {"ref": raw, "anchor": "", "quote": ""}
    return {
        "ref": str(raw.get("ref", "")),
        "anchor": str(raw.get("anchor", "")),
        "quote": str(raw.get("quote", "")),
    }


def collect_basis(case: CaseFile) -> list[dict[str, str]]:
    """按出现顺序去重收集全部法条指针。"""
    seen: list[dict[str, str]] = []
    for issue in case.issues:
        for raw in [*issue.basis, *(b for e in issue.elements for b in e.basis)]:
            basis = as_basis(raw)
            if basis not in seen:
                seen.append(basis)
    return seen


def verify_case(case: CaseFile, source: Source) -> list[Result]:
    results: list[Result] = []
    for basis in collect_basis(case):
        try:
            citation = parse_citation(basis["ref"], basis["anchor"], basis["quote"])
        except ValueError as exc:
            # 写错的指针和核不实的引用一样，都不能算数
            results.append(
                Result(
                    Citation(law=basis["ref"], article="?"),
                    Verdict.ERROR,
                    f"引用格式错误：{exc}",
                )
            )
            continue
        results.append(verify(citation, source))
    return results


def all_safe(results: list[Result]) -> bool:
    return bool(results) and all(r.safe for r in results)


def report(results: list[Result]) -> str:
    if not results:
        return "没有任何法条依据，无法出具意见。"

    lines: list[str] = []
    for r in results:
        lines.append(f"  [{'通过' if r.safe else '不通过'}] {r.citation} — {r.detail}")
        if r.safe and r.official_text:
            lines.append(f"          官方原文：{r.official_text[:70]}")

    ok = sum(r.safe for r in results)
    lines.append("")
    lines.append(f"核验通过 {ok}/{len(results)} 条。")
    if ok == len(results):
        lines.append("全部引用可回到官方源，依据部分成立。")
    else:
        lines.append("存在核不实的引用，本次不出结论——宁可不说，不能说错。")
    return "\n".join(lines)
