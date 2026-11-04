"""Set: one place the story visits, drawn in code as a stack of layers.

    from book_to_movie.art import Set
    from book_to_movie.svgkit import gray, lin, ridge, smooth, puff
    from book_to_movie.figures import figure

    s = Set(__file__)                      # art/chNN/<set>/build.py knows its project and chapter from its path
    s.layer("sky", '<rect .../>', defs)    # draw in stage coordinates (1920x1080); overhang the frame for the camera
    s.layer("grass", body, tile=True)      # an endless scrolling layer
    s.sprite("lantern", body, 120, 200)    # a small piece, placed with a "box" in the scene spec
    s.done()                               # engraves whatever changed and tells you where the PNGs went

Layers are full-canvas PNGs on a 2112x1188 sheet that overhangs the stage by 96 px left and right and 54 px top and
bottom, so draw inside -100..2020 x -60..1140. They come out in film/assets/art/chNN/<set>/.
"""
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .engrave import engrave, make_tileable
from .project import Project
from .svgkit import doc

W, H = 1920, 1080
CANVAS_W, CANVAS_H, OFFSET_X, OFFSET_Y = 2112, 1188, 96, 54
TILE_EXTRA = 256
OUT_SCALE = 1.25


def _engrave_job(job):
    svg, png, shadow, tile, paper, ink, pitch = job
    engrave(svg, png, scale=2.0, pitch=pitch, out_scale=OUT_SCALE, shadow=shadow, paper=paper, ink=ink)
    if tile:
        make_tileable(png, png, int(CANVAS_W * OUT_SCALE))
    return Path(png).name


def _spawn_job(job):
    """each layer engraves in its own process, so a build.py needs no __main__ guard and a crash names its layer"""
    r = subprocess.run([sys.executable, "-m", "book_to_movie.art", json.dumps(job)], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"engraving {Path(job[0]).name} failed:\n{(r.stderr or r.stdout)[-800:]}")
    return Path(job[1]).name


class Set:
    W, H = W, H

    def __init__(self, build_file, workers=None):
        here = Path(build_file).resolve().parent
        self.src, self.name, self.chapter = here, here.name, here.parent.name
        self.project = Project(here.parent.parent.parent)
        self.out = self.project.art_assets(self.chapter, self.name)
        self.workers = workers or int(os.environ.get("MOVIE_ART_WORKERS", max(1, min(4, (os.cpu_count() or 2) // 2))))
        self.items = []

    def layer(self, name, body, defs="", shadow=None, tile=False, pitch=3.6):
        """a full-canvas layer. shadow: the soft shadow it casts on what is behind it (the first layer casts none)."""
        width = CANVAS_W + (TILE_EXTRA if tile else 0)
        svg = doc(width, CANVAS_H, f'<g transform="translate({OFFSET_X},{OFFSET_Y})">{body}</g>', defs)
        if shadow is None:
            shadow = 0.0 if not self.items else 0.8
        self._add(name, svg, shadow, tile, True, pitch)
        return f"{name}.png"

    def sprite(self, name, body, w, h, defs="", shadow=0.6, pitch=3.6):
        """a small piece on its own w x h sheet. Place it with "box": [x, y, w, h] in the scene spec."""
        self._add(name, doc(w, h, body, defs), shadow, False, False, pitch)
        return f"{name}.png"

    def _add(self, name, svg, shadow, tile, full, pitch):
        (self.src / f"{name}.svg").write_text(svg)
        self.items.append({"name": name, "shadow": shadow, "tile": tile, "full": full, "pitch": pitch})

    def done(self):
        look = self.project.look
        cache = self.out / ".cache"
        cache.mkdir(exist_ok=True)
        jobs, kept = [], 0
        for it in self.items:
            svg, png = self.src / f"{it['name']}.svg", self.out / f"{it['name']}.png"
            key = hashlib.sha1(json.dumps([svg.read_text(), it["shadow"], it["tile"], it["pitch"], look["paper"], look["ink"]]).encode()).hexdigest()
            stamp = cache / it["name"]
            if png.exists() and stamp.exists() and stamp.read_text() == key:
                kept += 1
                continue
            jobs.append(((str(svg), str(png), it["shadow"], it["tile"], look["paper"], look["ink"], it["pitch"]), stamp, key))
        if jobs:
            with ThreadPoolExecutor(self.workers) as ex:
                list(ex.map(_spawn_job, [j[0] for j in jobs]))
            for _, stamp, key in jobs:
                stamp.write_text(key)
        (self.out / "layers.json").write_text(json.dumps(self.items, indent=1))
        print(f"{self.chapter}/{self.name}: {len(jobs)} engraved, {kept} unchanged -> {self.out}")


if __name__ == "__main__":
    _engrave_job(json.loads(sys.argv[1]))
