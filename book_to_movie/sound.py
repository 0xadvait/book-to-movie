"""Sound effects and score from a chapter's SFX and MUSIC tables: effects through fal or ElevenLabs, score through fal.

Effects are cheap and do most of the work. Music is off by default and needs an explicit --allow-spend: it is by far the
largest audio bill, and on the film this repo was built for the music was the first thing cut.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor

from pathlib import Path

from .project import elevenlabs_key, fal_key
from .voice import PERMANENT_HTTP, _http_json, download, explain_http

# Only what no narrated film wants. Period exclusions (no synths in 1890, say) go in a cue's own "neg" list.
NEGATIVE_STYLES = ["vocals", "singing", "choir", "lyrics"]


def _fal(endpoint, body, timeout=300):
    return json.loads(_http_json(f"https://fal.run/{endpoint}", body, {"Authorization": f"Key {fal_key()}"}, timeout))


def _effect_fal(body, out):
    download(_fal("fal-ai/elevenlabs/sound-effects/v2", body)["audio"]["url"], out)


def _effect_eleven(body, out):
    payload = {k: body[k] for k in ("text", "prompt_influence", "loop", "duration_seconds") if k in body}
    audio = _http_json("https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_128", payload, {"xi-api-key": elevenlabs_key()})
    tmp = f"{out}.part"
    Path(tmp).write_bytes(audio)
    Path(tmp).replace(out)


def sfx_chapter(p, ch):
    mod = p.module(ch)
    table = getattr(mod, "SFX", [])
    if not table:
        print("  no SFX table")
        return
    if not p.cfg["sfx"]:
        print("  sound effects are off in movie.json")
        return
    if not fal_key() and not elevenlabs_key():
        print("  skipping sound effects: no FAL_KEY or ELEVENLABS_API_KEY. The mix works without them.")
        return
    make_effect = _effect_fal if fal_key() else _effect_eleven
    out_dir = p.sfx_dir(ch)
    unique = {}
    for it in table:
        unique.setdefault(it["name"], it)

    def gen(item):
        name, out = item["name"], out_dir / f"{item['name']}.mp3"
        if out.exists():
            return name, "exists"
        body = {"text": item["prompt"], "prompt_influence": 0.55, "loop": item.get("loop", False),
                "output_format": "mp3_44100_128"}
        if item.get("dur"):
            body["duration_seconds"] = item["dur"]
        err = ""
        for attempt in range(4):
            try:
                make_effect(body, out)
                return name, "ok"
            except (OSError, KeyError, ValueError) as e:
                err = explain_http(e)
                if getattr(e, "code", None) in PERMANENT_HTTP:
                    break
                time.sleep(4 + attempt * 6)     # rate limits clear in seconds
        return name, "FAILED " + err

    failed = []
    with ThreadPoolExecutor(8 if fal_key() else 2) as ex:     # direct ElevenLabs plans allow only a few requests at once
        for name, status in ex.map(gen, unique.values()):
            print(f"  {status} {name}", flush=True)
            if status.startswith("FAILED"):
                failed.append(name)
    if failed:
        raise SystemExit(f"sound effects failed: {failed}. Run it again: finished effects are kept.")


def composition_plan(cue, tm):
    """a cue spans a run of scenes; its sections are timed to those scenes so the music turns where the story turns"""
    sections = []
    for name, sids, styles in cue["sections"]:
        d = sum(tm[s]["duration"] for s in sids)
        sections.append({"section_name": name, "positive_local_styles": styles, "negative_local_styles": [],
                         "duration_ms": int(max(3000, min(120000, d * 1000))), "lines": []})
    sections[-1]["duration_ms"] = min(120000, sections[-1]["duration_ms"] + int(cue.get("tail", 4.0) * 1000))
    return {"positive_global_styles": cue["global"], "negative_global_styles": NEGATIVE_STYLES + cue.get("neg", []),
            "sections": sections}


def music_chapter(p, ch, allow_spend=False):
    mod = p.module(ch)
    cues = getattr(mod, "MUSIC", {})
    if not cues:
        print("  no MUSIC table")
        return
    out_dir = p.music_dir(ch)
    missing = [n for n in cues if not (out_dir / f"{n}.mp3").exists()]
    if not missing:
        print("  every cue exists")
        return
    tm = p.timing(ch)
    minutes = sum(s["duration_ms"] for n in missing for s in composition_plan(cues[n], tm)["sections"]) / 60000
    if not allow_spend:
        raise SystemExit(f"music would generate {minutes:.1f} min, about ${minutes * 0.60:.2f} at fal's price. "
                         "Run again with --allow-spend if you want it, and set \"music\": true in movie.json.")
    if not fal_key():
        raise SystemExit("FAL_KEY is not set: add it to .env")

    def gen(name):
        out = out_dir / f"{name}.mp3"
        body = {"composition_plan": composition_plan(cues[name], tm), "respect_sections_durations": True,
                "output_format": "mp3_44100_192"}
        err = ""
        for _ in range(3):
            try:
                download(_fal("fal-ai/elevenlabs/music", body, timeout=900)["audio"]["url"], out)
                return name, "ok"
            except (OSError, KeyError, ValueError) as e:
                err = explain_http(e)
                if "mp3_44100_192" in err:         # that format needs a higher plan: try the common one
                    body["output_format"] = "mp3_44100_128"
                elif getattr(e, "code", None) in PERMANENT_HTTP:
                    break
                else:
                    time.sleep(5)
        return name, "FAILED " + err

    failed = []
    with ThreadPoolExecutor(5) as ex:
        for name, status in ex.map(gen, missing):
            print(f"  {status} {name}", flush=True)
            if status.startswith("FAILED"):
                failed.append(name)
    if failed:
        raise SystemExit(f"music failed: {failed}")
