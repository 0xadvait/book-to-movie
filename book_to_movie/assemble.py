"""Join a chapter's scene renders into its master: dissolves inside a story, dips through black between stories, fade in and
out, then mux the mix. Scenes not rendered yet become paper-coloured placeholders, so you can watch the cut at any stage."""
import os
import subprocess

from .project import mix_hex, probe_duration


def assemble_chapter(p, ch, preview=False):
    mod = p.module(ch)
    tm = p.timing(ch)
    fps = p.fps
    order = [s[0] for s in mod.S]
    trans_table = getattr(mod, "TRANS", {})
    placeholders = p.build / "placeholders"
    placeholders.mkdir(parents=True, exist_ok=True)
    tone = mix_hex(p.look["paper"], p.look["ink"], 0.12).lstrip("#")

    inputs, missing = [], []
    for sid in order:
        path = p.renders_dir(ch) / f"{sid}.mp4"
        if not path.exists():
            missing.append(sid)
            path = placeholders / f"{ch}-{sid}.mp4"
            d = tm[sid]["duration"] + 1.0
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x{tone}:s=1920x1080:r={fps}:d={d}",
                            "-vf", f"drawbox=x=0:y=500:w=1920:h=80:color=0x{p.look['ink'].lstrip('#')}@0.7:t=fill",
                            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(path)], check=True)
        inputs.append(path)

    trans = []
    for i in range(1, len(order)):
        kind, d = trans_table.get(order[i], ("fade", 0.8))
        trans.append((kind, min(d, 1.0)))       # scenes carry a 1.0 s tail handle

    args = ["ffmpeg", "-v", "error", "-y"]
    for path in inputs:
        args += ["-i", str(path)]
    fc = []
    for i, sid in enumerate(order):
        d_next = trans[i][1] if i < len(trans) else 1.0
        length = tm[sid]["duration"] + d_next
        fc.append(f"[{i}:v]trim=0:{length:.3f},setpts=PTS-STARTPTS,fps={fps},format=yuv420p[v{i}]")
    prev = "v0"
    for i in range(1, len(order)):
        kind, d = trans[i - 1]
        fc.append(f"[{prev}][v{i}]xfade=transition={kind}:duration={d}:offset={tm[order[i]]['start']:.3f}[x{i}]")
        prev = f"x{i}"
    total = tm[order[-1]]["start"] + tm[order[-1]]["duration"] + 1.0
    fc.append(f"[{prev}]fade=t=in:st=0:d=1.5,fade=t=out:st={total - 2.0:.3f}:d=2.0[vout]")
    video = p.film / "renders" / f"{ch}_video.mp4"
    crf, preset = ("27", "veryfast") if preview else ("18", "medium")
    args += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-c:v", "libx264", "-preset", preset, "-crf", crf,
             "-tune", "film", "-pix_fmt", "yuv420p", "-r", str(fps), "-movflags", "+faststart", str(video)]
    subprocess.run(args, check=True)

    mix = p.mix_dir() / f"{ch}_mix.wav"
    if not mix.exists():
        raise SystemExit(f"no mix for {ch} yet: run ./movie mix {ch}")
    final = p.master(ch, "-preview" if preview else "")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(mix), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", str(final)], check=True)
    os.remove(video)     # the master carries the same video stream; a second copy only fills the disk
    note = f" | placeholders: {missing}" if missing else ""
    print(f"  wrote {final}{note}")
    return final


def small_copy(p, src, megabytes=28):
    """a phone-sized two-pass copy under about 28 MiB, for sending"""
    dur = probe_duration(src)
    rate = int(min(900, (megabytes * 8 * 1024 * 1024 / dur - 64000) / 1000))
    dst = src.with_name(src.stem + "-phone.mp4")
    log = p.tmp("x264") / src.stem
    common = ["-vf", "scale=854:480:flags=lanczos", "-c:v", "libx264", "-preset", "slow", "-b:v", f"{rate}k", "-passlogfile", str(log)]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), *common, "-pass", "1", "-an", "-f", "mp4", os.devnull], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), *common, "-pass", "2", "-c:a", "aac", "-b:a", "64k",
                    "-movflags", "+faststart", str(dst)], check=True)
    print(f"  wrote {dst}")
    return dst
