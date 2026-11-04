"""Check a chapter's script before anything is spent on it. Every rule here exists because breaking it wasted a render or
a voice take on the film this repo was built for."""
import difflib
import json
import re

from .project import norm, parse_cue

CARD_KINDS = {"title", "chapter", "section", "quote", "words", "portrait", "close"}
SPOKEN_WPM = 175


def check_chapter(p, ch):
    """-> (errors, warnings, summary)"""
    mod = p.module(ch)
    errors, warnings = [], []
    for attr in ("TITLE", "CHAPTER", "S"):
        if not hasattr(mod, attr):
            errors.append(f"module has no {attr}")
    if errors:
        return errors, warnings, {}
    if f"ch{mod.CHAPTER:02d}" != ch:
        errors.append(f"CHAPTER = {mod.CHAPTER} but the file is {ch}.py")

    scenes = mod.S
    sets, cards = getattr(mod, "SETS", {}), getattr(mod, "CARDS", {})
    ids = [s[0] for s in scenes]
    for sid in {x for x in ids if ids.count(x) > 1}:
        errors.append(f"{sid}: scene id used twice")
    text_of = {s[0]: s[2] for s in scenes}
    words = 0
    for sid, art, text in scenes:
        if not re.fullmatch(r"s\d+-[a-z0-9-]+", sid):
            warnings.append(f"{sid}: scene ids look like s07-train")
        words += len(text.split())
        if not text.strip():
            errors.append(f"{sid}: no narration")
        if re.search(r"\d", text):
            errors.append(f"{sid}: digits in narration ({re.findall(r'[^ ]*[0-9][^ ]*', text)[:3]}). Spell numbers as they are spoken.")
        if "—" in text or "–" in text:
            errors.append(f"{sid}: em or en dash in narration. Use a comma or a full stop: dashes make the voice stumble.")
        if art.startswith("card:"):
            kind = art.split(":")[1]
            if kind not in CARD_KINDS:
                errors.append(f"{sid}: unknown card kind {art!r}. Use {sorted(CARD_KINDS)}")
            if sid not in cards:
                errors.append(f"{sid}: card scene with no entry in CARDS")
            else:
                card = cards[sid]
                if card.get("kind") != kind:
                    errors.append(f"{sid}: art says {kind} but CARDS says {card.get('kind')}")
                shown = card.get("text") or card.get("quote")
                if shown and _coverage(shown, text) < 0.8:
                    errors.append(f"{sid}: card text is not spoken in this scene. On-screen words ink in as they are read, so they must match.")
        elif art not in sets:
            errors.append(f"{sid}: art set {art!r} is not in SETS")

    for name, info in sets.items():
        for sid in info.get("scenes", []):
            if sid not in text_of:
                errors.append(f"SETS[{name}]: no scene {sid}")
    used = {s[1] for s in scenes}
    for name in sets:
        if name not in used:
            warnings.append(f"SETS[{name}] is not used by any scene")
    for sid in getattr(mod, "TRANS", {}):
        if sid not in text_of:
            errors.append(f"TRANS: no scene {sid}")
    for table in ("LEAD", "HOLD"):
        for sid in getattr(mod, table, {}):
            if sid not in text_of:
                errors.append(f"{table}: no scene {sid}")
    for name, cue in getattr(mod, "MUSIC", {}).items():
        for _, sids, _ in cue.get("sections", []):
            for sid in sids:
                if sid not in text_of:
                    errors.append(f"MUSIC[{name}]: no scene {sid}")
    for it in getattr(mod, "SFX", []):
        sid = it.get("scene")
        if sid not in text_of:
            errors.append(f"SFX[{it.get('name')}]: no scene {sid}")
            continue
        at = it.get("at", 0.0)
        if isinstance(at, str) and at != "end":
            try:
                word, nth, _ = parse_cue(at)
            except ValueError as e:
                errors.append(f"SFX[{it['name']}]: {e}")
                continue
            count = sum(1 for w in text_of[sid].split() if norm(w) == word)
            if count < nth:
                errors.append(f"SFX[{it['name']}]: cue {at!r} but {sid} says that word {count} time(s)")

    # scene specs that exist so far: their cues must be words the narration really says
    for path in sorted(p.specs(ch).glob("s*.json")):
        sid = path.stem
        if sid not in text_of:
            warnings.append(f"{path.name}: the script has no scene called {sid}")
            continue
        try:
            spec = json.loads(path.read_text())
        except ValueError as e:
            errors.append(f"{path.name}: not valid JSON: {e}")
            continue
        spoken = [norm(w) for w in text_of[sid].split()]
        for cue in sorted(set(_cues_in(spec))):
            try:
                word, nth, _ = parse_cue(cue)
            except ValueError as e:
                errors.append(f"{path.name}: {e}")
                continue
            if spoken.count(word) < nth:
                errors.append(f"{path.name}: {cue!r}, but {sid} says that word {spoken.count(word)} time(s)")

    summary = {"scenes": len(scenes), "words": words, "minutes": round(words / SPOKEN_WPM, 1), "sets": len(sets), "cards": len(cards)}
    return errors, warnings, summary


def _cues_in(value):
    if isinstance(value, str):
        if value.startswith("cue:"):
            yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _cues_in(v)
    elif isinstance(value, list):
        for v in value:
            yield from _cues_in(v)


def _coverage(shown, spoken):
    a, b = [norm(w) for w in shown.replace("|", " ").split()], [norm(w) for w in spoken.split()]
    blocks = difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()
    return sum(x.size for x in blocks) / max(1, len(a))
