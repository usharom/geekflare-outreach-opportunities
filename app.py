#!/usr/bin/env python3
"""
Geekflare Opportunity Finder — Sitemap Edition
Discovers pages via sitemap.xml (no Google, no search API needed).
"""

import re, json, time, threading, gzip
import xml.etree.ElementTree as ET
import requests
from flask import Flask, render_template, request, jsonify
from bs4 import BeautifulSoup
from openai import OpenAI

app = Flask(__name__, static_folder="static", template_folder="templates")

PRODUCT_KNOWLEDGE = """
## Geekflare AI / Connect (BYOK multi-model AI chat platform)
Target audiences: developers, dev teams, IT managers, technical professionals
Core value: one platform to access 40+ AI models (Claude, GPT-4/5, Gemini, Grok, DeepSeek, Mistral etc.)
         with API-key encryption, team workspaces, role-based access, side-by-side model comparison.
Relevant page topics:
  - ChatGPT alternatives / Claude alternatives / AI chat tools
  - Multi-model AI platforms / comparing AI models
  - BYOK (Bring Your Own Key) AI tools
  - Team AI tools / AI for teams / collaborative AI
  - AI productivity tools for developers / dev teams
  - AI chat platforms / enterprise AI tools
  - Prompt engineering tools / prompt libraries
  - Best AI tools roundups (developer-focused)
  - AI tool comparisons / AI model comparisons
  - AI writing tools / AI assistants

## Geekflare API (unified web & network automation REST API suite)
Target audiences: developers, SEOs, data engineers, AI/ML engineers, web automation teams
Core value: scraping, screenshots, URL to Markdown, PDF generation, DNS lookup, broken link checking.
Relevant page topics:
  - Web scraping tools / APIs / tutorials
  - Screenshot API / website screenshot tools
  - Broken link checker tools / APIs
  - DNS lookup tools / DNS monitoring
  - PDF generation from URL / HTML to PDF
  - Web automation tools / APIs
  - RAG pipeline tools / LLM data ingestion
  - SEO tools / SEO API / technical SEO automation
  - Developer tool roundups / API tool lists
  - Web data extraction / headless browser tools
"""

ALL_KEYWORDS = [
    "ai", "chatgpt", "gpt", "claude", "gemini", "llm", "artificial-intelligence",
    "machine-learning", "chat", "assistant", "copilot", "automation", "comparison",
    "alternative", "best-tools", "review", "software", "platform", "technology",
    "api", "scraping", "scraper", "screenshot", "broken-link", "dns", "pdf",
    "web-data", "extraction", "headless", "proxy", "seo", "monitoring", "developer",
    "tools", "integration", "technical", "data", "crawl", "fetch", "markdown", "html",
    "saas", "productivity", "no-code", "workflow"
]

jobs = {}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def fetch_raw(url, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    return None


def parse_sitemap(content):
    urls = []
    try:
        if content[:2] == b'\x1f\x8b':
            content = gzip.decompress(content)
        root = ET.fromstring(content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for el in root.findall("sm:sitemap/sm:loc", ns):
            if el.text:
                urls.append(("index", el.text.strip()))
        for el in root.findall("sm:url/sm:loc", ns):
            if el.text:
                urls.append(("url", el.text.strip()))
        if not urls:
            for el in root.iter():
                if el.tag.endswith("loc") and el.text:
                    urls.append(("url", el.text.strip()))
    except Exception:
        pass
    return urls


def get_sitemap_urls(domain, emit, max_urls=2000):
    clean = domain.replace("https://","").replace("http://","").rstrip("/")
    base = f"https://{clean}"

    candidates = [
        f"{base}/sitemap.xml",
        f"{base}/sitemap_index.xml",
        f"{base}/sitemap-index.xml",
        f"{base}/sitemap/sitemap.xml",
        f"{base}/blog-sitemap.xml",
        f"{base}/post-sitemap.xml",
    ]

    robots = fetch_raw(f"{base}/robots.txt")
    if robots:
        for line in robots.decode("utf-8", errors="ignore").splitlines():
            if line.lower().startswith("sitemap:"):
                sm_url = line.split(":", 1)[1].strip()
                if sm_url not in candidates:
                    candidates.insert(0, sm_url)

    all_pages = []
    visited = set()
    queue = list(candidates)

    while queue and len(all_pages) < max_urls:
        sm_url = queue.pop(0)
        if sm_url in visited:
            continue
        visited.add(sm_url)
        content = fetch_raw(sm_url)
        if not content:
            continue
        emit(f"   📄 Sitemap: {sm_url.split('/')[-1]}")
        entries = parse_sitemap(content)
        for kind, url in entries:
            if kind == "index" and url not in visited:
                queue.append(url)
            elif kind == "url" and clean.replace("www.","") in url:
                all_pages.append(url)
        time.sleep(0.3)

    return all_pages[:max_urls]


# Paths that are NEVER editorial — discard immediately
BLOCKED_PATH_PATTERNS = re.compile(
    r"/(docs|documentation|api-reference|api-docs|reference|sdk|changelog|release-notes"
    r"|support|help|kb|knowledge-base|helpdesk|faq|status|system-status"
    r"|pricing|plans|billing|checkout|cart|shop"
    r"|login|signin|sign-in|signup|sign-up|register|register|account|dashboard|portal"
    r"|privacy|terms|legal|cookie|gdpr|security|compliance"
    r"|about|team|careers|jobs|press|media|contact|partners|affiliate"
    r"|tag|author|category|page/\d|wp-json|feed|rss|amp"
    r"|product|features|solutions|platform|integrations|customers|case-studies"
    r"|webinar|event|demo|download|install|setup|onboarding"
    r"|community|forum|discussion|ticket|submit"
    r")(/|$)"
)

def keyword_filter(urls):
    filtered = []
    for url in urls:
        slug = url.lower().split("?")[0]
        # Hard block non-editorial paths
        if BLOCKED_PATH_PATTERNS.search(slug):
            continue
        # Must have enough path depth to be an article
        if slug.rstrip("/").count("/") < 2:
            continue
        for kw in ALL_KEYWORDS:
            if kw in slug:
                filtered.append(url)
                break
    return filtered


def fetch_page_text(url, max_chars=2500):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script","style","nav","footer","header","aside","form"]):
            tag.decompose()
        title = soup.title.string.strip() if soup.title else ""
        headings = [h.get_text(strip=True) for h in soup.find_all(["h1","h2","h3"])[:8]]
        body = " ".join(soup.get_text(separator=" ", strip=True).split())[:max_chars]
        return f"Title: {title}\nHeadings: {' | '.join(headings)}\n\n{body}"
    except Exception as e:
        return f"[Fetch failed: {e}]"


def ai_batch_score(client, urls):
    if not urls:
        return []
    slug_list = "\n".join(urls[:80])
    prompt = f"""You are a marketing analyst for Geekflare.

## Products:
{PRODUCT_KNOWLEDGE}

From the URLs below, return ONLY those whose slugs suggest the page is likely about a topic
relevant to Geekflare AI or Geekflare API. Be inclusive — if in doubt, include it.
Return ONLY a JSON array of selected URLs. No explanation. No markdown fences.

URLs:
{slug_list}

Return: ["url1", "url2", ...]"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.choices[0].message.content.strip().replace("```json","").replace("```","").strip()
        result = json.loads(raw)
        return [u for u in result if isinstance(u, str)]
    except Exception:
        return urls[:20]


def ai_confirm_page(client, url, page_text):
    prompt = f"""You are a strict marketing analyst for Geekflare. Your job is to find pages where adding Geekflare as a tool recommendation would feel COMPLETELY NATURAL to a reader — not forced, not a stretch.

## Geekflare products:
{PRODUCT_KNOWLEDGE}

## Known direct competitors to use as reference points:
Geekflare AI competitors: TypingMind, Magai, ChatHub, Poe, HuggingChat, OpenRouter, Merlin, FlowGPT, Chatsonic
Geekflare API competitors: ScrapingBee, Apify, Bright Data, Oxylabs, ZenRows, SerpApi, Screenshotone, Urlbox, ApiFlash, PDFShift, Bannerbear

## Page to evaluate:
URL: {url}
{page_text}

## Qualification rules — ALL must be true for is_opportunity: true:

RULE 1 — EDITORIAL ONLY
The page must be third-party editorial content: a blog post, roundup, comparison, or tutorial written to help readers discover or evaluate tools. 
INSTANT DISQUALIFY if the page is: product documentation, API reference, a help/support article, a page about the site's OWN product features, a pricing page, a login/signup page, or any page that exists to serve the site's own customers rather than inform general readers.

RULE 2 — ALREADY LISTS SIMILAR TOOLS
The page must ALREADY mention at least one named competitor tool in the same category as Geekflare AI or Geekflare API. 
Examples: if it mentions TypingMind, Magai, ChatHub, Poe — Geekflare AI fits. If it mentions ScrapingBee, Apify, Screenshotone — Geekflare API fits.
If the page discusses the TOPIC (e.g. "web scraping") but names NO specific competing tools, it is NOT an opportunity. We cannot ask a site to add Geekflare to a list that doesn't exist yet.

RULE 3 — GEEKFLARE WOULD FIT AS A PEER
Geekflare must belong in the same tier and context as the tools already listed. If the article lists enterprise tools costing $500/month, Geekflare doesn't fit. If it lists free developer tools, it might.

## Return ONLY this JSON (no markdown, no explanation):
{{
  "is_opportunity": true or false,
  "disqualify_reason": "EDITORIAL_FAIL or NO_COMPETITOR_NAMES or WRONG_TIER or null",
  "competitors_found": ["list of competitor tool names actually mentioned on the page"],
  "products": ["Geekflare AI", "Geekflare API"],
  "fit": "strong" or "moderate" or "weak",
  "page_type": "roundup" or "comparison" or "blog post" or "tutorial" or "tool listing" or "other",
  "reason": "1 sentence — name the specific competitors already on the page that make this a fit",
  "placement_note": "Exact context: e.g. In the section listing alternatives to TypingMind, add Geekflare AI as another option with [specific angle]"
}}

Default to is_opportunity: false. Only return true if you are confident all 3 rules pass."""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=350,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.choices[0].message.content.strip().replace("```json","").replace("```","").strip()
        return json.loads(raw)
    except Exception as e:
        return {"is_opportunity": False, "error": str(e)[:100]}


def process_domain(client, domain, job_id):
    job = jobs[job_id]
    def emit(msg):
        job["log"].append({"domain": domain, "msg": msg, "t": time.time()})

    emit(f"🔍 Starting {domain}...")

    # 1. Sitemap discovery
    emit(f"   Fetching sitemap...")
    all_urls = get_sitemap_urls(domain, emit)
    emit(f"   Found {len(all_urls)} URLs in sitemap")

    # Fallback: crawl homepage links
    if not all_urls:
        emit(f"   ⚠ No sitemap — crawling homepage links...")
        base = f"https://{domain}"
        try:
            r = requests.get(base, headers=HEADERS, timeout=12)
            soup = BeautifulSoup(r.text, "html.parser")
            links = set()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("/") and len(href) > 2:
                    links.add(f"{base}{href}")
                elif domain.replace("www.","") in href:
                    links.add(href)
            all_urls = list(links)[:200]
            emit(f"   Found {len(all_urls)} homepage links")
        except Exception as ex:
            emit(f"   ❌ Could not reach site: {ex}")

    if not all_urls:
        emit(f"   ❌ No pages discoverable on {domain}")
        job["results"].append({"domain": domain, "status": "no_results", "opportunities": []})
        return

    # 2. Keyword filter
    kw_filtered = keyword_filter(all_urls)
    emit(f"   Keyword filter: {len(kw_filtered)} relevant-looking URLs")
    if len(kw_filtered) < 5 and len(all_urls) >= 5:
        kw_filtered = all_urls[:100]
        emit(f"   Expanded to {len(kw_filtered)} URLs")

    # 3. AI batch scoring by slug
    emit(f"   AI scoring {min(len(kw_filtered),80)} URLs by slug...")
    shortlisted = []
    for i in range(0, min(len(kw_filtered), 160), 80):
        batch = kw_filtered[i:i+80]
        shortlisted.extend(ai_batch_score(client, batch))
    # Deduplicate
    seen = set()
    shortlisted = [u for u in shortlisted if not (u in seen or seen.add(u))]
    shortlisted = shortlisted[:25]
    emit(f"   Shortlisted {len(shortlisted)} pages for deep read")

    if not shortlisted:
        emit(f"   No promising pages found after scoring")
        job["results"].append({"domain": domain, "status": "done", "candidates_checked": len(kw_filtered), "opportunities": []})
        return

    # 4. Deep read + confirm
    confirmed = []
    for i, url in enumerate(shortlisted):
        emit(f"   Reading {i+1}/{len(shortlisted)}: ...{url[-55:]}")
        page_text = fetch_page_text(url)
        verdict = ai_confirm_page(client, url, page_text)
        if verdict.get("is_opportunity"):
            title_m = re.search(r"Title: (.+)", page_text)
            title = title_m.group(1).strip() if title_m else url
            confirmed.append({
                "url": url, "title": title,
                "products": verdict.get("products", []),
                "fit": verdict.get("fit", "moderate"),
                "page_type": verdict.get("page_type", ""),
                "reason": verdict.get("reason", ""),
                "placement_note": verdict.get("placement_note", ""),
                "competitors_found": verdict.get("competitors_found", []),
            })
            comp_str = ", ".join(verdict.get("competitors_found", []))
            emit(f"   ✅ {title[:50]} ({verdict.get('fit')} fit) — rivals: {comp_str}")
        time.sleep(0.8)

    emit(f"   ✔ Done — {len(confirmed)} opportunities on {domain}")
    job["results"].append({
        "domain": domain, "status": "done",
        "candidates_checked": len(shortlisted),
        "opportunities": confirmed
    })


def run_job(job_id, domains, api_key):
    client = OpenAI(api_key=api_key)
    jobs[job_id]["status"] = "running"
    for domain in domains:
        domain = domain.strip().lower().replace("https://","").replace("http://","").rstrip("/")
        if not domain or "." not in domain:
            continue
        try:
            process_domain(client, domain, job_id)
        except Exception as e:
            jobs[job_id]["log"].append({"domain": domain, "msg": f"❌ Error: {e}", "t": time.time()})
            jobs[job_id]["results"].append({"domain": domain, "status": "error", "error": str(e), "opportunities": []})
        jobs[job_id]["domains_done"] += 1
    jobs[job_id]["status"] = "complete"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/start", methods=["POST"])
def start():
    data = request.json
    api_key = data.get("api_key", "").strip()
    raw = data.get("domains", "").strip()
    if not api_key:
        return jsonify({"error": "OpenAI API key required"}), 400
    domains = re.split(r"[•\n,;]+", raw)
    domains = [d.strip().replace("https://","").replace("http://","").rstrip("/") for d in domains if d.strip()]
    domains = [d for d in domains if "." in d]
    if not domains:
        return jsonify({"error": "No valid domains found"}), 400
    job_id = f"job_{int(time.time()*1000)}"
    jobs[job_id] = {"status": "queued", "domains_total": len(domains), "domains_done": 0, "log": [], "results": []}
    threading.Thread(target=run_job, args=(job_id, domains, api_key), daemon=True).start()
    return jsonify({"job_id": job_id, "domains": domains})


@app.route("/api/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "status": job["status"],
        "domains_total": job["domains_total"],
        "domains_done": job["domains_done"],
        "log": job["log"][-80:],
        "results": job["results"],
    })


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5050))
    print(f"\n🚀 Geekflare Opportunity Finder running on port {port}\n")
    app.run(debug=False, host="0.0.0.0", port=port, threaded=True)
