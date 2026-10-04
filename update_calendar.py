#!/usr/bin/env python3
"""Download Forex Factory's weekly ICS, keep USD/EUR/JPY red+medium events,
add category + what-to-do notes, write docs/fx.ics for calendar subscription."""
import re, sys, collections, urllib.request
from datetime import datetime, timedelta, timezone

URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.ics"
OUT = "docs/fx.ics"
CUR = {"US": "USD", "EZ": "EUR", "GE": "EUR", "FR": "EUR", "IT": "EUR", "SP": "EUR", "JN": "JPY"}
LABEL = {"US": "USD", "EZ": "EUR", "GE": "EUR Germany", "FR": "EUR France", "IT": "EUR Italy", "SP": "EUR Spain", "JN": "JPY"}
td = lambda m: timedelta(minutes=m)

def load(src):
    if src.startswith("http"):
        req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
        text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    else:
        text = open(src, encoding="utf-8").read()
    return re.sub(r"\r\n[ \t]", "", text)

def parse(text):
    rows = []
    for e in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        summ = re.search(r"SUMMARY:(.*)", e).group(1).strip()
        desc = re.search(r"DESCRIPTION:(.*)", e).group(1)
        imp = re.search(r"Impact: (\w+)", desc)
        st = re.search(r"DTSTART[^:]*:(\d{8}T\d{6})", e)
        m = re.match(r"[^\w]*\s*([A-Z]{2})\s+(.*)", summ)
        if not (imp and st and m): continue
        cc, name = m.group(1), m.group(2).strip()
        if cc not in CUR or imp.group(1) != "High": continue
        fc = re.search(r"Forecast: ([^\\]+)", desc); pv = re.search(r"Previous: ([^\\]+)", desc)
        rows.append(dict(cc=cc, name=name, imp=imp.group(1),
                         t=datetime.strptime(st.group(1), "%Y%m%dT%H%M%S"),
                         fc=fc.group(1).strip() if fc else None, pv=pv.group(1).strip() if pv else None))
    return rows

# (currency, regex on event name, category, min before, min after, moves, what it is, why it matters)
RULES = [
 ("USD", r"fomc.*press conference", 2,5,20,"ZN, NQ, ES","The Fed Chair's press conference after the rate decision.","Answers to questions can reverse the 2:00 PM move. Stay flat or very small."),
 ("USD", r"federal funds|fomc statement|economic projections", 1,10,10,"ZN, NQ, ES","The Fed's interest rate decision and statement (quarterly meetings also include the dot plot).","The biggest scheduled event of the cycle. It sets rate expectations for everything, so ZN, NQ and ES all move hard."),
 ("USD", r"minutes", 1,10,10,"ZN, NQ","Notes from the previous Fed meeting. Not a new decision.","Can shift rate expectations if the tone differs from the statement. Usually smaller than a decision."),
 ("USD", r"chair|powell|testif|jackson hole|semiannual", 2,5,30,"ZN, NQ, ES","A speech or testimony from the Fed Chair.","The Chair can hint at rate changes. Moves can come at any point in the speech, so the window is longer."),
 ("USD", r"speaks|speech|trump|bessent|treasury sec|tariff", 2,5,20,"NQ, ES, ZN","A speech or remarks from a senior official.","Headlines can spike NQ and ES with no warning (rates, tariffs, trade). Timing is loose, so be careful for the whole speech."),
 ("USD", r"non-farm|average hourly|unemployment rate|employment cost", 1,10,10,"ZN, NQ, ES","The monthly jobs report (payrolls, wages, unemployment rate) or the quarterly Employment Cost Index.","Jobs and wages drive Fed rate expectations. Fast spike and reversal in the first minutes while the liquidity gap fills."),
 ("USD", r"adp", 3,0,0,"ZN","ADP private payrolls, a preview of the official jobs report.","Moves ZN a little, but it is not the official number."),
 ("USD", r"pce|deflator", 1,10,10,"ZN, NQ","PCE inflation, the Fed's preferred inflation gauge.","Hotter than forecast = yields up (ZN down), NQ pressured. Cooler = the reverse."),
 ("USD", r"cpi|ppi", 1,10,10,"ZN, NQ, ES","Consumer (CPI) or producer (PPI) inflation.","Hotter than forecast = yields up (ZN down), NQ hit hardest, ES follows. Whipsaw in the first minutes."),
 ("USD", r"gdp", 1,10,10,"ES, NQ, ZN","A GDP estimate (economic growth). The advance estimate matters most; later ones are revisions.","Shows if growth is strong or weak, which feeds rate expectations."),
 ("USD", r"retail sales", 1,10,10,"ZN, ES, NQ","Monthly consumer spending.","Strong spending can push yields up and shift rate expectations."),
 ("USD", r"durable goods|trade balance|philly|empire|housing starts|building permits|industrial production|import prices|productivity", 1,10,10,"ZN, ES","US economic data released at 8:30 AM ET.","Red-rated by Forex Factory, so it can move yields. Treated like other 8:30 data."),
 ("USD", r"ism|pmi|consumer confidence|sentiment|jolts|home sales|new home|pending home|beige book|factory orders", 3,0,0,"ES, NQ","A business or consumer survey, or a job-openings report.","Usually a smaller move than the 8:30 data, but it can spike for a few minutes."),
 ("USD", r"auction", 3,0,0,"ZN","A Treasury bond auction.","Weak demand can move Treasury yields, so ZN, at 1:00 PM ET."),
 ("EUR", r"main refinancing|deposit facility|monetary policy statement|rate decision", 2,5,15,"ZN, ES","The ECB's interest rate decision and statement.","Moves European yields, which spill into ZN and ES. Matches your 8:10 to 8:30 rule for an 8:15 release."),
 ("EUR", r"press conference", 2,5,15,"ZN, ES","The ECB President's press conference after the decision.","Can move markets again about 30 minutes after the decision."),
 ("EUR", r"lagarde|ecb president|ecb.*speaks|guindos|schnabel|lane|ecb", 2,5,15,"ZN, ES","A speech from the ECB President or board member.","Can hint at rate changes. Caution while it runs."),
 ("EUR", r"cpi|inflation", 3,0,0,"ZN","Euro area or national inflation (usually released around 5:00 AM ET).","Feeds ECB rate expectations. Be careful holding ZN overnight or premarket."),
 ("EUR", r".", 3,0,0,"ZN, ES","A euro-area economic report (growth, PMI, sentiment or jobs).","Red-rated, so it can move the euro and, a little, ZN and ES. Be aware only."),
 ("JPY", r"policy rate|monetary policy statement|outlook report|rate decision", 2,30,90,"ZN, NQ","The Bank of Japan's rate decision and statement (the Outlook Report comes at quarterly meetings).","Lands overnight in ET, so liquidity is thinner. The exact minute varies, so the window is wide."),
 ("JPY", r"press conference", 2,15,45,"ZN, NQ","The BOJ Governor's press conference after the decision.","Tone on future rate hikes can move the yen, ZN and NQ again."),
 ("JPY", r"ueda|boj gov|boj.*speaks|finance minister|intervention|minister", 2,15,45,"ZN, NQ","Remarks from the BOJ Governor or Japan's finance officials.","Hints about policy or yen intervention can move the yen and spill into ZN and NQ."),
 ("JPY", r".", 3,0,0,"ZN","A Japan economic report (inflation, growth, Tankan, trade or jobs).","Moves the yen, with little effect on NQ, ES and ZN. Be aware only."),
]

def classify(r):  # -> (category, minutes before, minutes after, moves, what, why)
    cur, n, hi = CUR[r["cc"]], r["name"].lower(), r["imp"] == "High"
    for c, pat, cat, pre, post, moves, what, why in RULES:
        if c == cur and re.search(pat, n): return (cat, pre, post, moves, what, why)
    # US red event we have no rule for: safest default
    return (1,10,10,"ZN, NQ, ES","A US event Forex Factory rates red that is not in the rule list.","Default rule: flat 10 minutes before to 10 minutes after, until you decide otherwise.")

def esc(s): return s.replace("\\","\\\\").replace(",","\\,").replace(";","\\;").replace("\n","\\n")
def fold(l):
    b = l.encode(); out = []; first = True
    while len(b) > (75 if first else 74):
        n = 75 if first else 74
        while (b[n] & 0xC0) == 0x80: n -= 1
        out.append(b[:n].decode()); b = b[n:]; first = False
    out.append(b.decode()); return "\r\n ".join(out)

def build(rows):
    F = lambda d: d.strftime("%Y%m%dT%H%M%S"); tf = lambda d: d.strftime("%-I:%M %p") + " ET"
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    L = ["BEGIN:VCALENDAR","PRODID:-//FX Events + What To Do//EN","VERSION:2.0","CALSCALE:GREGORIAN",
         "X-WR-CALNAME:FX Events + What To Do","X-WR-TIMEZONE:America/New_York",
         "REFRESH-INTERVAL;VALUE=DURATION:PT1H","X-PUBLISHED-TTL:PT1H",
         "BEGIN:VTIMEZONE","TZID:America/New_York",
         "BEGIN:DAYLIGHT","TZOFFSETFROM:-0500","TZOFFSETTO:-0400","TZNAME:EDT","DTSTART:19700308T020000","RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU","END:DAYLIGHT",
         "BEGIN:STANDARD","TZOFFSETFROM:-0400","TZOFFSETTO:-0500","TZNAME:EST","DTSTART:19701101T020000","RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU","END:STANDARD","END:VTIMEZONE"]
    for r in rows: r["cat"], r["pre"], r["post"], r["moves"], r["what"], r["why"] = classify(r)
    groups = collections.OrderedDict()
    for r in sorted(rows, key=lambda r: (r["t"], r["cc"])): groups.setdefault((r["cc"], r["t"], r["cat"]), []).append(r)
    LAB = {1:"NO TRADE", 2:"CAUTION", 3:"AWARE"}
    HEAD = {1:"CATEGORY 1 - DO NOT TRADE", 2:"CATEGORY 2 - PROCEED WITH CAUTION", 3:"CATEGORY 3 - SAFE TO TRADE, BE AWARE"}
    for (cc, t0, cat), g in groups.items():
        pre, post = max(x["pre"] for x in g), max(x["post"] for x in g)
        s, e = (t0 - td(pre), t0 + td(post)) if cat < 3 else (t0, t0 + td(10))
        title = f"{LAB[cat]} | {LABEL[cc]} " + ", ".join(x["name"] for x in g)
        d = [HEAD[cat], "", f"Release: {tf(t0)}"]
        if cat == 1: d += [f"Cancel bracket orders. Be 100% flat in NQ, ES and ZN by {tf(s)}.", f"Do not trade again until {tf(e)}."]
        elif cat == 2: d += [f"Be flat from {tf(s)} to {tf(e)}, then trade smaller until the move settles."]
        else: d += ["No flat window. Expect a volatility burst at the release."]
        d.append("")
        for x in g:
            d.append(f"{x['name']}")
            d.append(f"WHAT IT IS: {x['what']}")
            d.append(f"WHY IT MATTERS: {x['why']}")
            if x["fc"] or x["pv"]: d.append(f"Forecast {x['fc'] or 'n/a'}, Previous {x['pv'] or 'n/a'}")
            d.append("")
        d += ["Moves: " + ", ".join(dict.fromkeys(m.strip() for x in g for m in x["moves"].split(",")))]
        L += ["BEGIN:VEVENT", f"UID:fx-{cc}-{F(t0)}-{cat}@fxcalendar", f"DTSTAMP:{now}",
              f"DTSTART;TZID=America/New_York:{F(s)}", f"DTEND;TZID=America/New_York:{F(e)}",
              "SUMMARY:" + esc(title), "DESCRIPTION:" + esc("\n".join(d)),
              "BEGIN:VALARM","ACTION:DISPLAY","DESCRIPTION:" + esc(title), "TRIGGER:" + ("-PT15M" if cat < 3 else "-PT5M"), "END:VALARM", "END:VEVENT"]
    L.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in L) + "\r\n", len(groups)

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else URL
    out = sys.argv[2] if len(sys.argv) > 2 else OUT
    rows = parse(load(src))
    text, n = build(rows)
    import os; os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    open(out, "w", encoding="utf-8", newline="").write(text)
    print(f"{len(rows)} source events -> {n} calendar events -> {out}")
