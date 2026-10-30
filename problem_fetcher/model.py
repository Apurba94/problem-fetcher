"""The Problem record shared by parsers, the Competitive Companion receiver and the workspace."""
import json
import re
from dataclasses import asdict, dataclass, field


@dataclass
class Sample:
    input: str
    output: str = ""


@dataclass
class Problem:
    name: str
    url: str = ""
    group: str = ""                       # contest name / judge
    judge: str = ""
    contest_id: str = ""
    index: str = ""                       # problem letter or number
    time_limit_ms: int = 2000
    memory_limit_mb: int = 256
    interactive: bool = False
    samples: list = field(default_factory=list)
    statement: str = ""
    input_spec: str = ""
    output_spec: str = ""
    tags: list = field(default_factory=list)

    @property
    def slug(self):
        base = ("%s-%s" % (self.index, self.name)) if self.index and not self.name.startswith(self.index) else self.name
        return slugify(base)

    def to_dict(self):
        d = asdict(self)
        d["samples"] = [asdict(s) for s in self.samples]
        return d

    def to_json(self):
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        d["samples"] = [Sample(**s) for s in d.get("samples", [])]
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_companion(cls, data):
        """Competitive Companion payload (https://github.com/jmerle/competitive-companion)."""
        name = data.get("name", "problem")
        url = data.get("url", "")
        judge, contest, index = detect_ids(url)
        m = re.match(r"^\s*([A-Z]\d?|\d+)\s*[.\-:]\s*(.+)$", name)
        if m and not index:
            index = m.group(1)
        return cls(name=name, url=url, group=data.get("group", ""), judge=judge or data.get("group", "").split(" - ")[0],
                   contest_id=contest, index=index, time_limit_ms=int(data.get("timeLimit", 2000)),
                   memory_limit_mb=int(data.get("memoryLimit", 256)), interactive=bool(data.get("interactive")),
                   samples=[Sample(t.get("input", ""), t.get("output", "")) for t in data.get("tests", [])])


def slugify(s, limit=60):
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s[:limit].rstrip("-") or "problem"


_URLS = [
    ("codeforces", re.compile(r"codeforces\.com/(?:contest|gym)/(\d+)/problem/([A-Za-z0-9]+)")),
    ("codeforces", re.compile(r"codeforces\.com/problemset/problem/(\d+)/([A-Za-z0-9]+)")),
    ("atcoder", re.compile(r"atcoder\.jp/contests/([\w-]+)/tasks/[\w-]+_([a-z0-9]+)")),
    ("cses", re.compile(r"cses\.fi/problemset/task/()(\d+)")),
    ("leetcode", re.compile(r"leetcode\.com/problems/()([\w-]+)")),
    ("kattis", re.compile(r"kattis\.com/problems/()([\w-]+)")),
    ("spoj", re.compile(r"spoj\.com/problems/()(\w+)")),
]


def detect_ids(url):
    """(judge, contest id, problem index) from a problem URL; empty strings when unknown."""
    for judge, rx in _URLS:
        m = rx.search(url or "")
        if m:
            idx = m.group(2)
            return judge, m.group(1), idx.upper() if judge in ("codeforces", "atcoder") else idx
    return "", "", ""
