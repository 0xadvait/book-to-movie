"""Word timings for each narration clip: whisper word timestamps mapped back onto the script's own words, so a cue like
"cue:stave" fires on the word as written even when whisper heard it differently.

Writes audio/voice/chNN/<sid>.words.json {duration, words: [{w, s, e}], match}. Re-runs only clips newer than their json.
Uses mlx-whisper on Apple Silicon and faster-whisper elsewhere. A silent clip is timed proportionally without whisper.
"""
import difflib
import importlib.util
import json
import os

from .project import norm, probe_duration

MLX_MODELS = {"large-v3-turbo": "mlx-community/whisper-large-v3-turbo", "large-v3": "mlx-community/whisper-large-v3-mlx",
              "medium": "mlx-community/whisper-medium-mlx", "small": "mlx-community/whisper-small-mlx",
              "base": "mlx-community/whisper-base-mlx", "tiny": "mlx-community/whisper-tiny-mlx"}
_faster = {}


def backend():
    forced = os.environ.get("MOVIE_WHISPER")
    if forced:
        return forced
    if importlib.util.find_spec("mlx_whisper"):
        return "mlx"
    if importlib.util.find_spec("faster_whisper"):
        return "faster"
    return None


def transcribe(path, model="large-v3-turbo", language="en"):
    """-> [{"word", "start", "end"}]. No initial_prompt on purpose: it makes whisper skip text."""
    be = backend()
    if be == "mlx":
        import mlx_whisper
        r = mlx_whisper.transcribe(str(path), path_or_hf_repo=MLX_MODELS.get(model, model), word_timestamps=True,
                                   language=language, condition_on_previous_text=False, verbose=None)
        return [w for seg in r["segments"] for w in seg.get("words", [])]
    if be == "faster":
        from faster_whisper import WhisperModel
        if model not in _faster:
            _faster[model] = WhisperModel(model, device="auto", compute_type="auto")
        segments, _ = _faster[model].transcribe(str(path), word_timestamps=True, language=language,
                                                condition_on_previous_text=False)
        return [{"word": w.word, "start": w.start, "end": w.end} for s in segments for w in (s.words or [])]
    raise RuntimeError("no whisper backend installed")


def proportional(script, duration):
    """word times from word length alone: good enough for a silent animatic"""
    weights = [len(w) + 1 for w in script]
    total = sum(weights) or 1
    t, out = 0.15, []
    span = max(0.1, duration - 0.3)
    for w in weights:
        d = span * w / total
        out.append((t, t + d))
        t += d
    return out


def map_words(script, asr, duration):
    """script words, asr words -> [(start, end)] per script word, gaps filled by interpolation, and the match ratio"""
    a = [norm(w) for w in script]
    b = [norm(w["word"]) for w in asr]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    times = [None] * len(a)
    blocks = sm.get_matching_blocks()
    for blk in blocks:
        for k in range(blk.size):
            times[blk.a + k] = (asr[blk.b + k]["start"], asr[blk.b + k]["end"])
    i = 0
    while i < len(a):
        if times[i]:
            i += 1
            continue
        j = i
        while j < len(a) and not times[j]:
            j += 1
        lo = times[i - 1][1] if i else 0.0
        hi = times[j][0] if j < len(a) else duration
        step = (hi - lo) / (j - i)
        for k in range(i, j):
            times[k] = (lo + step * (k - i), lo + step * (k - i + 1))
        i = j
    matched = sum(blk.size for blk in blocks) / max(1, len(a))
    return times, matched


def align_chapter(p, ch):
    mod = p.module(ch)
    vdir = p.voice_dir(ch)
    warned = False
    for sid, _, text in mod.S:
        mp3, out = vdir / f"{sid}.mp3", vdir / f"{sid}.words.json"
        if not mp3.exists():
            raise SystemExit(f"no narration for {sid}: run ./movie voice {ch}")
        if out.exists() and out.stat().st_mtime > mp3.stat().st_mtime:
            continue
        script = text.replace("“", '"').split()
        duration = probe_duration(mp3)
        meta_path = vdir / f"{sid}.mp3.json"
        provider = json.loads(meta_path.read_text()).get("provider") if meta_path.exists() else None
        heard = ""
        if provider == "silent" or backend() is None:
            if provider != "silent" and not warned:
                print("align: no whisper installed, timing words by length. Cues will be approximate. "
                      "Run ./setup.sh to install it.")
                warned = True
            times, matched = proportional(script, duration), 0.0
        else:
            asr = transcribe(mp3, p.cfg["whisper"], p.cfg["language"])
            times, matched = map_words(script, asr, duration)
            heard = " ".join(w["word"].strip() for w in asr)
        words = [{"w": w, "s": round(s, 3), "e": round(e, 3)} for w, (s, e) in zip(script, times)]
        out.write_text(json.dumps({"duration": round(duration, 3), "words": words, "match": round(matched, 3), "asr": heard},
                                  indent=0))
        print(f"  {sid}: {duration:.1f}s match {matched:.2f}", flush=True)
