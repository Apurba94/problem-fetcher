"""Statement parsers for Codeforces, AtCoder, CSES and a generic fallback, plus an optional downloader.

All parsers take HTML text (so they work offline on saved pages) and return a Problem."""
import re
import urllib.request

from .dom import parse, pre_text
from .model import Problem, Sample, detect_ids

UA = "Mozilla/5.0 (problem-fetcher; +https://github.com)"


def _limit_ms(text):
    m = re.search(r"([\d.]+)\s*(seconds?|secs?|s)\b", text, re.I)
    if m:
        return int(float(m.group(1)) * 1000)
    m = re.search(r"(\d+)\s*ms", text, re.I)
    return int(m.group(1)) if m else 2000


def _limit_mb(text):
    m = re.search(r"([\d.]+)\s*(megabytes|MB|MiB)", text, re.I)
    if m:
        return int(float(m.group(1)))
    m = re.search(r"([\d.]+)\s*(GB|GiB)", text, re.I)
    return int(float(m.group(1)) * 1024) if m else 256


def parse_codeforces(html, url=""):
    root = parse(html)
    ps = root.find("div", class_="problem-statement")
    if ps is None:
        raise ValueError("not a Codeforces problem page")
    header = ps.find("div", class_="header")
    title = header.find("div", class_="title").text() if header and header.find("div", class_="title") else "problem"
    tl = header.find("div", class_="time-limit") if header else None
    ml = header.find("div", class_="memory-limit") if header else None
    samples = []
    st = ps.find("div", class_="sample-test")
    if st:
        ins = [d.find("pre") for d in st.find_all("div", class_="input")]
        outs = [d.find("pre") for d in st.find_all("div", class_="output")]
        samples = [Sample(pre_text(i), pre_text(o) if o else "") for i, o in zip(ins, outs + [None] * len(ins)) if i]

    def section(cls):
        d = ps.find("div", class_=cls)
        if not d:
            return ""
        title_div = d.find("div", class_="section-title")
        t = d.text()
        return t[len(title_div.text()):].strip() if title_div and t.startswith(title_div.text()) else t
    legend = [c for c in ps.children if not isinstance(c, str) and not c.classes & {"header", "input-specification",
                                                                                  "output-specification", "sample-tests", "note"}]
    judge, contest, index = detect_ids(url)
    m = re.match(r"^([A-Z]\d?)\.\s*(.+)$", title)
    name = title
    if m:
        index = index or m.group(1)
    tags = [t.text() for t in root.find_all("span", class_="tag-box")]
    return Problem(name=name, url=url, judge="codeforces", group="Codeforces", contest_id=contest, index=index,
                   time_limit_ms=_limit_ms(tl.text() if tl else ""), memory_limit_mb=_limit_mb(ml.text() if ml else ""),
                   interactive="interaction" in html.lower() and "interactive" in html.lower(), samples=samples,
                   statement="\n".join(c.text() for c in legend).strip(), input_spec=section("input-specification"),
                   output_spec=section("output-specification"), tags=tags)


def parse_atcoder(html, url=""):
    root = parse(html)
    title_node = root.find("span", class_="h2") or root.find("title")
    title = title_node.text() if title_node else "problem"
    title = re.sub(r"\s*Editorial\s*$", "", title).strip()
    body_text = root.text()
    limits = re.search(r"Time Limit:\s*([^/]+)/\s*Memory Limit:\s*(\S+\s*\S+)", body_text)
    task = root.find("div", id_="task-statement") or root
    part = task.find("span", class_="lang-en") or task
    samples, pending = [], None
    for h3 in part.find_all("h3"):
        label = h3.text()
        pre = h3.next_sibling("pre")
        if pre is None:
            continue
        if re.match(r"Sample Input", label):
            pending = pre_text(pre)
        elif re.match(r"Sample Output", label) and pending is not None:
            samples.append(Sample(pending, pre_text(pre)))
            pending = None
    judge, contest, index = detect_ids(url)
    m = re.match(r"^([A-Z]\d?)\s*-\s*(.+)$", title)
    if m:
        index = index or m.group(1)
    sections = {}
    for sec in part.find_all("section"):
        h = sec.find("h3")
        if h:
            sections[h.text().lower()] = sec.text()[len(h.text()):].strip()
    return Problem(name=title, url=url, judge="atcoder", group="AtCoder " + contest if contest else "AtCoder",
                   contest_id=contest, index=index,
                   time_limit_ms=_limit_ms(limits.group(1)) if limits else 2000,
                   memory_limit_mb=_limit_mb(limits.group(2)) if limits else 1024, samples=samples,
                   statement=sections.get("problem statement", ""), input_spec=sections.get("input", ""),
                   output_spec=sections.get("output", ""))


def parse_cses(html, url=""):
    root = parse(html)
    h1 = root.find("h1")
    name = h1.text() if h1 else "problem"
    content = root.find("div", class_="content") or root
    limits = " ".join(li.text() for li in root.find_all("li"))
    samples, pending = [], None
    for p in content.find_all("p"):
        label = p.text().strip().rstrip(":").lower()
        pre = p.next_sibling("pre")
        if pre is None:
            continue
        if label == "input":
            pending = pre_text(pre)
        elif label == "output" and pending is not None:
            samples.append(Sample(pending, pre_text(pre)))
            pending = None
    judge, contest, index = detect_ids(url)
    return Problem(name=name, url=url, judge="cses", group="CSES Problem Set", index=index,
                   time_limit_ms=_limit_ms(limits), memory_limit_mb=_limit_mb(limits), samples=samples,
                   statement=content.text()[:4000])


def parse_generic(html, url=""):
    """Fallback: pair <pre> blocks preceded by headings/paragraphs mentioning input and output."""
    root = parse(html)
    title = root.find("h1") or root.find("title")
    samples, pending = [], None
    for pre in root.find_all("pre"):
        prev_label = ""
        sibs = [c for c in pre.parent.children if not isinstance(c, str)] if pre.parent else []
        i = sibs.index(pre) if pre in sibs else 0
        for s in reversed(sibs[:i]):
            if s.tag != "pre":
                prev_label = s.text().lower()
                break
        if "input" in prev_label:
            pending = pre_text(pre)
        elif "output" in prev_label and pending is not None:
            samples.append(Sample(pending, pre_text(pre)))
            pending = None
    if not samples:                         # no labels: assume alternating input/output blocks
        pres = [pre_text(p) for p in root.find_all("pre")]
        samples = [Sample(pres[i], pres[i + 1]) for i in range(0, len(pres) - 1, 2)]
    judge, contest, index = detect_ids(url)
    text = root.text()
    return Problem(name=title.text() if title else "problem", url=url, judge=judge, index=index,
                   time_limit_ms=_limit_ms(text) if re.search(r"time limit", text, re.I) else 2000,
                   memory_limit_mb=_limit_mb(text) if re.search(r"memory limit", text, re.I) else 256, samples=samples)


PARSERS = {"codeforces": parse_codeforces, "atcoder": parse_atcoder, "cses": parse_cses}


def parse_page(html, url=""):
    judge = detect_ids(url)[0]
    if not judge:
        if "problem-statement" in html and "sample-test" in html:
            judge = "codeforces"
        elif "task-statement" in html:
            judge = "atcoder"
    return PARSERS.get(judge, parse_generic)(html, url)


def fetch(url, timeout=20):
    """Download a page (some judges block automated requests; save the page and parse the file instead)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8", errors="replace")
