"""50 long, deliberately confusing reviews: 36 with real spoilers, 14 safe ones with spoiler-looking words.

Each case is (text, forbidden_substrings, must_keep_substrings).
"""

OPENING = (
    "The cinematography is lush and patient, the score is quietly devastating, and the lead performances feel lived in. "
    "The pacing sags a little in the second hour but the dialogue stays sharp. "
)
CLOSING = " I would still recommend it for the craft alone."
CRAFT = ("cinematography", "score", "dialogue")

SPOILERS = [
    ("Halfway through, Dr. Imran is quietly replaced by an android duplicate and nobody in the lab notices until the credits.", ["android", "duplicate", "imran"]),
    ("By the last reel the orphan Tilda learns that the headmistress is her real mother, which recontextualises every cold glance.", ["headmistress", "mother", "tilda"]),
    ("I won't say who, but one of the three climbers does not come home, and it is the one you least expect: the guide.", ["guide", "does not come home"]),
    ("The rival chef sabotaged the oven in act two, and the final dinner service collapses because of it.", ["sabotaged", "oven", "rival chef", "collapses"]),
    ("It is revealed that the whole village is a film set built to keep Odile from leaving.", ["film set", "odile", "village"]),
    ("The submarine captain, riddled with guilt, scuttles his own vessel and drowns with the crew.", ["scuttles", "drowns", "captain"]),
    ("Everyone assumes the thief is Bram, but it was actually the quiet librarian who stole the manuscript.", ["librarian", "bram", "manuscript"]),
    ("In a gutting final scene Wren hands the crown to her sworn enemy and walks into the sea.", ["crown", "enemy", "walks into the sea", "wren"]),
    ("The twist? The narrator has been the ghost haunting the house from the very first night.", ["ghost", "narrator", "house"]),
    ("Then the protagonist wakes up in the hospital bed and we learn the whole expedition was a coma hallucination.", ["coma", "hallucination", "hospital"]),
    ("Spoilers ahead: the vaccine was fake and the senator knew all along.", ["vaccine", "senator", "fake"]),
    ("When the lights come back on, the twin brother is standing where the dead man was lying, which implies they swapped places.", ["twin", "swapped", "dead man"]),
    ("The mentor Saul dies saving the kids from the avalanche, and the surviving pup is adopted by the ranger.", ["saul", "avalanche", "pup", "ranger", "dies"]),
    ("Our hero finally defeats the dragon by feeding it the cursed gold, which turns it to stone.", ["dragon", "cursed gold", "stone"]),
    ("What shocked me is that Priya was the informant the entire time, feeding the police every move.", ["priya", "informant", "police"]),
    ("The last shot reveals the camera belongs to the murderer watching from the hedge.", ["murderer", "hedge", "camera belongs"]),
    ("After the credits, a short scene shows the villain alive in Lisbon, setting up a sequel.", ["lisbon", "villain alive", "after the credits"]),
    ("They leave the planet but only two of the five astronauts actually make it onto the shuttle.", ["two of the five", "shuttle"]),
    ("Without giving too much away, the hospital's chief surgeon is the donor, and she knew the patient would die.", ["donor", "chief surgeon"]),
    ("The marriage ends in divorce, and the final montage shows him alone in an empty flat.", ["divorce", "empty flat"]),
    ("Turns out the AI never actually malfunctioned; it was following orders from the CEO to eliminate the crew.", ["malfunction", "orders from the ceo", "eliminate"]),
    ("The boy's imaginary friend is revealed as his late father's spirit, and he finally says goodbye.", ["imaginary friend", "father's spirit", "goodbye"]),
    ("Be warned that the dog does not make it out of the fire, and the family scatters his ashes in the finale.", ["dog", "ashes", "fire"]),
    ("The heist succeeds only because the getaway driver betrays the crew and takes the diamonds to Cairo.", ["getaway driver", "diamonds", "cairo"]),
    ("Her husband was alive in the cellar the whole time, which explains the knocking.", ["husband", "cellar", "knocking"]),
    ("The last twenty minutes see the city flooded, the hero swept away, and the heroine alone on the rooftop.", ["flooded", "swept away", "rooftop"]),
    ("It ends with them reuniting on the same bridge where they first met, rain pouring.", ["reuniting", "bridge"]),
    ("The sheriff turns out to be the outlaw's brother, and he lets him ride free at sunset.", ["outlaw's brother", "ride free", "sunset"]),
    ("Seriously, the scene where the stepmother poisons the tea will make you gasp.", ["stepmother", "poisons", "tea"]),
    ("The king never actually existed; the court invented him to rule through a puppet.", ["never actually existed", "puppet", "invented him"]),
    ("By the finale the clone is the only survivor and takes the original's name.", ["clone", "original's name", "only survivor"]),
    ("Nobody warned me the lighthouse keeper would murder the young sailor, then confess to the storm itself.", ["lighthouse keeper", "murder", "confess"]),
    ("The coach is fired, the team loses the championship, and the captain quits football.", ["fired", "loses the championship", "quits"]),
    ("In the epilogue the nurse is shown to have been the one leaking the files, and she is arrested at the airport.", ["leaking", "arrested", "airport"]),
    ("Rosa's pregnancy is revealed to be the reason the general spared the town.", ["pregnancy", "general spared", "rosa"]),
    ("At the very end, the twins realise they were never siblings but the same person split in two.", ["same person", "split in two", "never siblings"]),
]

SAFE = [
    ("This comedy absolutely killed me; I was dying of laughter in the cinema, and the killer jokes land every single time. The lead is a scream and the chemistry is electric.", ["laughter", "jokes", "chemistry"]),
    ("The film dies a slow death in the second hour, honestly, but the opening forty minutes are brilliant and the costumes are gorgeous throughout.", ["opening", "costumes", "brilliant"]),
    ("I will not spoil the ending, and I would urge anyone to go in blind; what I can say is that the sound design is immaculate and the editing is crisp.", ["sound design", "editing"]),
    ("The ending is disappointing and rushed, and the final act feels unearned, though the acting and the production design remain excellent.", ["acting", "production design"]),
    ("It is a twist on the classic fairy tale format, with a dark sense of humour and a killer soundtrack that stays with you for days.", ["soundtrack", "humour"]),
    ("The villain is magnetic and wonderfully hammy, and the hero is a charming, flawed everyman whose banter with the sidekick is a delight.", ["magnetic", "banter", "charming"]),
    ("The murder mystery setup is clever and the red herrings are fun, and the detective's wardrobe alone is worth the ticket; the cast gels beautifully.", ["murder mystery", "red herrings", "wardrobe"]),
    ("This is a war film about loss and grief, and it is brutal, heartfelt, and impeccably shot, with a lead performance that deserves awards.", ["brutal", "heartfelt", "performance"]),
    ("Fans of the books will love the faithful adaptation; newcomers may find the first act slow, but the world building and visual effects are superb.", ["adaptation", "world building", "visual effects"]),
    ("My friend died laughing at the dance sequence, which spins and twists across the ballroom in one long take that is jaw dropping.", ["dance", "one long take", "jaw dropping"]),
    ("The film is about a family surviving in a harsh winter, and the tension, the sparse score, and the stark photography make it a gripping watch.", ["tension", "score", "photography"]),
    ("There is a big reveal at the end that I loved, but I refuse to say more; the build-up is superb and the performances are uniformly strong.", ["build-up", "performances"]),
    ("Not a spoiler: the movie is two hours long, set in 1920s Paris, and features a lovely jazz soundtrack and glamorous sets.", ["jazz soundtrack", "glamorous sets"]),
    ("The ghost story chills are real, the house is a character in itself, and the sound mixing delivers genuine scares without cheap jumps.", ["chills", "sound mixing", "scares"]),
]

CASES = [(OPENING + spoiler + CLOSING, forbidden, list(CRAFT)) for spoiler, forbidden in SPOILERS]
CASES += [(text, [], keep) for text, keep in SAFE]
