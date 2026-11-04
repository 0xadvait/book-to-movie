"""Final checks on an assembled chapter: whisper of the mixed soundtrack against the script per scene, how names were heard,
loudness, and that every scene's midpoint in the film matches its own render."""
import difflib
import json
import re
import subprocess

import numpy as np

from . import align
from .project import norm


def _frame(src, t):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1", "-vf", "scale=480:270", "-f", "rawvideo",
                        "-pix_fmt", "gray", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.uint8).astype(np.float32)


def unheard_names(scenes, words):
    """capitalised words whisper never heard, in any case. Listen to these."""
    heard = {norm(w["word"]) for w in words}
    names = sorted({n for _, _, t in scenes for n in re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*", t) if len(n) > 3})
    return [n for n in names if norm(n.split()[-1]) not in heard][:30]


def parse_loudness(ebur128_log):
    """the integrated loudness and true peak from ffmpeg's ebur128 summary"""
    summary = ebur128_log.split("Summary:")[-1]
    level = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", summary)
    peak = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    return f"{level.group(1) if level else '?'} LUFS, peak {peak.group(1) if peak else '?'} dBFS"


def _is_silent(p, ch, mod):
    meta = p.voice_dir(ch) / f"{mod.S[0][0]}.mp3.json"
    return meta.exists() and json.loads(meta.read_text()).get("provider") == "silent"


def qa_chapter(p, ch):
    mod = p.module(ch)
    tm = p.timing(ch)
    film = p.master(ch)
    if not film.exists():
        raise SystemExit(f"no master for {ch}: run ./movie assemble {ch}")
    if _is_silent(p, ch, mod) or align.backend() is None:
        print("  whisper check skipped (silent animatic, or no whisper installed)")
    else:
        wav = p.qa() / f"{ch}_master.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(film), "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
        words = align.transcribe(wav, p.cfg["whisper"], p.cfg["language"])
        low, scores = [], []
        for sid, _, text in mod.S:
            a = tm[sid]["start"] + tm[sid]["vo_offset"] - 1.2
            b = tm[sid]["start"] + tm[sid]["vo_offset"] + tm[sid]["vo_duration"] + 0.6
            heard = " ".join(w["word"] for w in words if a <= w["start"] <= b)
            ratio = difflib.SequenceMatcher(None, "".join(norm(x) for x in text.split()),
                                            "".join(norm(x) for x in heard.split()), autojunk=False).ratio()
            scores.append(ratio)
            if ratio < 0.9:
                low.append((sid, round(ratio, 2), heard[:140]))
        print(f"  whisper: {len(scores)} scenes, min {min(scores):.3f}, mean {sum(scores) / len(scores):.3f}; below 0.90: {low or 'none'}")
        if low:
            print("  full-file whisper sometimes skips words: re-check a flagged scene on its own before paying to re-voice it")
        print(f"  names not heard as written (check how they sound): {unheard_names(mod.S, words) or 'none'}")
    errs = []
    for sid, _, _ in mod.S:
        clip = p.renders_dir(ch) / f"{sid}.mp4"
        if not clip.exists():
            continue
        d = tm[sid]["duration"]
        x, y = _frame(film, tm[sid]["start"] + d / 2), _frame(clip, d / 2)
        errs.append((float(np.abs(x - y).mean()) if len(x) == len(y) and len(x) else 999.0, sid))
    if errs:
        print(f"  picture: every scene sits where it should if this is a few points at most. Worst difference from its own render: "
              f"{max(errs)[0]:.2f}/255 ({max(errs)[1]})")
    out = subprocess.run(["ffmpeg", "-nostats", "-i", str(film), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    print(f"  loudness: {parse_loudness(out)}")
