"""Silhouette figures for the engraved paper theatre, built from a posed profile skeleton.

    from figures import figure, POSES
    svg = figure("stand", hat="cap", coat="long", x=900, y=880, height=180, facing=1, tone=0.97)

A figure is drawn in profile, feet on (x, y), facing right (facing=1) or left (-1). Pose angles are in degrees:
limbs measure from straight down, positive = forward of the body. Parts are unioned shapes in one solid tone, so the
engraver closes them up to a crisp ink silhouette. Returns an SVG <g> string (data-h="solid").
"""
import math

H_UNITS = 7.5   # adult height in heads
WALK = ["walk1", "walk4", "walk3", "walk2"]     # the order that walks forward (numeric order shuffles backwards)

POSES = {
    #          torso head  arm_f(sh, el) arm_b(sh, el)  leg_f(hip, knee) leg_b(hip, knee)
    "stand":   dict(t=2, hd=0, af=(4, 8), ab=(-6, 6), lf=(3, 2), lb=(-4, 3)),
    "walk1":   dict(t=5, hd=-2, af=(-24, 18), ab=(26, 22), lf=(24, 6), lb=(-20, 28)),
    "walk2":   dict(t=5, hd=-2, af=(-6, 14), ab=(8, 14), lf=(6, 38), lb=(-4, 4)),
    "walk3":   dict(t=5, hd=-2, af=(22, 22), ab=(-22, 16), lf=(-18, 26), lb=(22, 6)),
    "walk4":   dict(t=5, hd=-2, af=(6, 14), ab=(-8, 14), lf=(-4, 4), lb=(6, 38)),
    "lean":    dict(t=14, hd=-6, af=(10, 40), ab=(-40, 70), lf=(10, 4), lb=(-14, 10)),   # leaning into wind, rear hand on a rail
    "point":   dict(t=4, hd=-4, af=(92, 4), ab=(-4, 10), lf=(5, 2), lb=(-6, 4)),
    "raise":   dict(t=-4, hd=-8, af=(150, 30), ab=(20, 40), lf=(14, 6), lb=(-16, 10)),   # arm raised overhead (stave)
    "reach":   dict(t=8, hd=0, af=(62, 10), ab=(-8, 12), lf=(6, 2), lb=(-6, 6)),        # hand held out
    "sit":     dict(t=12, hd=8, af=(30, 70), ab=(20, 80), lf=(84, 88), lb=(80, 92), sit=True),
    "slump":   dict(t=26, hd=22, af=(36, 64), ab=(26, 70), lf=(80, 86), lb=(76, 96), sit=True),
    "step":    dict(t=8, hd=-14, af=(-14, 20), ab=(14, 24), lf=(22, 10), lb=(-16, 14)),  # one step forward, chin up
    "think":   dict(t=4, hd=10, af=(40, 130), ab=(-2, 10), lf=(3, 2), lb=(-4, 3)),       # hand to chin
    "pocket":  dict(t=2, hd=4, af=(10, 34), ab=(-8, 30), lf=(3, 2), lb=(-4, 3)),         # hands in coat pockets
    "carry":   dict(t=6, hd=0, af=(30, 80), ab=(26, 86), lf=(4, 2), lb=(-5, 4)),         # holding something at the chest
    "sweep":   dict(t=18, hd=6, af=(40, 20), ab=(34, 30), lf=(12, 6), lb=(-14, 8)),      # bent over, arms down-forward
    "swing":   dict(t=-6, hd=-6, af=(165, 25), ab=(150, 35), lf=(16, 8), lb=(-18, 12)),  # pick raised before the blow
    "strike":  dict(t=34, hd=24, af=(58, 4), ab=(50, 10), lf=(24, 20), lb=(-22, 12)),    # pick driven down
    "run1":    dict(t=16, hd=-8, af=(-34, 70), ab=(44, 78), lf=(46, 34), lb=(-30, 58)),  # running: front leg reaching
    "run2":    dict(t=16, hd=-8, af=(44, 78), ab=(-34, 70), lf=(-30, 58), lb=(46, 34)),  # running: back leg reaching
    "cry":     dict(t=-4, hd=-22, af=(150, 20), ab=(-150, -20), lf=(14, 6), lb=(-16, 10)),  # both arms up, head back, calling
    "kneel":   dict(t=10, hd=10, af=(30, 60), ab=(16, 50), lf=(70, 96), lb=(-6, 92)),    # one knee down
}


def _rot(p, a):
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def _limb(origin, length, ang_deg):
    """end point of a segment hanging from origin at ang_deg from straight down (positive = forward, +x)"""
    a = math.radians(ang_deg)
    return (origin[0] + math.sin(a) * length, origin[1] + math.cos(a) * length)


def capsule(p0, p1, r0, r1, n=10):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ang = math.atan2(dy, dx)
    pts = []
    for k in range(n + 1):     # cap around p1
        a = ang - math.pi / 2 + math.pi * k / n
        pts.append((p1[0] + math.cos(a) * r1, p1[1] + math.sin(a) * r1))
    for k in range(n + 1):     # cap around p0
        a = ang + math.pi / 2 + math.pi * k / n
        pts.append((p0[0] + math.cos(a) * r0, p0[1] + math.sin(a) * r0))
    return pts


def ell(c, rx, ry, rot=0.0, n=28):
    out = []
    for k in range(n):
        t = 2 * math.pi * k / n
        p = (math.cos(t) * rx, math.sin(t) * ry)
        p = _rot(p, math.radians(rot))
        out.append((c[0] + p[0], c[1] + p[1]))
    return out


def _poly(pts):
    return "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + " Z"


def _smooth(pts, t=0.5):
    n = len(pts)
    d = [f"M{pts[0][0]:.2f},{pts[0][1]:.2f}"]
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) * t / 3, p1[1] + (p2[1] - p0[1]) * t / 3)
        c2 = (p2[0] - (p3[0] - p1[0]) * t / 3, p2[1] - (p3[1] - p1[1]) * t / 3)
        d.append(f"C{c1[0]:.2f},{c1[1]:.2f} {c2[0]:.2f},{c2[1]:.2f} {p2[0]:.2f},{p2[1]:.2f}")
    return " ".join(d) + " Z"


def lerp_pose(a, b, t):
    A, B = POSES[a] if isinstance(a, str) else a, POSES[b] if isinstance(b, str) else b
    out = {}
    for k in A:
        if isinstance(A[k], tuple):
            out[k] = tuple(x + (y - x) * t for x, y in zip(A[k], B[k]))
        elif isinstance(A[k], bool):
            out[k] = A[k]
        else:
            out[k] = A[k] + (B[k] - A[k]) * t
    return out


def figure(pose="stand", hat="cap", coat="long", x=0.0, y=0.0, height=180.0, facing=1, tone=0.97, child=False,
           hair=None, flare=0.0, prop=None, extra="", fill=None, beard=False, dress=False, belly=0.0, hunch=0.0,
           anchors=False):
    """one silhouette. hat: none | cap | bowler | fedora | top | boater | miner | slouch | hood | crown | helmet.
    coat: long | jacket | none. dress=True for a dress. hair: None | braids | bun. prop: None | case | cane (draw sticks,
    picks, brooms and staves yourself with held(), using anchors=True to get the hands).
    anchors=True returns (svg, {"hand_f", "hand_b", "head", "neck", "pelvis", "feet"}) in stage coordinates."""
    P = POSES[pose] if isinstance(pose, str) else pose
    heads = 5.6 if child else H_UNITS
    h = height / heads
    k = 0.92 if child else 1.0
    thigh, shin = (1.5 if child else 1.9) * h, (1.4 if child else 1.75) * h
    uarm, farm = (1.12 if child else 1.42) * h, (0.95 if child else 1.18) * h
    torso_len = (1.65 if child else 2.45) * h
    neck = (0.16 if child else 0.22) * h
    sit = P.get("sit", False)
    sleeve = 1.14 if coat in ("long", "jacket") else 1.0

    def leg_pts(hip, la):
        hip_a, knee_a = la
        knee = _limb(hip, thigh, hip_a)
        ankle = _limb(knee, shin, hip_a - knee_a)
        return knee, ankle

    kf, af_ = leg_pts((0.0, 0.0), P["lf"])
    kb, ab_ = leg_pts((0.0, 0.0), P["lb"])
    base = max(af_[1], ab_[1])
    pelvis = (0.0, -base - 0.2 * h)
    kf, af_ = leg_pts(pelvis, P["lf"])
    kb, ab_ = leg_pts(pelvis, P["lb"])

    lean = math.radians(P["t"])
    up = (math.sin(lean), -math.cos(lean))
    fwd = (math.cos(lean), math.sin(lean))
    def along(t, off):
        b_ = (pelvis[0] + up[0] * torso_len * t, pelvis[1] + up[1] * torso_len * t)
        return (b_[0] + fwd[0] * off, b_[1] + fwd[1] * off)
    neck_base = along(1.0, 0.08 * h)
    shoulder = along(0.86, -0.06 * h)
    hd_a = lean + math.radians(P["hd"]) * 0.8 + math.radians(hunch) * 0.4
    head_up = (math.sin(hd_a), -math.cos(hd_a))
    hr = 0.43 * h * (1.12 if child else 1.0)
    head_c = (neck_base[0] + head_up[0] * (neck + hr * 1.05) + 0.05 * h, neck_base[1] + head_up[1] * (neck + hr * 1.05))

    shapes = []

    def arm(spec):
        sh_a, el_a = spec
        elbow = _limb(shoulder, uarm, sh_a)
        wrist = _limb(elbow, farm, sh_a + el_a)
        r_s, r_e, r_w = 0.3 * h * k * sleeve, 0.23 * h * k * sleeve, 0.16 * h * k * sleeve
        shapes.append(capsule(shoulder, elbow, r_s, r_e))
        shapes.append(capsule(elbow, wrist, r_e, r_w))
        hand_c = _limb(wrist, 0.26 * h * k, sh_a + el_a)
        shapes.append(ell(hand_c, 0.17 * h * k, 0.26 * h * k, -(sh_a + el_a)))
        return elbow, wrist, hand_c

    for (knee, ankle) in ((kb, ab_), (kf, af_)):
        rt, rk, ra = 0.42 * h * k, 0.29 * h * k, 0.18 * h * k
        shapes.append(capsule(pelvis, knee, rt, rk))
        shapes.append(capsule(knee, ankle, rk, ra))
        L = (0.95 if not child else 0.85) * h
        toe = (ankle[0] + L * 0.78, ankle[1] + 0.13 * h)
        heel = (ankle[0] - L * 0.24, ankle[1] + 0.12 * h)
        shapes.append(_smooth([(heel[0], heel[1] - 0.12 * h), (ankle[0] - 0.05 * h, ankle[1] - 0.2 * h), (ankle[0] + 0.32 * h, ankle[1] - 0.14 * h),
                               (toe[0] - 0.08 * h, toe[1] - 0.14 * h), (toe[0], toe[1] - 0.02 * h), (toe[0] - 0.05 * h, toe[1] + 0.06 * h),
                               (heel[0], heel[1] + 0.06 * h)], 0.45))

    # torso: back curve, shoulder mass, chest, waist, seat
    depth = (1.0 if child else 1.18) * h
    pts = [along(0.02, depth * 0.5 + belly * 0.2 * h), along(0.38, depth * 0.44 + belly * 0.5 * h), along(0.7, depth * 0.56 + belly * 0.15 * h),
           along(0.93, depth * 0.36), along(1.0, depth * 0.1), along(0.97, -depth * 0.3), along(0.82, -depth * 0.5 - hunch * 0.04 * h),
           along(0.5, -depth * 0.42), along(0.12, -depth * 0.52), along(-0.06, -depth * 0.3)]
    shapes.append(_smooth(pts, 0.5))
    shapes.append(ell(shoulder, 0.42 * h * k, 0.4 * h * k, math.degrees(lean)))
    shapes.append(capsule(neck_base, (head_c[0] - head_up[0] * hr * 0.6, head_c[1] - head_up[1] * hr * 0.6), 0.21 * h * k, 0.19 * h * k))

    if dress or coat in ("long", "jacket"):
        kneey = max(kf[1], kb[1])
        if dress:
            hem_y = pelvis[1] + (kneey - pelvis[1]) * 1.05
        elif coat == "long":
            hem_y = pelvis[1] + (kneey - pelvis[1]) * 1.08
        else:
            hem_y = pelvis[1] + (kneey - pelvis[1]) * 0.42
        fx = max(kf[0], kb[0]) * 0.7 + 0.5 * h + (0.3 * h if dress else 0)
        bx = min(kf[0], kb[0]) * 0.7 - 0.62 * h - flare * h - (0.34 * h if dress else 0)
        if sit:
            hem_y = pelvis[1] + 0.32 * h
            fx, bx = max(kf[0], kb[0]) * 0.5 + 0.2 * h, -0.7 * h
        cp = [along(0.98, depth * 0.3), along(0.7, depth * 0.62), along(0.3, depth * 0.58), (fx, hem_y),
              ((fx + bx) / 2 - flare * 0.4 * h, hem_y + 0.1 * h), (bx, hem_y - flare * 0.5 * h),
              along(0.25, -depth * 0.62 - flare * 0.3 * h), along(0.62, -depth * 0.55), along(0.98, -depth * 0.36)]
        shapes.append(_smooth(cp, 0.45))
        if coat == "long" and not dress:   # turned-up collar
            shapes.append(_smooth([along(0.9, depth * 0.36), along(1.05, depth * 0.22), along(1.1, -depth * 0.05), along(1.03, -depth * 0.36), along(0.88, -depth * 0.4)], 0.5))

    arm(P["ab"])
    elbow_f, wrist_f, hand_f = arm(P["af"])

    shapes.append(ell(head_c, hr * 0.94, hr * 1.12, math.degrees(hd_a)))
    def hp(dx, dy):
        p_ = _rot((dx * h, dy * h), hd_a)
        return (head_c[0] + p_[0], head_c[1] + p_[1])
    if not child:
        shapes.append([hp(0.3, -0.16), hp(0.52, 0.06), hp(0.36, 0.12), hp(0.38, 0.22), hp(0.33, 0.33), hp(0.24, 0.48), hp(0.02, 0.46)])
    else:
        shapes.append([hp(0.32, -0.06), hp(0.46, 0.1), hp(0.34, 0.16), hp(0.33, 0.28), hp(0.16, 0.42), hp(0.0, 0.38)])
    if beard:
        shapes.append(_smooth([hp(0.36, 0.1), hp(0.52, 0.42), hp(0.5, 0.78), hp(0.26, 1.0), hp(-0.06, 0.92), hp(-0.3, 0.56),
                               hp(-0.3, 0.12), hp(0.0, 0.2)], 0.5))

    def hat_pts(kind):
        if kind == "cap":
            return [_smooth([hp(-0.48, -0.12), hp(-0.44, -0.48), hp(-0.1, -0.64), hp(0.34, -0.58), hp(0.5, -0.36), hp(0.82, -0.28),
                             hp(0.8, -0.18), hp(0.38, -0.2), hp(-0.48, -0.04)], 0.45)]
        if kind == "bowler":
            return [_smooth([hp(-0.42, -0.28), hp(-0.38, -0.68), hp(0.0, -0.86), hp(0.38, -0.68), hp(0.44, -0.28)], 0.6),
                    [hp(-0.64, -0.3), hp(0.66, -0.34), hp(0.62, -0.22), hp(-0.6, -0.18)]]
        if kind == "fedora":
            return [_smooth([hp(-0.42, -0.28), hp(-0.4, -0.7), hp(-0.12, -0.8), hp(0.0, -0.7), hp(0.14, -0.82), hp(0.42, -0.68), hp(0.46, -0.28)], 0.5),
                    [hp(-0.76, -0.28), hp(-0.3, -0.36), hp(0.42, -0.36), hp(0.84, -0.24), hp(0.74, -0.18), hp(-0.7, -0.18)]]
        if kind == "top":
            return [[hp(-0.38, -0.28), hp(-0.4, -1.2), hp(0.42, -1.22), hp(0.4, -0.28)],
                    [hp(-0.64, -0.32), hp(0.68, -0.34), hp(0.64, -0.22), hp(-0.6, -0.2)]]
        if kind == "boater":
            return [[hp(-0.4, -0.28), hp(-0.38, -0.6), hp(0.4, -0.6), hp(0.42, -0.28)],
                    [hp(-0.78, -0.28), hp(0.82, -0.3), hp(0.8, -0.2), hp(-0.74, -0.18)]]
        if kind == "miner":
            return [_smooth([hp(-0.48, -0.18), hp(-0.44, -0.6), hp(0.0, -0.76), hp(0.42, -0.58), hp(0.48, -0.18)], 0.6),
                    [hp(-0.7, -0.2), hp(0.74, -0.22), hp(0.7, -0.1), hp(-0.66, -0.1)]]
        if kind == "hood":     # a cloak hood, for anything from monks to wanderers
            return [_smooth([hp(-0.62, 0.42), hp(-0.66, -0.2), hp(-0.36, -0.68), hp(0.14, -0.74), hp(0.5, -0.44), hp(0.5, -0.12),
                             hp(0.2, -0.3), hp(-0.08, -0.12), hp(-0.2, 0.42)], 0.5)]
        if kind == "crown":
            return [[hp(-0.42, -0.28), hp(-0.5, -0.8), hp(-0.24, -0.52), hp(-0.1, -0.92), hp(0.08, -0.52), hp(0.24, -0.92),
                     hp(0.36, -0.52), hp(0.56, -0.8), hp(0.46, -0.28)]]
        if kind == "helmet":
            return [_smooth([hp(-0.5, -0.08), hp(-0.46, -0.56), hp(0.0, -0.76), hp(0.44, -0.56), hp(0.5, -0.08), hp(0.26, -0.16), hp(-0.2, -0.14)], 0.55),
                    [hp(-0.05, -0.74), hp(0.0, -1.06), hp(0.05, -0.74)]]
        if kind == "slouch":   # wide soft hat
            return [_smooth([hp(-0.44, -0.26), hp(-0.42, -0.66), hp(0.0, -0.78), hp(0.42, -0.64), hp(0.46, -0.26)], 0.55),
                    [hp(-0.9, -0.2), hp(-0.4, -0.34), hp(0.44, -0.34), hp(0.96, -0.18), hp(0.86, -0.1), hp(-0.84, -0.12)]]
        return []
    for hs in hat_pts(hat):
        shapes.append(hs)
    if hair == "braids":
        # hair hugging the skull (rounder than a cap, no brim), a plait down the back with a bow, a side puff
        shapes.append(_smooth([hp(-0.46, 0.0), hp(-0.5, -0.34), hp(-0.28, -0.6), hp(0.06, -0.66), hp(0.34, -0.5),
                               hp(0.4, -0.3), hp(0.2, -0.36), hp(-0.1, -0.3), hp(-0.36, -0.04)], 0.5))
        shapes.append(capsule(hp(-0.4, -0.06), hp(-0.56, 0.62), 0.14 * h, 0.1 * h))
        shapes.append(ell(hp(-0.58, 0.72), 0.13 * h, 0.15 * h))
        shapes.append([hp(-0.72, 0.58), hp(-0.44, 0.66), hp(-0.72, 0.8)])
        shapes.append(ell(hp(-0.12, -0.42), 0.16 * h, 0.12 * h))
    elif hair == "bun":
        shapes.append(ell(hp(-0.38, -0.36), 0.24 * h, 0.24 * h))

    if prop == "stave":
        tip = _limb(hand_f, 2.7 * h, P["af"][0] + P["af"][1] + 180)
        butt = _limb(hand_f, 0.4 * h, P["af"][0] + P["af"][1])
        shapes.append(capsule(butt, tip, 0.12 * h, 0.15 * h))
    elif prop == "pick":
        a_ = P["af"][0] + P["af"][1]
        top = _limb(hand_f, 2.3 * h, a_ + 180)
        bot = _limb(hand_f, 0.35 * h, a_)
        shapes.append(capsule(bot, top, 0.08 * h, 0.08 * h))
        d = (top[0] - hand_f[0], top[1] - hand_f[1])
        L = math.hypot(*d) or 1
        u_, n_ = (d[0] / L, d[1] / L), (-d[1] / L, d[0] / L)
        shapes.append(_smooth([(top[0] + n_[0] * 1.15 * h - u_[0] * 0.3 * h, top[1] + n_[1] * 1.15 * h - u_[1] * 0.3 * h),
                               (top[0] + u_[0] * 0.16 * h, top[1] + u_[1] * 0.16 * h),
                               (top[0] - n_[0] * 0.95 * h - u_[0] * 0.25 * h, top[1] - n_[1] * 0.95 * h - u_[1] * 0.25 * h),
                               (top[0] - u_[0] * 0.1 * h, top[1] - u_[1] * 0.1 * h)], 0.3))
    elif prop == "case":
        c = (hand_f[0], hand_f[1] + 0.62 * h)
        shapes.append([(c[0] - 0.75 * h, c[1] - 0.2 * h), (c[0] + 0.75 * h, c[1] - 0.2 * h), (c[0] + 0.78 * h, c[1] + 0.8 * h), (c[0] - 0.78 * h, c[1] + 0.8 * h)])
        shapes.append(capsule((c[0] - 0.22 * h, c[1] - 0.32 * h), (c[0] + 0.22 * h, c[1] - 0.32 * h), 0.07 * h, 0.07 * h))
    elif prop == "cane":
        shapes.append(capsule(hand_f, (hand_f[0] + 0.5 * h, 0.0), 0.07 * h, 0.07 * h))
    elif prop == "broom":
        a_ = P["af"][0] + P["af"][1]
        bot = _limb(hand_f, 2.7 * h, a_)
        topp = _limb(hand_f, 1.0 * h, a_ + 180)
        shapes.append(capsule(topp, bot, 0.07 * h, 0.07 * h))
        shapes.append([(bot[0] - 0.45 * h, bot[1] + 0.55 * h), (bot[0] - 0.12 * h, bot[1] - 0.1 * h), (bot[0] + 0.16 * h, bot[1] - 0.1 * h), (bot[0] + 0.55 * h, bot[1] + 0.55 * h)])

    fill = fill or _gray(tone)
    body = "".join(f'<path d="{s_ if isinstance(s_, str) else _poly(s_)}"/>' for s_ in shapes)
    svg = f'<g transform="translate({x:.1f},{y:.1f}) scale({facing},1)" fill="{fill}" data-h="solid">{body}{extra}</g>'
    if not anchors:
        return svg
    def w(p_):
        return (x + facing * p_[0], y + p_[1])

    pts = {"hand_f": w(hand_f), "hand_b": w(_limb(_limb(shoulder, uarm, P["ab"][0]), farm, P["ab"][0] + P["ab"][1])),
           "head": w(head_c), "neck": w(neck_base), "pelvis": w(pelvis), "feet": (x, y), "h": h}
    return svg, pts


def held(hand, angle_deg, length, r0=4.0, r1=None, tone=0.97, head=None):
    """a stick held in a hand (stage coordinates): a handle from the hand at angle_deg (0 = pointing right, 90 = down).
    head: None | "pick" (a pick head at the far end) | "broom" (bristles) | "fork" (a hayfork) | "stave" (a curved stave, use r0 ~ 7)"""
    a = math.radians(angle_deg)
    end = (hand[0] + math.cos(a) * length, hand[1] + math.sin(a) * length)
    back = (hand[0] - math.cos(a) * length * 0.12, hand[1] - math.sin(a) * length * 0.12)
    out = []
    if head == "stave":
        n = (-math.sin(a), math.cos(a))
        mid = ((back[0] + end[0]) / 2 + n[0] * length * 0.06, (back[1] + end[1]) / 2 + n[1] * length * 0.06)
        out.append(_smooth([(back[0] + n[0] * r0, back[1] + n[1] * r0), (mid[0] + n[0] * r0, mid[1] + n[1] * r0),
                            (end[0] + n[0] * r0 * 0.8, end[1] + n[1] * r0 * 0.8), (end[0] - n[0] * r0 * 0.8, end[1] - n[1] * r0 * 0.8),
                            (mid[0] - n[0] * r0, mid[1] - n[1] * r0), (back[0] - n[0] * r0, back[1] - n[1] * r0)], 0.4))
    else:
        out.append(_poly(capsule(back, end, r0, r1 or r0)))
    if head == "pick":
        n = (-math.sin(a), math.cos(a))
        L = length * 0.42
        out.append(_smooth([(end[0] + n[0] * L, end[1] + n[1] * L), (end[0] + math.cos(a) * r0 * 2.2, end[1] + math.sin(a) * r0 * 2.2),
                            (end[0] - n[0] * L * 0.85, end[1] - n[1] * L * 0.85), (end[0] - math.cos(a) * r0 * 1.2, end[1] - math.sin(a) * r0 * 1.2)], 0.3))
    elif head == "broom":
        n = (-math.sin(a), math.cos(a))
        b0 = (end[0] - math.cos(a) * length * 0.02, end[1] - math.sin(a) * length * 0.02)
        tip = (end[0] + math.cos(a) * length * 0.22, end[1] + math.sin(a) * length * 0.22)
        out.append(_poly([(b0[0] + n[0] * r0 * 1.5, b0[1] + n[1] * r0 * 1.5), (tip[0] + n[0] * length * 0.1, tip[1] + n[1] * length * 0.1),
                          (tip[0] - n[0] * length * 0.1, tip[1] - n[1] * length * 0.1), (b0[0] - n[0] * r0 * 1.5, b0[1] - n[1] * r0 * 1.5)]))
    elif head == "fork":
        n = (-math.sin(a), math.cos(a))
        u = (math.cos(a), math.sin(a))
        L = length * 0.2
        w = length * 0.075
        bar0, bar1 = (end[0] + n[0] * w, end[1] + n[1] * w), (end[0] - n[0] * w, end[1] - n[1] * w)
        out.append(_poly(capsule(bar0, bar1, r0 * 0.8, r0 * 0.8)))
        for off in (-w, 0.0, w):
            root = (end[0] + n[0] * off, end[1] + n[1] * off)
            out.append(_poly(capsule(root, (root[0] + u[0] * L, root[1] + u[1] * L), r0 * 0.65, r0 * 0.2)))
    return "".join(f'<path d="{d}" fill="{_gray(tone)}" data-h="solid"/>' for d in out)


def _gray(t):
    v = int(round((1 - max(0, min(1, t))) * 255))
    return f"#{v:02x}{v:02x}{v:02x}"


def reference_sheet():
    """every pose, hat and held prop on one tone-coded SVG page. ./movie figures engraves it so you can look at it."""
    from .svgkit import doc
    items, labels = [], []
    poses = list(POSES)
    for i, name in enumerate(poses):
        cx, cy = 90 + (i % 13) * 146, 280 + (i // 13) * 300
        items.append(figure(name, hat="none", coat="jacket", x=cx, y=cy, height=210))
        labels.append(f'<text x="{cx}" y="{cy + 28}" text-anchor="middle" font-family="Georgia, serif" font-size="17" '
                      f'fill="#222" data-h="solid">{name}</text>')
    hats = ["cap", "bowler", "fedora", "top", "boater", "miner", "slouch", "hood", "crown", "helmet"]
    for i, hat in enumerate(hats):
        cx, cy = 100 + i * 150, 1000
        items.append(figure("stand", hat=hat, coat="long", x=cx, y=cy, height=240))
        labels.append(f'<text x="{cx}" y="{cy + 28}" text-anchor="middle" font-family="Georgia, serif" font-size="17" '
                      f'fill="#222" data-h="solid">{hat}</text>')
    svg, pts = figure("carry", hat="none", coat="none", child=True, dress=True, hair="braids", x=1640, y=1000, height=190, anchors=True)
    items.append(svg)
    svg, pts = figure("sweep", hat="cap", coat="jacket", x=1740, y=1000, height=240, anchors=True)
    items.append(svg + held(pts["hand_f"], 80, 110, r0=3.2, head="broom"))
    return doc(1920, 1080, '<rect width="1920" height="1080" fill="#fff" data-h="paper"/>' + "".join(items) + "".join(labels))
