"""Batch lookup publication years for referenced works."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .api import api_get
from .config import API_BASE, BATCH_SIZE, DATA_DIR

# Number of concurrent API requests
CONCURRENCY = 10


def _lookup_batch(batch: list[str]) -> dict:
    """Look up publication years for a single batch of IDs. Returns {id: year}."""
    short_ids = [url.replace("https://openalex.org/", "") for url in batch]
    filter_val = "|".join(short_ids)
    params = {
        "filter": f"openalex_id:{filter_val}",
        "select": "id,publication_year",
        "per_page": 200,
    }

    results = {}
    data = api_get(f"{API_BASE}/works", params)
    for w in data.get("results", []):
        results[w["id"]] = w.get("publication_year")

    # Handle pagination if needed
    count = data.get("meta", {}).get("count", 0)
    if count > 200:
        cursor = "*"
        while True:
            params["cursor"] = cursor
            params.pop("page", None)
            page_data = api_get(f"{API_BASE}/works", params)
            for w in page_data.get("results", []):
                results[w["id"]] = w.get("publication_year")
            cursor = page_data.get("meta", {}).get("next_cursor")
            if not cursor or not page_data.get("results"):
                break

    return results


def batch_lookup_years(
    ref_ids: set,
    data_dir: Path | None = None,
    batch_size: int = BATCH_SIZE,
    save_interval: int = 500,
    concurrency: int = CONCURRENCY,
) -> dict:
    """Look up publication years for referenced works in concurrent batches.

    Maintains two persistent caches:
      - ref_years_cache.json: {id: publication_year} for resolved IDs
      - ref_ids_queried.json: list of IDs already sent to the API

    Args:
        ref_ids: Set of OpenAlex work URLs to look up.
        data_dir: Override default data directory.
        batch_size: Number of IDs per API request.
        save_interval: Save caches every N batches.
        concurrency: Number of parallel requests.

    Returns:
        {openalex_url: publication_year} for all resolved IDs.
    """
    _data_dir = data_dir or DATA_DIR
    ref_years_path = _data_dir / "ref_years_cache.json"
    queried_path = _data_dir / "ref_ids_queried.json"

    if ref_years_path.exists():
        ref_years = json.loads(ref_years_path.read_text())
    else:
        ref_years = {}

    if queried_path.exists():
        queried_ids = set(json.loads(queried_path.read_text()))
    else:
        queried_ids = set(ref_years.keys())

    remaining = ref_ids - queried_ids
    print(
        f"  Loaded {len(ref_years):,} cached ref years, "
        f"{len(queried_ids):,} previously queried, "
        f"{len(remaining):,} new IDs to look up"
    )

    if not remaining:
        return ref_years

    ref_list = sorted(remaining)
    # Build all batches upfront
    batches = []
    for i in range(0, len(ref_list), batch_size):
        batches.append(ref_list[i : i + batch_size])

    n_batches = len(batches)
    print(f"\nLooking up publication years: {len(ref_list):,} IDs in {n_batches} batches ({concurrency} concurrent)")

    lock = threading.Lock()
    completed = 0

    def _save_progress():
        ref_years_path.write_text(json.dumps(ref_years))
        queried_path.write_text(json.dumps(sorted(queried_ids)))

    try:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {}
            for batch_i, batch in enumerate(batches):
                fut = pool.submit(_lookup_batch, batch)
                futures[fut] = (batch_i, batch)

            for fut in as_completed(futures):
                batch_i, batch = futures[fut]
                try:
                    result = fut.result()
                    with lock:
                        ref_years.update(result)
                        queried_ids.update(batch)
                        completed += 1

                        if completed % save_interval == 0 or completed == 1:
                            pct = 100 * completed / n_batches
                            print(f"  Completed [{completed}/{n_batches}] ({pct:.0f}%) — {len(ref_years):,} ref years")
                            _save_progress()

                except Exception as e:
                    with lock:
                        completed += 1
                        print(f"  Warning: batch {batch_i} failed: {e}")
                        # Mark as queried to avoid infinite retry loops on bad IDs
                        queried_ids.update(batch)

    except KeyboardInterrupt:
        print(f"\n  Interrupted! Saving progress...")
        _save_progress()
        print(f"  Saved {len(ref_years):,} ref years. Re-run to resume.")
        raise

    _save_progress()
    print(f"  Done. {len(ref_years):,} resolved out of {len(queried_ids):,} queried.")
    return ref_years
