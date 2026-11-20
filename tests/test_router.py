import unittest

from wenlv.intake import router
from wenlv.model import Fact, Issue


def issue(id_, keywords, claim="请求"):
    return Issue(
        id=id_,
        claim=claim,
        basis=[],
        elements=[Fact(key="k", question="问？", why="因为。")],
        keywords=keywords,
    )


LAWSUITS = [
    issue("lending", ["借钱", "借款", "借条"], "返还借款"),
    issue("traffic", ["车祸", "交通事故", "被撞"], "赔偿损失"),
]


class RouteTest(unittest.TestCase):
    def test_picks_by_keyword_hits(self):
        match = router.best("朋友借钱不还，有借条", LAWSUITS)
        self.assertIsNotNone(match)
        self.assertEqual(match.issue.id, "lending")
        self.assertIn("借条", match.hits)

    def test_no_hit_returns_none(self):
        self.assertIsNone(router.best("我今天心情不好", LAWSUITS))

    def test_tie_returns_none(self):
        tied = [
            issue("a", ["欠钱"]),
            issue("b", ["欠钱"]),
        ]
        self.assertIsNone(router.best("他欠钱不还", tied))

    def test_empty_text(self):
        self.assertIsNone(router.best("", LAWSUITS))

    def test_ranking_is_ordered(self):
        ranked = router.route("借钱 车祸", LAWSUITS)
        self.assertEqual({m.score for m in ranked}, {1})


if __name__ == "__main__":
    unittest.main()
