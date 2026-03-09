#!/usr/bin/env python3
"""Bibliometrics Analysis: Reference Age Trends by Field and Subfield.

Fetches scholarly works data from the OpenAlex API, computes reference age
statistics (median, mean, P25, P75), and generates trend charts by field
and subfield.
"""

import hashlib
import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
import requests
import seaborn as sns

# ── Configuration ──────────────────────────────────────────────────────────────

API_BASE = "https://api.openalex.org"
DATA_DIR = Path("data")
CACHE_DIR = DATA_DIR / "cache"
OUTPUT_DIR = Path("output")

YEARS = list(range(2000, 2026))
WORKS_PER_SAMPLE = 50  # works sampled per field/subfield per year (increase for higher fidelity)
BATCH_SIZE = 40  # max IDs per batch ref-year lookup (keep URLs short)
REQUEST_DELAY = 0.2  # seconds between API calls (~5 req/s, conservative)
MIN_REF_RESOLUTION_RATE = 0.6  # drop data points where <60% of refs resolved

# Optional: set your email for the OpenAlex "polite pool" (faster rate limits)
MAILTO = ""

# Fields to analyze (display_name → looked up dynamically)
FIELD_NAMES = [
    "Computer Science",
    "Medicine",
    "Physics and Astronomy",
    "Mathematics",
    "Chemistry",
    "Economics, Econometrics and Finance",
    "Agricultural and Biological Sciences",
    "Psychology",
]

# Subfields to analyze
SUBFIELD_NAMES = [
    "Artificial Intelligence",
    "Ecology, Evolution, Behavior and Systematics",
    "Organic Chemistry",
    "Condensed Matter Physics",
    "Applied Mathematics",
    "Economics and Econometrics",
    "Pharmacology",
    "Genetics",
]

# ── API helpers ────────────────────────────────────────────────────────────────


def _cache_key(url: str, params: dict) -> str:
    raw = url + json.dumps(params, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def api_get(url: str, params: dict | None = None, retries: int = 3) -> dict:
    """GET from OpenAlex API with file-based caching and retry logic."""
    params = params or {}
    if MAILTO:
        params["mailto"] = MAILTO

    key = _cache_key(url, params)
    cache_path = CACHE_DIR / f"{key}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text())

    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            cache_path.write_text(json.dumps(data))
            time.sleep(REQUEST_DELAY)
            return data
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                raise
            print(f"  Request error ({e}), retrying in {2 ** attempt}s...")
            time.sleep(2 ** attempt)

    raise RuntimeError(f"Failed after {retries} retries: {url}")


# ── Step 1: Fetch field/subfield metadata ──────────────────────────────────────


def fetch_metadata() -> tuple[dict, dict]:
    """Fetch all fields and subfields, return {name: id} mappings."""
    print("Fetching field metadata...")
    fields_data = api_get(f"{API_BASE}/fields", {"per_page": 50})
    field_map = {}
    for f in fields_data["results"]:
        short_id = f["id"].replace("https://openalex.org/", "")
        field_map[f["display_name"]] = short_id

    print("Fetching subfield metadata...")
    all_subfields = []
    page = 1
    while True:
        data = api_get(f"{API_BASE}/subfields", {"per_page": 50, "page": page})
        all_subfields.extend(data["results"])
        if len(all_subfields) >= data["meta"]["count"]:
            break
        page += 1

    subfield_map = {}
    subfield_to_field = {}
    for s in all_subfields:
        short_id = s["id"].replace("https://openalex.org/", "")
        subfield_map[s["display_name"]] = short_id
        field_short = s["field"]["id"].replace("https://openalex.org/", "")
        subfield_to_field[s["display_name"]] = (
            field_short,
            s["field"]["display_name"],
        )

    return field_map, subfield_map, subfield_to_field


# ── Step 2: Sample works ──────────────────────────────────────────────────────


def sample_works(filter_str: str, year: int, n: int = WORKS_PER_SAMPLE) -> list[dict]:
    """Sample n works matching the filter for a given year."""
    params = {
        "filter": f"{filter_str},publication_year:{year},referenced_works_count:>0",
        "select": "id,publication_year,referenced_works",
        "per_page": min(n, 200),
        "sample": n,
        "seed": 42,
    }
    data = api_get(f"{API_BASE}/works", params)
    return data.get("results", [])


def sample_all_works(
    field_ids: dict, subfield_ids: dict
) -> tuple[dict, dict, set]:
    """
    Sample works for all field-year and subfield-year combinations.

    Returns:
        field_works: {(field_name, year): [works]}
        subfield_works: {(subfield_name, year): [works]}
        all_ref_ids: set of all referenced work IDs
    """
    field_works = {}
    subfield_works = {}
    all_ref_ids = set()

    total_field = len(field_ids) * len(YEARS)
    total_sub = len(subfield_ids) * len(YEARS)
    total = total_field + total_sub

    print(f"\nSampling works: {total} queries ({total_field} field + {total_sub} subfield)")

    i = 0
    for name, fid in field_ids.items():
        for year in YEARS:
            i += 1
            if i % 20 == 0 or i == 1:
                print(f"  [{i}/{total}] Sampling {name} / {year}...")
            works = sample_works(f"topics.field.id:{fid}", year)
            field_works[(name, year)] = works
            for w in works:
                all_ref_ids.update(w.get("referenced_works", []))

    for name, sid in subfield_ids.items():
        for year in YEARS:
            i += 1
            if i % 20 == 0:
                print(f"  [{i}/{total}] Sampling {name} / {year}...")
            works = sample_works(f"topics.subfield.id:{sid}", year)
            subfield_works[(name, year)] = works
            for w in works:
                all_ref_ids.update(w.get("referenced_works", []))

    print(f"  Collected {len(all_ref_ids):,} unique referenced work IDs")
    return field_works, subfield_works, all_ref_ids


# ── Step 3: Batch lookup publication years ─────────────────────────────────────


def batch_lookup_years(ref_ids: set) -> dict:
    """Look up publication years for referenced works in batches.

    Maintains two caches:
      - ref_years_cache.json: {id: publication_year} for successfully resolved IDs
      - ref_ids_queried.json: list of IDs already sent to the API (hit or miss)

    IDs that were queried but not found are not re-queried on subsequent runs.
    """
    ref_years_path = DATA_DIR / "ref_years_cache.json"
    queried_path = DATA_DIR / "ref_ids_queried.json"

    # Load existing caches
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
    n_batches = (len(ref_list) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"\nLooking up publication years: {len(ref_list):,} IDs in {n_batches} batches")

    for batch_i in range(n_batches):
        start = batch_i * BATCH_SIZE
        end = start + BATCH_SIZE
        batch = ref_list[start:end]

        if (batch_i + 1) % 200 == 0 or batch_i == 0:
            pct = 100 * (batch_i + 1) / n_batches
            print(f"  Batch [{batch_i + 1}/{n_batches}] ({pct:.0f}%)...")

        # Use short-form IDs (W12345) to keep URL length manageable
        short_ids = [url.replace("https://openalex.org/", "") for url in batch]
        filter_val = "|".join(short_ids)
        params = {
            "filter": f"openalex_id:{filter_val}",
            "select": "id,publication_year",
            "per_page": 200,
        }

        try:
            data = api_get(f"{API_BASE}/works", params)
            for w in data.get("results", []):
                ref_years[w["id"]] = w.get("publication_year")

            # Mark all IDs in this batch as queried (found or not)
            queried_ids.update(batch)

            # Handle pagination if needed
            meta = data.get("meta", {})
            count = meta.get("count", 0)
            if count > 200:
                cursor = "*"
                while True:
                    params["cursor"] = cursor
                    params.pop("page", None)
                    page_data = api_get(f"{API_BASE}/works", params)
                    for w in page_data.get("results", []):
                        ref_years[w["id"]] = w.get("publication_year")
                    cursor = page_data.get("meta", {}).get("next_cursor")
                    if not cursor or not page_data.get("results"):
                        break

        except Exception as e:
            print(f"  Warning: batch {batch_i} failed: {e}")
            continue

        # Periodic save
        if (batch_i + 1) % 200 == 0:
            ref_years_path.write_text(json.dumps(ref_years))
            queried_path.write_text(json.dumps(sorted(queried_ids)))
            print(f"  Saved {len(ref_years):,} ref years to cache")

    # Final save
    ref_years_path.write_text(json.dumps(ref_years))
    queried_path.write_text(json.dumps(sorted(queried_ids)))
    print(f"  Done. {len(ref_years):,} resolved out of {len(queried_ids):,} queried.")
    return ref_years


# ── Step 4: Compute reference age statistics ───────────────────────────────────


def compute_stats(works: list[dict], ref_years: dict) -> dict | None:
    """Compute reference age statistics for a set of works.

    Tracks the fraction of references that successfully resolved to a
    publication year so callers can filter out unreliable data points.
    """
    ages = []
    total_refs = 0
    resolved_refs = 0
    for w in works:
        pub_year = w["publication_year"]
        refs = w.get("referenced_works", [])
        total_refs += len(refs)
        for ref_id in refs:
            ref_year = ref_years.get(ref_id)
            if ref_year is not None:
                resolved_refs += 1
                if ref_year <= pub_year:
                    age = pub_year - ref_year
                    if 0 <= age <= 200:  # sanity check
                        ages.append(age)

    if len(ages) < 10:
        return None

    resolution_rate = resolved_refs / total_refs if total_refs > 0 else 0.0
    ages_arr = np.array(ages)
    return {
        "median_ref_age": float(np.median(ages_arr)),
        "mean_ref_age": float(np.mean(ages_arr)),
        "p25": float(np.percentile(ages_arr, 25)),
        "p75": float(np.percentile(ages_arr, 75)),
        "n_papers": len(works),
        "n_references": len(ages),
        "total_refs": total_refs,
        "ref_resolution_rate": round(resolution_rate, 3),
    }


def build_dataset(
    field_works: dict,
    subfield_works: dict,
    ref_years: dict,
    subfield_to_field: dict,
) -> pd.DataFrame:
    """Build the full dataset with reference age statistics."""
    rows = []
    dropped = 0

    print("\nComputing reference age statistics...")

    # Field-level stats
    for (field_name, year), works in field_works.items():
        stats = compute_stats(works, ref_years)
        if stats:
            if stats["ref_resolution_rate"] < MIN_REF_RESOLUTION_RATE:
                dropped += 1
                continue
            rows.append(
                {
                    "year": year,
                    "field": field_name,
                    "subfield": "All",
                    **stats,
                }
            )

    # Subfield-level stats
    for (subfield_name, year), works in subfield_works.items():
        stats = compute_stats(works, ref_years)
        if stats:
            if stats["ref_resolution_rate"] < MIN_REF_RESOLUTION_RATE:
                dropped += 1
                continue
            field_info = subfield_to_field.get(subfield_name, ("", "Unknown"))
            rows.append(
                {
                    "year": year,
                    "field": field_info[1],
                    "subfield": subfield_name,
                    **stats,
                }
            )

    if dropped:
        print(
            f"  Dropped {dropped} data points with ref resolution rate "
            f"< {MIN_REF_RESOLUTION_RATE:.0%}"
        )

    df = pd.DataFrame(rows)
    return df


# ── Step 5: Create charts ─────────────────────────────────────────────────────


def _smooth(series, window=3):
    """Apply rolling average for smoother trend lines."""
    return series.rolling(window=window, center=True, min_periods=1).mean()


def create_field_chart(df: pd.DataFrame):
    """Create reference age trends chart by field."""
    field_df = df[df["subfield"] == "All"].copy()
    if field_df.empty:
        print("  No field-level data to plot!")
        return

    sns.set_theme(style="whitegrid", font_scale=1.1)
    palette = sns.color_palette("tab10", n_colors=field_df["field"].nunique())
    fig, axes = plt.subplots(1, 2, figsize=(18, 7))

    ax = axes[0]
    for i, (name, grp) in enumerate(sorted(field_df.groupby("field"))):
        grp = grp.sort_values("year")
        smoothed = _smooth(grp["median_ref_age"])
        ax.plot(grp["year"], smoothed, label=name, linewidth=2, color=palette[i])
        ax.plot(grp["year"], grp["median_ref_age"], alpha=0.2, linewidth=0.5, color=palette[i])
    ax.set_xlabel("Publication Year")
    ax.set_ylabel("Median Reference Age (years)")
    ax.set_title("Median Reference Age by Field (3-yr smoothed)")
    ax.legend(fontsize=7, loc="upper left")
    ax.xaxis.set_major_locator(ticker.MultipleLocator(5))

    ax = axes[1]
    for i, (name, grp) in enumerate(sorted(field_df.groupby("field"))):
        grp = grp.sort_values("year")
        sm_median = _smooth(grp["median_ref_age"])
        sm_p25 = _smooth(grp["p25"])
        sm_p75 = _smooth(grp["p75"])
        ax.fill_between(grp["year"], sm_p25, sm_p75, alpha=0.12, color=palette[i])
        ax.plot(grp["year"], sm_median, label=name, linewidth=2, color=palette[i])
    ax.set_xlabel("Publication Year")
    ax.set_ylabel("Reference Age (years)")
    ax.set_title("Reference Age Distribution by Field (Median + IQR)")
    ax.legend(fontsize=7, loc="upper left")
    ax.xaxis.set_major_locator(ticker.MultipleLocator(5))

    year_lo = int(field_df["year"].min())
    year_hi = int(field_df["year"].max())
    fig.suptitle(
        f"Reference Age Trends by Academic Field ({year_lo}-{year_hi})\n"
        f"Source: OpenAlex API | Min {MIN_REF_RESOLUTION_RATE:.0%} reference resolution rate",
        fontsize=13, fontweight="bold",
    )
    plt.tight_layout()
    out_path = OUTPUT_DIR / "reference_age_by_field.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


def create_subfield_chart(df: pd.DataFrame):
    """Create reference age trends chart by subfield."""
    sub_df = df[df["subfield"] != "All"].copy()
    if sub_df.empty:
        print("  No subfield-level data to plot!")
        return

    sns.set_theme(style="whitegrid", font_scale=1.1)
    palette = sns.color_palette("tab10", n_colors=sub_df["subfield"].nunique())
    fig, axes = plt.subplots(1, 2, figsize=(18, 7))

    ax = axes[0]
    for i, (name, grp) in enumerate(sorted(sub_df.groupby("subfield"))):
        grp = grp.sort_values("year")
        smoothed = _smooth(grp["median_ref_age"])
        ax.plot(grp["year"], smoothed, label=name, linewidth=2, color=palette[i])
        ax.plot(grp["year"], grp["median_ref_age"], alpha=0.2, linewidth=0.5, color=palette[i])
    ax.set_xlabel("Publication Year")
    ax.set_ylabel("Median Reference Age (years)")
    ax.set_title("Median Reference Age by Subfield (3-yr smoothed)")
    ax.legend(fontsize=7, loc="upper left")
    ax.xaxis.set_major_locator(ticker.MultipleLocator(5))

    ax = axes[1]
    for i, (name, grp) in enumerate(sorted(sub_df.groupby("subfield"))):
        grp = grp.sort_values("year")
        sm_median = _smooth(grp["median_ref_age"])
        sm_p25 = _smooth(grp["p25"])
        sm_p75 = _smooth(grp["p75"])
        ax.fill_between(grp["year"], sm_p25, sm_p75, alpha=0.12, color=palette[i])
        ax.plot(grp["year"], sm_median, label=name, linewidth=2, color=palette[i])
    ax.set_xlabel("Publication Year")
    ax.set_ylabel("Reference Age (years)")
    ax.set_title("Reference Age Distribution by Subfield (Median + IQR)")
    ax.legend(fontsize=7, loc="upper left")
    ax.xaxis.set_major_locator(ticker.MultipleLocator(5))

    year_lo = int(sub_df["year"].min())
    year_hi = int(sub_df["year"].max())
    fig.suptitle(
        f"Reference Age Trends by Academic Subfield ({year_lo}-{year_hi})\n"
        f"Source: OpenAlex API | Min {MIN_REF_RESOLUTION_RATE:.0%} reference resolution rate",
        fontsize=13, fontweight="bold",
    )
    plt.tight_layout()
    out_path = OUTPUT_DIR / "reference_age_by_subfield.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    # Setup
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dataset_path = DATA_DIR / "reference_age_dataset.csv"

    # Check if dataset already exists
    if dataset_path.exists():
        print(f"Dataset already exists at {dataset_path}. Loading...")
        df = pd.read_csv(dataset_path)
        print(f"  {len(df)} rows loaded.")
    else:
        # Step 1: Fetch metadata
        field_map, subfield_map, subfield_to_field = fetch_metadata()

        # Select target fields
        field_ids = {}
        for name in FIELD_NAMES:
            if name in field_map:
                field_ids[name] = field_map[name]
            else:
                print(f"  Warning: field '{name}' not found. Available: {list(field_map.keys())[:5]}...")
        print(f"Selected {len(field_ids)} fields: {list(field_ids.keys())}")

        # Select target subfields
        subfield_ids = {}
        for name in SUBFIELD_NAMES:
            if name in subfield_map:
                subfield_ids[name] = subfield_map[name]
            else:
                print(f"  Warning: subfield '{name}' not found.")
        print(f"Selected {len(subfield_ids)} subfields: {list(subfield_ids.keys())}")

        # Step 2: Sample works
        field_works, subfield_works, all_ref_ids = sample_all_works(field_ids, subfield_ids)

        # Step 3: Batch lookup referenced work years
        ref_years = batch_lookup_years(all_ref_ids)

        # Step 4: Build dataset
        df = build_dataset(field_works, subfield_works, ref_years, subfield_to_field)
        df.to_csv(dataset_path, index=False)
        print(f"\nDataset saved to {dataset_path} ({len(df)} rows)")

    # Step 5: Create charts
    print("\nCreating charts...")
    create_field_chart(df)
    create_subfield_chart(df)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Dataset: {dataset_path}")
    print(f"Charts:  {OUTPUT_DIR}/reference_age_by_field.png")
    print(f"         {OUTPUT_DIR}/reference_age_by_subfield.png")
    print(f"\nDataset shape: {df.shape}")
    print(f"Year range: {df['year'].min()} – {df['year'].max()}")
    print(f"Fields: {df[df['subfield'] == 'All']['field'].nunique()}")
    print(f"Subfields: {df[df['subfield'] != 'All']['subfield'].nunique()}")
    if "ref_resolution_rate" in df.columns:
        print(f"\nRef resolution rate: "
              f"min={df['ref_resolution_rate'].min():.1%}, "
              f"median={df['ref_resolution_rate'].median():.1%}, "
              f"mean={df['ref_resolution_rate'].mean():.1%}")
    print("\nSample rows:")
    print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
