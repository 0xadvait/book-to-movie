# Book to movie

This repo turns books into illustrated, narrated films. When someone wants to make a film of a book, use the
`book-to-movie` skill (`.claude/skills/book-to-movie/SKILL.md`). It runs the `screenwriter` and `illustrator` agents and the
`./movie` command line.

- `book_to_movie/` is the pipeline. `examples/the-shepherds-boy/` is a complete worked film. `projects/` is where films are made,
  and it is git-ignored, so books, audio and renders never get committed.
- Keys are read only from the environment or `.env`, which is also git-ignored. Never write a key into any other file.
- Tests: `.venv/bin/pytest`. They need no network, keys, whisper or renderer. `./movie demo` is the end-to-end check.
