#!/usr/bin/env python3
"""Build assets/groups-map.json for the groups map (groups-map.shtml).

Reads the directory table in uk-groups-directory.shtml and the group pages in
community-pages/, works out a rough point for each area, and writes one entry
per area with every group there. National and online groups have no pin; they
go in a separate list.

Coordinates come from OpenStreetMap's Nominatim, looked up once and cached in
tools/geocode-cache.json (its usage policy: at most one request a second,
results stored, no bulk use). A pin marks the middle of the area a group
covers, not a venue.

Run from the site root after changing the directory or adding a group page:
    python3 tools/build-groups-map.py
"""

import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "tools" / "geocode-cache.json"
OUT = ROOT / "assets" / "groups-map.json"

NATIONAL = {"national", "uk", "united kingdom"}

# Group pages on this site: the area each one is pinned to, or None for a
# national group. A page whose name matches a directory row is merged into it.
PAGES = {
    "big-feelings-enm.shtml": "London",
    "bristol-south-west-polyamory.shtml": "Bristol",
    "east-of-england.shtml": "Cambridgeshire",
    "enm-brighton.shtml": "Brighton",
    "ipswich-poly-munch.shtml": "Ipswich",
    "london-poly-munch.shtml": "London",
    "london-poly-pub.shtml": "London",
    "northampton-polyamory-enm.shtml": "Northampton",
    "polyamory-support-group.shtml": "Birmingham",
    "uk-poly-list.shtml": None,
    "yorkshire-open.shtml": "Yorkshire",
}
SKIP_PAGES = {"index.shtml", "example.shtml"}
# Pages whose group is named differently in the directory.
SAME_AS = {"uk-poly-list.shtml": "UK-Poly mailing list",
           "london-poly-pub.shtml": "London Polyamory Meetup"}

# Areas Nominatim can't place well by name alone.
QUERY = {
    "North East": "North East England",
    "Sussex": "West Sussex",
    "Yorkshire": "North Yorkshire",
    "Scotland": "Perth, Scotland",
}
FIXED = {
    # no single OSM area called South Wales: roughly between Swansea and Cardiff
    "South Wales": (51.62, -3.55),
}


def text(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower().replace("&", "and"))


def directory() -> list[dict]:
    s = (ROOT / "uk-groups-directory.shtml").read_text()
    out = []
    for row in re.findall(r"<tr class=\"border-t[^>]*>(.*?)</tr>", s, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(tds) < 3:
            continue
        a = re.search(r'href="([^"]+)"[^>]*>(.*?)</a>', tds[0], re.S)
        out.append({
            "name": text(a.group(2) if a else tds[0]),
            "url": html.unescape(a.group(1)) if a else None,
            "area": text(tds[1]),
            "format": text(tds[2]),
            "page": None,
        })
    return out


def pages() -> list[dict]:
    out = []
    for f in sorted((ROOT / "community-pages").glob("*.shtml")):
        if f.name in SKIP_PAGES:
            continue
        if f.name not in PAGES:
            sys.exit(f"{f.name}: new group page; add its area to PAGES")
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", f.read_text(), re.S)
        out.append({"name": text(h1.group(1)) if h1 else f.stem,
                    "match": SAME_AS.get(f.name),
                    "page": f"/community-pages/{f.name}",
                    "area": PAGES[f.name]})
    return out


def geocode(area: str, cache: dict) -> tuple[float, float] | None:
    if area in FIXED:
        return FIXED[area]
    if area in cache:
        return tuple(cache[area]) if cache[area] else None
    q = QUERY.get(area, area)
    url = ("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "countrycodes": "gb,ie", "format": "jsonv2", "limit": 1}))
    req = urllib.request.Request(url, headers={"User-Agent": "groups-map-builder/1.0"})
    time.sleep(1.1)
    with urllib.request.urlopen(req, timeout=20) as r:
        hits = json.load(r)
    point = (round(float(hits[0]["lat"]), 4), round(float(hits[0]["lon"]), 4)) if hits else None
    cache[area] = point
    print(f"  looked up {area!r} as {q!r}: {point} "
          f"({hits[0]['display_name'][:60] if hits else 'not found'})")
    return point


def main() -> None:
    groups = directory()
    by_name = {norm(g["name"]): g for g in groups}
    for p in pages():
        # match a page to its directory row by name ("&" and "and" count as
        # the same), or by SAME_AS where the names differ
        match = by_name.get(norm(p["match"] or p["name"]))
        if match:
            match["page"] = p["page"]
        else:
            groups.append({"name": p["name"], "url": None,
                           "area": p["area"] or "National",
                           "format": "", "page": p["page"]})

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    areas: dict[str, dict] = {}
    national = []
    for g in groups:
        entry = {k: g[k] for k in ("name", "url", "format", "page") if g[k]}
        if g["format"] in ("TBD", ""):
            entry.pop("format", None)
        if g["area"].lower() in NATIONAL:
            national.append(entry)
            continue
        point = geocode(g["area"], cache)
        if not point:
            print(f"  no location for {g['name']!r} ({g['area']}): listed as national")
            national.append(entry)
            continue
        a = areas.setdefault(g["area"], {"area": g["area"], "lat": point[0],
                                         "lon": point[1], "groups": []})
        a["groups"].append(entry)
    CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")

    data = {"areas": sorted(areas.values(), key=lambda a: a["area"]),
            "national": national}
    # "updated" is the date the group list last changed, not the date this
    # script last ran: keep the old date if nothing else is different.
    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    old_date = old.pop("updated", None)
    data["updated"] = old_date if old == data and old_date else date.today().isoformat()
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    n = sum(len(a["groups"]) for a in data["areas"])
    print(f"wrote {OUT.relative_to(ROOT)}: {n} groups in {len(data['areas'])} areas, "
          f"{len(national)} national/online")


if __name__ == "__main__":
    main()
