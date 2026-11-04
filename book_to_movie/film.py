"""The whole film: every chapter master joined in order, with chapter markers.

Video is copied as it is (all masters share one encoding). Audio is decoded per chapter, cut or padded to exactly its
chapter's video length and encoded once, so nothing drifts at the joins: concatenating AAC streams directly adds 1024
priming samples, 21 ms, per join, and over a long film that is visible.
"""
import os
import subprocess

SR = 48000


def _frames(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return int(r.stdout.strip().rstrip(","))


def title_case(text):
    small = {"a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on", "or", "the", "to", "upon"}
    words = text.lower().split()
    return " ".join(w if i and w in small else "-".join(x.capitalize() for x in w.split("-")) for i, w in enumerate(words))


def chapter_name(p, ch):
    """the chapter card's words, or the module's NAME, or the tag"""
    mod = p.module(ch)
    if getattr(mod, "NAME", None):
        return mod.NAME
    for card in getattr(mod, "CARDS", {}).values():
        if card.get("kind") == "chapter":
            eyebrow = title_case(card.get("eyebrow", ""))
            return f"{eyebrow}: {title_case(card['title'])}" if eyebrow else title_case(card["title"])
    return ch


def build_film(p, first=None, last=None):
    chapters = p.chapters()
    if first is not None:
        chapters = [c for c in chapters if first <= int(c[2:]) <= (last if last is not None else first)]
    if not chapters:
        raise SystemExit("no chapters to join")
    whole = chapters == p.chapters()
    out = p.film / "renders" / (f"{p.slug}-film.mp4" if whole else f"{p.slug}-{chapters[0]}-{chapters[-1]}.mp4")
    raw = p.tmp("film") / "audio.s16"
    files, marks, t = [], [], 0.0
    with open(raw, "wb") as pcm:
        for ch in chapters:
            master = p.master(ch)
            if not master.exists():
                raise SystemExit(f"missing {master}: run ./movie finish {ch}")
            d = _frames(master) / p.fps
            samples = round(d * SR)
            x = subprocess.run(["ffmpeg", "-v", "error", "-i", str(master), "-vn", "-ac", "2", "-ar", str(SR), "-af",
                                f"apad,atrim=end_sample={samples}", "-f", "s16le", "-"], capture_output=True, check=True).stdout
            if len(x) != samples * 4:
                raise SystemExit(f"{ch}: audio came out {len(x)} bytes, expected {samples * 4}")
            pcm.write(x)
            files.append((master, d))
            marks.append((t, t + d, chapter_name(p, ch)))
            t += d
    listing = p.tmp("film") / "concat.txt"
    metadata = p.tmp("film") / "chapters.txt"
    listing.write_text("".join(f"file '{f}'\nduration {d:.6f}\n" for f, d in files))
    with open(metadata, "w") as m:
        m.write(f";FFMETADATA1\ntitle={p.cfg['title']}\n")
        if p.cfg.get("author"):
            m.write(f"artist={p.cfg['author']}\n")
        for s, e, name in marks:
            m.write(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={round(s * 1000)}\nEND={round(e * 1000)}\ntitle={name}\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-f", "s16le", "-ar", str(SR), "-ac", "2",
                    "-i", str(raw), "-i", str(metadata), "-map", "0:v", "-map", "1:a", "-map_metadata", "2", "-map_chapters", "2",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(out)], check=True)
    os.remove(raw)
    print(f"wrote {out}: {len(files)} chapters, {t / 60:.1f} min")
    for s, _, name in marks:
        print(f"  {int(s // 3600)}:{int(s % 3600 // 60):02d}:{int(s % 60):02d}  {name}")
    return out
