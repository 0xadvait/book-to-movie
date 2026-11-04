"""Where a project stands, what it will cost, and whether this machine can make films."""
import json
import os
import platform
import re
import shutil
import subprocess
import sys

from . import align
from .project import HYPERFRAMES, elevenlabs_key, fal_key
from .voice import pick_provider

# fal's listed prices when this was written. Look them up before a big run.
PRICE_VOICE_PER_1K_CHARS = 0.10
PRICE_SFX_PER_SECOND = 0.002
PRICE_MUSIC_PER_MINUTE = 0.60


def chapter_state(p, ch):
    mod = p.module(ch)
    sids = [s[0] for s in mod.S]
    voice = sum((p.voice_dir(ch) / f"{s}.words.json").exists() for s in sids)
    specs = sum((p.specs(ch) / f"{s}.json").exists() for s in sids)
    clips = sum((p.renders_dir(ch) / f"{s}.mp4").exists() for s in sids)
    sets_ = {s[1] for s in mod.S if not s[1].startswith("card:")}
    drawn = sum((p.film / "assets" / "art" / ch / name / "layers.json").exists() for name in sets_)
    mins = None
    tpath = p.specs(ch) / "_timing.json"
    if tpath.exists():
        tm = json.loads(tpath.read_text())
        if tm:
            last = tm[sids[-1]] if sids[-1] in tm else None
            mins = round((last["start"] + last["duration"]) / 60, 1) if last else None
    return {"chapter": ch, "scenes": len(sids), "voice": voice, "sets": f"{drawn}/{len(sets_)}", "specs": specs, "clips": clips,
            "mix": (p.mix_dir() / f"{ch}_mix.wav").exists(), "master": p.master(ch).exists(), "minutes": mins}


def next_step(s, ch):
    if s["voice"] < s["scenes"]:
        return f"./movie voice {ch}"
    if s["specs"] < s["scenes"]:
        return f"illustrate: {s['scenes'] - s['specs']} scene specs missing (./movie sheet {ch} lists them)"
    if s["clips"] < s["scenes"] or not s["master"]:
        return f"./movie finish {ch}"
    return "done"


def show_status(p):
    print(f"{p.cfg['title']}  [{p.slug}]  {p.root}")
    print(f"voice {pick_provider(p.cfg['voice']['provider'])}, look {p.cfg['look'] if isinstance(p.cfg['look'], str) else 'custom'}, "
          f"music {'on' if p.cfg['music'] else 'off'}, sound effects {'on' if p.cfg['sfx'] else 'off'}")
    index = p.root / "source" / "chapters.json"
    if index.exists():
        parts = json.loads(index.read_text())
        print(f"book: {len(parts)} sections, {sum(c['words'] for c in parts):,} words (source/chapters.json)")
    if (p.root / "TREATMENT.md").exists():
        print("treatment: TREATMENT.md")
    else:
        print("treatment: not written yet")
    chapters = p.chapters()
    if not chapters:
        print("no scripts yet (story/chNN.py).")
        return
    print(f"{'part':6s} {'scenes':>6s} {'voice':>6s} {'sets':>6s} {'specs':>6s} {'clips':>6s} {'mix':>4s} {'master':>7s} {'min':>6s}  next")
    total = 0.0
    for ch in chapters:
        s = chapter_state(p, ch)
        total += s["minutes"] or 0
        print(f"{ch:6s} {s['scenes']:6d} {s['voice']:6d} {s['sets']:>6s} {s['specs']:6d} {s['clips']:6d} "
              f"{'yes' if s['mix'] else '-':>4s} {'yes' if s['master'] else '-':>7s} {s['minutes'] if s['minutes'] else '-':>6}  {next_step(s, ch)}")
    print(f"total: {total:.1f} min")
    film = p.film / "renders" / f"{p.slug}-film.mp4"
    if film.exists():
        print(f"film: {film}")


def show_cost(p):
    """what the audio will cost at fal's prices. Claude's own usage is separate."""
    print(f"audio estimate for {p.cfg['title']} (fal prices; narration, effects, and music only if switched on)")
    print(f"{'part':6s} {'chars':>8s} {'voice':>8s} {'sfx s':>7s} {'sfx':>7s} {'music m':>8s} {'music':>8s}")
    totals = [0.0, 0.0, 0.0]
    for ch in p.chapters():
        mod = p.module(ch)
        chars = sum(len(s[2]) for s in mod.S)
        unique = {it["name"]: it for it in getattr(mod, "SFX", [])}
        sfx_s = sum(it.get("dur") or 5 for it in unique.values())
        words = sum(len(s[2].split()) for s in mod.S)
        music_m = (words / 175) if (getattr(mod, "MUSIC", None) and p.cfg["music"]) else 0.0
        v, s_, m = chars / 1000 * PRICE_VOICE_PER_1K_CHARS, sfx_s * PRICE_SFX_PER_SECOND, music_m * PRICE_MUSIC_PER_MINUTE
        totals = [totals[0] + v, totals[1] + s_, totals[2] + m]
        print(f"{ch:6s} {chars:8d} {'$%.2f' % v:>8s} {sfx_s:7.0f} {'$%.2f' % s_:>7s} {music_m:8.1f} {'$%.2f' % m:>8s}")
    print(f"total about ${sum(totals):.2f}: voice ${totals[0]:.2f}, effects ${totals[1]:.2f}, music ${totals[2]:.2f}")
    print("the free say, espeak and silent voices cost nothing; re-voicing only repeats scenes whose text changed")


def doctor():
    """-> True when everything required is present. Key values are never printed, only whether they are set."""
    ok = True
    mac, apt = platform.system() == "Darwin", shutil.which("apt-get") is not None

    def hint(brew, deb):
        return f"brew install {brew}" if mac else (f"sudo apt-get install -y {deb}" if apt else f"install {deb}")

    def report(name, good, fix="", required=True):
        nonlocal ok
        if good:
            print(f"  ok       {name}")
        elif required:
            ok = False
            print(f"  MISSING  {name}: {fix}")
        else:
            print(f"  optional {name}: {fix}")

    print("system")
    report("python 3.10+", sys.version_info >= (3, 10), "install a newer Python")
    report("ffmpeg", shutil.which("ffmpeg") and shutil.which("ffprobe"), hint("ffmpeg", "ffmpeg"))
    report("rsvg-convert", shutil.which("rsvg-convert"), hint("librsvg", "librsvg2-bin"))
    node_ok = False
    if shutil.which("node"):
        v = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip()
        m = re.match(r"v(\d+)", v)
        node_ok = bool(m and int(m.group(1)) >= 22)
    report("node 22+ and npx", node_ok and shutil.which("npx"), hint("node", "nodejs (22 or newer, from nodejs.org)"))
    report("pdftotext (only for PDFs)", shutil.which("pdftotext"), hint("poppler", "poppler-utils"), required=False)
    print("python packages")
    for mod in ("numpy", "scipy", "cv2", "PIL", "lxml", "soundfile", "pyloudnorm"):
        try:
            __import__(mod)
            report(mod, True)
        except ImportError:
            report(mod, False, "run ./setup.sh")
    report(f"whisper ({align.backend()})", align.backend() is not None, "run ./setup.sh (word timing falls back to a rough guess)", required=False)
    print("voice and sound")
    report("FAL_KEY (narration + effects, about $1 per 10 minutes of film)", fal_key(), "add it to .env for a real narrator", required=False)
    report("ELEVENLABS_API_KEY (narration, your own plan)", elevenlabs_key(), "or add this to .env instead", required=False)
    print(f"  voice used by default: {pick_provider('auto')}")
    print(f"renderer\n  hyperframes@{HYPERFRAMES} via npx (downloaded on the first render, with a headless browser)")
    free = shutil.disk_usage(os.getcwd()).free / 1e9
    report(f"disk space ({free:.0f} GB free)", free > 5, "a short film needs a few GB and a feature-length one tens of GB", required=False)
    print("ready" if ok else "not ready: fix the MISSING lines above")
    return ok
