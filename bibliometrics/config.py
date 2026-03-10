"""Configuration constants for the bibliometrics analysis."""

import os
from pathlib import Path

# Load .env file if present
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

API_BASE = "https://api.openalex.org"
API_KEY = os.environ.get("OPENALEX_API_KEY", "")

# Directories
DATA_DIR = Path("data")
CACHE_DIR = DATA_DIR / "cache"
OUTPUT_DIR = Path("output")

# Sampling
YEARS = list(range(2000, 2026))
WORKS_PER_SAMPLE = 1000
BATCH_SIZE = 40  # max IDs per batch ref-year lookup
REQUEST_DELAY = 0.02  # seconds between API calls (paid tier allows higher throughput)
MIN_REF_RESOLUTION_RATE = 0.6

# Polite pool email — gets 10 req/s instead of ~1 req/s
MAILTO = "bibliometrics-analysis@example.com"

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
