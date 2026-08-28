#!/usr/bin/env python3
"""Regenerate drama_search_db.json for the DramaLive Android app.

holoduke's own search backend (search_v2/search_v3 and languagepacks/teams_*)
returns empty results, so the app downloads this crawled database instead and
searches it on-device. Re-run this script every few months (or when a new
season starts) and commit the refreshed drama_search_db.json:

    python3 scripts/generate_drama_search_db.py
    git add drama_search_db.json && git commit -m "refresh search db" && git push

Sources (all verified working):
  - leagues: fixtures/feed_appstart.json  (full 180-country directory)
  - teams:   tables/<leagueKey>.json      (standings of every league)
  - players: topscorers/<leagueKey>.json  (top scorers of every league)
"""
import json, time, os, urllib.request, concurrent.futures as cf

UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36"}
B = "https://holoduke.nl/footapi"
OUT = os.path.join(os.path.dirname(__file__), "..", "drama_search_db.json")


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
            return json.load(r)
    except Exception:
        return None


def fetch_table(key):
    d = get(f"{B}/tables/{key}.json?lang=en&version=2800")
    rows = []
    if d:
        for g in d.get("groups", []):
            for t in g.get("teams", []):
                if t.get("id_gs") and t.get("team"):
                    rows.append((str(t["id_gs"]), t["team"]))
    return key, rows


def fetch_scorers(key):
    d = get(f"{B}/topscorers/{key}.json?lang=en&version=2800")
    rows = []
    if d:
        for tour in d.get("tournaments", []):
            for p in tour.get("players", []):
                if p.get("id") and p.get("name"):
                    rows.append((str(p["id"]), p["name"], p.get("team", ""),
                                 str(p.get("team_id_gs", ""))))
    return key, rows


def main():
    t0 = time.time()
    appstart = get(f"{B}/fixtures/feed_appstart.json?usercountrycode=us&lang=en&version=2800")
    leagues = [{"k": l["key"], "n": l["leagueName"], "c": c["country"]}
               for c in appstart.get("countries", []) for l in c.get("leagues", [])]
    keys = [l["k"] for l in leagues]
    country = {l["k"]: l["c"] for l in leagues}
    print(f"leagues: {len(leagues)}")

    teams, players = {}, {}
    with cf.ThreadPoolExecutor(12) as ex:
        for k, rows in ex.map(fetch_table, keys):
            for tid, name in rows:
                teams.setdefault(tid, (name, country.get(k, "")))
    with cf.ThreadPoolExecutor(12) as ex:
        for k, rows in ex.map(fetch_scorers, keys):
            for pid, name, team, teamid in rows:
                players.setdefault(pid, (name, team, teamid))

    db = {
        "generated": time.strftime("%Y-%m-%d"),
        "leagues": leagues,
        "teams": [{"i": i, "n": v[0], "c": v[1]} for i, v in teams.items()],
        "players": [{"i": i, "n": v[0], "t": v[1], "ti": v[2]} for i, v in players.items()],
    }
    raw = json.dumps(db, ensure_ascii=False, separators=(",", ":"))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(raw)
    print(f"teams: {len(teams)}  players: {len(players)}  "
          f"size: {len(raw.encode())//1024} KB  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
