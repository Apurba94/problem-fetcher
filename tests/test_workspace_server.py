import io
import json
import os
import tempfile
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr, redirect_stdout

from problem_fetcher.cli import main
from problem_fetcher.model import Problem, Sample
from problem_fetcher.server import serve_in_background
from problem_fetcher.workspace import (contest_skeleton, expand_indices, problem_dir, render_template, scan,
                                       write_problem)

from .fixtures import CODEFORCES, COMPANION


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.p = Problem.from_companion(COMPANION)

    def tearDown(self):
        self.tmp.cleanup()

    def test_write_problem_layout(self):
        d = write_problem(self.root, self.p, "cpp")
        self.assertEqual(d, os.path.join(self.root, "codeforces", "2061", "c-binary-string-cutting"))
        self.assertEqual(sorted(os.listdir(os.path.join(d, "tests"))), ["1.in", "1.out", "2.in", "2.out"])
        with open(os.path.join(d, "solution.cpp")) as fh:
            src = fh.read()
        self.assertIn("// https://codeforces.com/contest/2061/problem/C", src)
        self.assertIn("int main() {", src)
        with open(os.path.join(d, "README.md")) as fh:
            self.assertIn("Time limit: 2000 ms, memory limit: 256 MB", fh.read())
        with open(os.path.join(d, "problem.json")) as fh:
            self.assertEqual(Problem.from_dict(json.load(fh)), self.p)

    def test_solution_never_overwritten_and_custom_template(self):
        d = write_problem(self.root, self.p)
        sol = os.path.join(d, "solution.py")
        with open(sol, "w") as fh:
            fh.write("my work")
        write_problem(self.root, self.p)
        with open(sol) as fh:
            self.assertEqual(fh.read(), "my work")
        tdir = os.path.join(self.root, "tpl")
        os.makedirs(tdir)
        with open(os.path.join(tdir, "template.rs"), "w") as fh:
            fh.write("// {name} TL={time_limit}\nfn main() {{}}\n")
        d2 = write_problem(os.path.join(self.root, "w2"), self.p, "rs", tdir)
        with open(os.path.join(d2, "solution.rs")) as fh:
            self.assertEqual(fh.read(), "// C. Binary String Cutting TL=2000\nfn main() {}\n")
        with self.assertRaises(ValueError):
            write_problem(self.root, self.p, "brainfuck")

    def test_contest_skeleton_and_scan(self):
        self.assertEqual(expand_indices("A-D,E1,E2"), ["A", "B", "C", "D", "E1", "E2"])
        self.assertEqual(expand_indices("1-3"), ["1", "2", "3"])
        folders = contest_skeleton(self.root, "atcoder", "abc300", ["A", "B"])
        self.assertTrue(all(os.path.isdir(f) for f in folders))
        with open(os.path.join(folders[0], "problem.json")) as fh:
            self.assertEqual(json.load(fh)["url"], "https://atcoder.jp/contests/abc300/tasks/abc300_a")
        with open(os.path.join(folders[1], "solution.py"), "a") as fh:
            fh.write("\n".join("x = %d" % i for i in range(30)))
        rows = scan(self.root)
        self.assertEqual([edited for _, _, edited, _ in rows], [False, True])

    def test_readme_sections(self):
        p = Problem("B. Guess", "https://x", judge="codeforces", interactive=True, statement="Find x.",
                    input_spec="n", output_spec="answer", tags=["binary search"], samples=[Sample("1\n", "2\n")])
        d = write_problem(self.root, p)
        with open(os.path.join(d, "README.md")) as fh:
            text = fh.read()
        for frag in ("# B. Guess", "**interactive**", "Tags: binary search", "## Statement\n\nFind x.", "## Sample 1"):
            self.assertIn(frag, text)

    def test_render_template(self):
        p = Problem("Name", "u", time_limit_ms=1500)
        self.assertEqual(render_template("{name}|{url}|{time_limit}", p), "Name|u|1500")
        self.assertEqual(problem_dir("r", Problem("Z"), by_contest=True), os.path.join("r", "z"))


class ServerTests(unittest.TestCase):
    def test_receive_companion_post(self):
        with tempfile.TemporaryDirectory() as d:
            got = []
            srv = serve_in_background(d, 0, on_problem=lambda p, f: got.append(f))
            try:
                port = srv.server_address[1]
                req = urllib.request.Request("http://127.0.0.1:%d/" % port, data=json.dumps(COMPANION).encode(),
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=5) as r:
                    folder = json.load(r)["folder"]
                self.assertTrue(os.path.exists(os.path.join(folder, "tests", "2.out")))
                self.assertEqual(got, [folder])
                with urllib.request.urlopen("http://127.0.0.1:%d/" % port, timeout=5) as r:
                    self.assertIn(b"listening", r.read())
                bad = urllib.request.Request("http://127.0.0.1:%d/" % port, data=b"{not json")
                with self.assertRaises(urllib.error.HTTPError) as cm:
                    urllib.request.urlopen(bad, timeout=5)
                self.assertEqual(cm.exception.code, 400)
            finally:
                srv.shutdown()
                srv.server_close()


    def test_batch_of_problems(self):
        with tempfile.TemporaryDirectory() as d:
            srv = serve_in_background(d, 0, lang="js")
            try:
                port = srv.server_address[1]
                for letter in "AB":
                    payload = dict(COMPANION, name="%s. Task %s" % (letter, letter),
                                   url="https://codeforces.com/contest/2061/problem/" + letter)
                    req = urllib.request.Request("http://127.0.0.1:%d/" % port, data=json.dumps(payload).encode())
                    urllib.request.urlopen(req, timeout=5).close()
                self.assertEqual(len(srv.received), 2)
                folders = sorted(os.listdir(os.path.join(d, "codeforces", "2061")))
                self.assertEqual(folders, ["a-task-a", "b-task-b"])
                self.assertTrue(os.path.exists(os.path.join(d, "codeforces", "2061", "a-task-a", "solution.js")))
            finally:
                srv.shutdown()
                srv.server_close()


class CliTests(unittest.TestCase):
    def test_parse_contest_list(self):
        with tempfile.TemporaryDirectory() as d:
            page = os.path.join(d, "a.html")
            with open(page, "w", encoding="utf-8") as fh:
                fh.write(CODEFORCES)
            comp = os.path.join(d, "c.json")
            with open(comp, "w") as fh:
                json.dump(COMPANION, fh)
            ws = os.path.join(d, "ws")
            with redirect_stdout(io.StringIO()) as buf, redirect_stderr(io.StringIO()):
                self.assertEqual(main(["parse", page, "--url", "https://codeforces.com/contest/4/problem/A", "-d", ws]), 0)
                self.assertEqual(main(["parse", comp, "-d", ws, "-l", "java"]), 0)
                self.assertEqual(main(["parse", page, "--print"]), 0)
                self.assertEqual(main(["contest", "codeforces", "1900", "A-C", "-d", ws]), 0)
                self.assertEqual(main(["list", "-d", ws]), 0)
            out = buf.getvalue()
            self.assertIn("A. Watermelon: 2 sample(s), 1000 ms, 64 MB", out)
            self.assertIn('"memory_limit_mb": 64', out)
            self.assertIn("5 problem(s)", out)
            self.assertTrue(os.path.exists(os.path.join(ws, "codeforces", "2061", "c-binary-string-cutting", "Main.java")))


if __name__ == "__main__":
    unittest.main()
