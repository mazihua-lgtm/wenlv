import unittest

from wenlv.model import Certainty, parse_status


class ParseStatusTest(unittest.TestCase):
    def test_unknown_never_read_as_denial(self):
        # 「不清楚」以「不」开头，绝不能被判成「否」。
        for raw in ["不清楚", "不知道", "不确定", "记不清", "说不清", "说不准", "无法确定", "不一定", "忘了"]:
            self.assertIs(parse_status(raw), Certainty.UNKNOWN, raw)

    def test_confirmed(self):
        for raw in ["是", "有", "对", "是，双方都是自然人", "有借条", "yes"]:
            self.assertIs(parse_status(raw), Certainty.CONFIRMED, raw)

    def test_denied(self):
        for raw in ["否", "没有", "不是", "没约定", "无"]:
            self.assertIs(parse_status(raw), Certainty.DENIED, raw)

    def test_first_clause_decides(self):
        self.assertIs(parse_status("是，但我不清楚细节"), Certainty.CONFIRMED)
        self.assertIs(parse_status("不清楚，好像是借的"), Certainty.UNKNOWN)

    def test_noise_falls_back_to_unknown(self):
        for raw in ["", "   ", "?", "大概吧", "可能是借的"]:
            self.assertIs(parse_status(raw), Certainty.UNKNOWN, raw)


if __name__ == "__main__":
    unittest.main()
