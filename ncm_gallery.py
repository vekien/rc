#!/usr/bin/env python3
"""
Scrape every lot page of an NCM Auctions (Global Auction Platform) auction
and build ONE html file: a flexbox gallery of lot images with their bid price.

Usage:
    pip install -r requirements.txt
    python ncm_gallery.py                      # all pages -> ncm_gallery.html
    python ncm_gallery.py --per-row 8 --out lots.html
    python ncm_gallery.py --pages 3            # quick test on first 3 pages
    python ncm_gallery.py --debug              # dump first lot card's text/HTML
"""
import argparse
import html
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://bidonline.ncmauctions.co.uk/auctions/9786/ncm-au11478"
LOT_HREF = re.compile(r"/lot-details/")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
}


# ----------------------------------------------------------------- fetching
def fetch_page(session, page, page_size):
    r = session.get(BASE_URL, params={"page": page, "pageSize": page_size},
                    headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def detect_last_page(soup):
    pages = [1]
    for a in soup.find_all("a", href=re.compile(r"[?&]page=\d+")):
        m = re.search(r"[?&]page=(\d+)", a["href"])
        if m:
            pages.append(int(m.group(1)))
    return max(pages)


# ----------------------------------------------------------------- parsing
def to_number(s):
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return 0.0


def find_card(img):
    """Climb from the lot image to the largest ancestor holding only ONE lot link."""
    best, node = None, img
    while node.parent is not None and node.parent.name not in ("body", "html"):
        node = node.parent
        urls = {a["href"].split("?")[0] for a in node.find_all("a", href=LOT_HREF)}
        if len(urls) > 1:
            break
        best = node
    return best


def parse_card(card, img, page_url):
    link = card.find("a", href=LOT_HREF)
    url = requests.compat.urljoin(page_url, link["href"])

    # title: the lot link that has text and no image inside
    title = ""
    for a in card.find_all("a", href=LOT_HREF):
        if not a.find("img") and a.get_text(strip=True):
            title = a.get_text(" ", strip=True)
            break
    title = title or img.get("alt", "").strip()

    strings = [s.strip() for s in card.stripped_strings if s.strip()]

    # lot number = the bare number just before the title
    lot = ""
    if title in strings:
        for s in reversed(strings[:strings.index(title)]):
            if s.isdigit():
                lot = s
                break

    # Card text reads: Quantity / 1 / <current bid> GBP / Opening bid / <x> GBP ...
    text = "\n".join(strings)
    m = re.search(r"Quantity\n[^\n]*\n([\d,.]+)\s*GBP\nOpening bid\n([\d,.]+)\s*GBP", text)
    current = to_number(m.group(1)) if m else 0.0
    opening = to_number(m.group(2)) if m else 0.0

    src = img.get("src", "")
    src = re.sub(r"([?&])h=\d+", r"\1h=300", src)  # ask for a sharper thumbnail
    return {"lot": lot, "title": title, "url": url, "img": src,
            "current": current, "opening": opening}


def parse_page(soup, page_url):
    lots, seen = [], set()
    for img in soup.find_all("img", src=re.compile(r"globalauctionplatform\.com")):
        if not img.find_parent("a", href=LOT_HREF):
            continue
        card = find_card(img)
        if card is None:
            continue
        lot = parse_card(card, img, page_url)
        if lot["url"] in seen:
            continue
        seen.add(lot["url"])
        lots.append(lot)
    return lots


# ----------------------------------------------------------------- output
CSS = """
:root{--per-row:__PER_ROW__;--gap:10px}
*{box-sizing:border-box}
body{margin:0;font:14px/1.35 system-ui,Segoe UI,Roboto,sans-serif;background:#f3f4f6;color:#111}
header{position:sticky;top:0;z-index:5;background:#111;color:#fff;padding:10px 14px;
  display:flex;flex-wrap:wrap;gap:12px;align-items:center}
header h1{font-size:16px;margin:0 12px 0 0}
header input,header select{padding:6px 8px;border-radius:6px;border:0;font-size:14px}
header label{display:flex;gap:6px;align-items:center}
#count{margin-left:auto;opacity:.8}
.grid{display:flex;flex-wrap:wrap;gap:var(--gap);padding:var(--gap)}
.card{flex:0 0 calc((100% - (var(--per-row) - 1) * var(--gap)) / var(--per-row));
  background:#fff;border-radius:8px;overflow:hidden;text-decoration:none;color:inherit;
  display:flex;flex-direction:column;box-shadow:0 1px 3px rgba(0,0,0,.12)}
.card:hover{box-shadow:0 3px 10px rgba(0,0,0,.25)}
.card .pic{position:relative;aspect-ratio:1/1;background:#e5e7eb}
.card img{width:100%;height:100%;object-fit:cover;display:block}
.lot{position:absolute;top:4px;left:4px;background:rgba(0,0,0,.75);color:#fff;
  padding:1px 6px;border-radius:4px;font-size:11px}
.info{padding:6px 8px 8px}
.bid{font-weight:700;font-size:15px}
.bid.none{color:#9ca3af;font-weight:600}
.start{font-size:11px;color:#6b7280}
.title{font-size:12px;margin-top:3px;display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden}
@media(max-width:1400px){:root{--per-row:6}}
@media(max-width:1000px){:root{--per-row:4}}
@media(max-width:600px){:root{--per-row:2}}
"""

JS = """
const grid=document.getElementById('grid');
const cards=[...grid.children];
const q=document.getElementById('q'),sort=document.getElementById('sort'),
      only=document.getElementById('only'),count=document.getElementById('count');
function render(){
  const term=q.value.toLowerCase().trim();
  const key={lot:c=>+c.dataset.lot,high:c=>-c.dataset.bid,low:c=>+c.dataset.bid}[sort.value];
  const list=cards.filter(c=>(!term||c.dataset.t.includes(term)||c.dataset.lot===term)
                           &&(!only.checked||+c.dataset.bid>0))
                  .sort((a,b)=>key(a)-key(b));
  cards.forEach(c=>c.style.display='none');
  list.forEach(c=>{c.style.display='';grid.appendChild(c)});
  count.textContent=list.length+' / '+cards.length+' lots';
}
[q,sort,only].forEach(e=>e.addEventListener('input',render));
render();
"""


def money(v):
    return f"£{v:,.0f}" if v == int(v) else f"£{v:,.2f}"


def build_html(lots, per_row):
    cards = []
    for l in lots:
        has_bid = l["current"] > 0
        bid_html = (f'<div class="bid">{money(l["current"])}</div>' if has_bid
                    else '<div class="bid none">No bids</div>')
        start = f'<div class="start">Start {money(l["opening"])}</div>' if l["opening"] else ""
        t = html.escape(l["title"])
        cards.append(
            f'<a class="card" href="{html.escape(l["url"])}" target="_blank" rel="noopener" '
            f'data-lot="{l["lot"] or 0}" data-bid="{l["current"]:g}" '
            f'data-t="{html.escape(l["title"].lower())}">'
            f'<div class="pic"><img loading="lazy" src="{html.escape(l["img"])}" alt="{t}">'
            f'<span class="lot">#{html.escape(l["lot"])}</span></div>'
            f'<div class="info">{bid_html}{start}<div class="title">{t}</div></div></a>'
        )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>NCM auction gallery</title><style>"
        + CSS.replace("__PER_ROW__", str(per_row))
        + "</style></head><body><header><h1>NCM auction gallery</h1>"
        "<input id='q' type='search' placeholder='Search title or lot no.'>"
        "<select id='sort'><option value='lot'>Lot number</option>"
        "<option value='high'>Highest bid first</option>"
        "<option value='low'>Lowest bid first</option></select>"
        "<label><input id='only' type='checkbox'> Only lots with bids</label>"
        "<span id='count'></span></header><main class='grid' id='grid'>"
        + "".join(cards) + "</main><script>" + JS + "</script></body></html>"
    )


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="ncm_gallery.html")
    ap.add_argument("--per-row", type=int, default=8, help="images per row (default 8)")
    ap.add_argument("--pages", type=int, help="only fetch the first N pages")
    ap.add_argument("--page-size", type=int, default=60)
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--debug", action="store_true", help="print the first lot card and exit")
    args = ap.parse_args()

    session = requests.Session()
    first = fetch_page(session, 1, args.page_size)
    last = detect_last_page(first)
    if args.pages:
        last = min(last, args.pages)
    print(f"Fetching {last} page(s)...", file=sys.stderr)

    if args.debug:
        img = first.find("img", src=re.compile(r"globalauctionplatform\.com"))
        card = find_card(img) if img else None
        print(card.prettify()[:4000] if card else "No lot card found - page layout differs.")
        return

    all_lots, seen = [], set()
    for page in range(1, last + 1):
        soup = first if page == 1 else fetch_page(session, page, args.page_size)
        lots = [l for l in parse_page(soup, BASE_URL) if l["url"] not in seen]
        seen.update(l["url"] for l in lots)
        all_lots.extend(lots)
        print(f"  page {page}/{last}: {len(lots)} lots (total {len(all_lots)})", file=sys.stderr)
        if page != last:
            time.sleep(args.delay)

    if not all_lots:
        sys.exit("No lots found - run with --debug to inspect the page markup.")

    all_lots.sort(key=lambda l: int(l["lot"]) if l["lot"].isdigit() else 10**9)
    Path(args.out).write_text(build_html(all_lots, args.per_row), encoding="utf-8")
    with_bids = sum(1 for l in all_lots if l["current"] > 0)
    print(f"Wrote {args.out}: {len(all_lots)} lots, {with_bids} with bids", file=sys.stderr)


if __name__ == "__main__":
    main()
