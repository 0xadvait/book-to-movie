"""Engrave a tone-coded SVG into an intaglio-style paper cutout (RGBA PNG).

The SVG is an ordinary drawing: luminance sets the ink density (black = full ink, white = bare paper) and any
colour becomes a hand-tint wash under the lines. Shapes may carry data-h (inherited by children):

    data-h="<angle>[,<pitch>[,<style>]]"   angle in degrees (0 = horizontal lines), pitch multiplier (1 = default)
    style: lines (default) | cross | contour | solid | paper
    data-h="skip"     leave the element out of the hatch map (a glow or shade drawn over other shapes)

Lines swell with darkness, cross-hatch past mid-tone and close up to solid ink in the deepest shadows. A cut
margin of bare paper can be left around the drawing so each layer reads as a piece cut from an engraved sheet.
"""
import hashlib
import io
import os
import re
import subprocess
import sys

import cv2
import numpy as np
from lxml import etree
from PIL import Image
from scipy import ndimage

from .project import hex_rgb

PAPER = np.array([239, 231, 212], np.float32) / 255.0
INK = np.array([33, 27, 24], np.float32) / 255.0
STYLES = {"lines": 0, "cross": 1, "contour": 2, "solid": 3, "paper": 4}
SVGNS = "http://www.w3.org/2000/svg"


def palette(paper=None, ink=None):
    p = np.array(hex_rgb(paper), np.float32) / 255.0 if paper else PAPER
    i = np.array(hex_rgb(ink), np.float32) / 255.0 if ink else INK
    return p, i


def rsvg(svg_bytes, scale):
    try:
        r = subprocess.run(["rsvg-convert", "-z", str(scale), "-f", "png"], input=svg_bytes, capture_output=True)
    except FileNotFoundError:
        sys.exit("rsvg-convert is not installed (macOS: brew install librsvg, Linux: apt install librsvg2-bin)")
    if r.returncode:
        sys.exit("rsvg-convert failed: " + r.stderr.decode()[:400])
    return np.asarray(Image.open(io.BytesIO(r.stdout)).convert("RGBA"), np.float32) / 255.0


def parse_h(spec, inherited):
    if spec is None:
        return inherited
    if spec.strip() == "skip":
        return "skip"
    parts = [p.strip() for p in spec.split(",")]
    ang, pitch, style = inherited if isinstance(inherited, tuple) else (0.0, 1.0, "lines")
    if parts[0] in STYLES:          # data-h="solid" / "paper" / "contour"
        return (ang, pitch, parts[0])
    ang = float(parts[0])
    if len(parts) > 1 and parts[1]:
        pitch = float(parts[1])
    if len(parts) > 2 and parts[2]:
        style = parts[2]
    return (ang, pitch, style)


def hatch_svg(tree):
    """copy of the drawing where every shape is filled with its hatch code: R angle, G pitch, B style"""
    root = tree.getroot()
    root.set("shape-rendering", "crispEdges")
    for el in root.iter():
        if el.tag in (f"{{{SVGNS}}}defs", f"{{{SVGNS}}}clipPath", f"{{{SVGNS}}}mask", f"{{{SVGNS}}}linearGradient",
                      f"{{{SVGNS}}}radialGradient", f"{{{SVGNS}}}filter"):
            el.set("data-frozen", "1")

    def walk(el, inh, frozen):
        frozen = frozen or el.get("data-frozen") == "1"
        h = parse_h(el.get("data-h"), inh)
        if not frozen and isinstance(el.tag, str):
            for a in ("opacity", "fill-opacity", "stroke-opacity", "filter"):
                if a in el.attrib:
                    del el.attrib[a]
            st = el.get("style")
            if st:
                el.set("style", re.sub(r"(fill|stroke|opacity|fill-opacity|stroke-opacity|filter)\s*:[^;]+;?", "", st))
            if h == "skip":
                el.set("display", "none")
            else:
                ang, pitch, style = h
                code = f"rgb({int(round(ang)) % 180},{max(1, min(255, int(round(pitch * 50))))},{STYLES[style] * 40})"
                if el.get("fill") not in (None, "none") or el.tag.endswith(("path", "rect", "circle", "ellipse", "polygon", "text")) and el.get("fill") != "none":
                    el.set("fill", code)
                if el.get("stroke") not in (None, "none"):
                    el.set("stroke", code)
        for c in el:
            walk(c, h, frozen)
    walk(root, (0.0, 1.0, "lines"), False)
    return etree.tostring(tree)


def value_noise(h, w, cell, rng):
    gh, gw = h // cell + 3, w // cell + 3
    g = rng.random((gh, gw)).astype(np.float32)
    n = cv2.resize(g, (gw * cell, gh * cell), interpolation=cv2.INTER_CUBIC)
    return n[cell:cell + h, cell:cell + w]


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def line_ink(u, cover, pitch_px):
    """anti-aliased ink of parallel lines: u in line periods, cover = inked fraction of each period"""
    d = np.abs(u - np.floor(u) - 0.5) * pitch_px          # px from the nearest line centre
    hw = cover * pitch_px * 0.5
    return np.clip(hw - d + 0.5, 0, 1) * np.clip(hw * 2.2, 0, 1)   # very thin lines fade instead of aliasing


def engrave(svg_path, out_path, scale=2.0, pitch=3.6, margin=0.0, seed=None, out_scale=1.25, shadow=0.0, paper=None, ink=None):
    """svg -> engraved RGBA PNG. paper and ink are hex colours (default: the sepia look)."""
    PAPER_C, INK_C = palette(paper, ink)
    raw = open(svg_path, "rb").read()
    tone_rgba = rsvg(raw, scale)
    tree = etree.parse(io.BytesIO(raw))
    code = rsvg(hatch_svg(tree), scale)
    H, W = tone_rgba.shape[:2]
    if code.shape[:2] != (H, W):
        code = cv2.resize(code, (W, H), interpolation=cv2.INTER_NEAREST)
    seed = seed if seed is not None else int(hashlib.sha1(os.path.basename(svg_path).encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)

    a = tone_rgba[..., 3]
    rgb = tone_rgba[..., :3] / np.maximum(a[..., None], 1e-4)           # un-premultiplied colour
    rgb = np.clip(rgb, 0, 1)
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    T = 1.0 - lum                                                         # ink density wanted
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = np.where(mx > 1e-3, (mx - mn) / np.maximum(mx, 1e-3), 0)
    hue_rgb = rgb / np.maximum(lum[..., None], 0.05)                      # colour at unit brightness

    ang = np.deg2rad(np.round(code[..., 0] * 255))
    pmul = np.maximum(np.round(code[..., 1] * 255), 1) / 50.0
    style = np.round(code[..., 2] * 255 / 40).astype(np.int32)
    has = code[..., 3] > 0.5
    style[~has] = 0
    P = pitch * scale * pmul                                              # line pitch in px

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    wob = (value_noise(H, W, int(90 * scale), rng) - 0.5) * 0.55 + (value_noise(H, W, int(23 * scale), rng) - 0.5) * 0.12
    u1 = (-xx * np.sin(ang) + yy * np.cos(ang)) / P + wob
    a2 = ang + np.deg2rad(62.0)                                            # cross set, lozenge angle
    u2 = (-xx * np.sin(a2) + yy * np.cos(a2)) / (P * 1.08) + wob * 0.7

    # contour style: lines parallel to the region's edge (distance from the boundary of same-code pixels)
    cmask = (style == STYLES["contour"]) & has
    if cmask.any():
        lab, n = ndimage.label(cmask)
        dist = ndimage.distance_transform_edt(lab > 0)
        dist = cv2.GaussianBlur(dist.astype(np.float32), (0, 0), 1.2 * scale)
        u1 = np.where(cmask, dist / P + wob * 0.6, u1)

    Ts = cv2.GaussianBlur(T, (0, 0), 0.6 * scale)
    jitter = 1.0 + (value_noise(H, W, int(7 * scale), rng) - 0.5) * 0.18
    c1 = np.clip(Ts / 0.62, 0, 1) ** 0.9 * 0.58 + np.clip((Ts - 0.62) / 0.38, 0, 1) * 0.22
    c1 = c1 * jitter
    c2 = np.clip((Ts - 0.6) / 0.36, 0, 1) ** 1.1 * 0.62
    ink_map = line_ink(u1, c1, P)
    cross = (Ts > 0.6) & (style != STYLES["contour"]) | (style == STYLES["cross"]) & (Ts > 0.3)
    ink_map = np.where(cross, np.maximum(ink_map, line_ink(u2, c2, P)), ink_map)
    ink_map = np.where(Ts > 0.93, np.maximum(ink_map, smoothstep(0.93, 0.97, Ts)), ink_map)
    solid = style == STYLES["solid"]
    ink_map = np.where(solid, smoothstep(0.3, 0.6, Ts), ink_map)
    ink_map = np.where(style == STYLES["paper"], 0.0, ink_map)
    ink_map = np.where(Ts < 0.035, 0.0, ink_map)

    # crisp outline where the drawing changes tone sharply
    gx, gy = cv2.Sobel(Ts, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(Ts, cv2.CV_32F, 0, 1, ksize=3)
    et = smoothstep(0.9, 2.2, np.hypot(gx, gy) / scale)
    lmin = cv2.erode(Ts, np.ones((int(5 * scale) | 1, int(5 * scale) | 1), np.uint8))
    et = et * smoothstep(0.1, 0.24, lmin)            # no drawn outline around lights (moon, windows, lamps)
    ink_map = np.maximum(ink_map, et * 0.8)

    # printed-ink texture: slight density break-up and spread
    grain = value_noise(H, W, max(2, int(1.5 * scale)), rng)
    ink_map = np.clip(ink_map * (0.86 + 0.22 * grain), 0, 1)
    ink_map = cv2.GaussianBlur(ink_map, (0, 0), 0.35 * scale)

    # paper with hand-tint wash under the lines
    mott = (value_noise(H, W, int(160 * scale), rng) - 0.5) * 0.035 + (value_noise(H, W, int(11 * scale), rng) - 0.5) * 0.02
    sheet = PAPER_C[None, None, :] * (1 + mott[..., None])
    wash = np.clip(sheet * np.clip(hue_rgb, 0.35, 1.6), 0, 1)
    tint = np.clip(sat * 1.15, 0, 0.9)[..., None]
    base = sheet * (1 - tint) + wash * tint
    out = base * (1 - ink_map[..., None]) + INK_C[None, None, :] * ink_map[..., None]

    alpha = a
    if margin > 0:
        m = int(margin * scale)
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * m + 1, 2 * m + 1))
        rough = cv2.dilate((a > 0.02).astype(np.uint8), k).astype(np.float32)
        edge_noise = value_noise(H, W, int(6 * scale), rng)
        rough = cv2.GaussianBlur(rough, (0, 0), 1.6 * scale)
        alpha = np.maximum(a, smoothstep(0.42, 0.58, rough * (0.9 + 0.2 * edge_noise)))
        out = np.where(a[..., None] > 0.02, out, sheet)
    alpha = np.clip(alpha, 0, 1)
    out = np.clip(out, 0, 1)
    if shadow > 0:      # soft shadow this cutout casts on the layers behind it, baked under the paper
        sh = cv2.GaussianBlur(alpha, (0, 0), 9 * scale)
        sh = cv2.warpAffine(sh, np.float32([[1, 0, 7 * scale], [0, 1, 10 * scale]]), (W, H)) * 0.42 * shadow
        sa = sh * (1 - alpha)
        tot = alpha + sa
        dark = INK_C * 0.9
        out = (out * alpha[..., None] + dark[None, None, :] * sa[..., None]) / np.maximum(tot[..., None], 1e-4)
        alpha = np.clip(tot, 0, 1)
    rgba = np.dstack([out, alpha])
    if out_scale and abs(out_scale - scale) > 1e-6:
        w2, h2 = int(round(W * out_scale / scale)), int(round(H * out_scale / scale))
        prem = rgba.copy()
        prem[..., :3] *= prem[..., 3:4]
        prem = cv2.resize(prem, (w2, h2), interpolation=cv2.INTER_AREA)
        a2_ = prem[..., 3:4]
        prem[..., :3] = np.where(a2_ > 1e-4, prem[..., :3] / np.maximum(a2_, 1e-4), 0)
        rgba = np.clip(prem, 0, 1)
    Image.fromarray((rgba * 255 + 0.5).astype(np.uint8)).save(out_path, optimize=False, compress_level=3)
    return out_path


def photo_engrave(photo, out, crop, size, angle=8.0, pitch=3.4, warp=4.0, gamma=1.0, oval=0.88, frame=False, scale=2.0,
                  out_scale=1.25, paper=None, ink=None):
    """A photograph as a banknote portrait vignette: parallel lines displaced by the blurred tone of the picture, so they
    bend around the forms of the face, swell in the darks and cross-hatch in the deepest shadows. An oval fades to paper."""
    PAPER_C, INK_C = palette(paper, ink)
    x0, y0, x1, y1 = crop
    W, H = size
    S = scale
    Wp, Hp = int(W * S), int(H * S)
    img = cv2.imread(str(photo), cv2.IMREAD_GRAYSCALE)[y0:y1, x0:x1]
    img = cv2.resize(img, (Wp, Hp), interpolation=cv2.INTER_AREA)
    img = cv2.bilateralFilter(img, 9, 40, 7)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    L = clahe.apply(img).astype(np.float32) / 255.0
    T = np.clip(1.0 - L, 0, 1) ** gamma
    Ts = cv2.GaussianBlur(T, (0, 0), 0.9 * S)
    G = cv2.GaussianBlur(T, (0, 0), 7.5 * S)                 # the field that bends the lines around forms

    rng = np.random.default_rng(7)
    yy, xx = np.mgrid[0:Hp, 0:Wp].astype(np.float32)
    P = pitch * S
    th = np.deg2rad(angle)
    wob = (value_noise(Hp, Wp, int(70 * S), rng) - 0.5) * 0.35
    u1 = (yy * np.cos(th) - xx * np.sin(th)) / P + warp * G + wob
    th2 = th + np.deg2rad(58)
    u2 = (yy * np.cos(th2) - xx * np.sin(th2)) / (P * 1.1) + warp * 0.8 * G + wob * 0.7

    c1 = np.clip(Ts / 0.62, 0, 1) ** 0.85 * 0.58 + np.clip((Ts - 0.62) / 0.38, 0, 1) * 0.24
    c2 = np.clip((Ts - 0.55) / 0.4, 0, 1) ** 1.1 * 0.6
    ink_map = line_ink(u1, c1, P)
    ink_map = np.maximum(ink_map, np.where(Ts > 0.55, line_ink(u2, c2, P), 0))
    ink_map = np.where(Ts > 0.94, np.maximum(ink_map, smoothstep(0.94, 0.98, Ts)), ink_map)
    ink_map = np.where(Ts < 0.04, 0.0, ink_map)

    # oval vignette: the engraving thins out into bare paper toward the edge
    cx, cy = Wp / 2, Hp / 2
    r = np.hypot((xx - cx) / (Wp / 2), (yy - cy) / (Hp / 2))
    edge_noise = (value_noise(Hp, Wp, int(30 * S), rng) - 0.5) * 0.012
    fade = 1 - smoothstep(oval - 0.13, oval + 0.01, r + edge_noise)
    ink_map = ink_map * fade
    if frame:
        for rr, w in ((oval + 0.045, 1.6), (oval + 0.072, 0.9)):
            d = np.abs(r - rr) * (Wp / 2)
            ink_map = np.maximum(ink_map, np.clip(w * S * 0.5 - d + 0.5, 0, 1))

    grain = value_noise(Hp, Wp, max(2, int(1.5 * S)), rng)
    ink_map = np.clip(ink_map * (0.86 + 0.22 * grain), 0, 1)
    ink_map = cv2.GaussianBlur(ink_map, (0, 0), 0.35 * S)
    mott = (value_noise(Hp, Wp, int(160 * S), rng) - 0.5) * 0.035
    sheet = PAPER_C[None, None, :] * (1 + mott[..., None])
    result = sheet * (1 - ink_map[..., None]) + INK_C[None, None, :] * ink_map[..., None]
    alpha = np.clip(1 - smoothstep(oval + 0.075, oval + 0.11, r), 0, 1) if frame else fade
    rgba = np.dstack([np.clip(result, 0, 1), alpha])
    w2, h2 = int(W * out_scale), int(H * out_scale)
    rgba = cv2.resize(rgba, (w2, h2), interpolation=cv2.INTER_AREA)
    Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8)).save(out)
    return out


def make_tileable(src, dst, tile):
    """Make a horizontally scrolling layer seamless: the PNG is drawn wider than the tile, and the extra strip is
    cross-faded into the tile's start so x = 0 and x = tile meet without a seam."""
    a = np.asarray(Image.open(src).convert("RGBA"), np.float32)
    ov = a.shape[1] - tile
    if ov <= 8:
        raise ValueError("the drawing must be wider than the tile")
    out = a[:, :tile].copy()
    ramp = np.linspace(1, 0, ov, dtype=np.float32)[None, :, None]     # weight of the overhang

    def prem(x):
        return np.concatenate([x[..., :3] * x[..., 3:4] / 255, x[..., 3:4]], -1)

    head, tail_ = prem(out[:, :ov]), prem(a[:, tile:tile + ov])
    mixed = tail_ * ramp + head * (1 - ramp)
    al = mixed[..., 3:4]
    mixed[..., :3] = np.where(al > 0.5, mixed[..., :3] * 255 / np.maximum(al, 1e-3), 0)
    out[:, :ov] = mixed
    Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8)).save(dst)
    return dst
