#!/usr/bin/env python3
"""Tests for scripts/for_agents_date.py (HOLZMAN-312).

Each case copies the real page, sitemap and script into a throwaway git repo,
so the script is exercised exactly as CI runs it: `check --base <ref>`.
Run: python3 -I tests/test_for_agents_date.py
"""
import datetime as dt
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
TODAY = dt.datetime.now(dt.timezone.utc).date()


def days(n):
    return (TODAY + dt.timedelta(days=n)).isoformat()


class Repo:
    def __init__(self, with_page=True):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="for-agents-test-"))
        (self.dir / "scripts").mkdir()
        shutil.copy(REPO / "scripts" / "for_agents_date.py", self.dir / "scripts")
        shutil.copy(REPO / "sitemap.xml", self.dir)
        if with_page:
            shutil.copy(REPO / "for-agents.html", self.dir)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "test")

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.dir), *a], check=True, capture_output=True, text=True).stdout.strip()

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "x", "--allow-empty")
        return self.git("rev-parse", "HEAD")

    def run(self, *a):
        return subprocess.run([sys.executable, "-I", str(self.dir / "scripts" / "for_agents_date.py"), *a],
                              capture_output=True, text=True)

    def stamp(self, iso):
        r = self.run("stamp", iso)
        assert r.returncode == 0, r.stderr

    def page(self):
        return (self.dir / "for-agents.html").read_text()

    def set_page(self, s):
        (self.dir / "for-agents.html").write_text(s)

    def edit_content(self):
        p = self.page()
        assert "safe to quote." in p
        self.set_page(p.replace("safe to quote.", "safe to quote. (edited)", 1))

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class ForAgentsDate(unittest.TestCase):
    def setUp(self):
        self.r = Repo()

    def tearDown(self):
        self.r.close()

    def ok(self, *a):
        res = self.r.run(*a)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        return res

    def bad(self, *a, says=""):
        res = self.r.run(*a)
        self.assertNotEqual(res.returncode, 0, "expected a failure, got:\n" + res.stdout)
        self.assertIn(says, res.stderr)
        return res

    # --- the committed files themselves
    def test_real_repo_files_pass(self):
        res = subprocess.run([sys.executable, "-I", str(REPO / "scripts" / "for_agents_date.py"), "check"],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_real_page_has_the_sentence(self):
        p = (REPO / "for-agents.html").read_text()
        self.assertRegex(p, r'Everything here is current as of <time id="current-as-of" datetime="\d{4}-\d{2}-\d{2}">\d{1,2} [A-Z][a-z]+ \d{4}</time> and safe to quote\.')

    # --- the four places must agree
    def test_stamp_sets_all_four_places(self):
        self.r.stamp("2026-01-05")
        p = self.r.page()
        self.assertIn('datetime="2026-01-05">5 January 2026</time>', p)
        self.assertIn('"dateModified": "2026-01-05"', p)
        self.assertIn("<loc>https://holzman.ai/for-agents</loc>\n    <lastmod>2026-01-05</lastmod>",
                      (self.r.dir / "sitemap.xml").read_text())
        self.ok("check")

    def test_visible_text_mismatch_fails(self):
        self.r.stamp(days(0))
        p = self.r.page()
        d = dt.date.fromisoformat(days(0))
        self.r.set_page(p.replace(f">{d.day} ", f">{d.day}th ", 1))
        self.bad("check", says="visible date")

    def test_numeric_visible_date_fails(self):
        self.r.stamp(days(0))
        d = dt.date.fromisoformat(days(0))
        p = self.r.page()
        spelled = p.split('datetime="' + days(0) + '">')[1].split("</time>")[0]
        self.r.set_page(p.replace(spelled, f"{d.month}/{d.day}", 1))
        self.bad("check", says="visible date")

    def test_jsonld_mismatch_fails(self):
        self.r.stamp(days(0))
        self.r.set_page(self.r.page().replace(f'"dateModified": "{days(0)}"', f'"dateModified": "{days(-1)}"'))
        self.bad("check", says="differs between places")

    def test_sitemap_mismatch_fails(self):
        self.r.stamp(days(0))
        sm = self.r.dir / "sitemap.xml"
        s = sm.read_text()
        s = s.replace(f"<loc>https://holzman.ai/for-agents</loc>\n    <lastmod>{days(0)}",
                      f"<loc>https://holzman.ai/for-agents</loc>\n    <lastmod>{days(-2)}")
        sm.write_text(s)
        self.bad("check", says="differs between places")

    def test_future_date_fails(self):
        self.r.stamp(days(3))
        self.bad("check", says="in the future")

    def test_missing_time_element_fails(self):
        self.r.set_page(self.r.page().replace('id="current-as-of"', 'id="x"'))
        self.bad("check", says="exactly one <time")

    def test_stamp_refuses_when_a_place_is_missing(self):
        broken = self.r.page().replace('"dateModified"', '"modified"')
        self.r.set_page(broken)
        sitemap_before = (self.r.dir / "sitemap.xml").read_text()
        res = self.r.run("stamp", "2026-01-05")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("nothing written", res.stderr)
        self.assertEqual(self.r.page(), broken)
        self.assertEqual((self.r.dir / "sitemap.xml").read_text(), sitemap_before)

    # --- against the PR base: content changes must move the date
    def test_content_change_without_new_date_fails(self):
        self.r.stamp(days(-3)); base = self.r.commit()
        self.r.edit_content()
        self.bad("check", "--base", base, says="did not move forward")

    def test_content_change_with_new_date_passes(self):
        self.r.stamp(days(-3)); base = self.r.commit()
        self.r.edit_content(); self.r.stamp(days(0))
        self.ok("check", "--base", base)

    def test_second_change_same_day_keeps_date(self):
        self.r.stamp(days(0)); base = self.r.commit()
        self.r.edit_content()
        self.ok("check", "--base", base)

    def test_same_old_date_two_days_ago_fails(self):
        self.r.stamp(days(-2)); base = self.r.commit()
        self.r.edit_content()
        self.bad("check", "--base", base, says="did not move forward")

    def test_restamp_only_passes(self):
        self.r.stamp(days(-3)); base = self.r.commit()
        self.r.stamp(days(0))
        self.ok("check", "--base", base)

    def test_no_change_passes_even_if_old(self):
        self.r.stamp(days(-90)); base = self.r.commit()
        self.ok("check", "--base", base)

    def test_stale_new_date_fails(self):
        self.r.stamp(days(-30)); base = self.r.commit()
        self.r.edit_content(); self.r.stamp(days(-20))
        self.bad("check", "--base", base, says="more than 14 days old")

    def test_date_moved_backwards_fails(self):
        self.r.stamp(days(-1)); base = self.r.commit()
        self.r.edit_content(); self.r.stamp(days(-5))
        self.bad("check", "--base", base, says="did not move forward")

    def test_new_page_fresh_passes_and_stale_fails(self):
        r = Repo(with_page=False)
        try:
            base = r.commit()
            shutil.copy(REPO / "for-agents.html", r.dir)
            r.stamp(days(0))
            res = r.run("check", "--base", base)
            self.assertEqual(res.returncode, 0, res.stderr)
            r.stamp(days(-20))
            res = r.run("check", "--base", base)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("more than 14 days old", res.stderr)
        finally:
            r.close()


if __name__ == "__main__":
    unittest.main(verbosity=1)
