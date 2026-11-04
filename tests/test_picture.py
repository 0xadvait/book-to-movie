"""Compositions, cards and the engraver. Rendering itself is covered by ./movie demo."""
import json
import re

import numpy as np
import pytest
from PIL import Image

from book_to_movie import cards, figures, render, scene_html, svgkit
from book_to_movie.art import Set
from book_to_movie.engrave import engrave, make_tileable
from book_to_movie.timing import timing_chapter

from .conftest import needs_ffmpeg, needs_rsvg


def spec(project, sid="s02-harbour", **extra):
    base = {"id": sid, "set": "harbour", "layers": [{"name": "sky", "src": "sky.png", "z": 0.0}], "camera": [{"t": 0}, {"t": "end", "zoom": 1.05}]}
    base.update(extra)
    (project.specs("ch01") / f"{sid}.json").write_text(json.dumps(base))


def payload(html):
    return json.loads(re.search(r"var P = (\{.*\});", html).group(1))


def test_composition_is_complete_and_timed_from_cues(voiced):
    timing_chapter(voiced, "ch01")
    spec(voiced, layers=[{"name": "boat", "src": "boat.png", "z": 0.5, "move": [{"t": 0, "x": 0}, {"t": "cue:water", "x": 100}]}],
         text=[{"type": "stamp", "text": "QUIT", "at": "cue:lamp+0.5", "x": 1, "y": 1}])
    html = scene_html.build(voiced, "ch01", "s02-harbour").read_text()
    assert not re.findall(r"%[A-Z]+%", html), "an unfilled template token"
    tm = voiced.timing("ch01")["s02-harbour"]
    words = voiced.words("ch01", "s02-harbour")
    water = next(w for w in words if w["w"].startswith("water"))
    p = payload(html)
    assert p["layers"][0]["move"][1]["t"] == pytest.approx(tm["vo_offset"] + water["s"], abs=0.002)
    assert p["dur"] == pytest.approx(tm["duration"] + 1.0, abs=0.002)
    assert "../../assets/art/ch01/harbour/boat.png" in html
    assert 'data-composition-id="s02-harbour"' in html


def test_a_cue_for_an_unspoken_word_fails_loudly(voiced):
    timing_chapter(voiced, "ch01")
    spec(voiced, text=[{"type": "label", "text": "x", "at": "cue:thunder"}])
    with pytest.raises(ValueError, match="thunder"):
        scene_html.build(voiced, "ch01", "s02-harbour")


def test_quote_words_follow_the_voice_even_with_words_added_inside(voiced):
    timing_chapter(voiced, "ch01")
    spec(voiced, text=[{"type": "quote", "text": "captain walked to the water", "at": 0.5}])
    p = payload(scene_html.build(voiced, "ch01", "s02-harbour").read_text())
    times = p["text"][0]["times"]
    assert times == sorted(times) and len(times) == 5


def test_look_reaches_the_composition(voiced):
    voiced.look = {**voiced.look, "paper": "#123456", "accent": "#abcdef"}
    timing_chapter(voiced, "ch01")
    spec(voiced)
    html = scene_html.build(voiced, "ch01", "s02-harbour").read_text()
    assert "--paper:#123456" in html and "--accent:#abcdef" in html
    assert "--font-display:'Cinzel'" in html


def test_reused_art_from_another_set_keeps_its_path(voiced):
    timing_chapter(voiced, "ch01")
    spec(voiced, layers=[{"src": "../../assets/art/ch01/other/sky.png", "z": 0}])
    assert 'src="../../assets/art/ch01/other/sky.png"' in scene_html.build(voiced, "ch01", "s02-harbour").read_text()


def test_composition_hash_notices_a_changed_image(voiced, tmp_path):
    timing_chapter(voiced, "ch01")
    spec(voiced)
    art = voiced.art_assets("ch01", "harbour") / "sky.png"
    art.write_bytes(b"one")
    html = scene_html.build(voiced, "ch01", "s02-harbour")
    first = render.composition_hash(html)
    assert render.composition_hash(html) == first
    art.write_bytes(b"something else")
    assert render.composition_hash(html) != first


def test_titles_fit_the_ribbon():
    assert cards.fit_size("SHORT", 112) == 112
    assert cards.fit_size("A TITLE OF SOME LENGTH", 112) < 112
    long_title = "AN EXTREMELY LONG TITLE FOR A BOOK THAT KEEPS GOING ON"
    assert 46 <= cards.fit_size(long_title, 94) <= 72
    very_long = "X" * 200
    assert cards.fit_size(very_long, 94) == 46


def test_quote_slips_stay_on_the_page():
    assert cards.quote_top("short", 52, 1260) > 300
    assert cards.quote_top("word " * 120, 38, 1260) >= 120


def test_figures_draw_every_pose_and_hat():
    for pose in figures.POSES:
        assert "<path" in figures.figure(pose)
    for hat in ("none", "cap", "bowler", "fedora", "top", "boater", "miner", "slouch", "hood", "crown", "helmet"):
        assert "<path" in figures.figure("stand", hat=hat)
    svg, pts = figures.figure("stand", anchors=True, x=100, y=200)
    assert {"hand_f", "hand_b", "head", "feet"} <= set(pts)
    for head in (None, "pick", "broom", "fork", "stave"):
        assert "<path" in figures.held((0, 0), 45, 100, head=head)


def test_figures_face_both_ways_about_their_feet():
    _, right = figures.figure("point", x=500, y=800, facing=1, anchors=True)
    _, left = figures.figure("point", x=500, y=800, facing=-1, anchors=True)
    assert right["hand_f"][0] - 500 == pytest.approx(500 - left["hand_f"][0])


@needs_rsvg
def test_engraving_inks_the_dark_and_spares_the_light(tmp_path):
    svg = tmp_path / "t.svg"
    svg.write_text(svgkit.doc(400, 200, f'<rect width="200" height="200" fill="{svgkit.gray(0.95)}" data-h="0"/>'
                                        f'<rect x="200" width="200" height="200" fill="#ffffff" data-h="paper"/>'))
    out = tmp_path / "t.png"
    engrave(str(svg), str(out), out_scale=1.0, seed=1)
    a = np.asarray(Image.open(out).convert("RGB"), np.float32)
    half = a.shape[1] // 2
    assert a[:, :half].mean() < a[:, half:].mean() - 60
    assert a[:, half + 8:, 0].std() < 8                  # bare paper, no lines


@needs_rsvg
def test_engraving_is_repeatable_and_takes_the_palette(tmp_path):
    svg = tmp_path / "t.svg"
    svg.write_text(svgkit.doc(200, 100, f'<rect width="200" height="100" fill="{svgkit.gray(0.6)}" data-h="30"/>'))
    a, b, c = tmp_path / "a.png", tmp_path / "b.png", tmp_path / "c.png"
    engrave(str(svg), str(a), seed=3)
    engrave(str(svg), str(b), seed=3)
    assert a.read_bytes() == b.read_bytes()
    engrave(str(svg), str(c), seed=3, paper="#eef0ea", ink="#172658")
    blue = np.asarray(Image.open(c).convert("RGB"), np.float32)
    assert blue[..., 2].mean() > blue[..., 0].mean()


@needs_rsvg
def test_set_writes_layers_and_only_redoes_what_changed(project, capsys):
    folder = project.art_dir("ch01", "harbour")
    folder.mkdir(parents=True)
    build = folder / "build.py"
    build.write_text("# stands in for a drawing script\n")

    def draw(tone):
        s = Set(build, workers=2)
        s.layer("sky", f'<rect x="-100" y="-60" width="2120" height="1200" fill="{svgkit.gray(tone)}" data-h="0"/>')
        s.sprite("lamp", '<rect width="40" height="40" fill="#f0a447" data-h="paper"/>', 40, 40)
        s.done()
        return s

    s = draw(0.4)
    assert "2 engraved" in capsys.readouterr().out
    assert Image.open(s.out / "sky.png").size == (2640, 1485)
    assert Image.open(s.out / "lamp.png").size == (50, 50)
    assert [i["name"] for i in json.loads((s.out / "layers.json").read_text())] == ["sky", "lamp"]
    draw(0.4)
    assert "0 engraved, 2 unchanged" in capsys.readouterr().out
    draw(0.6)
    assert "1 engraved, 1 unchanged" in capsys.readouterr().out


def test_tiling_cross_fades_the_seam(tmp_path):
    w, tile = 300, 250
    a = np.zeros((10, w, 4), np.uint8)
    a[..., 3] = 255
    a[:, :, 0] = np.linspace(0, 255, w).astype(np.uint8)
    Image.fromarray(a).save(tmp_path / "in.png")
    make_tileable(tmp_path / "in.png", tmp_path / "out.png", tile)
    out = np.asarray(Image.open(tmp_path / "out.png"), np.float32)
    assert out.shape[1] == tile
    # the first column continues from where the last one stops
    expected = a[0, tile, 0]
    assert abs(out[0, 0, 0] - float(expected)) < 8


@needs_rsvg
@needs_ffmpeg
def test_every_card_kind_makes_a_composition(voiced):
    path = voiced.root / "story" / "ch01.py"
    path.write_text('''
TITLE = "T"
CHAPTER = 1
S = [("s01-t", "card:title", "A title line here."), ("s02-c", "card:chapter", "Chapter one here."), ("s03-s", "card:section", "A section here."),
     ("s04-q", "card:quote", "He said the words."), ("s05-w", "card:words", "One short line."), ("s06-p", "card:portrait", "She said a thing."),
     ("s07-x", "card:close", "The last line. Next, the end."), ("s08-e", "card:close", "Truly the end now.")]
CARDS = {"s01-t": {"kind": "title", "eyebrow": "A", "title": "THE TITLE", "sub": "s"}, "s02-c": {"kind": "chapter", "eyebrow": "ONE", "title": "CH", "step": "STEP"},
         "s03-s": {"kind": "section", "eyebrow": "TWO", "title": "SEC"}, "s04-q": {"kind": "quote", "text": "the words", "attr": "He"},
         "s05-w": {"kind": "words", "text": "One short | line."}, "s06-p": {"kind": "portrait", "person": "A Person", "quote": "a thing"},
         "s07-x": {"kind": "close", "title": "THE LAST LINE", "next_eyebrow": "NEXT", "next_title": "THE END", "next_sub": "s"},
         "s08-e": {"kind": "close", "title": "TRULY THE END"}}
SETS = {}
''')
    mod = voiced.module("ch01")
    for sid, _, text in mod.S:
        t, words = 0.0, []
        for w in text.split():
            words.append({"w": w, "s": round(t, 3), "e": round(t + 0.3, 3)})
            t += 0.35
        (voiced.voice_dir("ch01") / f"{sid}.words.json").write_text(json.dumps({"duration": round(t, 3), "words": words, "match": 1.0}))
    timing_chapter(voiced, "ch01")
    cards.cards_chapter(voiced, "ch01")
    for sid, _, _ in mod.S:
        html = scene_html.build(voiced, "ch01", sid).read_text()
        assert not re.findall(r"%[A-Z]+%", html)
    # the numerals follow the chapter, and the very last close card needs no "next"
    assert (voiced.art_assets("ch01", "cards") / "corners_I.svg").exists()
    assert len(json.loads((voiced.specs("ch01") / "s08-e.json").read_text())["text"]) == 1
