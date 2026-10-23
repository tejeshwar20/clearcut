"""Probe: tricky spoiler sentences. Prints output + whether forbidden terms leaked."""
import sys

sys.path.insert(0, ".")
from pipeline import analyze_reader_review

CASES = [
    ("The acting is superb. Rosebud turns out to be his childhood sled.", ["sled", "childhood"]),
    ("Great visuals. It was all a simulation the whole time, which blew my mind.", ["simulation"]),
    ("Brilliant direction. Darth Vader is Luke's father, and that scene still gives me chills.", ["father"]),
    ("The music is lovely. Jack doesn't make it and freezes in the water while Rose lets go.", ["freezes", "lets go", "doesn't make it"]),
    ("Strong performances throughout. Dumbledore is killed by Snape on the tower.", ["snape", "tower", "killed"]),
    ("I loved it. The hero loses his arm in the last battle and never walks again.", ["arm", "never walks"]),
    ("Gripping thriller. The wife was behind everything from the start.", ["wife", "behind everything"]),
    ("Fun ride. Turns out the mentor was the villain, which I didn't see coming.", ["mentor", "villain"]),
    ("Beautifully shot. The dog doesn't survive, so bring tissues.", ["dog", "survive"]),
    ("The pacing is tight. She wakes up in hospital and realises the whole film was in her head.", ["hospital", "in her head", "wakes up"]),
    ("Solid cast. Both brothers get shot in the final standoff.", ["shot", "standoff", "brothers"]),
    ("Clever script. The killer is the narrator himself, hiding in plain sight.", ["narrator", "killer"]),
    ("Wonderful film. In the last ten minutes, the city is destroyed and only the kid survives.", ["destroyed", "survives", "kid"]),
    ("The score is incredible. Spoiler: the aliens were humans from the future.", ["aliens", "humans", "future"]),
    ("Heartfelt drama. Their mother had cancer all along and hid it from them.", ["cancer", "mother"]),
    ("The visual effects are stunning, but I hated that the main character dies at the end.", ["dies", "main character"]),
    ("A tense, gripping war drama with strong performances.", []),
    ("The romance between the leads is sweet and the chemistry is real.", []),
]

leaks = 0
for text, forbidden in CASES:
    out = analyze_reader_review([text])["review"]
    leaked = [term for term in forbidden if term.lower() in out.lower()]
    leaks += bool(leaked)
    print(("LEAK " if leaked else "ok   ") + repr(out) + (f"  <- {leaked}" if leaked else ""))
print("\nleaking cases:", leaks, "/", sum(1 for _, f in CASES if f))
