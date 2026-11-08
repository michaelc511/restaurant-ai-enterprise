# F5: turns each restaurant menu PDF into src/menus/<cuisine>.json for the customer site, so every
# dish, price and policy shown comes straight from domains/restaurant/docs/*.pdf (no hand-typed copy).
# Run from the repo root after a PDF changes:  python web-customer/scripts/build_menus.py
import json
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "domains" / "restaurant" / "docs"
OUT = ROOT / "web-customer" / "src" / "menus"
CUISINES = ("sushi", "steak", "italian")
NAMES = {  # F5: restaurant names exactly as printed at the top of each PDF; the rest of that line is the tagline
    "sushi": "Sakura Sushi & Izakaya Lounge",
    "steak": "Prime & Ember Steakhouse",
    "italian": "Bella Vista Italian Trattoria",
}
SECTION = r"(APPETIZERS|ENTRÉES|DESSERTS|BEVERAGES & DRINKS)(?:\s*\(\d+ Items\))?"
ITEM = r"[●•]\s*(.+?)\s*\(\$([\d,.]+)\)\s*\[([^\]]*)\]\s*-\s*(.+?)(?=\s*[●•]|$)"
INFO_FIELDS = {
    "address": "Address", "hours": "Hours of Operation", "payment": "Accepted Payment Types",
    "reservations": "Reservation Policy", "takeout": "Delivery & Takeout Options",
    "parking": "Parking Information", "dress": "Dining Rules & Dress Code", "alcohol": "Alcohol & Corkage Rules",
}


def _text(pdf: Path) -> str:
    raw = " ".join(re.sub(r"\s+", " ", p.extract_text() or "") for p in PdfReader(pdf).pages)
    return raw.replace("ﬂ", "fl").replace("ﬁ", "fi").strip()


def _info(cuisine: str, head: str) -> dict:
    title_line, rest = head.split("RESTAURANT INFORMATION", 1)
    name = NAMES[cuisine]
    assert title_line.strip().startswith(name), f"{cuisine}: PDF title no longer starts with {name!r}"
    info = {"name": name, "tagline": title_line.strip()[len(name):].strip()}
    for key, label in INFO_FIELDS.items():
        m = re.search(re.escape(label) + r":\s*(.+?)(?=\s*•|$)", rest)
        info[key] = m.group(1).strip() if m else None
    return info


def parse(cuisine: str) -> dict:
    text = _text(DOCS / f"{cuisine}.pdf")
    first = re.search(SECTION, text)
    head, body = text[: first.start()], text[first.start():]
    sections = []
    for m in re.finditer(SECTION + r"(.*?)(?=" + SECTION + r"|$)", body):
        items = [
            {"name": i.group(1).strip(), "price": float(i.group(2).replace(",", "")),
             "tags": [t.strip() for t in re.split(r"[|,]", i.group(3)) if t.strip()],
             "description": i.group(4).strip()}
            for i in re.finditer(ITEM, m.group(2))
        ]
        sections.append({"title": m.group(1).title().replace("&", "&"), "items": items})
    return {"_source": f"Generated from domains/restaurant/docs/{cuisine}.pdf by scripts/build_menus.py (F5)",
            "info": _info(cuisine, head), "sections": sections}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for c in CUISINES:
        data = parse(c)
        (OUT / f"{c}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        counts = {s["title"]: len(s["items"]) for s in data["sections"]}
        print(c, counts, "|", data["info"]["name"], "|", data["info"]["tagline"])
