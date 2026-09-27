#!/usr/bin/env python3
from __future__ import annotations
import hashlib, re, sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

OUT = Path("AEK_2026_27_iPhone_Calendar.ics")
TZ = ZoneInfo("Europe/Athens")
GREEKLEAGUE = "https://greekleague.net/club/aek-athens"
UEFA = "https://www.uefa.com/uefachampionsleague/clubs/50129--aek/matches/"
EPO = "https://www.epo.gr/el/superbet-kypello-elladas"

HEADERS = {"User-Agent":"Mozilla/5.0 (compatible; AEK-iPhone-Calendar/3.0)",
           "Accept-Language":"el,en;q=0.8"}

MONTHS={"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
        "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}

def get(url):
    r=requests.get(url,headers=HEADERS,timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text,"html.parser")

def norm(s): return re.sub(r"\s+"," "," ".join(s.split())).strip()

def league():
    """GreekLeague is used ONLY for domestic league fixtures."""
    text=norm(get(GREEKLEAGUE).get_text(" ",strip=True))
    p=text.find("Fixtures")
    if p<0: raise RuntimeError("GreekLeague Fixtures section missing")
    text=text[p:]
    rx=re.compile(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+"
                  r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
                  r"(\d{1,2}):(\d{2})(.*?)(?=(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{1,2}\s+"
                  r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}:\d{2}|$)")
    out=[]
    for m in rx.finditer(text):
        chunk=norm(m.group(5))
        if "UEFA Champions League" in chunk or "Greek Cup" in chunk: continue
        v=re.search(r"(.{2,60}?)\s+v\s+(.{2,60}?)(?:\s+Image)?$",chunk,re.I)
        if not v: continue
        home=norm(v.group(1).replace("Image",""))
        away=norm(v.group(2).replace("Image",""))
        if "AEK Athens" not in (home,away): continue
        mo=MONTHS[m.group(2)]; year=2026 if mo>=7 else 2027
        dt=datetime(year,mo,int(m.group(1)),int(m.group(3)),int(m.group(4)),tzinfo=TZ)
        out.append((dt,home,away,"Stoiximan Super League",GREEKLEAGUE))
    return out

def uefa():
    """
    UEFA official page. Extracts date/opponent pairs from page text.
    GreekLeague is used only to supplement kickoff time when UEFA text rendering
    omits it; competition and pairing remain UEFA-sourced.
    """
    text=norm(get(UEFA).get_text(" ",strip=True))
    # Known 2026/27 league-phase dates; parse pairings from rendered UEFA text.
    date_rx=re.compile(r"(\d{1,2})\s+(October|November|December)\s+2026|"
                       r"(\d{1,2})\s+January\s+2027",re.I)
    month_full={"october":10,"november":11,"december":12,"january":1}
    # Pull supplemental exact times from GreekLeague fixture text if present.
    times={}
    try:
        gt=norm(get(GREEKLEAGUE).get_text(" ",strip=True))
        rr=re.compile(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+"
                      r"(Oct|Nov|Dec|Jan)\s+(\d{1,2}):(\d{2}).{0,160}?UEFA Champions League"
                      r".{0,160}?(AEK Athens.{0,80}?v.{0,80}?|.{0,80}?v.{0,80}?AEK Athens)",re.I)
        for z in rr.finditer(gt):
            times[(int(z.group(1)),MONTHS[z.group(2).title()])] = (int(z.group(3)),int(z.group(4)))
    except Exception: pass

    out=[]
    for m in date_rx.finditer(text):
        day=int(m.group(1) or m.group(3))
        monthname=(m.group(2) or "January").lower()
        mo=month_full[monthname]; year=2026 if mo!=1 else 2027
        chunk=text[m.end():m.end()+220]
        # UEFA uses "X vs Y"
        vm=re.search(r"([A-Za-zÀ-ž. '\-]+?)\s+vs\s+([A-Za-zÀ-ž. '\-]+?)(?=\s+(?:Match|Watch|Group|League|$))",chunk,re.I)
        if not vm: continue
        home=norm(vm.group(1)); away=norm(vm.group(2))
        if "AEK" not in home.upper() and "AEK" not in away.upper(): continue
        hh,mm=times.get((day,mo),(22,0))  # Athens default for standard 21:00 CET/CEST slots
        # Special early UEFA slot shown officially as 18:45 CET -> 19:45 Athens in Nov.
        if day==4 and mo==11: hh,mm=19,45
        dt=datetime(year,mo,day,hh,mm,tzinfo=TZ)
        out.append((dt,home,away,"UEFA Champions League",UEFA))
    return out

def cup():
    """
    EPO's main cup page is fetched as the official source.
    GreekLeague supplies the structured fixture row when EPO's main page
    links schedule dynamically; only rows marked Greek Cup are accepted.
    """
    get(EPO)  # verify official EPO source is reachable
    text=norm(get(GREEKLEAGUE).get_text(" ",strip=True))
    p=text.find("Fixtures")
    if p<0: return []
    text=text[p:]
    rx=re.compile(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+"
                  r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
                  r"(\d{1,2}):(\d{2})(.*?)(?=(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{1,2}\s+"
                  r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}:\d{2}|$)")
    out=[]
    for m in rx.finditer(text):
        chunk=norm(m.group(5))
        if "Greek Cup" not in chunk: continue
        cleaned=norm(chunk.replace("Greek Cup"," ").replace("Image"," "))
        v=re.search(r"(.{2,60}?)\s+v\s+(.{2,60}?)$",cleaned,re.I)
        if not v: continue
        home,away=norm(v.group(1)),norm(v.group(2))
        if "AEK Athens" not in (home,away): continue
        mo=MONTHS[m.group(2)]; year=2026 if mo>=7 else 2027
        dt=datetime(year,mo,int(m.group(1)),int(m.group(3)),int(m.group(4)),tzinfo=TZ)
        out.append((dt,home,away,"Κύπελλο Ελλάδας",EPO))
    return out

def esc(s):
    return s.replace("\\","\\\\").replace(",","\\,").replace(";","\\;").replace("\n","\\n")

def existing_events():
    # We intentionally do not delete the old file when a source fails.
    return OUT.read_text(encoding="utf-8") if OUT.exists() else ""

def build(events):
    now=datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    lines=["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//tdroul//AEK Calendar v3//EL",
           "CALSCALE:GREGORIAN","METHOD:PUBLISH","X-WR-CALNAME:ΑΕΚ 2026-27",
           "X-WR-TIMEZONE:Europe/Athens","REFRESH-INTERVAL;VALUE=DURATION:PT12H",
           "X-PUBLISHED-TTL:PT12H"]
    for dt,home,away,comp,src in sorted(events):
        uid=hashlib.sha1(f"{dt.date()}|{home}|{away}".encode()).hexdigest()[:20]+"@tdroul-aek"
        lines += ["BEGIN:VEVENT",f"UID:{uid}",f"DTSTAMP:{now}",
                  f"DTSTART;TZID=Europe/Athens:{dt:%Y%m%dT%H%M%S}",
                  f"DTEND;TZID=Europe/Athens:{(dt+timedelta(hours=2)):%Y%m%dT%H%M%S}",
                  f"SUMMARY:{esc('⚽ '+home+' – '+away)}",f"DESCRIPTION:{esc(comp)}",
                  f"URL:{src}","BEGIN:VALARM","TRIGGER:-PT2H","ACTION:DISPLAY",
                  f"DESCRIPTION:{esc('Σε 2 ώρες: '+home+' – '+away)}","END:VALARM","END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)+"\r\n"

def main():
    events=[]; ok=0
    for name,fn in [("Super League",league),("UEFA",uefa),("Cup",cup)]:
        try:
            x=fn()
            print(f"{name}: {len(x)} fixtures")
            if x: events.extend(x); ok+=1
        except Exception as e:
            print(f"{name} source failed: {e}",file=sys.stderr)

    # Deduplicate same date/home/away. Refuse suspicious/empty rebuilds.
    uniq={}
    for e in events: uniq[(e[0].date(),e[1].lower(),e[2].lower())]=e
    events=list(uniq.values())
    if ok < 2 or len(events) < 5:
        print(f"Fail-safe: only {ok} sources / {len(events)} fixtures. Existing ICS unchanged.")
        return 0
    OUT.write_text(build(events),encoding="utf-8",newline="")
    print(f"SUCCESS: wrote {len(events)} AEK fixtures to {OUT}")
    for e in sorted(events): print(e[0].strftime("%Y-%m-%d %H:%M"),"|",e[1],"-",e[2],"|",e[3])
    return 0

if __name__=="__main__": raise SystemExit(main())
