"""./movie: every deterministic step of making a film. Claude writes and draws; this does the rest."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .project import PROJECTS, REPO, Project, chapter_tag, find_project, load_env, set_current, slugify


def _chapters(p, value):
    """1, ch01, or all"""
    if value in (None, "all"):
        found = p.chapters()
        if not found:
            raise SystemExit("no scripts yet: story/chNN.py")
        return found
    return [chapter_tag(value)]


def cmd_new(a):
    from .ingest import ingest
    book = Path(a.book).expanduser()
    if not book.exists():
        raise SystemExit(f"no such file: {book}")
    slug = a.name or slugify(a.title or book.stem)
    root = PROJECTS / slug
    if (root / "movie.json").exists() and not a.force:
        raise SystemExit(f"{root} already exists. Use another --name, or --force to re-read the book into it.")
    (root / "source").mkdir(parents=True, exist_ok=True)
    if not (root / "movie.json").exists():
        (root / "movie.json").write_text(json.dumps({"title": a.title or book.stem.replace("-", " ").replace("_", " ").title(),
                                                     "author": a.author or "", "language": a.language, "look": "sepia"}, indent=2) + "\n")
    p = Project(root)
    shutil.copyfile(book, root / "source" / f"book{book.suffix.lower()}")
    index, meta = ingest(p, book, a.heading)
    if meta.get("title") and not a.title or meta.get("author") and not a.author:
        cfg = json.loads((root / "movie.json").read_text())
        cfg["title"] = a.title or meta.get("title") or cfg["title"]
        cfg["author"] = a.author or meta.get("author") or cfg["author"]
        (root / "movie.json").write_text(json.dumps(cfg, indent=2) + "\n")
    p = Project(root).scaffold()
    set_current(slug)
    print(f"{p.cfg['title']} -> {root}")
    print(f"{'#':>3s} {'words':>7s}  title")
    for c in index:
        print(f"{c['chapter']:3d} {c['words']:7d}  {c['title']}")
    print(f"{sum(c['words'] for c in index):,} words in {len(index)} sections. If the split looks wrong, re-run with --force --heading 'REGEX'.")


def cmd_use(a):
    if not (PROJECTS / a.name / "movie.json").exists():
        raise SystemExit(f"no project called {a.name}")
    set_current(a.name)
    print("using", a.name)


def cmd_status(a):
    from .status import show_status
    show_status(find_project(a.project))


def cmd_cost(a):
    from .status import show_cost
    show_cost(find_project(a.project))


def cmd_doctor(a):
    from .status import doctor
    load_env()
    sys.exit(0 if doctor() else 1)


def cmd_check(a):
    from .check import check_chapter
    p = find_project(a.project)
    bad = False
    for ch in _chapters(p, a.chapter):
        errors, warnings, summary = check_chapter(p, ch)
        print(f"{ch}: {summary or 'unreadable'}")
        for w in warnings:
            print(f"  warning {w}")
        for e in errors:
            print(f"  ERROR {e}")
        bad = bad or bool(errors)
    print("not ready: fix the errors above" if bad else "looks right")
    sys.exit(1 if bad else 0)


def cmd_voice(a):
    from .align import align_chapter
    from .cards import cards_chapter
    from .check import check_chapter
    from .timing import timing_chapter
    from .voice import voice_chapter
    p = find_project(a.project)
    for ch in _chapters(p, a.chapter):
        errors, _, _ = check_chapter(p, ch)
        if errors:
            raise SystemExit(f"{ch} has script errors, not spending anything on it. Run: ./movie check {ch}")
        print(f"{ch}: narration")
        voice_chapter(p, ch, only=set(a.only.split(",")) if a.only else None, provider=a.provider)
        print(f"{ch}: word timing")
        align_chapter(p, ch)
        print(f"{ch}: scene timing and cards")
        timing_chapter(p, ch)
        cards_chapter(p, ch)     # cards ink in on spoken words, so they follow the voice


def cmd_cards(a):
    from .cards import cards_chapter
    p = find_project(a.project)
    for ch in _chapters(p, a.chapter):
        cards_chapter(p, ch)


def cmd_sfx(a):
    from .sound import sfx_chapter
    p = find_project(a.project)
    for ch in _chapters(p, a.chapter):
        print(f"{ch}: effects")
        sfx_chapter(p, ch)


def cmd_music(a):
    from .sound import music_chapter
    p = find_project(a.project)
    for ch in _chapters(p, a.chapter):
        print(f"{ch}: music")
        music_chapter(p, ch, a.allow_spend)


def cmd_art(a):
    p = find_project(a.project)
    for ch in _chapters(p, a.chapter):
        folder = p.art_dir(ch)
        names = a.sets or sorted(d.name for d in folder.glob("*") if (d / "build.py").exists()) if folder.exists() else a.sets
        for name in names or []:
            script = p.art_dir(ch, name) / "build.py"
            if not script.exists():
                raise SystemExit(f"no drawing for {ch}/{name}: expected {script}")
            if subprocess.run([sys.executable, str(script)], cwd=script.parent).returncode:
                raise SystemExit(f"{script} failed: see the error above")


def cmd_preview(a):
    from .previews import preview_set
    p = find_project(a.project)
    preview_set(p, chapter_tag(a.chapter), a.set, a.layers or None, Path(a.out) if a.out else None)


def cmd_figures(a):
    from .engrave import engrave
    from .figures import reference_sheet
    p = find_project(a.project)
    svg = p.tmp("figures") / "sheet.svg"
    svg.write_text(reference_sheet())
    out = p.qa() / "figures.png"
    engrave(str(svg), str(out), out_scale=1.0, paper=p.look["paper"], ink=p.look["ink"])
    print(out)


def cmd_sheet(a):
    """what is left to illustrate in a chapter: scenes without specs, per art set, with their briefs"""
    p = find_project(a.project)
    ch = chapter_tag(a.chapter)
    mod = p.module(ch)
    sets = getattr(mod, "SETS", {})
    print(f"{ch}: full timing and narration in {p.specs(ch) / '_scenes.md'}")
    for name, info in sets.items():
        scenes = [s[0] for s in mod.S if s[1] == name]
        drawn = (p.film / "assets" / "art" / ch / name / "layers.json").exists()
        todo = [s for s in scenes if not (p.specs(ch) / f"{s}.json").exists()]
        print(f"\n{name}  [{'drawn' if drawn else 'not drawn'}; {len(scenes) - len(todo)}/{len(scenes)} specs]")
        if todo:
            print(f"  specs to write: {', '.join(todo)}")
        if not drawn or todo:
            print(f"  brief: {info.get('desc', '')}")
            for sid, shot in info.get("shots", {}).items():
                print(f"  shot {sid}: {shot}")
            if info.get("reuse"):
                print(f"  reuse: {info['reuse']}")


def cmd_scene(a):
    """render one scene or a few, and pull check frames to look at"""
    from .previews import scene_frames
    from .render import render_scenes
    p = find_project(a.project)
    ch = chapter_tag(a.chapter)
    render_scenes(p, ch, a.scenes, jobs=a.jobs or 1, workers=a.workers or 2, force=a.force)
    for sid in a.scenes:
        for f in scene_frames(p, ch, sid):
            print(f)


def cmd_render(a):
    from .render import render_scenes
    p = find_project(a.project)
    for ch in _chapters(p, a.chapter):
        print(f"{ch}: render")
        render_scenes(p, ch, a.scenes or None, a.jobs, a.workers, a.force)


def cmd_mix(a):
    from .mix import mix_chapter
    p = find_project(a.project)
    for ch in _chapters(p, a.chapter):
        print(f"{ch}: mix")
        mix_chapter(p, ch)


def cmd_assemble(a):
    from .assemble import assemble_chapter
    p = find_project(a.project)
    for ch in _chapters(p, a.chapter):
        print(f"{ch}: assemble")
        assemble_chapter(p, ch, a.preview)


def cmd_qa(a):
    from .qa import qa_chapter
    p = find_project(a.project)
    for ch in _chapters(p, a.chapter):
        print(f"{ch}: checks")
        qa_chapter(p, ch)


def cmd_finish(a):
    """everything after the drawings: render what changed, mix, assemble, check"""
    from .assemble import assemble_chapter
    from .mix import mix_chapter
    from .qa import qa_chapter
    from .render import render_scenes
    p = find_project(a.project)
    for ch in _chapters(p, a.chapter):
        print(f"{ch}: render")
        render_scenes(p, ch, None, a.jobs, a.workers, a.force)
        print(f"{ch}: mix")
        mix_chapter(p, ch)
        print(f"{ch}: assemble")
        master = assemble_chapter(p, ch, a.preview)
        if a.preview:
            print(f"{ch}: preview at {master}")
            continue
        print(f"{ch}: checks")
        qa_chapter(p, ch)
        print(f"{ch}: finished -> {master}")


def cmd_contact(a):
    from .previews import contact_sheet
    p = find_project(a.project)
    contact_sheet(p, chapter_tag(a.chapter), Path(a.out) if a.out else None, a.scenes or None)


def cmd_film(a):
    from .film import build_film
    p = find_project(a.project)
    build_film(p, a.first, a.last)


def cmd_phone(a):
    from .assemble import small_copy
    p = find_project(a.project)
    src = (p.film / "renders" / f"{p.slug}-film.mp4") if a.what == "film" else p.master(chapter_tag(a.what))
    if not src.exists():
        raise SystemExit(f"missing {src}")
    small_copy(p, src)


def cmd_portrait(a):
    from .portrait import make_portrait
    p = find_project(a.project)
    crop = tuple(int(x) for x in a.crop.split(",")) if a.crop else None
    make_portrait(p, chapter_tag(a.chapter), a.slug, a.commons_file, crop)


def cmd_engrave(a):
    from .engrave import engrave
    p = None
    try:
        p = find_project(a.project)
    except SystemExit:
        pass
    look = p.look if p else {"paper": None, "ink": None}
    engrave(a.svg, a.png, pitch=a.pitch, shadow=a.shadow, out_scale=a.out_scale, paper=look["paper"], ink=look["ink"])
    print(a.png)


def cmd_demo(a):
    """make the small example film: free, no API key needed"""
    from .assemble import assemble_chapter
    from .align import align_chapter
    from .cards import cards_chapter
    from .mix import mix_chapter
    from .qa import qa_chapter
    from .render import render_scenes
    from .timing import timing_chapter
    from .voice import pick_provider, voice_chapter
    load_env()
    src = REPO / "examples" / "the-shepherds-boy"
    root = PROJECTS / "the-shepherds-boy"
    if not (root / "movie.json").exists():
        PROJECTS.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, root, ignore=shutil.ignore_patterns("__pycache__", "*.svg"))
    p = Project(root).scaffold()
    set_current(p.slug)
    started = time.time()
    # free by default: this must never spend money unless asked to
    free = "say" if shutil.which("say") else ("espeak" if shutil.which("espeak-ng") else "silent")
    provider = a.voice or free
    if provider in ("say", "espeak", "silent"):
        os.environ.pop("FAL_KEY", None)
        os.environ.pop("FAL_API_KEY", None)
        os.environ.pop("ELEVENLABS_API_KEY", None)
        os.environ.pop("ELEVEN_API_KEY", None)
    ch = "ch01"
    print(f"1/6 voice ({pick_provider(provider)})")
    voice_chapter(p, ch, provider=provider)
    print("2/6 word timing")
    align_chapter(p, ch)
    timing_chapter(p, ch)
    print("3/6 cards and drawings")
    cards_chapter(p, ch)
    for script in sorted(p.art_dir(ch).glob("*/build.py")):
        subprocess.run([sys.executable, str(script)], check=True, cwd=script.parent)
    print("4/6 render (the first run downloads HyperFrames and a headless browser)")
    render_scenes(p, ch, None, a.jobs, a.workers)
    print("5/6 mix")
    if provider not in ("say", "espeak", "silent"):
        from .sound import sfx_chapter
        sfx_chapter(p, ch)
    mix_chapter(p, ch, audit=False)
    print("6/6 assemble")
    master = assemble_chapter(p, ch)
    qa_chapter(p, ch)
    print(f"\nDone in {(time.time() - started) / 60:.1f} min: {master}")


def build_parser():
    ap = argparse.ArgumentParser(prog="movie", description=__doc__)
    ap.add_argument("-p", "--project", help="project name or folder (default: the last one used)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_, *args):
        s = sub.add_parser(name, help=help_, description=help_)
        s.set_defaults(fn=fn)
        for names, kw in args:
            s.add_argument(*names, **kw)
        return s

    part = (["chapter"], {"nargs": "?", "default": "all", "help": "a part of the film: 1, ch01 or all (default)"})
    one = (["chapter"], {"help": "a part of the film: 1 or ch01"})
    jobs = (["--jobs"], {"type": int, "help": "scenes rendered at once"})
    workers = (["--workers"], {"type": int, "help": "browser workers per scene"})
    force = (["--force"], {"action": "store_true", "help": "redo it even if nothing changed"})
    scenes = (["scenes"], {"nargs": "*", "help": "scene ids (default: all)"})

    add("doctor", cmd_doctor, "check this machine has what it needs")
    add("demo", cmd_demo, "make a one-minute example film, free", (["--voice"], {"help": "say, espeak, silent, fal or elevenlabs"}), jobs, workers)
    add("new", cmd_new, "start a project from a book (.txt .md .pdf .epub .html .docx)",
        (["book"], {}), (["--name"], {"help": "folder name under projects/"}), (["--title"], {}), (["--author"], {}),
        (["--language"], {"default": "en"}), (["--heading"], {"help": "regex matching chapter headings, if the split is wrong"}),
        (["--force"], {"action": "store_true"}))
    add("use", cmd_use, "switch to another project", (["name"], {}))
    add("status", cmd_status, "where the project stands, and what to do next")
    add("cost", cmd_cost, "estimate the audio bill before spending anything")
    add("check", cmd_check, "check scripts before spending anything", part)
    add("voice", cmd_voice, "narration, word timing, scene timing, cards", part, (["--only"], {"help": "comma-separated scene ids"}),
        (["--provider"], {"help": "fal, elevenlabs, say, espeak or silent"}))
    add("cards", cmd_cards, "rewrite the cards after editing CARDS (voice already does this)", part)
    add("sfx", cmd_sfx, "generate sound effects", part)
    add("music", cmd_music, "generate score cues (off by default; asks for --allow-spend)", part, (["--allow-spend"], {"action": "store_true"}))
    add("sheet", cmd_sheet, "what is left to illustrate in a chapter", one)
    add("art", cmd_art, "run drawing scripts and engrave their layers", part, (["sets"], {"nargs": "*", "help": "art sets (default: all)"}))
    add("preview", cmd_preview, "a still of a set's layers, composited", one, (["set"], {}), (["layers"], {"nargs": "*"}), (["-o", "--out"], {}))
    add("figures", cmd_figures, "a reference sheet of every figure pose and hat")
    add("scene", cmd_scene, "render scenes and pull check frames", one, (["scenes"], {"nargs": "+"}), jobs, workers, force)
    add("render", cmd_render, "render scenes (only what changed)", part, scenes, jobs, workers, force)
    add("mix", cmd_mix, "voice-first mix, with a per-line audit", part)
    add("assemble", cmd_assemble, "join scenes and mix into a chapter master", part, (["--preview"], {"action": "store_true"}))
    add("qa", cmd_qa, "whisper, sync and loudness checks", part)
    add("finish", cmd_finish, "render + mix + assemble + qa", part, jobs, workers, force, (["--preview"], {"action": "store_true"}))
    add("contact", cmd_contact, "a contact sheet of rendered scenes", one, scenes, (["-o", "--out"], {}))
    add("film", cmd_film, "join all chapter masters into the film, with chapter markers", (["--first"], {"type": int}), (["--last"], {"type": int}))
    add("phone", cmd_phone, "a small copy for sending: 'film' or a chapter", (["what"], {}))
    add("portrait", cmd_portrait, "engrave a portrait from a public-domain Wikimedia Commons file", one, (["slug"], {}), (["commons_file"], {}),
        (["--crop"], {"help": "x0,y0,x1,y1"}))
    add("engrave", cmd_engrave, "engrave one SVG into a PNG", (["svg"], {}), (["png"], {}), (["--pitch"], {"type": float, "default": 3.6}),
        (["--shadow"], {"type": float, "default": 0.0}), (["--out-scale"], {"type": float, "default": 1.25}))
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    load_env()
    a.fn(a)


if __name__ == "__main__":
    main()
