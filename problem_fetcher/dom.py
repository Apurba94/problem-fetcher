"""A tiny HTML DOM built on html.parser, enough to scrape problem statements without dependencies."""
from html.parser import HTMLParser

VOID = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}
BLOCK = {"div", "p", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "section", "ul", "ol", "table"}


class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.children, self.parent = tag, dict(attrs or {}), [], parent

    @property
    def classes(self):
        return set((self.attrs.get("class") or "").split())

    def iter(self):
        stack = [self]
        while stack:
            n = stack.pop()
            yield n
            stack.extend(c for c in reversed(n.children) if isinstance(c, Node))

    def find_all(self, tag=None, class_=None, id_=None):
        out = []
        for n in self.iter():
            if n is self:
                continue
            if tag and n.tag != tag:
                continue
            if class_ and class_ not in n.classes:
                continue
            if id_ and n.attrs.get("id") != id_:
                continue
            out.append(n)
        return out

    def find(self, tag=None, class_=None, id_=None):
        r = self.find_all(tag, class_, id_)
        return r[0] if r else None

    def text(self, preserve=False):
        """Visible text. Block elements and <br> become line breaks; with preserve=True whitespace inside
        <pre> is kept exactly (sample tests)."""
        parts = []

        def walk(node, in_pre):
            for c in node.children:
                if isinstance(c, str):
                    if in_pre or preserve:
                        parts.append(c)
                    else:
                        words = " ".join(c.split())
                        if words:
                            parts.append(" " + words + " ")
                else:
                    if c.tag in ("script", "style"):
                        continue
                    if c.tag == "br":
                        parts.append("\n")
                        continue
                    block = c.tag in BLOCK
                    if block and parts and not parts[-1].endswith("\n"):
                        parts.append("\n")
                    walk(c, in_pre or c.tag == "pre")
                    if block and parts and not parts[-1].endswith("\n"):
                        parts.append("\n")
        walk(self, self.tag == "pre")
        text = "".join(p for p in parts if p)
        if preserve or self.tag == "pre":
            return text
        lines = [" ".join(l.split()) for l in text.split("\n")]
        return "\n".join(l for l in lines if l)

    def next_sibling(self, tag=None):
        if not self.parent:
            return None
        sibs = [c for c in self.parent.children if isinstance(c, Node)]
        i = sibs.index(self)
        for s in sibs[i + 1:]:
            if tag is None or s.tag == tag:
                return s
        return None


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:      # tolerate unclosed tags
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def parse(html):
    b = _Builder()
    b.feed(html)
    b.close()
    return b.root


def pre_text(node):
    """Text of a sample <pre>: Codeforces wraps each line in a div, others use <br> or plain newlines."""
    lines = node.find_all("div", class_="test-example-line")
    if lines:
        return "\n".join(l.text(preserve=True).strip("\n") for l in lines) + "\n"
    t = node.text(preserve=True).replace("\r\n", "\n").strip("\n")
    return t + "\n" if t else ""
