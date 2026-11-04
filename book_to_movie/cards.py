"""Card scenes (title, chapter, section, quote, words, portrait, close) written automatically from a chapter's CARDS table.
Every card is a sheet of engraved paper with guilloche line-work that draws itself in, the way banknotes and old title
pages are made."""
import difflib
import json
import shutil

from .engrave import engrave
from .guilloche import band, rosette, spiro, svg as line_svg
from .project import norm, roman
from .svgkit import doc

FULL = [0, 0, 1920, 1080]
SHARED_FILES = ("paper.png", "rosette_title.svg", "rosette_core.svg", "rosette_card.svg", "frame.svg", "rules.svg", "ribbon.svg")


def build_shared(p):
    """the line-work and paper every card is made from, in this project's colours"""
    out = p.film / "assets" / "art" / "_cards"
    if (out / "ribbon.svg").exists() and (out / "paper.png").exists():
        return out
    out.mkdir(parents=True, exist_ok=True)
    W, H, line, paper = 1920, 1080, p.look["line"], p.look["paper"]

    def write(name, text):
        (out / name).write_text(text)

    big = rosette(960, 540, 250, 470, lobes=24, strands=30, n=1400, amp2=0.22) + rosette(960, 540, 120, 255, lobes=16, strands=22, n=1000)
    write("rosette_title.svg", line_svg(big, W, H, stroke=line, width=0.75, opacity=0.5))
    inner = spiro(960, 540, 120, 45, 52, n=5000) + spiro(960, 540, 100, 35, 30, n=4000, rot=0.3)
    write("rosette_core.svg", line_svg(inner, W, H, stroke=line, width=0.7, opacity=0.55))
    small = rosette(960, 470, 150, 300, lobes=20, strands=26, n=1100, amp2=0.2)
    write("rosette_card.svg", line_svg(small, W, H, stroke=line, width=0.7, opacity=0.42))

    def border(x, y, w, h, bh=20, strands=7, wpp=1 / 26):
        d = band(x + 40, x + w - 40, y, bh, waves=int((w - 80) * wpp), strands=strands)
        d += band(x + 40, x + w - 40, y + h, bh, waves=int((w - 80) * wpp), strands=strands)
        d += band(y + 40, y + h - 40, x, bh, waves=int((h - 80) * wpp), strands=strands, vertical=True)
        d += band(y + 40, y + h - 40, x + w, bh, waves=int((h - 80) * wpp), strands=strands, vertical=True)
        for cx, cy in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
            d += rosette(cx, cy, 14, 40, lobes=10, strands=12, n=420)
        return d

    write("frame.svg", line_svg(border(84, 70, 1752, 940), W, H, stroke=line, width=0.7, opacity=0.62))
    rules = (f'<g fill="none" stroke="{line}" stroke-opacity="0.7"><rect x="120" y="106" width="1680" height="868" stroke-width="1.6"/>'
             f'<rect x="129" y="115" width="1662" height="850" stroke-width="0.7"/></g>')
    write("rules.svg", f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">{rules}</svg>')
    ribbon = (f'<rect x="200" y="338" width="1520" height="324" fill="{paper}" fill-opacity="0.93"/>'
              f'<g fill="none" stroke="{line}" stroke-opacity="0.75"><path d="M200,338 L1720,338 M200,662 L1720,662" stroke-width="1.6"/>'
              f'<path d="M200,347 L1720,347 M200,653 L1720,653" stroke-width="0.7"/></g>')
    write("ribbon.svg", f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">{ribbon}</svg>')
    sheet = out / "paper.svg"
    sheet.write_text(doc(2112, 1188, '<rect width="2112" height="1188" fill="#ffffff" data-h="paper"/>'))
    engrave(str(sheet), str(out / "paper.png"), paper=paper, ink=p.look["ink"])
    sheet.unlink()
    return out


def quote_top(text, size, width, attr=True, centre=540):
    """the top of a quote slip so it sits centred: lines estimated from an average character of 0.45 em"""
    per_line = max(1, int((width - 104) / (size * 0.45)))
    lines = -(-len(text) // per_line)
    height = 84 + lines * size * 1.32 + (48 if attr else 0)
    return max(120, int(centre - height / 2))


def fit_size(text, largest, width=1420, smallest=46):
    """a title size that keeps the words inside the ribbon. Cinzel caps with tracking run about 0.84 em a character.
    One line if it can stay large, otherwise two or three shorter ones."""
    length = max(1, len(text)) * 0.84
    one_line = width / length
    if one_line >= 64:
        return int(min(largest, one_line))
    two_lines = width / (length / 1.8)
    if two_lines >= 56:
        return int(min(72, two_lines))
    return int(max(smallest, width / (length / 2.7)))


class ChapterCards:
    def __init__(self, p, ch):
        self.p, self.ch = p, ch
        self.mod = p.module(ch)
        self.number = int(ch[2:])
        self.tm = p.timing(ch)
        self.dst = p.art_assets(ch, "cards")
        shared = build_shared(p)
        for f in SHARED_FILES:
            if not (self.dst / f).exists():
                shutil.copyfile(shared / f, self.dst / f)

    def corners(self, num):
        """the four corner rosettes with the chapter's numeral"""
        name = f"corners_{num}.svg"
        if not (self.dst / name).exists():
            line = self.p.look["line"]
            pts = ((250, 230), (1670, 230), (250, 850), (1670, 850))
            paths = []
            for cx, cy in pts:
                paths += rosette(cx, cy, 34, 74, lobes=14, strands=16, n=600)
            size = 50 if len(num) <= 2 else (40 if len(num) == 3 else (32 if len(num) <= 5 else 25))
            txt = "".join(f'<text x="{cx}" y="{cy + size * 0.36:.0f}" text-anchor="middle" font-family="Cinzel" font-weight="700" '
                          f'font-size="{size}" fill="{line}" fill-opacity="0.85">{num}</text>' for cx, cy in pts)
            (self.dst / name).write_text(line_svg(paths, 1920, 1080, stroke=line, width=0.7, opacity=0.55).replace("</svg>", txt + "</svg>"))
        return name

    def spoken_at(self, sid, text, default=1.0, min_ratio=0.0):
        """scene time at which the words of `text` start being spoken"""
        words = self.p.words(self.ch, sid)
        q = [norm(x) for x in text.split()]
        sm = difflib.SequenceMatcher(None, q, [norm(x["w"]) for x in words], autojunk=False)
        blocks = [b for b in sm.get_matching_blocks() if b.size]
        if not blocks or sum(b.size for b in blocks) / max(1, len(q)) < min_ratio:
            return default
        return round(self.tm[sid]["vo_offset"] + words[blocks[0].b]["s"], 3)

    def base(self, corner_name, title_at, draw_end=2.2):
        return [{"src": "paper.png", "z": 0.0},
                {"svg": "rosette_card.svg", "box": FULL, "z": 0.1, "spin": {"speed": 1.4, "origin": [960, 470]},
                 "draw": [{"t": 0.0, "p": 0}, {"t": draw_end + 0.6, "p": 1, "ease": "power2.inOut"}]},
                {"svg": "frame.svg", "box": FULL, "z": 0.05, "draw": [{"t": 0.1, "p": 0}, {"t": draw_end, "p": 1, "ease": "power2.inOut"}]},
                {"svg": corner_name, "box": FULL, "z": 0.05, "draw": [{"t": 0.3, "p": 0}, {"t": draw_end, "p": 1, "ease": "power2.out"}]},
                {"svg": "ribbon.svg", "box": FULL, "z": 0.08, "move": [{"t": 0, "o": 0}, {"t": title_at, "o": 0}, {"t": title_at + 0.6, "o": 1}]}]

    def spec(self, sid, c, story_no):
        kind = c["kind"]
        camera = [{"t": 0, "zoom": 1.0}, {"t": "end", "zoom": 1.035, "ease": "sine.inOut"}]
        fx = []
        if kind == "title":     # the film's opening card
            at = min(2.3, max(0.8, self.tm[sid]["duration"] * 0.2))
            layers = [{"src": "paper.png", "z": 0.0},
                      {"svg": "rosette_title.svg", "box": FULL, "z": 0.12, "spin": {"speed": 1.0, "origin": [960, 540]},
                       "draw": [{"t": 0.2, "p": 0}, {"t": at + 1.9, "p": 1, "ease": "power2.inOut"}]},
                      {"svg": "rosette_core.svg", "box": FULL, "z": 0.12, "spin": {"speed": -2.0, "origin": [960, 540]},
                       "draw": [{"t": 0.8, "p": 0}, {"t": at + 2.5, "p": 1, "ease": "power2.inOut"}]},
                      {"svg": "frame.svg", "box": FULL, "z": 0.04, "draw": [{"t": 0.0, "p": 0}, {"t": at + 0.7, "p": 1, "ease": "power2.inOut"}]},
                      {"svg": "rules.svg", "box": FULL, "z": 0.04, "draw": [{"t": 0.6, "p": 0}, {"t": at + 0.3, "p": 1, "ease": "power2.inOut"}]},
                      {"svg": "ribbon.svg", "box": FULL, "z": 0.08, "move": [{"t": 0, "o": 0}, {"t": at - 0.4, "o": 0}, {"t": at + 0.3, "o": 1}]}]
            text = [{"type": "title", "eyebrow": c.get("eyebrow", ""), "text": c["title"], "sub": c.get("sub"), "at": at, "y": 372,
                     "size": fit_size(c["title"], 94)}]
            camera = [{"t": 0, "zoom": 1.06}, {"t": "end", "zoom": 1.0, "ease": "sine.out"}]
            fx = [{"type": "fade", "color": "#120d09", "keys": [{"t": 0, "o": 1}, {"t": 1.4, "o": 0, "ease": "power2.out"}]}]
        elif kind == "chapter":
            at = 0.6
            layers = self.base(self.corners(roman(self.number)), at)
            text = [{"type": "title", "eyebrow": c.get("eyebrow", ""), "text": c["title"], "sub": c.get("sub"), "at": at,
                     "y": 372 if c.get("sub") else 404, "size": fit_size(c["title"], 112)}]
            if c.get("step"):
                text.append({"type": "caption", "text": c["step"], "box": [0, 700, 1920], "size": 28, "at": at + 0.8})
        elif kind == "section":
            at = 0.7
            layers = self.base(self.corners(roman(story_no)), at)
            text = [{"type": "title", "eyebrow": c.get("eyebrow", ""), "text": c["title"], "sub": c.get("sub"), "at": at,
                     "y": 372 if c.get("sub") else 404, "size": fit_size(c["title"], 104)}]
        elif kind in ("quote", "portrait"):
            q = c.get("text") or c.get("quote", "")
            t0 = self.spoken_at(sid, q)
            n = len(q.split())
            size = 52 if n < 30 else (44 if n < 50 else 38)
            if kind == "quote":
                layers = [{"src": "paper.png", "z": 0.0},
                          {"svg": "rosette_title.svg", "box": FULL, "z": 0.12, "opacity": 0.55, "spin": {"speed": 0.9, "origin": [960, 540]}},
                          {"svg": "frame.svg", "box": FULL, "z": 0.04, "opacity": 0.7}]
                text = [{"type": "quote", "text": q, "attr": c.get("attr", ""), "box": [330, quote_top(q, size, 1260, bool(c.get("attr"))), 1260], "size": size,
                         "at": max(0.3, t0 - 0.6)}]
            else:
                person = c["person"]
                slug = norm(person)
                portrait = self.dst.parent / "portraits" / f"{slug}.png"
                if not portrait.exists():
                    print(f"  {sid}: no portrait of {person} yet. Find a public-domain photo on Wikimedia Commons, then run: "
                          f"./movie portrait {self.ch} {slug} \"File:Name_on_Commons.jpg\"")
                layers = [{"src": "paper.png", "z": 0.0},
                          {"svg": "rosette_title.svg", "box": [-440, 0, 1920, 1080], "z": 0.12, "opacity": 0.7,
                           "spin": {"speed": 1.0, "origin": [960, 540]}},
                          {"src": f"../portraits/{slug}.png", "box": [200, 120, 640, 800], "z": 0.3,
                           "move": [{"t": 0, "s": 1.0}, {"t": "end", "s": 1.035, "ease": "sine.inOut"}], "origin": [320, 400]}]
                text = [{"type": "caption", "text": person.upper(), "box": [200, 950, 640], "size": 26, "at": 0.3},
                        {"type": "quote", "text": q, "attr": person, "box": [930, quote_top(q, size - 2, 830), 830], "size": size - 2,
                         "at": max(0.3, t0 - 0.6)}]
        elif kind == "words":
            t0 = self.spoken_at(sid, c["text"])
            n = len(c["text"].split())
            layers = [{"src": "paper.png", "z": 0.0},
                      {"svg": "rosette_card.svg", "box": FULL, "z": 0.1, "opacity": 0.75, "spin": {"speed": 1.2, "origin": [960, 470]}}]
            text = [{"type": "words", "text": c["text"], "box": [210, 380 if n > 8 else 430, 1500], "size": 88 if n <= 8 else 70,
                     "at": max(0.2, t0 - 0.1)}]
        elif kind == "close":
            t_title = self.spoken_at(sid, c["title"])
            end_vo = self.tm[sid]["vo_offset"] + self.tm[sid]["vo_duration"]
            next_title = c.get("next_title", "")
            t_next = self.spoken_at(sid, next_title, default=end_vo - 0.6, min_ratio=0.6) if next_title else end_vo
            t_next = max(t_next - 0.2, t_title + 1.5)
            numeral = roman(self.number + 1) if next_title and str(c.get("next_eyebrow", "")).upper().startswith("NEXT") else roman(self.number)
            layers = [{"src": "paper.png", "z": 0.0},
                      {"svg": "rosette_title.svg", "box": FULL, "z": 0.12, "spin": {"speed": 0.8, "origin": [960, 540]},
                       "draw": [{"t": 0.5, "p": 0}, {"t": t_title + 0.4, "p": 1, "ease": "sine.inOut"}]},
                      {"svg": "rosette_core.svg", "box": FULL, "z": 0.12, "spin": {"speed": -1.6, "origin": [960, 540]},
                       "draw": [{"t": max(0.6, t_title - 4.0), "p": 0}, {"t": t_title + 0.4, "p": 1, "ease": "sine.inOut"}]},
                      {"svg": "frame.svg", "box": FULL, "z": 0.04, "draw": [{"t": t_next - 1.0, "p": 0}, {"t": t_next + 1.6, "p": 1, "ease": "power2.out"}]},
                      {"svg": self.corners(numeral), "box": FULL, "z": 0.04,
                       "draw": [{"t": t_next - 0.6, "p": 0}, {"t": t_next + 1.8, "p": 1, "ease": "power2.out"}]},
                      {"svg": "ribbon.svg", "box": FULL, "z": 0.08, "move": [{"t": 0, "o": 0}, {"t": t_title - 0.4, "o": 0}, {"t": t_title + 0.3, "o": 1}]}]
            text = [{"type": "title", "text": c["title"], "at": t_title, "until": t_next - 0.2 if next_title else "end", "y": 452,
                     "size": fit_size(c["title"], 96)}]
            if next_title:
                text.append({"type": "title", "eyebrow": c.get("next_eyebrow", ""), "text": next_title, "sub": c.get("next_sub"),
                             "at": t_next, "y": 372, "size": fit_size(next_title, 120)})
            camera = [{"t": 0, "zoom": 1.08}, {"t": "end", "zoom": 1.0, "ease": "sine.inOut"}]
        else:
            raise SystemExit(f"{sid}: unknown card kind {kind!r}. Use title, chapter, section, quote, words, portrait or close.")
        return {"id": sid, "set": "cards", "background": self.p.look["paper"], "layers": layers, "camera": camera, "fx": fx, "text": text}


def cards_chapter(p, ch):
    cc = ChapterCards(p, ch)
    cards = getattr(cc.mod, "CARDS", {})
    story_no, n = 1, 0
    for sid, art, _ in cc.mod.S:
        if not art.startswith("card:"):
            continue
        if sid not in cards:
            raise SystemExit(f"{sid} is a card scene but has no entry in CARDS")
        if cards[sid]["kind"] == "section":
            story_no += 1
        (p.specs(ch) / f"{sid}.json").write_text(json.dumps(cc.spec(sid, cards[sid], story_no), indent=1))
        n += 1
    print(f"  {ch}: {n} card specs")
