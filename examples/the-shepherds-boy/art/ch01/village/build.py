"""The village street: stone and timber cottages under thatch. The people run in by day and stay indoors at night.
The sky and far mountains are reused from the hill set, so the village sits in the same valley."""
import random

from book_to_movie.art import Set
from book_to_movie.figures import figure, held
from book_to_movie.svgkit import gray, lin, poly, puff, ridge, smooth, taper_line

s = Set(__file__)
W, H = s.W, s.H
BASE = 760        # where the houses meet the street
LAMP = "#f0a447"


def rect(x, y, w, h, fill, h_):
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" data-h="{h_}"/>'


# ---------- low hills behind the roofs ----------
far = ridge(-140, W + 140, 610, 26, 2.1, octaves=((1.0, 0.0016), (0.4, 0.0055)))
b = [f'<path d="{smooth(far + [(W + 140, H + 80), (-140, H + 80)], closed=True)}" fill="{gray(0.5)}" data-h="-6,0.9"/>']
rnd = random.Random(3)
for _ in range(70):
    x = rnd.uniform(-90, W + 90)
    h_ = rnd.uniform(24, 46)
    y = 612 + 22 * ((x % 640) / 640)
    b.append(f'<path d="{poly([(x, y - h_), (x + h_ * 0.24, y), (x - h_ * 0.24, y)])}" fill="{gray(0.9)}" data-h="solid"/>')
s.layer("hills", "".join(b), shadow=0.55)


# ---------- the cottages ----------
def window(x, y, w, h, lit=True):
    glass = rect(x, y, w, h, LAMP if lit else gray(0.86), "paper" if lit else "solid")
    frame = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="none" stroke="{gray(0.96)}" stroke-width="4" data-h="solid"/>'
    bars = (f'<line x1="{x + w / 2:.1f}" y1="{y:.1f}" x2="{x + w / 2:.1f}" y2="{y + h:.1f}" stroke="{gray(0.96)}" stroke-width="3" data-h="solid"/>'
            f'<line x1="{x:.1f}" y1="{y + h / 2:.1f}" x2="{x + w:.1f}" y2="{y + h / 2:.1f}" stroke="{gray(0.96)}" stroke-width="3" data-h="solid"/>')
    return glass + frame + bars


def door(x, w, h, tone=0.9):
    y = BASE - h
    d = f'M{x:.1f},{BASE} L{x:.1f},{y + w / 2:.1f} A{w / 2:.1f},{w / 2:.1f} 0 0 1 {x + w:.1f},{y + w / 2:.1f} L{x + w:.1f},{BASE} Z'
    planks = "".join(f'<line x1="{x + w * t:.1f}" y1="{y + 8:.1f}" x2="{x + w * t:.1f}" y2="{BASE}" stroke="{gray(0.99)}" stroke-width="1.6" data-h="solid"/>' for t in (0.25, 0.5, 0.75))
    frame = f'<path d="{d}" fill="none" stroke="{gray(0.97)}" stroke-width="5" data-h="solid"/>'
    return f'<path d="{d}" fill="{gray(tone)}" data-h="90,0.8"/>' + planks + frame


def timbers(x, y, w, h, rnd):
    out = []
    for t in (0.0, 0.5, 1.0):
        out.append(rect(x + w * t - 5, y, 10, h, gray(0.93), "solid"))
    out.append(rect(x - 5, y + h * 0.42, w + 10, 9, gray(0.93), "solid"))
    for a, bb in (((x + 5, y + h * 0.42), (x + w * 0.5 - 5, y)), ((x + w - 5, y + h * 0.42), (x + w * 0.5 + 5, y))):
        out.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{bb[0]:.1f}" y2="{bb[1]:.1f}" stroke="{gray(0.93)}" stroke-width="8" data-h="solid"/>')
    return "".join(out)


def stones(x, y, w, h, rnd):
    """a course of stones along the foot of a wall"""
    out = [rect(x, y, w, h, gray(0.44), "0,0.7")]
    row_y = y + 3
    while row_y < y + h - 4:
        sx = x + rnd.uniform(0, 14)
        while sx < x + w - 10:
            sw = rnd.uniform(14, 28)
            out.append(f'<rect x="{sx:.1f}" y="{row_y:.1f}" width="{min(sw, x + w - sx - 2):.1f}" height="{rnd.uniform(8, 12):.1f}" rx="3" fill="{gray(rnd.uniform(0.16, 0.3))}" data-h="20,0.5"/>')
            sx += sw + 3
        row_y += 14
    return "".join(out)


def thatch_marks(pts_top, pts_bottom, rnd, n):
    """tapered straw strokes running down the slope"""
    out = []
    for _ in range(n):
        t, u = rnd.random(), rnd.random() * 0.8
        x0, y0 = pts_top[0][0] + (pts_top[1][0] - pts_top[0][0]) * t, pts_top[0][1] + (pts_top[1][1] - pts_top[0][1]) * t
        x1, y1 = pts_bottom[0][0] + (pts_bottom[1][0] - pts_bottom[0][0]) * t, pts_bottom[0][1] + (pts_bottom[1][1] - pts_bottom[0][1]) * t
        ax, ay = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
        out.append(f'<path d="{taper_line([(ax, ay), (ax + (x1 - x0) * 0.12, ay + (y1 - y0) * 0.12)], 2.4, ends=0.4)}" fill="{gray(0.95)}" data-h="solid"/>')
    return "".join(out)


def cottage(x, w, wall_h, roof_h, seed, lit=True, windows=2, door_at=None):
    r = random.Random(seed)
    top = BASE - wall_h
    parts = [rect(x, top, w, wall_h, "url(#wall)", "90,0.9")]
    parts.append(timbers(x, top, w, wall_h * 0.72, r))
    parts.append(stones(x, BASE - wall_h * 0.28, w, wall_h * 0.28, r))
    door_x = x + w * (door_at if door_at is not None else 0.36)
    door_w = min(62, w * 0.2)
    parts.append(door(door_x, door_w, wall_h * 0.66))
    for k in range(windows):
        wx = x + w * (0.1 + 0.62 * k) + (w * 0.2 if k and door_at and door_at > 0.5 else 0)
        wx = x + w * 0.08 if k == 0 else x + w * 0.68
        parts.append(window(wx, top + wall_h * 0.16, min(68, w * 0.2), wall_h * 0.26, lit))
    # the thatch: front slope seen side on, hatched along the fall of the roof, with a dark shadow under the eave
    eave_l, eave_r = (x - 22, top + 6), (x + w + 22, top + 6)
    ridge_l, ridge_r = (x + 26, top - roof_h), (x + w - 26, top - roof_h)
    parts.append(f'<path d="{poly([eave_l, ridge_l, ridge_r, eave_r])}" fill="url(#thatch)" data-h="82,0.9"/>')
    parts.append(thatch_marks((ridge_l, ridge_r), (eave_l, eave_r), r, int(w * 0.5)))
    parts.append(f'<path d="{smooth([eave_l, (x + w / 2, top + 14), eave_r], closed=False, t=0.4)}" fill="none" stroke="{gray(0.97)}" stroke-width="7" data-h="solid"/>')
    parts.append(f'<path d="{smooth([ridge_l, (x + w / 2, top - roof_h - 7), ridge_r], closed=False, t=0.4)}" fill="none" stroke="#fbf3dc" stroke-width="2.4" data-h="paper"/>')
    parts.append(rect(x, top + 10, w, 12, gray(0.92), "0,0.6"))
    # chimney
    cx = x + w * (0.72 if seed % 2 else 0.26)
    parts.append(rect(cx, top - roof_h - 42, 36, 62, gray(0.68), "90,0.7"))
    parts.append(rect(cx - 5, top - roof_h - 48, 46, 9, gray(0.95), "solid"))
    return "".join(parts), (cx + 18, top - roof_h - 52)


defs = lin("wall", [(0, gray(0.05)), (1, gray(0.3))], x2=1, y2=0) + lin("thatch", [(0, gray(0.42)), (1, gray(0.72))])
b, chimneys = [], []
for x, w, wall_h, roof_h, seed, door_at in [(-120, 400, 200, 120, 1, 0.42), (330, 330, 170, 104, 2, 0.4), (710, 420, 214, 128, 3, 0.4),
                                             (1190, 340, 176, 110, 4, 0.4), (1580, 440, 206, 126, 5, 0.4)]:
    body, chimney = cottage(x, w, wall_h, roof_h, seed, door_at=door_at)
    b.append(body)
    chimneys.append(chimney)
s.layer("houses", "".join(b), defs)

# ---------- chimney smoke, its own layer so it can drift ----------
rnd = random.Random(8)
b = []
for cx, cy in chimneys:
    for k in range(14):
        t = k / 13
        b.append((t, cx + 60 * t ** 1.5 + rnd.uniform(-5, 5), cy - 160 * t, 7 + 26 * t))
out = [puff(x, y, r, light=-120, arcs=3 if r > 15 else 2, w=1.2, outline=1.0) for t, x, y, r in sorted(b, key=lambda c: -c[0])]
s.layer("smoke", "".join(out), shadow=0.3)

# ---------- the street ----------
defs = lin("street", [(0, gray(0.34)), (0.4, gray(0.16)), (1, gray(0.44))])
b = [rect(-120, BASE - 6, W + 240, H - BASE + 80, "url(#street)", "1,0.95")]
rnd = random.Random(6)
for _ in range(240):
    x, y = rnd.uniform(-100, W + 100), rnd.uniform(BASE + 8, H + 40)
    rx = rnd.uniform(4, 13) * (0.5 + (y - BASE) / 320)
    b.append(f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{rx:.1f}" ry="{rx * 0.34:.1f}" fill="{gray(rnd.uniform(0.5, 0.85))}" data-h="0,0.6"/>')
for y0 in (848, 924):
    pts = [(x, y0 + 8 * ((x % 300) / 300 - 0.5)) for x in range(-100, W + 120, 60)]
    b.append(f'<path d="{taper_line(pts, 6, ends=0.15)}" fill="{gray(0.72)}" data-h="0,0.7"/>')
s.layer("street", "".join(b), defs, shadow=0.0)


# ---------- the people ----------
PEOPLE = [dict(x=1020, y=956, height=250, hat="cap", coat="jacket", prop="fork"),
          dict(x=1230, y=930, height=226, hat="slouch", coat="long", prop="stick"),
          dict(x=1410, y=974, height=262, hat="none", coat="none", dress=True, hair="bun", prop=None),
          dict(x=1610, y=936, height=232, hat="hood", coat="long", prop="stick"),
          dict(x=1800, y=966, height=258, hat="cap", coat="jacket", prop="fork")]


def person(cfg, pose, facing=-1, stick_angle=-112):
    c = dict(cfg)
    prop = c.pop("prop")
    svg, pts = figure(pose, facing=facing, anchors=True, **c)
    if prop == "fork":
        svg += held(pts["hand_f"], stick_angle, 160, r0=3.2, head="fork")
    elif prop == "stick":
        svg += held(pts["hand_f"], stick_angle, 130, r0=3.6)
    return svg


s.layer("crowd_run1", "".join(person(c, "run1" if i % 2 else "run2") for i, c in enumerate(PEOPLE)), shadow=0.8)
s.layer("crowd_run2", "".join(person(c, "run2" if i % 2 else "run1") for i, c in enumerate(PEOPLE)), shadow=0.8)
s.layer("crowd_stand", "".join(person(c, "reach", stick_angle=-84) for c in PEOPLE), shadow=0.8)
SLUMP = dict(t=12, hd=20, af=(6, 8), ab=(-4, 8), lf=(10, 4), lb=(-10, 10))
SLUMP2 = dict(t=12, hd=20, af=(-4, 8), ab=(6, 8), lf=(-10, 10), lb=(10, 4))
s.layer("crowd_leave1", "".join(person(c, SLUMP if i % 2 else SLUMP2, facing=1, stick_angle=108) for i, c in enumerate(PEOPLE)), shadow=0.8)
s.layer("crowd_leave2", "".join(person(c, SLUMP2 if i % 2 else SLUMP, facing=1, stick_angle=108) for i, c in enumerate(PEOPLE)), shadow=0.8)

# ---------- the boy ----------
BOY = dict(hat="none", coat="jacket", child=True, x=360, y=940, height=226, facing=1)
LAUGH = dict(t=-12, hd=-26, af=(28, 96), ab=(18, 104), lf=(10, 4), lb=(-12, 8))
s.layer("boy_stand", figure("stand", **BOY), shadow=0.8)
s.layer("boy_cry", figure("cry", **BOY), shadow=0.8)
s.layer("boy_laugh", figure(LAUGH, **BOY), shadow=0.8)

# ---------- a low fence and grass nearest the lens ----------
rnd = random.Random(14)
b = []
for x in list(range(-90, 330, 104)) + list(range(1660, 2050, 104)):
    tilt = rnd.uniform(-4, 4)
    b.append(f'<path d="{poly([(x, 1120), (x + tilt, 978), (x + tilt + 9, 964), (x + tilt + 22, 978), (x + 22, 1120)])}" fill="{gray(0.96)}" data-h="solid"/>')
for y in (1010, 1060):
    b.append(rect(-120, y, 470, 13, gray(0.96), "solid") + rect(1640, y, 440, 13, gray(0.96), "solid"))
b.append(f'<path d="{smooth([(-120, 1090), (400, 1102), (900, 1124), (1400, 1124), (1800, 1098), (2060, 1088), (2060, 1160), (-120, 1160)], closed=True, t=0.4)}" fill="{gray(0.97)}" data-h="solid"/>')
x = -120
while x < W + 120:
    x += rnd.uniform(6, 16)
    h_ = (24 + rnd.uniform(0, 1) ** 2 * 64) * (1.0 - 0.55 * (1 - min(abs(x - 960) / 980, 1)))
    lean = rnd.uniform(-14, 12)
    pts_ = [(x + lean * (i / 6) ** 1.6, 1126 - h_ * i / 6) for i in range(7)]
    b.append(f'<path d="{taper_line(pts_, rnd.uniform(3.2, 6), ends=0.25)}" fill="{gray(0.98)}" data-h="solid"/>')
s.layer("fg", "".join(b))

s.done()
