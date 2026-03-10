"""Shared fixtures for bibliometrics tests."""

import pytest


# ── OpenAlex API response fixtures ───────────────────────────────────────────


@pytest.fixture
def fields_response():
    """Minimal /fields response with 2 fields."""
    return {
        "meta": {"count": 2},
        "results": [
            {"id": "https://openalex.org/fields/17", "display_name": "Computer Science"},
            {"id": "https://openalex.org/fields/27", "display_name": "Medicine"},
        ],
    }


@pytest.fixture
def subfields_response():
    """Minimal /subfields response with 2 subfields (single page)."""
    return {
        "meta": {"count": 2},
        "results": [
            {
                "id": "https://openalex.org/subfields/1702",
                "display_name": "Artificial Intelligence",
                "field": {
                    "id": "https://openalex.org/fields/17",
                    "display_name": "Computer Science",
                },
            },
            {
                "id": "https://openalex.org/subfields/2701",
                "display_name": "Pharmacology",
                "field": {
                    "id": "https://openalex.org/fields/27",
                    "display_name": "Medicine",
                },
            },
        ],
    }


@pytest.fixture
def sample_works_response():
    """Response from /works with sample parameter — 3 works."""
    return {
        "meta": {"count": 3},
        "results": [
            {
                "id": "https://openalex.org/W1001",
                "publication_year": 2020,
                "referenced_works": [
                    "https://openalex.org/W2001",
                    "https://openalex.org/W2002",
                    "https://openalex.org/W2003",
                ],
            },
            {
                "id": "https://openalex.org/W1002",
                "publication_year": 2020,
                "referenced_works": [
                    "https://openalex.org/W2001",
                    "https://openalex.org/W2004",
                ],
            },
            {
                "id": "https://openalex.org/W1003",
                "publication_year": 2020,
                "referenced_works": [
                    "https://openalex.org/W2005",
                    "https://openalex.org/W2006",
                    "https://openalex.org/W2007",
                ],
            },
        ],
    }


@pytest.fixture
def ref_years_response():
    """Response from /works batch lookup — publication years for refs."""
    return {
        "meta": {"count": 5},
        "results": [
            {"id": "https://openalex.org/W2001", "publication_year": 2015},
            {"id": "https://openalex.org/W2002", "publication_year": 2010},
            {"id": "https://openalex.org/W2003", "publication_year": 2018},
            {"id": "https://openalex.org/W2004", "publication_year": 2012},
            {"id": "https://openalex.org/W2005", "publication_year": 2019},
        ],
    }


@pytest.fixture
def ref_years_lookup():
    """Pre-built ref_years dict matching the fixture data."""
    return {
        "https://openalex.org/W2001": 2015,
        "https://openalex.org/W2002": 2010,
        "https://openalex.org/W2003": 2018,
        "https://openalex.org/W2004": 2012,
        "https://openalex.org/W2005": 2019,
        "https://openalex.org/W2006": 2005,
        "https://openalex.org/W2007": 2017,
    }
