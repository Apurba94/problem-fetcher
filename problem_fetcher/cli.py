"""Command-line interface for problem-fetcher."""
import argparse
import json
import os
import sys

from . import parsers
from .model import Problem
from .server import DEFAULT_PORT, make_server
from .workspace import contest_skeleton, expand_indices, scan, write_problem


def _common(p):
    p.add_argument("-d", "--dir", default=".", help="workspace root")
    p.add_argument("-l", "--lang", default="py", help="solution template: py, cpp, java, js (or template.<ext> in --templates)")
    p.add_argument("--templates", help="folder with your own template.<ext> files")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="problem-fetcher", description="Problem workspaces for competitive programming.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("listen", help="receive problems from the Competitive Companion extension")
    l.add_argument("-p", "--port", type=int, default=DEFAULT_PORT)
    l.add_argument("-v", "--verbose", action="store_true")
    _common(l)
    f = sub.add_parser("fetch", help="download and parse a problem page")
    f.add_argument("url")
    _common(f)
    pa = sub.add_parser("parse", help="parse a saved HTML page or a Companion JSON file")
    pa.add_argument("file")
    pa.add_argument("--url", default="", help="original URL (helps detect the judge)")
    pa.add_argument("--print", action="store_true", help="only print the parsed problem as JSON")
    _common(pa)
    c = sub.add_parser("contest", help="create folders for a whole contest")
    c.add_argument("judge", choices=["codeforces", "atcoder", "other"])
    c.add_argument("contest_id")
    c.add_argument("problems", help="e.g. A-F or A,B,C1,C2")
    _common(c)
    ls = sub.add_parser("list", help="list problems in the workspace")
    ls.add_argument("-d", "--dir", default=".")
    args = ap.parse_args(argv)

    if args.cmd == "listen":
        def show(problem, folder):
            print("received %-40s -> %s (%d samples)" % (problem.name[:40], folder, len(problem.samples)), flush=True)
        srv = make_server(args.dir, args.port, args.lang, args.templates, show, args.verbose)
        print("listening on http://127.0.0.1:%d (Ctrl+C to stop)" % args.port, flush=True)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            srv.server_close()
        return 0
    if args.cmd in ("fetch", "parse"):
        try:
            if args.cmd == "fetch":
                problem = parsers.parse_page(parsers.fetch(args.url), args.url)
            elif args.file.endswith(".json"):
                with open(args.file, encoding="utf-8") as fh:
                    problem = Problem.from_companion(json.load(fh))
            else:
                with open(args.file, encoding="utf-8", errors="replace") as fh:
                    problem = parsers.parse_page(fh.read(), args.url)
        except (OSError, ValueError) as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 1
        if getattr(args, "print", False):
            print(problem.to_json())
            return 0
        folder = write_problem(args.dir, problem, args.lang, args.templates)
        print("%s: %d sample(s), %d ms, %d MB -> %s" % (problem.name, len(problem.samples), problem.time_limit_ms,
                                                       problem.memory_limit_mb, folder))
        return 0 if problem.samples else 2
    if args.cmd == "contest":
        folders = contest_skeleton(args.dir, args.judge, args.contest_id, expand_indices(args.problems), args.lang,
                                   args.templates)
        for fd in folders:
            print(fd)
        return 0
    rows = scan(args.dir)
    for folder, p, edited, n in rows:
        print("%-3s %-45s %2d test(s)  %s" % ("*" if edited else "", os.path.relpath(folder, args.dir)[:45], n, p.url))
    print("%d problem(s); * = solution edited" % len(rows))
    return 0
