---
tags:
  - '#audit'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:3bd829a0be85a5b77fce36c1e43a48435e16c4af6eb19ba5718f32e06f52a826'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
  - "[[2026-09-07-quality-gate-zero-closure-blind-green-gates-adr]]"
---
# quality-gate-zero-closure audit: S114 locale-bound detector implementation review

## Scope

Reviewed W08.P25.S114 against the accepted blind-green decision and its exact
four-locale catalogue and declaration-derived pinning requirements. The review
covered the uncommitted locale-bound detector, its test gate and non-collected
fixture as evidence, the production declarations in language_argv.py and
external_constants.py, and the real catalogue layout. No production or test file
was changed.

Direct production-scanner probes reproduced the catalogue, ordering, and data-flow
findings below. The declared spellings are read successfully as --language,
--lang, and --output-language, their three equals prefixes, and
CADRUMO_OUTPUT_LANGUAGE. The gate itself contains a prohibited monkeypatch.

## Findings

### incomplete-catalogue-join | high | the real sweep loads only one domain file from each locale

The gate constructs each locale corpus from cli.yml alone, although every locale
catalogue is distributed across nine YAML domain files and the detector API already
accepts multiple paths. This silently excludes application, error, common, and
other translated output from the join. As a direct control, the unique English
application literal Rounding produces no finding with the gate's cli-only corpus
but produces the expected English-only finding when all locale YAML is loaded.
The four locale keys are present, but their catalogue contents are incomplete, so
S114's four-catalogue join does not cover the real output vocabulary.

### same-line-pin-ordering | high | an explicit declared pin before an assertion on the same line is reported as unpinned

Pin state is filtered by source line with assignment line strictly less than
assertion line. Therefore an assignment from invoke_cached_cli using --lang=en,
followed by a semicolon and the absence assertion on the same line, is reported as
locale-bound even though the invocation is explicitly pinned. The committed
fixture currently expects this false positive. A gate that rejects a legitimate
declared pin creates the suppression pressure forbidden by the accepted decision.

### pin-propagation-is-not-causal | high | any pinned return or referenced output can hide an unpinned result

Output-helper discovery promotes a helper when any return expression is pinned,
rather than when the return reaching the call is pinned. A helper with one pinned
return and one unpinned return is classified pinned even when called with the
argument selecting the unpinned branch; the production scanner returns no finding.
The assignment state has a second independent overreach: any previously pinned
output name appearing anywhere inside a later call makes the later result pinned.
Passing a pinned result through an unrelated audit keyword therefore hides an
unpinned invocation. These are blind-green false negatives in the detector written
to expose blind-green assertions.

Dynamic equals-form f-strings are also treated as pins solely because their literal
prefix matches, without proving that the dynamic value is one of the supported
locales. This is safe only when the value's supported-locale domain is established;
the current implementation establishes no such binding.

### prohibited-monkeypatch-gate | high | the locale gate proves UTF-8 use by replacing Path.read_text

test_catalogue_loader_requests_utf8 uses pytest monkeypatch to replace
Path.read_text and observe its encoding argument. The governing plan prohibits
mock and monkeypatch evidence for these detector gates because call observation
can remain green without proving real filesystem behaviour. This is a binding
violation even though the test belongs to the S115 gate surface rather than the
S114 production module.

## Recommendations

For incomplete-catalogue-join, construct each locale corpus from every declared
locale YAML domain used by operator output and add a control whose literal lives
outside cli.yml. Keep the locale set explicit and prove all four are populated.

For same-line-pin-ordering, order assignments and assertions by AST traversal
position within the same lexical scope, then replace the current false-positive
expectation with a control proving a preceding same-line declared pin is accepted.

For pin-propagation-is-not-causal, bind pin state to the value that actually
produces the asserted output. Do not mark a helper pinned from one of several
possible returns, and do not inherit output pin state merely because a pinned name
appears in an unrelated argument. Either prove the dynamic equals-form locale
domain or retain it as unknown rather than pinned. Add each reproduced specimen as
a detector control.

For prohibited-monkeypatch-gate, exercise the real filesystem adapter under a
non-UTF-8 ambient locale and assert decoded content and source attribution through
the public loader. Do not replace or spy on Path.read_text.

S114 is not approved. Four high findings remain; no critical finding was found.
**2026-09-07 repair re-review - all four high findings.** The real gate now
loads every YAML domain file for each of en, es, ca, and hu. The independent
Rounding control, whose producer is outside cli.yml, is reported as an English-only
locale binding under the Spanish axis. This closes incomplete-catalogue-join.

Assignment state now uses same-scope AST traversal position. A declared --lang=en
assignment preceding its assertion on the same source line is accepted, while
nested lexical scopes are excluded. This closes same-line-pin-ordering.

Pin recognition reconstructs only fully literal f-strings and requires their value
to be a supported locale. Environment and output helper fixed points require every
explicit return to be pinned, and arbitrary pinned call arguments no longer
propagate pin state to the call result. Independent probes now report the unpinned
branch of a mixed helper, an unpinned result carrying an unrelated pinned audit
argument, and an unknown dynamic spliced locale; literal declared forms remain
accepted. This closes pin-propagation-is-not-causal.

The UTF-8 loader control now writes and reads a real accented catalogue through the
production loader. The locale gate contains no monkeypatch, unittest.mock, patching
API, or mock-object use. This closes prohibited-monkeypatch-gate.

The focused non-residual gate selection passed 51 tests in 7.80 seconds. Ruff lint,
Ruff formatting, and ty passed over the detector and gate. The complete real-tree
axis reports eight live assertion sites, seven under Spanish and one under English.
Those findings are honest S115 repair input and demonstrate the detector is biting;
they are not an S114 implementation defect and are not suppressed here.

S114 is approved. All four high findings are closed and no high or critical finding
remains.