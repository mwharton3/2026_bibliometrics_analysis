# Data

## Overview

The dataset is not committed to this repository due to its size (~500 MB for caches, plus the CSV). It cost approximately **$20 in OpenAlex API credits** to build. The pipeline is fully reproducible — running `python -m bibliometrics.cli` will regenerate the dataset from scratch, though it takes several hours due to the volume of API calls (~169K requests cached).

## Output Dataset

**File:** `data/reference_age_dataset_1000.csv`

A CSV with 416 rows capturing reference age statistics for 8 academic fields and 8 subfields, annually from 2000 to 2025.

### Schema

| Column | Type | Description |
|--------|------|-------------|
| `year` | int | Publication year (2000–2025) |
| `field` | string | OpenAlex field name |
| `subfield` | string | `"All"` for field-level aggregations, otherwise the subfield name |
| `median_ref_age` | float | Mean of per-paper median reference ages (years) |
| `mean_ref_age` | float | Mean of per-paper mean reference ages (years) |
| `p25` | float | Mean of per-paper 25th-percentile reference ages (years) |
| `p75` | float | Mean of per-paper 75th-percentile reference ages (years) |
| `n_papers` | int | Number of papers contributing to the statistics |
| `n_references` | int | Total resolved reference ages used in computation |
| `total_refs` | int | Total references before resolution (including unresolved) |
| `ref_resolution_rate` | float | Fraction of references with a resolved publication year |

### Fields Covered

- Agricultural and Biological Sciences
- Chemistry
- Computer Science
- Economics, Econometrics and Finance
- Mathematics
- Medicine
- Physics and Astronomy
- Psychology

### Subfields Covered

| Subfield | Parent Field |
|----------|-------------|
| Applied Mathematics | Mathematics |
| Artificial Intelligence | Computer Science |
| Condensed Matter Physics | Physics and Astronomy |
| Ecology, Evolution, Behavior and Systematics | Agricultural and Biological Sciences |
| Economics and Econometrics | Economics, Econometrics and Finance |
| Genetics | Medicine |
| Organic Chemistry | Chemistry |
| Pharmacology | Pharmacology, Toxicology and Pharmaceutics |

### Summary Statistics

- **416 rows** (208 field-level + 208 subfield-level)
- **1,000 papers sampled** per (field/subfield, year) group
- **11.5 million** resolved reference ages from **12.7 million** total references
- **6.29 million** unique referenced works resolved
- Reference resolution rate: min 79.3%, median 92.0%, max 97.5%
- Median reference age range: 5.0–12.0 years across all groups
- Mean reference age range: 8.3–18.3 years across all groups

## Intermediate/Cache Files

These files live in `data/` but are gitignored. They exist to make the pipeline resumable and avoid redundant API calls.

| File | Size | Description |
|------|------|-------------|
| `ref_years_cache.json` | ~252 MB | Lookup table mapping 6.29M OpenAlex work URLs to their publication year |
| `ref_ids_queried.json` | ~232 MB | List of all reference IDs already sent to the API (for resumability) |
| `cache/` | ~169K files | Raw cached OpenAlex API responses, keyed by MD5 hash of request URL + params |

### Legacy File

`data/reference_age_dataset.csv` (341 rows) is an earlier dataset built with only 50 papers per sample. It is superseded by `reference_age_dataset_1000.csv` and can be safely deleted.

## Reproducing the Dataset

```bash
uv run python -m bibliometrics.cli
```

The pipeline will:
1. Fetch field/subfield metadata from OpenAlex
2. Sample 1,000 works per (field/subfield, year) combination
3. Batch-resolve publication years for all referenced works
4. Compute statistics and write the CSV
5. Generate charts in `output/`

If interrupted, re-running the command resumes from the last checkpoint. Cached API responses in `data/cache/` are reused automatically.
