# Bibliometrics Analysis: Reference Age Trends

Analyzes how the age of cited references in academic papers has changed over time across fields and subfields, using data from the [OpenAlex](https://openalex.org/) API.

## What It Does

This project samples scholarly works from OpenAlex for each year from 2000–2025, computes the age of every cited reference (publication year of citing paper minus publication year of cited paper), and produces summary statistics and trend charts. The result is a dataset and two visualizations showing how "citation recency" varies by discipline.

## Output

- **`data/reference_age_dataset.csv`** — Core dataset with columns: `year`, `field`, `subfield`, `median_ref_age`, `mean_ref_age`, `p25`, `p75`, `n_papers`, `n_references`, `total_refs`, `ref_resolution_rate`
- **`output/reference_age_by_field.png`** — Trend chart of median reference age (with IQR bands) across 8 academic fields
- **`output/reference_age_by_subfield.png`** — Same chart for 8 selected subfields

## Fields and Subfields Analyzed

**Fields:** Computer Science, Medicine, Physics and Astronomy, Mathematics, Chemistry, Economics/Econometrics/Finance, Agricultural and Biological Sciences, Psychology

**Subfields:** Artificial Intelligence, Ecology/Evolution/Behavior/Systematics, Organic Chemistry, Condensed Matter Physics, Applied Mathematics, Economics and Econometrics, Pharmacology, Genetics

## Methodology

### 1. Fetch Topic Metadata

The script queries the OpenAlex `/fields` and `/subfields` endpoints to resolve display names (e.g., "Computer Science") to OpenAlex IDs (e.g., `fields/17`). Subfields are also mapped back to their parent field.

### 2. Sample Works

For each field-year and subfield-year combination, the script requests a **random sample of 50 works** from the OpenAlex `/works` endpoint using the `sample` parameter with a fixed seed (`seed=42`) for reproducibility. The filter requires `referenced_works_count:>0` so that every sampled work has at least one citation to analyze.

Example API call for Computer Science in 2020:

```
GET https://api.openalex.org/works?filter=topics.field.id:fields/17,publication_year:2020,referenced_works_count:>0&select=id,publication_year,referenced_works&per_page=50&sample=50&seed=42
```

This yields 416 queries total (8 fields x 26 years + 8 subfields x 26 years).

### 3. Resolve Reference Publication Years

Each sampled work includes a list of `referenced_works` (OpenAlex IDs of cited papers). To compute reference ages, the publication year of each cited work must be looked up. The script collects all unique referenced work IDs across the entire sample, then batch-queries the `/works` endpoint using the `openalex_id` filter with pipe-delimited IDs (up to 40 per batch).

Example batch lookup:

```
GET https://api.openalex.org/works?filter=openalex_id:W123|W456|W789&select=id,publication_year&per_page=200
```

Results are cached to `data/ref_years_cache.json` and IDs already queried (whether found or not) are tracked in `data/ref_ids_queried.json` to avoid redundant API calls on reruns.

### 4. Compute Reference Age Statistics

For each field/subfield-year combination, the script computes:

| Metric | Description |
|---|---|
| `median_ref_age` | Median of (citing year − cited year) across all resolved references |
| `mean_ref_age` | Mean reference age |
| `p25` | 25th percentile of reference age |
| `p75` | 75th percentile of reference age |
| `n_papers` | Number of works in the sample |
| `n_references` | Number of references with a resolved age |
| `ref_resolution_rate` | Fraction of total references successfully resolved to a year |

**Filtering rules:**
- Reference ages must be non-negative and ≤ 200 years (sanity bound)
- Data points with fewer than 10 resolved reference ages are dropped
- Data points where < 60% of references resolved to a publication year are dropped

### 5. Visualization

Two dual-panel PNG charts are generated:

- **Left panel:** 3-year rolling average of median reference age, with faint raw values
- **Right panel:** Smoothed median with shaded P25–P75 interquartile range

## OpenAlex API Interaction Details

- **Base URL:** `https://api.openalex.org`
- **Authentication:** None required. Optionally set the `MAILTO` variable in `bibliometrics.py` to an email address to join the [polite pool](https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication#the-polite-pool) for higher rate limits.
- **Rate limiting:** The script waits 0.2 seconds between requests (~5 req/s). On HTTP 429 responses, it backs off exponentially (2s, 4s, 8s).
- **Retries:** Each request is retried up to 3 times on failure with exponential backoff.
- **Caching:** Every API response is cached to `data/cache/` as a JSON file keyed by an MD5 hash of the URL + parameters. Subsequent runs skip already-cached requests entirely. Referenced work years are additionally cached in `data/ref_years_cache.json` for efficient cross-run persistence.
- **Endpoints used:**
  - `GET /fields` — list all fields with IDs and display names
  - `GET /subfields` — list all subfields (paginated, 50 per page)
  - `GET /works` — sample works by field/subfield and year; batch-resolve reference publication years

## Setup and Usage

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
# Install dependencies
uv sync

# Run the analysis
uv run python bibliometrics.py
```

On the first run, the script will make ~2,000–5,000+ API calls (depending on how many unique references need resolving) and cache everything locally. Subsequent runs reuse cached data and skip to chart generation.
