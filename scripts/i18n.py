#!/usr/bin/env python3
"""Translations for Lumi Trades (stdlib only). English is the source language and the default at /.

Strings live in assets/i18n/<lang>.json, keyed by the ENGLISH text itself (gettext style):
  {"_meta": {...language name, locale, date formats...},
   "ui":    {"English text": "translation", ...},   # browser strings (assets/*.js) + shared ones (signal states, statuses)
   "pages": {"English text": "translation", ...}}  # static-page strings (build_pages.py, trade_pages.py, index.html)
Placeholders use {name} and must be kept as-is. A missing key falls back to the English text.

  python3 scripts/i18n.py check [lang]   # list missing / unused keys per language (exit 1 if any are missing)
  python3 scripts/i18n.py bundle         # rewrite assets/i18n/<lang>.js (window.LUMI_I18N) from the JSON

build_pages.py imports this module, renders every page once per language (English at /, others under /<lang>/),
and calls bundle() so the browser bundles never drift from the JSON.
"""
import ast, datetime as dt, html, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "assets", "i18n")
SITE = "https://lumitrades.io/"
ORDER = ["en", "es", "pt", "tr", "ko", "ja"]  # switcher + hreflang order; a language is live once its JSON exists
EN_META = {"name": "English", "locale": "en-US", "og_locale": "en_US", "short": "EN"}
MON_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def codes():
    return ["en"] + [c for c in ORDER[1:] if os.path.exists(os.path.join(DIR, f"{c}.json"))]


class Lang:
    def __init__(self, code):
        self.code = code
        self.en = code == "en"
        self.prefix = "" if self.en else f"{code}/"
        self.missing = set()
        self.used = set()
        if self.en:
            self.meta, self.ui, self.pages = dict(EN_META), {}, {}
        else:
            with open(os.path.join(DIR, f"{code}.json"), encoding="utf-8") as f:
                d = json.load(f)
            self.meta, self.ui, self.pages = d.get("_meta", {}), d.get("ui", {}), d.get("pages", {})
        self.s = {**self.ui, **self.pages}

    # ---- strings ----
    def t(self, _key, **kw):
        s = str(_key)
        if not self.en:
            self.used.add(s)
            if s in self.s and self.s[s]:
                s = self.s[s]
            elif s.strip():
                self.missing.add(s)
        return s.format(**kw) if kw else s

    def has(self, s):
        return self.en or bool(self.s.get(str(s)))

    def opt(self, s):
        """Translate when a translation exists, else return the English text without recording a miss (free text)."""
        return self.s.get(str(s)) or str(s) if not self.en else str(s)

    def state(self, s):
        """Signal states like 'lower half · squeeze': translate each ' · ' part."""
        return " · ".join(self.t(p) for p in str(s or "").split(" · ")) if s else ""

    def loc(self, obj, field, default=""):
        """Free text from data/*.json: an optional per-language override obj["i18n"][lang][field], else the English
        value. Returns (text, is_english) so callers can mark untranslated text with lang="en"."""
        obj = obj or {}
        if not self.en:
            o = ((obj.get("i18n") or {}).get(self.code) or {}).get(field)
            if o:
                return o, False
        v = obj.get(field)
        if not self.en and isinstance(v, str) and self.s.get(v):  # fixed text the scripts write (e.g. a stats note) that has a translation
            return self.s[v], False
        return (v if v is not None else default), (not self.en and bool(v))

    def free(self, obj, field, E, default="", tag="span", cls=""):
        """Escaped free text; untranslated English on a non-English page is wrapped in lang="en" with the .i18n-en marker."""
        txt, en = self.loc(obj, field, default)
        if not txt:
            return ""
        return f'<{tag} lang="en" class="i18n-en{(" " + cls) if cls else ""}">{E(txt)}</{tag}>' if en else (
            f'<{tag} class="{cls}">{E(txt)}</{tag}>' if cls else E(txt))

    # ---- dates (US Central, like the English site) ----
    def date(self, t, with_time=True):
        if self.en:
            s = t.strftime("%b %-d, %Y")
            return s + t.strftime(", %-I:%M %p ") + t.tzname() if with_time else s
        m = self.meta
        mon = (m.get("months") or MON_EN)[t.month - 1]
        s = m.get("date", "{d} {mon} {y}").format(d=t.day, m=t.month, y=t.year, mon=mon)
        if not with_time:
            return s
        return m.get("datetime", "{date}, {time} {tz}").format(date=s, time=f"{t.hour}:{t.minute:02d}", tz=t.tzname())

    def day(self, t):
        """Short axis label without the year."""
        if self.en:
            return t.strftime("%b %-d")
        m = self.meta
        mon = (m.get("months") or MON_EN)[t.month - 1]
        return m.get("day", "{d} {mon}").format(d=t.day, m=t.month, mon=mon)

    def dayhour(self, t):
        if self.en:
            return t.strftime("%b %-d %-I%p").replace("AM", "a").replace("PM", "p")
        return f"{self.day(t)} {t.hour}h" if self.code not in ("ko", "ja") else f"{self.day(t)} {t.hour}{'시' if self.code == 'ko' else '時'}"


def all_langs():
    return [Lang(c) for c in codes()]


# ---------- links between language versions ----------
def rel(from_path, to_path):
    """Relative href from page `from_path` (e.g. 'es/xrp/') to `to_path` (e.g. 'pt/xrp/'); '' = site root."""
    depth = from_path.count("/")
    return ("../" * depth + to_path) or "./"


def alternates(path, langs):
    """<link rel=alternate hreflang> tags for a page at `path` (relative to a language root, '' = home)."""
    out = [f'<link rel="alternate" hreflang="{L.code}" href="{SITE}{L.prefix}{path}">' for L in langs]
    out.append(f'<link rel="alternate" hreflang="x-default" href="{SITE}{path}">')
    return "\n".join(out)


GLOBE = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm6.9 6h-2.9a15.7 15.7 0 0 0-1.4-3.6A8 8 0 0 1 18.9 8zM12 4c.8 1.2 1.5 2.5 1.9 4h-3.8c.4-1.5 1.1-2.8 1.9-4zM4.3 14a8.2 8.2 0 0 1 0-4h3.4a16.5 16.5 0 0 0 0 4zm.8 2h2.9a15.7 15.7 0 0 0 1.4 3.6A8 8 0 0 1 5.1 16zM8 8H5.1a8 8 0 0 1 4.3-3.6A15.7 15.7 0 0 0 8 8zm4 12c-.8-1.2-1.5-2.5-1.9-4h3.8c-.4 1.5-1.1 2.8-1.9 4zm2.3-6H9.7a14.7 14.7 0 0 1 0-4h4.6a14.7 14.7 0 0 1 0 4zm.3 5.6a15.7 15.7 0 0 0 1.4-3.6h2.9a8 8 0 0 1-4.3 3.6zm1.7-5.6a16.5 16.5 0 0 0 0-4h3.4a8.2 8.2 0 0 1 0 4z"/></svg>')


def switcher(L, path, langs):
    """Static language menu (works without JS); assets/i18n.js remembers the choice in localStorage."""
    here = L.prefix + path
    items = "".join(
        f'<li><a href="{rel(here, x.prefix + path)}" hreflang="{x.code}" lang="{x.code}" data-lang="{x.code}"'
        f'{" aria-current=\"true\"" if x.code == L.code else ""}>{html.escape(x.meta.get("name", x.code))}</a></li>' for x in langs)
    label = L.t("Language")
    return (f'<details class="lang-menu"><summary aria-label="{html.escape(label)}: {html.escape(L.meta.get("name", ""))}">{GLOBE}'
            f'<span>{html.escape(L.meta.get("short", L.code.upper()))}</span></summary><ul>{items}</ul></details>')


# ---------- index.html (hand-written English shell) -> /<lang>/index.html ----------
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr", "path", "circle", "rect", "line", "stop"}
ATTRS = ("aria-label", "placeholder", "title", "alt")
TOK = re.compile(r"(<!--.*?-->|<script\b.*?</script>|<style\b.*?</style>|<[^>]+>)", re.S)


def _norm(s):
    return re.sub(r"\s+", " ", s).strip()


def translate_html(src, L):
    """Translate a fragment of the English shell: elements marked data-i18n (inner HTML = key), every other text node,
    and aria-label/placeholder/title/alt attributes. Script/style/comments are left alone."""
    toks = TOK.split(src)
    out, i = [], 0

    def attr_tr(tag):
        def rep(m):
            v = html.unescape(m.group(2))
            return f'{m.group(1)}="{html.escape(L.t(v), quote=True)}"' if v.strip() else m.group(0)
        return re.sub(r'\b(' + "|".join(ATTRS) + r')="([^"]*)"', rep, tag)

    while i < len(toks):
        tk = toks[i]
        if tk.startswith("<!--") or tk.startswith("<script") or tk.startswith("<style"):
            out.append(tk); i += 1; continue
        if tk.startswith("<"):
            m = re.match(r"<([a-zA-Z0-9]+)", tk)
            if m and " data-i18n" in tk and not tk.startswith("</"):
                name = m.group(1).lower()
                depth, j = 1, i + 1
                while j < len(toks) and depth:
                    x = toks[j]
                    mm = re.match(r"<(/?)([a-zA-Z0-9]+)", x)
                    if mm and mm.group(2).lower() == name and not x.endswith("/>"):
                        depth += -1 if mm.group(1) else 1
                    j += 1
                inner = "".join(toks[i + 1:j - 1])
                out.append(attr_tr(tk).replace(" data-i18n", "", 1))
                out.append(L.t(_norm(inner)))
                out.append(toks[j - 1])
                i = j
                continue
            out.append(attr_tr(tk)); i += 1; continue
        # text node
        core = tk.strip()
        if core and re.search(r"[A-Za-z]{2}", core):
            lead, trail = tk[:len(tk) - len(tk.lstrip())], tk[len(tk.rstrip()):]
            key = _norm(html.unescape(core))
            tr = key if key in NO_TR else L.t(key)
            out.append(lead + (core if tr == key else html.escape(tr, quote=False)) + trail)
        else:
            out.append(tk)
        i += 1
    return "".join(out)


NO_TR = {"Lumi Trades",  "RSI", "MACD", "EMA", "BTC"}


def bundle(langs=None):
    """assets/i18n/<lang>.js = the 'ui' strings for the browser (window.LUMI_I18N), plus the short 'pages' words
    (statuses, directions, labels...) that the scripts can also show from data."""
    changed = []
    for L in langs or all_langs():
        if L.en:
            continue
        js = ("/* GENERATED by scripts/i18n.py from assets/i18n/" + L.code + ".json; edit the JSON, not this file. */\n"
              "window.LUMI_I18N=" + json.dumps({"lang": L.code, "locale": L.meta.get("locale", L.code), "strings": {**{k: v for k, v in L.pages.items() if len(k) <= 30}, **L.ui}},
                                               ensure_ascii=False, separators=(",", ":")) + ";\n")
        p = os.path.join(DIR, f"{L.code}.js")
        old = open(p, encoding="utf-8").read() if os.path.exists(p) else None
        if old != js:
            with open(p, "w", encoding="utf-8") as f:
                f.write(js)
            changed.append(os.path.relpath(p, ROOT))
    return changed


# ---------- keys used in the code (for `check`) ----------
_LIT = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _tr_literals(src, call=r"\btr\(", py=False):
    """String literals that are the first argument of tr(...) (including both arms of a ternary)."""
    out = set()
    for m in re.finditer(call, src):
        i, depth, arg = m.end(), 0, []
        while i < len(src):
            c = src[i]
            if c == '"':
                j = src.index('"', i + 1)
                while src[j - 1] == "\\":
                    j = src.index('"', j + 1)
                skip = src[i - 1] in "fF" or (py and (src[i - 1] == "[" or src[i - 4:i] == "get(" or src[j + 1:j + 2] in (":", "]")))
                arg.append(" " if skip else src[i:j + 1]); i = j + 1; continue  # skip f-strings, data keys t["x"] / .get("x") / {"x": …}
            if c in "'`":  # other quote styles: skip (keys always use double quotes)
                j = src.index(c, i + 1); arg.append(" "); i = j + 1; continue
            if c in "([{":
                depth += 1
            elif c in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif c == "," and depth == 0:
                break
            arg.append(c if depth == 0 else " "); i += 1
        for lit in _LIT.findall("".join(arg)):
            if lit.strip(): out.add(ast.literal_eval('"' + lit + '"') if py else json.loads('"' + lit + '"'))
    return out


def js_keys():
    keys = set()
    for fn in sorted(os.listdir(os.path.join(ROOT, "assets"))):
        if fn.endswith(".js") and fn != "i18n.js":
            src = open(os.path.join(ROOT, "assets", fn), encoding="utf-8").read()
            keys |= _tr_literals(src)
    return keys


PY_CALL = r"(?<![\w.])(?:_t|_)\(|\bh\._\(|\bL\.t\("  # _("…") in build_pages.py, _t("…") / h._("…") in trade_pages.py


def py_keys():
    """Literal keys in the page generators, so `check` also sees strings for states today's data doesn't reach
    (e.g. a breakout fill). Keep keys literal: _("A" if x else "B"), never _(f"…")."""
    keys = set()
    for fn in ("build_pages.py", "trade_pages.py", "site_pages.py"):
        src = open(os.path.join(ROOT, "scripts", fn), encoding="utf-8").read()
        keys |= {k for k in _tr_literals(src, PY_CALL, py=True)}
    return keys


def check(only=None):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import build_pages
    langs = build_pages.build(dry=True)
    jk, pk = js_keys(), py_keys()
    bad = 0
    for L in langs:
        if L.en or (only and L.code != only):
            continue
        miss = sorted(L.missing | {k for k in jk if not L.ui.get(k)} | {k for k in pk if not L.s.get(k)})
        print(f"== {L.code}: {len(L.s)} strings, {len(miss)} missing")
        for k in miss:
            print("  MISSING", json.dumps(k, ensure_ascii=False))
        bad += len(miss)
    return bad


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "bundle":
        print("\n".join(bundle()) or "i18n: bundles up to date")
    else:
        sys.exit(1 if check(sys.argv[2] if len(sys.argv) > 2 else None) else 0)
