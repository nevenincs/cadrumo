---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:71672b749c4532d0181685400ee2a206fa6e888b6e2b0c03ec2d85732523a42a'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `source-casilla-integration audit: s175 cli row identity redaction review`

## Scope

Independent review of the CLI review allowlist, safe fingerprint projection, output-channel redaction, encrypted failure behavior, and activity-label preservation.

## Findings

### s175-cli-row-identity-redaction-review | high | resolved implicit application payload inheritance

The initial CLI payload subclassed the application review model and began from its unrestricted dump, so a future sensitive application field could cross the CLI boundary automatically. The final payload is an independent output schema with an explicit field allowlist and field-by-field construction.

### s175-cli-row-identity-redaction-review | medium | resolved CLI failure-channel proof gap

The first tests called payload helpers directly and later removed the sensitive canaries before exercising failure. The final test invokes the registered command and mutates only the encrypted identity coordinate while proving the raw identity and fingerprint remain present, then scans stdout, stderr, exception, formatted traceback, and logs.

### s175-cli-row-identity-redaction-review | pass | final CLI projection is value-safe

JSON and text review surfaces expose only safe cohort fingerprints. Raw identity fields refuse without echoing their values, secure serializer contexts cannot bypass the projection, legitimate activity labels survive, and neighboring calculation-revision commands retain their explicit projections. Final review reported zero findings.

## Recommendations

Proceed with S176 using the encrypted identity and safe CLI contracts without adding raw source-row identities to ordinary operator output.
