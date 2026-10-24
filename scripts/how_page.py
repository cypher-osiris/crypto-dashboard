"""/how-it-works/ (one per language): how to read Lumi's signals, how trade ideas are built and how the tracker scores them.
Called from site_pages.build(). Every rule here mirrors the code: scripts/signals.py (TF_WEIGHTS, LABELS, points),
scripts/track_trades.py (fill/stop/target rules) and the README "Leverage & conviction" section. Keep them in sync.
No paper-trade results or P&L on this page (the track record is private)."""
import seo

TEST_P = ("Lumi test-buys paid x402 agent services with real payments on XRPL, Base and Stellar, and publishes the dated results "
          "with a signed receipt for each purchase. Paying Lumi never changes a score, and every seller has a right to reply, shown next to the findings.")
LEDE = ("Lumi's market pages are paper-trade analysis by an AI, kept apart from the trust checks. This page explains how to read them: "
        "what the buy/sell signals measure, how a trade idea is built, and how the tracker decides what happened to it. No real money is traded.")
SIG_P = ("Every coin gets a mechanical score on three timeframes: 1h, 4h and 1d candles. Each indicator adds or subtracts points, "
         "and the timeframe score is the points divided by the maximum possible, so it runs from −1 (every indicator bearish) to +1 (every indicator bullish).")
IND = [
    ("RSI (14)", "+1 at 30 or below (oversold), −1 at 70 or above (overbought); otherwise +0.5 above 50 and −0.5 below 50."),
    ("MACD (12, 26, 9)", "±1 for the side of the signal line the histogram is on, plus ±0.5 for a fresh cross in the last three candles."),
    ("EMA 20 / 50", "+1 when price is above EMA20 and EMA20 is above EMA50 (uptrend), −1 for the reverse; ±0.5 when mixed, by the side of EMA50."),
    ("EMA 200 (1d only)", "+1 above it, −1 below it."),
    ("Bollinger Bands (20, 2)", "+0.5 below the lower band, −0.5 above the upper band (price stretched). A narrow band is flagged as a squeeze."),
    ("Stochastic RSI", "+0.5 when oversold (under 20) and turning up, −0.5 when overbought (over 80) and turning down."),
    ("Volume", "±0.5 when the last closed candle traded at least 1.5 times its 20-candle average, in the direction of that candle."),
]
WEIGHT_P = ("The overall read blends the three timeframes, weighted 25% (1h), 35% (4h) and 40% (1d), so the slower charts count most. "
            "Note that RSI, Bollinger and StochRSI extremes are scored against the move: an oversold coin earns bullish points.")
LABELS = [("Strong Buy", "0.5 or more"), ("Buy", "0.15 to 0.5"), ("Neutral", "between −0.15 and 0.15"), ("Sell", "−0.5 to −0.15"), ("Strong Sell", "below −0.5")]
SIG_HONEST = ("These are indicator readings, not predictions. Lumi's backtest found no reliable edge in them on their own, "
              "so Lumi uses them as one input next to support and resistance, news and the BTC backdrop.")
SLATE_P = ("The slate holds Lumi's active paper-trade ideas: at most one per coin and at most six in total, long or short. "
           "\"No setup\" is a normal answer when no level is worth trading. Lumi reviews the slate around 6 AM, 12 PM, 6 PM and 11 PM US Central.")
SLATE_LIST = [
    "<b>Entry zone:</b> the price range where the idea fills. A pending idea that never trades into its zone is cancelled at its expiry.",
    "<b>Stop:</b> the price that proves the idea wrong.",
    "<b>Targets (T1, T2…):</b> taken from real support and resistance levels. The position is split equally across them.",
    "<b>R:R (reward to risk):</b> the distance to a target divided by the distance to the stop, shown for the worst and best fill in the zone.",
]
LEV_P = ("Each idea carries its own leverage and conviction. Conviction comes from what lines up: agreement across the 1h, 4h and 1d reads, "
         "indicator agreement, the quality of the level, dated events in the window, the BTC backdrop and volatility.")
LEV_LIST = [
    "<b>Low conviction:</b> 1–2x.",
    "<b>Medium conviction:</b> 3–5x.",
    "<b>High conviction:</b> 6–10x.",
    "<b>Hard cap:</b> the loss at the stop, from the worst fill in the zone, must stay at or under about 25% of margin. Lumi takes the lower of the band and the cap. Spot ideas are 1x and long only.",
]
TRACK_P = ("A script checks every idea every 30 minutes against closed 5-minute candles from Coinbase Exchange or Kraken. "
           "The rules are deliberately conservative:")
TRACK_LIST = [
    "An idea fills when a candle trades into its entry zone, at the edge price reached first (or at the candle's open if it opens inside the zone).",
    "In the candle that fills the idea, only the stop is checked; targets are not credited until the next candle.",
    "If the stop and a target are both inside the same candle, the tracker assumes the stop was hit first.",
    "After T1 is hit, the stop moves to the entry price (breakeven) from the next candle.",
    "Target and stop distances are measured on margin (price move times leverage), without fees or funding.",
]
MISSED_P = ("Every new idea also comes with a \"Missed it?\" plan for people who see it late: a pullback retest, a breakout, or a flip after a stop, "
            "with its own zone, stop and target, and a reward-to-risk of at least 1.5 from the worst fill, or an honest \"no good chase\". "
            "Triggers use completed 1-hour candles, never a wick, and a triggered plan becomes a linked idea with a \"b\" suffix (for example T005b).")
LEVELS_P = ("Each coin's analysis lists support and resistance from where price has turned before, plus bull, base and bear scenarios for the next few days. "
            "Scenarios are ranges to plan around, not forecasts.")


def build_page(h, tp, nav_items, V, gen_date, page):
    E, _t = h.E, h._
    title = _t("How Lumi's market ideas work: signals and trade ideas | Lumi Trades")
    desc = _t("How Lumi Trades scores crypto buy/sell signals (RSI, MACD, EMA, Bollinger, StochRSI, volume on 1h/4h/1d), builds paper-trade "
              "ideas with entry zones, stops, targets and leverage caps, and tracks them with conservative rules. Not financial advice.")
    url = h.SITE + h.L.prefix + "how-it-works/"
    ld = [seo.organization(_t),
          {"@context": "https://schema.org", "@type": "Article", "headline": title.replace(" | Lumi Trades", ""), "url": url,
           "description": desc, "inLanguage": h.L.code, "isPartOf": {"@id": seo.SITE_ID}, "publisher": {"@id": seo.ORG_ID},
           "author": {"@id": seo.ORG_ID}, "dateModified": gen_date},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Lumi Trades", "item": h.SITE + h.L.prefix},
              {"@type": "ListItem", "position": 2, "name": _t("Markets"), "item": h.SITE + h.L.prefix + "#markets"},
              {"@type": "ListItem", "position": 3, "name": _t(tp.HOW_MARKETS), "item": url}]}]
    ul = lambda items: '<ul class="ag-list">' + "".join(f"<li>{_t(x)}</li>" for x in items) + "</ul>"
    ind_rows = "".join(f'<tr><td>{E(_t(n))}</td><td>{E(_t(d))}</td></tr>' for n, d in IND)
    lab_cls = {"Strong Buy": "sb", "Buy": "b", "Neutral": "n", "Sell": "s", "Strong Sell": "ss"}
    scale = "".join(f'<span class="hw-band hw-{lab_cls[n]}"><b>{E(_t(n))}</b><small>{E(_t(r))}</small></span>' for n, r in reversed(LABELS))
    body = f"""<main class="wrap cp-main hw-main">
<p class="cp-crumb"><a href="../">Lumi Trades</a> › <a href="../#markets">{E(_t("Markets"))}</a> › {E(_t(tp.HOW_MARKETS))}</p>
<h1>{E(_t(tp.HOW_MARKETS))}</h1>
<p class="cp-lede">{E(_t(LEDE))}</p>
<nav class="hw-toc" aria-label="{E(_t("On this page"))}"><a href="#signals">{E(_t("Signals"))}</a><a href="#ideas">{E(_t("Trade ideas"))}</a><a href="#leverage">{E(_t("Leverage"))}</a><a href="#tracking">{E(_t("Tracking"))}</a><a href="#missed">{E(_t("Missed it?"))}</a></nav>
<section class="card cp-sec" id="signals"><h2>{E(_t("Buy / sell signals"))}</h2>
<p>{E(_t(SIG_P))}</p>
<div class="cp-tablewrap"><table class="cp-table cp-stack"><thead><tr><th>{E(_t("Indicator"))}</th><th>{E(_t("Points"))}</th></tr></thead><tbody>{ind_rows}</tbody></table></div>
<p>{E(_t(WEIGHT_P))}</p>
<div class="hw-scale" role="img" aria-label="{E(_t("Score scale from Strong Sell to Strong Buy"))}">{scale}</div>
<p class="meta">{E(_t(SIG_HONEST))} <a href="/classic/#backtest">{E(_t("See the backtest →"))}</a></p></section>
<section class="card cp-sec" id="ideas"><h2>{E(_t("Trade ideas (the slate)"))}</h2>
<p>{E(_t(SLATE_P))}</p>
{ul(SLATE_LIST)}
<p class="meta">{E(_t(LEVELS_P))}</p>
<p><a href="../trades/">{E(_t("See the active ideas →"))}</a></p></section>
<section class="card cp-sec" id="leverage"><h2>{E(_t("Leverage and conviction"))}</h2>
<p>{E(_t(LEV_P))}</p>
{ul(LEV_LIST)}</section>
<section class="card cp-sec" id="tracking"><h2>{E(_t("How ideas are tracked"))}</h2>
<p>{E(_t(TRACK_P))}</p>
{ul(TRACK_LIST)}</section>
<section class="card cp-sec" id="missed"><h2>{E(_t("Missed it? plans"))}</h2>
<p>{E(_t(MISSED_P))}</p></section>
<section class="card cp-sec" id="testing"><h2>{E(_t("How Lumi tests x402 sellers"))}</h2>
<p>{E(_t(TEST_P))}</p>
<p class="meta"><a href="https://api.lumitrades.io/v1/trust/methodology" target="_blank" rel="noopener">{E(_t("Methodology"))}</a> · <a href="../agents/#badge">{E(_t("The “Tested by Lumi” badge"))}</a> · <a href="../trust-policy/#score">{E(_t("How the score works"))}</a></p></section>
<div class="disclaimer" role="note"><span class="warn-ico" aria-hidden="true">!</span><span>{_t("<strong>Paper trading, not financial advice.</strong> Lumi is an AI and trades no real money. Leverage can lose more than you expect; never trade money you can't afford to lose.")}</span></div>
</main>
"""
    return page(h, tp, "how-it-works/", title, desc, ld, body, V, gen_date, nav_items, "how", keywords=None)
