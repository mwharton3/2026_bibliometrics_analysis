"""Tests for metadata fetching."""

from unittest.mock import patch

from bibliometrics.metadata import fetch_metadata, select_ids


class TestFetchMetadata:
    @patch("bibliometrics.metadata.api_get")
    def test_parses_fields_and_subfields(
        self, mock_api_get, fields_response, subfields_response
    ):
        mock_api_get.side_effect = [fields_response, subfields_response]

        field_map, subfield_map, subfield_to_field = fetch_metadata()

        assert field_map == {
            "Computer Science": "fields/17",
            "Medicine": "fields/27",
        }
        assert subfield_map == {
            "Artificial Intelligence": "subfields/1702",
            "Pharmacology": "subfields/2701",
        }
        assert subfield_to_field["Artificial Intelligence"] == (
            "fields/17",
            "Computer Science",
        )
        assert subfield_to_field["Pharmacology"] == ("fields/27", "Medicine")


class TestSelectIds:
    def test_selects_matching_names(self):
        id_map = {"Foo": "id1", "Bar": "id2", "Baz": "id3"}
        result = select_ids(["Foo", "Baz"], id_map, "field")
        assert result == {"Foo": "id1", "Baz": "id3"}

    def test_warns_on_missing_name(self, capsys):
        id_map = {"Foo": "id1"}
        result = select_ids(["Foo", "Missing"], id_map, "field")
        assert result == {"Foo": "id1"}
        assert "Warning" in capsys.readouterr().out
