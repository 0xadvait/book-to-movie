---
name: book-to-movie
description: Turn a book (PDF, EPUB, text, Word or HTML) into an illustrated, narrated film, one story at a time. Use when someone wants to make a movie, film, animation or video adaptation of a book, novel, story or long document. Pass the path to the book.
---

# Book to movie

You are the director. You read the book, plan the film, get it approved, and run a small crew: screenwriters who adapt the
text, illustrators who draw every frame in code, and `./movie`, which does everything deterministic (voice, timing,
rendering, mixing, joining). Run all commands from the repo root.

Work in this order and do not skip the two approval gates: a rendered film is expensive to redo.

## 1. Start the project

1. If `.venv` is missing, run `./setup.sh`. Then `./movie doctor`. Fix anything marked MISSING. Tell the person which voice
   they will get: `fal` or `elevenlabs` if a key is in `.env` or the shell, otherwise the computer's free voice. Free is fine for
   a pilot. To force it even with a key present, set `"voice": {"provider": "say"}` in `movie.json` (`espeak` on Linux, or
   `silent` for an animatic with real timing and no sound).
2. `./movie new <book> --title "..." --author "..."` makes `projects/<slug>/` and prints the chapters it found. Check the
   table. If the split is wrong (a contents page counted, chapters merged), re-run with `--force --heading 'REGEX'`. A scan
   with no text layer needs OCR first.
3. **Rights, once, in one line.** If the book is not clearly public domain or the person's own, ask whether they have the
   right to adapt it. If it is plainly someone else's and they do not, say that this needs the rights holder's permission
   and stop there. Never publish, and never quote, more than they have the right to.

## 2. The treatment (approval gate one)

Read the book: `source/chapters.json`, then the chapters. For a long book, read the opening and closing chapters yourself
and have `Explore` agents summarise the rest. Then write `TREATMENT.md` in the project:

| Part | From chapters | The story we tell | Set pieces | Minutes |
|---|---|---|---|---|

The idea that makes this work: **one story per part.** Not a summary of every chapter, a story. Non-fiction: the author's
best anecdote for that idea. Fiction: the plot's spine, grouped so each part has its own beginning and turn. A long novel
maps several chapters to one part. Aim for 6 to 12 minutes a part. Open on a scene. Part one also carries the film's title
card.

Set these in `movie.json`:
- `period`: what the illustrators draw, in one sentence ("Regency England, country houses and muddy lanes").
- `look`: `sepia` (default), `noir`, `indigo`, `forest`, `oxblood`, or `{"paper": "#...", "ink": "#...", "accent": "#..."}`.
- `voice`: `name` is any ElevenLabs voice (default `Bill`, an older storyteller), `respell` fixes specific words the voice
  gets wrong, only after hearing them wrong. Let names alone until then: forced respellings often sound worse.
- `whisper`: the speech model for word timing. `large-v3-turbo` (default) is the most accurate, `small` is a smaller download.
- `language` if not English. Only English has been tested end to end; the fonts shipped cover Latin script, and whisper's
  word timing assumes words separated by spaces.

Show the person the treatment, the look and the rough cost (below). Wait for their yes.

## 3. The pilot (approval gate two)

Make part one completely before anything else. It is how you find out if the look, the voice and the pace are right.

1. Spawn one `screenwriter` agent for part one. Read what it wrote: the narration is the film.
2. `./movie check 1`, then `./movie cost` so the person sees the bill before you spend it.
3. `./movie voice 1` then `./movie sfx 1`. (`voice` also times every word and writes the cards, and it refuses a script with
   errors. Effects are skipped without a key, and the mix does not mind.)
4. `./movie sheet 1` lists the sets. Spawn `illustrator` agents, each owning 2 to 4 sets and their scenes, with no overlap.
   Run at most 3 or 4 at once on a laptop: each renders video, and 8 or 9 at once saturate a 12-core machine. Give each the
   project name, chapter, and exact list of sets and scene ids. Look at the frames they report.
5. `./movie finish 1` renders whatever changed, mixes, joins and checks. Read its output:
   - The whisper line compares the soundtrack with the script. Below 0.90 usually means a garbled word. Full-file whisper
     sometimes skips words, so re-check a flagged scene on its own before paying to re-voice it.
   - "Names not heard as written" is a list of words to listen to.
6. Open the master for the person (`open` on a Mac) and ask for a verdict on look, voice, pace and length. Nothing else gets
   drawn until they like it. If they want it faster, change `voice.tempo` and run `./movie voice 1`: tempo re-times the audio
   without paying again, and cues follow the words.

## 4. The rest of the film

1. Screenwriters in parallel, two parts each. `./movie check all`.
2. `./movie voice all`, `./movie sfx all`. Portrait cards need `./movie portrait NN <slug> "File:..."` with a public-domain file
   from Wikimedia Commons; it refuses anything else.
3. Illustrators in waves, a few parts at a time, `./movie status` between waves. Tell them which approved part to match.
4. `./movie finish NN` per part as its art lands, then `./movie film` joins everything with chapter markers.

Tell the person where the film is, how long it runs and how big the file is. `./movie phone film` makes a small copy for
sending.

## What it costs

Measured on the film this repo was built for (a 92,000-word book, 15 parts, 1 hour 48 minutes):

- **Claude:** one part took about seven illustrators and 3.7 million subagent tokens. This is the real bill. Keep sets few and
  reuse places.
- **Audio through fal:** narration about $0.10 per 1,000 characters (about $1 a part), effects $0.002 a second, music $0.60 a
  minute. `./movie cost` adds it up for your script.
- **Disk:** the finished project reached 76 GB, mostly scene renders and check frames. `build/` can be deleted at any time.
- **Time:** a 20-second scene renders in about 30 seconds on a laptop.

Music is off by default on purpose: it was $69 of the $86 audio bill, and on that film it was the one thing cut in the end. To turn it on, write MUSIC tables, set `"music": true` in `movie.json` and run `./movie music NN --allow-spend`, but only
if the person asks for it.

## When something goes wrong

| What you see | What to do |
|---|---|
| `voice` refuses a script | `./movie check NN` lists the errors: usually digits or a dash in narration |
| A cue error: "the narration says that word 0 time(s)" | Use a word that is really in that scene's narration |
| A layer pops or a frame edge shows | Camera moved past the overhang: see the camera limits in the illustrator brief |
| A render fails | The error names the spec and the cause (a bad image path, a cue that is not spoken), or the log to read |
| The voice stumbles over a word | Add it to `voice.respell` in `movie.json`, then `./movie voice NN`: only that scene is re-voiced |
| A scene is a blank paper bar in the cut | It has no spec yet: the cut works anyway, with placeholders |
| Running out of disk | Delete `build/`, then renders of finished parts in `film/renders/chNN/` once the masters exist |

## Rules

- Keys stay in `.env`. Never write one into a file, a spec or a commit.
- Ask before anything that costs real money beyond what `./movie cost` showed, and before generating music.
- Do not redo finished work: `./movie render` only repeats scenes whose composition or images changed.
- Never invent facts in the narration. Dramatise with pictures, not claims.
