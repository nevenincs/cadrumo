---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:f101d8f066971a2509bb750af783b489f01e9adb119a25c9af207b1a991edd4d'
step_id: 'S21'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# add a strict roundtrip test for `Justificante` populating every defaultable field non-default, plus an anti-tautology proof corrupting the persisted CSV value and asserting refusal

## Scope

- `src/cadrumo/domain/justificante/tests/`

## Description

- Add `test_secure_storage_roundtrip.py` under the receipt domain's own tests
  directory, driving save and load through the real `JustificanteRepository`
  persistence adapter rather than a hand-rolled repository call, so the test
  exercises the path production uses.
- Build the fixture with every defaultable field carrying a non-default value
  and guard that claim with a dedicated test.
- Add two anti-tautology proofs: an out-of-bound persisted CSV must be refused
  at load, and a deleted optional amount must surface as strict inequality.
- Add an iteration test confirming the CSV is the natural key for `list_csvs`
  and `iter_justificantes`.

## Outcome

Five tests, all green. The roundtrip runs against real adapters throughout: a
real ephemeral master-key provider, a real on-disk SQLite engine and the real
serializer, provisioned through the shared isolated runtime profile helper. No
mock, fake, stub or monkeypatch appears in the module.

**Defaultable-field count: four of thirteen.** `Justificante` declares thirteen
fields, of which nine are required and exactly four are defaultable —
`ejercicio`, `presentation_id`, `total_a_ingresar` and `total_a_devolver`, each
defaulting to `None`. All four carry a non-default value in the fixture. Both
amount fields are populated simultaneously; a real receipt prints one or the
other, but the schema constrains neither and the point is to give the equality
witness signal on both slots. The count is pinned as a literal frozenset and
cross-checked against the model's own optional-field set, so a new optional
field added later fails loudly instead of silently widening the set the
roundtrip believes it covers.

The equality assertion is strict pydantic equality on the whole model, not a
per-field comparison; the explicit per-field assertions that follow it are
readability aids, not the contract.

Three separate bite proofs were run, each from a throwaway pytest plugin
outside the repository tree loaded via `PYTHONPATH`, so no tracked file was
edited and a crashed run leaves no residue.

First, the strict-equality witness. Marking the optional amount excluded from
serialisation **in place on the one model class** — deliberately not via a
subclass, so a class-identity mismatch cannot be what explains the red — reds
three of the five tests, the roundtrip failing on `assert loaded == original`
with `Justificante(...) == Justificante(...)` on both sides. This is exactly
the save-drops-field, load-re-defaults-field regression the discipline names,
and it is invisible to a fixture that leaves the field at its default.

Second, the CSV-corruption proof. Giving the csv field a before-validator that
discards the envelope's value and substitutes the fixture's own makes the
corruption undetectable; the proof reds with its own message, "an out-of-bound
CSV persisted on disk loaded without refusal and compared equal to the
original". Without this second proof the corruption test could have been
passing on a boundary that never reads the persisted value at all.

Third, the deleted-field proof's own fixture guard fires under the first bite,
correctly refusing to run a signal-free negative case rather than passing
vacuously.

## Notes

The corruption token chosen is short of the eight-character floor **and**
carries a separator the character class refuses. That is deliberate: the alias
normalises by stripping and uppercasing before its constraints run, so
corrupting the persisted value to a mere lowercase variant would be
accepted-and-corrected back to the original and the proof would falsely
conclude the boundary was broken. A corruption used as a refusal proof has to
be a value the normal form cannot rescue.

Two tree-wide gates are red at HEAD and neither is owned by this Step. The type
gate reports 432 diagnostics across more than 240 files; the two new modules
appear in none of them. The import-hygiene gate fails three assertions on a
test-only private-reach count that regressed from a documented 94 to a live
107; running the scanner directly and filtering its inventory returns zero
sites under this Step's directory. The relative-imports gate is separately red
with six violations, all in one live-application test module.
