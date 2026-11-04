"""Build one standalone HyperFrames composition per scene from a scene spec (JSON).

Everything on screen is a pure function of time: a single clock tween drives render(t), which places every layer
from the camera, its depth and its own motion, so any frame can be seeked and re-rendered exactly.

Spec (story/specs/chNN/<sid>.json):
{
  "id": "s07-train", "set": "train",
  "layers": [ {"name": "sky", "src": "sky.png", "z": 0.0,
               "box": [x, y, w, h]            # optional, design px on the 1920x1080 stage; default = set canvas
               "scroll": {"speed": -260, "tile": 2112},       # endless horizontal drift (px/s), tiled copies
               "bob": {"amp": 1.2, "period": 0.42, "phase": 0},
               "sway": {"amp": 1.5, "period": 3.1, "origin": [x, y]},       # degrees, origin in layer px
               "spin": {"speed": 240, "origin": [x, y]},                    # degrees per second
               "move": [ {"t": 0, "x": 0, "y": 0, "s": 1, "r": 0, "o": 1}, {"t": "cue:freight", "x": -40, "ease": "power2.inOut"} ],
               "origin": [x, y],                                            # for move scale/rotation
               "frames": {"srcs": ["walk1.png", ...], "fps": 8},           # sprite cycle, or "keys": [[time, index], ...]
               "blend": "screen" } ],
  "camera": [ {"t": 0, "x": 0, "y": 0, "zoom": 1}, {"t": "end", "x": 40, "zoom": 1.06, "ease": "sine.inOut"} ],
  "fx": [ {"type": "glow", "x": 1090, "y": 715, "r": 520, "color": "#fff1c4", "opacity": 0.3, "z": 0.1, "flicker": 0.05},
          {"type": "beam", "points": [[x,y],...], "color": "#fff3d0", "opacity": 0.22, "z": 0.5},
          {"type": "dust", "box": [x, y, w, h], "n": 60, "z": 0.6, "color": "#fff6dc"},
          {"type": "sparkle", "x": 900, "y": 600, "at": "cue:gold", "size": 26, "z": 0.7},
          {"type": "fade", "color": "#000", "keys": [{"t": 0, "o": 1}, {"t": 0.8, "o": 0}]} ],
  "text": [ {"type": "quote", "text": "...", "attr": "A Person", "box": [x, y, w], "size": 46, "at": "cue:stood", "until": "end"},
            {"type": "title", "text": "A TITLE", "at": 0.4, "until": "end", "y": 470, "size": 96},
            {"type": "stamp", "text": "QUIT", "at": "cue:quit", "x": 1300, "y": 380, "rot": -8, "size": 120},
            {"type": "label", "text": "A PLACE NAME", "at": 0.6, "until": 5.0},
            {"type": "words", "text": "a kinetic line | that lands word by word", "at": "cue:line"} ]
}
Times: seconds from scene start, "end", or "cue:<word>[#n][+/-sec]" = start of the n-th spoken occurrence (1-based)
of <word> in the scene's narration, which begins at the scene's vo_offset.
"""
import html
import json
import re

from .project import STAGE_H, STAGE_W, cue_seconds, norm

CANVAS = (-96, -54, 2112, 1188)      # default layer box: the set canvas, centred on the stage


class Clock:
    def __init__(self, words, vo_offset, dur):
        self.words, self.off, self.dur = words, vo_offset, dur

    def t(self, v):
        if isinstance(v, (int, float)):
            return round(float(v), 3)
        if v == "end":
            return self.dur
        return cue_seconds(v, self.words, self.off)


def keys(seq, clk, fields, defaults):
    out = []
    for k in seq:
        d = {"t": clk.t(k.get("t", 0)), "ease": k.get("ease", "sine.inOut")}
        for f in fields:
            d[f] = k.get(f, None)
        out.append(d)
    out.sort(key=lambda d: d["t"])
    # carry values forward so every key is complete
    last = dict(defaults)
    for d in out:
        for f in fields:
            if d[f] is None:
                d[f] = last[f]
            last[f] = d[f]
    return out


def quote_spans(text, words, vo_offset, clk_at):
    """map each word of an on-screen quote to the time it is spoken (sequence alignment, so words the narration
    adds inside the quote, like "he said", are skipped); unmatched words take their neighbours' times"""
    import difflib
    q = text.split()
    nq = [norm(w) for w in q]
    nw = [norm(w["w"]) for w in words]
    sm = difflib.SequenceMatcher(None, nq, nw, autojunk=False)
    t = [None] * len(q)
    for b in sm.get_matching_blocks():
        for k in range(b.size):
            t[b.a + k] = round(vo_offset + words[b.b + k]["s"], 3)
    last = clk_at
    for k in range(len(q)):
        if t[k] is None:
            nxt = next((t[j] for j in range(k + 1, len(q)) if t[j] is not None), None)
            t[k] = last if nxt is None else min(nxt, last + 0.25)
        last = t[k]
    return q, t


def build(p, chapter, sid):
    spec_path = p.specs(chapter) / f"{sid}.json"
    if not spec_path.exists():
        raise FileNotFoundError(f"no scene spec: {spec_path}")
    FILM, FPS = p.film, p.fps
    sp = json.loads(spec_path.read_text())
    tm = p.timing(chapter)[sid]
    dur, vo_off = tm["duration"] + tm.get("handle", 1.0), tm["vo_offset"]   # rendered with a tail handle for the dissolve
    words = p.words(chapter, sid)
    clk = Clock(words, vo_off, dur)
    set_dir = f"../../assets/art/{chapter}/{sp['set']}" if sp.get("set") else "../../assets/art"
    E = html.escape

    layers_js, layers_html = [], []
    for i, L in enumerate(sp.get("layers", [])):
        bx, by, bw, bh = L.get("box", CANVAS)
        lid = f"L{i}"
        if "svg" in L:
            raw = (FILM / "assets" / "art" / chapter / sp["set"] / L["svg"]).read_text()
            raw = re.sub(r"<\?xml[^>]*>", "", raw)
            raw = re.sub(r"<svg ", f'<svg style="position:absolute;left:0;top:0;width:{bw}px;height:{bh}px;overflow:visible" ', raw, count=1)
            if L.get("draw"):
                raw = raw.replace("<path ", '<path pathLength="1" ')
            blend = f' style="mix-blend-mode:{L["blend"]}"' if L.get("blend") else ""
            op = f"opacity:{L['opacity']};" if "opacity" in L else ""
            layers_html.append(f'<!--L:{L.get("name", "")}--><div class="par" id="{lid}p"{blend}><div class="lay{" draw" if L.get("draw") else ""}" id="{lid}" '
                               f'style="left:{bx}px;top:{by}px;width:{bw}px;height:{bh}px;{op}">{raw}</div></div>')
            kf = keys(L.get("move", []), clk, ["x", "y", "s", "r", "o"], {"x": 0, "y": 0, "s": 1, "r": 0, "o": L.get("opacity", 1)})
            layers_js.append({"id": lid, "z": L.get("z", 0.5), "move": kf, "origin": L.get("origin", [bw / 2, bh / 2]),
                              "scroll": None, "bob": L.get("bob"), "sway": L.get("sway"), "spin": L.get("spin"), "frames": None,
                              "draw": keys(L["draw"], clk, ["p"], {"p": 0}) if L.get("draw") else None})
            continue
        srcs = L["frames"]["srcs"] if "frames" in L else [L["src"]]
        tile = L.get("scroll", {}).get("tile")
        copies = 2 if tile else 1
        imgs = ""
        for c in range(copies):
            for fi, s in enumerate(srcs):
                src = s if s.startswith("../../assets/") else f"{set_dir}/{s}"
                vis = "" if fi == 0 else "visibility:hidden;"
                imgs += (f'<img class="im" data-f="{fi}" data-c="{c}" src="{E(src)}" '
                         f'style="left:{c * (tile or 0)}px;width:{bw}px;height:{bh}px;{vis}">')
        blend = f' style="mix-blend-mode:{L["blend"]}"' if L.get("blend") else ""
        op = f"opacity:{L['opacity']};" if "opacity" in L else ""
        layers_html.append(f'<!--L:{L.get("name", "")}--><div class="par" id="{lid}p"{blend}><div class="lay" id="{lid}" style="left:{bx}px;top:{by}px;'
                           f'width:{bw}px;height:{bh}px;{op}">{imgs}</div></div>')
        mv = keys(L.get("move", []), clk, ["x", "y", "s", "r", "o"], {"x": 0, "y": 0, "s": 1, "r": 0, "o": L.get("opacity", 1)})
        spin = L.get("spin")
        js = {"id": lid, "z": L.get("z", 0.5), "move": mv, "origin": L.get("origin", [bw / 2, bh / 2]),
              "scroll": L.get("scroll"), "bob": L.get("bob"), "sway": L.get("sway"), "spin": spin,
              "frames": ({"n": len(srcs), "fps": L["frames"].get("fps", 8), "keys": L["frames"].get("keys")} if "frames" in L else None)}
        if js["frames"] and js["frames"]["keys"]:
            js["frames"]["keys"] = sorted([[clk.t(k[0]), k[1]] for k in js["frames"]["keys"]], key=lambda k: k[0])
        layers_js.append(js)

    cam = keys(sp.get("camera", [{"t": 0}]), clk, ["x", "y", "zoom"], {"x": 0, "y": 0, "zoom": 1})

    fx_html, fx_js = [], []
    for i, F in enumerate(sp.get("fx", [])):
        fid = f"F{i}"
        typ = F["type"]
        z = F.get("z", 0.5)
        if typ == "glow":
            r = F.get("r", 300)
            fx_html.append(f'<div class="par" id="{fid}p" style="mix-blend-mode:{F.get("blend", "screen")}"><div class="fx" id="{fid}" style="left:{F["x"] - r}px;top:{F["y"] - r}px;'
                           f'width:{2 * r}px;height:{2 * r}px;background:radial-gradient(circle, {F.get("color", "#fff2c8")} 0%, '
                           f'transparent 70%);opacity:{F.get("opacity", 0.3)}"></div></div>')
        elif typ == "beam":
            pts = F["points"]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            poly = ",".join(f"{p[0] - x0}px {p[1] - y0}px" for p in pts)
            ang = F.get("angle", 180)
            fx_html.append(f'<div class="par" id="{fid}p" style="mix-blend-mode:{F.get("blend", "screen")}"><div class="fx" id="{fid}" style="left:{x0}px;top:{y0}px;width:{x1 - x0}px;'
                           f'height:{y1 - y0}px;clip-path:polygon({poly});background:linear-gradient({ang}deg, {F.get("color", "#fff3d0")} 0%, '
                           f'transparent 100%);opacity:{F.get("opacity", 0.25)};filter:blur({F.get("blur", 6)}px)"></div></div>')
        elif typ == "dust":
            fx_html.append(f'<div class="par" id="{fid}p" style="mix-blend-mode:screen"><canvas class="fx" id="{fid}" width="{STAGE_W}" height="{STAGE_H}" '
                           f'style="left:0;top:0;width:{STAGE_W}px;height:{STAGE_H}px"></canvas></div>')
        elif typ == "sparkle":
            sz = F.get("size", 26)
            fx_html.append(f'<div class="par" id="{fid}p" style="mix-blend-mode:screen"><svg class="fx" id="{fid}" viewBox="-50 -50 100 100" style="left:{F["x"] - sz}px;'
                           f'top:{F["y"] - sz}px;width:{2 * sz}px;height:{2 * sz}px;opacity:0">'
                           f'<path d="M0,-50 C4,-8 8,-4 50,0 C8,4 4,8 0,50 C-4,8 -8,4 -50,0 C-8,-4 -4,-8 0,-50Z" fill="{F.get("color", "#ffe9a8")}"/>'
                           f'<circle r="9" fill="#fff8e0"/></svg></div>')
        elif typ in ("fade", "tint"):
            fx_html.append(f'<div class="fx full" id="{fid}" style="background:{F.get("color", "#000")};'
                           f'mix-blend-mode:{F.get("blend", "normal")};opacity:0"></div>')
        if F.get("under"):
            fx_html[-1] = f'<!--UNDER:{F["under"]}-->' + fx_html[-1]
        fj = {"id": fid, "type": typ, "z": z, "flicker": F.get("flicker", 0), "base": F.get("opacity", 0.3)}
        if typ == "dust":
            fj.update({"box": F.get("box", [0, 0, STAGE_W, STAGE_H]), "n": F.get("n", 50), "color": F.get("color", "#fff6dc"),
                       "seed": F.get("seed", i + 1), "size": F.get("size", 2.2), "speed": F.get("speed", 6), "alpha": F.get("opacity", 0.55)})
        if typ == "sparkle":
            fj.update({"at": clk.t(F.get("at", 0)), "len": F.get("len", 1.4)})
        if typ in ("fade", "tint", "glow", "beam"):
            if "keys" in F:
                fj["keys"] = keys(F["keys"], clk, ["o"], {"o": F.get("opacity", 0.3)})
        fx_js.append(fj)

    text_html, text_js = [], []
    for i, T in enumerate(sp.get("text", [])):
        tid = f"T{i}"
        at, until = clk.t(T.get("at", 0)), clk.t(T.get("until", "end"))
        typ = T["type"]
        if typ == "quote":
            x, y, w = T.get("box", [1040, 260, 760])
            q, times = quote_spans(T["text"], words, vo_off, at)
            spans = " ".join(f'<span class="qw" id="{tid}w{k}">{E(wd)}</span>' for k, wd in enumerate(q))
            attr = f'<div class="qa">{E(T["attr"])}</div>' if T.get("attr") else ""
            text_html.append(f'<div class="quote" id="{tid}" style="left:{x}px;top:{y}px;width:{w}px;font-size:{T.get("size", 44)}px">'
                             f'<div class="qr"></div><div class="qt">{spans}</div>{attr}</div>')
            text_js.append({"id": tid, "type": "quote", "at": at, "until": until, "times": times})
        elif typ == "title":
            sub = f'<div class="tsub">{E(T["sub"])}</div>' if T.get("sub") else ""
            eyebrow = f'<div class="teye">{E(T["eyebrow"])}</div>' if T.get("eyebrow") else ""
            text_html.append(f'<div class="title" id="{tid}" style="top:{T.get("y", 420)}px">{eyebrow}<div class="tmain" '
                             f'style="font-size:{T.get("size", 96)}px">{E(T["text"])}</div>{sub}</div>')
            text_js.append({"id": tid, "type": "title", "at": at, "until": until})
        elif typ == "stamp":
            text_html.append(f'<div class="stamp" id="{tid}" style="left:{T["x"]}px;top:{T["y"]}px;font-size:{T.get("size", 110)}px;'
                             f'color:{T.get("color", "var(--accent)")};border-color:{T.get("color", "var(--accent)")}">{E(T["text"])}</div>')
            text_js.append({"id": tid, "type": "stamp", "at": at, "until": until, "rot": T.get("rot", -7)})
        elif typ == "label":
            text_html.append(f'<div class="label" id="{tid}" style="{"left" if T.get("side", "left") == "left" else "right"}:96px;'
                             f'top:{T.get("y", 950)}px">{E(T["text"])}</div>')
            text_js.append({"id": tid, "type": "label", "at": at, "until": until})
        elif typ == "caption":
            x, y, w = T.get("box", [0, 900, 1920])
            text_html.append(f'<div class="cap" id="{tid}" style="left:{x}px;top:{y}px;width:{w}px;font-size:{T.get("size", 26)}px;'
                             f'text-align:{T.get("align", "center")};color:{T.get("color", "var(--ink)")}">{E(T["text"])}</div>')
            text_js.append({"id": tid, "type": "label", "at": at, "until": until})
        elif typ == "words":   # big kinetic line, words land on their spoken times
            x, y, w = T.get("box", [160, 420, 1600])
            q, times = quote_spans(T["text"].replace("|", " "), words, vo_off, at)
            breaks, n_ = set(), 0
            for tok in T["text"].split():
                if tok == "|":
                    breaks.add(n_)
                else:
                    n_ += 1
            spans = " ".join(('<span style="display:block;height:0"></span>' if k in breaks else "") +
                             f'<span class="kw" id="{tid}w{k}">{E(wd)}</span>' for k, wd in enumerate(q))
            text_html.append(f'<div class="kin" id="{tid}" style="left:{x}px;top:{y}px;width:{w}px;font-size:{T.get("size", 84)}px;'
                             f'text-align:{T.get("align", "center")}">{spans}</div>')
            text_js.append({"id": tid, "type": "words", "at": at, "until": until, "times": times})

    # place "under" fx just before their layer; the rest stay above all layers
    under = {}
    rest = []
    for h_ in fx_html:
        m_ = re.match(r"<!--UNDER:([^>]*)-->", h_)
        if m_:
            under.setdefault(m_.group(1), []).append(h_[m_.end():])
        else:
            rest.append(h_)
    merged = []
    for h_ in layers_html:
        m_ = re.match(r"<!--L:([^>]*)-->", h_)
        name = m_.group(1) if m_ else ""
        merged += under.pop(name, [])
        merged.append(h_[m_.end():] if m_ else h_)
    for v_ in under.values():
        rest = v_ + rest
    layers_html, fx_html = merged, rest
    payload = json.dumps({"dur": dur, "fps": FPS, "layers": layers_js, "cam": cam, "fx": fx_js, "text": text_js})
    fonts = "".join(
        f"@font-face{{font-family:'{fam}';src:url('../../assets/fonts/{fn}') format('woff2');font-style:{st};font-weight:{wt};font-display:block}}"
        for fam, st, wt, fn in (line.split("|") for line in (FILM / "assets" / "fonts" / "fonts.txt").read_text().split("\n") if line))
    doc = TEMPLATE.replace("%FONTS%", fonts).replace("%VARS%", css_vars(p)).replace("%SID%", sid).replace("%DUR%", f"{dur:.3f}") \
        .replace("%FPS%", str(FPS)).replace("%LAYERS%", "\n".join(layers_html)).replace("%FX%", "\n".join(fx_html)) \
        .replace("%TEXT%", "\n".join(text_html)).replace("%PAYLOAD%", payload) \
        .replace("%BG%", sp.get("background", p.look["paper"]))
    out = p.scenes_dir(chapter) / f"{sid}.html"
    out.write_text(doc)
    return out


def css_vars(p):
    from .project import hex_rgb, mix_hex
    k = p.look
    rgb = ",".join(str(v) for v in hex_rgb(k["slip"]))
    shade = ",".join(str(v) for v in hex_rgb(k["shade"]))
    night = mix_hex(k["ink"], "#000000", 0.15)
    return (f":root{{--paper:{k['paper']};--slip:{rgb};--shade:{shade};--night:{night};--ink:{k['ink']};--ink-soft:{k['ink_soft']};"
            f"--ink-mute:{k['ink_mute']};--accent:{k['accent']};--label:{k['slip']};"
            f"--font-display:'{p.cfg['fonts']['display']}',serif;--font-body:'{p.cfg['fonts']['body']}',serif}}")


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1920, height=1080" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
%FONTS%
%VARS%
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: 1920px; height: 1080px; overflow: hidden; background: var(--night); }
#root { width: 100%; height: 100%; position: relative; overflow: hidden; background: %BG%; }
#stage { position: absolute; inset: 0; overflow: hidden; }
.par { position: absolute; inset: 0; transform-origin: 960px 540px; will-change: transform; }
.lay { position: absolute; will-change: transform, opacity; }
.lay .im { position: absolute; top: 0; display: block; }
.lay.draw path { stroke-dasharray: 1 1; stroke-dashoffset: var(--d, 1); }
.lay.draw text, .lay.draw circle { opacity: calc(1 - var(--d, 1)); }
.fx { position: absolute; pointer-events: none; }
.fx.full { inset: 0; }
#grain { position: absolute; inset: -64px; background: url('../../assets/fx/grain.png'); opacity: 0.16; mix-blend-mode: overlay; }
#vig { position: absolute; inset: 0; background: radial-gradient(ellipse 72% 70% at 50% 47%, rgba(0,0,0,0) 55%, rgba(var(--shade),0.42) 100%); mix-blend-mode: multiply; }
#flick { position: absolute; inset: 0; background: var(--night); opacity: 0; }
.quote { position: absolute; padding: 44px 52px 40px; background: rgba(var(--slip),0.96); color: var(--ink);
  font-family: var(--font-body); line-height: 1.32; box-shadow: 8px 12px 26px rgba(var(--shade),0.35); opacity: 0; }
.quote .qr { position: absolute; inset: 12px; border: 2px solid var(--ink-soft); outline: 1px solid var(--ink-soft); outline-offset: 5px; pointer-events: none; }
.quote .qw { opacity: 0.2; }
.quote .qa { margin-top: 26px; font-family: var(--font-display); font-size: 22px; letter-spacing: 0.28em; text-transform: uppercase; color: var(--ink-mute); }
.title { position: absolute; left: 230px; right: 230px; text-align: center; color: var(--ink); opacity: 0; }
.title .tmain { font-family: var(--font-display); font-weight: 600; letter-spacing: 0.16em; line-height: 1.1; }
.title .tsub { margin-top: 22px; font-family: var(--font-body); font-style: italic; font-size: 40px; color: var(--ink-soft); }
.title .teye { margin-bottom: 18px; font-family: var(--font-display); font-size: 30px; font-weight: 600; letter-spacing: 0.42em; color: var(--ink-mute); }
.stamp { position: absolute; font-family: var(--font-display); font-weight: 800; letter-spacing: 0.12em; padding: 6px 30px 2px;
  border: 7px double; opacity: 0; transform-origin: 50% 50%; filter: url(#rough); mix-blend-mode: multiply; }
.label { position: absolute; font-family: var(--font-display); font-size: 24px; letter-spacing: 0.36em; color: var(--label);
  padding: 10px 22px; background: rgba(var(--shade),0.72); opacity: 0; }
.kin { position: absolute; font-family: var(--font-body); color: var(--ink); line-height: 1.2; }
.cap { position: absolute; font-family: var(--font-display); font-weight: 600; letter-spacing: 0.3em; opacity: 0; }
.kin .kw { display: inline-block; opacity: 0; }
</style>
</head>
<body>
<div id="root" data-composition-id="%SID%" data-start="0" data-duration="%DUR%" data-width="1920" data-height="1080" data-fps="%FPS%">
  <div id="stage" class="clip" data-start="0" data-duration="%DUR%" data-track-index="0">
%LAYERS%
%FX%
%TEXT%
    <div id="grain"></div>
    <div id="vig"></div>
    <div id="flick"></div>
    <svg width="0" height="0" style="position:absolute"><filter id="rough"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="3"/><feDisplacementMap in="SourceGraphic" scale="5"/></filter></svg>
  </div>
</div>
<script>
(function () {
  var P = %PAYLOAD%;
  var D = P.dur;
  var $ = function (id) { return document.getElementById(id); };
  var EASE = {};
  function ease(name) { if (!EASE[name]) EASE[name] = gsap.parseEase(name || "none"); return EASE[name]; }
  function interp(ks, t, f) {
    if (!ks.length) return null;
    if (t <= ks[0].t) return ks[0][f];
    for (var i = 1; i < ks.length; i++) {
      if (t <= ks[i].t) {
        var a = ks[i - 1], b = ks[i], u = (t - a.t) / Math.max(1e-6, b.t - a.t);
        u = ease(b.ease)(Math.min(1, Math.max(0, u)));
        return a[f] + (b[f] - a[f]) * u;
      }
    }
    return ks[ks.length - 1][f];
  }
  function hash(n) { var x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); }
  function rng(seed) { var s = seed * 9301 + 49297; return function () { s = (s * 9301 + 49297) % 233280; return s / 233280; }; }
  var dust = {};
  P.fx.forEach(function (f) {
    if (f.type !== "dust") return;
    var r = rng(f.seed), pts = [];
    for (var i = 0; i < f.n; i++) pts.push([r(), r(), r(), 0.4 + r() * 0.9, r() * 6.28]);
    dust[f.id] = pts;
  });
  function render(t) {
    t = Math.max(0, Math.min(D, t));
    var cx = interp(P.cam, t, "x") || 0, cy = interp(P.cam, t, "y") || 0, cz = interp(P.cam, t, "zoom") || 1;
    function par(el, z) {
      var s = 1 + (cz - 1) * (0.35 + 0.65 * z);
      el.style.transform = "translate(" + (-cx * z).toFixed(2) + "px," + (-cy * z).toFixed(2) + "px) scale(" + s.toFixed(5) + ")";
    }
    P.layers.forEach(function (L) {
      var el = $(L.id); par($(L.id + "p"), L.z);
      var x = interp(L.move, t, "x") || 0, y = interp(L.move, t, "y") || 0;
      var s = L.move.length ? interp(L.move, t, "s") : 1, r = L.move.length ? interp(L.move, t, "r") : 0;
      var o = L.move.length ? interp(L.move, t, "o") : null;
      if (L.scroll) { var tile = L.scroll.tile || 2112; x += ((L.scroll.speed * t) % tile + tile) % tile - tile; }
      if (L.bob) y += L.bob.amp * Math.sin(6.2832 * t / L.bob.period + (L.bob.phase || 0));
      if (L.sway) r += L.sway.amp * Math.sin(6.2832 * t / L.sway.period + (L.sway.phase || 0));
      if (L.spin) r += L.spin.speed * t;
      var org = (L.spin && L.spin.origin) || (L.sway && L.sway.origin) || L.origin;
      el.style.transformOrigin = org[0] + "px " + org[1] + "px";
      el.style.transform = "translate(" + x.toFixed(2) + "px," + y.toFixed(2) + "px) rotate(" + r.toFixed(3) + "deg) scale(" + s.toFixed(5) + ")";
      if (o !== null) el.style.opacity = Math.max(0, Math.min(1, o)).toFixed(4);
      if (L.draw) el.style.setProperty("--d", (1 - Math.max(0, Math.min(1, interp(L.draw, t, "p")))).toFixed(4));
      if (L.frames) {
        var fi;
        if (L.frames.keys) { fi = 0; L.frames.keys.forEach(function (k) { if (t >= k[0]) fi = k[1]; }); }
        else fi = Math.floor(t * L.frames.fps) % L.frames.n;
        el.querySelectorAll(".im").forEach(function (im) { im.style.visibility = (+im.dataset.f === fi) ? "visible" : "hidden"; });
      }
    });
    P.fx.forEach(function (f) {
      var el = $(f.id); if (!el) return;
      var pe = $(f.id + "p"); if (pe) par(pe, f.z);
      var frame = Math.floor(t * P.fps);
      if (f.type === "glow" || f.type === "beam") {
        var o = f.keys ? interp(f.keys, t, "o") : f.base;
        if (f.flicker) o *= 1 - f.flicker * (0.5 + 0.5 * Math.sin(t * 9.1) * Math.sin(t * 3.7 + 1.3) + 0.4 * (hash(frame) - 0.5));
        el.style.opacity = Math.max(0, o).toFixed(4);
      } else if (f.type === "fade" || f.type === "tint") {
        el.style.opacity = Math.max(0, Math.min(1, f.keys ? interp(f.keys, t, "o") : 0)).toFixed(4);
      } else if (f.type === "sparkle") {
        var u = (t - f.at) / f.len, a = (u < 0 || u > 1) ? 0 : Math.sin(Math.PI * u);
        el.style.opacity = a.toFixed(3);
        el.style.transform = "rotate(" + (u * 70).toFixed(2) + "deg) scale(" + (0.35 + 0.75 * a).toFixed(3) + ")";
      } else if (f.type === "dust") {
        var g = el.getContext("2d"); g.clearRect(0, 0, el.width, el.height);
        var b = f.box;
        g.fillStyle = f.color;
        dust[f.id].forEach(function (p) {
          var x = b[0] + ((p[0] * b[2] + Math.sin(t * 0.21 * p[3] + p[4]) * 26 + t * f.speed * (p[3] - 0.6)) % b[2] + b[2]) % b[2];
          var y = b[1] + ((p[1] * b[3] - t * f.speed * 0.6 * p[3] + Math.cos(t * 0.17 + p[4]) * 18) % b[3] + b[3]) % b[3];
          var tw = 0.55 + 0.45 * Math.sin(t * (1.2 + p[2]) + p[4]);
          g.globalAlpha = f.alpha * tw * p[2];
          g.beginPath(); g.arc(x, y, f.size * (0.5 + p[2]), 0, 6.2832); g.fill();
        });
      }
    });
    P.text.forEach(function (T) {
      var el = $(T.id);
      var vin = Math.min(1, Math.max(0, (t - T.at) / 0.7)), vout = Math.min(1, Math.max(0, (T.until - t) / 0.6));
      var v = Math.min(vin, vout);
      if (T.type === "quote") {
        el.style.opacity = v.toFixed(3);
        el.style.transform = "translateY(" + ((1 - ease("power3.out")(vin)) * 26).toFixed(2) + "px)";
        T.times.forEach(function (wt, k) { var w = $(T.id + "w" + k); var u = Math.min(1, Math.max(0, (t - wt + 0.05) / 0.28)); w.style.opacity = (0.2 + 0.8 * u).toFixed(3); });
      } else if (T.type === "title") {
        el.style.opacity = v.toFixed(3);
        el.style.letterSpacing = "0";
        el.style.transform = "translateY(" + ((1 - ease("power3.out")(vin)) * 18).toFixed(2) + "px)";
      } else if (T.type === "stamp") {
        var u = Math.min(1, Math.max(0, (t - T.at) / 0.32));
        var sc = u < 1 ? 1.9 - 0.9 * ease("power4.in")(u) : 1;
        el.style.opacity = (u > 0 ? Math.min(1, u * 3) : 0) * vout;
        el.style.transform = "rotate(" + T.rot + "deg) scale(" + sc.toFixed(4) + ")";
      } else if (T.type === "label") {
        el.style.opacity = (v * 0.95).toFixed(3);
      } else if (T.type === "words") {
        T.times.forEach(function (wt, k) { var w = $(T.id + "w" + k); var u = Math.min(1, Math.max(0, (t - wt + 0.08) / 0.45));
          w.style.opacity = (ease("power2.out")(u) * vout).toFixed(3); w.style.transform = "translateY(" + ((1 - ease("power3.out")(u)) * 22).toFixed(2) + "px)"; });
      }
    });
    var frame = Math.floor(t * P.fps);
    $("grain").style.transform = "translate(" + Math.floor(hash(frame) * 64 - 32) + "px," + Math.floor(hash(frame + 99) * 64 - 32) + "px)";
    $("flick").style.opacity = (0.015 + 0.03 * hash(frame * 3 + 7)).toFixed(4);
  }
  var clock = { t: 0 };
  var tl = gsap.timeline({ paused: true });
  tl.to(clock, { t: D, duration: D, ease: "none", onUpdate: function () { render(clock.t); } }, 0);
  window.addEventListener("hf-seek", function (e) { if (e && e.detail && typeof e.detail.time === "number") render(e.detail.time); });
  render(0);
  window.__timelines = window.__timelines || {};
  window.__timelines["%SID%"] = tl;
})();
</script>
</body>
</html>
"""
