# Book to movie, for coding agents

If you were asked to turn a book into a film, read `.claude/skills/book-to-movie/SKILL.md` and follow it. It was written for
Claude Code, but nothing in it depends on Claude Code except spawning helpers. If you cannot spawn helpers, do their jobs
yourself using their briefs:

- `.claude/agents/screenwriter.md`: adapting the text into a narration script.
- `.claude/agents/illustrator.md`: drawing and animating scenes in code.

`./movie --help` lists every deterministic step. `examples/the-shepherds-boy/` is a complete worked example.
Keys come only from the environment or the git-ignored `.env`. Never write a key into any other file.
