"""案由清单的查找顺序。

这几个用例守的是一个真事故：清单原来放在仓库根目录，
pip install（非 editable）之后程序报"没有找到检视清单"，
别人装完根本用不起来。
"""

import os
import tempfile
import unittest
from pathlib import Path

from wenlv.intake.issue_loader import PACKAGE_ISSUES, default_dir, load_all


class DefaultDirTest(unittest.TestCase):
    def test_package_issues_are_shipped(self):
        self.assertTrue(PACKAGE_ISSUES.is_dir())
        self.assertTrue(list(PACKAGE_ISSUES.glob("*.yaml")))

    def test_falls_back_to_package_when_cwd_has_none(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                self.assertEqual(default_dir(), PACKAGE_ISSUES)
                self.assertGreaterEqual(len(load_all()), 5)
            finally:
                os.chdir(cwd)

    def test_empty_issues_dir_does_not_shadow_package(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "issues").mkdir()
            os.chdir(tmp)
            try:
                self.assertEqual(default_dir(), PACKAGE_ISSUES)
            finally:
                os.chdir(cwd)

    def test_local_issues_dir_wins_when_it_has_files(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp, "issues")
            local.mkdir()
            (local / "x.yaml").write_text("id: x\nclaim: y\nelements: []\n", encoding="utf-8")
            os.chdir(tmp)
            try:
                # Path.cwd() 在 macOS 上会解析成 /private/var/...，比之前先归一化
                self.assertEqual(default_dir().resolve(), local.resolve())
            finally:
                os.chdir(cwd)

    def test_env_var_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["WENLV_ISSUES"] = tmp
            try:
                self.assertEqual(default_dir().resolve(), Path(tmp).resolve())
            finally:
                del os.environ["WENLV_ISSUES"]


if __name__ == "__main__":
    unittest.main()
