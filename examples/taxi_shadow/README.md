# Pythology Taxi Intelligence — Shadow Pilot (no-dispatch prototype)

This is an isolated, **offline** prototype for comparing an AI-extracted taxi booking with a human operator's recorded booking. It is not a Dograh integration or an Amazon Connect deployment yet.

## Safety boundary

- **No MTI or SmartMove network access or write credentials.**
- **No dispatch endpoint, outbound calls, live caller audio, or production contact flow changes.**
- Does not modify Dograh application code.
- All examples and tests use fictitious people/addresses. Do not ingest real customer information until the employer, fleet owners, and privacy/security leads have authorised a controlled pilot.
- Prefer keeping original recordings in Amazon Connect with role-based access. Store a secure contact-record reference rather than copying raw audio into the prototype.
- Pilot results must not automatically be used to evaluate staff performance. A discrepancy is a prompt for fair, human review, **not** a finding that either side is wrong.

## Two planned modes

### 1. Shadow mode (observe only)
1. Amazon Connect receives the existing fleet-specific DID; the human answers normally.
2. Obtain an authorised transcript of the recorded call. **Start with post-call analysis** (Contact Lens / S3); consider dual-channel Kinesis Video Streams later.
3. An extraction adapter outputs one structured `ai` row with the Amazon Connect `contact_id`, `fleet_id`, and `dispatch_system`.
4. A separate read-only adapter obtains the **actual** staff booking from the MTI or SmartMove booking/audit export. Matching by `contact_id` is ideal; if the dispatch system doesn't retain it, a controlled correlation step needs to be designed and validated.
5. The local comparison engine highlights differences. A supervisor reviews the source audio and chooses AI correct, staff correct, changed during call, both acceptable, or unresolved. Human corrections must be preserved.
6. Keep only the minimum personal information for the authorised retention period.

### 2. Phone test mode (separate route)
1. Allocate a **dedicated test phone number** and explicitly approved test users/fleets.
2. Connect test calls to a Dograh voice agent through an approved Amazon Connect integration/transfer or supported telephony carrier. **The telephony bridge is not implemented here.**
3. Announce: "You are speaking with an AI test system. No taxi will be dispatched."
4. Save simulated booking details to an isolated test database, marked `TEST_ONLY`, `DO_NOT_DISPATCH`. Supply a fake reference e.g. `TEST-0042`.
5. Never send test calls or simulated bookings to live fleet dispatch. Only use vendor-provided test/sandbox API environments if later approved.
6. Give fleet representatives scoped access to their test records and feedback, never to unrelated fleets' data.

## Data contract for this offline comparison

Input format: JSON Lines (`.jsonl`), one record per line. Two separate files: `--ai` and `--operator`. Both must contain:

- `contact_id`: opaque Amazon Connect contact identifier
- `fleet_id`: canonical fleet identifier, resolved from dialled number / routing table
- `dispatch_system`: `smartmove` or `mti`
- `intent`: for this initial comparator only `new_booking`
- `pickup_address`: string
- `destination_address`: string or null
- `pickup_time`: preferably ISO 8601 with NZ timezone offset for prebookings, or a standard `ASAP`
- `passenger_count`: integer or null
- `vehicle_type`: string or null

An operator record may also include `booking_id`, for review/correlation. We **do not** compare booking IDs as semantic fields.

Inputs must be independently generated: the AI must not read the operator's fields before its own interpretation is stored. For operator exports with no contact ID, do **not** arbitrarily match by phone or proximity to call time.

Comparisons use conservative casing/whitespace normalization only. Street-number or pickup-time differences are always flagged. Missing fields are labelled incomplete, not counted as a match. Non-booking callbacks need a separate workflow later.

## Run (Python 3.11+, standard library only)

```bash
python examples/taxi_shadow/compare.py --ai examples/taxi_shadow/samples/ai.jsonl --operator examples/taxi_shadow/samples/operator.jsonl
python -m unittest discover -s examples/taxi_shadow/tests -v
```

Outputs a JSON report to standard output. It does not write anything to a database.

## Next implementation gates

1. Confirm enterprise permission to examine live call material; complete a NZ privacy impact assessment and call/staff notices.
2. Discover Amazon Connect instance/region, existing recording/Contact Lens configuration, and where each DID is mapped to a fleet.
3. Discover how the staff booking form is populated and whether `contact_id` passes to MTI/SmartMove; secure **read-only** booking data, not production write access.
4. Add a transcription/extraction worker, confidence/evidence offsets, review dashboard, and audit trail.
5. Add a Dograh voice agent on a segregated test DID and booking database. Test spoken NZ addresses, ambiguous pickup points, background noise, changes/cancellations, multiple concurrent calls, caller frustration, escalation.
6. Establish quantitative acceptance thresholds **before** any eventual live booking trial. Rollback and transfer-to-human paths are mandatory.

Architecture reference: Amazon Connect supports customer audio streaming via Kinesis Video Streams, recorded audio via S3, and caller-number / contact-ID attributes. The Dograh fork supports inbound telephony and customizable tool workflows, but no passive shadow adapter exists in this prototype.

## Fleet-wide trial strategy (director demonstration)

**Scope: every consenting fleet, both dispatch systems.** Do not limit the programme to one pilot SmartMove fleet and one MTI fleet. Roll out fleet configurations in batches for troubleshooting, but give every fleet an opportunity to test before judging platform readiness. This is a test-coverage decision, not permission to deploy to all real calls at once.

### Fleet registry

For each fleet, configure separately:

- `fleet_id` and business display name
- incoming Amazon Connect dialled number (DID), and approved test-route identifier
- dispatch platform (`smartmove` or `mti`) and **read-only** booking/audit source, where authorised
- service area, pickup landmarks, local pronunciations, geography exceptions, business rules and escalation numbers
- test-call permissions and manager/reviewer access; scoped storage/retention rules
- explicit authorisation status for shadow analysis and sandbox phone tests

Use the incoming Amazon Connect number to identify the production fleet; never guess based on the caller's stated location. The simulator may use a dedicated test number with an explicit, authenticated fleet selection; never route tests into live dispatch.

### Two separate fleet-wide tests

1. **Recorded-call shadow comparisons:** For each authorised fleet, independently extract booking details from recorded calls, correlate with independently sourced operator booking records, and flag unresolved mismatches for human review. Only report evaluated, paired calls; exclude unsupported callbacks from booking-accuracy denominators. Publish per-fleet metrics and an overall summary with sample sizes and uncertainty.
2. **Independent telephone test calls:** Give participating companies an approved test telephone route, clear AI/non-dispatch disclosure, their own simulated fleet persona and booking rules, fake reference numbers, and access to their own results. Include new bookings, prebookings, changes, cancellations, callbacks, unclear accents, rural addresses, special vehicles, multiple calls and outage simulations. Use fictitious test identities and addresses where practical.

### Evaluation and governance

- A mismatch is **not** evidence that an employee was wrong. Review the full call context, later corrections and dispatch status; mark `AI_CORRECT`, `HUMAN_CORRECT`, `BOTH_ACCEPTABLE`, `CHANGED_DURING_CALL`, or `UNRESOLVED`.
- Keep the programme separate from individual disciplinary investigations. Agree on staff notification, authorised recording use, privacy assessment and fair employment procedures before live-call analysis.
- Track fleet-by-fleet extraction completeness, match rate on comparable fields, AI-confirmed errors, human-confirmed errors, test-call completion, wrong-fleet routing, duplicate submissions (must be zero in no-dispatch modes), false booking confirmations (must be zero), and callback handling.
- Run the director demonstration entirely in the isolated test-number/test-database environment. No live job creation, dispatch, cancellation or customer notification.
- Require explicit authorisation and passing thresholds for each fleet before any future live-booking trial; do not infer readiness for all fleets from an average across fleets.
