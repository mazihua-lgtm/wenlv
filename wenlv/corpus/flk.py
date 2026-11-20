"""国家法律法规数据库（flk.npc.gov.cn）读取层。

只做两件事：查法规、取命中正文。

刻意不缓存整库：条文会被修订，一份本地全量库过期后，
会把失效条文当成现行法喂给用户，比查不到更糟。
"""

from __future__ import annotations

import http.cookiejar
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Protocol

BASE = "https://flk.npc.gov.cn"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; wenlv/0.1)",
    "Referer": BASE + "/",
    "Content-Type": "application/json",
}


class _KeepMethodRedirect(urllib.request.HTTPRedirectHandler):
    """跟随重定向时保留原方法和请求体。

    官方库前置了 CDN 的 cookie 挑战：第一次 POST 回 307 并下发 wzws_cid，
    再跳回同一路径。urllib 默认把 POST 重定向降级成 GET（还会丢 body），
    结果就是 307 直接抛异常，整个工具全挂。
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if req.get_method() == "POST":
            return urllib.request.Request(
                newurl,
                data=req.data,
                headers=dict(req.header_items()),
                method="POST",
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# 不走系统代理：官方库本身就是国内直连，串代理只会平白挂死。
# 带 cookie jar 是必须的：CDN 挑战靠它把第一跳的 cookie 带回第二跳。
_COOKIES = http.cookiejar.CookieJar()
_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPCookieProcessor(_COOKIES),
    _KeepMethodRedirect(),
)

# 时效性编码取自官方前端：1 已废止 / 2 已修改 / 3 有效 / 4 尚未生效
SXX_LABELS = {"1": "已废止", "2": "已修改", "3": "有效", "4": "尚未生效"}

_TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(text: str) -> str:
    """官方返回的标题和正文里夹着 <em class='highlight'>，去掉。"""
    return _TAG_RE.sub("", text or "")


@dataclass
class LawRecord:
    bbbs: str
    title: str
    gbrq: str = ""   # 公布日期
    sxrq: str = ""   # 施行日期
    sxx: str = ""    # 时效性
    organ: str = ""  # 制定机关
    kind: str = ""   # 法律性质

    @property
    def effective(self) -> bool:
        return self.sxx == "3"

    @property
    def status_label(self) -> str:
        return SXX_LABELS.get(self.sxx, f"未知编码 {self.sxx!r}")


class Source(Protocol):
    """核验器只依赖这两个动作，测试时可以换成离线假源。"""

    def search_laws(self, name: str) -> list[LawRecord]: ...

    def fetch_hits(self, bbbs: str, query: str, pages: int = 1) -> list[str]: ...


class FlkClient:
    def __init__(self, timeout: float = 20.0, base: str = BASE):
        self.timeout = timeout
        self.base = base.rstrip("/")

    def _request(self, req: urllib.request.Request) -> dict:
        with _OPENER.open(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post(self, path: str, payload: dict) -> dict:
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers=_HEADERS,
            method="POST",
        )
        return self._request(req)

    def _get(self, path: str, params: dict) -> dict:
        url = f"{self.base}{path}?{urllib.parse.urlencode(params)}"
        return self._request(urllib.request.Request(url, headers=_HEADERS))

    def search_laws(self, name: str, size: int = 10) -> list[LawRecord]:
        data = self._post(
            "/law-search/search/list",
            {
                "searchContent": name,
                "searchType": 1,   # 1 按标题，2 按正文
                "searchRange": 1,
                "page": 1,
                "pageSize": size,
            },
        )
        return [
            LawRecord(
                bbbs=row.get("bbbs", ""),
                title=strip_tags(row.get("title", "")),
                gbrq=row.get("gbrq", "") or "",
                sxrq=row.get("sxrq", "") or "",
                sxx=str(row.get("sxx", "") or ""),
                organ=row.get("zdjgName", "") or "",
                kind=row.get("flxz", "") or "",
            )
            for row in (data.get("rows") or [])
        ]

    def fetch_hits(self, bbbs: str, query: str, pages: int = 1) -> list[str]:
        """取指定法规中命中 query 的正文片段。

        返回的是命中点周围的连续正文，一段里通常跨好几条，
        所以调用方要自己按条号切开再比对。
        """
        chunks: list[str] = []
        for page in range(1, max(1, pages) + 1):
            data = self._post(
                "/law-search/search/hitDisplay",
                {
                    "searchContent": query,
                    "searchType": 2,
                    "searchRange": 1,
                    "bbbs": bbbs,
                    "page": page,
                    "pageSize": 10,
                },
            )
            found = (data.get("data") or {}).get("contentHitDisplay") or []
            if not found:
                break
            chunks.extend(strip_tags(c) for c in found)
        return chunks
