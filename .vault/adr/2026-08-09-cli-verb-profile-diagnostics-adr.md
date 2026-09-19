---
tags:
  - '#adr'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:5f1042fadcd580635634c91ba412fe9908d808845e6ff5bf581c75b3e4736382'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-reference]]"
---

# `cli-verb-profile-diagnostics` adr: `Schema-derived profile refusals across CLI verbs` | (**status:** `accepted`)

## Problem Statement

A CLI verb that refuses because the active profile lacks specific information
must tell the operator which field is missing, under its human label, with its
legal basis where the registry grounds one. Several verbs instead print a raw
internal identifier: a profile selector token, a registry binding id, or a bare
count. The inventory in `2026-08-09-cli-verb-profile-diagnostics-reference`
records each site with its locator.

A decision is needed on the MECHANISM before any site is touched, because the
obvious per-site fix - hand-writing a better sentence at each call site - is
exactly the fragmentation this project already removed once for the readiness
gate.

## Considerations

- The canonical mechanism already exists and is proven:
  `build_profile_preflight_requirement` backs the readiness gate,
  `config profile preflight` and `app modelo readiness`. Per
  `2026-08-09-cli-verb-profile-diagnostics-reference`, its coverage is
  incomplete, not its design.
- Every site in scope holds a `model_selectors` token or a binding selector key,
  not a `section.field` path, and no by-selector index exists. The reference
  records this as the one missing primitive.
- The project's CLI contract makes the typed `Notice` channel the only sanctioned
  operator-facing diagnostic channel; one site in scope raises a Click parameter
  error instead.
- A message fix and a verdict flip are separable, and only the former is
  sanctioned here. The standing deferral on the three readiness surfaces is a
  decision about which profiles REFUSE, not about what they read when they do.

## Considered options

- **Per-site bespoke messages.** Rejected: reproduces the scattered-authority
  defect the canonical builder was introduced to remove, and each site would
  re-derive labels and legal refs independently and drift.
- **Widen `build_profile_preflight_requirement` to accept selector tokens
  directly.** Rejected: it would silently change the meaning of its `path`
  argument for every existing caller, and a token that collides with a field key
  would resolve ambiguously with no signal.
- **Add a dedicated selector-to-path resolver, then route every site through the
  existing builder unchanged.** Chosen.
- **Rewire the deferred readiness surfaces onto the schema verdict at the same
  time.** Rejected: flips the readiness verdict for real profiles, which is a
  product decision with its own review, not a side effect of a message fix.

## Constraints

- The resolver depends only on the loaded `ProfileSchemaDefinition`, which is
  already available at every site in scope, so no new registry-authority
  plumbing is required.
- Selector tokens are declared per field in the profile schema and are not
  guaranteed unique by construction; the resolver must therefore be built from
  the loaded schema and must refuse to guess when a token is ambiguous or absent
  rather than returning an arbitrary match.
- Not every identifier reaching these sites is a profile selector. The overview
  warning stream mixes profile-field warnings with censo, justificante and
  evidence-conflict warnings whose codes are genuine warning codes. Enrichment
  must resolve the profile subset and pass the rest through untouched.
- Any new operator-facing string needs real translations in all four locale
  catalogues through the locale CLI.

## Implementation

A single resolver maps a declared selector token to its `section.field` path by
walking the loaded profile schema's sections and fields, returning nothing when
the token names no field or names more than one. It lives with the other
schema-reading helpers in the profile domain package and is promoted to that
package's public facade, since consumers sit in both the application and
entrypoint layers.

Each site in scope then resolves its identifiers through that resolver, feeds
the resolved paths to `build_profile_preflight_requirement` unchanged, and
renders the resulting requirement rows - label, and legal refs where grounded -
rather than the raw identifier. An identifier the resolver does not recognise is
rendered as it is today, so a non-profile warning code degrades to current
behaviour instead of being mislabelled.

The overview refusals additionally move from the Click parameter error onto the
shared envelope's refusal path so a missing profile fact reads as a
workflow-state refusal rather than invalid operator input. The refusal
CONDITION at each site is left exactly as it is.

## Rationale

The knockout criterion is that a refusal message must be derived from the same
authority as the readiness verdict it explains. Once the selector-to-path gap is
closed, every site in scope reaches the existing builder with no new grounding
logic, so labels and legal refs cannot drift between the gate that refuses and
the message that explains the refusal - which is precisely what a per-site fix
would allow.

Choosing a separate resolver over widening the builder keeps the builder's
contract intact for its existing callers, and makes the ambiguity case explicit:
the resolver returns nothing rather than guessing, so an unresolvable token
degrades to today's output instead of being confidently mislabelled.

## Consequences

Operators reading any refusal in scope get the field's operator label and its
legal basis, from the same schema the gate consults. The overview refusals also
become machine-readable through the typed notice channel.

The honest limits: a field the registry does not ground contributes no legal
refs, and that is correct - nothing is invented. A selector token that is
ambiguous or absent still renders raw, so the fix is a strict improvement rather
than a guarantee that no raw identifier can ever reach an operator; closing that
fully would require the schema to guarantee token uniqueness, which it does not
today.

This work deliberately leaves both the readiness verdicts and the known wrong
legal citation on the Modelo 100 declarant-identity cluster untouched. A
consequence worth stating plainly: enriching a refusal with a field's existing
`legal_refs` will surface that wrong citation to operators at more surfaces than
before. That is the correct behaviour for this mechanism - it reports what the
registry carries - and it raises the value of fixing the citation, but it does
mean this work increases the visibility of a known defect it does not own.
