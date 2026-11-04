"""This repo is public. This test fails if a credential, a personal path or a stray binary ever lands in it."""
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

CREDENTIALS = {
    "fal key": r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:[0-9a-f]{32}\b",
    "ElevenLabs key": r"\bsk_[0-9a-f]{40,}\b",
    "OpenAI or Anthropic key": r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}\b",
    "Replicate token": r"\br8_[A-Za-z0-9]{30,}\b",
    "Google key": r"\bAIza[0-9A-Za-z_-]{30,}\b",
    "GitHub token": r"\bgh[pousr]_[A-Za-z0-9]{30,}\b",
    "AWS access key": r"\bAKIA[0-9A-Z]{16}\b",
    "DigitalOcean token": r"\bdop_v1_[0-9a-f]{40,}\b",
    "Fireworks key": r"\bfw_[A-Za-z0-9]{20,}\b",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "JWT": r"\beyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b",
}
PERSONAL = {
    "home path": r"/(?:Users|home)/[a-z][a-z0-9._-]+/",
    "scratch path": r"/private/tmp/|claude-\d{3}/",
    "email": r"\b[A-Za-z0-9._%+-]+@(?!example\.|anthropic\.com)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
}
TEXT = {".py", ".md", ".json", ".toml", ".sh", ".yml", ".yaml", ".txt", ".example", ".html", ".css", ".svg", ""}
ALLOWED_BINARY = {".woff2", ".png", ".jpg", ".mp4", ".gif", ".webp"}


def tracked():
    """everything git would publish: tracked files plus anything new and not ignored"""
    r = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=REPO, capture_output=True, text=True)
    if r.returncode:
        pytest.skip("not a git checkout")
    return [REPO / f for f in r.stdout.splitlines() if (REPO / f).is_file()]


def test_no_credentials_or_personal_paths_anywhere():
    this_file = Path(__file__).resolve()
    problems = []
    for f in tracked():
        if f.suffix not in TEXT or f.resolve() == this_file or f.name.startswith("OFL-"):     # font licences name their authors
            continue
        text = f.read_text(errors="ignore")
        for name, rx in {**CREDENTIALS, **PERSONAL}.items():
            for m in re.finditer(rx, text):
                problems.append(f"{f.relative_to(REPO)}: {name}: {m.group(0)[:12]}...")
    assert not problems, "\n".join(problems)


def test_keys_only_come_from_the_environment():
    """no assignment of a literal to anything that looks like a key, in code"""
    rx = re.compile(r"""(?:key|token|secret|password)\w*\s*=\s*["'][^"']{12,}["']""", re.I)
    problems = []
    for f in tracked():
        if f.suffix == ".py" and "tests" not in f.parts:
            problems += [f"{f.relative_to(REPO)}: {m.group(0)[:40]}" for m in rx.finditer(f.read_text())]
    assert not problems, "\n".join(problems)


def test_private_folders_are_ignored():
    for path in (".env", ".env.local", "projects/anything/book.pdf", "projects/x/movie.json", ".venv/x"):
        r = subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO)
        assert r.returncode == 0, f"{path} is not git-ignored"
    assert subprocess.run(["git", "check-ignore", "-q", ".env.example"], cwd=REPO).returncode != 0


def test_env_example_holds_no_values():
    for line in (REPO / ".env.example").read_text().splitlines():
        if line and not line.startswith("#"):
            assert line.rstrip().endswith("="), f"a value in .env.example: {line.split('=')[0]}"


def test_no_unexpected_binaries_or_big_files():
    for f in tracked():
        assert f.stat().st_size < 30 * 1024 * 1024, f"{f.name} is too big to commit"
        if f.suffix not in TEXT:
            assert f.suffix in ALLOWED_BINARY, f"unexpected file type: {f.relative_to(REPO)}"


def test_no_book_text_or_renders_ship_except_the_public_domain_example():
    for f in tracked():
        rel = f.relative_to(REPO)
        assert f.suffix != ".pdf" and f.suffix != ".epub", rel
        if f.suffix in (".mp3", ".wav"):
            pytest.fail(f"audio in the repo: {rel}")
        if f.name == "book.txt":
            assert "Public domain" in f.read_text(), rel


def test_images_carry_no_metadata():
    from PIL import Image
    for f in tracked():
        if f.suffix in (".png", ".jpg"):
            with Image.open(f) as im:
                info = {k: v for k, v in im.info.items() if k not in ("dpi", "gamma", "srgb", "jfif", "jfif_version", "jfif_density", "jfif_unit", "progressive", "progression")}
                assert not info, f"{f.name} carries metadata: {sorted(info)}"
                assert not im.getexif(), f"{f.name} carries EXIF"
