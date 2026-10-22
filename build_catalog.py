"""Build a real, attributed offline catalog without saving original reviews."""

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from movie_source import SourceError, fetch_movie_title
from movie_store import MAX_SAVED_MOVIES, MovieReportStore
from pipeline import analyze_reception
from editorial_writer import write_editorial


CATALOG_TITLES = (
    "Breaking Bad",
    "Inception", "The Dark Knight", "Interstellar (film)", "The Prestige (film)",
    "Dunkirk (2017 film)", "Oppenheimer (film)", "Memento (film)", "Tenet (film)",
    "The Shawshank Redemption", "The Godfather", "The Godfather Part II", "Goodfellas",
    "Pulp Fiction", "Reservoir Dogs", "Inglourious Basterds", "Django Unchained",
    "Once Upon a Time in Hollywood", "Kill Bill: Volume 1", "Fight Club", "Se7en",
    "Zodiac (film)", "The Social Network", "Gone Girl (film)", "The Girl with the Dragon Tattoo (2011 film)",
    "Forrest Gump", "Saving Private Ryan", "Schindler's List", "Jurassic Park (film)",
    "Jaws (film)", "E.T. the Extra-Terrestrial", "Raiders of the Lost Ark", "Catch Me If You Can",
    "The Truman Show", "Eternal Sunshine of the Spotless Mind", "Her (film)", "Lost in Translation (film)",
    "Arrival (film)", "Blade Runner", "Blade Runner 2049", "Dune (2021 film)",
    "Dune: Part Two", "Mad Max: Fury Road", "The Matrix", "Alien (film)",
    "Aliens (film)", "The Terminator", "Terminator 2: Judgment Day", "Back to the Future",
    "Star Wars (film)", "The Empire Strikes Back", "Return of the Jedi", "Rogue One",
    "The Lord of the Rings: The Fellowship of the Ring", "The Lord of the Rings: The Two Towers",
    "The Lord of the Rings: The Return of the King", "Harry Potter and the Philosopher's Stone (film)",
    "Harry Potter and the Prisoner of Azkaban (film)", "Pan's Labyrinth", "The Shape of Water",
    "Everything Everywhere All at Once", "Parasite (2019 film)", "Memories of Murder",
    "The Handmaiden", "Oldboy (2003 film)", "Train to Busan", "Burning (film)",
    "Spirited Away", "Princess Mononoke", "My Neighbor Totoro", "Howl's Moving Castle (film)",
    "Your Name", "A Silent Voice (film)", "Akira (1988 film)", "Grave of the Fireflies",
    "Toy Story", "Toy Story 3", "Finding Nemo", "WALL-E", "Up (2009 film)",
    "Inside Out (2015 film)", "Coco (2017 film)", "Ratatouille (film)",
    "Spider-Man: Into the Spider-Verse", "Spider-Man: Across the Spider-Verse",
    "The Incredibles", "The Lion King (1994 film)", "Shrek", "How to Train Your Dragon (2010 film)",
    "3 Idiots", "Dangal (2016 film)", "Lagaan", "Taare Zameen Par", "PK (film)",
    "Swades", "Dil Chahta Hai", "Zindagi Na Milegi Dobara", "Queen (2013 film)",
    "The Lunchbox", "Andhadhun", "Gully Boy", "Kahaani", "Barfi!", "Piku",
    "RRR", "Baahubali: The Beginning", "Baahubali 2: The Conclusion", "Eega",
    "Drishyam (2013 film)", "Drishyam (2015 film)", "Drishyam 2", "Super Deluxe (film)",
    "Vikram Vedha", "Jai Bhim (film)", "Sita Ramam", "Kantara (film)",
    "The Grand Budapest Hotel", "Moonrise Kingdom", "Fantastic Mr. Fox (film)",
    "Whiplash (2014 film)", "La La Land", "Birdman (film)", "Black Swan (film)",
    "The King's Speech", "The Imitation Game", "A Beautiful Mind (film)",
    "Little Women (2019 film)", "Lady Bird (film)", "Frances Ha", "Marriage Story",
    "Aftersun", "Past Lives (film)", "The Holdovers", "Anatomy of a Fall",
    "Amélie", "Cinema Paradiso", "Life Is Beautiful", "City of God (2002 film)",
    "The Lives of Others", "A Separation", "Roma (2018 film)", "Crouching Tiger, Hidden Dragon",
    "Get Out", "Us (2019 film)", "Nope (film)", "A Quiet Place (film)", "The Babadook",
    "The Witch (2015 film)", "The Lighthouse (2019 film)", "The Shining (film)",
    "The Silence of the Lambs (film)", "The Sixth Sense", "The Others (2001 film)",
    "Knives Out", "Glass Onion: A Knives Out Mystery", "The Nice Guys", "Hot Fuzz",
    "Shaun of the Dead", "Baby Driver", "Scott Pilgrim vs. the World", "Paddington (film)",
    "Paddington 2", "The Iron Giant", "The Wild Robot", "Soul (2020 film)", "Luca (2021 film)",
    "Turning Red", "Moana (2016 film)", "Zootopia", "Frozen (2013 film)",
    "Black Panther (film)", "Iron Man (2008 film)", "The Avengers (2012 film)",
    "Guardians of the Galaxy (film)", "Logan (film)", "Spider-Man 2", "The Batman (film)",
    "Casablanca (film)", "Citizen Kane", "12 Angry Men (1957 film)", "Rear Window",
    "Vertigo (film)", "Psycho (1960 film)", "Singin' in the Rain", "Modern Times (film)",
    "The Departed", "No Country for Old Men", "There Will Be Blood", "Fargo (1996 film)",
    "The Big Lebowski", "Before Sunrise", "Before Sunset", "Before Midnight",
    "Rocky", "Creed (film)", "Ford v Ferrari", "Moneyball (film)", "The Martian (film)",
)


def prepare_report(title):
    movie = fetch_movie_title(title)
    report = analyze_reception(movie["reviews"], title=movie.get("title", ""))
    supported = sum(item["safe_mentions"] > 0 for item in report["aspects"] if item["aspect"] != "ending")
    if supported < 2 or report["overall"]["safe_opinion_sentences"] < 3:
        raise SourceError("Too little spoiler-safe aspect evidence for a useful catalog review.")
    report["movie"] = {"id": movie["id"], "title": movie["title"]}
    report["source"] = movie["source"]
    report["evidence_unit"] = "source passages"
    report["saved"] = True
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    write_editorial(report)
    report["notice"] += " Catalog reports omit story setup entirely for extra spoiler protection."
    return movie["id"], movie["title"], report


def build_catalog(database, limit=100, workers=2, refresh=False, manifest_path=None, titles=CATALOG_TITLES):
    if not 1 <= limit <= MAX_SAVED_MOVIES or not 1 <= workers <= 4:
        raise ValueError("Choose 1-100 movies and 1-4 workers.")
    store = MovieReportStore(database)
    manifest_path = Path(manifest_path or Path(database).with_name("catalog_manifest.json"))
    previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    saved_ids = {item["id"] for item in store.list_reports()}
    entries = {} if refresh else {title: entry for title, entry in previous.get("entries", {}).items() if entry["id"] in saved_ids}
    failures = []
    candidates = iter(titles)

    def checkpoint():
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "requested": limit, "saved_movies": len(saved_ids),
            "entries": entries, "failures": failures,
            "policy": "Real source evidence only. No raw reviews or story setup stored. Direct and Wikipedia-cited sources are distinguished.",
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
        return manifest

    with ThreadPoolExecutor(max_workers=workers) as executor:
        while len(entries) < limit:
            batch = []
            for title in candidates:
                if title in entries and entries[title]["id"] in saved_ids:
                    continue
                entries.pop(title, None)
                batch.append(title)
                if len(batch) >= min(workers, limit - len(entries)):
                    break
            if not batch:
                break
            futures = {executor.submit(prepare_report, title): title for title in batch}
            for future in as_completed(futures):
                title = futures[future]
                try:
                    page_id, display_title, report = future.result()
                    if page_id in {entry["id"] for entry in entries.values()}:
                        continue
                    store.save_report(page_id, display_title, report)
                    saved_ids = {item["id"] for item in store.list_reports()}
                    entries[title] = {"id": page_id, "title": display_title, "direct_review_pages": report["source"].get("direct_review_pages", 0), "citations": len(report["source"].get("citations", []))}
                    print(f"[{len(entries)}/{limit}] Saved {display_title}", flush=True)
                except (SourceError, ValueError, OSError) as error:
                    failures.append({"title": title, "error": str(error)})
                    print(f"Skipped {title}: {error}", flush=True)
                checkpoint()
    return checkpoint()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=os.environ.get("CLEARCUT_REPORT_DB", str(Path(__file__).parent / "data" / "clearcut.sqlite3")))
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--export-seed", help="Export existing safe reports for deployment without fetching sources.")
    arguments = parser.parse_args()
    if arguments.export_seed:
        export_catalog(arguments.database, arguments.export_seed)
        return 0
    manifest = build_catalog(arguments.database, arguments.limit, arguments.workers, arguments.refresh)
    print(f"Catalog complete: {len(manifest['entries'])}/{arguments.limit} collected titles; {manifest['saved_movies']} reports in database.")
    return 0 if len(manifest["entries"]) >= arguments.limit else 1


def export_catalog(database, output_path):
    store = MovieReportStore(database)
    records = [{"id": item["id"], "title": item["title"], "report": store.get_report(item["id"])} for item in store.list_reports()]
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "reports": records}, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"Exported {len(records)} safe reports to {path}.")


if __name__ == "__main__":
    raise SystemExit(main())