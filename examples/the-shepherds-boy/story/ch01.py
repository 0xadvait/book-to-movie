"""A whole fable as one short film: Aesop, in V. S. Vernon Jones's 1912 translation (public domain).
Each scene is (id, art, narration). Numbers are spelled out, quotes are read verbatim, nothing is invented."""

TITLE = "The Shepherd's Boy and the Wolf"
CHAPTER = 1

S = [
    ("s01-title", "card:title", "The Shepherd's Boy and the Wolf. A fable of Aesop."),
    ("s02-flock", "hill",
     "A shepherd's boy was tending his flock near a village, and thought it would be great fun to hoax the villagers, "
     "by pretending that a wolf was attacking the sheep."),
    ("s03-shout", "village",
     "So he shouted out, \"Wolf! Wolf!\" And when the people came running up, he laughed at them for their pains."),
    ("s04-again", "village",
     "He did this more than once, and every time the villagers found they had been hoaxed, for there was no wolf at all."),
    ("s05-wolf", "hill", "At last a wolf really did come, and the boy cried, \"Wolf! Wolf!\" as loud as he could."),
    ("s06-nobody", "village",
     "But the people were so used to hearing him call, that they took no notice of his cries for help."),
    ("s07-leisure", "hill", "And so the wolf had it all his own way, and killed off sheep after sheep at his leisure."),
    ("s08-moral", "card:quote", "You cannot believe a liar, even when he tells the truth."),
]

LEAD = {"s01-title": 2.2, "s08-moral": 0.9}
HOLD = {"s01-title": 1.6, "s05-wolf": 0.8, "s07-leisure": 1.0, "s08-moral": 2.2}
TRANS = {"s05-wolf": ("fadeblack", 1.0), "s08-moral": ("fadeblack", 1.0)}

CARDS = {
    "s01-title": {"kind": "title", "eyebrow": "AESOP", "title": "THE SHEPHERD'S BOY", "sub": "and the wolf"},
    "s08-moral": {"kind": "quote", "text": "You cannot believe a liar, even when he tells the truth.", "attr": "Aesop"},
}

SETS = {
    "hill": {
        "desc": "A sheep meadow under far mountains, with a dark forest along one side and the village small in the valley. "
                "The boy on a rise with his crook, the flock around him. By day first, then at dusk under a low moon.",
        "scenes": ["s02-flock", "s05-wolf", "s07-leisure"],
        "shots": {"s02-flock": "day: wide, slow push toward the boy.",
                  "s05-wolf": "dusk: the wolf comes out of the forest at 'wolf', the boy throws up his arms at 'cried'.",
                  "s07-leisure": "night: the wolf among the flock, sheep slipping away one after another. No blood."},
        "reuse": None,
    },
    "village": {
        "desc": "A street of stone and timber cottages with thatched roofs and smoking chimneys. Villagers run in with sticks "
                "and hayforks by day. At night the same street stands still, windows lit, doors shut.",
        "scenes": ["s03-shout", "s04-again", "s06-nobody"],
        "shots": {"s03-shout": "day: the boy calls at 'shouted', the people run in at 'running', and he laughs at them.",
                  "s04-again": "dusk: the same trick, the crowd now walking away with slumped shoulders.",
                  "s06-nobody": "night: the boy small at the end of the empty street, nobody comes."},
        "reuse": None,
    },
}

# Effects are generated when FAL_KEY is set, and simply skipped otherwise.
SFX = [
    {"name": "meadow_wind", "scene": "s02-flock", "at": 0.0, "prompt": "gentle wind over an open hill meadow, distant sheep bleating", "dur": 15, "gain": -20, "loop": True},
    {"name": "village_day", "scene": "s03-shout", "at": 0.0, "prompt": "a small village street by day, chickens, a distant dog, footsteps on packed earth", "dur": 12, "gain": -20, "loop": True},
    {"name": "crowd_running", "scene": "s03-shout", "at": "cue:running", "prompt": "a small crowd of villagers running on packed earth, urgent footsteps, no speech", "dur": 4, "gain": -17},
    {"name": "wolf_howl", "scene": "s05-wolf", "at": "cue:wolf", "prompt": "a single wolf howling at dusk over open hills, long and low, natural", "dur": 5, "gain": -15},
    {"name": "night_street", "scene": "s06-nobody", "at": 0.0, "prompt": "a quiet village street at night, crickets, faint wind, nothing else", "dur": 12, "gain": -21, "loop": True},
    {"name": "sheep_scatter", "scene": "s07-leisure", "at": "cue:sheep", "prompt": "frightened sheep bleating and scattering in the dark, distant", "dur": 5, "gain": -18},
]
