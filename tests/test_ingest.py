"""Finding chapters is the first thing a new user sees work or fail."""
import zipfile

import pytest

from book_to_movie.ingest import clean_pdf_text, read_book, split_chapters, strip_boilerplate

BODY = " ".join(["word"] * 400)


def chapter(n, title=""):
    return f"CHAPTER {n}\n{title}\n\n{BODY}\n\n"


def titles(chunks):
    return [c["title"] for c in chunks]


def test_plain_chapters():
    chunks = split_chapters("".join(chapter(i) for i in range(1, 4)))
    assert len(chunks) == 3
    assert titles(chunks)[0].startswith("CHAPTER 1")


def test_front_matter_is_kept_apart():
    front = " ".join(["preface"] * 100)
    chunks = split_chapters(front + "\n\n" + chapter(1) + chapter(2))
    assert chunks[0].get("front")
    assert len(chunks) == 3


def test_contents_page_with_dot_leaders_is_not_chapters():
    toc = "".join(f"CHAPTER {i} ........ {i * 10}\n" for i in range(1, 6))
    preface = " ".join(["preface"] * 800)
    chunks = split_chapters(toc + "\n" + preface + "\n\n" + "".join(chapter(i) for i in range(1, 6)))
    numbered = [c for c in chunks if not c.get("front")]
    assert len(numbered) == 5
    assert numbered[0]["title"].startswith("CHAPTER 1")


def test_contents_page_without_leaders_last_entry_followed_by_preface():
    """the bug that made a contents line look like a chapter: its last entry is followed by the long preface"""
    toc = "".join(f"CHAPTER {i}\n" for i in range(1, 6))
    preface = " ".join(["preface"] * 800)
    chunks = split_chapters(toc + preface + "\n\n" + "".join(chapter(i) for i in range(1, 6)))
    numbered = [c for c in chunks if not c.get("front")]
    assert len(numbered) == 5
    assert numbered[0]["title"].startswith("CHAPTER 1")
    assert "preface" in chunks[0]["text"]


def test_contents_page_then_real_first_chapter_is_kept():
    toc = "".join(f"Chapter {i}\n" for i in range(1, 25))
    chunks = split_chapters(toc + "\n" + "".join(f"Chapter {i}\n\n{BODY}\n\n" for i in range(1, 4)))
    assert len([c for c in chunks if not c.get("front")]) == 3


def test_letters_and_chapters_mix():
    text = "".join(f"Letter {i}\n\n{BODY}\n\n" for i in range(1, 3)) + "".join(f"Chapter {i}\n\n{BODY}\n\n" for i in range(1, 3))
    assert len(split_chapters(text)) == 4


def test_roman_numerals_and_words():
    assert len(split_chapters(f"CHAPTER I.\n\n{BODY}\n\nCHAPTER II.\n\n{BODY}\n\nCHAPTER III.\n\n{BODY}")) == 3
    assert len(split_chapters(f"Chapter One\n\n{BODY}\n\nChapter Two\n\n{BODY}")) == 2
    assert len(split_chapters(f"Chapter Twenty-One\n\n{BODY}\n\nChapter Twenty-Two\n\n{BODY}")) == 2


def test_bare_numerals_must_run_in_order():
    text = "".join(f"{r}\n\n{BODY}\n\n" for r in ("I", "II", "III", "IV"))
    assert len(split_chapters(text)) == 4
    # stray roman-looking lines out of order are not a chapter sequence
    assert len(split_chapters(f"X\n\n{BODY}\n\nC\n\n{BODY}\n\nV\n\n{BODY}")) == 1


def test_markdown_headings():
    assert len(split_chapters(f"# Book\n\n## One\n\n{BODY}\n\n## Two\n\n{BODY}\n\n## Three\n\n{BODY}")) >= 3


def test_titles_never_swallow_the_first_sentence():
    chunks = split_chapters(f"Chapter 1\n\nI am by birth a Genevese, and my family is one of the most\n{BODY}\n\nChapter 2\n\n{BODY}")
    assert "Genevese" not in chunks[0]["title"]


def test_title_lines_in_capitals_are_used():
    chunks = split_chapters(f"CHAPTER 2\nDESIRE\nTHE STARTING POINT\n\n{BODY}\n\nCHAPTER 3\nFAITH\n\n{BODY}")
    assert "DESIRE" in chunks[0]["title"] and "THE STARTING POINT" in chunks[0]["title"]


def test_no_headings_makes_even_parts():
    text = "\n\n".join(" ".join(["para"] * 500) for _ in range(20))
    chunks = split_chapters(text)
    assert len(chunks) >= 2
    assert chunks[0]["title"] == "Part 1"
    assert sum(len(c["text"].split()) for c in chunks) == 10000


def test_custom_heading_regex():
    text = f"FABLE: one\n\n{BODY}\n\nFABLE: two\n\n{BODY}"
    assert len(split_chapters(text, heading_regex=r"^FABLE:")) == 2


def test_nothing_is_lost():
    front = " ".join(["front"] * 100)
    text = front + "\n\n" + "".join(chapter(i) for i in range(1, 4))
    assert sum(len(c["text"].split()) for c in split_chapters(text)) == len(text.split())


def test_gutenberg_licence_is_removed():
    t = "licence words\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\nthe book\n*** END OF THE PROJECT GUTENBERG EBOOK X ***\nmore licence"
    assert strip_boilerplate(t).strip() == "the book"


def test_pdf_page_furniture_is_removed():
    pages = [f"THE RUNNING HEADER\nopening line {'abcdefghijklmnop'[i]} of the page\nthe middle of page {'abcdefghijklmnop'[i]} has a word bro-\nken across lines\n"
             f"and a closing line {'abcdefghijklmnop'[i]} here\nthe last words {'abcdefghijklmnop'[i]} too\n{i + 1}\n" for i in range(12)]
    out = clean_pdf_text("\f".join(pages))
    assert "THE RUNNING HEADER" not in out
    assert "broken across lines" in out
    assert "opening line c of the page" in out
    assert "\n7\n" not in out


def test_read_txt_and_markdown(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    assert read_book(tmp_path / "a.txt")[0] == "hello"


def test_read_html(tmp_path):
    (tmp_path / "a.html").write_text("<html><head><style>x{}</style><title>t</title></head><body><h1>One</h1><p>two &amp; three</p><script>no()</script></body></html>")
    text, _ = read_book(tmp_path / "a.html")
    assert "One" in text and "two & three" in text and "no()" not in text and "x{}" not in text


def test_read_epub_in_spine_order_with_metadata(tmp_path):
    path = tmp_path / "b.epub"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("META-INF/container.xml", '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                   '<rootfile full-path="OEBPS/c.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr("OEBPS/c.opf", '<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                   '<dc:title>A Title</dc:title><dc:creator>An Author</dc:creator></metadata><manifest>'
                   '<item id="a" href="second.xhtml" media-type="application/xhtml+xml"/><item id="b" href="first.xhtml" media-type="application/xhtml+xml"/>'
                   '</manifest><spine><itemref idref="b"/><itemref idref="a"/></spine></package>')
        z.writestr("OEBPS/first.xhtml", "<html><body><p>first part</p></body></html>")
        z.writestr("OEBPS/second.xhtml", "<html><body><p>second part</p></body></html>")
    text, meta = read_book(path)
    assert text.index("first part") < text.index("second part")
    assert meta == {"title": "A Title", "author": "An Author"}


def test_read_docx(tmp_path):
    path = tmp_path / "d.docx"
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f'<w:document {w}><w:body><w:p><w:r><w:t>one </w:t></w:r><w:r><w:t>line</w:t></w:r></w:p><w:p><w:r><w:t>two</w:t></w:r></w:p></w:body></w:document>')
    assert read_book(path)[0] == "one line\n\ntwo"


def test_unknown_format_says_what_works(tmp_path):
    (tmp_path / "a.xyz").write_text("x")
    with pytest.raises(SystemExit, match="pdf"):
        read_book(tmp_path / "a.xyz")
