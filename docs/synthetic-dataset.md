# Synthetic demonstration dataset

All records under `datasets/` are fictional and exist only to exercise the local workflow. They do not describe real people, organizations, locations, vehicles, cases, or criminal activity.

## Seeded scenario

The bootstrap creates `CASE-2026-001`, a small harbor/logistics network with:

- Four people with aliases.
- Phone, vehicle, location, organization, and event entities.
- Ten relationships, including reciprocal calls and cross-type links.
- A synthetic FIR text source with evidence links.
- Timestamped relationships suitable for timeline and signal analysis.

## Files

- `persons.csv`, `phones.csv`, `vehicles.csv`, `locations.csv`, `organizations.csv`: entity-shaped records.
- `cdr.csv`, `transactions.csv`, `events.csv`: structured source samples.
- `reports/FIR_001.txt`: unstructured text sample.
- `cases.csv`: case context sample.

The Admin CSV import endpoint accepts small UTF-8 files and marks imported relationships for review. It does not silently approve extracted facts.
