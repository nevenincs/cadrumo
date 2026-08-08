---
tags:
  - '#exec'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:51445f000e26f2fe55ec5a57a63373f65333d1562d6a2e907cb2dbccb275de63'
step_id: 'S09'
related:
  - "[[2026-08-08-m200-export-envelope-tag-plan]]"
---




# add a closed-set guard test asserting no accounts-regime concept (aseguradora, entidad de credito, inversion colectiva, garantia reciproca, estado de cuentas) exists anywhere in the registry or domain model outside an explicit allowlist, so a future addition fails the gate until both hardcoded discriminante literal '0' sites are revisited together

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_export.py`

## Description

- Add a guard asserting the Modelo 200 page-000 discriminante field is still a
  literal `0`, located by its AEAT-fixed byte position (offset 6, length 1) rather
  than by id or kind, since id and kind are exactly what the guard watches.
- Add a scan asserting no closed typed declaration channel -- the export
  `draft_attribute` token set and the binding source-kind set -- names the
  estado-de-cuentas axis or any of the four non-Normal regimes.
- Add a cross-site agreement assertion at the export surface: both envelope tags'
  discriminante bytes are read out of the rendered payload and compared against
  each other, not against a third restatement of the expected value.
- Factor both detectors into named predicates and give each an anti-vacuity
  control, so a matcher that never fires cannot read as a clean tree.

## Outcome

The discriminante's two independent authorities -- a registry literal for the
opening tag, a hardcoded character inside the closing tag's computed template --
are now tied together three ways: the literal cannot change or be re-kinded
silently, a typed channel that could feed it cannot appear silently, and the two
rendered bytes must agree. Each failure message names both sites, because fixing
one alone ships a fichero whose tags disagree about the filer's accounts regime,
and no completeness or parity gate reads that divergence: both tags stay
structurally well-formed.

The Step asked for a substring scan of the registry and domain model behind an
explicit allowlist. That shape was measured before being adopted and rejected: the
regime vocabulary matches 61 files under the source tree once the corpus and locale
catalogues are excluded -- casilla labels quoting AEAT's own wording, and unrelated
bindings whose ids contain "creditos" for dotaciones por deterioro de créditos. An
allowlist of that size is the honor-system list the quality rules forbid, and it
would detect nothing through the noise.

So the scan was narrowed to closed typed sets small enough to enumerate, which
carry none of the vocabulary today and therefore need no allowlist at all. The
substituted shape is not weaker for the Step's stated purpose -- it fires when a
regime concept becomes *declarable*, which is strictly earlier than when one
becomes *mentioned* -- but it is narrower than the literal wording, and a regime
concept introduced only as registry prose, with no typed channel and no change to
the discriminante field, would not trip it. That residue is stated rather than
papered over.

## Verification


Both guards, both anti-vacuity controls, the fixture anchor and the cross-site
agreement assertion, alongside every other test in the two modules they landed in:

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_export.py src/cadrumo/application/filing/tests/test_export.py -n0 -q
    81 passed in 20.67s

The controls are what make the detectors load bearing: each is exercised on input
that must trip it and on input that must not.

The fixture anchor is what makes the GUARD load bearing, which is a separate claim.
The scan is green today because its subject does not exist, so it was demonstrated
firing at the real site: a regime member was injected into the live binding
source-kind enum from a pytest plugin loaded outside the repository, and the real
guard went red on it.

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_export.py -k "accounts_regime" -n0 -q -s -p regime_plugin
    PLUGIN: injected ESTADO_CUENTAS into BindingSourceKind; live members now 28
    FAILED ...::test_no_typed_declaration_channel_names_an_accounts_regime_concept
    1 failed, 2 passed, 31 deselected in 0.72s

Nothing under the source tree changed for that proof, so there was no window in
which a peer sweep could commit the injected member. The permanent anchor test
carries the same coverage without the plugin, by scanning each real set with one
regime token added -- the shape a future addition actually takes.

## Notes

The Step's guidance pointed at the draft-attribute canonical-width table's
totality convention as the shape to reuse. That convention does not transfer: it
makes a RULING MAPPING total over a closed set, so adding a member without a ruling
fails. This guard asserts an ABSENCE, and there is no mapping to be total over. What
does carry across is its actual principle -- key the check on the property rather
than on the declarations that happen to exist now -- and the scan does that by
deriving both sets from the schema rather than listing today's tokens. Reusing the
convention's letter would have meant inventing a ruling table with no rulings in it.

The narrowing described above is a deliberate substitution of gate shape, not a
reduction of scope, and it is the one judgement in this Step a reviewer should
check rather than accept.
