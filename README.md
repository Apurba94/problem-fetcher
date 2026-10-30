# problem-fetcher

**Start every problem in seconds: receive problems from the Competitive Companion browser extension,
or parse Codeforces, AtCoder, CSES and other statement pages, and get a ready folder with the sample
tests, a solution from your template, the limits and the statement.**

Part of the *Competitive Programming Suite* (10 large automation tools for algorithmic problem solving).

## Why

In a contest the first minutes of every problem go into copying samples into files, creating a source
file from a template, and noting the limits. Copy mistakes (a missing trailing line, a lost space) make you
debug a correct solution. Automating the setup removes both the delay and the errors, and the folders it
creates are exactly what `cp-judge` and `stress-tester` expect.

## Features

| Area | Details |
|------|---------|
| Competitive Companion | HTTP receiver (`listen`, default port 10043) for the browser extension; one click on a problem or a whole contest creates the folders |
| Parsers | Codeforces (including the per-line sample format and `<br>` samples, tags, input/output specs), AtCoder (English statement only, all samples, limits), CSES (constraints, examples), generic pages (labelled or alternating `<pre>` blocks) |
| DOM | dependency-free HTML tree (`dom.parse`) with `find`, `find_all`, sibling navigation and whitespace-exact sample extraction |
| Workspace | `<judge>/<contest>/<letter-name>/` with `tests/1.in`, `1.out`, `problem.json`, `README.md` (limits, statement, samples), and `solution.<ext>` from built-in (py, cpp, java, js) or your own `template.<ext>` files; existing solutions are never overwritten |
| Contests | `contest codeforces 1900 A-F` creates empty folders and URLs before the start |
| Overview | `list` shows every problem, its test count and whether the solution has been edited |

Template placeholders: `{name}`, `{url}`, `{time_limit}`, `{memory_limit}`, `{judge}`, `{index}`, `{date}`
(write literal braces as `{{` and `}}`, as in the C++ template).

## Usage

```bash
pip install .
problem-fetcher listen -d ~/contests -l cpp             # then click Competitive Companion in the browser
problem-fetcher fetch https://codeforces.com/problemset/problem/4/A -d ~/contests
problem-fetcher parse saved_page.html --url https://atcoder.jp/contests/abc300/tasks/abc300_d
problem-fetcher contest atcoder abc300 A-G -l py --templates ~/cp/templates
problem-fetcher list -d ~/contests
cp-judge run ~/contests/codeforces/4/a-watermelon/solution.py ~/contests/codeforces/4/a-watermelon/tests
```

## Limitations

Some judges block automated downloads (Cloudflare); use the browser extension or save the page and use
`parse`. Statements with images or complex formulas are reduced to plain text.

## Testing

```bash
python -m unittest discover -s tests -t .
```

## License

MIT (c) JANIN A APURBA
