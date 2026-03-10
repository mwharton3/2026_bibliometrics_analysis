#!/usr/bin/env python3
"""Main entry point for the bibliometrics analysis."""

import pandas as pd

from .charts import create_field_chart, create_subfield_chart
from .config import (
    CACHE_DIR,
    DATA_DIR,
    FIELD_NAMES,
    OUTPUT_DIR,
    SUBFIELD_NAMES,
    WORKS_PER_SAMPLE,
)
from .metadata import fetch_metadata, select_ids
from .references import batch_lookup_years
from .sampling import sample_all_works
from .stats import build_dataset


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dataset_path = DATA_DIR / f"reference_age_dataset_{WORKS_PER_SAMPLE}.csv"
    checkpoint_path = DATA_DIR / f"sampling_checkpoint_{WORKS_PER_SAMPLE}.json"

    if dataset_path.exists():
        print(f"Dataset already exists at {dataset_path}. Loading...")
        df = pd.read_csv(dataset_path)
        print(f"  {len(df)} rows loaded.")
    else:
        # Step 1: Fetch metadata
        field_map, subfield_map, subfield_to_field = fetch_metadata()
        field_ids = select_ids(FIELD_NAMES, field_map, "field")
        subfield_ids = select_ids(SUBFIELD_NAMES, subfield_map, "subfield")

        # Step 2: Sample works (with checkpointing)
        field_works, subfield_works, all_ref_ids = sample_all_works(
            field_ids,
            subfield_ids,
            checkpoint_path=checkpoint_path,
            works_per_sample=WORKS_PER_SAMPLE,
        )

        # Step 3: Batch lookup referenced work years
        ref_years = batch_lookup_years(all_ref_ids)

        # Step 4: Build dataset
        df = build_dataset(field_works, subfield_works, ref_years, subfield_to_field)
        df.to_csv(dataset_path, index=False)
        print(f"\nDataset saved to {dataset_path} ({len(df)} rows)")

        # Clean up checkpoint on success
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            print("  Removed sampling checkpoint (complete).")

    # Step 5: Create charts
    print("\nCreating charts...")
    create_field_chart(df)
    create_subfield_chart(df)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Dataset: {dataset_path}")
    print(f"Charts:  {OUTPUT_DIR}/reference_age_by_field.png")
    print(f"         {OUTPUT_DIR}/reference_age_by_subfield.png")
    print(f"\nDataset shape: {df.shape}")
    print(f"Year range: {df['year'].min()} - {df['year'].max()}")
    print(f"Fields: {df[df['subfield'] == 'All']['field'].nunique()}")
    print(f"Subfields: {df[df['subfield'] != 'All']['subfield'].nunique()}")
    if "ref_resolution_rate" in df.columns:
        print(
            f"\nRef resolution rate: "
            f"min={df['ref_resolution_rate'].min():.1%}, "
            f"median={df['ref_resolution_rate'].median():.1%}, "
            f"mean={df['ref_resolution_rate'].mean():.1%}"
        )
    print("\nSample rows:")
    print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
