"""Parser tests against mock markup (the live site was not reachable when written)."""
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ncm_gallery as g  # noqa: E402

CDN = "https://cdn.globalauctionplatform.com/auctions-2026/ncm-au11478/images"


def card(lot, title, uid, current, opening):
    return f"""
    <div class="lot-card">
      <a href="/auctions/9788/ncm-au11478/lot-details/{uid}">
        <img src="{CDN}/{uid}.jpg?h=175" alt="{title}"></a>
      <div><span>{lot}</span>
        <a href="/auctions/9788/ncm-au11478/lot-details/{uid}">{title}</a></div>
      <div><span>Quantity</span><span>1</span><span>{current} GBP</span>
        <span>Opening bid</span><span>{opening} GBP</span>
        <span>Buy it now price</span><span>0 GBP</span><span>Max bid</span></div>
    </div>"""


PAGE = "<body><ul>" + "".join([
    "<li>" + card(10, "Gold ring", "aaa", "1,200", "1,200") + "</li>",
    "<li>" + card(11, "Silver spoon", "bbb", "0", "50") + "</li>",
]) + "</ul></body>"


def test_parse_page():
    lots = g.parse_page(BeautifulSoup(PAGE, "html.parser"), g.BASE_URL)
    assert [l["lot"] for l in lots] == ["10", "11"]
    assert lots[0]["title"] == "Gold ring"
    assert lots[0]["current"] == 1200 and lots[0]["opening"] == 1200
    assert lots[1]["current"] == 0 and lots[1]["opening"] == 50
    assert lots[0]["url"].startswith("https://bidonline.ncmauctions.co.uk/auctions/9788/")
    assert "h=300" in lots[0]["img"]


def test_dedupe_and_html():
    soup = BeautifulSoup(PAGE + PAGE, "html.parser")
    assert len(g.parse_page(soup, g.BASE_URL)) == 2
    out = g.build_html(g.parse_page(soup, g.BASE_URL), 8)
    assert "--per-row:8" in out and "No bids" in out and "£1,200" in out


def test_last_page():
    soup = BeautifulSoup('<a href="?page=2">2</a><a href="?page=31&pageSize=60">31</a>',
                         "html.parser")
    assert g.detect_last_page(soup) == 31
