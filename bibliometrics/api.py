"""HTTP client with file-based caching and retry/rate-limit handling."""

import hashlib
import json
import time
from pathlib import Path

import requests

from .config import API_KEY, CACHE_DIR, MAILTO, REQUEST_DELAY


def _cache_key(url: str, params: dict) -> str:
    raw = url + json.dumps(params, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def api_get(
    url: str,
    params: dict | None = None,
    retries: int = 6,
    cache_dir: Path | None = None,
    request_delay: float | None = None,
    mailto: str | None = None,
) -> dict:
    """GET from OpenAlex API with file-based caching and retry logic.

    Args:
        url: API endpoint URL.
        params: Query parameters.
        retries: Max retry attempts on failure.
        cache_dir: Override default cache directory (useful for testing).
        request_delay: Override default delay between requests.
        mailto: Override default mailto for polite pool.

    Returns:
        Parsed JSON response.

    Raises:
        RuntimeError: If all retries exhausted.
    """
    params = dict(params) if params else {}
    _mailto = mailto if mailto is not None else MAILTO
    if _mailto:
        params["mailto"] = _mailto
    if API_KEY:
        params["api_key"] = API_KEY

    _cache_dir = cache_dir if cache_dir is not None else CACHE_DIR
    _delay = request_delay if request_delay is not None else REQUEST_DELAY

    # Cache key excludes auth params so cached responses are reusable
    cache_params = {k: v for k, v in params.items() if k not in ("api_key", "mailto")}
    key = _cache_key(url, cache_params)
    cache_path = _cache_dir / f"{key}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text())

    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                # Use Retry-After header if available, otherwise exponential backoff
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    wait = int(retry_after) + 1
                else:
                    wait = min(2 ** (attempt + 2), 60)
                print(f"  Rate limited, waiting {wait}s... (attempt {attempt + 1}/{retries})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            _cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(data))
            time.sleep(_delay)
            return data
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                raise
            wait = min(2 ** (attempt + 1), 30)
            print(f"  Request error ({e}), retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"Failed after {retries} retries: {url}")
