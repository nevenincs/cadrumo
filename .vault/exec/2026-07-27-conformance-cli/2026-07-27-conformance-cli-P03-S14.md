---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:7678e743058a3312dbd4beb5f1a3d4493c6a0d4ca6eb46634d1c69e67e0d43c0'
step_id: 'S14'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# build the Typer cli and __main__ with report and coverage verbs, greppable key=value text rows and strict --json payloads

## Scope

- `dev/registry/conformance`

## Description

- Add `cli.py` with a Typer app named `conformance` and `__main__.py` so the surface runs
  as `python -m dev.registry.conformance`, following the matrix and terminology-handbook
  trio precedent. No `aeat` root is touched; the module docstring states that non-impact
  explicitly, as the terminology CLI's docstring does.
- Add the `report` and `coverage` verbs, each with `--json` and `--no-validate`.
- Emit the strict pydantic payload through `model_dump_json` for `--json`, and the
  greppable renderers otherwise.
- Emit a `warning rows=0` record when a screen composes nothing, while keeping the exit
  at zero.

## Outcome

Both verbs always exit 0. That is the decided screen-first posture, and the module
docstring gives the reason rather than only the rule: the picture is currently bad —
ninety unreviewed revisions, five dead schema axes, independent-check coverage under five
per cent — and a screen that refused to render would leave the backlog unread and teach
peers to route around the tool. Gate teeth belong to `audit --check`.

The one honesty addition beyond rendering is the vacuity warning. An empty render that
said nothing would be indistinguishable from a clean registry, which is the false-green
shape this surface exists to remove, so the screen keeps its zero exit but says outright
that its counts describe the read rather than the registry. It is a record line, not
prose, so a caller greps it.

Verification, actual output of `report` against the real bundled registry:

```
summary registry_validated=true revisions=90 modelos=73 engineered_by_declared=0
independent_check_coverage=0.0460 reconciled_casillas=1261 independently_checked_casillas=58
reconciles_nothing_rows=39 grounding_findings=0 modelo_scope_classification_findings=24
required_coverage_gap_rows=0 coverage_unmeasured_rows=0 unattributed_oracle_payloads=0
unmatched_oracle_evidence=0 bundled_oracle_payloads=21 scope_diagnostics=0
unattributed_scope_diagnostics=0 locale_unavailable_modelos=0
census review_status=agent_reviewed revisions=0
census review_status=operator_reviewed revisions=0
census review_status=pending_review revisions=90
row modelo=036 revision=2025-02-03-y-siguientes registry_validated=true
  review_status=pending_review engineered_by=n/a reviewed_by=n/a reviewed_at=n/a
  calc_grade=true casillas=31 formulas=0 bindings=1 verification_expectations=1
  extraction_profiles=1 completeness_manifest=true fixed_width_export=false
  xml_dictionary_export=false reconciled_casillas=1 declared_grounded_casillas=0
  independently_checked_casillas=0 independent_check_coverage=0.0000 grounding_findings=0
  required_coverage_gap_tiers=- modelo_authorization=authorized
  modelo_authorization_evidence_class=threshold_continuity modelo_calculation_class=filing
  modelo_tax_domain=censo modelo_scope_classification_findings=0 scope_diagnostics=0
  latest_revision_probed=2025-02-03-y-siguientes support_probe_describes_this_revision=true
  locale_audited_locales=3 locale_labels_required_per_locale=31 locale_labels_translated=6
  locale_complete_locales=0 locale_stale_keys=0
```

Modelo 038 in the same run shows the distinction the whole design turns on:
`reconciled_casillas=0 independent_check_coverage=n/a` — no claim, rendered as no claim —
beside modelo 036's `reconciled_casillas=1 independent_check_coverage=0.0000`, a real
claim scoring zero.

Actual output of `coverage`, first twelve axes:

```
summary registry_validated=true revisions=90 modelos=73 axes=26
axis axis=revision.calc_grade scope=revision measured=52 population=90 fraction=0.5778
axis axis=revision.verification_expectations scope=revision measured=51 population=90 fraction=0.5667
axis axis=revision.completeness_manifest scope=revision measured=52 population=90 fraction=0.5778
axis axis=revision.extraction_profiles scope=revision measured=31 population=90 fraction=0.3444
axis axis=revision.fixed_width_export scope=revision measured=23 population=90 fraction=0.2556
axis axis=revision.xml_dictionary_export scope=revision measured=6 population=90 fraction=0.0667
axis axis=external_grounding.independently_checked_casillas scope=casilla measured=58
  population=1261 fraction=0.0460 caveat="coverage of independent checking, never
  correctness: a low value means most reconciliation here is the engine agreeing with
  itself, not that any number is wrong"
axis axis=external_grounding.declared_grounding_claims scope=casilla measured=58
  population=1261 fraction=0.0460 caveat="a declaration that a casilla is externally
  grounded, not evidence that it is"
axis axis=external_grounding.revisions_reconciling_nothing scope=revision measured=39
  population=90 fraction=0.4333 caveat="these revisions make no independent-check claim at
  all, which is not a claim of zero"
axis axis=oracle_payloads.unattributed scope=payload measured=0 population=21 fraction=0.0000
axis axis=oracle_evidence.unmatched scope=payload measured=0 population=21 fraction=0.0000
axis axis=authorization.authorized scope=modelo measured=30 population=73 fraction=0.4110
```

Two details are deliberate. The caveat is OMITTED on axes needing none rather than
rendered `n/a`, because an axis needing no caveat has not failed to measure one. And the
JSON payload carries `measured` and `population` but no precomputed `fraction`, so a
programmatic consumer cannot take the ratio without also seeing its denominator.

`--json --no-validate` confirms the label survives serialisation: the envelope reports
`registry_validated: false`, all 90 rows carry `false` individually, and
`independent_check_coverage`, `required_coverage_gap_tiers`, `modelo_authorization` and
`latest_revision_probed` are `null` rather than `0`.

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator direction;
grounding was by whole-file reads and `rg`.

This Step's files did NOT land under a commit of mine. An operator-directed sweep,
`33129cc83f` "chore(worktree): operator-directed commit of all in-flight work", committed
the entire working tree including `cli.py` and `__main__.py` while I was preparing their
pathspec commit. Nothing was lost and the content is what I intended — verified by
diffing `git show HEAD:<path>` against the working tree — but the audit trail attributes
this Step's code to that sweep rather than to a commit carrying its reasoning. Recorded so
the trail is honest rather than tidy.
