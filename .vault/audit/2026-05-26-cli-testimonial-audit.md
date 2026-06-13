---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - "[[2026-05-21-cli-testimonial-audit]]"
  - "[[2026-05-21-persona-fleet-round3-findings-audit]]"
---


# `cli-testimonial` audit: `persona-fleet round 5 — Roser auth-surface findings`

## Scope

Fifth testimonial round, focused on the `aeat config auth` subtree.
One persona — Roser Marés, a Catalan-speaking autónoma setting up
digital authentication for the first time — exercising provider
listing, configure, switch, status, test, login, and diagnostics
end-to-end. Method: the testimonial playbook (CLI-only, no source,
isolated `AEAT_LOCAL_STORAGE_ROOT`, no live rights, `--output-language
ca`). Recovers the four Álvaro round-3 regression-persona residuals
that were tracked as task #37 but never persisted as their own audit.

## Findings

### BLOCKER — `auth configure` and `auth status` contradict each other on the certificate

`aeat config auth configure --provider certificate --file <path>`
returns `status = configured` and `next_action = aeat config auth
test`. Run immediately after, `aeat config auth status` returns
`configured = False`, `health_severity = error`, `health_summary =
"certificate path not configured"` — while `certificate_path` in the
same record IS the path just supplied. Configure and status disagree
on whether the certificate is configured. The summary lies about its
own state: the path is set; the field is named `certificate_path`;
status nonetheless claims the path is not configured. A normal
operator cannot decide which command to trust, and the loudest
severity (`error`) on a freshly-configured cert is the opposite of
what should be surfaced. The defect persists across provider
switches: switching to `clave_movil` and back to `certificate`
returns to the same broken state.

### BLOCKER — `auth login` refusal is raw engineering English

The refusal text `"AEAT_CERTIFICATE_PATH is not set; cannot build
CertificateBundle"` quotes an environment-variable name and a class
name. It is not user prose, not localised, and does NOT mention the
`AEAT_LIVE_TESTS_ENABLED` safety gate that should be the primary
reason a non-live tool refuses login. A Catalan-speaking taxpayer
gets neither safety reassurance nor a translation. The persona
explicitly read this as a traceback fragment, not an error message.

### BLOCKER — `--output-language` not accepted on `auth status` / `auth test` / `auth login`

`aeat config auth status --output-language ca` and the equivalents
on `test` / `login` fail with `Error: No such option:
--output-language`. The Typer commands do not register the option.
Other auth commands (`configure`, the `clave_movil` mismatch
message) DO honour Catalan, so the tool can speak it — but the two
commands a worried operator runs most are silent in their
preferred language. The flag works on sibling commands and must
work here.

### MAJOR — `auth test` is observably `status --verbose`

`auth test` returns the same record as `auth status` plus three
session-related rows whose values are uniformly empty / `None` /
"no token on disk; run `auth login`". The command's name promises
an active verb — open the `.p12`, verify PKCS#12 well-formedness,
check expiry, walk a cert chain — but executes none of it. This
is the round-3 G5 finding (`auth test observably identical to
auth status`) still present after the #28 remediation; the new
diff is three informational rows, not an actual test.

### MAJOR — `health_severity` contradicts its own summary

For `clave_movil`, `auth status` returns `health_severity = error`
with `health_summary = "Preparat; requereix finalització de Cl@ve
mediada per l'operador."` ("Ready; requires operator-mediated
Cl@ve completion"). The summary describes a normal pending state;
the severity calls it an error. The same severity / summary
mismatch appears on the certificate path with a misleading
summary. A user-facing severity field that disagrees with its own
description is worse than no severity at all.

### MAJOR — phantom DNI in `clave_movil` identity_alignment

`aeat config auth configure --provider clave_movil` reports
`identity_alignment = mismatch` with detail naming a NIF
`<redacted real-shaped NIE>` that the persona never typed. The text suggests this
is a default fixture leaking into a live session. The proposed
`next_action` ("switch to the profile whose tax id matches the
Cl@ve DNI/NIE") is impossible — the persona has one profile and
the NIF in the detail is not theirs. The `next_action` string also
drops out of Catalan into English mid-sentence.

### MINOR

- `auth providers` lists `clave_pin`, `clave_permanente`,
  `dnie_pkcs` as `reserved` without a "no disponible aún" gloss.
  A layperson reading "reserved" reads it as "reserved for me" —
  confusion the surface should remove. The refusal on attempted
  use IS clear; the listing above is what misleads first.
- `configure --provider certificate` accepts a non-existent path
  and persists it; `auth status` then cannot distinguish "no path
  set", "path set, file missing", "path set, file present" — all
  surface as the same misleading "not configured" with `error`
  severity. Three different operator failure modes deserve three
  different messages.
- The provider-switch round-trip (certificate → clave_movil →
  certificate) lands back on the first BLOCKER's broken state;
  the specific "cert path leaks after switch" round-3 G1 fear is
  NOT present (the path correctly clears when the active provider
  is `clave_movil`), but the return path resurfaces the same lying
  severity.

### POLISH

- `auth status` mixes Catalan and English in the same payload —
  the `health_summary` is rendered in English while a sibling
  `probe_summary` in the same record renders in Catalan.
- `next_action` strings embed CLI invocations with bare `NAME` /
  `PATH` placeholders that a real user does not recognise as
  placeholders. They should be quoted or angle-bracketed.

## Recommendations

The three BLOCKERs and three MAJORs cluster on a single surface —
`src/aeat/application/auth/` plus the CLI entrypoint — and resolve
naturally as one focused remediation:

- Make `auth status` agree with `auth configure`: the health check
  must read the configured cert path and report `configured = True`
  with no `error` severity when the path is set and resolves to a
  file; surface "path set, file missing" as a distinct degraded
  state; "no path set" as a distinct undeclared state.
- Make `auth login` refusal user prose: cite the
  `AEAT_LIVE_TESTS_ENABLED` safety gate first, never the env-var
  name or class name, localise to es / en / ca / hu via the locale
  CLI, and explain the next step.
- Register `--output-language` on `auth status`, `auth test`,
  `auth login` (parity with `configure` and other commands).
- Make `auth test` genuinely test: open the `.p12`, parse PKCS#12,
  check expiry, surface a real `probe_result` distinct from
  `status`. Close round-3 G5.
- Make `health_severity` and `health_summary` consistent: a
  reassuring summary cannot pair with `error`; an `error` summary
  cannot pair with a reassuring severity. Lower severity to
  `warning` / `info` for normal pending states.
- Remove the phantom real-shaped DNI/NIE fixture leak; if the value is
  a placeholder it must be obviously such, not a real-shape NIF.

Remediation tracked as the round-5 auth-surface cluster fix.
