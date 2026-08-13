---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:0b8f213feaf7c975d895f5ee7037de3b1ccd10209d702b227f1215c084ad9571'
step_id: 'S58'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# author the identifier-enrollment ratchet test asserting every production pydantic field whose name matches the namespace vocabulary carries a `core.identity` namespace alias rather than bare `str`, with `Declaracion.estado`, `Deuda.situacion`, and the three free-text sub-populations from `W07.P11.S48` as named, documented exclusions

## Scope

- `src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py`

## Description

- Derive the namespace vocabulary at runtime from the alias family `core.identity`
  actually exports, rather than from the deleted `IdentifierNamespace` enum.
- Walk production pydantic model fields at a pinned revision and report every
  identifier-named field still declared as a bare `str`.
- Rehome the three free-text sub-populations stranded by the enum deletion as
  falsifiable claims against the derived vocabulary.
- Record the adjudicated bare-by-design sites and the not-yet-enrolled population
  in two separate, stale-checked ledgers.
- Anchor the derivation, the shared stem, the free-text exclusions and the
  truncated-display-companion exclusion so none can pass vacuously.

## Outcome

Committed as `4c08b90d5defd68dd4d060996a8702571a0068b2`. Eleven assertions, green.

**Vocabulary derivation.** The row was written when an `IdentifierNamespace`
StrEnum named the vocabulary. That enum was deleted as a dormant symbol with no
consumer, so the vocabulary is now computed from the surviving alias family: every
name in the identity package's `__all__` that is a type alias — a PEP 695
`TypeAliasType` or an `Annotated[...]` object — contributes its snake_case
spelling, plus the same spelling with a leading `aeat_` issuer token stripped.
Classes, functions and scalar constants on the same facade contribute nothing.
Twenty-one aliases yield twenty-eight tokens. A field matches when a token is the
field name or a trailing token-run of it, so `parent_transaction_id` and
`winning_expediente_id` match while `financial_default_csv_encoding` does not.

Deriving rather than listing means a new alias widens the gate with no edit, and
deleting an alias cannot quiet it: a deletion narrows the vocabulary and strands
its sites in the ledgers, which the staleness assertions then fail.

Only the issuer token is stripped, never a distinguishing one. An earlier draft
generated every trailing token-run and was wrong: it reduced `filing_record_id` to
`record_id` and `calculation_revision_id` to `revision_id`, which erases exactly
the token separating two namespaces — a registry revision tag and a calculation
revision are different concepts sharing a suffix, and the deleted enum's own prose
said so. That reduction conflated the namespaces the taxonomy exists to separate,
and it was removed. One declared exception survives, `tax_id`, because two aliases
carry that concept and neither alias name is the field spelling; it is anchored by
an assertion that both aliases still exist.

**The rehoming.** The deleted enum carried a trailing comment block naming three
sub-populations deliberately outside the taxonomy, "recorded here so a later sweep
does not enroll them by name-shape and call the surface closed". This gate is now
their only consumer and their home. Each is stated with its reason and made
falsifiable rather than left as prose: an assertion proves its representative field
tokens are absent from the derived vocabulary, so adding an alias naming one would
fail the claim and force a re-adjudication instead of silently widening the gate.
The populations are AEAT-printed adjudicated-case prose, bounded free text the app
neither controls nor can enumerate; counterparty-issued document numbers, minted by
a third party under a numbering scheme this codebase may not constrain; and
identifiers from non-AEAT issuing authorities, each belonging to another authority's
namespace. The first is additionally anchored to two live occurrences — a
declaration's `estado` and a debt's `situacion` — which must still exist and still
carry free text, so retyping either fails the gate rather than leaving a stale
carve-out standing.

**Two ledgers, deliberately separate.** The adjudicated ledger names eight sites
ruled bare-by-design, each carrying its own reason: the two auth-session facts and
the two wizard setup answers are captured before validation runs, so validating at
those boundaries would refuse a session AEAT itself issued or crash while
constructing an answer record; the four LLM invoice-grounding claims are held
verbatim because canonicalising and uppercasing broke anchor matching against the
source text, a real regression rather than a hypothesis.

The second ledger records two hundred and thirty fields that are simply not yet
enrolled. Keeping them apart is the point: collapsing the two would make a recorded
gap indistinguishable from a considered carve-out. Both key on module, model and
field, never a line number, and both fail when an entry stops answering a live bare
occurrence, so the population can only ratchet down. The property is asserted as a
set of identities and never as a count.

**Reuse over reinvention.** The scanner consumes the existing pinned-revision source
reader and the existing bare-annotation and annotation-rendering predicates from the
identifier noun census rather than restating them, and follows the census-plus-gate
shape the hex-64 redeclaration ratchet established.

**Stated limits.** Only pydantic models are in reach, so the einvoice record batch's
dual-role party tax identifier — a frozen dataclass — is invisible and is named in
the module docstring so a green run is not read as covering it. Function parameters
are likewise out of reach. A `short_`-prefixed field is excluded structurally rather
than by allowlist, because it carries twelve characters of a sixty-four character
identity and the alias is strictly narrower than the value the field exists to
serve; that exclusion is anchored by proving every excluded companion has its full
sibling declared on the same model.

## Notes

**The row's premise did not hold, and this is the finding.** The plan's verification
section states this gate is green "against the fully-enrolled baseline". At the
revision measured, six hundred and fifty-three identifier-named production model
fields exist; four hundred and fifteen are enrolled and two hundred and thirty-eight
are still bare. One hundred and twenty-eight of those sit in the CLI entrypoint
layer, then the ledger, live, user-profile, modelo, auth and LLM suggestion
surfaces. By concept: bucket eighty-seven, transaction thirty-nine, profile
twenty-two, tax twenty-one, snapshot twenty-one, work-unit twenty, invoice fourteen,
calculation-revision thirteen, expediente ten, filing-record seven.

This is drift, not a layer convention, and one file proves it: in the ledger CLI
payload module the import transaction reference payload carries typed bucket and
transaction identities while the removal result payload beside it carries both as
bare `str` — same base class, same concepts, both spellings.

Only eight of the two hundred and thirty-eight were previously adjudicated. The
remaining two hundred and thirty are an unadjudicated enrollment gap. They were not
retyped here: that is outside this Step, and two hundred and thirty retypes across
live peer surfaces is its own campaign. They were not hidden either — they are
enumerated in the baseline ledger, greppable per site, and the ledger cannot grow
without a reviewer seeing the edit. The plan lead was notified before this record
was written so the campaign's completion criterion can be amended or a follow-up
enrollment row opened; a scope-narrowing note must say what the standing goal still
asks for that it excludes, and what it excludes is the enrollment of those sites.

**Gate collisions: none.** The gate was checked against the import-hygiene,
modelo-string-usage, CSV-normalisation-singularity, docstring cross-reference,
docstring well-formedness, docstring core-struct-link, marker-integrity,
relative-import, tautology, mock and monkeypatch gates. This module's name appears
in zero failure lists across all of them, and no oscillation was observed.

**Red gates outside this Step, all peer-owned and pre-existing.** The ratchet suite
reports eight failures and the docstring and import-hygiene suites ten more, none
naming this module: a tautological inequality assertion in an IVA rate-slot refusal
test; two banned recording and refusing attachment-store doubles in a notification
documents test; an architecture-marker mismatch in a registry export-value-policy
test expecting the domain marker; eleven pytestmark placement violations across dev
audit and application test modules; a production ECB provider gating a live read on
the pytest opt-in token; campaign metadata in dev CI and terminology test
docstrings; the absolute-self-import gate, which a separate agent is already
investigating as red at head; a TUI migration manifest census digest mismatch; and
an import-hygiene test-debt count that no longer matches its recorded manifest. The
tree-wide type check reports three hundred and eighty-three diagnostics across
roughly two hundred and forty files, none in this module.
