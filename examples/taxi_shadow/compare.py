"""Offline, read-only comparator for the Pythology Taxi Intelligence pilot.

No telephony connections, booking writes, dispatch integrations or external packages.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

REQUIRED_FIELDS = ("pickup_address", "pickup_time")
OPTIONAL_FIELDS = ("destination_address", "passenger_count", "vehicle_type")
IDENTITY_FIELDS = ("fleet_id", "dispatch_system")


def normalized(value: Any) -> str | None:
    """Conservative comparison: never silently reinterpret an address or time."""
    if value is None or isinstance(value, bool):
        return None
    text = re.sub(r"\\s+", " ", str(value)).strip()
    return text.casefold() if text else None


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            parsed = json.loads(line)
            if not isinstance(parsed, dict):
                raise ValueError(f"{path}:{line_no}: expected a JSON object")
            records.append(parsed)
    return records


def index_records(records: list[dict[str, Any]], source: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        contact_id = record.get("contact_id")
        if not isinstance(contact_id, str) or not contact_id.strip():
            raise ValueError(f"{source}: a nonempty contact_id is required")
        if contact_id in indexed:
            raise ValueError(f"{source}: duplicate contact_id {contact_id!r}; refusing ambiguous match")
        indexed[contact_id] = record
    return indexed


def compare_record(ai: dict[str, Any], operator: dict[str, Any]) -> dict[str, Any]:
    """Return mismatch field names without sending passenger details to report logs."""
    if ai.get("contact_id") != operator.get("contact_id"):
        raise ValueError("Cannot compare different Amazon Connect contacts")
    contact_id = ai["contact_id"]
    if ai.get("intent") != "new_booking" or operator.get("intent") != "new_booking":
        return {
            "contact_id": contact_id,
            "status": "UNSUPPORTED_INTENT",
            "differences": [],
            "missing": [],
        }

    differences: list[str] = []
    missing: list[str] = []
    for field in IDENTITY_FIELDS + REQUIRED_FIELDS + OPTIONAL_FIELDS:
        left = normalized(ai.get(field))
        right = normalized(operator.get(field))
        if left is None and right is None:
            if field in IDENTITY_FIELDS + REQUIRED_FIELDS:
                missing.append(field)
        elif left != right:
            differences.append(field)

    return {
        "contact_id": contact_id,
        "status": "REVIEW" if differences else ("INCOMPLETE" if missing else "MATCH"),
        "differences": differences,
        "missing": missing,
    }


def compare_batches(
    ai_records: list[dict[str, Any]], operator_records: list[dict[str, Any]]
) -> dict[str, Any]:
    ai = index_records(ai_records, "AI")
    operator = index_records(operator_records, "operator")
    results: list[dict[str, Any]] = []

    # Explicitly expose unpaired records, rather than guessing which booking matches.
    for contact_id in sorted(set(ai) | set(operator)):
        if contact_id not in ai or contact_id not in operator:
            results.append({
                "contact_id": contact_id,
                "status": "UNPAIRED",
                "missing_side": "AI" if contact_id not in ai else "operator",
                "differences": [],
                "missing": [],
            })
            continue
        results.append(compare_record(ai[contact_id], operator[contact_id]))

    return {
        "mode": "SHADOW_ONLY_NO_DISPATCH",
        "summary": dict(Counter(item["status"] for item in results)),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare independent AI and operator taxi booking exports")
    parser.add_argument("--ai", required=True, help="JSONL of AI-extracted bookings")
    parser.add_argument("--operator", required=True, help="JSONL of human-saved bookings")
    args = parser.parse_args()
    report = compare_batches(load_jsonl(args.ai), load_jsonl(args.operator))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
