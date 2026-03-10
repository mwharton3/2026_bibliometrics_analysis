"""Fetch field and subfield metadata from OpenAlex."""

from .api import api_get
from .config import API_BASE


def fetch_metadata() -> tuple[dict, dict, dict]:
    """Fetch all fields and subfields from OpenAlex.

    Returns:
        field_map: {display_name: short_id}
        subfield_map: {display_name: short_id}
        subfield_to_field: {subfield_name: (field_short_id, field_display_name)}
    """
    print("Fetching field metadata...")
    fields_data = api_get(f"{API_BASE}/fields", {"per_page": 50})
    field_map = {}
    for f in fields_data["results"]:
        short_id = f["id"].replace("https://openalex.org/", "")
        field_map[f["display_name"]] = short_id

    print("Fetching subfield metadata...")
    all_subfields = []
    page = 1
    while True:
        data = api_get(f"{API_BASE}/subfields", {"per_page": 50, "page": page})
        all_subfields.extend(data["results"])
        if len(all_subfields) >= data["meta"]["count"]:
            break
        page += 1

    subfield_map = {}
    subfield_to_field = {}
    for s in all_subfields:
        short_id = s["id"].replace("https://openalex.org/", "")
        subfield_map[s["display_name"]] = short_id
        field_short = s["field"]["id"].replace("https://openalex.org/", "")
        subfield_to_field[s["display_name"]] = (
            field_short,
            s["field"]["display_name"],
        )

    return field_map, subfield_map, subfield_to_field


def select_ids(names: list[str], id_map: dict, label: str) -> dict:
    """Select a subset of field/subfield IDs by name.

    Args:
        names: Desired display names.
        id_map: Full {display_name: short_id} mapping.
        label: "field" or "subfield" for log messages.

    Returns:
        {display_name: short_id} for matched names.
    """
    selected = {}
    for name in names:
        if name in id_map:
            selected[name] = id_map[name]
        else:
            print(f"  Warning: {label} '{name}' not found.")
    print(f"Selected {len(selected)} {label}s: {list(selected.keys())}")
    return selected
