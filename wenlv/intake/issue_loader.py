"""从 YAML 读请求权基础检视清单。

清单里只放"问什么、为什么问、对应哪一条法条"，不放条文原文。
条文原文一律去官方源取并核验，避免把人工转录的错误带进项目。
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from wenlv.model import Fact, Issue


def default_dir() -> Path:
    """找 issues 目录：环境变量 > 仓库根 > 当前目录。"""
    if env := os.environ.get("WENLV_ISSUES"):
        return Path(env)
    repo = Path(__file__).resolve().parents[2] / "issues"
    if repo.is_dir():
        return repo
    return Path.cwd() / "issues"


def _basis(raw) -> dict[str, str]:
    """basis 支持字符串简写，也支持 {ref, anchor, quote} 完整写法。"""
    if isinstance(raw, str):
        return {"ref": raw, "anchor": "", "quote": ""}
    return {
        "ref": str(raw.get("ref", "")).strip(),
        "anchor": str(raw.get("anchor", "")).strip(),
        "quote": str(raw.get("quote", "")).strip(),
    }


def load_issue(path: Path) -> Issue:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    elements = [
        Fact(
            key=e["key"],
            question=e["question"].strip(),
            why=e["why"].strip(),
            basis=[_basis(b) for b in (e.get("basis") or [])],
            probe=[p.strip() for p in (e.get("probe") or [])],
        )
        for e in raw["elements"]
    ]
    return Issue(
        id=raw["id"],
        claim=raw["claim"].strip(),
        basis=[_basis(b) for b in (raw.get("basis") or [])],
        elements=elements,
    )


def load_all(directory: Path | None = None) -> list[Issue]:
    folder = directory or default_dir()
    return [load_issue(p) for p in sorted(folder.glob("*.yaml"))]
