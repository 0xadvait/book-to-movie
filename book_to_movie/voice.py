"""Narration, one clip per scene.

Providers: fal (ElevenLabs through fal), elevenlabs (direct), say (macOS, free), espeak (Linux, free) and silent
(no audio, for a timing-accurate animatic before you pay for anything). "auto" uses the best one you have.
Each clip is told its neighbours' text so the delivery flows across scene cuts. A clip whose exact request was already
voiced is reused, so editing one scene re-voices only that scene.
"""
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .project import elevenlabs_key, fal_key

USER_AGENT = "book-to-movie/0.1"
FAL_ENDPOINTS = {"v3": "fal-ai/elevenlabs/tts/eleven-v3", "v2": "fal-ai/elevenlabs/tts/multilingual-v2"}
ELEVEN_MODELS = {"v3": "eleven_v3", "v2": "eleven_multilingual_v2"}
ELEVEN_VOICE_IDS = {"Bill": "pqHfZKP75CvOlQylNhV4"}     # add your own, or put a voice id in movie.json
SILENT_WPM = 175
PERMANENT_HTTP = {400, 401, 402, 403, 404, 422}     # retrying these only wastes time


def explain_http(e):
    """an API error in words a person can act on. Never includes request headers, so never a key."""
    body = ""
    try:
        body = e.read().decode(errors="replace")[:300]
    except (AttributeError, OSError, ValueError):
        pass
    hint = {401: "the API key was refused: check it in .env", 402: "the account is out of credit", 403: "the API key is not allowed to do this"}.get(getattr(e, "code", None), "")
    return " ".join(x for x in (str(e), hint, body) if x)


def pick_provider(requested="auto"):
    if requested != "auto":
        return requested
    if fal_key():
        return "fal"
    if elevenlabs_key():
        return "elevenlabs"
    if platform.system() == "Darwin" and shutil.which("say"):
        return "say"
    if shutil.which("espeak-ng"):
        return "espeak"
    return "silent"


def _http_json(url, body, headers, timeout=300):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": USER_AGENT, **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def download(url, out, timeout=300):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    tmp = f"{out}.part"
    with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    os.replace(tmp, out)


def eleven_voice_id(name):
    """a known name, a raw voice id, or a lookup in your ElevenLabs voice list"""
    if name in ELEVEN_VOICE_IDS:
        return ELEVEN_VOICE_IDS[name]
    if re.fullmatch(r"[A-Za-z0-9]{16,}", name):
        return name
    req = urllib.request.Request("https://api.elevenlabs.io/v1/voices",
                                 headers={"xi-api-key": elevenlabs_key(), "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        for v in json.load(r)["voices"]:
            if v["name"].split(" ")[0].lower() == name.lower() or v["name"].lower() == name.lower():
                return v["voice_id"]
    raise SystemExit(f"no ElevenLabs voice called {name!r}: put its voice id in movie.json")


def to_mp3(src, out):
    tmp = f"{out}.tmp.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-ac", "1", "-ar", "44100",
                    "-c:a", "libmp3lame", "-q:a", "2", tmp], check=True)
    os.replace(tmp, out)


def synth_fal(body, model, out):
    if not fal_key():
        raise SystemExit("FAL_KEY is not set. Add it to .env, or set voice.provider in movie.json to say or silent.")
    raw = _http_json(f"https://fal.run/{FAL_ENDPOINTS[model]}", body, {"Authorization": f"Key {fal_key()}"})
    download(json.loads(raw)["audio"]["url"], out)


def synth_eleven(body, model, out, voice_id):
    if not elevenlabs_key():
        raise SystemExit("ELEVENLABS_API_KEY is not set. Add it to .env, or set voice.provider to say or silent.")
    payload = {"text": body["text"], "model_id": ELEVEN_MODELS[model], "previous_text": body["previous_text"],
               "next_text": body["next_text"],
               "voice_settings": {k: body[k] for k in ("stability", "similarity_boost", "style", "speed")}}
    audio = _http_json(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128", payload,
                       {"xi-api-key": elevenlabs_key()})
    tmp = f"{out}.part"
    Path(tmp).write_bytes(audio)
    os.replace(tmp, out)


def synth_say(text, voice, out):
    with tempfile.TemporaryDirectory() as d:
        script, aiff = Path(d) / "line.txt", Path(d) / "line.aiff"
        script.write_text(text)
        cmd = ["say", "-f", str(script), "-o", str(aiff), "-r", "178"]
        r = subprocess.run(cmd + ["-v", voice], capture_output=True) if voice else None
        if r is None or r.returncode:      # that voice is not installed here: use the system voice
            subprocess.run(cmd, check=True, capture_output=True)
        to_mp3(aiff, out)


def synth_espeak(text, language, out):
    with tempfile.TemporaryDirectory() as d:
        script, wav = Path(d) / "line.txt", Path(d) / "line.wav"
        script.write_text(text)
        subprocess.run(["espeak-ng", "-v", language, "-s", "165", "-f", str(script), "-w", str(wav)],
                       check=True, capture_output=True)
        to_mp3(wav, out)


def synth_silent(text, out):
    seconds = max(1.0, len(text.split()) / SILENT_WPM * 60 + 0.3)
    tmp = f"{out}.tmp.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{seconds:.3f}",
                    "-c:a", "libmp3lame", "-q:a", "6", tmp], check=True)
    os.replace(tmp, out)


def apply_tempo(mp3, factor, fresh=True):
    """lift the pace, pitch kept. The untouched take stays as <sid>.raw.mp3, so changing the factor later costs nothing."""
    mp3 = Path(mp3)
    raw = mp3.with_suffix(".raw.mp3")
    if fresh:
        shutil.copyfile(mp3, raw)
    if abs(factor - 1.0) < 1e-6:
        if not fresh:
            shutil.copyfile(raw, mp3)
        return
    tmp = f"{mp3}.tmp.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", f"atempo={factor}", "-c:a", "libmp3lame",
                    "-q:a", "2", tmp], check=True)
    os.replace(tmp, mp3)


def voice_chapter(p, ch, only=None, provider=None):
    mod = p.module(ch)
    scenes, v = mod.S, p.cfg["voice"]
    prov = pick_provider(provider or v["provider"])
    model, speed = v["model"], float(v["speed"])
    tempo = float(v["tempo"]) if prov in ("fal", "elevenlabs") else 1.0
    respell = v.get("respell") or {}
    out_dir = p.voice_dir(ch)
    voice_id = eleven_voice_id(v["name"]) if prov == "elevenlabs" else None
    if prov in ("say", "espeak"):
        print(f"voice: using the free {prov} voice. Put FAL_KEY in .env for a real narrator.")
    elif prov == "silent":
        print("voice: silent animatic. Timing is real, the soundtrack is not.")
    else:
        print(f"voice: {prov}, {v['name']}, model {model}, speed {speed}, tempo {tempo}")

    def speak(text):
        for a, b in respell.items():
            text = text.replace(a, b)
        return text

    def job(i):
        sid, _, text = scenes[i]
        prev = scenes[i - 1][2] if i > 0 else ""
        nxt = scenes[i + 1][2] if i + 1 < len(scenes) else ""
        body = {"text": speak(text), "voice": v["name"], "stability": 0.55, "similarity_boost": 0.75, "style": 0.12,
                "speed": speed, "previous_text": speak(prev)[-400:], "next_text": speak(nxt)[:200]}
        own = {k: v for k, v in body.items() if k not in ("previous_text", "next_text")}     # a neighbour's edit buys nothing here
        key = hashlib.sha1(json.dumps([prov, model, own], sort_keys=True).encode()).hexdigest()[:10]
        out, meta = out_dir / f"{sid}.mp3", out_dir / f"{sid}.mp3.json"
        if out.exists() and meta.exists():
            m = json.loads(meta.read_text())
            if m.get("key") == key:
                if m.get("tempo") == tempo:
                    return sid, "cached"
                if out.with_suffix(".raw.mp3").exists():     # same take, new pace: no new generation
                    apply_tempo(out, tempo, fresh=False)
                    meta.write_text(json.dumps({**m, "tempo": tempo}))
                    return sid, "re-timed"
        err = ""
        for attempt in range(3):
            try:
                if prov == "fal":
                    synth_fal(body, model, out)
                elif prov == "elevenlabs":
                    synth_eleven(body, model, out, voice_id)
                elif prov == "say":
                    synth_say(body["text"], v.get("say_voice", "Daniel"), out)
                elif prov == "espeak":
                    synth_espeak(body["text"], p.cfg["language"], out)
                elif prov == "silent":
                    synth_silent(body["text"], out)
                else:
                    raise SystemExit(f"unknown voice provider {prov!r}")
                apply_tempo(out, tempo)
                meta.write_text(json.dumps({"key": key, "provider": prov, "voice": v["name"], "model": model,
                                            "tempo": tempo, "text": text}))
                return sid, "ok"
            except subprocess.CalledProcessError as e:
                err = f"{e.cmd[0]} failed: {(e.stderr or b'').decode(errors='replace')[:300]}"
            except (OSError, KeyError, ValueError) as e:
                err = explain_http(e)
                if getattr(e, "code", None) in PERMANENT_HTTP:
                    return sid, "FAILED " + err
            time.sleep(3 + attempt * 5)
        return sid, "FAILED " + err

    todo = [i for i, s in enumerate(scenes) if not only or s[0] in only]
    workers = {"fal": 6, "elevenlabs": 2}.get(prov, 4)
    failed = []
    with ThreadPoolExecutor(workers) as ex:
        for sid, status in ex.map(job, todo):
            print(f"  {status} {sid}", flush=True)
            if status.startswith("FAILED"):
                failed.append(sid)
    if failed:
        raise SystemExit(f"voice failed for {failed}. Fix the error above and run it again: finished clips are kept.")
    return prov
