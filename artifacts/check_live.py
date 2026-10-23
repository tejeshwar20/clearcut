import json
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8080"

request = urllib.request.Request(
    BASE + "/api/analyze",
    data=json.dumps({"reviews": ["The acting is superb. Darth Vader is Luke's father, and that scene still gives me chills. The pacing is tight."]}).encode(),
    headers={"Content-Type": "application/json"},
)
data = json.load(urllib.request.urlopen(request, timeout=60))
print("score-like keys in API response:", [key for key in data if "score" in key.lower()])
print("review:", data["review"])
print("blocked:", data["reader_output"]["blocked"])
html = urllib.request.urlopen(BASE + "/", timeout=10).read().decode()
for name, text in (("html", html), ("app.js", open("static/app.js", encoding="utf-8").read()), ("style.css", open("static/style.css", encoding="utf-8").read())):
    print(f"{name} mentions score:", bool(re.search("score", text, re.I)))
