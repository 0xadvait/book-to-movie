"""The mix keeps the voice in front, and the cut stays in sync. Real audio and video, generated with ffmpeg."""
import json
import subprocess

import numpy as np
import pyloudnorm as pyln
import pytest
import soundfile as sf

from book_to_movie.assemble import assemble_chapter
from book_to_movie.film import build_film, chapter_name, title_case
from book_to_movie.mix import SR, mix_chapter
from book_to_movie.status import chapter_state, next_step
from book_to_movie.timing import timing_chapter

from .conftest import needs_ffmpeg

pytestmark = needs_ffmpeg


def tone(path, seconds, freq=440, volume=0.3):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}", "-af", f"volume={volume}",
                    "-c:a", "libmp3lame", "-q:a", "2", str(path)], check=True)


def voiced_audio(p):
    for sid, _, _ in p.module("ch01").S:
        tone(p.voice_dir("ch01") / f"{sid}.mp3", json.loads((p.voice_dir("ch01") / f"{sid}.words.json").read_text())["duration"])


def clip(path, seconds, colour):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={colour}:s=1920x1080:r=24:d={seconds}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(path)], check=True)


def loudness(path):
    x, sr = sf.read(path)
    return pyln.Meter(sr).integrated_loudness(x), x, sr


def test_voice_only_mix_is_mastered_to_target(voiced):
    timing_chapter(voiced, "ch01")
    voiced_audio(voiced)
    out = mix_chapter(voiced, "ch01")
    level, x, sr = loudness(out)
    assert sr == SR
    assert level == pytest.approx(-16.0, abs=0.5)
    assert np.max(np.abs(x)) <= 10 ** (-1 / 20) + 0.01
    total = voiced.timing("ch01")["s03-quote"]["start"] + voiced.timing("ch01")["s03-quote"]["duration"] + 1.0
    assert len(x) / sr == pytest.approx(total, abs=0.02)


def test_silent_animatic_mix_stays_silent(voiced):
    from book_to_movie.voice import synth_silent
    timing_chapter(voiced, "ch01")
    for sid, _, text in voiced.module("ch01").S:
        synth_silent(text, voiced.voice_dir("ch01") / f"{sid}.mp3")
    x, _ = sf.read(mix_chapter(voiced, "ch01"))
    assert np.max(np.abs(x)) < 1e-3


def test_music_stays_under_the_voice_and_is_left_out_when_off(voiced, capsys):
    path = voiced.root / "story" / "ch01.py"
    path.write_text(path.read_text() + '\nMUSIC = {"m1": {"global": ["x"], "sections": [["a", ["s01-chapter", "s02-harbour", "s03-quote"], ["x"]]]}}\n')
    timing_chapter(voiced, "ch01")
    voiced_audio(voiced)
    total = sum(t["duration"] for t in voiced.timing("ch01").values()) + 6
    tone(voiced.music_dir("ch01") / "m1.mp3", total, freq=220, volume=0.5)

    voiced.cfg["music"] = False
    off, _ = sf.read(mix_chapter(voiced, "ch01"))
    capsys.readouterr()
    voiced.cfg["music"] = True
    on, _ = sf.read(mix_chapter(voiced, "ch01"))
    assert not np.allclose(off[:len(on)], on[:len(off)], atol=1e-3), "the music changed nothing"

    # the mix's own audit: voice, music, how far under. The score must sit 12 dB under every line.
    audit = capsys.readouterr().out
    for sid in ("s01-chapter", "s02-harbour", "s03-quote"):
        line = next(x for x in audit.splitlines() if x.strip().startswith(sid))
        voice_level, music_level, under = (float(v) for v in line.split()[1:4])
        assert voice_level == pytest.approx(-19.0, abs=0.5)
        assert under == pytest.approx(12.0, abs=2.0)


def test_missing_effects_do_not_stop_the_mix(voiced, capsys):
    timing_chapter(voiced, "ch01")
    voiced_audio(voiced)
    mix_chapter(voiced, "ch01")
    assert "mixing without them" in capsys.readouterr().out


def test_effects_land_on_their_cue(voiced):
    timing_chapter(voiced, "ch01")
    for sid, _, _ in voiced.module("ch01").S:     # silent voice, so only the effect makes sound
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t",
                        str(json.loads((voiced.voice_dir("ch01") / f"{sid}.words.json").read_text())["duration"]),
                        "-c:a", "libmp3lame", str(voiced.voice_dir("ch01") / f"{sid}.mp3")], check=True)
    tone(voiced.sfx_dir("ch01") / "gulls.mp3", 1.0)
    x, sr = sf.read(mix_chapter(voiced, "ch01"))
    env = np.abs(x).max(axis=1)
    onset = np.argmax(env > 0.01) / sr
    tm = voiced.timing("ch01")["s02-harbour"]
    word = next(w for w in voiced.words("ch01", "s02-harbour") if w["w"].startswith("water"))
    assert onset == pytest.approx(tm["start"] + tm["vo_offset"] + word["s"], abs=0.1)


def cut(voiced, with_all=True):
    tm = timing_chapter(voiced, "ch01")
    voiced_audio(voiced)
    mix_chapter(voiced, "ch01", audit=False)
    colours = ["red", "green", "blue"]
    for (sid, _, _), c in zip(voiced.module("ch01").S, colours):
        if with_all or c != "green":
            clip(voiced.renders_dir("ch01") / f"{sid}.mp4", tm[sid]["duration"] + 1.0, c)
    return tm


def probe(path, entries="format=duration"):
    return subprocess.run(["ffprobe", "-v", "error", "-show_entries", entries, "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip()


def test_master_has_the_slots_length_and_both_streams(voiced):
    tm = cut(voiced)
    master = assemble_chapter(voiced, "ch01", preview=True)
    total = tm["s03-quote"]["start"] + tm["s03-quote"]["duration"] + 1.0
    assert float(probe(master)) == pytest.approx(total, abs=0.15)
    assert sorted(probe(master, "stream=codec_type").split()) == ["audio", "video"]


def test_a_scene_not_drawn_yet_becomes_a_placeholder(voiced, capsys):
    cut(voiced, with_all=False)
    master = assemble_chapter(voiced, "ch01", preview=True)
    assert master.exists()
    assert "s02-harbour" in capsys.readouterr().out


def test_film_joins_chapters_with_markers_and_no_drift(voiced):
    cut(voiced)
    # a second chapter, by copying the first
    second = voiced.root / "story" / "ch02.py"
    second.write_text((voiced.root / "story" / "ch01.py").read_text().replace("CHAPTER = 1", 'CHAPTER = 2\nNAME = "The Second Part"'))
    a = assemble_chapter(voiced, "ch01", preview=False)
    b = voiced.master("ch02")
    b.write_bytes(a.read_bytes())
    out = build_film(voiced)
    assert out.name == "test-movie-film.mp4"
    chapters = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_chapters", "-of", "json", str(out)], capture_output=True, text=True).stdout)["chapters"]
    assert [c["tags"]["title"] for c in chapters] == ["Chapter One: The Storm", "The Second Part"]
    assert float(probe(out)) == pytest.approx(2 * float(probe(a)), abs=0.2)
    # picture and sound end together: no drift at the join
    streams = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "json", str(out)], capture_output=True, text=True).stdout)["streams"]
    durations = {s["codec_type"]: float(s["duration"]) for s in streams}
    assert durations["video"] == pytest.approx(durations["audio"], abs=0.05)


def test_film_names_come_from_the_cards(voiced):
    assert chapter_name(voiced, "ch01") == "Chapter One: The Storm"
    assert title_case("THE WIND AND THE RAIN") == "The Wind and the Rain"
    assert title_case("AUTO-SUGGESTION") == "Auto-Suggestion"


def test_status_says_what_to_do_next(voiced):
    timing_chapter(voiced, "ch01")
    s = chapter_state(voiced, "ch01")
    assert s["voice"] == 3 and s["specs"] == 0 and s["clips"] == 0
    assert "specs missing" in next_step(s, "ch01")
