"""Tests for the API client (caching, retries, rate limiting)."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from bibliometrics.api import api_get


class TestApiGet:
    def test_returns_cached_response(self, tmp_path):
        """Cache hit should return stored data without making HTTP request."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Pre-populate cache
        from bibliometrics.api import _cache_key

        url = "https://api.openalex.org/works"
        params = {"filter": "test"}
        key = _cache_key(url, params)
        cached_data = {"results": [{"id": "cached"}]}
        (cache_dir / f"{key}.json").write_text(json.dumps(cached_data))

        result = api_get(url, params, cache_dir=cache_dir, mailto="")
        assert result == cached_data

    @patch("bibliometrics.api.requests.get")
    @patch("bibliometrics.api.time.sleep")
    def test_successful_request_is_cached(self, mock_sleep, mock_get, tmp_path):
        """A successful request should be written to cache."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        response_data = {"results": [{"id": "fresh"}]}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = response_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = api_get(
            "https://api.openalex.org/works",
            {"filter": "new"},
            cache_dir=cache_dir,
            request_delay=0,
            mailto="",
        )

        assert result == response_data
        mock_get.assert_called_once()
        # Verify it was cached
        cache_files = list(cache_dir.glob("*.json"))
        assert len(cache_files) == 1

    @patch("bibliometrics.api.requests.get")
    @patch("bibliometrics.api.time.sleep")
    def test_retries_on_429(self, mock_sleep, mock_get, tmp_path):
        """Should retry on 429 rate limit responses."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        rate_limit_resp = MagicMock()
        rate_limit_resp.status_code = 429

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"results": []}
        ok_resp.raise_for_status = MagicMock()

        mock_get.side_effect = [rate_limit_resp, ok_resp]

        result = api_get(
            "https://api.openalex.org/works",
            {"filter": "test"},
            retries=3,
            cache_dir=cache_dir,
            request_delay=0,
            mailto="",
        )
        assert result == {"results": []}
        assert mock_get.call_count == 2

    @patch("bibliometrics.api.requests.get")
    @patch("bibliometrics.api.time.sleep")
    def test_raises_after_exhausted_retries(self, mock_sleep, mock_get, tmp_path):
        """Should raise RuntimeError when all retries fail with 429."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        rate_limit_resp = MagicMock()
        rate_limit_resp.status_code = 429

        mock_get.return_value = rate_limit_resp

        with pytest.raises(RuntimeError, match="Failed after 2 retries"):
            api_get(
                "https://api.openalex.org/works",
                {"filter": "test"},
                retries=2,
                cache_dir=cache_dir,
                request_delay=0,
                mailto="",
            )

    @patch("bibliometrics.api.requests.get")
    @patch("bibliometrics.api.time.sleep")
    def test_retries_on_network_error(self, mock_sleep, mock_get, tmp_path):
        """Should retry on network errors then succeed."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"meta": {"count": 0}, "results": []}
        ok_resp.raise_for_status = MagicMock()

        mock_get.side_effect = [
            requests.exceptions.ConnectionError("connection refused"),
            ok_resp,
        ]

        result = api_get(
            "https://api.openalex.org/works",
            cache_dir=cache_dir,
            request_delay=0,
            mailto="",
        )
        assert result["results"] == []
        assert mock_get.call_count == 2
