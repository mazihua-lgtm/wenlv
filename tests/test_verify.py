import unittest

from wenlv.corpus.flk import LawRecord
from wenlv.verify.citation import (
    Citation,
    Verdict,
    split_articles,
    verify,
)

# 下面两段正文是从 flk.npc.gov.cn 的 hitDisplay 接口实际取回的官方片段，
# 原样保留（含全角空格），用来测切条和逐字比对。
CHUNK_ART_667 = (
    "第十二章　借款合同"
    "第六百六十七条　借款合同是借款人向贷款人借款，到期返还借款并支付利息的合同。"
    "第六百六十八条　借款合同应当采用书面形式，但是自然人之间借款另有约定的除外。"
)
CHUNK_ART_670 = (
    "第六百七十条　借款的利息不得预先在本金中扣除。"
    "利息预先在本金中扣除的，应当按照实际借款数额返还借款并计算利息。"
    "第六百七十一条　贷款人未按照约定的日期、数额提供借款，造成借款人损失的，应当赔偿损失。"
)

CIVIL_CODE = LawRecord(
    bbbs="ff808081729d1efe01729d50b5c500bf",
    title="中华人民共和国民法典",
    gbrq="2020-05-28",
    sxrq="2021-01-01",
    sxx="3",
)


class FakeSource:
    def __init__(self, laws, chunks):
        self._laws = laws
        self._chunks = chunks
        self.calls = 0

    def search_laws(self, name):
        return self._laws

    def fetch_hits(self, bbbs, query, pages=1):
        self.calls += 1
        return self._chunks


class SplitArticlesTest(unittest.TestCase):
    def test_splits_on_real_official_text(self):
        arts = split_articles(CHUNK_ART_667)
        self.assertIn("第六百六十七条", arts)
        self.assertIn("第六百六十八条", arts)
        self.assertTrue(arts["第六百六十七条"].startswith("借款合同是借款人向贷款人借款"))

    def test_reference_inside_an_article_is_not_a_new_article(self):
        text = (
            "第六百七十五条　借款人应当按照约定的期限返还借款。"
            "对借款期限没有约定或者约定不明确，依据本法第五百一十条的规定仍不能确定的，"
            "借款人可以随时返还。"
        )
        arts = split_articles(text)
        self.assertEqual(list(arts), ["第六百七十五条"])


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.source = FakeSource([CIVIL_CODE], [CHUNK_ART_667, CHUNK_ART_670])

    def test_verbatim_quote_passes(self):
        result = verify(
            Citation(
                law="中华人民共和国民法典",
                article="第六百六十七条",
                text="借款合同是借款人向贷款人借款，到期返还借款并支付利息的合同。",
            ),
            self.source,
        )
        self.assertIs(result.verdict, Verdict.VERIFIED)
        self.assertTrue(result.safe)

    def test_wrong_quote_is_caught_and_official_text_returned(self):
        result = verify(
            Citation(
                law="中华人民共和国民法典",
                article="第六百六十七条",
                text="借款合同是借款人向贷款人借款，到期返还本金和利息的合同。",
            ),
            self.source,
        )
        self.assertIs(result.verdict, Verdict.MISMATCH)
        self.assertFalse(result.safe)
        # 官方原文必须原样带出来，供纠正而不是让模型再猜一次
        self.assertIn("到期返还借款并支付利息", result.official_text)

    def test_article_not_in_official_text(self):
        result = verify(
            Citation(law="中华人民共和国民法典", article="第六百七十五条", text=""),
            self.source,
        )
        self.assertIs(result.verdict, Verdict.NOT_FOUND)
        self.assertFalse(result.safe)

    def test_citation_without_quote_still_gets_official_text(self):
        result = verify(
            Citation(law="中华人民共和国民法典", article="第六百七十条"),
            self.source,
        )
        self.assertIs(result.verdict, Verdict.EXISTS)
        self.assertTrue(result.safe)
        self.assertIn("借款的利息不得预先在本金中扣除", result.official_text)

    def test_unknown_law_is_refused(self):
        result = verify(
            Citation(law="中华人民共和国不存在的法", article="第一条", text="随便什么"),
            self.source,
        )
        self.assertIs(result.verdict, Verdict.LAW_MISSING)
        self.assertFalse(result.safe)

    def test_repealed_law_is_refused(self):
        repealed = LawRecord(bbbs="x", title="中华人民共和国合同法", sxx="1")
        result = verify(
            Citation(law="中华人民共和国合同法", article="第二百零六条", text="借款人应当按照约定的期限返还借款。"),
            FakeSource([repealed], [CHUNK_ART_667]),
        )
        self.assertIs(result.verdict, Verdict.LAW_OUTDATED)
        self.assertFalse(result.safe)
        self.assertIn("已废止", result.detail)

    def test_source_failure_never_counts_as_pass(self):
        class Broken(FakeSource):
            def fetch_hits(self, bbbs, query, pages=1):
                raise OSError("连接超时")

        result = verify(
            Citation(law="中华人民共和国民法典", article="第六百六十七条", text="借款合同"),
            Broken([CIVIL_CODE], []),
        )
        self.assertIs(result.verdict, Verdict.ERROR)
        self.assertFalse(result.safe)


if __name__ == "__main__":
    unittest.main()
