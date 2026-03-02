# Geekflare Opportunity Finder

A local AI agent that takes a list of domains, autonomously searches each one,
and finds the specific pages where Geekflare AI and/or Geekflare API can be naturally placed.

---

## How it works (what the agent does)

For each domain your manager sends you, the tool:

1. **Visits the homepage** to understand what kind of site it is
2. **Asks Claude** to pick the most relevant search queries for that site
   (e.g. "ChatGPT alternatives", "web scraping API", "broken link checker" — based on built-in product knowledge)
3. **Runs Google `site:domain.com [query]`** searches across all relevant keywords
4. **Collects every candidate URL** found across all queries
5. **Fetches and reads each page** to extract actual content
6. **Asks Claude to confirm** whether it's a genuine placement opportunity — and if so, which product fits and exactly where
7. **Displays results** domain by domain, with fit level, reason, and a specific placement note

---

## Setup

**Requirements:** Python 3.9+, OpenAI API key from https://openai.com/api/

```bash
cd geekflare-opportunity-finder

# Optional: virtual environment
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

pip install -r requirements.txt
python app.py
```

Open **http://localhost:5050** in your browser.

---

## How to use

1. Paste your OpenAI API key
2. Paste the domain list separated by — bullets `•`, commas, newlines — all formats work
3. Click **Find Opportunities**
4. Watch the live log as the agent works through each domain
5. Filter by Strong Fit, GF AI only, GF API only
6. Export to CSV and share with your manager

---

## What it costs

Each domain uses roughly:
- ~5–8 Google searches
- ~10–15 page fetches
- ~3–4 Claude API calls

Approximate cost: **$0.10–$0.20 per domain** with Claude Sonnet.
For a 40-domain list: roughly **$4–$8 total**.

---

## Notes

- Results update in real time as each domain is processed — you don't wait until the end
- The agent processes one domain at a time with polite delays (avoids rate limits)
- If Google blocks site: search temporarily, results for that domain will be sparse — just retry later
- The tool has no rate limits, no usage caps, and runs entirely on your machine
