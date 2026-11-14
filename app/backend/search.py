"""Web search (Kagi) and page fetching, both cached in the DB's web_cache (SPEC §3.6, §4).

The cache is DEMO safety: once the demo question has run, its search results and pages
replay from the DB, so a flaky network on stage doesn't matter. seed.py --reset keeps it.
"""
import html as html_lib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

import httpx
import trafilatura

import db

KAGI_URL = "https://kagi.com/api/v1/search"  # v1; the legacy v0 GET returns 401 with new keys
KAGI_USD_PER_SEARCH = 0.012  # what one search costs (SPEC §9.1)
SEARCH_LIMIT = 15  # of ~30 Kagi returns; extra candidates because some good sites refuse our fetcher
FETCH_TIMEOUT_S = 15
MAX_EXCERPT_CHARS = 20_000
# A generic client name: no user or project details go to the sites we fetch.
USER_AGENT = "Mozilla/5.0 (compatible; Dialectic/0.1)"


def cache_get(conn, key):
    row = conn.execute("SELECT value FROM web_cache WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else None


def cache_put(conn, key, value):
    conn.execute(
        "INSERT OR REPLACE INTO web_cache (key, value, created_at) VALUES (?, ?, ?)",
        (key, json.dumps(value), db.now()),
    )
    conn.commit()


def clean_html(text):
    """Kagi snippets contain HTML (<strong>, &#39;): strip tags, unescape entities."""
    return html_lib.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def search(conn, meter, query):
    """Web search. Returns [{title, url, snippet}]. Only `query` leaves the server.
    An uncached search is paid: check the spending limits first, record it after (SPEC §9.1)."""
    key = f"search:{query}"
    cached = cache_get(conn, key)
    if cached is not None:
        return cached
    api_key = os.environ.get("KAGI_API_KEY")
    if not api_key:
        raise RuntimeError("KAGI_API_KEY is not set (put it in .env), or turn off 'AI may find sources' in the charter")
    meter.check("search")
    resp = httpx.post(
        KAGI_URL,
        json={"query": query},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=FETCH_TIMEOUT_S,
    )
    resp.raise_for_status()
    meter.record("search", 1, KAGI_USD_PER_SEARCH)
    # data.search holds the web results (about 30); video, infobox and related_search are ignored.
    results = [
        {"title": clean_html(item.get("title", "")), "url": item["url"], "snippet": clean_html(item.get("snippet") or "")}
        for item in resp.json()["data"]["search"][:SEARCH_LIMIT]
    ]
    cache_put(conn, key, results)
    return results


def download_page(url):
    """Fetch a page and extract its main text, with no caching. Returns {title, text};
    text is '' if extraction found nothing. Raises httpx.HTTPError if the site refuses."""
    resp = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=FETCH_TIMEOUT_S, follow_redirects=True)
    resp.raise_for_status()
    html = resp.text
    text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
    metadata = trafilatura.extract_metadata(html)
    title = (metadata.title if metadata and metadata.title else url)
    return {"title": title, "text": text[:MAX_EXCERPT_CHARS]}


def fetch_page(conn, url):
    """One page, cached. Used when the professor adds a source and by the seed."""
    key = f"page:{url}"
    cached = cache_get(conn, key)
    if cached is not None:
        return cached
    page = download_page(url)
    cache_put(conn, key, page)
    return page


def fetch_pages(conn, urls):
    """Several pages at once, so one slow site doesn't hold up the rest.

    Returns {url: page}, where page is {title, text}, or the httpx.HTTPError the site raised.
    Downloads run in threads; the cache is read and written here, on this thread, because
    a SQLite connection can't be shared across threads.
    """
    pages = {}
    to_download = []
    for url in urls:
        cached = cache_get(conn, f"page:{url}")
        if cached is not None:
            pages[url] = cached
        else:
            to_download.append(url)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {url: pool.submit(download_page, url) for url in to_download}
    for url, future in futures.items():
        try:
            pages[url] = future.result()
        except httpx.HTTPError as e:
            pages[url] = e
            continue
        cache_put(conn, f"page:{url}", pages[url])
    return pages
