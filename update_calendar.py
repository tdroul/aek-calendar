#!/usr/bin/env python3
"""
AEK Calendar updater.
Primary source: official AEK FC match-schedule page.
Safety rule: never overwrite the existing .ics unless valid AEK match data
can be extracted.
"""
from __future__ import annotations
import re, sys, html, hashlib
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SOURCE = "https://www.aekfc.gr/?iid=43306&lang=el&path=-1449899271"
OUT = Path("AEK_2026_27_iPhone_Calendar.ics")
ATHENS = ZoneInfo("Europe/Athens")

MONTHS = {
    "ΙΑΝ":1,"ΙΑΝΟΥΑΡΙ":1,"ΦΕΒ":2,"ΦΕΒΡΟΥΑΡΙ":2,"ΜΑΡ":3,"ΜΑΡΤΙΟΥ":3,
    "ΑΠΡ":4,"ΑΠΡΙΛΙΟΥ":4,"ΜΑΙ":5,"ΜΑΪ":5,"ΜΑΙΟΥ":5,"ΜΑΪΟΥ":5,
    "ΙΟΥΝ":6,"ΙΟΥΝΙΟΥ":6,"ΙΟΥΛ":7,"ΙΟΥΛΙΟΥ":7,"ΑΥΓ":8,"ΑΥΓΟΥΣΤΟΥ":8,
    "ΣΕΠ":9,"ΣΕΠΤΕΜΒΡΙΟΥ":9,"ΟΚΤ":10,"ΟΚΤΩΒΡΙΟΥ":10,
    "ΝΟΕ":11,"ΝΟΕΜΒΡΙΟΥ":11,"ΔΕΚ":12,"ΔΕΚΕΜΒΡΙΟΥ":12,
}

def fetch(url: str) -> str:
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AEKCalendar/1.0; +https://github.com/tdroul/aek-calendar)",
        "Accept-Language": "el-GR,el;q=0.9,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml",
    })
    with urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def clean(raw: str) -> str:
    raw = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I|re.S)
    raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.I|re.S)
    raw = re.sub(r"<[^>]+>", "\n", raw)
    raw = html.unescape(raw).replace("\xa0", " ")
    return "\n".join(x.strip() for x in raw.splitlines() if x.strip())

def normalize_team(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip(" -–—|")
    return s

def parse_matches(text: str):
    """
    The AEK page renders match cards server-side/client-side depending on request.
    This parser accepts common Greek date/time + 'TEAM - TEAM' card layouts.
    It deliberately rejects uncertain rows.
    """
    t = text.upper()
    # Flatten nearby card text while retaining separators.
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    matches = []
    current_year = datetime.now(ATHENS).year

    date_patterns = [
        re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b"),
        re.compile(r"\b(\d{1,2})\s+([Α-ΩΪΫΆΈΉΊΌΎΏA-Z]+)\s+(20\d{2})\b", re.I),
    ]
    time_re = re.compile(r"\b([01]?\d|2[0-3])[:.](\d{2})\b")
    scoreish = re.compile(r"^\d+\s*[-–]\s*\d+$")
    team_re = re.compile(r"^(.{2,45}?)\s+[-–—]\s+(.{2,45}?)$")

    for i, line in enumerate(lines):
        dt = None
        for p in date_patterns:
            m = p.search(line.upper())
            if not m: continue
            if p is date_patterns[0]:
                d, mo, y = map(int, m.groups())
            else:
                d, mon, y = m.groups()
                key = mon.upper().rstrip(".")
                mo = MONTHS.get(key) or next((v for k,v in MONTHS.items() if key.startswith(k)), None)
                if not mo: continue
                d, y = int(d), int(y)
            dt = (y, mo, d)
            break
        if not dt:
            continue

        window = lines[max(0,i-4):min(len(lines),i+10)]
        tm = None
        teams = None
        competition = "AEK FC"
        for w in window:
            mt = time_re.search(w)
            if mt and not tm:
                tm = (int(mt.group(1)), int(mt.group(2)))
            mm = team_re.match(w)
            if mm and not scoreish.match(w):
                a,b = normalize_team(mm.group(1)), normalize_team(mm.group(2))
                if "ΑΕΚ" in (a+" "+b).upper() or "AEK" in (a+" "+b).upper():
                    teams = (a,b)
            wu = w.upper()
            if "CHAMPIONS" in wu: competition = "UEFA Champions League"
            elif "ΚΥΠΕΛ" in wu: competition = "Κύπελλο Ελλάδας"
            elif "SUPER" in wu or "ΠΡΩΤΑΘΛ" in wu: competition = "Stoiximan Super League"

        if tm and teams:
            y,mo,d = dt
            try:
                start = datetime(y,mo,d,tm[0],tm[1],tzinfo=ATHENS)
            except ValueError:
                continue
            matches.append((start, teams[0], teams[1], competition))

    # de-duplicate
    unique = {}
    for m in matches:
        unique[(m[0],m[1],m[2])] = m
    return sorted(unique.values())

def esc(s: str) -> str:
    return s.replace("\\","\\\\").replace(",","\\,").replace(";","\\;").replace("\n","\\n")

def build_ics(matches):
    now = datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    out = [
        "BEGIN:VCALENDAR","VERSION:2.0",
        "PRODID:-//tdroul//AEK Calendar//EL",
        "CALSCALE:GREGORIAN","METHOD:PUBLISH",
        "X-WR-CALNAME:ΑΕΚ 2026-27","X-WR-TIMEZONE:Europe/Athens",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for start,a,b,comp in matches:
        uid = hashlib.sha1(f"{start.date()}|{a}|{b}".encode()).hexdigest()[:20] + "@tdroul-aek"
        end = start + timedelta(hours=2)
        title = f"⚽ {a} – {b}"
        out += [
            "BEGIN:VEVENT",f"UID:{uid}",f"DTSTAMP:{now}",
            f"DTSTART;TZID=Europe/Athens:{start:%Y%m%dT%H%M%S}",
            f"DTEND;TZID=Europe/Athens:{end:%Y%m%dT%H%M%S}",
            f"SUMMARY:{esc(title)}",f"DESCRIPTION:{esc(comp)}",
            f"URL:{SOURCE}",
            "BEGIN:VALARM","TRIGGER:-PT2H","ACTION:DISPLAY",
            f"DESCRIPTION:{esc('Σε 2 ώρες: '+a+' – '+b)}","END:VALARM","END:VEVENT"
        ]
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"

def main():
    try:
        page = fetch(SOURCE)
        text = clean(page)
        matches = parse_matches(text)
    except Exception as e:
        print(f"AEKFC fetch failed: {e}", file=sys.stderr)
        print("Keeping existing calendar unchanged.", file=sys.stderr)
        return 0

    # Safety: a valid schedule page should yield multiple AEK fixtures.
    if len(matches) < 3:
        print(f"Only {len(matches)} valid matches found; refusing to overwrite {OUT}.", file=sys.stderr)
        print("AEKFC may have changed markup or blocked automated access.", file=sys.stderr)
        return 0

    OUT.write_text(build_ics(matches), encoding="utf-8", newline="")
    print(f"Updated {OUT} with {len(matches)} matches from official AEK FC.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
