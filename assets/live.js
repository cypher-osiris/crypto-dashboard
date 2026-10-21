/* Live prices in the visitor's browser.
   Coinbase Exchange websocket (ticker+heartbeat) for coins with a "coinbase" product in data/coins.json,
   Kraken v2 websocket for coins with a "kraken" pair (ZBCN). Live.configure(coins) sets the list before start().
   CoinGecko simple/price polling (60s) as a fallback for any coin without a recent websocket tick.
   Emits ticks via Live.on(cb): {id, price, change24, source, ts}. */
(() => {
  "use strict";
  const FEEDS = {
    bitcoin: { coinbase: "BTC-USD" }, ripple: { coinbase: "XRP-USD" }, stellar: { coinbase: "XLM-USD" },
    "hedera-hashgraph": { coinbase: "HBAR-USD" }, axelar: { coinbase: "AXL-USD" }, "zebec-network": { kraken: "ZBCN/USD" },
  };
  const SOURCE_LABEL = { coinbase: "Coinbase", kraken: "Kraken", coingecko: "CoinGecko" };
  const STALE_MS = 120000;       // a coin with no websocket tick yet is polled; CoinGecko values refresh every 60s
  const WATCHDOG_MS = 20000;     // reconnect if a socket is silent this long (both send 1s heartbeats)
  const POLL_MS = 60000;
  const listeners = [];
  const last = {};               // id -> {price, change24, source, ts}
  const conn = { coinbase: "connecting", kraken: "connecting", coingecko: "idle" };
  const statusListeners = [];

  const emit = (t) => { last[t.id] = Object.assign(last[t.id] || {}, t); listeners.forEach((f) => { try { f(t); } catch (e) { console.error(e); } }); };
  const setConn = (k, v) => { if (conn[k] !== v) { conn[k] = v; statusListeners.forEach((f) => f(status())); } };

  function socket(name, url, onOpen, onMsg) {
    let ws, timer, backoff = 1000, lastMsg = 0, closedByUs = false;
    const connect = () => {
      setConn(name, "connecting");
      try { ws = new WebSocket(url); } catch (e) { schedule(); return; }
      ws.onopen = () => { backoff = 1000; lastMsg = Date.now(); onOpen(ws); };
      ws.onmessage = (ev) => { lastMsg = Date.now(); try { onMsg(JSON.parse(ev.data)); } catch (e) { /* ignore malformed */ } };
      ws.onerror = () => setConn(name, "error");
      ws.onclose = () => { setConn(name, "down"); if (!closedByUs) schedule(); closedByUs = false; };
    };
    const schedule = () => { clearTimeout(timer); timer = setTimeout(connect, backoff + Math.random() * 500); backoff = Math.min(backoff * 2, 30000); };
    const restart = () => { if (ws) { closedByUs = true; try { ws.close(); } catch (e) {} } schedule(); };
    setInterval(() => { if (ws && ws.readyState === 1 && Date.now() - lastMsg > WATCHDOG_MS) restart(); }, 5000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden && (!ws || ws.readyState > 1)) { backoff = 1000; connect(); } });
    window.addEventListener("online", () => { backoff = 1000; if (!ws || ws.readyState > 1) connect(); });
    connect();
  }

  function startCoinbase() {
    const products = Object.entries(FEEDS).filter(([, f]) => f.coinbase);
    const byProd = Object.fromEntries(products.map(([id, f]) => [f.coinbase, id]));
    socket("coinbase", "wss://ws-feed.exchange.coinbase.com",
      (ws) => ws.send(JSON.stringify({ type: "subscribe", product_ids: Object.keys(byProd), channels: ["ticker", "heartbeat"] })),
      (m) => {
        if (m.type === "subscriptions") setConn("coinbase", "live");
        if (m.type !== "ticker" || !byProd[m.product_id]) return;
        setConn("coinbase", "live");
        const price = +m.price, open = +m.open_24h;
        emit({ id: byProd[m.product_id], price, change24: open ? (price / open - 1) * 100 : null, source: "coinbase", ts: Date.parse(m.time) || Date.now() });
      });
  }

  function startKraken() {
    const pairs = Object.entries(FEEDS).filter(([, f]) => f.kraken);
    if (!pairs.length) return;
    const bySym = Object.fromEntries(pairs.map(([id, f]) => [f.kraken, id]));
    socket("kraken", "wss://ws.kraken.com/v2",
      (ws) => ws.send(JSON.stringify({ method: "subscribe", params: { channel: "ticker", symbol: Object.keys(bySym) } })),
      (m) => {
        if (m.method === "subscribe" && m.success) setConn("kraken", "live");
        if (m.channel === "heartbeat" || m.channel === "status") { if (conn.kraken === "connecting" && m.channel === "heartbeat") setConn("kraken", "live"); return; }
        if (m.channel !== "ticker") return;
        setConn("kraken", "live");
        for (const d of m.data || []) {
          if (!bySym[d.symbol]) continue;
          emit({ id: bySym[d.symbol], price: +d.last, change24: d.change_pct != null ? +d.change_pct : null, source: "kraken", ts: Date.now() });
        }
      });
  }

  // CoinGecko fallback polling for coins whose websocket ticks are missing/stale.
  async function poll() {
    const now = Date.now();
    // poll a coin if it never got a websocket tick, or its websocket is not currently live
    const wsOf = (id) => (FEEDS[id].coinbase ? "coinbase" : FEEDS[id].kraken ? "kraken" : "none");
    const need = Object.keys(FEEDS).filter((id) => !last[id] || conn[wsOf(id)] !== "live" || (last[id].source === "coingecko" && now - last[id].ts > STALE_MS));
    if (!need.length) { setConn("coingecko", "idle"); return; }
    try {
      const r = await fetch(`https://api.coingecko.com/api/v3/simple/price?ids=${need.join(",")}&vs_currencies=usd&include_24hr_change=true`);
      if (!r.ok) throw new Error(r.status);
      const j = await r.json();
      setConn("coingecko", "polling");
      for (const id of need) if (j[id]) {
        const cur = last[id];
        if (cur && cur.source !== "coingecko" && conn[wsOf(id)] === "live") continue; // ws is delivering
        emit({ id, price: j[id].usd, change24: j[id].usd_24h_change, source: "coingecko", ts: Date.now() });
      }
    } catch (e) { setConn("coingecko", "error"); }
  }

  function status() {
    const now = Date.now();
    const ids = Object.keys(FEEDS);
    const liveIds = ids.filter((id) => last[id] && last[id].source !== "coingecko" && now - last[id].ts < STALE_MS * 5);
    const anyWs = conn.coinbase === "live" || conn.kraken === "live";
    const mode = anyWs ? "live" : Object.values(last).length ? "delayed" : "snapshot";
    return { mode, conn: { ...conn }, liveIds, last: { ...last } };
  }

  window.Live = {
    FEEDS, SOURCE_LABEL,
    configure(list) {
      if (this.started || !Array.isArray(list)) return;
      for (const k of Object.keys(FEEDS)) delete FEEDS[k];
      for (const c of list) { if (c.coinbase) FEEDS[c.id] = { coinbase: c.coinbase }; else if (c.kraken) FEEDS[c.id] = { kraken: c.kraken }; else FEEDS[c.id] = {}; }
    },
    on: (f) => listeners.push(f),
    onStatus: (f) => statusListeners.push(f),
    status, last,
    start() {
      if (this.started) return; this.started = true;
      startCoinbase(); startKraken();
      setTimeout(poll, 8000);                // give websockets a head start
      setInterval(poll, POLL_MS);
    },
  };
})();
