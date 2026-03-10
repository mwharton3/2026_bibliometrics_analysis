"""Tests for batch reference year lookup."""

import json
from unittest.mock import patch

from bibliometrics.references import batch_lookup_years


class TestBatchLookupYears:
    @patch("bibliometrics.references.api_get")
    def test_looks_up_new_ids(self, mock_api_get, tmp_path, ref_years_response):
        mock_api_get.return_value = ref_years_response

        ref_ids = {
            "https://openalex.org/W2001",
            "https://openalex.org/W2002",
            "https://openalex.org/W2003",
            "https://openalex.org/W2004",
            "https://openalex.org/W2005",
        }

        result = batch_lookup_years(ref_ids, data_dir=tmp_path, batch_size=5)
        assert result["https://openalex.org/W2001"] == 2015
        assert result["https://openalex.org/W2005"] == 2019
        assert len(result) == 5

        # Verify caches were written
        assert (tmp_path / "ref_years_cache.json").exists()
        assert (tmp_path / "ref_ids_queried.json").exists()

    @patch("bibliometrics.references.api_get")
    def test_skips_cached_ids(self, mock_api_get, tmp_path):
        """IDs in queried cache should not trigger new API calls."""
        # Pre-populate caches
        cache = {"https://openalex.org/W2001": 2015}
        queried = ["https://openalex.org/W2001", "https://openalex.org/W2002"]
        (tmp_path / "ref_years_cache.json").write_text(json.dumps(cache))
        (tmp_path / "ref_ids_queried.json").write_text(json.dumps(queried))

        ref_ids = {"https://openalex.org/W2001", "https://openalex.org/W2002"}
        result = batch_lookup_years(ref_ids, data_dir=tmp_path)

        mock_api_get.assert_not_called()
        assert result["https://openalex.org/W2001"] == 2015

    @patch("bibliometrics.references.api_get")
    def test_saves_progress_despite_partial_failure(self, mock_api_get, tmp_path):
        """Partial batch failures should not lose successful results."""
        # First batch succeeds, second fails
        mock_api_get.side_effect = [
            {"meta": {"count": 1}, "results": [{"id": "https://openalex.org/W1", "publication_year": 2020}]},
            Exception("API down"),
        ]

        ref_ids = {f"https://openalex.org/W{i}" for i in range(1, 5)}
        result = batch_lookup_years(ref_ids, data_dir=tmp_path, batch_size=2, concurrency=1)

        # Successful batch results should be in the return value and saved
        assert "https://openalex.org/W1" in result
        saved = json.loads((tmp_path / "ref_years_cache.json").read_text())
        assert "https://openalex.org/W1" in saved
