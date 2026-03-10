"""Tests for statistics computation."""

import numpy as np
import pandas as pd

from bibliometrics.stats import build_dataset, compute_stats


class TestComputeStats:
    def test_basic_stats(self, ref_years_lookup):
        """Should compute correct median, mean, P25, P75 from fixture data."""
        # Need >= 10 resolved ages, so repeat refs across multiple works
        refs_a = [
            "https://openalex.org/W2001",  # 2015 -> age 5
            "https://openalex.org/W2002",  # 2010 -> age 10
            "https://openalex.org/W2003",  # 2018 -> age 2
        ]
        refs_b = [
            "https://openalex.org/W2004",  # 2012 -> age 8
            "https://openalex.org/W2005",  # 2019 -> age 1
            "https://openalex.org/W2006",  # 2005 -> age 15
            "https://openalex.org/W2007",  # 2017 -> age 3
        ]
        works = [
            {"publication_year": 2020, "referenced_works": refs_a + refs_b},
            {"publication_year": 2020, "referenced_works": refs_a + refs_b},
        ]
        stats = compute_stats(works, ref_years_lookup)

        # Ages per work: [5, 10, 2, 8, 1, 15, 3] x2 = 14 ages
        assert stats is not None
        assert stats["n_papers"] == 2
        assert stats["n_references"] == 14
        assert stats["total_refs"] == 14
        assert stats["ref_resolution_rate"] == 1.0
        # median of [1,2,3,5,8,10,15] x2 = median is (5+5)/2 = 5? no...
        # sorted 14 ages: [1,1,2,2,3,3,5,5,8,8,10,10,15,15] -> median = (5+5)/2 = 5
        assert stats["median_ref_age"] == 5.0

    def test_returns_none_with_few_ages(self):
        """Should return None when fewer than 10 reference ages resolved."""
        works = [
            {
                "publication_year": 2020,
                "referenced_works": ["https://openalex.org/W9999"],
            },
        ]
        result = compute_stats(works, {})
        assert result is None

    def test_ignores_future_refs(self, ref_years_lookup):
        """References published after the citing work should be excluded."""
        works = [
            {
                "publication_year": 2010,
                "referenced_works": [
                    "https://openalex.org/W2001",  # 2015 > 2010, excluded
                    "https://openalex.org/W2002",  # 2010 -> age 0
                    "https://openalex.org/W2006",  # 2005 -> age 5
                ] * 5,  # repeat to get > 10 ages
            },
        ]
        stats = compute_stats(works, ref_years_lookup)
        assert stats is not None
        # Ages should only be [0, 5] * 5 = 10 ages, no age from W2001
        assert stats["n_references"] == 10


class TestBuildDataset:
    def test_builds_field_and_subfield_rows(self, ref_years_lookup):
        works = [
            {
                "publication_year": 2020,
                "referenced_works": list(ref_years_lookup.keys()),
            },
        ] * 3  # 3 papers, each with 7 refs -> 21 ages

        field_works = {("Computer Science", 2020): works}
        subfield_works = {("Artificial Intelligence", 2020): works}
        subfield_to_field = {
            "Artificial Intelligence": ("fields/17", "Computer Science")
        }

        df = build_dataset(field_works, subfield_works, ref_years_lookup, subfield_to_field)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

        field_row = df[df["subfield"] == "All"].iloc[0]
        assert field_row["field"] == "Computer Science"
        assert field_row["year"] == 2020

        sub_row = df[df["subfield"] == "Artificial Intelligence"].iloc[0]
        assert sub_row["field"] == "Computer Science"

    def test_drops_low_resolution_rate(self):
        """Rows with low ref resolution rate should be dropped."""
        # 20 refs but only 11 resolve -> 55% < 60%
        ref_years = {f"https://openalex.org/W{i}": 2010 for i in range(11)}
        all_refs = [f"https://openalex.org/W{i}" for i in range(20)]
        works = [{"publication_year": 2020, "referenced_works": all_refs}]

        field_works = {("CS", 2020): works}
        df = build_dataset(field_works, {}, ref_years, {}, min_resolution_rate=0.6)
        assert len(df) == 0
