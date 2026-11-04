"""Render scene compositions to video with HyperFrames. A scene whose composition and images have not changed is not
rendered again: a film has thousands of seconds of picture and nobody should pay for them twice."""
import hashlib
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import scene_html
from .project import HYPERFRAMES, probe_duration, tail


def npx_path():
    npx = shutil.which("npx")
    if not npx:
        raise SystemExit("npx not found: install Node 22 or newer (macOS: brew install node)")
    return npx


def composition_hash(html_path):
    """the composition's text plus the size and age of every image it uses"""
    text = Path(html_path).read_text()
    h = hashlib.sha1(text.encode())
    for src in sorted(set(re.findall(r'''(?:src="|url\(')(\.\./\.\./assets/[^"']+)''', text))):
        f = (Path(html_path).parent / src).resolve()
        h.update(f"{src}:{f.stat().st_size}:{f.stat().st_mtime_ns}".encode() if f.exists() else f"{src}:missing".encode())
    return h.hexdigest()


def render_one(p, ch, sid, workers=2, force=False):
    try:
        html = scene_html.build(p, ch, sid)
    except FileNotFoundError:
        return sid, "no spec"
    out = p.renders_dir(ch) / f"{sid}.mp4"
    stamp = out.with_suffix(".hash")
    key = composition_hash(html)
    if not force and out.exists() and stamp.exists() and stamp.read_text() == key:
        return sid, "unchanged"
    log = p.logs() / f"render-{ch}-{sid}.log"
    rel_html = os.path.relpath(html, p.film)
    rel_out = os.path.relpath(out, p.film)
    cmd = [npx_path(), "--yes", f"hyperframes@{HYPERFRAMES}", "render", "-c", rel_html, "-o", rel_out, "--fps", str(p.fps),
           "--quiet", "--workers", str(workers)]
    out.unlink(missing_ok=True)
    for _ in range(2):      # headless browsers occasionally die; one retry clears it
        with open(log, "w") as f:
            subprocess.run(cmd, cwd=p.film, stdout=f, stderr=subprocess.STDOUT)
        if out.exists():
            stamp.write_text(key)
            return sid, "rendered"
    return sid, f"FAILED (log: {log})\n{tail(log, 12)}"


def render_scenes(p, ch, sids=None, jobs=None, workers=None, force=False):
    mod = p.module(ch)
    order = [s[0] for s in mod.S]
    wanted = sids or order
    unknown = [s for s in wanted if s not in order]
    if unknown:
        raise SystemExit(f"{ch} has no scene {unknown}. Scenes: {order}")
    cores = os.cpu_count() or 4
    jobs = jobs or max(1, min(4, cores // 4))
    workers = workers or 3
    results = {}
    with ThreadPoolExecutor(jobs) as ex:
        for sid, status in ex.map(lambda s: render_one(p, ch, s, workers, force), wanted):
            print(f"  {status} {sid}", flush=True)
            results[sid] = status
    failed = [s for s, st in results.items() if st.startswith("FAILED")]
    if failed:
        raise SystemExit(f"render failed for {failed}")
    no_spec = [s for s, st in results.items() if st == "no spec"]
    if no_spec:
        print(f"  no spec yet, these will be placeholders in the cut: {no_spec}")
    check_coverage(p, ch, mod, order)


def check_coverage(p, ch, mod, order):
    """every clip must be long enough for its slot and the dissolve out of it"""
    tm = p.timing(ch)
    trans = getattr(mod, "TRANS", {})
    short = []
    for i, sid in enumerate(order):
        video = p.renders_dir(ch) / f"{sid}.mp4"
        if not video.exists():
            continue
        need = tm[sid]["duration"] + (trans.get(order[i + 1], ("fade", 0.8))[1] if i + 1 < len(order) else 1.0)
        got = probe_duration(video)
        if got < need - 0.05:
            short.append((sid, round(got, 2), round(need, 2)))
    if short:
        print(f"  WARNING clips shorter than their slot (scene, has, needs): {short}. Re-render them with ./movie render {ch} <scene> --force")
    else:
        print("  every rendered clip covers its slot")
