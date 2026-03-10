"""Sample works from OpenAlex for each field/subfield and year."""

import json
from pathlib import Path

from .api import api_get
from .config import API_BASE, WORKS_PER_SAMPLE, YEARS


def sample_works(
    filter_str: str,
    year: int,
    n: int = WORKS_PER_SAMPLE,
    seed: int = 42,
) -> list[dict]:
    """Sample n works matching the filter for a given year.

    Handles pagination when n > 200 (OpenAlex per_page max).
    """
    per_page = min(n, 200)
    params = {
        "filter": f"{filter_str},publication_year:{year},referenced_works_count:>0",
        "select": "id,publication_year,referenced_works",
        "per_page": per_page,
        "sample": n,
        "seed": seed,
    }
    data = api_get(f"{API_BASE}/works", params)
    results = list(data.get("results", []))

    # Paginate if we need more than 200
    total_available = min(n, data.get("meta", {}).get("count", 0))
    page = 2
    while len(results) < total_available and len(results) < n:
        params_page = {**params, "page": page}
        page_data = api_get(f"{API_BASE}/works", params_page)
        new_results = page_data.get("results", [])
        if not new_results:
            break
        results.extend(new_results)
        page += 1

    return results[:n]


def sample_all_works(
    field_ids: dict,
    subfield_ids: dict,
    checkpoint_path: Path | None = None,
    years: list[int] | None = None,
    works_per_sample: int = WORKS_PER_SAMPLE,
) -> tuple[dict, dict, set]:
    """Sample works for all field-year and subfield-year combinations.

    Supports checkpointing: saves progress after each query so that
    a rate-limited run can be resumed by re-running.

    Args:
        field_ids: {field_name: openalex_id}
        subfield_ids: {subfield_name: openalex_id}
        checkpoint_path: Path to save/load checkpoint JSON.
        years: Override default year range.
        works_per_sample: Override default sample size.

    Returns:
        field_works: {(field_name, year): [works]}
        subfield_works: {(subfield_name, year): [works]}
        all_ref_ids: set of all referenced work IDs
    """
    _years = years or YEARS

    # Load checkpoint if it exists
    checkpoint = {}
    if checkpoint_path and checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text())
        print(f"  Loaded checkpoint with {len(checkpoint)} completed queries")

    field_works = {}
    subfield_works = {}
    all_ref_ids = set()

    # Restore completed work from checkpoint
    for key_str, works in checkpoint.items():
        name, year_str = key_str.rsplit("|", 1)
        year = int(year_str)
        if name in field_ids:
            field_works[(name, year)] = works
        elif name in subfield_ids:
            subfield_works[(name, year)] = works
        for w in works:
            all_ref_ids.update(w.get("referenced_works", []))

    total_field = len(field_ids) * len(_years)
    total_sub = len(subfield_ids) * len(_years)
    total = total_field + total_sub
    done = len(checkpoint)

    print(f"\nSampling works: {total} queries ({done} already done)")

    i = done
    for name, fid in field_ids.items():
        for year in _years:
            key = f"{name}|{year}"
            if key in checkpoint:
                continue
            i += 1
            if i % 20 == 0 or i == done + 1:
                print(f"  [{i}/{total}] Sampling {name} / {year}...")
            works = sample_works(f"topics.field.id:{fid}", year, n=works_per_sample)
            field_works[(name, year)] = works
            for w in works:
                all_ref_ids.update(w.get("referenced_works", []))

            # Save checkpoint
            if checkpoint_path:
                checkpoint[key] = works
                checkpoint_path.write_text(json.dumps(checkpoint))

    for name, sid in subfield_ids.items():
        for year in _years:
            key = f"{name}|{year}"
            if key in checkpoint:
                continue
            i += 1
            if i % 20 == 0:
                print(f"  [{i}/{total}] Sampling {name} / {year}...")
            works = sample_works(f"topics.subfield.id:{sid}", year, n=works_per_sample)
            subfield_works[(name, year)] = works
            for w in works:
                all_ref_ids.update(w.get("referenced_works", []))

            if checkpoint_path:
                checkpoint[key] = works
                checkpoint_path.write_text(json.dumps(checkpoint))

    print(f"  Collected {len(all_ref_ids):,} unique referenced work IDs")
    return field_works, subfield_works, all_ref_ids
