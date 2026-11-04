"""Looking at the work: a still of a set's layers composited the way the film will, and contact sheets of rendered scenes."""
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


def _load(path):
    return np.asarray(Image.open(path).convert("RGBA"), np.float32) / 255.0


def _composite(layers):
    base = None
    for L in layers:
        if base is None:
            base = L[..., :3].copy()
            continue
        a = L[..., 3]
        base = base * (1 - a[..., None]) + L[..., :3] * a[..., None]
    return base


def _finish(img):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
    img = img * (1 - 0.32 * np.clip((r - 0.55) / 0.85, 0, 1) ** 1.6)[..., None]
    g = np.random.default_rng(1).normal(0, 0.018, (h, w)).astype(np.float32)
    return np.clip(img + cv2.GaussianBlur(g, (0, 0), 0.7 * w / 1920)[..., None], 0, 1)


def preview_set(p, ch, set_name, names=None, out=None, size=1920):
    """composite full-canvas layers back to front (they already carry their baked shadows)"""
    folder = p.art_assets(ch, set_name)
    listing = folder / "layers.json"
    if names:
        paths = [folder / f"{n.removesuffix('.png')}.png" for n in names]
    elif listing.exists():
        paths = [folder / f"{it['name']}.png" for it in json.loads(listing.read_text()) if it.get("full", True)]
    else:
        raise SystemExit(f"no layers for {ch}/{set_name}: run ./movie art {ch} {set_name}")
    missing = [str(x) for x in paths if not x.exists()]
    if missing:
        raise SystemExit(f"missing layers: {missing}")
    im = Image.fromarray((_finish(_composite([_load(x) for x in paths])) * 255 + 0.5).astype(np.uint8))
    if im.width != size:
        im = im.resize((size, int(im.height * size / im.width)), Image.LANCZOS)
    out = Path(out) if out else p.qa() / f"{ch}_{set_name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    print(out)
    return out


def scene_frames(p, ch, sid, times=None):
    """three check frames from a rendered scene, for looking at with your eyes"""
    video = p.renders_dir(ch) / f"{sid}.mp4"
    d = p.timing(ch)[sid]["duration"]
    times = times or (1.0, d / 2, max(1.0, d - 1.0))
    out = []
    for t in times:
        f = p.qa() / f"{ch}_{sid}_{t:.1f}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", str(f)], check=True)
        out.append(f)
    return out


def contact_sheet(p, ch, out=None, sids=None):
    """frames at 15%, 50% and 85% of each scene, one row per scene"""
    tm = p.timing(ch)
    sids = sids or [s[0] for s in p.module(ch).S]
    rows, tile_w, tile_h = [], 640, 360
    for sid in sids:
        video = p.renders_dir(ch) / f"{sid}.mp4"
        if not video.exists():
            continue
        frames = []
        for f in (0.15, 0.5, 0.85):
            tmp = p.tmp("contact") / f"{sid}_{f}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{tm[sid]['duration'] * f:.2f}", "-i", str(video),
                            "-frames:v", "1", str(tmp)], check=True)
            frames.append(Image.open(tmp).convert("RGB").resize((tile_w, tile_h)))
        rows.append((sid, frames))
    if not rows:
        raise SystemExit(f"no rendered scenes for {ch} yet")
    sheet = Image.new("RGB", (tile_w * 3, (tile_h + 28) * len(rows)), (20, 16, 13))
    draw = ImageDraw.Draw(sheet)
    for i, (sid, frames) in enumerate(rows):
        y = i * (tile_h + 28)
        draw.text((8, y + 6), sid, fill=(240, 230, 210))
        for k, im in enumerate(frames):
            sheet.paste(im, (k * tile_w, y + 28))
    out = Path(out) if out else p.qa() / f"{ch}_contact.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(out)
    return out
