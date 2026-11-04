"""Small helpers for writing tone-coded SVG layers (see engrave.py for the data-h hatch codes)."""
import math


def smooth(pts, closed=True, t=0.5):
    """Catmull-Rom through the points, as a cubic Bezier path"""
    n = len(pts)
    if n < 3:
        return poly(pts, closed)
    d = [f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"]
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0 = pts[(i - 1) % n] if (closed or i > 0) else pts[i]
        p1, p2 = pts[i], pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) * t / 3, p1[1] + (p2[1] - p0[1]) * t / 3)
        c2 = (p2[0] - (p3[0] - p1[0]) * t / 3, p2[1] - (p3[1] - p1[1]) * t / 3)
        d.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    if closed:
        d.append("Z")
    return " ".join(d)


def poly(pts, closed=True):
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return d + (" Z" if closed else "")


def tf(pts, dx=0, dy=0, s=1.0, flip=False, rot=0.0):
    c, sn = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    out = []
    for x, y in pts:
        x = -x if flip else x
        x, y = x * c - y * sn, x * sn + y * c
        out.append((x * s + dx, y * s + dy))
    return out


def ridge(x0, x1, base, amp, seed, step=18, octaves=((1.0, 0.0031), (0.45, 0.009), (0.18, 0.031))):
    """a hill line from x0 to x1 (deterministic sum of sines), closed down to the frame bottom"""
    pts = []
    x = x0
    while x <= x1 + step:
        y = base
        for k, (a, f) in enumerate(octaves):
            y -= amp * a * math.sin(x * f * 6.283 + seed * (k + 1.7)) * (0.6 + 0.4 * math.sin(seed * 3.1 + k))
        pts.append((x, y))
        x += step
    return pts


def doc(w, h, body, defs="", extra=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" {extra}>'
            f"<defs>{defs}</defs>{body}</svg>")


def lin(id_, stops, x1=0, y1=0, x2=0, y2=1):
    s = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops)
    return f'<linearGradient id="{id_}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">{s}</linearGradient>'


def rad(id_, stops, cx=0.5, cy=0.5, r=0.5, fx=None, fy=None):
    s = "".join(f'<stop offset="{o}" stop-color="{c}" stop-opacity="{op}"/>' for o, c, op in stops)
    f = f' fx="{fx}" fy="{fy}"' if fx is not None else ""
    return f'<radialGradient id="{id_}" cx="{cx}" cy="{cy}" r="{r}"{f}>{s}</radialGradient>'


def gray(t):
    """tone (0 paper .. 1 ink) as an svg grey"""
    v = int(round((1 - max(0, min(1, t))) * 255))
    return f"#{v:02x}{v:02x}{v:02x}"


def taper_arc(cx, cy, r, a0, a1, w, n=28, ends=0.5):
    """an engraver's stroke along a circular arc (angles in degrees), swelling to width w in the middle"""
    outer, inner = [], []
    for k in range(n + 1):
        t = k / n
        a = math.radians(a0 + (a1 - a0) * t)
        hw = 0.5 * w * (math.sin(math.pi * t) ** ends)
        outer.append((cx + math.cos(a) * (r + hw), cy + math.sin(a) * (r + hw)))
        inner.append((cx + math.cos(a) * (r - hw), cy + math.sin(a) * (r - hw)))
    return poly(outer + inner[::-1])


def taper_line(pts, w, ends=0.6):
    """a tapered stroke along a polyline (a two-point stroke is subdivided so it keeps its width)"""
    if len(pts) == 2:
        (x0, y0), (x1, y1) = pts
        pts = [(x0 + (x1 - x0) * k / 6, y0 + (y1 - y0) * k / 6) for k in range(7)]
    n = len(pts)
    L, R = [], []
    for k, (x, y) in enumerate(pts):
        x0, y0 = pts[max(0, k - 1)]
        x1, y1 = pts[min(n - 1, k + 1)]
        dx, dy = x1 - x0, y1 - y0
        d = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / d, dx / d
        t = k / (n - 1)
        hw = 0.5 * w * (math.sin(math.pi * t) ** ends)
        L.append((x + nx * hw, y + ny * hw))
        R.append((x - nx * hw, y - ny * hw))
    return poly(L + R[::-1])


def puff(cx, cy, r, light=-135.0, arcs=6, ink="#050505", fill="#f4ecd8", w=2.4, outline=1.6, disk_h="paper"):
    """an engraved billow: a disk shaded by concentric tapered arcs on the side away from the light"""
    shade = light + 180
    out = [f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" data-h="{disk_h}"/>']
    out.append(f'<path d="{taper_arc(cx, cy, r - outline * 0.4, shade - 150, shade + 150, outline * 2.2, ends=0.35)}" fill="{ink}" data-h="solid"/>')
    gap = max(2.6, r / (arcs + 3.5))
    for i in range(1, arcs + 1):
        rr = r - i * gap
        if rr <= gap:
            break
        span = 118 * (1 - i / (arcs + 1.6)) + 12
        out.append(f'<path d="{taper_arc(cx, cy, rr, shade - span, shade + span, w * (1 - 0.55 * i / arcs))}" fill="{ink}" data-h="solid"/>')
    return "".join(out)
