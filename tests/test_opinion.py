import unittest
from datetime import date

from wenlv.corpus.flk import LawRecord
from wenlv.model import CaseFile, Certainty, Fact, Issue, LawyerTrigger
from wenlv.report import opinion
from wenlv.report.limitation import assess
from wenlv.verify.citation import Citation, Result, Verdict

LAW = LawRecord(bbbs="x", title="中华人民共和国民法典", sxx="3")


def make_issue(denied: bool = False) -> Issue:
    fact = Fact(
        key="delivery",
        question="钱实际给出去了吗？",
        why="没有交付，借款合同不成立。",
        basis=[{"ref": "民法典第679条", "anchor": "自贷款人提供借款时成立", "quote": ""}],
        evidence=["银行转账流水", "微信转账记录"],
    )
    fact.record(Certainty.DENIED if denied else Certainty.CONFIRMED, "否" if denied else "是")
    return Issue(
        id="t",
        claim="出借人请求返还本金",
        basis=[],
        elements=[fact],
        actions=["整理转账记录", "发书面催告"],
        lawyer_triggers=[LawyerTrigger(when="时效可能已过", fact_key="limitation", status=Certainty.CONFIRMED)],
    )


def ok_result() -> Result:
    return Result(
        Citation(law="中华人民共和国民法典", article="第六百七十九条"),
        Verdict.EXISTS,
        "条号已定位",
        "自然人之间的借款合同，自贷款人提供借款时成立。",
        LAW,
    )


class RejectedTest(unittest.TestCase):
    def test_denial_kills_the_claim(self):
        case = CaseFile()
        issue = make_issue(denied=True)
        case.add(issue)

        text = opinion.build_rejected(issue)
        self.assertIn("不成立", text)
        self.assertIn("钱实际给出去了吗", text)
        # 这条路走不通时，不能再给行动清单
        self.assertNotIn("整理转账记录", text)
        self.assertIn("免责声明", text)

    def test_issue_denials_only_counts_essential(self):
        issue = make_issue(denied=True)
        self.assertEqual(len(issue.denials()), 1)
        issue.elements[0].essential = False
        self.assertEqual(issue.denials(), [])


class BuildTest(unittest.TestCase):
    def test_opinion_has_all_sections(self):
        case = CaseFile()
        case.add(make_issue())
        text = opinion.build(case, [ok_result()])

        for section in ["结论", "时效", "现在要做什么", "需要准备的材料", "什么时候请律师", "免责声明"]:
            self.assertIn(section, text, section)
        self.assertIn("银行转账流水", text)
        self.assertIn("整理转账记录", text)

    def test_failed_citation_blocks_conclusion(self):
        case = CaseFile()
        case.add(make_issue())
        bad = Result(Citation(law="民法典", article="第九条"), Verdict.NOT_FOUND, "查无此条")
        text = opinion.build(case, [bad])
        self.assertIn("本次不出结论", text)

    def test_expired_limitation_forces_lawyer(self):
        case = CaseFile()
        case.add(make_issue())
        a = assess(date(2015, 1, 1), 3, today=date(2026, 11, 20))
        text = opinion.build(case, [ok_result()], a)
        self.assertIn("时效可能已经过了", text)

    def test_urgent_limitation_mentions_days_left(self):
        case = CaseFile()
        case.add(make_issue())
        a = assess(date(2024, 3, 1), 3, today=date(2026, 11, 20))
        text = opinion.build(case, [ok_result()], a)
        self.assertIn(f"只剩 {a.days_left} 天", text)


if __name__ == "__main__":
    unittest.main()
