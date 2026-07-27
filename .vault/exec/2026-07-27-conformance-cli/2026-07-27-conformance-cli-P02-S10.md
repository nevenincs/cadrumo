---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S10'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# add the per-revision conformance profile composer with strict typed row models, composing model-law coverage, support matrix, registry-scope diagnostics, authorization state, external grounding, and governance stamps

## Scope

- `src/cadrumo/application/registry/_conformance.py`

## Description

- Add `_conformance.py` under the registry application package: strict frozen
  pydantic rows (`RevisionGovernanceStamp`, `RevisionCapabilityFacts`,
  `LatestRevisionSupportProbe`, `RevisionModelLawCoverage`,
  `RevisionConformanceRow`, `RegistryConformanceProfile`), the pure fold
  `build_registry_conformance_profile`, and the bundled entry point
  `audit_bundled_registry_conformance`.
- Export the six models and two functions through the `application.registry`
  public top-level facade.
- Promote `REQUIRED_COVERAGE_TIERS` (renamed from the private
  `_REQUIRED_COVERAGE_TIERS`) and `RequiredCoverageTier` out of the coverage
  module, and promote `validate_registry_scope`, onto the registry package
  facade, because a cross-package consumer must not dot into a private
  submodule and promotion is a precondition of the consuming change.
- Regenerate the API reference stubs for the new module.

## Outcome

The composer emits exactly one row per modelo revision in the loaded tree and
joins six previously unjoined fact sources onto it: model-law evidence-tier
coverage, the support matrix, registry-scope diagnostics, the derived
authorization capability, the external-oracle grounding fold, the
classification-coherence fold, and the declared governance stamp. Verified over
the real bundled registry: 90 rows across 73 modelos.

Four semantic decisions carry the weight.

Status stays derived. No per-modelo status scalar is read and none is
synthesised; the row exposes the individual signals and the module docstring
states that a composed row is discovery evidence, not authority to act. The only
declared axis is the governance provenance stamp.

Scope is carried in the name, not attributed silently. The support matrix probes
the modelo's LATEST revision only, so it is not spread across every revision
row: per-revision capabilities are resolved from the revision itself into
`RevisionCapabilityFacts`, while the support probe travels as
`LatestRevisionSupportProbe` naming `probed_revision` and stating
`describes_this_revision` outright. Over the bundled tree the probe describes
73 of the 90 rows, so 17 rows would otherwise have carried a current capability
attributed to a superseded revision.

Absence is distinguishable from zero everywhere it matters.
`independent_check_coverage` returns `None`, never `0.0`, when a revision
reconciles nothing at all, because no coverage claim exists to report; 39 of the
90 rows are in exactly that state, against 42 rows that do reconcile and score a
real zero. The three axes that require the validating authority are `None` in
degraded mode rather than defaulted. Reporting the authorization as
`UNAUTHORIZED` there would have asserted the default-deny verdict for an axis
nobody checked, which is the precise failure this rule exists to prevent.

Degraded-mode labelling rides on the row. `registry_validated` is a field on
every emitted `RevisionConformanceRow`, not only on the envelope, so a renderer
that drops the envelope flag cannot present a degraded row as validated
authority. Confirmed: all 90 rows of a `validate=False` compose carry
`registry_validated=False`.

Registry-scope diagnostics that name no single modelo and revision are preserved
on `unattributed_scope_diagnostics` rather than dropped, mirroring the
`unattributed_payloads` shape the sibling grounding fold already established.

Verification run over the real bundled registry, validated mode:

```
validated compose 12.7s
rows=90 modelos=73 validated=True
review census: {'pending_review': 90, 'agent_reviewed': 0, 'operator_reviewed': 0}
reviewed=0 engineered_by_declared=0
required coverage gap rows=0
registry-wide independent_check_coverage=0.045995241871530534
grounding findings=0
scope diagnostics=0 unattributed=0
unattributed oracle payloads=1 unmatched evidence=0
rows reconciling something=51 rows reconciling nothing=39
zero-coverage-but-reconciling=42
rows the support matrix actually describes=73
rows on authorized modelos=47
```

Degraded mode:

```
degraded compose 2.7s
rows=90 validated=False
rows stamped unvalidated=90
coverage absent=90 support absent=90 auth absent=90
has_required_coverage_gap values: {None}
```

Gates: `ruff check` and `ruff format` clean on every touched file; `ty check`
clean; `pyright` clean (0 errors); the core-struct docstring link gate passes
(`3 passed in 16.56s`); `python -m dev.docs.apidocs scaffold` emitted exactly
two stub deltas, both naming this module.

## Notes

The mandatory semantic-discovery probe was WAIVED for this campaign by explicit
operator directive: the semantic index is broken and the service is stopped
under a hands-off order. Discovery was carried by whole-file reads of each fact
source before composing it, plus targeted content search for the exact symbols
and facade exports.

The fact-lifts review record for this campaign is an unpopulated scaffold — it
carries no findings body — so its findings could not shape what this step
trusts. The two remediations it produced are visible only as closed plan rows.

Owner-vs-peer triage on the layered import-contract linter: it reports two
broken contracts on the current shared tree, and neither names this module or
package. The tree carries 725 dirty paths from concurrent campaigns; the
breakage is peer churn, not owned by this step.

`pyright` widens a `Literal` tier to `str` through a generator comprehension, so
the three coverage-tier locals are explicitly annotated. The reason is recorded
at the site rather than left as an unexplained annotation.

The composer consumes the support matrix through `build_support_matrix`, which
takes a `ValidatedRegistryAuthority`. That is why the probe is absent rather than
recomputed in degraded mode: re-deriving it from the raw definitions would have
created a second implementation of a fact the matrix already owns.
