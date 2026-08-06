---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:138bc7966dae27fb131a796837f55809cc24f2e29008323c8b90ec957e939869'
step_id: 'S51'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Bundle RD 1619/2012 art. 4 and refuse a factura simplificada for an entrega intracomunitaria exenta (art. 4.4.a), declaring the amount-threshold and sector-list eligibility axis unverified pending an ADR amendment

## Scope

- `src/cadrumo/_data/corpus/normatives/html`
- `src/cadrumo/domain/invoices/_models.py`
- `src/cadrumo/domain/invoices/tests`

## Description

- Fetched the current consolidated BOE text of RD 1619/2012 art. 4 (Facturas
  simplificadas) live from `boe.es` and bundled it verbatim into
  `src/cadrumo/_data/corpus/normatives/html/rd-1619-2012-art-4.html`, matching
  the shape of the three already-bundled articles (2, 6, 11). Verified the
  written file byte-identical to the fetched source, paragraph by paragraph,
  including the apostrophe-bearing `artículo 2.3.b) b')` cross-reference.
- Read the full article before designing anything: it carries FOUR distinct
  eligibility axes, not one ceiling -- an amount threshold (400 EUR general,
  apartado 1.a), a SECOND amount threshold restricted to a closed list of
  ~14 named sectors (3.000 EUR, apartado 2), an AEAT-discretionary
  authorisation for other cases (apartado 3), and four categorical exclusions
  independent of amount (apartado 4, a-d).
- Modelled ONLY the one categorical exclusion representable from fields
  already on `Invoice`: apartado 4.a) forbids a factura simplificada for an
  entrega intracomunitaria exenta (`IvaCategory.INTRA_COMMUNITY_SUPPLY`)
  outright, regardless of amount or tax id. Added the guard to
  `_validate_invoice_class_consistency`, citing RD 1619/2012 art. 4.4.a.
- Found and fixed a real, closeable hole this uncovered: the existing
  `_SIMPLIFICADA_MANDATORY_TAX_ID_CATEGORIES` re-imposed the counterparty NIF
  requirement for this category when SIMPLIFICADA, but silently ALLOWED the
  combination to construct once a NIF was supplied -- the actual prohibition
  (never issue SIMPLIFICADA for this category at all) was never enforced.
  Updated the now-superseded existing test
  (`test_invoice_simplificada.py::test_a_simplificada_is_refused_outright_for_an_exempt_intracommunity_supply`,
  renamed from ...`_still_requires_the_tax_id_for_an_exempt_intracommunity_supply`)
  and added a dedicated `test_invoice_simplificada_eligibility.py` with full
  polarity: the degraded case (refused, with the art. 4.4.a message, even with
  a valid tax id present) plus four truthful companions (the same operation as
  ORDINARIA; as RECTIFICATIVA; SIMPLIFICADA for a different category; and
  SIMPLIFICADA with no declared category).
- Declared the REST of art. 4 unverified, not silently assumed: the two
  amount thresholds (the record has no field for the closed ~14-sector list
  the 3.000 EUR tier depends on, and even the simpler 400 EUR rule is a
  PERMISSION, not a hard ceiling, since the sector exception and the
  apartado-3 AEAT authorisation can both legitimately raise or bypass it -- a
  naive "refuse over 400" check would produce false refusals on legitimate
  higher-value retail/hostelería/etc. invoices), the AEAT-discretionary
  apartado 3 (a live administrative fact no document field could ever state),
  and the other three categorical exclusions (4.b distance sales / art.
  68.Tres.a, needing a LIVA cross-reference against the existing OSS fields;
  4.c self-billing by a non-established foreign provider per art. 5, needing
  a "who physically issued this document" fact the record does not carry,
  even after the concurrently-landed issuer-establishment derivation, which
  answers a different question -- whether OUR OWN taxpayer is established,
  not whether the counterparty self-billed; 4.d, a cross-reference to art.
  2.3.b)b') not yet analysed). This declared gap is documented in the
  `_validate_invoice_class_consistency` docstring and needs the ADR
  amendment the plan Step names; requesting it from the team lead as
  instructed rather than authoring it here.

## Outcome

RD 1619/2012 art. 4 is bundled and its FULL text read and analysed, not just
a proof-of-concept citation. The eligibility hole the team flagged (any
invoice could self-declare SIMPLIFICADA to escape the counterparty-NIF
requirement) is narrowed by the one exclusion this record can enforce today
without inventing a fact: an entrega intracomunitaria exenta can no longer be
documented as SIMPLIFICADA, full stop. The remaining, larger amount- and
sector-dependent eligibility question is a declared, documented,
ADR-pending gap rather than an implicit assumption -- the hybrid answer
between the plan Step's (a) and (b) options, chosen because art. 4 itself
splits cleanly into a representable categorical axis and an unrepresentable
amount/sector/discretion axis.

Two unrelated incidents occurred and were resolved during this Step's
mutation-proofing (both already reported to the team lead in chat): (1) this
agent's own stale-backup `cp`-based mutation restore briefly overwrote a
peer's concurrently staged fix in the working tree; recovered with zero data
loss via a read-only `git show :path` extraction from the index, since the
peer's work was already staged. (2) the peer's subsequent apply-cached commit
(`8efa8b7f3c`) unintentionally captured this agent's mutation-probe dead code
(`if False: ...`) into its committed tree, briefly shipping a guard that
could never fire at HEAD; caught immediately after re-running the suite and
fixed with an isolated one-line corrective commit (`e91c30663b`). Both
incidents are now closed; the general hazard (an apply-cached isolation copy
must be built from `git show HEAD:path`, never from the live working tree,
even when only isolating "the other part") has been reported for the standing
safety guidance.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/invoices/tests/ -q --no-header -n 0
    186 passed in 6.57s

    uv run --no-sync ruff check src/cadrumo/domain/invoices/_models.py src/cadrumo/domain/invoices/tests/test_invoice_simplificada.py src/cadrumo/domain/invoices/tests/test_invoice_simplificada_eligibility.py
    All checks passed!

    uv run --no-sync ruff format --check src/cadrumo/domain/invoices/_models.py src/cadrumo/domain/invoices/tests/test_invoice_simplificada.py src/cadrumo/domain/invoices/tests/test_invoice_simplificada_eligibility.py
    3 files already formatted

Mutation proof (redone with surgical `Edit`-based mutate/restore after the
`cp`-restore incident above): disabling the new art. 4.4.a guard
(`if self.invoice_class is InvoiceClass.SIMPLIFICADA and self.iva_category is
IvaCategory.INTRA_COMMUNITY_SUPPLY:` replaced with `if False:`) reddened
exactly the two tests targeting it
(`test_invoice_simplificada.py::test_a_simplificada_is_refused_outright_for_an_exempt_intracommunity_supply`
and
`test_invoice_simplificada_eligibility.py::test_a_simplificada_entrega_intracomunitaria_is_refused_regardless_of_tax_id`),
2 failed / 184 passed, nothing else. Restored via the exact inverse `Edit`
call (no whole-file copy); the full suite returned to 186 passed and `git
diff` against the pre-mutation working tree showed zero unexpected changes.

The bundled corpus file was verified byte-identical to the live BOE fetch by
comparing every `<p class="parrafo">` paragraph's normalised text
programmatically (25/25 matched, including the apostrophe-bearing
`artículo 2.3.b) b')` line), not by manual proofreading alone.

## Notes

- Both incidents above are also filed as their own coordinator-tracked
  findings (the dead-guard one independently surfaced as a tracked finding
  before this record was written). No further action needed here beyond what
  is already stated; this Notes section exists to keep the incident account
  self-contained in the Step that produced it.
- The ADR amendment this Step's declared gap needs was requested from the
  team lead in chat per their explicit offer ("If you take (b), the ADR needs
  the amendment -- say so and I will write it"); this Step took a HYBRID of
  (a) and (b), so the amendment covers only the amount/sector/discretion/
  self-billing/distance-sale portion, not the intracommunity exclusion this
  Step already implemented.
- `test_invoice_intracommunity_destination.py` and
  `test_secure_storage_roundtrip.py` were checked for any existing
  SIMPLIFICADA + INTRA_COMMUNITY_SUPPLY fixture the new guard might silently
  break; neither combines the two, so no other test needed updating beyond
  the one renamed above.
