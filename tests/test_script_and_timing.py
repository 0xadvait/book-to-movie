"""The rules that stop money being spent on a broken script, and the timing everything hangs from."""
import json

import pytest

from book_to_movie.check import check_chapter
from book_to_movie.project import chapter_tag, cue_seconds, mix_hex, norm, parse_cue, resolve_look, roman, slugify
from book_to_movie.timing import timing_chapter


def write(project, text):
    (project.root / "story" / "ch01.py").write_text(text)
    return check_chapter(project, "ch01")


def module(narration='Before dawn the captain walked.', art="harbour", extra=""):
    return f'''
TITLE = "T"
CHAPTER = 1
S = [("s01-one", {art!r}, {narration!r})]
SETS = {{"harbour": {{"desc": "x", "scenes": ["s01-one"], "shots": {{}}, "reuse": None}}}}
CARDS = {{}}
{extra}
'''


def test_good_script_passes(project):
    errors, warnings, summary = check_chapter(project, "ch01")
    assert errors == []
    assert summary["scenes"] == 3 and summary["sets"] == 1


def test_digits_are_refused(project):
    assert any("digits" in e for e in write(project, module("In 1937 he left."))[0])


def test_dashes_are_refused(project):
    assert any("dash" in e for e in write(project, module("He left — at once."))[0])


def test_unknown_set_is_refused(project):
    assert any("is not in SETS" in e for e in write(project, module(art="nowhere"))[0])


def test_card_needs_an_entry(project):
    assert any("no entry in CARDS" in e for e in write(project, module(art="card:quote"))[0])


def test_card_kind_must_exist(project):
    assert any("unknown card kind" in e for e in write(project, module(art="card:poster"))[0])


def test_card_text_must_be_spoken(project):
    extra = 'CARDS = {"s01-one": {"kind": "quote", "text": "Words nobody ever says in this scene at all"}}'
    assert any("not spoken" in e for e in write(project, module(art="card:quote", extra=extra))[0])


def test_effect_cue_must_be_spoken(project):
    extra = 'SFX = [{"name": "x", "scene": "s01-one", "at": "cue:thunder", "prompt": "p"}]'
    assert any("cue" in e for e in write(project, module(extra=extra))[0])
    extra = 'SFX = [{"name": "x", "scene": "s01-one", "at": "cue:captain", "prompt": "p"}]'
    assert write(project, module(extra=extra))[0] == []


def test_references_to_missing_scenes_are_refused(project):
    extra = 'TRANS = {"s09-gone": ("fade", 1.0)}\nLEAD = {"s09-gone": 1.0}\nMUSIC = {"m": {"global": [], "sections": [["a", ["s09-gone"], []]]}}'
    errors = write(project, module(extra=extra))[0]
    assert len([e for e in errors if "s09-gone" in e]) == 3


def test_chapter_number_must_match_the_file(project):
    assert any("CHAPTER" in e for e in write(project, module().replace("CHAPTER = 1", "CHAPTER = 2"))[0])


def test_norm_compares_across_spelling_and_alphabets():
    assert norm("Wolf!") == norm("wolf") == "wolf"
    assert norm("don’t") == norm("don't") == "dont"
    assert norm("café") == "cafe"
    assert norm("fifty-cent") == "fiftycent"
    assert norm("волк") == "волк"       # Cyrillic survives
    assert norm("—") == ""


@pytest.mark.parametrize("value,expected", [
    ("cue:wolf", ("wolf", 1, 0.0)),
    ("cue:wolf#2", ("wolf", 2, 0.0)),
    ("cue:wolf+0.4", ("wolf", 1, 0.4)),
    ("cue:wolf-0.25", ("wolf", 1, -0.25)),
    ("cue:wolf#3-0.5", ("wolf", 3, -0.5)),
    ("cue:fifty-cent", ("fiftycent", 1, 0.0)),
    ("cue:fifty-cent#2+1", ("fiftycent", 2, 1.0)),
])
def test_cue_grammar(value, expected):
    assert parse_cue(value) == expected


def test_bad_time_is_explained():
    with pytest.raises(ValueError, match="cue:word"):
        parse_cue("soon")


def test_cue_seconds_adds_the_narration_offset():
    words = [{"w": "the", "s": 0.0, "e": 0.2}, {"w": "Wolf!", "s": 0.5, "e": 0.9}, {"w": "wolf", "s": 1.5, "e": 2.0}]
    assert cue_seconds("cue:wolf", words, 1.0) == 1.5
    assert cue_seconds("cue:wolf#2+0.5", words, 1.0) == 3.0
    with pytest.raises(ValueError, match="1 time|2 time"):
        cue_seconds("cue:wolf#3", words, 0.0)


def test_timing_stacks_scenes_end_to_end(voiced):
    tm = timing_chapter(voiced, "ch01")
    order = ["s01-chapter", "s02-harbour", "s03-quote"]
    assert tm[order[0]]["start"] == 0.0
    assert tm[order[0]]["vo_offset"] == 1.0                      # from LEAD
    assert tm[order[1]]["vo_offset"] == 0.35                     # picture default
    assert tm[order[2]]["vo_offset"] == 1.0                      # card default
    for a, b in zip(order, order[1:]):
        assert tm[b]["start"] == pytest.approx(tm[a]["start"] + tm[a]["duration"], abs=0.002)
    assert tm[order[1]]["duration"] == pytest.approx(0.35 + tm[order[1]]["vo_duration"] + 0.5, abs=0.002)
    assert json.loads((voiced.specs("ch01") / "_timing.json").read_text()) == tm
    assert "s02-harbour" in (voiced.specs("ch01") / "_scenes.md").read_text()


def test_small_helpers():
    assert chapter_tag(3) == chapter_tag("3") == chapter_tag("ch03") == chapter_tag("03") == "ch03"
    with pytest.raises(SystemExit):
        chapter_tag("three")
    assert [roman(n) for n in (1, 4, 9, 14, 40, 90, 2024)] == ["I", "IV", "IX", "XIV", "XL", "XC", "MMXXIV"]
    assert slugify("The Shepherd's Boy & the Wolf!") == "the-shepherd-s-boy-the-wolf"
    assert mix_hex("#000000", "#ffffff", 0.5) == "#808080"


def test_looks_fill_in_what_is_not_given():
    for name in ("sepia", "noir", "indigo", "forest", "oxblood"):
        assert {"paper", "ink", "accent", "ink_soft", "ink_mute", "line", "slip", "shade"} <= set(resolve_look(name))
    assert resolve_look({"paper": "#ffffff", "ink": "#000000"})["accent"]
    with pytest.raises(SystemExit):
        resolve_look({"paper": "#ffffff"})


def test_user_settings_merge_over_defaults(tmp_path):
    from book_to_movie.project import Project
    (tmp_path / "movie.json").write_text(json.dumps({"voice": {"name": "Rachel"}, "music": True}))
    p = Project(tmp_path)
    assert p.cfg["voice"]["name"] == "Rachel" and p.cfg["voice"]["tempo"] == 1.07
    assert p.cfg["music"] is True and p.cfg["sfx"] is True


def test_music_is_off_unless_asked_for(project):
    assert project.cfg["music"] is False
