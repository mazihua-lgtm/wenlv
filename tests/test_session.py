import unittest

from wenlv.intake.session import IntakeSession
from wenlv.model import CaseFile, Certainty, Fact, Issue


def make_issue(probe: list[str]) -> Issue:
    fact = Fact(
        key="agreement",
        question="有没有说过这笔钱是借的？",
        why="没有合意就不是借款关系。",
        basis=["民法典第667条"],
        probe=probe,
    )
    return Issue(id="t.issue", claim="请求返还本金", basis=["民法典第667条"], elements=[fact])


class SessionTest(unittest.TestCase):
    def test_unknown_opens_probes_in_order(self):
        case = CaseFile()
        case.add(make_issue(["有没有借条？", "转账备注写了什么？"]))
        s = IntakeSession(case)

        first = s.next_prompt()
        self.assertEqual(first.kind, "fact")
        s.record(first, "不清楚")

        second = s.next_prompt()
        self.assertEqual(second.kind, "probe")
        self.assertEqual(second.text, "有没有借条？")
        s.record(second, "不清楚")

        self.assertEqual(s.next_prompt().text, "转账备注写了什么？")

    def test_probe_answered_settles_the_fact(self):
        case = CaseFile()
        case.add(make_issue(["有没有借条？"]))
        s = IntakeSession(case)
        s.record(s.next_prompt(), "不清楚")
        s.record(s.next_prompt(), "是有借条")
        self.assertTrue(s.ready)
        self.assertIs(case.issues[0].elements[0].status, Certainty.CONFIRMED)

    def test_exhausted_probes_leave_a_gap_and_block(self):
        case = CaseFile()
        case.add(make_issue(["有没有借条？"]))
        s = IntakeSession(case)
        s.record(s.next_prompt(), "不清楚")
        s.record(s.next_prompt(), "不清楚")

        self.assertIsNone(s.next_prompt())
        self.assertFalse(s.ready)
        self.assertEqual(len(s.gaps()), 1)
        self.assertIn("已追问到底仍未明确", s.gaps()[0])

    def test_fact_without_probes_blocks_immediately(self):
        case = CaseFile()
        case.add(make_issue([]))
        s = IntakeSession(case)
        s.record(s.next_prompt(), "不清楚")
        self.assertIsNone(s.next_prompt())
        self.assertFalse(s.ready)

    def test_all_confirmed_is_ready(self):
        case = CaseFile()
        case.add(make_issue([]))
        s = IntakeSession(case)
        s.record(s.next_prompt(), "是")
        self.assertTrue(s.ready)
        self.assertEqual(s.gaps(), [])


if __name__ == "__main__":
    unittest.main()
