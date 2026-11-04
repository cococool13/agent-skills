#!/usr/bin/env python3
"""live.py - read-only live product checks (stdlib only).

Run with: python3 -I live.py <command> ...
  site    <url> --out DIR      headers, meta, robots/sitemap, link crawl, external links
  psi     <url> --out DIR      PageSpeed Insights mobile+desktop (cached, 1 req / 10 s)
  appcast <url>                Sparkle appcast checks (XML, https, edSignature, versions)
  batch   <urls.json> --out DIR [--kinds site,landing] [--psi]
  --selftest                   no network; uses an in-memory synthetic site

Safety: GET/HEAD only, <=2 req/s (global), <=200 internal URLs per site,
<=50 external hosts per site, polite User-Agent, never logs in, never submits forms.
Only point it at the owner's own domains (plus the keyless PSI endpoint).
"""
import argparse, hashlib, json, os, re, ssl, struct, sys, threading, time
import urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

UA = "cohen-ai-stack-audit/1.0 (+read-only)"
PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
SPARKLE_NS = "http://www.andymatuschak.org/xml-namespaces/sparkle"
SKIP_EXT = re.compile(r"\.(png|jpe?g|gif|webp|avif|svg|ico|css|js|mjs|woff2?|ttf|otf|pdf|zip|dmg|pkg|mp4|mov|webm|mp3|xml|json|txt|map)(\?|$)", re.I)
SEC_HEADERS = ["strict-transport-security", "content-security-policy", "x-content-type-options",
               "referrer-policy", "permissions-policy", "cross-origin-opener-policy",
               "x-frame-options", "cache-control", "server", "cf-cache-status", "content-type"]


class Limiter:
    def __init__(self, rps):
        self.gap = 1.0 / rps if rps else 0
        self.lock = threading.Lock()
        self.next = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next)
            self.next = t + self.gap
        if t > now:
            time.sleep(t - now)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Net:
    """Single point for HTTP. GET/HEAD only. Global rate limit."""

    def __init__(self, rps=2.0, timeout=20):
        self.limiter = Limiter(rps)
        self.timeout = timeout
        self.count = 0
        ctx = ssl.create_default_context()
        self.opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=ctx))

    def _fetch(self, url, method, headers, max_bytes):
        req = urllib.request.Request(url, method=method, headers=dict({"User-Agent": UA, "Accept": "*/*"}, **(headers or {})))
        try:
            r = self.opener.open(req, timeout=self.timeout)
            code, hdrs = r.status, r.headers
            body = r.read(max_bytes) if method == "GET" else b""
            return code, hdrs, body, None
        except urllib.error.HTTPError as e:
            body = b""
            try:
                body = e.read(max_bytes) if method == "GET" else b""
            except Exception:
                pass
            return e.code, e.headers, body, None
        except Exception as e:  # DNS, TLS, timeout
            return 0, {}, b"", "%s: %s" % (type(e).__name__, str(e)[:120])

    def request(self, url, method="GET", headers=None, max_bytes=1_500_000):
        assert method in ("GET", "HEAD"), "read-only"
        self.limiter.wait()
        self.count += 1
        code, hdrs, body, err = self._fetch(url, method, headers, max_bytes)
        h = {}
        for k in (hdrs.keys() if hdrs else []):
            vals = hdrs.get_all(k) if hasattr(hdrs, "get_all") else [hdrs[k]]
            h[k.lower()] = ", ".join(vals)
        return {"url": url, "status": code, "headers": h, "body": body, "error": err}

    def follow(self, url, method="GET", max_hops=6, max_bytes=1_500_000):
        """Follow redirects manually. Returns (final_response, chain[list of (url,status,location)])."""
        chain, cur = [], url
        for _ in range(max_hops + 1):
            r = self.request(cur, method, max_bytes=max_bytes)
            loc = r["headers"].get("location")
            chain.append((cur, r["status"], loc))
            if r["status"] in (301, 302, 303, 307, 308) and loc:
                cur = urllib.parse.urljoin(cur, loc)
                continue
            return r, chain
        return r, chain


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self.meta, self.links, self.anchors, self.refs = {}, [], [], []
        self.jsonld = 0
        self.h1 = 0
        self.imgs = 0
        self.imgs_noalt = 0
        self.html_lang = None
        self.styles = []
        self._in_style = False
        self.inline_style_attrs = []
        self.stylesheets = []

    def handle_starttag(self, tag, attrs):
        a = dict((k, v or "") for k, v in attrs)
        if tag == "html":
            self.html_lang = a.get("lang")
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = a.get("name") or a.get("property") or a.get("http-equiv")
            if key:
                self.meta[key.lower()] = a.get("content", "")
        elif tag == "link":
            self.links.append(a)
            if "stylesheet" in a.get("rel", "").lower() and a.get("href"):
                self.stylesheets.append(a["href"])
            if a.get("href"):
                self.refs.append(a["href"])
        elif tag == "a" and a.get("href"):
            self.anchors.append(a["href"])
        elif tag == "script":
            if a.get("type", "").lower() == "application/ld+json":
                self.jsonld += 1
            if a.get("src"):
                self.refs.append(a["src"])
        elif tag == "img":
            self.imgs += 1
            if "alt" not in a:
                self.imgs_noalt += 1
            if a.get("src"):
                self.refs.append(a["src"])
        elif tag in ("source", "iframe", "video", "audio") and a.get("src"):
            self.refs.append(a["src"])
        elif tag == "h1":
            self.h1 += 1
        elif tag == "style":
            self._in_style = True
        if a.get("style"):
            self.inline_style_attrs.append(a["style"])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "style":
            self._in_style = False

    def handle_data(self, d):
        if self._in_title:
            self.title += d
        if self._in_style:
            self.styles.append(d)


def parse_html(body):
    p = Page()
    try:
        p.feed(body.decode("utf-8", "replace"))
    except Exception:
        pass
    return p


def image_dims(b):
    """(w,h,fmt) from PNG/JPEG/GIF/WebP header bytes, else None."""
    try:
        if b[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", b[16:24])
            return w, h, "png"
        if b[:6] in (b"GIF87a", b"GIF89a"):
            w, h = struct.unpack("<HH", b[6:10])
            return w, h, "gif"
        if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
            if b[12:16] == b"VP8X":
                w = 1 + int.from_bytes(b[24:27], "little")
                h = 1 + int.from_bytes(b[27:30], "little")
                return w, h, "webp"
            if b[12:16] == b"VP8 ":
                w, h = struct.unpack("<HH", b[26:30])
                return w & 0x3FFF, h & 0x3FFF, "webp"
            if b[12:16] == b"VP8L":
                v = int.from_bytes(b[21:25], "little")
                return (v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1, "webp"
        if b[:2] == b"\xff\xd8":
            i = 2
            while i < len(b) - 9:
                if b[i] != 0xFF:
                    i += 1
                    continue
                m = b[i + 1]
                if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
                    i += 2
                    continue
                ln = struct.unpack(">H", b[i + 2:i + 4])[0]
                if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h, w = struct.unpack(">HH", b[i + 5:i + 9])
                    return w, h, "jpeg"
                i += 2 + ln
    except Exception:
        pass
    return None


def sec_headers(h):
    return {k: h.get(k) for k in SEC_HEADERS}


def norm(url):
    u = urllib.parse.urldefrag(url)[0]
    p = urllib.parse.urlsplit(u)
    path = p.path or "/"
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), path, p.query, ""))


def parse_sitemap(net, url, depth=0):
    r, _ = net.follow(url, max_bytes=3_000_000)
    out = {"url": url, "status": r["status"], "valid_xml": False, "urls": [], "children": []}
    if r["status"] != 200:
        return out
    try:
        root = ET.fromstring(r["body"])
        out["valid_xml"] = True
    except ET.ParseError as e:
        out["error"] = str(e)[:100]
        return out
    tag = lambda e: e.tag.split("}")[-1]
    if tag(root) == "sitemapindex" and depth < 2:
        for loc in root.iter():
            if tag(loc) == "loc" and loc.text:
                out["children"].append(loc.text.strip())
                sub = parse_sitemap(net, loc.text.strip(), depth + 1)
                out["urls"] += sub["urls"]
    else:
        out["urls"] = [e.text.strip() for e in root.iter() if tag(e) == "loc" and e.text]
    return out


def audit_site(net, base, outdir=None, max_urls=200, max_ext=50, ext_cache=None, budget_s=240):
    ext_cache = ext_cache if ext_cache is not None else {}
    t_start = time.monotonic()
    p0 = urllib.parse.urlsplit(base)
    host = p0.netloc
    res = {"base": base, "host": host, "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    # --- scheme / host variants
    r, chain = net.follow("http://%s/" % host)
    res["http_to_https"] = {"final": chain[-1][0], "hops": len(chain) - 1, "ok": chain[-1][0].startswith("https://") and r["status"] == 200,
                            "status_first": chain[0][1]}
    own_domain = not host.endswith(("workers.dev", "pages.dev"))
    if own_domain:
        alt = host[4:] if host.startswith("www.") else "www." + host
        r2, ch2 = net.follow("https://%s/" % alt)
        res["alt_host"] = {"host": alt, "status": r2["status"], "hops": len(ch2) - 1,
                           "final": ch2[-1][0], "redirects_to_canonical": urllib.parse.urlsplit(ch2[-1][0]).netloc == host,
                           "error": r2["error"]}
    # --- home
    home, hchain = net.follow(base)
    res["home"] = {"status": home["status"], "chain": [(u, s) for u, s, _ in hchain], "final": hchain[-1][0], "error": home["error"]}
    res["headers_html"] = sec_headers(home["headers"])
    if home["status"] != 200:
        return res
    final = hchain[-1][0]
    base_netloc_home = urllib.parse.urlsplit(final).netloc
    pg = parse_html(home["body"])
    res["html_bytes"] = len(home["body"])
    res["meta"] = {
        "title": pg.title.strip(), "title_len": len(pg.title.strip()),
        "description": pg.meta.get("description"), "description_len": len(pg.meta.get("description", "")),
        "canonical": next((l.get("href") for l in pg.links if l.get("rel", "").lower() == "canonical"), None),
        "og": {k: v for k, v in pg.meta.items() if k.startswith("og:")},
        "twitter": {k: v for k, v in pg.meta.items() if k.startswith("twitter:")},
        "viewport": pg.meta.get("viewport"), "lang": pg.html_lang, "h1_count": pg.h1,
        "jsonld_blocks": pg.jsonld, "imgs": pg.imgs, "imgs_missing_alt": pg.imgs_noalt,
        "robots_meta": pg.meta.get("robots"), "theme_color": pg.meta.get("theme-color"),
    }
    # icons
    icons = [(l.get("rel", ""), l.get("href")) for l in pg.links if "icon" in l.get("rel", "").lower() and l.get("href")]
    res["icons"] = []
    for rel, href in icons[:6]:
        u = urllib.parse.urljoin(final, href)
        rr, _ = net.follow(u, "HEAD")
        res["icons"].append({"rel": rel, "href": href, "status": rr["status"]})
    if not any("icon" == r.lower() or "shortcut icon" == r.lower() for r, _ in icons):
        rr, _ = net.follow(urllib.parse.urljoin(final, "/favicon.ico"), "HEAD")
        res["icons"].append({"rel": "(implicit)/favicon.ico", "href": "/favicon.ico", "status": rr["status"]})
    res["has_apple_touch_icon"] = any("apple-touch-icon" in r.lower() for r, _ in icons)
    # OG image
    ogi = pg.meta.get("og:image")
    if ogi:
        u = urllib.parse.urljoin(final, ogi)
        rr, _ = net.follow(u, max_bytes=262144)
        res["og_image"] = {"url": u, "status": rr["status"], "type": rr["headers"].get("content-type"),
                           "bytes_header": rr["headers"].get("content-length"), "dims": image_dims(rr["body"])}
    # asset headers
    # first same-origin stylesheet/script (third-party assets such as Google Fonts say nothing about this site's own cache policy)
    asset = next((u for u in (pg.stylesheets + [r for r in pg.refs if r.split("?")[0].endswith((".js", ".mjs"))])
                  if u and urllib.parse.urlsplit(urllib.parse.urljoin(final, u)).netloc == base_netloc_home), None)
    if asset:
        au = urllib.parse.urljoin(final, asset)
        ar, _ = net.follow(au, "HEAD")
        res["asset_url"] = au
        res["headers_asset"] = sec_headers(ar["headers"])
        res["asset_status"] = ar["status"]
    # robots + sitemap
    rb, _ = net.follow(urllib.parse.urljoin(final, "/robots.txt"))
    robots_txt = rb["body"].decode("utf-8", "replace") if rb["status"] == 200 else ""
    res["robots"] = {"status": rb["status"], "looks_like_text": "html" not in rb["headers"].get("content-type", "") and bool(re.search(r"(?i)user-agent|sitemap|disallow", robots_txt)),
                     "sitemap_lines": re.findall(r"(?im)^sitemap:\s*(\S+)", robots_txt), "disallow_all": bool(re.search(r"(?im)^disallow:\s*/\s*$", robots_txt))}
    sm_url = (res["robots"]["sitemap_lines"] or [urllib.parse.urljoin(final, "/sitemap.xml")])[0]
    sm = parse_sitemap(net, sm_url)
    sample = []
    for u in sm["urls"][:5]:
        rr, ch = net.follow(u, "HEAD")
        sample.append({"url": u, "status": rr["status"], "hops": len(ch) - 1})
    sm_hosts = sorted({urllib.parse.urlsplit(u).netloc for u in sm["urls"]})
    res["sitemap"] = {"url": sm_url, "status": sm["status"], "valid_xml": sm["valid_xml"], "count": len(sm["urls"]), "sample": sample,
                      "hosts": sm_hosts, "host_matches_site": (not sm_hosts) or sm_hosts == [host]}
    # --- crawl
    seen, queue, pages = set(), [norm(final)], []
    for u in sm["urls"]:
        if urllib.parse.urlsplit(u).netloc == host:
            queue.append(norm(u))
    ext_links, issues = {}, []
    base_netloc = urllib.parse.urlsplit(final).netloc
    time_capped = False
    while queue and len(seen) < max_urls:
        if time.monotonic() - t_start > budget_s:
            time_capped = True
            break
        u = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        r, ch = net.follow(u)
        row = {"url": u, "status": r["status"], "hops": len(ch) - 1}
        if len(ch) > 2:
            issues.append({"type": "redirect_chain", "url": u, "chain": [c[0] for c in ch]})
        if r["status"] >= 400 or r["status"] == 0:
            issues.append({"type": "broken", "url": u, "status": r["status"], "error": r["error"]})
        ctype = r["headers"].get("content-type", "")
        if r["status"] == 200 and "html" in ctype:
            pp = parse_html(r["body"])
            row["title"] = pp.title.strip()
            mixed = [x for x in pp.refs if x.lower().startswith("http://")]
            if mixed:
                issues.append({"type": "mixed_content", "url": u, "refs": mixed[:5]})
            row["h1"] = pp.h1
            row["noindex"] = "noindex" in (pp.meta.get("robots", "")).lower()
            for a in pp.anchors:
                if a.startswith(("mailto:", "tel:", "javascript:", "#", "data:", "sms:")):
                    continue
                full = urllib.parse.urljoin(ch[-1][0], a)
                sp = urllib.parse.urlsplit(full)
                if sp.scheme not in ("http", "https"):
                    continue
                if sp.netloc == base_netloc:
                    nu = norm(full)
                    if nu not in seen and not SKIP_EXT.search(sp.path) and nu not in queue:
                        queue.append(nu)
                else:
                    ext_links.setdefault(sp.netloc, full)
        pages.append(row)
    res["crawl"] = {"pages_fetched": len(pages), "capped": bool(queue) and len(seen) >= max_urls, "time_capped": time_capped, "queue_left": len(queue),
                    "ok": sum(1 for p in pages if p["status"] == 200), "issues": issues,
                    "dup_titles": sorted({t for t in [p.get("title") for p in pages if p.get("title")] if [p.get("title") for p in pages].count(t) > 1}),
                    "missing_h1": [p["url"] for p in pages if p.get("h1") == 0][:10]}
    # --- external hosts
    ext = []
    for h, u in list(ext_links.items())[:max_ext]:
        if h in ext_cache:
            ext.append(dict(ext_cache[h], url=u))
            continue
        rr, ch = net.follow(u, "HEAD")
        row = {"host": h, "url": u, "status": rr["status"], "error": rr["error"], "hops": len(ch) - 1}
        ext_cache[h] = row
        ext.append(row)
    res["external"] = {"hosts_total": len(ext_links), "checked": len(ext),
                       "bad": [e for e in ext if e["status"] >= 400 or e["status"] == 0]}
    # --- save HTML/CSS for design check
    if outdir:
        d = os.path.join(outdir, "html", host.replace(":", "_"))
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "wb").write(home["body"])
        for i, href in enumerate(pg.stylesheets[:8]):
            cu = urllib.parse.urljoin(final, href)
            if urllib.parse.urlsplit(cu).netloc != base_netloc_home:
                continue  # only the site's own origin; never fetch third-party hosts
            cr, _ = net.follow(cu, max_bytes=800_000)
            if cr["status"] == 200:
                open(os.path.join(d, "style-%d.css" % i), "wb").write(cr["body"])
        open(os.path.join(d, "inline-style.css"), "w").write("\n".join(pg.styles + pg.inline_style_attrs))
    res["requests_used"] = net.count
    return res


# ---------------- PageSpeed Insights ----------------
class PSI:
    def __init__(self, cache_dir, gap=10.5):
        self.cache = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.gap = gap
        self.last = 0.0
        self.quota_hit = False

    def run(self, url, strategy):
        key = hashlib.sha256(("%s|%s" % (url, strategy)).encode()).hexdigest()[:16]
        cp = os.path.join(self.cache, key + ".json")
        if os.path.exists(cp):
            return json.load(open(cp))
        if self.quota_hit:
            return {"error": "PSI quota"}
        wait = self.gap - (time.monotonic() - self.last)
        if wait > 0:
            time.sleep(wait)
        q = [("url", url), ("strategy", strategy)] + [("category", c) for c in ("performance", "accessibility", "best-practices", "seo")]
        full = PSI_ENDPOINT + "?" + urllib.parse.urlencode(q)
        req = urllib.request.Request(full, headers={"User-Agent": UA})
        self.last = time.monotonic()
        try:
            raw = urllib.request.urlopen(req, timeout=120).read()
            d = json.loads(raw)
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", "replace")
            if e.code == 429 or "quota" in body.lower():
                self.quota_hit = True
                return {"error": "PSI quota", "http": e.code}
            return {"error": "HTTP %d" % e.code, "detail": body[:120]}
        except Exception as e:
            return {"error": "%s: %s" % (type(e).__name__, str(e)[:100])}
        out = self.summarize(d)
        json.dump(out, open(cp, "w"))
        return out

    @staticmethod
    def summarize(d):
        lh = d.get("lighthouseResult", {})
        cats = lh.get("categories", {})
        au = lh.get("audits", {})
        sc = {k: (None if v.get("score") is None else round(v["score"] * 100)) for k, v in cats.items()}
        lab = {k: au.get(k, {}).get("numericValue") for k in
               ("first-contentful-paint", "largest-contentful-paint", "total-blocking-time", "cumulative-layout-shift", "speed-index")}
        fe = (d.get("loadingExperience") or {}).get("metrics") or {}
        field = {k: {"p75": v.get("percentile"), "cat": v.get("category")} for k, v in fe.items()
                 if k in ("LARGEST_CONTENTFUL_PAINT_MS", "INTERACTION_TO_NEXT_PAINT", "CUMULATIVE_LAYOUT_SHIFT_SCORE", "FIRST_CONTENTFUL_PAINT_MS")}
        failed = sorted([(k, v.get("score")) for k, v in au.items() if v.get("score") is not None and v["score"] < 0.9 and v.get("scoreDisplayMode") in ("binary", "numeric")],
                        key=lambda x: x[1])[:12]
        return {"scores": sc, "lab": lab, "field": field, "failing_audits": [k for k, _ in failed],
                "final_url": lh.get("finalDisplayedUrl") or lh.get("finalUrl"), "runtime_error": (lh.get("runtimeError") or {}).get("code")}


# ---------------- Sparkle appcast ----------------
def check_appcast(net, url):
    r, chain = net.follow(url, max_bytes=2_000_000)
    out = {"url": url, "status": r["status"], "https": url.startswith("https://"), "hops": len(chain) - 1,
           "content_type": r["headers"].get("content-type"), "items": [], "problems": []}
    if r["status"] != 200:
        out["problems"].append("appcast status %s" % r["status"])
        return out
    try:
        root = ET.fromstring(r["body"])
    except ET.ParseError as e:
        out["problems"].append("invalid XML: %s" % e)
        return out
    S = "{%s}" % SPARKLE_NS
    for it in root.iter("item"):
        enc = it.find("enclosure")
        g = lambda t: (it.findtext(S + t) or (enc.get(S + t) if enc is not None else None))
        row = {"title": it.findtext("title"), "pubDate": it.findtext("pubDate"),
               "version": g("version"), "short": g("shortVersionString"), "minSys": g("minimumSystemVersion"),
               "edSignature": (enc.get(S + "edSignature") if enc is not None else None) or it.findtext(S + "edSignature"),
               "dsaSignature": bool(enc.get(S + "dsaSignature")) if enc is not None else False,
               "notes": it.findtext(S + "releaseNotesLink"), "has_description": bool(it.findtext("description")),
               "critical": it.find(S + "criticalUpdate") is not None,
               "enclosure": None if enc is None else {"url": enc.get("url"), "length": enc.get("length"), "type": enc.get("type")}}
        out["items"].append(row)
    if not out["items"]:
        out["problems"].append("no <item> entries")
    for i, row in enumerate(out["items"][:3]):  # latest few only
        e = row["enclosure"]
        if not e or not e["url"]:
            out["problems"].append("item %d: no enclosure" % i)
            continue
        if not e["url"].startswith("https://"):
            out["problems"].append("item %d: enclosure not https" % i)
        if not row["edSignature"]:
            out["problems"].append("item %d: missing sparkle:edSignature" % i)
        if not row["version"]:
            out["problems"].append("item %d: missing sparkle:version" % i)
        if not row["short"]:
            out["problems"].append("item %d: missing shortVersionString" % i)
        if not row["minSys"]:
            out["problems"].append("item %d: missing minimumSystemVersion" % i)
        hr, hc = net.follow(e["url"], "HEAD")
        row["enclosure"]["head_status"] = hr["status"]
        row["enclosure"]["head_len"] = hr["headers"].get("content-length")
        row["enclosure"]["head_type"] = hr["headers"].get("content-type")
        if hr["status"] != 200:
            out["problems"].append("item %d: enclosure HEAD %s" % (i, hr["status"]))
        elif e["length"] and hr["headers"].get("content-length") and e["length"] != hr["headers"]["content-length"]:
            out["problems"].append("item %d: length attr %s != served %s" % (i, e["length"], hr["headers"]["content-length"]))
        if row["notes"]:
            nr, _ = net.follow(row["notes"], "HEAD")
            row["notes_status"] = nr["status"]
            if nr["status"] != 200:
                out["problems"].append("item %d: release notes HEAD %s" % (i, nr["status"]))
    return out


# ---------------- batch ----------------
def slug(u):
    return re.sub(r"[^a-z0-9]+", "-", urllib.parse.urlsplit(u).netloc.lower()).strip("-")


def batch(path, out, kinds, do_psi, rps=2.0):
    inv = json.load(open(path))
    os.makedirs(out, exist_ok=True)
    net = Net(rps=rps)
    ext_cache = {}
    sites = []
    seen = set()
    for e in inv:
        if e["kind"] in kinds and e["url"] not in seen:
            seen.add(e["url"])
            sites.append(e)
    psi = PSI(os.path.join(out, "psi-cache"))
    psi_results = {}

    def psi_worker():
        for e in sites:
            for st in ("mobile", "desktop"):
                psi_results[(e["url"], st)] = psi.run(e["url"], st)
                json.dump({"%s|%s" % k: v for k, v in psi_results.items()}, open(os.path.join(out, "psi.json"), "w"), indent=1)

    th = None
    if do_psi:
        th = threading.Thread(target=psi_worker, daemon=True)
        th.start()
    def one(e):
        fp = os.path.join(out, "site-%s.json" % slug(e["url"]))
        if os.path.exists(fp):
            return
        try:
            res = audit_site(net, e["url"], out, ext_cache=ext_cache)
        except Exception as ex:
            res = {"base": e["url"], "fatal": "%s: %s" % (type(ex).__name__, ex)}
        res["project"] = e.get("project")
        json.dump(res, open(fp, "w"), indent=1, default=str)
        print("done", e["url"], flush=True)

    # sites run in parallel threads, but every request still passes the one global 2 req/s limiter
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(one, sites))
    if th:
        th.join()
    print("batch complete; requests:", net.count, flush=True)


# ---------------- selftest ----------------
class FakeNet(Net):
    def __init__(self, routes):
        super().__init__(rps=0)
        self.routes = routes

    def _fetch(self, url, method, headers, max_bytes):
        r = self.routes.get(url)
        if r is None:
            return 404, {}, b"", None
        code, hdr, body = r
        class H(dict):
            def keys(s): return list(dict.keys(s))
            def get_all(s, k): return [dict.__getitem__(s, k)]
        return code, H(hdr), (body if method == "GET" else b""), None


def selftest():
    png = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 1200, 630) + b"\x08\x06\x00\x00\x00"
    home = """<!doctype html><html lang="en"><head><title>Fixture</title>
<meta name="description" content="short"><link rel="canonical" href="https://t.test/">
<meta property="og:image" content="/og.png"><link rel="icon" href="/f.ico"><link rel="stylesheet" href="/a.css">
<script type="application/ld+json">{}</script></head><body><h1>x</h1><a href="/p1">p1</a><a href="/gone">g</a>
<a href="/moved">m</a><a href="https://ext.test/x">e</a><img src="http://t.test/i.png"></body></html>"""
    R = {
        "http://t.test/": (301, {"location": "https://t.test/"}, b""),
        "https://t.test/": (200, {"content-type": "text/html", "strict-transport-security": "max-age=1"}, home.encode()),
        "https://www.t.test/": (301, {"location": "https://t.test/"}, b""),
        "https://t.test/p1": (200, {"content-type": "text/html"}, b"<title>P1</title><h1>a</h1>"),
        "https://t.test/gone": (404, {"content-type": "text/html"}, b""),
        "https://t.test/moved": (301, {"location": "/moved2"}, b""),
        "https://t.test/moved2": (301, {"location": "/p1"}, b""),
        "https://t.test/og.png": (200, {"content-type": "image/png"}, png),
        "https://t.test/f.ico": (200, {"content-type": "image/x-icon"}, b"x"),
        "https://t.test/a.css": (200, {"content-type": "text/css", "cache-control": "max-age=60"}, b"body{font-family:Inter}"),
        "https://t.test/robots.txt": (200, {"content-type": "text/plain"}, b"User-agent: *\nSitemap: https://t.test/sitemap.xml\n"),
        "https://t.test/sitemap.xml": (200, {"content-type": "application/xml"}, b"<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'><url><loc>https://t.test/</loc></url><url><loc>https://t.test/p1</loc></url></urlset>"),
        "https://ext.test/x": (200, {}, b""),
    }
    n = FakeNet(R)
    res = audit_site(n, "https://t.test/", None, max_urls=20)
    assert res["http_to_https"]["ok"] and res["http_to_https"]["hops"] == 1
    assert res["alt_host"]["redirects_to_canonical"]
    assert res["meta"]["description_len"] == 5 and res["meta"]["jsonld_blocks"] == 1
    assert res["og_image"]["dims"] == (1200, 630, "png"), res["og_image"]
    assert res["sitemap"]["count"] == 2 and res["sitemap"]["valid_xml"]
    kinds = {i["type"] for i in res["crawl"]["issues"]}
    assert {"broken", "redirect_chain", "mixed_content"} <= kinds, kinds
    assert res["external"]["checked"] == 1 and not res["external"]["bad"]
    ac = ('<rss xmlns:sparkle="%s"><channel><item><title>1.0</title><enclosure url="http://t.test/a.zip" length="5" type="application/zip" '
          'sparkle:version="1" sparkle:shortVersionString="1.0"/></item></channel></rss>' % "http://www.andymatuschak.org/xml-namespaces/sparkle").encode()
    R["https://t.test/appcast.xml"] = (200, {"content-type": "application/xml"}, ac)
    R["http://t.test/a.zip"] = (200, {"content-length": "5"}, b"")
    a = check_appcast(n, "https://t.test/appcast.xml")
    probs = " ".join(a["problems"])
    assert "not https" in probs and "edSignature" in probs and "minimumSystemVersion" in probs, probs
    assert image_dims(b"\xff\xd8\xff\xc0\x00\x11\x08\x01\x40\x00\xf0" + b"\x00" * 20)[:2] == (240, 320)
    try:
        n.request("https://t.test/", "POST")
    except AssertionError:
        pass
    else:
        raise SystemExit("POST was allowed")
    print("selftest ok (no network used)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    sp = ap.add_subparsers(dest="cmd")
    s = sp.add_parser("site"); s.add_argument("url"); s.add_argument("--out", default=".")
    s = sp.add_parser("psi"); s.add_argument("url"); s.add_argument("--out", default=".")
    s = sp.add_parser("appcast"); s.add_argument("url")
    s = sp.add_parser("batch"); s.add_argument("inventory"); s.add_argument("--out", required=True)
    s.add_argument("--kinds", default="site,landing"); s.add_argument("--psi", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.cmd == "site":
        print(json.dumps(audit_site(Net(), a.url, a.out), indent=1, default=str))
    elif a.cmd == "psi":
        p = PSI(os.path.join(a.out, "psi-cache"))
        print(json.dumps({st: p.run(a.url, st) for st in ("mobile", "desktop")}, indent=1))
    elif a.cmd == "appcast":
        print(json.dumps(check_appcast(Net(), a.url), indent=1))
    elif a.cmd == "batch":
        batch(a.inventory, a.out, set(a.kinds.split(",")), a.psi)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
