"""The hill: a sheep meadow under far mountains, the forest along the right, the village small in the valley.
Used three times, by day, at dusk and at night: same layers, different skies, so the place stays one place."""
import math
import random

from book_to_movie.art import Set
from book_to_movie.figures import figure, held
from book_to_movie.svgkit import gray, lin, poly, puff, rad, ridge, smooth, taper_line

s = Set(__file__)
W, H = s.W, s.H


def rect(x, y, w, h, fill, h_):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" data-h="{h_}"/>'


def cloud(cx, cy, r, rnd, fill="#f4ecd8", disk="paper"):
    out = []
    for k in range(7):
        t = k / 6
        x = cx + (t - 0.5) * r * 4.2
        rr = r * (0.55 + 0.6 * math.sin(math.pi * t)) * rnd.uniform(0.85, 1.1)
        out.append((x, cy - rr * 0.34 + rnd.uniform(-3, 3), rr))
    return "".join(puff(x, y, rr, light=-120, arcs=4, w=1.8, outline=1.2, fill=fill, disk_h=disk) for x, y, rr in out)


# ---------- skies: day, dusk, night ----------
rnd = random.Random(4)
defs = lin("day", [(0, gray(0.56)), (0.5, gray(0.3)), (0.72, gray(0.12)), (1, gray(0.05))]) + \
    rad("sun", [(0, "#ffffff", 0.95), (0.25, "#ffffff", 0.55), (1, "#ffffff", 0)])
b = [rect(-100, -60, W + 200, H + 120, "url(#day)", "0,1"),
     '<circle cx="430" cy="196" r="420" fill="url(#sun)" data-h="skip"/>',
     '<circle cx="430" cy="196" r="58" fill="#f7ebc4" data-h="paper"/>']
for k in range(24):     # engraved rays, thin paper strokes round the sun
    a = 2 * math.pi * k / 24
    r0, r1 = 74, 150 + 58 * (k % 2)
    b.append(f'<path d="{taper_line([(430 + math.cos(a) * r0, 196 + math.sin(a) * r0), (430 + math.cos(a) * r1, 196 + math.sin(a) * r1)], 5, ends=0.5)}" fill="#fbf3dc" data-h="paper"/>')
b.append(cloud(1250, 170, 44, rnd))
b.append(cloud(1660, 300, 30, rnd))
b.append(cloud(170, 360, 26, rnd))
s.layer("sky_day", "".join(b), defs)

rnd = random.Random(9)
defs = lin("dusk", [(0, gray(0.86)), (0.45, gray(0.66)), (0.68, gray(0.38)), (1, gray(0.22))]) + \
    rad("moon", [(0, "#ffffff", 0.75), (0.3, "#ffffff", 0.3), (1, "#ffffff", 0)])
b = [rect(-100, -60, W + 200, H + 120, "url(#dusk)", "0,1"),
     '<ellipse cx="960" cy="640" rx="1500" ry="150" fill="#e9b7a0" fill-opacity="0.55" data-h="skip"/>',
     '<circle cx="1420" cy="250" r="360" fill="url(#moon)" data-h="skip"/>',
     '<circle cx="1420" cy="250" r="76" fill="#f7ebc4" data-h="paper"/>']
for x, y, r in [(1396, 226, 13), (1446, 276, 9), (1404, 288, 6), (1456, 224, 5)]:
    b.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#e8d6a4" data-h="30,0.6"/>')
for _ in range(90):
    x, y = rnd.uniform(-90, W + 90), rnd.uniform(-50, 440)
    if math.hypot(x - 1420, y - 250) > 180:
        b.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rnd.uniform(1.0, 2.4):.1f}" fill="#ffffff" data-h="paper"/>')
s.layer("sky_dusk", "".join(b), defs)

rnd = random.Random(12)
defs = lin("night", [(0, gray(0.95)), (0.55, gray(0.84)), (1, gray(0.6))]) + \
    rad("moon2", [(0, "#ffffff", 0.7), (0.35, "#ffffff", 0.22), (1, "#ffffff", 0)])
b = [rect(-100, -60, W + 200, H + 120, "url(#night)", "0,1"),
     '<circle cx="1420" cy="170" r="330" fill="url(#moon2)" data-h="skip"/>',
     '<circle cx="1420" cy="170" r="70" fill="#f7ebc4" data-h="paper"/>']
for x, y, r in [(1398, 150, 12), (1442, 196, 8), (1408, 204, 6)]:
    b.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#e8d6a4" data-h="30,0.6"/>')
for _ in range(190):
    x, y = rnd.uniform(-90, W + 90), rnd.uniform(-50, 560)
    if math.hypot(x - 1420, y - 170) > 150:
        b.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rnd.uniform(1.0, 2.8):.1f}" fill="#ffffff" data-h="paper"/>')
s.layer("sky_night", "".join(b), defs)


# ---------- mountains: every peak has a lit face and a shadow face, hatched along its slope ----------
def peak(cx, base, w, h, seed, lit=0.1, shade=0.56, snow=True):
    r = random.Random(seed)
    apex = (cx + r.uniform(-w * 0.05, w * 0.05), base - h)
    spine = [apex]
    x, y = apex
    for _ in range(5):
        y += h / 6
        x += r.uniform(-w * 0.05, w * 0.07)
        spine.append((x, y))
    spine.append((cx + w * 0.07, base + 20))
    left, right = (cx - w / 2, base + 20), (cx + w / 2, base + 20)
    ang_l = math.degrees(math.atan2(h, w / 2))
    out = [f'<path d="{poly([left, apex] + spine[1:])}" fill="{gray(lit)}" data-h="{-ang_l:.0f},1.1"/>',
           f'<path d="{poly([apex, right] + spine[::-1][:-1])}" fill="{gray(shade)}" data-h="{ang_l:.0f},0.95"/>']
    if snow:
        drop = h * r.uniform(0.2, 0.28)
        wid = w * (drop / h) * 0.5
        z = [(apex[0] - wid, apex[1] + drop * 1.05), (apex[0] - wid * 0.45, apex[1] + drop * 0.72), (apex[0] - wid * 0.2, apex[1] + drop * 1.12),
             (apex[0] + wid * 0.1, apex[1] + drop * 0.7), (apex[0] + wid * 0.48, apex[1] + drop * 1.05), (apex[0] + wid * 0.72, apex[1] + drop * 0.86), (apex[0] + wid, apex[1] + drop)]
        out.append(f'<path d="{poly([apex] + z[::-1])}" fill="#fbf6e6" data-h="paper"/>')
        out.append(f'<path d="{poly([apex, z[-1], z[-2], z[-3], (spine[1][0], spine[1][1] - 6)])}" fill="{gray(0.34)}" data-h="{ang_l:.0f},0.8"/>')
    return "".join(out)


b = []
for cx, w, h, seed in [(-40, 520, 300, 1), (280, 640, 400, 2), (690, 560, 330, 3), (1040, 720, 470, 4), (1460, 620, 360, 5), (1830, 640, 420, 6), (2060, 420, 260, 7)]:
    b.append(peak(cx, 640, w, h, seed))
s.layer("peaks_far", "".join(b), shadow=0.5)

b = []
for cx, w, h, seed in [(120, 560, 230, 11), (590, 640, 250, 12), (1210, 600, 270, 13), (1660, 560, 220, 14)]:
    b.append(peak(cx, 660, w, h, seed, lit=0.3, shade=0.7, snow=False))
s.layer("peaks_near", "".join(b), shadow=0.6)


# ---------- the valley floor with the village in it, tiny ----------
def tiny_house(x, y, w, h, rnd, lit=False):
    roof = h * 0.7
    out = rect(x, y - h, w, h, gray(0.3), "90,0.5")
    out += f'<path d="{poly([(x - 3, y - h), (x + w / 2, y - h - roof), (x + w + 3, y - h)])}" fill="{gray(0.72)}" data-h="35,0.5"/>'
    out += rect(x + w * 0.35, y - h * 0.55, w * 0.25, h * 0.32, "#f0a447" if lit else gray(0.75), "paper" if lit else "solid")
    return out


valley = ridge(-140, W + 140, 650, 14, 3.3, octaves=((1.0, 0.0018), (0.4, 0.006)))
defs = lin("valley", [(0, gray(0.22)), (1, gray(0.42))])
b = [f'<path d="{smooth(valley + [(W + 140, H + 80), (-140, H + 80)], closed=True)}" fill="url(#valley)" data-h="4,0.9"/>']
rnd = random.Random(21)
for x0 in range(330, 760, 34):
    h_ = rnd.uniform(15, 24)
    b.append(tiny_house(x0 + rnd.uniform(-4, 4), 668 + rnd.uniform(-4, 6), rnd.uniform(22, 30), h_, rnd))
# a small church tower among the houses
b.append(rect(548, 618, 16, 48, gray(0.4), "90,0.5") + f'<path d="{poly([(544, 618), (556, 588), (568, 618)])}" fill="{gray(0.8)}" data-h="solid"/>')
for x, y, r in [(392, 644, 4), (396, 632, 5), (402, 620, 6), (660, 640, 4), (665, 628, 5), (672, 616, 6)]:     # chimney smoke
    b.append(puff(x, y, r, arcs=1, w=0.8, outline=0.7))
s.layer("valley", "".join(b), defs, shadow=0.6)


# ---------- the forest along the right: rows of engraved conifers ----------
def conifer(x, base, h, tone=0.95):
    r = h * 0.2
    pts = [(x, base - h), (x + r * 0.5, base - h * 0.72), (x + r * 0.22, base - h * 0.72), (x + r * 0.85, base - h * 0.44), (x + r * 0.34, base - h * 0.44),
           (x + r * 1.15, base - h * 0.12), (x + r * 0.16, base - h * 0.12), (x + r * 0.16, base), (x - r * 0.16, base), (x - r * 0.16, base - h * 0.12),
           (x - r * 1.15, base - h * 0.12), (x - r * 0.34, base - h * 0.44), (x - r * 0.85, base - h * 0.44), (x - r * 0.22, base - h * 0.72), (x - r * 0.5, base - h * 0.72)]
    return f'<path d="{poly(pts)}" fill="{gray(tone)}" data-h="solid"/>'


rnd = random.Random(31)
b = [f'<path d="{smooth([(1180, 700), (1360, 640), (1560, 590), (1800, 555), (2100, 540), (2100, 900), (1180, 900)], closed=True, t=0.2)}" fill="{gray(0.84)}" data-h="-14,0.8"/>']
rows = []
for row, (y0, h0) in enumerate([(610, 62), (640, 84), (680, 118)]):
    x = 1240 + row * 30
    while x < W + 120:
        x += rnd.uniform(18, 34) + row * 6
        slope = max(0, (1560 - x) / 400)
        rows.append((y0 + slope * 90 + rnd.uniform(-6, 6), x, h0 * rnd.uniform(0.8, 1.2) * (1 - 0.35 * slope)))
for base, x, h_ in sorted(rows):
    b.append(conifer(x, base, h_, tone=0.86 + 0.1 * (base - 600) / 170))
s.layer("forest", "".join(b))

# ---------- the meadow the flock stands on ----------
rise = ridge(-140, W + 140, 800, 26, 1.1, octaves=((1.0, 0.0012), (0.3, 0.005)))
defs = lin("meadow", [(0, gray(0.34)), (0.45, gray(0.56)), (1, gray(0.74))])
b = [f'<path d="{smooth(rise + [(W + 140, H + 80), (-140, H + 80)], closed=True)}" fill="url(#meadow)" data-h="-7,1"/>']
rnd = random.Random(41)
for _ in range(420):
    x = rnd.uniform(-90, W + 90)
    y = rnd.uniform(790, 1120)
    h_ = rnd.uniform(6, 16) * (0.6 + (y - 780) / 340)
    lean = rnd.uniform(-4, 4)
    b.append(f'<path d="{taper_line([(x, y), (x + lean * 0.5, y - h_ * 0.6), (x + lean, y - h_)], 2.2, ends=0.3)}" fill="{gray(0.9)}" data-h="solid"/>')
s.layer("meadow", "".join(b), defs)


# ---------- sheep: wool in engraved billows on dark legs. Each one is its own small group so a flock can be split ----------
def sheep(x, y, scale=1.0, facing=1, seed=0, grazing=False):
    r = random.Random(seed)
    legs = "".join(f'<rect x="{lx}" y="-34" width="8" height="36" rx="3" fill="{gray(0.96)}" data-h="solid"/>' for lx in (-30, -14, 14, 28))
    wool = []
    blobs = [(0, -58, 34), (-30, -56, 25), (30, -56, 25), (-16, -78, 21), (14, -80, 22), (-42, -46, 15), (40, -46, 15), (0, -38, 22)]
    for bx, by, br in blobs:
        wool.append(puff(bx + r.uniform(-2, 2), by + r.uniform(-2, 2), br, light=-120, arcs=3, w=1.7, outline=1.3))
    hy = -40 if grazing else -80
    hx = 62
    head = (f'<ellipse cx="{hx}" cy="{hy}" rx="17" ry="11.5" transform="rotate({38 if grazing else -14} {hx} {hy})" fill="{gray(0.96)}" data-h="solid"/>'
            f'<ellipse cx="{hx - 12}" cy="{hy - 10}" rx="9" ry="4" transform="rotate(-40 {hx - 12} {hy - 10})" fill="{gray(0.96)}" data-h="solid"/>')
    return f'<g transform="translate({x},{y}) scale({scale * facing},{scale})">{legs}{"".join(wool)}{head}</g>'


far = [(220, 836, 0.62, 1, 1, True), (430, 820, 0.56, -1, 2, False), (620, 846, 0.66, 1, 3, True), (1040, 828, 0.6, -1, 4, True), (1590, 852, 0.68, 1, 5, False), (1740, 830, 0.58, -1, 6, True)]
s.layer("sheep_far", "".join(sheep(*a) for a in far), shadow=0.55)
near = [("sheep_a", (140, 968, 1.0, 1, 7, True)), ("sheep_b", (690, 990, 1.08, 1, 9, False)), ("sheep_c", (1210, 972, 1.02, -1, 11, True)), ("sheep_d", (1610, 996, 1.12, -1, 13, True))]
for name, a in near:
    s.layer(name, sheep(*a), shadow=0.75)


# ---------- the boy, on the rise, with his crook ----------
def crook(hand, tone=0.97):
    top = (hand[0] + 14, hand[1] - 92)
    out = held(hand, -82, 94, r0=3.2, tone=tone)
    bottom = held(hand, 96, 96, r0=3.2, tone=tone)
    hook = (f'<path d="M{top[0]:.0f},{top[1]:.0f} C{top[0] + 2:.0f},{top[1] - 30:.0f} {top[0] + 34:.0f},{top[1] - 34:.0f} {top[0] + 36:.0f},{top[1] - 8:.0f}" '
            f'fill="none" stroke="{gray(tone)}" stroke-width="6" stroke-linecap="round" data-h="solid"/>')
    return out + bottom + hook


BOY = dict(hat="none", coat="jacket", x=960, y=872, height=210, child=True)
svg, pts = figure("reach", anchors=True, **BOY)
s.layer("boy_stand", svg + crook(pts["hand_f"]), shadow=0.8)
svg, pts = figure("cry", anchors=True, **BOY)
s.layer("boy_cry", svg, shadow=0.8)


# ---------- the wolf: two trotting frames, drawn low and long, then placed in the scene with a move ----------
def wolf(frame=0, x=0.0, y=0.0, scale=1.0, tone=0.985):
    body = [(-112, -84), (-70, -96), (-10, -100), (44, -104), (72, -120), (92, -134), (104, -160), (110, -140), (120, -158), (128, -134),
            (168, -112), (174, -102), (130, -94), (108, -80), (92, -56), (60, -46), (6, -54), (-44, -52), (-84, -58), (-108, -66)]
    tail = [(-104, -86), (-140, -82), (-172, -60), (-186, -34), (-176, -32), (-150, -48), (-122, -62), (-102, -70)]
    legs_a = [[(-92, -62), (-80, -40), (-98, -18), (-92, 0), (-78, 0), (-82, -18), (-60, -44), (-60, -60)],
              [(-58, -60), (-40, -38), (-30, -18), (-14, 0), (0, 0), (-16, -22), (-24, -44), (-30, -60)],
              [(50, -56), (58, -28), (50, 0), (64, 0), (72, -28), (76, -56)],
              [(74, -58), (100, -30), (112, 0), (126, 0), (112, -36), (100, -60)]]
    legs_b = [[(-96, -62), (-112, -40), (-118, -18), (-124, 0), (-108, 0), (-100, -18), (-84, -44), (-66, -60)],
              [(-60, -60), (-62, -36), (-68, -18), (-62, 0), (-48, 0), (-52, -20), (-40, -42), (-34, -60)],
              [(44, -56), (22, -30), (4, -6), (16, 2), (40, -22), (70, -54)],
              [(70, -58), (78, -28), (72, 0), (86, 0), (94, -28), (98, -56)]]
    parts = [body, tail] + (legs_a if frame == 0 else legs_b)
    paths = "".join(f'<path d="{smooth(p, closed=True, t=0.4)}"/>' for p in parts)
    return f'<g transform="translate({x},{y}) scale({scale})" fill="{gray(tone)}" data-h="solid">{paths}</g>'


# the wolf faces left, coming out of the forest toward the flock
WOLF = 'transform="translate(1290,912) scale(-1.02,1.02)"'
s.layer("wolf_1", f"<g {WOLF}>{wolf(0)}</g>", shadow=0.8)
s.layer("wolf_2", f"<g {WOLF}>{wolf(1)}</g>", shadow=0.8)

# ---------- foreground: thistles and tall grass, nearest the lens ----------
rnd = random.Random(51)
b = [f'<path d="{smooth([(-120, 1060), (300, 1072), (700, 1098), (1200, 1102), (1700, 1076), (2060, 1054), (2060, 1160), (-120, 1160)], closed=True, t=0.4)}" fill="{gray(0.97)}" data-h="solid"/>']
x = -120
while x < W + 120:
    x += rnd.uniform(5, 13)
    edge = 1 - min(abs(x - 960) / 980, 1)
    h_ = (34 + rnd.uniform(0, 1) ** 2 * 96) * (1.1 - 0.75 * edge)
    lean = rnd.uniform(-16, 14)
    pts_ = [(x + lean * (i / 6) ** 1.6, 1110 - h_ * i / 6) for i in range(7)]
    b.append(f'<path d="{taper_line(pts_, rnd.uniform(3.5, 6.5), ends=0.25)}" fill="{gray(0.98)}" data-h="solid"/>')
s.layer("fg", "".join(b))

s.done()
