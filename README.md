# NCM auction gallery scraper

Scrapes one NCM Auctions timed auction (`ncm-au11478`, 31 pages, ~1,847 lots) and
writes a single self-contained `ncm_gallery.html`: every lot image in a flexbox
grid (8 per row, dropping to 6/4/2 on narrower screens) with its current bid,
search, sort and an "only lots with bids" filter.

## Run

```
pip install -r requirements.txt
python ncm_gallery.py              # all pages -> ncm_gallery.html
python ncm_gallery.py --pages 3    # quick test
python ncm_gallery.py --debug      # print the first lot card's markup
```

Needs outbound access to `bidonline.ncmauctions.co.uk` and
`cdn.globalauctionplatform.com`. Requests are sequential with a 1s delay.

## Bid parsing (unverified against the live site)

Card text reads `Quantity, <qty>, <n> GBP, Opening bid, <n> GBP, ...`. The first
(unlabelled) figure is treated as the current bid (0 = no bids) and the figure
after `Opening bid` as the start price. If every lot shows 0, the bid is probably
filled in by JavaScript and the scraper needs Playwright instead.

## Tests

`python -m pytest tests` runs the parser against mock markup only.
