---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S37'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# extend the fragment placement refusal to the remaining legally load-bearing revision scalars legal_refs, orden_aplicabilidad and valid_to, closing the last instance of the readability hazard the governance refusal proved worth closing

## Scope

- `src/cadrumo/domain/calculations/registry/_loader.py`
- `src/cadrumo/domain/calculations/registry/_schema.py`
- `src/cadrumo/domain/calculations/registry/_schema_base.py`
- `src/cadrumo/domain/calculations/registry/__init__.py`
- `src/cadrumo/domain/calculations/registry/tests/test_revision_manifest_only_placement.py`

## Description

- Add a `ManifestOnlyMarker` and its `MANIFEST_ONLY` singleton beside the
  governance marker, with a `manifest_only_fields` derivation reading it back
  out of pydantic's retained annotation metadata. Mark `legal_refs`,
  `orden_aplicabilidad` and `valid_to` on the revision model, and derive
  `REVISION_MANIFEST_ONLY_FIELDS` from the marker.
- Make `GovernanceStampMarker` a SUBCLASS of `ManifestOnlyMarker` rather than a
  sibling, so the governance fields are manifest-only by construction and the
  governance vocabulary stays exactly its four scalars.
- Extend the loader's fragment refusal to the derived manifest-only set, keeping
  the governance branch first so its existing diagnostic and the assertions that
  read it are untouched, and give the legal scalars a message naming why they
  are pinned.
- Export the derived set through the registry package facade beside the
  governance one.
- Add a placement module driving the real directory loader over real on-disk
  TOML: the parametrized refusal over the derived set, the
  placement-not-content differential, the two shapes the pre-existing
  redeclaration guard could never have caught, the marker separation, the
  gate-reads-the-derived-object pin, the enrolment and marked-versus-unmarked
  flip, and the shipped-tree floor.

### The marker design call

Governance provenance and legal grounding are different subjects, and the
difference is load-bearing rather than philosophical. The governance field set
is the stamp VOCABULARY: the conformance report reads it as declared provenance
and the dev-side stamp writer emits it key by key. Marking `legal_refs` with the
governance marker would have made the stamp writer try to write a revision's
legal grounding as a provenance claim, and would have reddened the gate that
pins the writer's key set to the derived field set. So they had to be separate
markers.

They could not be independent siblings either. Two sibling markers means a
governance field added tomorrow needs BOTH to keep its placement guarantee, and
forgetting the second is precisely the failure the derived set was built to
remove — it would reopen the laundering route inside the mechanism that closed
it. Making the governance marker a SUBCLASS resolves both constraints at once:
the placement derivation matches on the base class and so captures every
governance field automatically, the stamp derivation matches on the subclass and
so stays narrow, and governance-implies-manifest-only becomes a type relation
nobody can forget to restate. Two markers, two derived sets, one placement
refusal, and the subset relation holds by construction rather than by
discipline.

## Outcome

The tightening was gated on a sweep, run before any edit. Every bundled section
fragment was parsed the way the loader parses it — the `[revisions."<id>"]`
table — and every TOP-LEVEL key counted, so a `legal_refs` nested inside a
casilla or a construct is not miscounted as a revision scalar:

```
revision fragment directories: 90
section fragment files parsed: 15945
distinct top-level revision keys across all fragments: 19
top-level key census: [('application_links', 217), ('bindings', 665),
 ('casilla_continuidad_evolutions', 15), ('casillas', 12663),
 ('completeness_manifest', 76), ('constructs', 153), ('deadline_windows', 94),
 ('dependency_classifications', 52), ('export_layouts', 208),
 ('extraction_profiles', 37), ('filing_schedules', 34), ('formulas', 1122),
 ('live_cross_references', 46), ('parameters', 325), ('period_selector', 1),
 ('relations', 57), ('verification_expectations', 69),
 ('verification_predicates', 21), ('workbook_parity_refs', 90)]

HITS on ['legal_refs', 'orden_aplicabilidad', 'valid_to'] + governance keys: 0

revision.toml manifests omitting legal_refs: 0
```

Zero hits, so no bundled revision loses anything. The census also reproduces the
earlier campaign's result exactly: one non-section scalar anywhere in the tree, a
period selector in a Modelo 303 fragment, and zero governance keys. The manifest
half of the sweep was added on top, because the redeclaration guard only fires
when the manifest already carries the field, so a manifest silent on its legal
grounding is the shape a fragment could have supplied it for unchallenged; all
90 declare it.

The shipped tree still compiles, and the two derived sets read as intended:

```
modelos=73 revisions=90
governance:    ['engineered_by', 'review_status', 'reviewed_at', 'reviewed_by']
manifest-only: ['engineered_by', 'legal_refs', 'orden_aplicabilidad',
                'review_status', 'reviewed_at', 'reviewed_by', 'valid_to']
```

The governance set is byte-for-byte what it was, which is what keeps the stamp
writer and its gate untouched.

The new module is `16 passed in 10.10s`, marked `unit` so the repository's
default lane selects it — `16 tests collected`, no deselection. Together with the
governance stamp module it is `47 passed in 11.40s`. The whole registry package
is `3134 passed, 2 warnings in 245.26s`. The dev-side conformance CLI gate, which
consumes the governance field set and was not edited, is `31 passed in 58.34s`.
`ruff format --check` reports `5 files already formatted`, `ruff check` and `ty`
report `All checks passed!`, `pyright` reports `0 errors` (two pre-existing
private-usage warnings for intra-package test imports), and `apidocs scaffold
--check` reports `Stub tree is conformant. No drift detected.`

Three mutations flip assertions, each run in a child process against the real
loader with every touched source restored byte-for-byte afterwards and the
restore confirmed by digest:

```
=== MUTATION D1: loader placement refusal for manifest-only fields deleted ===
7 failed, 9 passed
FAILED ...::test_a_manifest_only_field_declared_in_a_section_fragment_is_refused[legal_refs]
FAILED ...::test_a_manifest_only_field_declared_in_a_section_fragment_is_refused[orden_aplicabilidad]
FAILED ...::test_a_manifest_only_field_declared_in_a_section_fragment_is_refused[valid_to]
FAILED ...::test_the_refusal_is_about_placement_not_content
FAILED ...::test_a_fragment_cannot_append_a_second_approving_orden
FAILED ...::test_a_fragment_cannot_supply_legal_grounding_the_manifest_never_declares

=== MUTATION D2: MANIFEST_ONLY markers dropped from valid_to and legal_refs ===
3 failed, 11 passed
FAILED ...::test_the_refusal_is_about_placement_not_content
FAILED ...::test_a_fragment_cannot_supply_legal_grounding_the_manifest_never_declares
FAILED ...::test_the_manifest_only_set_is_exactly_todays_marked_fields

=== MUTATION D3: governance marker demoted from subclass to sibling ===
3 failed, 9 passed
FAILED ...::test_the_governance_stamp_is_manifest_only_by_type_not_by_a_second_marker
FAILED ...::test_the_manifest_only_set_is_exactly_todays_marked_fields
FAILED ...::test_a_newly_marked_field_enrols_itself_into_the_right_set

restored _loader.py       ...5949 identical=True
restored _schema.py       ...9dfa identical=True
restored _schema_base.py  ...1101 identical=True
```

D2 is the enrolment proof: removing the marker from two fields and changing
nothing else drops them out of both the derived set and the refusal, so
enrolment is a property of the declaration rather than of a list. D3 is the
design proof: demoting the governance marker to a sibling immediately breaks the
subset relation and the separation case, which is the failure mode the subclass
exists to prevent. In every mutation the majority of cases still pass, so none is
killing a fixture.

D1 additionally showed the shipped-tree floor red, which is NOT a real signal and
was chased down rather than assumed. Mutating a registry-package source re-keys
the compiled disk cache, whose key folds a content hash of every file in that
package, and the parallel workers then race rebuilding it. Re-run serially under
the identical mutation, that case is `1 passed in 11.39s`. Recorded because a
reader comparing the counts would otherwise read a real failure there.

## Notes

**Discovery waiver.** The mandatory semantic-discovery probe was explicitly
waived by the operator for this campaign: the semantic index is broken and its
service is stopped, with a standing instruction not to start, restart, reindex or
otherwise touch it. Grounding was literal search plus whole-file reads of the
schema base module, the revision model, the loader's fragment merge and its
derived field-set computations, the governance stamp module, and the dev-side
consumers of the governance set.

One scalar was deliberately left out and is reported rather than fixed. The sweep
found a single `period_selector` declared in a Modelo 303 section fragment. It is
arguably manifest-only on the same reasoning, since it decides which periods a
revision governs, but marking it would refuse the shipped tree until that
fragment is corrected, and the Modelo 303 registry subtree was explicitly out of
bounds for this Step with a peer active in it. It is a one-line correction plus
one marker for whoever owns that tree next.

The facade was entangled with live peer work and was staged accordingly. A peer
holds an uncommitted retraction of the filing-year grounding resolver from the
same file, so a pathspec commit would have taken the working-tree copy and
carried their in-flight change under this SHA. Only the two authored additions
were staged, as a HEAD-anchored own-edits-only patch applied straight to the
index; the staged set was verified to name exactly five files and to carry zero
occurrences of the peer's symbol immediately before a no-pathspec commit of the
verified index. Their working-tree change is untouched and HEAD is coherent — the
facade still exports the symbol the module still defines.
