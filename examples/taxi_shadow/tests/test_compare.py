"""Unit tests: synthetic bookings only; no dispatch side effects."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compare import compare_batches, compare_record, normalized


def booking(**overrides):
    data = {
        "contact_id": "FAKE-CONTACT-1",
        "fleet_id": "DEMO-FLEET",
        "dispatch_system": "smartmove",
        "intent": "new_booking",
        "pickup_address": "18 Queen Street",
        "destination_address": "Airport",
        "pickup_time": "ASAP",
        "passenger_count": 2,
        "vehicle_type": "standard",
    }
    data.update(overrides)
    return data


class ShadowComparatorTests(unittest.TestCase):
    def test_whitespace_and_case_only_are_ignored(self):
        self.assertEqual(normalized("  Queen   STREET  "), "queen street")
        result = compare_record(booking(), booking(pickup_address="  18  QUEEN street "))
        self.assertEqual(result["status"], "MATCH")

    def test_street_number_discrepancy_is_detected(self):
        result = compare_record(booking(), booking(pickup_address="80 Queen Street"))
        self.assertEqual(result["status"], "REVIEW")
        self.assertIn("pickup_address", result["differences"])

    def test_pickup_time_discrepancy_is_detected(self):
        result = compare_record(booking(), booking(pickup_time="2026-10-12T22:30:00+13:00"))
        self.assertIn("pickup_time", result["differences"])

    def test_fleet_id_conflict_requires_review(self):
        result = compare_record(booking(), booking(fleet_id="ANOTHER-FLEET"))
        self.assertIn("fleet_id", result["differences"])

    def test_missing_required_fields_is_not_match(self):
        result = compare_record(booking(pickup_address=None), booking(pickup_address=None))
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertIn("pickup_address", result["missing"])

    def test_unmatched_bookings_are_exposed(self):
        result = compare_batches([booking()], [])
        self.assertEqual(result["results"][0]["status"], "UNPAIRED")
        self.assertEqual(result["results"][0]["missing_side"], "operator")

    def test_duplicate_contact_id_is_rejected(self):
        with self.assertRaises(ValueError):
            compare_batches([booking(), booking()], [booking()])

    def test_callbacks_are_not_false_bookings(self):
        result = compare_record(booking(intent="cancel_booking"), booking(intent="cancel_booking"))
        self.assertEqual(result["status"], "UNSUPPORTED_INTENT")

    def test_no_customer_addresses_in_batch_report(self):
        result = compare_batches([booking()], [booking(pickup_address="80 Queen Street")])
        self.assertNotIn("Queen Street", str(result))


if __name__ == "__main__":
    unittest.main()
