"""Shared fixtures. Nothing here needs a network, an API key, whisper or the renderer."""
import json
import shutil

import pytest

from book_to_movie.project import Project

MODULE = '''
TITLE = "Test"
CHAPTER = 1
S = [
    ("s01-chapter", "card:chapter", "Chapter one. The storm."),
    ("s02-harbour", "harbour", "Before dawn the captain walked down to the water, and the fifty-cent lamp went out."),
    ("s03-quote", "card:quote", "She wrote, \\"The sea keeps nothing it does not want.\\" And that was that."),
]
LEAD = {"s01-chapter": 1.0}
HOLD = {"s02-harbour": 0.5}
TRANS = {"s03-quote": ("fadeblack", 1.0)}
CARDS = {
    "s01-chapter": {"kind": "chapter", "eyebrow": "CHAPTER ONE", "title": "THE STORM"},
    "s03-quote": {"kind": "quote", "text": "The sea keeps nothing it does not want.", "attr": "A Writer"},
}
SETS = {"harbour": {"desc": "a quay", "scenes": ["s02-harbour"], "shots": {}, "reuse": None}}
SFX = [{"name": "gulls", "scene": "s02-harbour", "at": "cue:water", "prompt": "gulls", "dur": 3, "gain": -18}]
'''


@pytest.fixture
def project(tmp_path):
    """a small project on disk with one chapter's script"""
    root = tmp_path / "test-movie"
    (root / "story").mkdir(parents=True)
    (root / "movie.json").write_text(json.dumps({"title": "Test Movie", "voice": {"provider": "silent"}}))
    (root / "story" / "ch01.py").write_text(MODULE)
    return Project(root).scaffold()


@pytest.fixture
def voiced(project):
    """the same project with hand-made word timings, as if it had been voiced"""
    mod = project.module("ch01")
    for sid, _, text in mod.S:
        t, words = 0.0, []
        for w in text.split():
            words.append({"w": w, "s": round(t, 3), "e": round(t + 0.3, 3)})
            t += 0.35
        (project.voice_dir("ch01") / f"{sid}.words.json").write_text(json.dumps({"duration": round(t, 3), "words": words, "match": 1.0}))
    return project


needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
needs_rsvg = pytest.mark.skipif(shutil.which("rsvg-convert") is None, reason="needs rsvg-convert")
