"""Measure spoiler removal, preservation of harmless sentences, and latency.

Cases are written by the developer (not independent). Each spoiler case has terms that must NOT appear in the
output. Each safe case must come back word for word.
"""
import statistics
import sys
import time

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")
from pipeline import analyze_reader_review

PREFIX = "The acting is superb and the pacing is tight. "
SPOILERS = [
    ("Rosebud turns out to be his childhood sled.", ["sled"]),
    ("Darth Vader is Luke's father, and that scene still gives me chills.", ["father", "vader"]),
    ("Jack doesn't make it and freezes in the water while Rose lets go.", ["freezes", "lets go"]),
    ("It was all a simulation the whole time, which blew my mind.", ["simulation"]),
    ("The wife was behind everything from the start.", ["wife", "behind everything"]),
    ("Tyler is a figment of the narrator's imagination.", ["figment"]),
    ("Dumbledore is killed by Snape on the tower.", ["snape", "killed", "tower"]),
    ("Their mother had cancer all along and hid it from them.", ["cancer", "mother"]),
    ("In the end the hero dies saving his village.", ["dies"]),
    ("Both brothers get shot in the final standoff.", ["shot", "standoff"]),
    ("The killer is the narrator himself.", ["narrator", "killer"]),
    ("She wakes up in hospital and realises the whole film was in her head.", ["hospital", "her head"]),
    ("Spoiler: the aliens were humans from the future.", ["aliens", "humans"]),
    ("The dog doesn't survive, so bring tissues.", ["dog", "survive"]),
    ("Natasha sacrifices herself on Vormir to obtain the Soul Stone.", ["vormir", "sacrifices", "soul stone"]),
    ("Teddy is actually Andrew Laeddis, a patient at the hospital.", ["laeddis", "actually"]),
    ("Amy faked her own disappearance to frame Nick for murder.", ["faked", "frame", "murder"]),
    ("The finale reveals that the mentor was the villain all along.", ["mentor", "villain"]),
    ("Eventually the housekeeper's husband is discovered living in the bunker.", ["bunker", "husband"]),
    ("The film's biggest twist is that the detective is the thief.", ["detective", "thief"]),
    ("He loses his arm in the last battle and never walks again.", ["arm", "never walks"]),
    ("The hero's brother betrays him and joins the enemy.", ["betrays", "brother"]),
    ("Devara is actually dead, and he was killed by his own son.", ["actually dead", "killed"]),
    ("It turns out the whole town was a theme park.", ["theme park"]),
    ("She is revealed to be the queen's long-lost daughter.", ["long-lost", "daughter"]),
]
SAFE = [
    "The acting is superb and the cinematography is gorgeous.",
    "A tense, gripping war drama with strong performances.",
    "The romance between the leads is sweet and the chemistry is real.",
    "The dream sequences are gorgeous.",
    "The father-daughter bond is heartwarming and the dialogue is sharp.",
    "I'd watch it again tomorrow.",
    "The soundtrack is joyous and the editing is brisk.",
    "A beautifully shot, slow-burn mystery with a haunting soundtrack.",
    "The heist sequence is brilliantly executed and the editing is crisp.",
    "Her shattering performance is the heart of the film, and the score is triumphant.",
    "The dialogue is clunky and the villain is a cardboard cutout, though the stunts are spectacular.",
    "The screenplay is meticulous and the tension never lets up.",
    "It runs a little long, but the second half is worth the wait.",
    "The production design is superb and the costumes are lovely.",
    "Funny, warm and well cast, with a script that respects its audience.",
    "The pacing drags in the middle, yet the performances keep it afloat.",
    "A revenge thriller that knows exactly what it wants to be.",
    "The set pieces are inventive and the music is thunderous.",
    "Great visuals and superb sound design.",
    "The chemistry between the leads carries the film.",
]


def review(text):
    report = analyze_reader_review([text])
    return report["review"], report["reader_output"]["blocked"]


leaked, blocked_spoiler, kept_extra = 0, 0, 0
details = []
for sentence, forbidden in SPOILERS:
    out, blocked = review(PREFIX + sentence)
    low = out.lower()
    hit = [term for term in forbidden if term in low]
    leaked += bool(hit)
    blocked_spoiler += blocked
    kept_prefix = out.startswith(PREFIX.strip())
    kept_extra += (not kept_prefix)
    details.append((sentence, hit, kept_prefix))

changed_safe, blocked_safe = 0, 0
changed_examples = []
for sentence in SAFE:
    out, blocked = review(sentence)
    blocked_safe += blocked
    if out != sentence:
        changed_safe += 1
        changed_examples.append((sentence, out))

# Mixed reviews: harmless sentences around a spoiler must be untouched.
mixed_total, mixed_intact = 0, 0
for sentence, _ in SPOILERS[:12]:
    for safe in SAFE[:4]:
        text = safe + " " + sentence + " " + SAFE[5]
        out, _ = review(text)
        mixed_total += 1
        mixed_intact += out.startswith(safe) and out.endswith(SAFE[5])

timings = []
long_text = " ".join(SAFE) + " " + " ".join(s for s, _ in SPOILERS[:10])
for _ in range(15):
    start = time.perf_counter()
    analyze_reader_review([long_text])
    timings.append((time.perf_counter() - start) * 1000)
short_timings = []
for _ in range(25):
    start = time.perf_counter()
    analyze_reader_review([PREFIX + SPOILERS[1][0]])
    short_timings.append((time.perf_counter() - start) * 1000)

print(f"SPOILER cases: {len(SPOILERS)}  leaked: {leaked}  blocked-whole-review: {blocked_spoiler}  lost-opening-sentence: {kept_extra}")
for sentence, hit, kept in details:
    if hit or not kept:
        print("  LEAK/LOSS:", sentence, hit, kept)
print(f"SAFE cases: {len(SAFE)}  changed: {changed_safe}  blocked: {blocked_safe}")
for sentence, out in changed_examples:
    print("  CHANGED:", sentence, "->", out)
print(f"MIXED reviews: {mixed_total}  harmless sentences intact: {mixed_intact}")
print(f"LATENCY short (1 spoiler, ~2 sentences): median {statistics.median(short_timings):.0f} ms, p95 {sorted(short_timings)[int(len(short_timings)*0.95)-1]:.0f} ms")
print(f"LATENCY long ({len(long_text.split())} words): median {statistics.median(timings):.0f} ms, max {max(timings):.0f} ms")
