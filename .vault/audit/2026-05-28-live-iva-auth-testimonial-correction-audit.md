---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `live-iva-compensation-wallet` Auth Evidence Correction

The operator states on 2026-05-28 that they have never completed AEAT
authentication in this work. This testimonial is authoritative for the live
evidence record.

Any earlier plan, audit, or execution wording that implies an operator-approved
AEAT login, successful Cl@ve completion, filed-history read, wallet/cartera
read, or promotion of live AEAT IVA history is disputed and must not be used as
accepted evidence.

Accepted evidence categories after this correction:

- local code and local tests that exercise production application paths;
- encrypted diagnostic/auth-attempt artifacts, only as auth-attempt evidence;
- browser navigation, selector, and route observations before completed auth;
- redacted storage and report-shape checks that do not include private taxpayer
  values.

Not accepted as evidence until a fresh operator-observed live run completes:

- current AEAT IVA wallet or cartera balance;
- filed Modelo 303 or Modelo 390 history from AEAT;
- multi-year AEAT IVA compensation history;
- successful Cl@ve authentication;
- any promoted remote IVA balance derived from AEAT live data.

Next live work must require a fresh read-only auth attempt observed by the
operator, record only redacted aggregate shape, and keep every AEAT surface
typed as unauthenticated or failed until that run reaches the intended read
surface.
