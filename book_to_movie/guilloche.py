"""Guilloche: the interlaced spirograph line-work of banknotes and certificates, as SVG paths.

    rosette(cx, cy, r0, r1, lobes=18, strands=40)        a ring of woven sine strands
    band(x0, x1, y, h, waves=40, strands=12)             a straight woven border band
    frame(x, y, w, h, inset, ...)                         four bands with corner rosettes
All return lists of SVG path 'd' strings (stroke them; fill none)."""
import math


def _path(pts, closed=False):
    d = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts)
    return d + (" Z" if closed else "")


def rosette(cx, cy, r0, r1, lobes=18, strands=40, twist=2, n=900, amp2=0.18):
    """strands of rho(t) = mid + amp*sin(lobes*t + phase) (+ a slower modulation), phases spread round the ring"""
    out = []
    mid, amp = (r0 + r1) / 2, (r1 - r0) / 2
    for i in range(strands):
        ph = 2 * math.pi * i / strands
        pts = []
        for k in range(n + 1):
            t = 2 * math.pi * k / n
            rho = mid + amp * (1 - amp2) * math.sin(lobes * t + ph) + amp * amp2 * math.sin(twist * lobes * t - ph * 2)
            pts.append((cx + rho * math.cos(t), cy + rho * math.sin(t)))
        out.append(_path(pts, True))
    return out


def spiro(cx, cy, R, r, d, turns=None, n=4000, rot=0.0):
    """hypotrochoid"""
    g = math.gcd(int(R), int(r))
    turns = turns or r // g
    pts = []
    for k in range(n + 1):
        t = 2 * math.pi * turns * k / n
        x = (R - r) * math.cos(t) + d * math.cos((R - r) / r * t)
        y = (R - r) * math.sin(t) - d * math.sin((R - r) / r * t)
        c, s = math.cos(rot), math.sin(rot)
        pts.append((cx + x * c - y * s, cy + x * s + y * c))
    return [_path(pts, True)]


def band(x0, x1, y, h, waves=40, strands=10, n=None, vertical=False):
    out = []
    L = x1 - x0
    n = n or int(L / 2)
    for i in range(strands):
        ph = 2 * math.pi * i / strands
        pts = []
        for k in range(n + 1):
            u = k / n
            v = 0.5 * h * (0.78 * math.sin(2 * math.pi * waves * u + ph) + 0.22 * math.sin(2 * math.pi * waves * 3 * u - 2 * ph))
            pts.append((y + v, x0 + u * L) if vertical else (x0 + u * L, y + v))
        out.append(_path(pts))
    return out


def frame(x, y, w, h, bh=26, waves_per_px=1 / 22, strands=9, corner=46):
    out = []
    out += band(x + corner, x + w - corner, y, bh, waves=int((w - 2 * corner) * waves_per_px), strands=strands)
    out += band(x + corner, x + w - corner, y + h, bh, waves=int((w - 2 * corner) * waves_per_px), strands=strands)
    out += band(y + corner, y + h - corner, x, bh, waves=int((h - 2 * corner) * waves_per_px), strands=strands, vertical=True)
    out += band(y + corner, y + h - corner, x + w, bh, waves=int((h - 2 * corner) * waves_per_px), strands=strands, vertical=True)
    for cx, cy in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
        out += rosette(cx, cy, corner * 0.35, corner, lobes=12, strands=16, n=500)
    return out


def svg(paths, w, h, stroke="#2a211b", width=1.0, opacity=1.0, extra=""):
    body = "".join(f'<path d="{d}"/>' for d in paths)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'<g fill="none" stroke="{stroke}" stroke-width="{width}" stroke-opacity="{opacity}" stroke-linejoin="round">{body}</g>{extra}</svg>')
