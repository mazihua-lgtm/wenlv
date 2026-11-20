"""从 YAML 读请求权基础检视清单。

清单里只放"问什么、为什么问、对应哪一条法条"，不放条文原文。
条文原文一律去官方源取并核验，避免把人工转录的错误带进项目。
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from wenlv.model import Certainty, Fact, Issue, LawyerTrigger, Limitation

# 案由清单随包发布，装在 site-packages 里也能读到。
# 曾经把它放在仓库根目录，结果 pip install（非 editable）之后
# 程序报"没有找到检视清单"——别人根本用不起来。
PACKAGE_ISSUES = Path(__file__).resolve().parents[1] / "issues"


def default_dir() -> Path:
    """找案由清单：环境变量 > 当前目录下的 issues（且真有清单）> 包内自带。"""
    if env := os.environ.get("WENLV_ISSUES"):
        return Path(env)
    local = Path.cwd() / "issues"
    # 光看目录存在不行：一个空的 issues/ 目录会把包内清单挡掉，
    # 程序报"没有找到检视清单"，其实是自己遮住了自己。
    if local.is_dir() and any(local.glob("*.yaml")):
        return local
    return PACKAGE_ISSUES


def _basis(raw) -> dict[str, str]:
    """basis 支持字符串简写，也支持 {ref, anchor, quote} 完整写法。"""
    if isinstance(raw, str):
        return {"ref": raw, "anchor": "", "quote": ""}
    return {
        "ref": str(raw.get("ref", "")).strip(),
        "anchor": str(raw.get("anchor", "")).strip(),
        "quote": str(raw.get("quote", "")).strip(),
    }


def _limitation(raw) -> Limitation | None:
    if not raw:
        return None
    return Limitation(
        years=int(raw.get("years", 3)),
        fact_key=str(raw.get("fact", "limitation")).strip(),
        start_prompt=str(raw.get("start_prompt", "")).strip(),
        note=str(raw.get("note", "")).strip(),
    )


def _triggers(raw) -> list[LawyerTrigger]:
    out: list[LawyerTrigger] = []
    for item in raw or []:
        status = item.get("status")
        out.append(
            LawyerTrigger(
                when=str(item.get("when", "")).strip(),
                fact_key=str(item.get("fact", "")).strip(),
                status=Certainty(status) if status else None,
            )
        )
    return out


def load_issue(path: Path) -> Issue:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    elements = [
        Fact(
            key=e["key"],
            question=e["question"].strip(),
            why=e["why"].strip(),
            basis=[_basis(b) for b in (e.get("basis") or [])],
            probe=[p.strip() for p in (e.get("probe") or [])],
            evidence=[s.strip() for s in (e.get("evidence") or [])],
            essential=bool(e.get("essential", True)),
        )
        for e in raw["elements"]
    ]
    return Issue(
        id=raw["id"],
        claim=raw["claim"].strip(),
        basis=[_basis(b) for b in (raw.get("basis") or [])],
        elements=elements,
        limitation=_limitation(raw.get("limitation")),
        lawyer_triggers=_triggers(raw.get("lawyer")),
        keywords=[k.strip() for k in (raw.get("keywords") or [])],
        actions=[a.strip() for a in (raw.get("actions") or [])],
    )


def load_all(directory: Path | None = None) -> list[Issue]:
    folder = directory or default_dir()
    return [load_issue(p) for p in sorted(folder.glob("*.yaml"))]
