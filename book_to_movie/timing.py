"""Scene slots: narration starts vo_offset into the scene and the scene holds a tail after it. Writes _timing.json, and
_scenes.md (the sheet illustrators work from)."""
import json


def is_card(art):
    return art.startswith("card:")


def timing_chapter(p, ch):
    mod = p.module(ch)
    hold = getattr(mod, "HOLD", {})     # extra seconds of picture after the line, per scene
    lead = getattr(mod, "LEAD", {})     # seconds before the line starts, per scene
    out, t = {}, 0.0
    for sid, art, _ in mod.S:
        vd = json.loads((p.voice_dir(ch) / f"{sid}.words.json").read_text())["duration"]
        a = lead.get(sid, 1.0 if is_card(art) else 0.35)
        b = hold.get(sid, 0.8 if is_card(art) else 0.45)
        d = round(a + vd + b, 3)
        out[sid] = {"duration": d, "vo_offset": a, "vo_duration": vd, "start": round(t, 3), "art": art, "handle": 1.0}
        t += d
    (p.specs(ch) / "_timing.json").write_text(json.dumps(out, indent=1))
    write_scene_sheet(p, ch, mod, out)
    print(f"  {len(out)} scenes, {t / 60:.2f} min")
    return out


def write_scene_sheet(p, ch, mod, tm):
    lines = [f"# {ch} scenes: slot timing and narration", "",
             "duration = the scene's slot on the film timeline (s). Every scene renders 1.0 s longer (a tail handle the",
             "next scene dissolves over), so the time 'end' = duration + 1.0. Narration starts vo_offset seconds in.",
             f"Exact word timings: audio/voice/{ch}/<sid>.words.json (relative to the narration start).", ""]
    for sid, art, text in mod.S:
        t = tm[sid]
        lines += [f"## {sid}  (art: {art})",
                  f"- duration {t['duration']} s, narration {t['vo_duration']} s starting at {t['vo_offset']} s", "", text, ""]
    (p.specs(ch) / "_scenes.md").write_text("\n".join(lines))
