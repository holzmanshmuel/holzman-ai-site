#!/usr/bin/env python3
"""Keep the "current as of" date on /for-agents honest (HOLZMAN-312).

The page says "Everything here is current as of <date>". That date lives in
four places, and they must always agree:
  1. <time id="current-as-of" datetime="YYYY-MM-DD"> in for-agents.html
  2. the visible text inside that <time>, spelled out ("15 November 2026")
  3. "dateModified" in the page's JSON-LD
  4. <lastmod> for https://holzman.ai/for-agents in sitemap.xml

  stamp [YYYY-MM-DD]   set all four to the given date (default: today, UTC).
  check [--base REF]   fail if they disagree or the date is in the future.
                       With --base, also fail when the page's content changed
                       since REF but the date did not move forward, or the new
                       date is more than STALE_DAYS old (re-stamp before merge).

CI runs `check --base <the PR base>` on every pull request, so the page cannot
change without its date changing too. Nobody has to remember: CI says no.
"""
import argparse
import datetime as dt
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = "for-agents.html"
SITEMAP = "sitemap.xml"
PAGE_URL = "https://holzman.ai/for-agents"
STALE_DAYS = 14

TIME_RE = re.compile(r'<time id="current-as-of" datetime="(\d{4}-\d{2}-\d{2})">([^<]*)</time>')
LD_RE = re.compile(r'"dateModified": "(\d{4}-\d{2}-\d{2})"')
SITEMAP_RE = re.compile(
    r"(<loc>" + re.escape(PAGE_URL) + r"</loc>\s*<lastmod>)(\d{4}-\d{2}-\d{2})(</lastmod>)"
)
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def spelled(d: dt.date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def parse(iso: str) -> dt.date:
    return dt.date.fromisoformat(iso)


def today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def read_stamps(page: str, sitemap: str):
    """Return (dates found, errors). dates = dict of place -> ISO string."""
    errors, dates = [], {}
    t = TIME_RE.findall(page)
    if len(t) != 1:
        errors.append(f'{PAGE}: expected exactly one <time id="current-as-of" datetime="YYYY-MM-DD">, found {len(t)}')
    else:
        dates["time datetime"] = t[0][0]
        try:
            want = spelled(parse(t[0][0]))
        except ValueError:
            errors.append(f"{PAGE}: datetime {t[0][0]!r} is not a real date")
        else:
            if t[0][1] != want:
                errors.append(f"{PAGE}: visible date {t[0][1]!r} does not match datetime {t[0][0]} (want {want!r})")
    ld = LD_RE.findall(page)
    if len(ld) != 1:
        errors.append(f'{PAGE}: expected exactly one JSON-LD "dateModified", found {len(ld)}')
    else:
        dates["JSON-LD dateModified"] = ld[0]
    sm = SITEMAP_RE.findall(sitemap)
    if len(sm) != 1:
        errors.append(f"{SITEMAP}: expected exactly one <lastmod> for {PAGE_URL}, found {len(sm)}")
    else:
        dates["sitemap lastmod"] = sm[0][1]
    if len(set(dates.values())) > 1:
        errors.append("the date differs between places: " + ", ".join(f"{k}={v}" for k, v in dates.items()))
    return dates, errors


def normalized(page: str) -> str:
    """The page with its own date stamps blanked, to tell content changes apart."""
    page = TIME_RE.sub('<time id="current-as-of" datetime="DATE">DATE</time>', page)
    return LD_RE.sub('"dateModified": "DATE"', page)


def git_show(ref: str, path: str):
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{ref}:{path}"],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def cmd_stamp(args) -> int:
    d = parse(args.date) if args.date else today()
    page_p, sm_p = ROOT / PAGE, ROOT / SITEMAP
    page, sm = page_p.read_text(), sm_p.read_text()
    page, n1 = TIME_RE.subn(f'<time id="current-as-of" datetime="{d.isoformat()}">{spelled(d)}</time>', page)
    page, n2 = LD_RE.subn(f'"dateModified": "{d.isoformat()}"', page)
    sm, n3 = SITEMAP_RE.subn(lambda m: m.group(1) + d.isoformat() + m.group(3), sm)
    if (n1, n2, n3) != (1, 1, 1):
        print(f"stamp: could not find each place exactly once (time {n1}, JSON-LD {n2}, sitemap {n3}); nothing written",
              file=sys.stderr)
        return 1
    page_p.write_text(page)
    sm_p.write_text(sm)
    print(f"stamped {d.isoformat()} ({spelled(d)})")
    return 0


def cmd_check(args) -> int:
    page = (ROOT / PAGE).read_text()
    sm = (ROOT / SITEMAP).read_text()
    dates, errors = read_stamps(page, sm)
    d = None
    if not errors:
        d = parse(next(iter(dates.values())))
        if d > today() + dt.timedelta(days=1):
            errors.append(f"the date {d} is in the future")
    if not errors and args.base:
        old = git_show(args.base, PAGE)
        if old is None:
            if d < today() - dt.timedelta(days=STALE_DAYS):
                errors.append(f"new page, but its date {d} is more than {STALE_DAYS} days old: run `python3 scripts/for_agents_date.py stamp`")
        elif normalized(old) != normalized(page):
            m = TIME_RE.search(old)
            old_d = parse(m.group(1)) if m else None
            if old_d is not None and d <= old_d:
                errors.append(f"{PAGE} changed since {args.base} but its date did not move forward ({old_d} -> {d}): "
                              "run `python3 scripts/for_agents_date.py stamp` and commit")
            elif d < today() - dt.timedelta(days=STALE_DAYS):
                errors.append(f"{PAGE} changed, but its date {d} is more than {STALE_DAYS} days old: re-stamp before merging")
    if errors:
        for e in errors:
            print("FAIL: " + e, file=sys.stderr)
        return 1
    print(f"for-agents date OK: {d} ({spelled(d)})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stamp"); s.add_argument("date", nargs="?")
    c = sub.add_parser("check"); c.add_argument("--base")
    args = ap.parse_args(argv)
    return cmd_stamp(args) if args.cmd == "stamp" else cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
