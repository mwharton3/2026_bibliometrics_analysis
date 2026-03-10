# Methodology

## Overview

This project measures **reference age** — the time gap between a paper's publication year and the publication years of its cited references — across academic fields and subfields, using data from [OpenAlex](https://openalex.org/).

Reference age is a proxy for how quickly a field builds on recent work versus drawing on older foundational literature. A field with low median reference age tends to cite recent papers (fast-moving), while a high median suggests reliance on older work (slow-moving or theoretically mature).

## Pipeline

The analysis runs in four stages:

### 1. Metadata Fetch

OpenAlex organizes academic work into a hierarchy of **fields** (e.g., Computer Science) and **subfields** (e.g., Artificial Intelligence). The pipeline fetches the full taxonomy via the `/fields` and `/subfields` API endpoints to resolve display names to OpenAlex IDs.

### 2. Work Sampling

For each (field or subfield, year) combination, we sample **1,000 works** from OpenAlex using their built-in `sample` parameter with `seed=42` for reproducibility. Only works with at least one reference (`referenced_works_count > 0`) are included.

This produces 416 sample groups: 8 fields x 26 years + 8 subfields x 26 years.

The sampling is checkpointed to disk so that interrupted runs can resume without re-querying completed groups.

### 3. Reference Year Resolution

Each sampled work contains a list of OpenAlex IDs for its references. We batch-query the API to retrieve the publication year for each unique referenced work. Across all samples, this involved resolving **6.29 million unique reference IDs**.

Resolution uses concurrent requests (10 threads) with file-based caching and progress checkpointing. Failed batches are marked as queried to avoid infinite retry loops.

### 4. Statistics Computation

For each sample group, we compute reference age statistics using a **two-level aggregation**:

1. **Per paper:** For each paper, compute the median, mean, 25th percentile, and 75th percentile of `(publication_year - reference_year)` across its resolved references.
2. **Per group:** Average the per-paper statistics across all papers in the group.

This two-level approach avoids two problems:
- **Prolific-paper bias:** A single paper with 200 references doesn't dominate a group where most papers have 20.
- **Integer quantization:** Since reference ages are integer year-differences, a pooled median over thousands of ages almost always lands on an exact integer, obscuring real differences between groups.

#### Filters Applied

- References where `ref_year > pub_year` are excluded (likely metadata errors or preprint dates).
- Reference ages above 200 years are excluded as outliers.
- Papers with fewer than 3 resolved references are excluded from aggregation.
- Sample groups with fewer than 5 qualifying papers are dropped entirely.
- A minimum reference resolution rate of 60% is enforced per group (configurable via `MIN_REF_RESOLUTION_RATE`).

## Known Limitations

### Resolution Rate Degradation

The fraction of references that can be resolved to a publication year declines for more recent papers. For example, Computer Science papers from 2000 have ~90% resolution, while 2024 papers have ~79%. This happens because recently published works are less likely to be fully indexed in OpenAlex.

The missing references are probably **not random**: very recent citations (age 0-2) are disproportionately likely to be unresolved. This could systematically bias recent-year statistics upward (overstating reference age), since the youngest references are the ones most likely to be missing.

### Sampling vs. Census

We sample 1,000 works per group rather than analyzing every paper. For large fields with hundreds of thousands of papers per year, this is a tiny fraction. The `seed=42` parameter makes results reproducible but the sample may not perfectly represent the population, particularly for heterogeneous fields.

### OpenAlex Coverage

OpenAlex has broad coverage but is not exhaustive. Coverage varies by field, time period, and publication venue. Some disciplines (e.g., humanities, non-English-language journals) may be underrepresented. The reference lists in OpenAlex are also derived from metadata parsing and may be incomplete compared to the actual bibliographies.

### Field/Subfield Assignment

OpenAlex assigns topics (and therefore fields/subfields) algorithmically. A paper may span multiple subfields, but we query by primary topic assignment. Interdisciplinary work may be undercounted in some categories.
