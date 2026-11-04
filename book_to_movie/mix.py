"""Voice-first mix for one chapter: narration, effects and (if switched on) score on the film timeline, then mastered.

Narration lines are levelled to one loudness. A score sits 12 dB under any line and 4 dB under the voice level between
lines (one merged duck, held across gaps under 0.8 s so it never pumps), with a cut at 1.8 kHz where AI masters run hot.
Effects are levelled, then placed at their gain relative to the voice. Master: -16 LUFS, peaks at -1 dBFS.
Prints a per-line audit (music and effects under each line) so the balance is measured, not guessed.
"""
import subprocess

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.signal import lfilter

from .project import cue_seconds

SR = 48000
VOICE_LUFS = -19.0


def load(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"], capture_output=True)
    if r.returncode:
        raise SystemExit(f"cannot read {path}: {r.stderr.decode(errors='replace')[:200]}")
    return np.frombuffer(r.stdout, np.float32).reshape(-1, 2).copy()


def db(g):
    return 10 ** (g / 20)


def peaking(x, f0, gain_db, q):
    A = 10 ** (gain_db / 40)
    w = 2 * np.pi * f0 / SR
    al = np.sin(w) / (2 * q)
    b = np.array([1 + al * A, -2 * np.cos(w), 1 - al * A])
    a = np.array([1 + al / A, -2 * np.cos(w), 1 - al / A])
    return lfilter(b / a[0], a / a[0], x, axis=0)


def mix_chapter(p, ch, audit=True):
    mod = p.module(ch)
    tm = p.timing(ch)
    meter = pyln.Meter(SR)

    def lufs(x):
        try:
            v = meter.integrated_loudness(x)
            return v if np.isfinite(v) else -70.0
        except ValueError:      # shorter than one gating block
            return -70.0

    order = [s[0] for s in mod.S]
    total = tm[order[-1]]["start"] + tm[order[-1]]["duration"] + 1.0
    N = int(total * SR) + SR

    # ---- narration ----
    voice = np.zeros((N, 2), np.float32)
    speech = np.zeros(N, np.float32)
    lines = []
    for sid in order:
        x = load(p.voice_dir(ch) / f"{sid}.mp3")
        level = lufs(x)
        if level > -69:           # a silent animatic stays silent
            x = x * db(VOICE_LUFS - level)
        t0 = tm[sid]["start"] + tm[sid]["vo_offset"]
        i0 = int(t0 * SR)
        L = min(len(x), N - i0)
        voice[i0:i0 + L] += x[:L]
        for w in p.words(ch, sid):
            speech[int((t0 + w["s"]) * SR):int((t0 + w["e"]) * SR)] = 1.0
        lines.append((sid, t0, t0 + len(x) / SR))

    # ---- one merged duck: speech held across short gaps, smoothed attack and release ----
    hold = int(0.8 * SR)
    s = speech.copy()
    idx = np.flatnonzero(s)
    if len(idx):
        for g in np.flatnonzero(np.diff(idx) > 1):
            a, b = idx[g], idx[g + 1]
            if b - a < hold:
                s[a:b] = 1.0
    att, rel = 1 - np.exp(-1 / (0.08 * SR)), 1 - np.exp(-1 / (0.45 * SR))
    step = 64
    coarse = s[::step]
    e = np.zeros_like(coarse)
    v = 0.0
    for k, target in enumerate(coarse):
        c = att if target > v else rel
        v += (target - v) * (1 - (1 - c) ** step)
        e[k] = v
    env = np.repeat(e, step)[:N]

    # ---- score, only when switched on ----
    music = np.zeros((N, 2), np.float32)
    cues = getattr(mod, "MUSIC", {}) if p.cfg["music"] else {}
    starts = {name: tm[cue["sections"][0][1][0]]["start"] for name, cue in cues.items()
              if (p.music_dir(ch) / f"{name}.mp3").exists()}
    if cues and not starts:
        print("  music is on but no cues exist yet: run ./movie music", ch)
    names = sorted(starts, key=starts.get)
    for k, name in enumerate(names):
        x = load(p.music_dir(ch) / f"{name}.mp3")
        x = peaking(x, 1800, -4.5, 0.7).astype(np.float32)
        x = x * db(VOICE_LUFS - lufs(x))
        t0 = starts[name]
        end = starts[names[k + 1]] + 2.5 if k + 1 < len(names) else total
        L = min(len(x), int((end - t0) * SR))
        x = x[:L].copy()
        fi, fo = int(1.2 * SR), int(min(3.0, L / SR / 3) * SR)
        x[:fi] *= np.linspace(0, 1, fi)[:, None]
        x[-fo:] *= np.linspace(1, 0, fo)[:, None]
        i0 = int(t0 * SR)
        L = min(L, N - i0)
        music[i0:i0 + L] += x[:L]
    music *= db(-4.0 + (-8.0) * env)[:, None]          # -4 dB between lines, -12 dB under them

    # ---- effects ----
    sfx = np.zeros((N, 2), np.float32)
    cache, skipped = {}, set()
    for it in (getattr(mod, "SFX", []) if p.cfg["sfx"] else []):
        sid = it["scene"]
        path = p.sfx_dir(ch) / f"{it['name']}.mp3"
        if not path.exists():
            skipped.add(it["name"])
            continue
        if it["name"] not in cache:
            x = load(path)
            cache[it["name"]] = x * db(VOICE_LUFS - lufs(x))
        x = cache[it["name"]]
        at = it.get("at", 0.0)
        offset = float(at) if isinstance(at, (int, float)) else cue_seconds(at, p.words(ch, sid), tm[sid]["vo_offset"])
        t0 = tm[sid]["start"] + offset
        scene_end = tm[sid]["start"] + tm[sid]["duration"] + 0.8
        if it.get("loop") or len(x) / SR < scene_end - t0 and it.get("dur", 0) >= 15:
            reps = int(np.ceil((scene_end - t0) * SR / len(x))) + 1
            xf = int(0.5 * SR)
            y = x.copy()
            for _ in range(reps - 1):
                ramp = np.linspace(0, 1, xf)[:, None]
                y[-xf:] = y[-xf:] * (1 - ramp) + x[:xf] * ramp
                y = np.concatenate([y, x[xf:]])
            x = y
        L = min(len(x), int((scene_end - t0) * SR))
        y = x[:L] * db(it.get("gain", -16))
        fo = int(min(0.8, L / SR / 3) * SR)
        if fo > 0:
            y[-fo:] *= np.linspace(1, 0, fo)[:, None]
        i0 = int(t0 * SR)
        L = min(L, N - i0)
        sfx[i0:i0 + L] += y[:L]
    if skipped:
        print(f"  no audio yet for effects {sorted(skipped)}: mixing without them")

    # ---- per-line correction: pull the score toward 12 dB under each line (at most +/-4 dB), as a smooth curve ----
    if names:
        corr = np.zeros(N, np.float32)
        for _, a, b in lines:
            i0, i1 = int(a * SR), int(b * SR)
            under = lufs(voice[i0:i1]) - lufs(music[i0:i1])
            if under <= 60:
                corr[i0:i1] = np.clip(under - 12.0, -4.0, 4.0)
        music *= db(uniform_filter1d(corr, int(0.6 * SR)))[:, None]

    final = voice + music + sfx

    if audit:
        print(f"  {'scene':24s} voice  music  under    sfx  under")
        for sid, a, b in lines:
            i0, i1 = int(a * SR), int(b * SR)
            lv, lm, lsx = lufs(voice[i0:i1]), lufs(music[i0:i1]), lufs(sfx[i0:i1])
            print(f"  {sid:24s} {lv:6.1f} {lm:6.1f} {lv - lm:6.1f} {lsx:6.1f} {lv - lsx:6.1f}")

    # ---- master: -16 LUFS integrated, then a gentle peak ceiling at -1 dBFS ----
    level = lufs(final)
    if level > -69:
        final = final * db(-16.0 - level)
        ceiling = db(-1.0)
        if np.max(np.abs(final)) > ceiling:
            peak = np.abs(final).max(axis=1)
            g = np.minimum(1.0, ceiling / np.maximum(peak, 1e-9))
            win = int(0.005 * SR)
            g = uniform_filter1d(minimum_filter1d(g, win * 4), win * 2)
            final = final * g[:, None]
    out = p.mix_dir() / f"{ch}_mix.wav"
    sf.write(out, final[:int(total * SR)], SR, subtype="PCM_24")
    sf.write(p.mix_dir() / f"{ch}_voice.wav", voice[:int(total * SR)], SR, subtype="PCM_24")
    print(f"  mix {lufs(final):.1f} LUFS, peak {20 * np.log10(np.max(np.abs(final)) + 1e-9):.2f} dBFS, {total:.2f} s -> {out}")
    return out
