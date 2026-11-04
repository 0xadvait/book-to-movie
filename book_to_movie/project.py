"""A movie project: one folder holding a book and everything made from it.

    projects/<slug>/
      movie.json                 title, voice, look, music on/off
      TREATMENT.md               the plan: which story each part of the film tells
      source/                    the book, its plain text, chapters/chNN.txt, pd/ (public-domain images)
      story/chNN.py              one part of the film: scenes, narration, art plan, sound plan
      story/specs/chNN/          _timing.json, _scenes.md, <scene>.json (how each scene moves)
      art/chNN/<set>/build.py    the drawings, as code
      audio/{voice,sfx,music,mix}/
      film/                      the HyperFrames project: assets/, scenes/, renders/
      build/                     check frames, logs and scratch files (safe to delete)
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROJECTS = REPO / "projects"
ASSETS = Path(__file__).resolve().parent / "assets"

STAGE_W, STAGE_H = 1920, 1080
HYPERFRAMES = os.environ.get("HYPERFRAMES_VERSION", "0.8.172")

DEFAULTS = {
    "title": "Untitled",
    "author": "",
    "language": "en",
    "period": "",
    "look": "sepia",
    "fonts": {"display": "Cinzel", "body": "IM Fell English"},
    # speed + tempo = about 175-180 spoken words a minute. A calm audiobook pace drags on film.
    "voice": {"provider": "auto", "name": "Bill", "model": "v2", "speed": 1.12, "tempo": 1.07, "respell": {}},
    "whisper": "large-v3-turbo",
    "music": False,
    "sfx": True,
    "fps": 24,
}

# Ink on paper. Anything not given is mixed from these three.
LOOKS = {
    "sepia": {"paper": "#efe7d4", "ink": "#211b18", "accent": "#8e2a1f",
              "ink_soft": "#4a3d32", "ink_mute": "#5a4a3c", "line": "#4a3b2f"},
    "noir": {"paper": "#e9e7e2", "ink": "#131417", "accent": "#a51f1b"},
    "indigo": {"paper": "#eef0ea", "ink": "#172658", "accent": "#b4472b"},
    "forest": {"paper": "#ece9d8", "ink": "#1b2a1f", "accent": "#a0591b"},
    "oxblood": {"paper": "#f1e7d9", "ink": "#3b1411", "accent": "#20406a"},
}


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_hex(c):
    return "#" + "".join(f"{max(0, min(255, int(round(v)))):02x}" for v in c)


def mix_hex(a, b, t):
    """a blended toward b by t (0..1)"""
    ca, cb = hex_rgb(a), hex_rgb(b)
    return rgb_hex([x + (y - x) * t for x, y in zip(ca, cb)])


def resolve_look(look):
    """a palette name or {"paper", "ink", "accent"} -> the full palette"""
    base = dict(LOOKS[look]) if isinstance(look, str) else dict(look)
    missing = {"paper", "ink"} - set(base)
    if missing:
        raise SystemExit(f"look needs {sorted(missing)}; named looks are {sorted(LOOKS)}")
    base.setdefault("accent", "#8e2a1f")
    base.setdefault("ink_soft", mix_hex(base["ink"], base["paper"], 0.2))
    base.setdefault("ink_mute", mix_hex(base["ink"], base["paper"], 0.28))
    base.setdefault("line", mix_hex(base["ink"], base["paper"], 0.16))
    base.setdefault("slip", mix_hex(base["paper"], "#ffffff", 0.2))
    base.setdefault("shade", mix_hex(base["ink"], "#000000", 0.25))
    return base


def norm(word):
    """a word reduced to its letters and digits, in any alphabet, so script and transcript can be compared"""
    w = unicodedata.normalize("NFKD", word.lower())
    w = "".join(c for c in w if not unicodedata.combining(c))
    return re.sub(r"[\W_]+", "", w, flags=re.UNICODE)


def parse_cue(value):
    """'cue:word', 'cue:word#2', 'cue:word+0.4', 'cue:fifty-cent#2-0.5' -> (word, nth, shift)"""
    m = re.fullmatch(r"cue:(.+?)(?:#(\d+))?([+\-]\d[\d.]*)?", value)
    if not m:
        raise ValueError(f"bad time {value!r}: expected seconds, 'end' or 'cue:word[#n][+/-sec]'")
    return norm(m.group(1)), int(m.group(2) or 1), float(m.group(3) or 0)


def cue_seconds(value, words, vo_offset):
    """scene time of a narration cue"""
    word, nth, shift = parse_cue(value)
    hits = [w for w in words if norm(w["w"]) == word]
    if len(hits) < nth:
        raise ValueError(f"cue {value!r}: the narration says that word {len(hits)} time(s)")
    return round(vo_offset + hits[nth - 1]["s"] + shift, 3)


def chapter_tag(n):
    """1, '1', '01' or 'ch01' -> 'ch01'"""
    s = str(n).lower().removeprefix("ch")
    if not s.isdigit():
        raise SystemExit(f"bad chapter {n!r}: use a number like 1 or ch01")
    return f"ch{int(s):02d}"


def roman(n):
    out = ""
    for v, s in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
                 (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out += s
            n -= v
    return out


def slugify(text):
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-") or "movie"


def load_env():
    """read .env from the repo root. Real environment variables win. Keys stay in memory and are never written out."""
    path = REPO / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip().removeprefix("export ").strip(), v.strip().strip("'\"")
            if v:
                os.environ.setdefault(k, v)


def fal_key():
    return os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY")


def elevenlabs_key():
    return os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_API_KEY")


def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    if r.returncode or not r.stdout.strip():
        raise SystemExit(f"cannot read the duration of {path}: {r.stderr.strip()[:200]}")
    return float(r.stdout)


def tail(path, lines=20):
    try:
        return "\n".join(Path(path).read_text(errors="replace").splitlines()[-lines:])
    except OSError:
        return ""


class Project:
    def __init__(self, root):
        self.root = Path(root).resolve()
        cfg_path = self.root / "movie.json"
        if not cfg_path.exists():
            raise SystemExit(f"{self.root} is not a movie project (no movie.json). Start one with: ./movie new <book>")
        user = json.loads(cfg_path.read_text())
        self.cfg = {**DEFAULTS, **user}
        self.cfg["voice"] = {**DEFAULTS["voice"], **user.get("voice", {})}
        self.cfg["fonts"] = {**DEFAULTS["fonts"], **user.get("fonts", {})}
        self.slug = self.root.name
        self.look = resolve_look(self.cfg["look"])
        self.fps = self.cfg["fps"]

    # ---- places ----
    @property
    def film(self):
        return self.root / "film"

    @property
    def build(self):
        return self.root / "build"

    def qa(self):
        d = self.build / "qa"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def tmp(self, name="tmp"):
        d = self.build / "tmp" / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def logs(self):
        d = self.build / "logs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def voice_dir(self, ch):
        d = self.root / "audio" / "voice" / ch
        d.mkdir(parents=True, exist_ok=True)
        return d

    def sfx_dir(self, ch):
        d = self.root / "audio" / "sfx" / ch
        d.mkdir(parents=True, exist_ok=True)
        return d

    def music_dir(self, ch):
        d = self.root / "audio" / "music" / ch
        d.mkdir(parents=True, exist_ok=True)
        return d

    def mix_dir(self):
        d = self.root / "audio" / "mix"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def specs(self, ch):
        d = self.root / "story" / "specs" / ch
        d.mkdir(parents=True, exist_ok=True)
        return d

    def art_dir(self, ch, set_name=None):
        d = self.root / "art" / ch
        return d / set_name if set_name else d

    def art_assets(self, ch, set_name):
        d = self.film / "assets" / "art" / ch / set_name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def scenes_dir(self, ch):
        d = self.film / "scenes" / ch
        d.mkdir(parents=True, exist_ok=True)
        return d

    def renders_dir(self, ch):
        d = self.film / "renders" / ch
        d.mkdir(parents=True, exist_ok=True)
        return d

    def master(self, ch, suffix=""):
        return self.film / "renders" / f"{self.slug}-{ch}{suffix}.mp4"

    # ---- the story ----
    def chapters(self):
        """every part of the film that has a script, in order"""
        return sorted(p.stem for p in (self.root / "story").glob("ch[0-9]*.py"))

    def module(self, ch):
        path = self.root / "story" / f"{ch}.py"
        if not path.exists():
            raise SystemExit(f"no script for {ch}: expected {path}")
        spec = importlib.util.spec_from_file_location(f"movie_story_{self.slug.replace('-', '_')}_{ch}", path)
        mod = importlib.util.module_from_spec(spec)
        sys.dont_write_bytecode, before = True, sys.dont_write_bytecode
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.dont_write_bytecode = before
        return mod

    def timing(self, ch):
        path = self.specs(ch) / "_timing.json"
        if not path.exists():
            raise SystemExit(f"no timing for {ch} yet. Run: ./movie voice {ch}")
        return json.loads(path.read_text())

    def words(self, ch, sid):
        path = self.voice_dir(ch) / f"{sid}.words.json"
        return json.loads(path.read_text())["words"] if path.exists() else []

    # ---- the film folder HyperFrames renders from ----
    def scaffold(self):
        fonts = self.film / "assets" / "fonts"
        fx = self.film / "assets" / "fx"
        fonts.mkdir(parents=True, exist_ok=True)
        fx.mkdir(parents=True, exist_ok=True)
        for f in (ASSETS / "fonts").glob("*.woff2"):
            if not (fonts / f.name).exists():
                shutil.copyfile(f, fonts / f.name)
        listing = fonts / "fonts.txt"
        if not listing.exists():
            listing.write_text((ASSETS / "fonts" / "fonts.txt").read_text())
        if not (fx / "grain.png").exists():
            shutil.copyfile(ASSETS / "grain.png", fx / "grain.png")
        (self.film / "package.json").write_text(json.dumps(
            {"name": f"{self.slug}-film", "private": True, "type": "module"}, indent=2) + "\n")
        (self.film / "hyperframes.json").write_text(json.dumps({
            "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
            "paths": {"assets": "assets"}, "media": {"autoProxy": True}}, indent=2) + "\n")
        (self.film / "meta.json").write_text(json.dumps({"id": self.slug, "name": self.slug}, indent=2) + "\n")
        return self


def find_project(explicit=None):
    """--project, then $MOVIE_PROJECT, then the folder you are in, then the last one used, then the only one"""
    load_env()
    target = explicit or os.environ.get("MOVIE_PROJECT")
    if target:
        p = Path(target)
        return Project(p if (p / "movie.json").exists() else PROJECTS / target)
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / "movie.json").exists():
            return Project(d)
    current = PROJECTS / ".current"
    if current.exists() and (PROJECTS / current.read_text().strip() / "movie.json").exists():
        return Project(PROJECTS / current.read_text().strip())
    found = [d for d in PROJECTS.glob("*") if (d / "movie.json").exists()] if PROJECTS.exists() else []
    if len(found) == 1:
        return Project(found[0])
    if found:
        raise SystemExit("several projects here, pick one: ./movie use <name>  ("
                         + ", ".join(sorted(d.name for d in found)) + ")")
    raise SystemExit("no project yet. Start one with: ./movie new <book>")


def set_current(slug):
    PROJECTS.mkdir(parents=True, exist_ok=True)
    (PROJECTS / ".current").write_text(slug + "\n")
