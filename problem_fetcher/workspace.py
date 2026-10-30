"""Create per-problem folders: tests, problem.json, a README with limits and samples, and a solution
from a template. Templates use {name}, {url}, {time_limit}, {memory_limit}, {judge}, {index}, {date}."""
import datetime
import json
import os
import re

from .model import Problem

TEMPLATES = {
    "py": '''# {name}
# {url}
# time limit {time_limit} ms, memory limit {memory_limit} MB
import sys
input = sys.stdin.readline


def solve():
    pass


def main():
    t = 1
    # t = int(input())
    for _ in range(t):
        solve()


main()
''',
    "cpp": '''// {name}
// {url}
// time limit {time_limit} ms, memory limit {memory_limit} MB
#include <bits/stdc++.h>
using namespace std;
using ll = long long;

void solve() {{
}}

int main() {{
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int t = 1;
    // cin >> t;
    while (t--) solve();
    return 0;
}}
''',
    "java": '''// {name}
// {url}
import java.io.*;
import java.util.*;

public class Main {{
    public static void main(String[] args) throws IOException {{
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        PrintWriter out = new PrintWriter(new BufferedWriter(new OutputStreamWriter(System.out)));
        out.flush();
    }}
}}
''',
    "js": '''// {name}
// {url}
const lines = require("fs").readFileSync(0, "utf8").split("\\n");
let ptr = 0;
const next = () => lines[ptr++];
''',
}
FILE_NAMES = {"py": "solution.py", "cpp": "solution.cpp", "java": "Main.java", "js": "solution.js"}


def render_template(text, problem):
    values = {"name": problem.name, "url": problem.url, "time_limit": problem.time_limit_ms,
              "memory_limit": problem.memory_limit_mb, "judge": problem.judge, "index": problem.index,
              "date": datetime.date.today().isoformat()}
    return text.format(**values)


def load_template(lang, template_dir=None):
    if template_dir:
        for fn in os.listdir(template_dir) if os.path.isdir(template_dir) else []:
            if fn.startswith("template.") and fn.split(".")[-1] == lang:
                with open(os.path.join(template_dir, fn), encoding="utf-8") as fh:
                    return fh.read(), fn.replace("template", "solution", 1)
    if lang not in TEMPLATES:
        raise ValueError("no template for language %r (built-in: %s)" % (lang, ", ".join(TEMPLATES)))
    return TEMPLATES[lang], FILE_NAMES[lang]


def problem_dir(root, problem, by_contest=True):
    parts = [root]
    if by_contest and problem.judge:
        parts.append(problem.judge)
        if problem.contest_id:
            parts.append(problem.contest_id)
    parts.append(problem.slug)
    return os.path.join(*parts)


def write_problem(root, problem, lang="py", template_dir=None, by_contest=True, overwrite_tests=True):
    """Create the folder; never overwrites an existing solution. Returns the folder path."""
    d = problem_dir(root, problem, by_contest)
    tests = os.path.join(d, "tests")
    os.makedirs(tests, exist_ok=True)
    for i, s in enumerate(problem.samples, 1):
        p_in = os.path.join(tests, "%d.in" % i)
        if overwrite_tests or not os.path.exists(p_in):
            with open(p_in, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(s.input if s.input.endswith("\n") else s.input + "\n")
            with open(os.path.join(tests, "%d.out" % i), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(s.output if s.output.endswith("\n") or not s.output else s.output + "\n")
    with open(os.path.join(d, "problem.json"), "w", encoding="utf-8") as fh:
        fh.write(problem.to_json())
    text, fname = load_template(lang, template_dir)
    sol = os.path.join(d, fname)
    if not os.path.exists(sol):
        with open(sol, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render_template(text, problem))
    with open(os.path.join(d, "README.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(problem_readme(problem))
    return d


def problem_readme(p):
    lines = ["# %s" % p.name, ""]
    if p.url:
        lines += ["<%s>" % p.url, ""]
    lines += ["- Judge: %s %s" % (p.judge or p.group or "-", p.contest_id),
              "- Time limit: %d ms, memory limit: %d MB%s" % (p.time_limit_ms, p.memory_limit_mb,
                                                             ", **interactive**" if p.interactive else ""), ""]
    if p.tags:
        lines += ["Tags: " + ", ".join(p.tags), ""]
    for title, body in (("Statement", p.statement), ("Input", p.input_spec), ("Output", p.output_spec)):
        if body:
            lines += ["## " + title, "", body, ""]
    for i, s in enumerate(p.samples, 1):
        lines += ["## Sample %d" % i, "", "```", s.input.rstrip("\n"), "```", "", "```", s.output.rstrip("\n"), "```", ""]
    return "\n".join(lines)


def contest_skeleton(root, judge, contest_id, indices, lang="py", template_dir=None):
    """Folders for a whole contest before it starts (samples can be added later)."""
    out = []
    for idx in indices:
        p = Problem(name=idx, judge=judge, contest_id=str(contest_id), index=idx, url=contest_url(judge, contest_id, idx))
        out.append(write_problem(root, p, lang, template_dir))
    return out


def contest_url(judge, contest_id, idx):
    if judge == "codeforces":
        return "https://codeforces.com/contest/%s/problem/%s" % (contest_id, idx)
    if judge == "atcoder":
        return "https://atcoder.jp/contests/%s/tasks/%s_%s" % (contest_id, contest_id, idx.lower())
    return ""


def expand_indices(spec):
    """'A-F' -> A..F; 'A,B,C1,C2' -> list; '1-5' -> 1..5."""
    out = []
    for part in spec.split(","):
        part = part.strip()
        m = re.fullmatch(r"([A-Za-z])-([A-Za-z])", part)
        n = re.fullmatch(r"(\d+)-(\d+)", part)
        if m:
            out += [chr(c) for c in range(ord(m.group(1).upper()), ord(m.group(2).upper()) + 1)]
        elif n:
            out += [str(i) for i in range(int(n.group(1)), int(n.group(2)) + 1)]
        elif part:
            out.append(part)
    return out


def scan(root):
    """Problems under root: (folder, Problem, has_solution_edits, n_tests)."""
    out = []
    for dp, dns, fns in os.walk(root):
        if "problem.json" in fns:
            with open(os.path.join(dp, "problem.json"), encoding="utf-8") as fh:
                p = Problem.from_dict(json.load(fh))
            sols = [f for f in fns if f.startswith(("solution.", "Main."))]
            edited = False
            for s in sols:
                with open(os.path.join(dp, s), encoding="utf-8") as fh:
                    body = fh.read()
                edited = edited or not ("pass\n" in body and "def solve" in body and body.count("\n") < 25)
            tests = os.path.join(dp, "tests")
            n = len([f for f in os.listdir(tests) if f.endswith(".in")]) if os.path.isdir(tests) else 0
            out.append((dp, p, edited, n))
    return sorted(out, key=lambda x: x[0])
