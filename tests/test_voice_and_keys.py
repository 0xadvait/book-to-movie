"""The narration cache protects real money, and keys must never reach disk or the screen."""
import json
import os

import pytest

from book_to_movie import project as project_mod
from book_to_movie import sound, status, voice
from book_to_movie.project import load_env

from .conftest import needs_ffmpeg

KEY_NAMES = ("FAL_KEY", "FAL_API_KEY", "ELEVENLABS_API_KEY", "ELEVEN_API_KEY")
FAKE_KEY = "test-not-a-real-key-1234567890"


@pytest.fixture(autouse=True)
def clean_keys(monkeypatch):
    for k in KEY_NAMES:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(project_mod, "REPO", project_mod.Path("/nonexistent-repo-root"))


def test_provider_prefers_fal_then_elevenlabs(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", FAKE_KEY)
    assert voice.pick_provider("auto") == "elevenlabs"
    monkeypatch.setenv("FAL_KEY", FAKE_KEY)
    assert voice.pick_provider("auto") == "fal"


def test_explicit_provider_wins(monkeypatch):
    monkeypatch.setenv("FAL_KEY", FAKE_KEY)
    assert voice.pick_provider("silent") == "silent"


def test_no_key_falls_back_to_something_free(monkeypatch):
    assert voice.pick_provider("auto") in ("say", "espeak", "silent")


def test_env_file_is_read_and_real_env_wins(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("# a comment\nFAL_KEY='from-file'\nexport ELEVENLABS_API_KEY=also-from-file\nEMPTY=\n")
    monkeypatch.setattr(project_mod, "REPO", tmp_path)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "from-environment")
    monkeypatch.delenv("FAL_KEY", raising=False)
    load_env()
    assert os.environ["FAL_KEY"] == "from-file"
    assert os.environ["ELEVENLABS_API_KEY"] == "from-environment"
    assert "EMPTY" not in os.environ
    monkeypatch.delenv("FAL_KEY")


def test_doctor_never_prints_a_key(monkeypatch, capsys):
    monkeypatch.setenv("FAL_KEY", FAKE_KEY)
    monkeypatch.setenv("ELEVENLABS_API_KEY", FAKE_KEY)
    status.doctor()
    out = capsys.readouterr().out
    assert FAKE_KEY not in out
    assert "FAL_KEY" in out


class FakeAudio:
    """stands in for the paid API: counts requests and writes real (silent) audio"""

    def __init__(self):
        self.calls = []

    def fal(self, body, model, out):
        self.calls.append(body)
        voice.synth_silent(body["text"], out)


@needs_ffmpeg
def test_paid_voice_is_cached_retimed_free_and_never_stores_the_key(project, monkeypatch):
    fake = FakeAudio()
    monkeypatch.setenv("FAL_KEY", FAKE_KEY)
    monkeypatch.setattr(voice, "synth_fal", fake.fal)
    project.cfg["voice"]["provider"] = "fal"
    n = len(project.module("ch01").S)

    voice.voice_chapter(project, "ch01")
    assert len(fake.calls) == n
    # every clip knows its neighbours, so the delivery flows across scene cuts
    middle = next(c for c in fake.calls if "captain" in c["text"])
    assert middle["previous_text"] and middle["next_text"]

    # run again: nothing is bought twice
    voice.voice_chapter(project, "ch01")
    assert len(fake.calls) == n

    # change the pace: the audio is re-timed from the kept take, nothing is bought
    before = (project.voice_dir("ch01") / "s02-harbour.mp3").read_bytes()
    project.cfg["voice"]["tempo"] = 1.2
    voice.voice_chapter(project, "ch01")
    assert len(fake.calls) == n
    assert (project.voice_dir("ch01") / "s02-harbour.mp3").read_bytes() != before
    assert json.loads((project.voice_dir("ch01") / "s02-harbour.mp3.json").read_text())["tempo"] == 1.2

    # edit one scene's text: exactly that one clip is bought again
    path = project.root / "story" / "ch01.py"
    path.write_text(path.read_text().replace("Before dawn the captain", "At dawn the captain"))
    voice.voice_chapter(project, "ch01")
    assert len(fake.calls) == n + 1

    # no file the pipeline wrote may contain the key
    for f in project.root.rglob("*"):
        if f.is_file() and f.suffix in (".json", ".txt", ".md", ".py", ".html", ".log"):
            assert FAKE_KEY not in f.read_text(errors="ignore"), f


@needs_ffmpeg
def test_failed_voice_stops_with_a_clear_message(project, monkeypatch):
    def boom(*a):
        raise OSError("connection refused")
    monkeypatch.setenv("FAL_KEY", FAKE_KEY)
    monkeypatch.setattr(voice, "synth_fal", boom)
    monkeypatch.setattr(voice.time, "sleep", lambda s: None)
    project.cfg["voice"]["provider"] = "fal"
    with pytest.raises(SystemExit, match="voice failed"):
        voice.voice_chapter(project, "ch01")


def test_fal_request_shape(project, monkeypatch, tmp_path):
    """the request the real endpoint expects, without calling it"""
    seen = {}

    def fake_http(url, body, headers, timeout=300):
        seen.update(url=url, body=body, headers=headers)
        return json.dumps({"audio": {"url": "https://example.invalid/a.mp3"}}).encode()

    monkeypatch.setenv("FAL_KEY", FAKE_KEY)
    monkeypatch.setattr(voice, "_http_json", fake_http)
    monkeypatch.setattr(voice, "download", lambda url, out, timeout=300: seen.update(download=url))
    voice.synth_fal({"text": "hello", "voice": "Bill"}, "v2", tmp_path / "a.mp3")
    assert seen["url"] == "https://fal.run/fal-ai/elevenlabs/tts/multilingual-v2"
    assert seen["headers"]["Authorization"] == f"Key {FAKE_KEY}"
    assert seen["download"].endswith("a.mp3")


def test_missing_key_says_what_to_do(tmp_path):
    with pytest.raises(SystemExit, match="FAL_KEY"):
        voice.synth_fal({"text": "x"}, "v2", tmp_path / "a.mp3")
    with pytest.raises(SystemExit, match="ELEVENLABS_API_KEY"):
        voice.synth_eleven({"text": "x"}, "v2", tmp_path / "a.mp3", "id")


def test_effects_are_skipped_without_a_key(project, capsys):
    sound.sfx_chapter(project, "ch01")
    assert "skipping" in capsys.readouterr().out
    assert not list(project.sfx_dir("ch01").glob("*.mp3"))


def test_music_refuses_to_spend_without_being_told(voiced, monkeypatch):
    from book_to_movie.timing import timing_chapter
    timing_chapter(voiced, "ch01")
    path = voiced.root / "story" / "ch01.py"
    path.write_text(path.read_text() + '\nMUSIC = {"m1": {"global": ["strings"], "sections": [["a", ["s02-harbour"], ["slow"]]]}}\n')
    monkeypatch.setenv("FAL_KEY", FAKE_KEY)
    monkeypatch.setattr(sound, "_fal", lambda *a, **k: pytest.fail("music was bought without --allow-spend"))
    with pytest.raises(SystemExit, match="allow-spend"):
        sound.music_chapter(voiced, "ch01")


def test_music_plan_turns_with_the_scenes(voiced):
    from book_to_movie.timing import timing_chapter
    tm = timing_chapter(voiced, "ch01")
    cue = {"global": ["strings"], "sections": [["a", ["s01-chapter"], ["soft"]], ["b", ["s02-harbour"], ["rising"]]], "tail": 2.0}
    plan = sound.composition_plan(cue, tm)
    assert plan["sections"][0]["duration_ms"] == max(3000, int(tm["s01-chapter"]["duration"] * 1000))
    assert plan["sections"][1]["duration_ms"] == int(tm["s02-harbour"]["duration"] * 1000) + 2000
    assert "vocals" in plan["negative_global_styles"]
