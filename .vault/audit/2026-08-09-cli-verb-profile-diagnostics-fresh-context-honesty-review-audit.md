---
tags:
  - '#audit'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:78707b702c49c49f6fecf25e8d5824a3f035c67c0a3912550da6ec0aed1b3815'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
  - "[[2026-08-09-cli-verb-profile-diagnostics-adr]]"
---

# `cli-verb-profile-diagnostics` audit: `Fresh-context honesty review`

## Scope

## Findings

## Recommendations

## Context

## Method

Fresh-context honesty review per the campaign-close rule: read the plan as if just inherited, verify claims against current code rather than trusting prose. All 36 steps at review time had exec records with real content (36-40 lines each, no scaffold residue) - the "checked box, nothing behind it" failure mode is absent here.

**Cross-reference:** a second, independently-run honesty review landed concurrently as `[[2026-08-09-cli-verb-profile-diagnostics-closure-honesty-review-audit]]`, reaching the same two actionable findings by a separately-run census. Treat the two documents as one finding independently confirmed twice, not two separate findings.

## F1 - Verification gates are phase-scoped but read as campaign-scoped (structural, highest severity)

P04 ("Verification and honesty review") closed all three of its Steps: S17 sequential run, S18 locale parity, S19 honesty review. But P05-P09 (roughly half the campaign, ~17 Steps) were CREATED BY S19 and land after it - the phase descriptions say so outright ("found during the honesty review", "found by the closing locale-catalogue sweep"). The plan's Verification section names exactly those three activities as closure criteria, so the campaign could be declared complete on a verification that never saw half the work. S17's record states the owner surface is green - true when written, predating `test_export_declarant_identity_grounding.py`, `_overview_calendar_support.py`, `test_status_refusal_grounding.py` and `test_session_identity_refusal_grounding.py`, none of which existed yet.

Not anyone's error - structural, because the review that satisfies the gate is also what generates the work that invalidates it.

**Action taken:** added Phase P11.S44 (this review's own P11), a terminal re-verification step re-running S17/S18/S19-shaped checks after every Phase through P11 lands. Campaign must not be declared complete until that step is green.

## F2 - The "closing locale-catalogue sweep" (P09) was not exhaustive

An independent census (every one of the 161 real profile-schema field keys matched as a dotted token against operator prose in en.yml) found three more messages of the same raw-dotted-path defect class still in the catalogue, not caught by P09's sweep:
- `application.modelo.findings.m210_baseline_tipo_deferred.next_action`
- `application.modelo.findings.m210_convenio_rate_missing.next_action`
- `application.modelo.findings.representante_fiscal_required.next_action`

Two further candidates (`cli.config.{get,set}.key_help` naming `iva.regime`) were examined and ruled OUT - there the dotted key is the literal argument format the operator types, not a raw field-path leak.

## F3 - Those three paths are not merely raw, they are WRONG (severity upgrade on F2)

The three messages instruct the operator to set `profile.country_of_fiscal_residence` and `profile.representante_fiscal_nif`. There is no `profile` section in the schema. The real paths are `taxpayer_type.country_of_fiscal_residence` and `taxpayer_type.representante_fiscal_nif`. An operator following the current message is misdirected to a field path that does not exist.

Verified against the live schema: `taxpayer_type.country_of_fiscal_residence` -> "Country of fiscal residence (trlirnr-rdleg-5-2004:art-2, :art-25.1.a, :art-25.1.f)"; `taxpayer_type.representante_fiscal_nif` -> "Fiscal representative NIF (trlirnr-rdleg-5-2004:art-10)".

**Action taken:** added Phase P11.S43 to fix these three sites through the same schema-derived-label mechanism P08/P09/P10 already use, with the same operator-label-not-raw-path test pattern.

## F4 - Audit recommendation 3 has no owner and no row

The originating audit's recommendations 1 and 2 became Phases P07 and P08. Recommendation 3 ("scope the next inventory by behaviour, not location") was a method change with no Step, no gate, no follow-up reference - and F2/F3 are direct evidence it was not fully applied, since the closing sweep (P09) still stopped early using a location-scoped rather than behaviour-scoped method.

**Resolution:** actioned by this review itself - the F2 census was explicitly behaviour-scoped (every real schema field key checked against every catalogue message, not a location/pattern guess), and it is what surfaced F2/F3. Recommendation 3 is satisfied by this review's method; no further row needed beyond the P11 fix it produced.

## F5 - Four exec records precede their Steps (noted, not a defect)

P09.S33-S36 had complete exec records while their boxes were unchecked and target files were live peer WIP at review time (they have since landed). Not a defect - legitimate work in flight - but the inverse of the usual "checked but not done" trap: a scan for "does every closed Step have a record" would read clean while records described work not yet landed. Recorded so a future reader does not conflate record-presence with completion.

## Verified vs not run

**Verified:** `dev.locales scaffold --check` (all four catalogues ok), exec-record coverage and content for all reviewed steps, the three F2/F3 sites and their correct schema paths, the two ruled-out false positives.

**Deliberately not run:** the S17 sequential suite - long, and the P09 files were live peer WIP at review time, so a run then would have measured an in-flight edit rather than the landed tree. Covered by the new P11.S44 terminal re-verification requirement instead.

**Known limit of the F2 census:** swept `en.yml` only (the locale parity gate means the finding transfers to es/ca/hu, but the census itself only read English prose), and keys off dotted tokens - a message naming a field in prose without a dot ("set your fiscal residence country") would not be caught by either this census or the original P09 sweep. That class remains unmeasured.

## Recommendation

Do not close this campaign on the current Verification section. Minimum bar: P11.S43 (the three F3 sites) lands, P11.S44 (terminal re-verification) runs green, and this document stands as the record that recommendation 3 was actioned via behaviour-scoped method rather than left open.
