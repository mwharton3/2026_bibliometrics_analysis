"""Compute reference age statistics and build the output dataset."""

import numpy as np
import pandas as pd

from .config import MIN_REF_RESOLUTION_RATE


def compute_stats(works: list[dict], ref_years: dict) -> dict | None:
    """Compute reference age statistics for a set of works.

    Computes per-paper median/mean/p25/p75 reference ages, then averages
    across papers. This avoids integer quantization artifacts that occur
    when pooling all reference ages into a single flat list (since ages
    are integer year-differences, the pooled median almost always lands
    on an exact integer).

    Args:
        works: List of work dicts with 'publication_year' and 'referenced_works'.
        ref_years: {openalex_url: publication_year} lookup.

    Returns:
        Dict of stats or None if insufficient data.
    """
    paper_medians = []
    paper_means = []
    paper_p25s = []
    paper_p75s = []
    total_refs = 0
    resolved_refs = 0
    total_valid_ages = 0

    for w in works:
        pub_year = w["publication_year"]
        refs = w.get("referenced_works", [])
        total_refs += len(refs)
        paper_ages = []
        for ref_id in refs:
            ref_year = ref_years.get(ref_id)
            if ref_year is not None:
                resolved_refs += 1
                if ref_year <= pub_year:
                    age = pub_year - ref_year
                    if 0 <= age <= 200:
                        paper_ages.append(age)

        if len(paper_ages) >= 3:
            arr = np.array(paper_ages)
            paper_medians.append(float(np.median(arr)))
            paper_means.append(float(np.mean(arr)))
            paper_p25s.append(float(np.percentile(arr, 25)))
            paper_p75s.append(float(np.percentile(arr, 75)))
            total_valid_ages += len(paper_ages)

    if len(paper_medians) < 5:
        return None

    resolution_rate = resolved_refs / total_refs if total_refs > 0 else 0.0
    return {
        "median_ref_age": float(np.mean(paper_medians)),
        "mean_ref_age": float(np.mean(paper_means)),
        "p25": float(np.mean(paper_p25s)),
        "p75": float(np.mean(paper_p75s)),
        "n_papers": len(paper_medians),
        "n_references": total_valid_ages,
        "total_refs": total_refs,
        "ref_resolution_rate": round(resolution_rate, 3),
    }


def build_dataset(
    field_works: dict,
    subfield_works: dict,
    ref_years: dict,
    subfield_to_field: dict,
    min_resolution_rate: float = MIN_REF_RESOLUTION_RATE,
) -> pd.DataFrame:
    """Build the full dataset with reference age statistics.

    Args:
        field_works: {(field_name, year): [works]}
        subfield_works: {(subfield_name, year): [works]}
        ref_years: {openalex_url: publication_year}
        subfield_to_field: {subfield_name: (field_id, field_name)}
        min_resolution_rate: Drop rows below this threshold.

    Returns:
        DataFrame with columns: year, field, subfield, median_ref_age,
        mean_ref_age, p25, p75, n_papers, n_references, total_refs,
        ref_resolution_rate.
    """
    rows = []
    dropped = 0

    print("\nComputing reference age statistics...")

    for (field_name, year), works in field_works.items():
        stats = compute_stats(works, ref_years)
        if stats:
            if stats["ref_resolution_rate"] < min_resolution_rate:
                dropped += 1
                continue
            rows.append({"year": year, "field": field_name, "subfield": "All", **stats})

    for (subfield_name, year), works in subfield_works.items():
        stats = compute_stats(works, ref_years)
        if stats:
            if stats["ref_resolution_rate"] < min_resolution_rate:
                dropped += 1
                continue
            field_info = subfield_to_field.get(subfield_name, ("", "Unknown"))
            rows.append({
                "year": year,
                "field": field_info[1],
                "subfield": subfield_name,
                **stats,
            })

    if dropped:
        print(f"  Dropped {dropped} data points with ref resolution rate < {min_resolution_rate:.0%}")

    return pd.DataFrame(rows)
