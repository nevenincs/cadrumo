---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:55017021034fef2aee0371beb4d0ace10479b8da2177543797aa20ef6585ca7a'
step_id: 'S250'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# URGENT CONFIDENTIALITY. Add an EU VAT identity rule to the CLI redaction funnel, whose tax-identity matchers are Spanish-shaped only and carry no EU VAT rule at all. Verified at HEAD through redact_for_cli_output: B12345674 and 12345678Z redact to a sha256 digest, while SE556677889901, DE811234567 and ESB12345674 all pass through RAW. The last is the sharpest, since it is a SPANISH taxpayer's own identifier written in the EU-prefixed form our own structured readers produce and our own parsers emit, and the ES prefix defeats the word boundary the CIF rule anchors on so the rule that catches the bare form does not fire. The IBAN pattern does not incidentally cover them either. It reaches real envelopes on the SUCCESS path: a German intra-community fixture confirming with exit 0 emits the counterparty identifier raw inside a notice context, and the same funnel governs every log line. The project rules name this apparatus the load-bearing confidentiality guarantee of the application, and it currently holds only for unprefixed Spanish shapes. Cover the prefixed form for every Member State INCLUDING ES, prove it on both redact_for_cli_output and redact_for_log, and anchor the gate on the PROPERTY that an identifier the VAT-prefix authority recognises must not survive the funnel, rather than a fixed list which would pin today's Member States the way a country pinned the vocabulary

## Scope

- `src/cadrumo/core`

## Description

- Declare a redaction strategy that admits a VAT identification number on its per-State structure, with Spain routed to the control-character authority the VAT format table omits.
- Add the scanning pattern for the prefixed spelling and enrol the rule in every policy that already redacts a tax identity.
- Gate the behaviour on the shipped format table's own declared examples, both directions, so a Member State added to the table joins the cases on the day it is declared.

## Outcome

The two shipped tax-identity rules anchor on a word boundary, and a country prefix is a word character, so a prefixed identifier presented no boundary before the body and neither rule fired. Measured before this change: a bare Spanish company identifier redacted to a digest while the same taxpayer's identifier in its prefixed spelling passed through raw, on operator output and log lines alike. Foreign numbers likewise. The bank-account arm beside them already states the correct reasoning in the other direction -- that an ES-only arm protects the domestic case and leaks the foreign one -- and that reasoning had not been applied to tax identities.

It was reaching real envelopes on the success path, not only on refusals: a confirming intra-community document emitted its counterparty's identifier verbatim inside a notice context at exit code zero.

Spain needed its own arm and that was the surprise. The shipped VAT format table carries twenty-seven entries and omits Spain, because Spanish identities belong to the control-character authority instead. A gate keyed only on that table would have missed the prefixed Spanish spelling, which is the sharpest case of the three.

The design is a wide scan admitted by a strict gate, following the bank-account arm rather than the shape-only identity arms: two leading letters plus an alphanumeric run collides with digests, opaque identifiers and document references, so the shape cannot be the evidence and the per-State structure decides.

## Verification

    uv run --no-sync pytest src/cadrumo/core/tests/test_redaction_nif_iva.py -n0 -q -m unit
    38 passed in 2.61s

    uv run --no-sync pytest src/cadrumo/core/tests/test_redaction.py src/cadrumo/core/tests/test_redaction_rule_enrolment.py -n0 -q
    25 passed in 5.53s

    uv run --no-sync pytest src/cadrumo/core/tests -n0 -q -m unit
    2 failed, 959 passed in 245.14s (0:04:05)

Both failures are tree-wide scanning gates flagging other lanes' test files -- route literals under the authentication adapter's tests, and year-qualified period tokens under two inbound adapter test directories. Neither is redaction-related.

Mutation proof from outside the repository, three rungs asserted: neutralising the per-State authority reds twenty-seven of thirty-eight cases. The eleven that stay green are the negative controls and the Spanish cases, which route through the control-character authority and are independently gated -- the discrimination that shows the two arms are not one.

## Notes

A probe of twenty real output tokens found the wide scan over-firing on none of them: invoice numbers, file names, digests, period codes and transaction identifiers all survive intact, because a separator breaks the scanned token.

That same property is a residual gap, and it predates this change: an identifier carrying separators passes raw in every shape, including a bare Spanish company identifier, because the shipped pattern has always had the limitation. The application normalises separators and treats the spellings as one identity, and the provenance envelope carries the verbatim printed form, so the spelling that reaches an operator is the one the funnel cannot see. Closing it means normalise-then-match rather than a wider pattern, which is a different risk profile and needs its own measurement; it is reported for a separate row rather than absorbed here.

For the Member States whose shipped format is structural rather than checksummed, the gate admits on shape alone and is therefore wider for them than for Spain. That is the correct trade for a confidentiality boundary -- over-redacting a lookalike costs readability, under-redacting costs a taxpayer's identity -- and is recorded so it is known rather than discovered.

Code review has not yet run against this change.
