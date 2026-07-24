---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S13'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

# Make the personal-data category derivation exhaustive by construction so a new portable-bundle schema field cannot silently vanish from the subject-access disclosure, classifying every bundle field as category-mapped, envelope metadata, or carried-namespace derived and refusing an unclassified field, gated on a non-tautological test that enumerates the model's own fields and proves an unmapped field fails

## Scope

- `src/cadrumo/application/user_profile/_bundle_export_contracts.py`
- `src/cadrumo/application/user_profile/tests/test_bundle_export.py`

## Description

- Enumerate the portable bundle's live field set and classify the two fields the
  category map never covered: the generic secure-object carry surface, whose personal
  data is disclosed per registry namespace out of the coverage manifest.
- Declare `_ENVELOPE_METADATA_BUNDLE_FIELDS` for the schema-version marker and the export
  provenance timestamp, each stated as describing the export rather than the subject.
- Declare `_CARRIED_NAMESPACE_DERIVED_BUNDLE_FIELDS` for the carry surface, stating why
  one carried-objects tuple cannot take a single flat field label.
- Add `_refuse_unclassified_bundle_fields` and call it from `bundle_data_categories`, so
  a field belonging to none of the three classifications refuses by name instead of
  falling out of the walrus lookup.
- Correct the module docstring, which claimed derivation from the schema without
  disclosing that the field-to-label mapping is still authored.
- Rewrite the derivation proof to walk the full serialized field set with no pre-filter,
  so an unmapped field raises rather than being skipped by the comprehension guard.
- Add a schema-coverage gate enumerating the model's own fields, asserting the three
  classifications partition them and that none names a field the schema no longer has.
- Add a refusal proof over a real pydantic subclass declaring an unmapped field.

## Outcome

The completeness claim the subject-access notice makes to a data subject is now
structurally backed rather than resting on someone remembering to edit a dictionary. The
notice's wording is unchanged, which was the point: the claim was made true rather than
softened.

Classification of the schema is total and enforced in production, not only in CI. A field
belonging to none of the three sets raises a typed export refusal naming it, which
follows the precedent this codebase already uses for a declared-but-unrouted registry
binding source rather than inventing a new posture. The two fields the previous map
silently skipped are now positively classified with their reason recorded beside them, so
the gap is explicit rather than a coincidence of the current field set.

Non-tautology is observed three ways. Removing the refusal makes the unmapped-field proof
fail on did-not-raise. Temporarily adding a field to the real portable-export model
reddens both the schema-coverage gate, which names the field, and the end-to-end
derivation proof, which fails through the real export path with the production refusal.
The proof of the refusal uses a genuine pydantic subclass carrying a real extra field, so
there is no monkeypatch, stub, or fake anywhere in it.

## Notes

The previous coverage assertion pre-filtered to fields already present in the map, so it
could not fail on the very drift it appeared to guard; it is replaced rather than
supplemented.

The refusal is scoped to top-level bundle schema fields. Personal data reaching the
archive through the carry surface is disclosed per namespace from the coverage manifest,
which is a separate derivation and keeps its own coverage semantics. Attachment evidence
bytes and remote captures remain excluded from the portable bundle by design, and the
notice already states that exclusion.
