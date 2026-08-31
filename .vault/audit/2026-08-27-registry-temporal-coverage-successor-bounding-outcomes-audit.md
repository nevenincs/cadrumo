---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:8d198cb09a46a7003b9774f0839fd950de0ae302b976704681490c2b0e4994dc'
related:
  - "[[2026-08-27-registry-temporal-coverage-design-authority-declaration-adr]]"
---

# `registry-temporal-coverage` audit: `Successor-bounding outcomes across five design gaps`

## Scope

The five design `applies_to` gaps ruled extendable, each taken behind the
documented negative search the ruling requires. Two were extended. Three were
stopped, and each stop found something the gap census could not see.

## Findings

### m181-both-gaps-closed | resolved | the successor rule held where the evidence held

`aeat-dr-181-2009` ran to 2015-12-31 and `aeat-dr-181-2017` to 2021-12-31. The
bundled corpus holds four modelo 181 designs (2009, 2016, 2017, 2022) with
nothing between them, and the BOE consolidated text for BOE-A-2009-21165 lists
exactly three amending norms -- HFP/1923/2016, HFP/1308/2017 and HFP/1192/2022 --
so neither 2010-2015 nor 2018-2021 carries a modification. Both bounds were
era-end stamps, not evidenced boundaries. Checked for collisions as well as
holes: the design overlaps in the tree are pre-existing intra-year sub-period
splits and none involves modelo 181, so both extensions tile.

Noted outside the gaps: Orden HAC/747/2025 (BOE-A-2025-14600) approves modelo 181
again in 2025, which the open-ended 2022 design may eventually need to account
for.

### m202-intervening-ordenes-are-bundled | high | the gap was never empty

Three modelo 202 designs sit inside the 2010-2012 window and each names its own
orden: `aeat-dr-202-2010-v13` (EHA/664/2010), `aeat-dr-202-2012-v32`
(HAP/2055/2012) and `aeat-dr-202-2013-v33` (HAP/636/2013). All three carry no
`applies_from` and no `applies_to`.

That is why the gap census read the span as empty: it walks only designs that
HAVE a window. The span was never unevidenced -- it holds three real designs with
no declared window. Extending `aeat-dr-202-2008` across it would have asserted
that pagos fraccionados for 2010-2012 filed under the 2008 layout, which the
bundled corpus itself contradicts.

The remedy is not successor-bounding. It is the version-to-period adjudication
already recorded as pending for those three ("the official version label does not
establish a filing-period window").

### m165-supersedes-the-original-escalation | high | a third answer neither option held

Orden HFP/1284/2023 (BOE-A-2023-24412), article 13, modifies Orden HAP/2455/2013
-- modelo 165's approving orden -- adding a field to the tipo-1 declarante record
identifying `Empresa emergente` declarants. So `aeat-dr-165-2016-2022` did NOT
govern 2023-2025 unmodified, and successor-bounding it would have asserted a
superseded layout for three filing years.

The 2026 design's window is correct, checked against the document rather than its
filename: the bundled file is named `actualizado-en-2023`, but its own heading
reads `Ejercicio 2026` and it already carries the emergente field. AEAT publishes
only the current diseno, consolidated.

This supersedes the modelo 165 layout-authority escalation raised earlier in this
campaign, which offered two options -- accept the 2022-12-31 bound, or
successor-bound to 2025-12-31 -- and both are wrong. The 2023-2025 era has no
layout authority because THE DESIGN THAT GOVERNS IT WAS NEVER ACQUIRED.

### m194-search-incomplete-and-a-date-conflict | medium | stopped on two counts

The bundled corpus is clean (2019, 2023, 2024; nothing 2020-2022), but the
authoritative BOE consolidated amendment list could not be reached: the ELI
consolidated URL 404s and the `doc.php` hit for an "Orden de 18 de noviembre de
1999" resolves to BOE-A-1999-22309, which approves modelos 123 and 193 -- a
different orden of the same date. Searches surface only HFP/1284/2023 and
HAC/1504/2024, i.e. nothing in 2020-2022, but that is search-summary evidence,
not the consolidated list.

Separately, `aeat-dr-194-2019` cites the "Orden de 18 de ENERO de 1999" in its
corpus path while BOE consistently names modelo 194's approving orden the "Orden
de 18 de NOVIEMBRE de 1999" -- including HAC/1504/2024, which modifies "la Orden
de 18 de noviembre de 1999, por la que se aprueba el modelo 194". The block
already admits the AEAT historical-index title was retained verbatim. The
successor-bounding argument rests on knowing which orden governs, so this
grounding question comes first.

## Recommendations

Acquire and enrol the modelo 165 diseno edition covering ejercicios 2023-2025 --
the HFP/1284/2023 state, before the 2026 edition. Enrolment asserts
`review_status = reviewed`, so it needs the operator. This closes the modelo 165
layout-authority gap properly, and the earlier escalation's two options should be
retired rather than answered.

Give the three modelo 202 designs their filing-period windows. That is a
version-to-period ruling on the official version labels, not a bound extension.

Settle whether modelo 194's approving orden is dated January or November 1999
before any bound is moved, and record the answer on the source.

Extend the gap census to report designs that carry NO window alongside the gaps
themselves. As written it can only see windowed designs, so it reports a span as
empty when the corpus holds designs nobody has dated -- which is exactly how the
m202 gap read as a candidate for extension.
