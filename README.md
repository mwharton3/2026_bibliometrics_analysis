# Bibliometrics Analysis: Reference Age Trends

Analyzes how the age of cited references in academic papers has changed over time across fields and subfields, using data from the [OpenAlex](https://openalex.org/) API.

## What It Does

This project samples scholarly works from OpenAlex for each year from 2000–2025, computes the age of every cited reference (publication year of citing paper minus publication year of cited paper), and produces summary statistics and trend charts. The result is a dataset and visualizations showing how "citation recency" varies by discipline.

## Output

- **`data/reference_age_dataset_1000.csv`** — Core dataset with columns: `year`, `field`, `subfield`, `median_ref_age`, `mean_ref_age`, `p25`, `p75`, `n_papers`, `n_references`, `total_refs`, `ref_resolution_rate`
- **`output/reference_age_by_field.png`** — Trend chart of mean reference age (with IQR bands) across 8 academic fields
- **`output/reference_age_by_subfield.png`** — Same chart for 8 selected subfields
- **`output/reference_age_by_field_raw.png`** — Unsmoothed field chart with markers
- **`output/reference_age_by_subfield_raw.png`** — Unsmoothed subfield chart with markers

## Fields and Subfields Analyzed

**Fields:** Computer Science, Medicine, Physics and Astronomy, Mathematics, Chemistry, Economics/Econometrics/Finance, Agricultural and Biological Sciences, Psychology

**Subfields:** Artificial Intelligence, Ecology/Evolution/Behavior/Systematics, Organic Chemistry, Condensed Matter Physics, Applied Mathematics, Economics and Econometrics, Pharmacology, Genetics

## Project Structure

```
bibliometrics/
  __init__.py       # Package init
  api.py            # HTTP client with caching, retries, rate-limit handling
  charts.py         # Dual-panel chart generation (smoothed + IQR)
  cli.py            # Main pipeline entry point
  config.py         # All configuration constants
  metadata.py       # OpenAlex field/subfield ID resolution
  references.py     # Concurrent batch lookup of reference publication years
  sampling.py       # Work sampling with checkpointing
  stats.py          # Two-level reference age statistics
tests/              # pytest suite covering api, metadata, sampling, references, stats
docs/
  DATA.md           # Dataset schema and summary statistics
  METHODOLOGY.md    # Detailed methodology and known limitations
regenerate_charts.py  # Standalone script to regenerate charts from existing CSV
```

## Methodology

### 1. Fetch Topic Metadata

Queries the OpenAlex `/fields` and `/subfields` endpoints to resolve display names (e.g., "Computer Science") to OpenAlex IDs (e.g., `fields/17`). Subfields are also mapped back to their parent field.

### 2. Sample Works

For each field-year and subfield-year combination, requests a **random sample of 1,000 works** from the OpenAlex `/works` endpoint using the `sample` parameter with a fixed seed (`seed=42`) for reproducibility. The filter requires `referenced_works_count:>0` so that every sampled work has at least one citation to analyze.

Example API call for Computer Science in 2020:

```
GET https://api.openalex.org/works?filter=topics.field.id:fields/17,publication_year:2020,referenced_works_count:>0&select=id,publication_year,referenced_works&per_page=200&sample=1000&seed=42
```

This yields 416 queries total (8 fields x 26 years + 8 subfields x 26 years). Progress is checkpointed after each query so interrupted runs can resume.

### 3. Resolve Reference Publication Years

Each sampled work includes a list of `referenced_works` (OpenAlex IDs of cited papers). To compute reference ages, the publication year of each cited work must be looked up. The script collects all unique referenced work IDs across the entire sample (~6.3 million), then batch-queries the `/works` endpoint using the `openalex_id` filter with pipe-delimited IDs (up to 40 per batch), using **10 concurrent threads** for throughput.

Example batch lookup:

```
GET https://api.openalex.org/works?filter=openalex_id:W123|W456|W789&select=id,publication_year&per_page=200
```

Results are cached to `data/ref_years_cache.json` and IDs already queried are tracked in `data/ref_ids_queried.json` to avoid redundant API calls on reruns.

### 4. Compute Reference Age Statistics (Two-Level Aggregation)

Statistics are computed using a two-level aggregation to avoid bias from papers with many references:

1. **Per-paper:** median, mean, P25, and P75 of reference ages for each paper
2. **Per-group:** average of per-paper statistics across all papers in the group

| Metric | Description |
|---|---|
| `median_ref_age` | Average of per-paper median reference ages |
| `mean_ref_age` | Average of per-paper mean reference ages |
| `p25` | Average of per-paper 25th percentile reference ages |
| `p75` | Average of per-paper 75th percentile reference ages |
| `n_papers` | Number of qualifying papers in the sample |
| `n_references` | Number of references with a resolved age |
| `ref_resolution_rate` | Fraction of total references successfully resolved to a year |

**Filtering rules:**
- References where the cited year is after the citing year are excluded (metadata errors)
- Reference ages > 200 years are excluded (outliers)
- Papers with fewer than 3 resolved references are excluded
- Groups with fewer than 5 qualifying papers are dropped
- Groups where < 60% of references resolved to a publication year are dropped

### 5. Visualization

Two dual-panel PNG charts are generated:

- **Left panel:** 3-year rolling average of mean reference age, with faint raw values
- **Right panel:** Smoothed mean with shaded P25–P75 interquartile range

## OpenAlex API Interaction Details

- **Base URL:** `https://api.openalex.org`
- **Authentication:** None required. Optionally set `OPENALEX_API_KEY` in a `.env` file at the project root. The `MAILTO` header is sent for access to the [polite pool](https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication#the-polite-pool) (10 req/s instead of 1 req/s).
- **Rate limiting:** The script waits 0.02 seconds between requests (~50 req/s). On HTTP 429 responses, it respects the `Retry-After` header or backs off exponentially (up to 60s).
- **Retries:** Each request is retried up to 6 times on failure with exponential backoff.
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

# Run the full pipeline
uv run bibliometrics

# Regenerate charts from existing dataset (no API calls)
uv run python regenerate_charts.py

# Run tests
uv run pytest
```

### Environment Variables

Create a `.env` file in the project root (optional):

```
OPENALEX_API_KEY=your_key_here
```

### Resumability

The pipeline is designed for interrupted runs. Work sampling saves a checkpoint file, and reference year lookups are cached incrementally. Re-running the command picks up where it left off. Once the dataset CSV exists, subsequent runs skip directly to chart generation.
