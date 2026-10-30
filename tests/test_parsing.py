import unittest

from problem_fetcher.dom import parse, pre_text
from problem_fetcher.model import Problem, detect_ids, slugify
from problem_fetcher.parsers import parse_atcoder, parse_codeforces, parse_cses, parse_generic, parse_page

from .fixtures import ATCODER, CODEFORCES, COMPANION, CSES, GENERIC, UNLABELLED


class DomTests(unittest.TestCase):
    def test_tree_and_queries(self):
        root = parse('<div class="a b"><p id="x">Hello <b>big</b><br>world</p><ul><li>1<li>2</ul></div>')
        self.assertEqual(root.find("p", id_="x").text(), "Hello big\nworld")
        self.assertEqual(len(root.find_all("li")), 2)
        self.assertEqual(root.find("div", class_="b").tag, "div")
        self.assertIsNone(root.find("table"))
        self.assertEqual(root.find("p").next_sibling().tag, "ul")

    def test_pre_text_variants(self):
        root = parse('<pre><div class="test-example-line">1 2</div><div class="test-example-line">3</div></pre>'
                     '<pre>a<br>b</pre><pre>\n  x  y\n</pre><pre></pre>')
        pres = root.find_all("pre")
        self.assertEqual([pre_text(p) for p in pres], ["1 2\n3\n", "a\nb\n", "  x  y\n", ""])

    def test_entities_scripts_and_unclosed(self):
        root = parse("<p>1&nbsp;&le;&nbsp;n<script>var x=1</script></p><div><span>open")
        self.assertEqual(root.find("p").text().replace("\xa0", " "), "1 ≤ n")
        self.assertEqual(root.find("span").text(), "open")


class ModelTests(unittest.TestCase):
    def test_detect_ids(self):
        self.assertEqual(detect_ids("https://codeforces.com/contest/1900/problem/c2"), ("codeforces", "1900", "C2"))
        self.assertEqual(detect_ids("https://codeforces.com/problemset/problem/4/A"), ("codeforces", "4", "A"))
        self.assertEqual(detect_ids("https://codeforces.com/gym/104/problem/B"), ("codeforces", "104", "B"))
        self.assertEqual(detect_ids("https://atcoder.jp/contests/abc300/tasks/abc300_d"), ("atcoder", "abc300", "D"))
        self.assertEqual(detect_ids("https://cses.fi/problemset/task/1068"), ("cses", "", "1068"))
        self.assertEqual(detect_ids("https://example.org/x"), ("", "", ""))

    def test_companion_and_round_trip(self):
        p = Problem.from_companion(COMPANION)
        self.assertEqual((p.judge, p.contest_id, p.index, p.time_limit_ms), ("codeforces", "2061", "C", 2000))
        self.assertEqual(len(p.samples), 2)
        self.assertEqual(p.slug, "c-binary-string-cutting")
        q = Problem.from_dict(p.to_dict())
        self.assertEqual(q, p)
        self.assertEqual(slugify("  Hello, World!! "), "hello-world")


class ParserTests(unittest.TestCase):
    def test_codeforces(self):
        p = parse_codeforces(CODEFORCES, "https://codeforces.com/problemset/problem/4/A")
        self.assertEqual((p.name, p.index, p.contest_id), ("A. Watermelon", "A", "4"))
        self.assertEqual((p.time_limit_ms, p.memory_limit_mb), (1000, 64))
        self.assertEqual([(s.input, s.output) for s in p.samples], [("8\n1 2  3\n", "YES\n"), ("3\n4\n", "NO\n")])
        self.assertIn("watermelon", p.statement)
        self.assertTrue(p.input_spec.startswith("The first"))
        self.assertEqual(p.tags, ["brute force", "math"])

    def test_atcoder_english_only(self):
        p = parse_atcoder(ATCODER, "https://atcoder.jp/contests/practice/tasks/practice_1")
        self.assertEqual(p.name, "A - Welcome to AtCoder")
        self.assertEqual((p.time_limit_ms, p.memory_limit_mb, p.contest_id), (2000, 1024, "practice"))
        self.assertEqual([s.output for s in p.samples], ["6 test\n", "456 myonmyon\n"])
        self.assertEqual(p.samples[0].input, "1\n2 3\ntest\n")
        self.assertIn("Compute a+b+c", p.statement)

    def test_cses_and_generic(self):
        p = parse_cses(CSES, "https://cses.fi/problemset/task/1068")
        self.assertEqual((p.name, p.time_limit_ms, p.memory_limit_mb), ("Weird Algorithm", 1000, 512))
        self.assertEqual(p.samples[0].output, "3 10 5 16 8 4 2 1\n")
        g = parse_generic(GENERIC)
        self.assertEqual([(s.input, s.output) for s in g.samples], [("1 2\n", "3\n"), ("5 5\n", "10\n")])
        self.assertEqual((g.time_limit_ms, g.memory_limit_mb), (3000, 128))
        u = parse_generic(UNLABELLED)
        self.assertEqual(len(u.samples), 2)

    def test_dispatch(self):
        self.assertEqual(parse_page(CODEFORCES).judge, "codeforces")
        self.assertEqual(parse_page(ATCODER).judge, "atcoder")
        self.assertEqual(parse_page(CSES, "https://cses.fi/problemset/task/1068").judge, "cses")
        self.assertEqual(parse_page(GENERIC).name, "Sum of Two")
        with self.assertRaises(ValueError):
            parse_codeforces("<html></html>")


class LimitTests(unittest.TestCase):
    def test_time_units(self):
        from problem_fetcher.parsers import _limit_ms
        cases = {"1 second": 1000, "2 seconds": 2000, "2.5 sec": 2500, "1.00 s": 1000, "500 ms": 500,
                 "time limit per test3 seconds": 3000, "nothing": 2000}
        for text, ms in cases.items():
            self.assertEqual(_limit_ms(text), ms, text)

    def test_memory_units(self):
        from problem_fetcher.parsers import _limit_mb
        cases = {"256 megabytes": 256, "1024 MB": 1024, "512 MiB": 512, "1 GB": 1024, "2 GiB": 2048, "?": 256}
        for text, mb in cases.items():
            self.assertEqual(_limit_mb(text), mb, text)

    def test_interactive_flag_and_missing_samples(self):
        html = CODEFORCES.replace("One hot summer day", "This is an interactive problem. Interaction protocol:")
        self.assertTrue(parse_codeforces(html).interactive)
        self.assertFalse(parse_codeforces(CODEFORCES).interactive)
        bare = parse_generic("<html><body><p>no samples here</p></body></html>")
        self.assertEqual((bare.name, bare.samples), ("problem", []))


if __name__ == "__main__":
    unittest.main()
