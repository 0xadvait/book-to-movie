"""Turn a book file into plain text, one file per chapter.

Reads .txt, .md, .pdf, .epub, .html and .docx with no paid service. Chapters are found from headings ("Chapter 3", "PART
TWO", "# Title", a run of roman numerals or plain numbers). A contents page is told apart from real chapters by how much
text follows each heading. If a book has no headings at all it is cut into even parts at paragraph breaks.
"""
import html
import json
import re
import shutil
import subprocess
import zipfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from posixpath import dirname as posix_dirname
from posixpath import join as posix_join
from posixpath import normpath as posix_normpath
from xml.etree import ElementTree

NUMBER_WORDS = ("one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
                "nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred")
_NUM = rf"(?:\d{{1,3}}|[ivxlcdm]{{1,7}}|(?:{NUMBER_WORDS})(?:[- ](?:{NUMBER_WORDS}))?)"
CHAPTER_RE = re.compile(rf"^\s*(?:chapter|chap\.|lesson|letter)\s+({_NUM})\b[\s.:\-—–]*(.*)$", re.I)
PART_RE = re.compile(rf"^\s*(?:part|book|act|volume|section)\s+({_NUM})\b[\s.:\-—–]*(.*)$", re.I)
MARKDOWN_RE = re.compile(r"^\s{0,3}(#{1,2})\s+(.+?)\s*#*\s*$")
ROMAN_RE = re.compile(r"^\s*([IVXLCDM]{1,7})\.?\s*$")
ARABIC_RE = re.compile(r"^\s*(\d{1,3})\.?\s*$")
MIN_CHAPTER_WORDS = 120
EVEN_PART_WORDS = 3500


# ---- reading ----
class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "blockquote", "section", "title"}
    SKIP = {"script", "style", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.depth = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.depth:
            self.out.append(re.sub(r"[ \t\r\n]+", " ", data))

    def text(self):
        return re.sub(r"\n[ \t]*", "\n", "".join(self.out))


def _html_text(markup):
    t = _Text()
    t.feed(markup)
    return t.text()


def read_pdf(path):
    if shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-enc", "UTF-8", str(path), "-"], capture_output=True)
        if r.returncode == 0 and r.stdout.strip():
            return clean_pdf_text(r.stdout.decode("utf-8", "replace"))
    raise SystemExit("reading a PDF needs pdftotext (macOS: brew install poppler, Linux: apt install poppler-utils). "
                     "If the PDF is a scan with no text layer, run it through OCR first.")


def clean_pdf_text(text):
    """page furniture out: form feeds, page numbers, headers and footers that repeat on most pages, hyphenated line ends"""
    pages = text.split("\f")
    edges = Counter()
    for page in pages:
        lines = [x.strip() for x in page.splitlines() if x.strip()]
        for line in lines[:2] + lines[-2:]:
            edges[re.sub(r"\d+", "#", line)] += 1
    repeated = {k for k, v in edges.items() if v >= max(4, len(pages) * 0.1) and len(k) < 80}
    kept = []
    for page in pages:
        for line in page.splitlines():
            s = line.strip()
            if re.fullmatch(r"(page\s+)?\d{1,4}", s, re.I) or re.sub(r"\d+", "#", s) in repeated:
                continue
            kept.append(line.rstrip())
        kept.append("")
    joined = "\n".join(kept)
    return re.sub(r"(\w)-\n(\w)", r"\1\2", joined)


def read_epub(path):
    """the spine in reading order, and the title and author from the metadata"""
    meta = {}
    with zipfile.ZipFile(path) as z:
        container = ElementTree.fromstring(z.read("META-INF/container.xml"))
        ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container", "o": "http://www.idpf.org/2007/opf",
              "d": "http://purl.org/dc/elements/1.1/"}
        opf_path = container.find(".//c:rootfile", ns).attrib["full-path"]
        opf = ElementTree.fromstring(z.read(opf_path))
        title, author = opf.find(".//d:title", ns), opf.find(".//d:creator", ns)
        meta["title"] = (title.text or "").strip() if title is not None else ""
        meta["author"] = (author.text or "").strip() if author is not None else ""
        items = {i.attrib["id"]: i.attrib["href"] for i in opf.findall(".//o:manifest/o:item", ns)}
        base = posix_dirname(opf_path)
        parts = []
        for ref in opf.findall(".//o:spine/o:itemref", ns):
            href = items.get(ref.attrib["idref"])
            if not href:
                continue
            name = posix_normpath(posix_join(base, html.unescape(href).split("#")[0]))
            try:
                parts.append(_html_text(z.read(name).decode("utf-8", "replace")))
            except KeyError:
                continue
    return "\n\n".join(parts), meta


def read_docx(path):
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))
    paragraphs = ["".join(t.text or "" for t in para.iter(f"{w}t")) for para in root.iter(f"{w}p")]
    return "\n\n".join(paragraphs)


def read_book(path):
    """-> (text, {"title", "author"})"""
    path = Path(path)
    ext = path.suffix.lower()
    if ext in (".txt", ".md", ".markdown", ".text"):
        return path.read_text(encoding="utf-8", errors="replace"), {}
    if ext == ".pdf":
        return read_pdf(path), {}
    if ext == ".epub":
        return read_epub(path)
    if ext in (".html", ".htm", ".xhtml"):
        return _html_text(path.read_text(encoding="utf-8", errors="replace")), {}
    if ext == ".docx":
        return read_docx(path), {}
    raise SystemExit(f"cannot read {ext or path.name} files. Use .txt, .md, .pdf, .epub, .html or .docx.")


def strip_boilerplate(text):
    """Project Gutenberg's licence block, which is not the book"""
    m = re.search(r"\*\*\*\s*START OF (?:THE |THIS )?PROJECT GUTENBERG[^\n]*\n", text, re.I)
    if m:
        text = text[m.end():]
    m = re.search(r"\*\*\*\s*END OF (?:THE |THIS )?PROJECT GUTENBERG", text, re.I)
    if m:
        text = text[:m.start()]
    return text.replace("\r\n", "\n").replace("\r", "\n")


# ---- finding chapters ----
def _roman_value(s):
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total, prev = 0, 0
    for ch in reversed(s.upper()):
        v = vals[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def _sequential(hits, value):
    """keep the longest in-order run 1, 2, 3 ... of numbered lines, so stray numbers and page numbers do not count"""
    expect, keep = 1, []
    for i, raw in hits:
        v = value(raw)
        if v == expect:
            keep.append((i, ""))
            expect += 1
    return keep


def find_headings(lines, heading_regex=None):
    """-> [(line index, trailing title text)] using the strongest pattern the book actually uses"""
    if heading_regex:
        rx = re.compile(heading_regex, re.I)
        return [(i, "") for i, x in enumerate(lines) if rx.search(x)]
    for rx in (CHAPTER_RE, PART_RE):
        hits = [(i, (m.group(2) or "").strip()) for i, x in enumerate(lines) if (m := rx.match(x))]
        if len(hits) >= 2:
            return hits
    hits = [(i, m.group(2).strip()) for i, x in enumerate(lines) if (m := MARKDOWN_RE.match(x)) and len(m.group(1)) == 2]
    if len(hits) >= 2:
        return hits
    hits = [(i, m.group(2).strip()) for i, x in enumerate(lines) if (m := MARKDOWN_RE.match(x))]
    if len(hits) >= 2:
        return hits
    run = _sequential([(i, m.group(1)) for i, x in enumerate(lines) if (m := ROMAN_RE.match(x))], _roman_value)
    if len(run) >= 3:
        return run
    run = _sequential([(i, m.group(1)) for i, x in enumerate(lines) if (m := ARABIC_RE.match(x))], int)
    if len(run) >= 3:
        return run
    return []


def _title_after(lines, i, stop):
    """the short title lines right under a heading. Only capitals or Title Case count, so a chapter's first sentence never
    becomes its title."""
    bits = []
    for x in lines[i + 1:min(i + 7, stop)]:
        s = x.strip().strip("_*")
        if not s:
            if bits:
                break
            continue
        words = [w for w in re.findall(r"[^\W\d_]+", s)]
        capitals = sum(w[0].isupper() for w in words)
        looks_like_title = words and len(s) <= 70 and s[-1] not in ".,;:" and (s.isupper() or capitals >= max(1, len(words) * 0.6))
        if not looks_like_title:
            break
        bits.append(s)
        if not s.isupper():
            break
    return " ".join(bits)[:90]


def _is_contents_line(line):
    """dot leaders or a trailing page number after a gap: 'Chapter 4 ........ 37'"""
    return bool(re.search(r"\.{3,}\s*\d*\s*$|\s{3,}\d{1,4}\s*$", line))


def _heading_key(line):
    return " ".join(re.sub(r"\W+", " ", line).lower().split()[:2])


def _drop_contents_page(lines, heads):
    """A contents page is a run of headings with next to nothing between them. Its last entry can look like a real chapter,
    because the preface follows it. Real chapter one, though, was already listed in the run, so that is how to tell them
    apart. A section too short to stand alone simply stays part of the one before it."""
    kept, run, listed = [], 0, set()
    for k, (i, title) in enumerate(heads):
        stop = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        words = len(" ".join(lines[i + 1:stop]).split())
        key = _heading_key(lines[i])
        if _is_contents_line(lines[i]) or words < 12:
            run += 1
            listed.add(key)
            continue
        if run >= 3 and key not in listed:
            run = 0
            listed.add(key)
            continue
        run = 0
        if words >= MIN_CHAPTER_WORDS:
            kept.append((i, title))
    return kept


def split_chapters(text, heading_regex=None):
    """-> [{"title", "text"}], with anything before the first heading as front matter at index 0"""
    text = strip_boilerplate(text)
    lines = text.split("\n")
    heads = find_headings(lines, heading_regex)
    chunks = []
    heads = _drop_contents_page(lines, heads) if heads else heads
    if heads:
        front = "\n".join(lines[:heads[0][0]]).strip()
        if len(front.split()) >= 40:
            chunks.append({"title": "Front matter", "text": front, "front": True})
        for k, (i, title) in enumerate(heads):
            stop = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
            heading = lines[i].strip()
            name = title or _title_after(lines, i, stop)
            heading = re.sub(r"[\s.:\-\u2014\u2013]+$", "", heading)
            label = f"{heading}: {name}" if name and not MARKDOWN_RE.match(lines[i]) else (name or heading)
            chunks.append({"title": label[:110], "text": "\n".join(lines[i:stop]).strip()})
        return chunks
    # no headings: even parts, cut at paragraph breaks
    paragraphs, part, count = re.split(r"\n\s*\n", text.strip()), [], 0
    for para in paragraphs:
        part.append(para)
        count += len(para.split())
        if count >= EVEN_PART_WORDS:
            chunks.append({"title": f"Part {len(chunks) + 1}", "text": "\n\n".join(part)})
            part, count = [], 0
    if part:
        chunks.append({"title": f"Part {len(chunks) + 1}", "text": "\n\n".join(part)})
    return chunks


def ingest(p, book_path, heading_regex=None):
    """write source/book.txt, source/chapters/chNN.txt (ch00 = front matter) and source/chapters.json"""
    book_path = Path(book_path)
    src = p.root / "source"
    (src / "chapters").mkdir(parents=True, exist_ok=True)
    text, meta = read_book(book_path)
    if not text.strip():
        raise SystemExit(f"{book_path} has no readable text")
    (src / "book.txt").write_text(text)
    chunks = split_chapters(text, heading_regex)
    for old in (src / "chapters").glob("ch*.txt"):
        old.unlink()
    index, n = [], 1
    for c in chunks:
        number = 0 if c.get("front") else n
        n += 0 if c.get("front") else 1
        tag = f"ch{number:02d}"
        (src / "chapters" / f"{tag}.txt").write_text(c["text"] + "\n")
        index.append({"chapter": number, "file": f"source/chapters/{tag}.txt", "title": c["title"], "words": len(c["text"].split())})
    (src / "chapters.json").write_text(json.dumps(index, indent=1, ensure_ascii=False))
    return index, meta
