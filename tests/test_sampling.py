"""Tests for work sampling."""

import json
from unittest.mock import patch

from bibliometrics.sampling import sample_all_works, sample_works


class TestSampleWorks:
    @patch("bibliometrics.sampling.api_get")
    def test_returns_works(self, mock_api_get, sample_works_response):
        mock_api_get.return_value = sample_works_response
        works = sample_works("topics.field.id:fields/17", 2020, n=3)
        assert len(works) == 3
        assert works[0]["id"] == "https://openalex.org/W1001"

    @patch("bibliometrics.sampling.api_get")
    def test_paginates_when_n_exceeds_200(self, mock_api_get):
        """Should fetch multiple pages when n > 200."""
        page1 = {
            "meta": {"count": 300},
            "results": [{"id": f"W{i}", "publication_year": 2020, "referenced_works": []} for i in range(200)],
        }
        page2 = {
            "meta": {"count": 300},
            "results": [{"id": f"W{i}", "publication_year": 2020, "referenced_works": []} for i in range(200, 300)],
        }
        mock_api_get.side_effect = [page1, page2]
        works = sample_works("topics.field.id:fields/17", 2020, n=300)
        assert len(works) == 300
        assert mock_api_get.call_count == 2


class TestSampleAllWorks:
    @patch("bibliometrics.sampling.sample_works")
    def test_collects_ref_ids(self, mock_sample, tmp_path):
        work = {
            "id": "W1",
            "publication_year": 2020,
            "referenced_works": ["https://openalex.org/W100", "https://openalex.org/W101"],
        }
        mock_sample.return_value = [work]

        field_ids = {"CS": "fields/17"}
        subfield_ids = {"AI": "subfields/1702"}
        cp = tmp_path / "checkpoint.json"

        fw, sw, refs = sample_all_works(
            field_ids, subfield_ids,
            checkpoint_path=cp,
            years=[2020],
            works_per_sample=1,
        )
        assert ("CS", 2020) in fw
        assert ("AI", 2020) in sw
        assert "https://openalex.org/W100" in refs
        assert "https://openalex.org/W101" in refs

    @patch("bibliometrics.sampling.sample_works")
    def test_checkpoint_resumes(self, mock_sample, tmp_path):
        """Pre-existing checkpoint should skip already-done queries."""
        cp = tmp_path / "checkpoint.json"
        existing = {
            "CS|2020": [{"id": "W1", "publication_year": 2020, "referenced_works": []}],
        }
        cp.write_text(json.dumps(existing))

        mock_sample.return_value = [{"id": "W2", "publication_year": 2020, "referenced_works": []}]

        fw, sw, refs = sample_all_works(
            {"CS": "fields/17"},
            {},
            checkpoint_path=cp,
            years=[2020],
            works_per_sample=1,
        )
        # sample_works should NOT be called since CS|2020 was checkpointed
        mock_sample.assert_not_called()
        assert ("CS", 2020) in fw
