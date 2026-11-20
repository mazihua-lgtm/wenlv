import unittest

from wenlv.corpus.flk import LawRecord
from wenlv.intake.session import IntakeSession
from wenlv.model import CaseFile, Fact, Issue
from wenlv.verify import stage
from wenlv.verify.citation import parse_basis, to_chinese_number


class ChineseNumberTest(unittest.TestCase):
    def test_covers_article_numbering(self):
        cases = {
            1: "一",
            10: "十",
            11: "十一",
            20: "二十",
            21: "二十一",
            100: "一百",
            101: "一百零一",
            110: "一百一十",
            188: "一百八十八",
            667: "六百六十七",
            670: "六百七十",
            675: "六百七十五",
            1001: "一千零一",
            1260: "一千二百六十",
        }
        for n, want in cases.items():
            self.assertEqual(to_chinese_number(n), want, n)

    def test_rejects_non_positive(self):
        for n in [0, -1]:
            with self.assertRaises(ValueError):
                to_chinese_number(n)


class ParseBasisTest(unittest.TestCase):
    def test_short_name_gets_full_title(self):
        c = parse_basis("民法典第667条")
        self.assertEqual(c.law, "中华人民共和国民法典")
        self.assertEqual(c.article, "第六百六十七条")

    def test_full_name_kept(self):
        c = parse_basis("中华人民共和国劳动合同法第87条")
        self.assertEqual(c.law, "中华人民共和国劳动合同法")
        self.assertEqual(c.article, "第八十七条")

    def test_bad_format_raises(self):
        for bad in ["民法典", "民法典六百六十七条", ""]:
            with self.assertRaises(ValueError, msg=bad):
                parse_basis(bad)


class FakeSource:
    def __init__(self, chunks, law_title="中华人民共和国民法典"):
        self.law = LawRecord(bbbs="x", title=law_title, sxx="3")
        self.chunks = chunks

    def search_laws(self, name):
        return [self.law]

    def fetch_hits(self, bbbs, query, pages=1):
        return self.chunks


def make_case(basis: list[str], settled: bool = True) -> CaseFile:
    fact = Fact(key="k", question="问？", why="因为。", basis=basis)
    if settled:
        fact.record(parse_status_stub(), "是")
    case = CaseFile()
    case.add(Issue(id="t", claim="请求", basis=basis, elements=[fact]))
    return case


def parse_status_stub():
    from wenlv.model import Certainty

    return Certainty.CONFIRMED


class StageTest(unittest.TestCase):
    def test_collect_dedupes_in_order(self):
        case = make_case(["民法典第667条", "民法典第675条"])
        case.issues[0].elements[0].basis = ["民法典第675条", "民法典第679条"]
        refs = [b["ref"] for b in stage.collect_basis(case)]
        self.assertEqual(refs, ["民法典第667条", "民法典第675条", "民法典第679条"])

    def test_collect_keeps_anchor_distinct(self):
        case = make_case(
            [
                {"ref": "民法典第667条", "anchor": "借款合同是借款人向贷款人借款"},
                {"ref": "民法典第667条", "anchor": "另一个锚点"},
            ]
        )
        self.assertEqual(len(stage.collect_basis(case)), 2)

    def test_anchor_is_used_as_lookup_query(self):
        class Recording(FakeSource):
            def __init__(self):
                super().__init__(["第六百八十条\u3000禁止高利放贷，借款的利率不得违反国家有关规定。"])
                self.queries = []

            def fetch_hits(self, bbbs, query, pages=1):
                self.queries.append(query)
                return self.chunks

        source = Recording()
        case = make_case([{"ref": "民法典第680条", "anchor": "禁止高利放贷"}])
        results = stage.verify_case(case, source)
        self.assertTrue(results[0].safe)
        self.assertEqual(source.queries[0], "禁止高利放贷")

    def test_all_safe_requires_every_citation(self):
        source = FakeSource(["第六百六十七条　借款合同是借款人向贷款人借款的合同。"])
        case = make_case(["民法典第667条", "民法典第9999条"])
        results = stage.verify_case(case, source)
        self.assertFalse(stage.all_safe(results))
        self.assertIn("不通过", stage.report(results))
        self.assertIn("本次不出结论", stage.report(results))

    def test_empty_results_never_safe(self):
        self.assertFalse(stage.all_safe([]))

    def test_bad_pointer_counts_as_failure(self):
        case = make_case(["民法典六百六十七条"])
        results = stage.verify_case(case, FakeSource([]))
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].safe)
        self.assertIn("格式错误", results[0].detail)


if __name__ == "__main__":
    unittest.main()
