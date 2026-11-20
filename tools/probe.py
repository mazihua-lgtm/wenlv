"""取条文：按锚点词去官方库捞某部法的正文片段，打印切出的条号。

写清单前用它确认条号和锚点词，避免凭记忆写错。
用法：
    python tools/probe.py 中华人民共和国劳动合同法 "违法解除"
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wenlv.corpus.flk import FlkClient
from wenlv.verify.citation import resolve_law, split_articles


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1

    law_name, query = sys.argv[1], sys.argv[2]
    pages = int(sys.argv[3]) if len(sys.argv) > 3 else 2

    client = FlkClient(timeout=30)
    law = resolve_law(client, law_name)
    if law is None:
        print(f"查不到《{law_name}》")
        return 1

    print(f"《{law.title}》 状态={law.status_label} 施行={law.sxrq} bbbs={law.bbbs}\n")
    seen: set[str] = set()
    for chunk in client.fetch_hits(law.bbbs, query, pages=pages):
        for article, body in split_articles(chunk).items():
            if article in seen:
                continue
            seen.add(article)
            print(f"{article}　{body[:120]}")
    if not seen:
        print("没有切出任何条号，换个锚点词试试")
    return 0


if __name__ == "__main__":
    sys.exit(main())
