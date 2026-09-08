---
tags:
  - '#audit'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:1bc80f21bd491cd0f23979b937b2be0fadbfba8a047cd727e3684c8ba714d17d'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
  - "[[2026-09-07-quality-gate-zero-closure-blind-green-gates-adr]]"
---
---
tags:
  - '#audit'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:f9c3597260d85e9da76be41b0506ca2548cf5753ab9e5bcec501cd3495d886cf'
related:
  - "`2026-08-24-quality-gate-zero-closure-plan`"
  - "`2026-09-07-quality-gate-zero-closure-blind-green-gates-adr`"
---
# quality-gate-zero-closure audit: S118 taxonomy absence conformance implementation review

## Scope

Reviewed W08.P26.S118 against the accepted blind-green-gates decision, the owning
plan, the new detector, its non-collected fixture corpus and 51-test gate, the
modified `PINNED_TAXONOMY_LITERALS` declaration sites, deletion of the superseded
off-lane conformance test and exception/debt tables, mutation configuration and
reported disposition, and the S118 execution record. Focused probes exercised the
required stale and undeclared directions plus adversarial site identity and
assignment-order cases. No production, test, plan, fixture, or execution record was
changed.

The real-tree sweep and basic anti-vacuity floor are present: the gate scans more
than 500 product test modules and refuses any finding. The supplied direct controls
for one undeclared literal and one stale token pass. The old shrink-only,
homonym-exception, and embedded-exception implementation is deleted. The mutation
record reports exact selected, killed, and individually classified inert counts
rather than a score. These strengths do not close the findings below.

## Findings

### declaration-does-not-name-an-exact-site | high | a module-wide token declaration silently authorises new sites and survives deletion of its stated site

The accepted declaration is site-specific: its adjacent rationale must name why a
particular assertion site is correct, an undeclared site must fail, and deleting
that site must make the declaration stale. The implementation instead parses only
a module-wide `frozenset[str]` and treats any nonempty adjacent string as adequate.
It neither extracts nor validates a function/site identity from that rationale.
Once `buckets` is declared anywhere in a module, every later raw `buckets` absence
in that module is accepted without changing the declaration or its rationale.

An independent specimen declared `buckets` for `test_one`, then added an otherwise
identical raw absence in `test_new`; the scanner returned no findings. A second
specimen deleted the declared absence site but retained an unrelated executable
`OTHER = "buckets"`; `_used_declared_tokens` treated that unrelated string as a
source site and again returned no findings. Thus both required drift directions
pass in realistic same-token cases, and the declaration behaves as the unchecked
module-token allowlist the ADR forbids.

### assignment-index-ignores-program-order | high | an accessor assignment anywhere in the function hides a raw asserted path

`_assigned_values` aggregates every simple assignment in the containing function
without binding each use to its nearest preceding write. `_dependency_nodes` then
expands all values ever assigned to a name, and `_routes_through_accessor` exempts
the entire assertion if any one of those values calls a canonical accessor. A raw
`target = tmp_path / "buckets"` immediately before the assertion is therefore
silently accepted when `target` was assigned from `storage_path(...)` earlier; an
accessor assignment after the assertion has the same masking effect. Independent
probes of both forms returned no findings. This is a false-negative path through
the core accessor-or-declaration predicate.

### banned-monkeypatch-in-gate | high | the replacement gate violates the plan's explicit test-double prohibition

`test_scan_paths_reads_utf8_sources_explicitly` accepts `monkeypatch`, replaces
`Path.read_text`, and mutates four locale environment variables through the
fixture. The plan explicitly permits no mock or monkeypatch in any Step. The real
child-process locale half does not cure the binding violation, and the execution
record does not disclose it. The gate therefore cannot be accepted in its current
form even if its UTF-8 claim is otherwise valid.

## Recommendations

For declaration-does-not-name-an-exact-site, make the declaration structurally bind
each sanctioned assertion locator, such as its containing test identity plus the
specific taxonomy token, and validate that the adjacent rationale names that exact
site. Require one-to-one conformance: adding another site with an already declared
token fails undeclared, and deleting or moving the named site fails stale even when
the token remains elsewhere. Add both adversarial controls.

For assignment-index-ignores-program-order, resolve names at each assertion to the
nearest preceding write in the same lexical scope, treating unsupported or
ambiguous writes as barriers rather than unioning all assignments. Add controls for
raw-overwrites-accessor and accessor-after-assertion, plus nested-scope and
same-line ordering where applicable.

For banned-monkeypatch-in-gate, replace the `Path.read_text` spy and environment
mutation fixture with real observation and explicit try/finally restoration or a
fresh-process environment. Add a repository scan proving the gate and fixture carry
no mock or monkeypatch spellings.

Re-run the focused controls, complete real-tree sweep, and bounded mutation run
after these mechanisms change; the existing 404-kill/6-inert disposition does not
cover the newly demonstrated false-negative behaviors.

S118 is not approved. Three high findings remain; no critical finding was found.
**2026-09-07 UTF-8 control re-review - banned-monkeypatch finding resolved.**
The current gate no longer imports or accepts `monkeypatch` and no mock or
monkeypatch spelling remains in the implementation, gate, or fixture corpus.
`test_scan_paths_reads_utf8_sources_under_a_c_locale` writes a real UTF-8 source,
scans it normally, then executes the real path scanner in a spawned process under
`LC_ALL=C`, `LANG=C`, `PYTHONCOERCECLOCALE=0`, and `PYTHONUTF8=0`. Environment
changes are restored in a `finally` path. This closes banned-monkeypatch-in-gate.

S118 remains unapproved on the two mechanism findings: declaration-does-not-name-
an-exact-site and assignment-index-ignores-program-order. No critical finding
remains.
**2026-09-07 exact-site and source-order remediation re-review.**
The stable implementation SHA-256 was
`C973FDF82A03D3F70B3F74C97C10B831CA3A9BC945D6B8AFA00A9358A8758D05`
before and after independent execution of the complete focused suite, which passed
59 tests in 15.40 seconds. All 32 production declaration modules carry
`PINNED_TAXONOMY_ABSENCE_SITES` entries.

Declaration identity now binds the qualified containing function, one-based
same-scope absence ordinal, taxonomy token, and normalized assertion expression.
Controls prove a second same-token site is undeclared; deletion remains stale despite
unrelated token use; duplicate assertions in one function are distinguished; and
function renames or expression changes produce both stale and undeclared findings.
This closes declaration-does-not-name-an-exact-site.

Assignment expansion now chooses the nearest preceding write by source position,
never a future assignment, and refuses to use conditionally guarded assignments as
accessor provenance. The raw-overwrites-accessor, accessor-after-assertion, and
conditional-branch controls all pass. This closes assignment-index-ignores-program-
order. The real-tree sweep retains its greater-than-500-module anti-vacuity floor,
and no mock or monkeypatch spelling is present.

### accessor-origin-is-not-verified | high | unrelated callables named storage_path suppress undeclared sites

The scanner treats any imported name whose imported symbol is `storage_path` or
`bucket_scoped_storage_path` as canonical without checking its module, and
`_routes_through_accessor` accepts any attribute call with either method name
without resolving its receiver. Independent specimens using
`from unrelated import storage_path` and `fake.storage_path("buckets")` each returned
no findings for a raw taxonomy-bound absence assertion. Neither routes through the
canonical storage-taxonomy accessor. A coincidental or adversarial callable name can
therefore bypass both the exact-site declaration and the undeclared-site failure,
which is a false negative in the core accessor-or-declaration predicate.

For accessor-origin-is-not-verified, derive accepted direct aliases only from the
canonical accessor module and accept attribute forms only when their receiver is a
verified import alias for that module. Add positive canonical qualified/aliased
controls and negative foreign-import and arbitrary-object-method controls, then
rerun the real-tree and mutation proofs.

S118 remains unapproved with one high finding. No critical finding was found.
## 2026-09-08 final single-declaration re-review

This section supersedes the earlier recommendations and conclusions in this
audit where they describe or endorse `PINNED_TAXONOMY_ABSENCE_SITES`. That
parallel declaration was rejected and removed. It is not part of the accepted
mechanism.

The current implementation has one checked declaration surface:
`PINNED_TAXONOMY_LITERALS: frozenset[str]`. A raw taxonomy-related absence
assertion is conforming only when it routes through a verified canonical
storage accessor, or the declared token has an adjacent rationale naming both
the containing function and the token. A second same-token assertion without
that site-naming rationale fails undeclared; removing the executable source
site leaves a stale declaration. Standalone strings and docstrings do not
manufacture source sites.

The source-order finding is closed. Nearest preceding writes are resolved
within the relevant lexical scope; future and conditional writes do not confer
accessor provenance. Direct and qualified accessor calls are accepted only
when their import origin is canonical. Foreign imports and arbitrary objects
with a coincidental `storage_path` method remain raw sites.

Synthetic source modules live in the named, non-collected fixture corpus. The
definition-line control is a genuine one-physical-line function. It killed the
last behavioral survivor, which changed
`candidate.lineno <= node.lineno` to `candidate.lineno < node.lineno`.

The current gate passes 69 tests, including the real-tree sweep, positive
controls, greater-than-500-module anti-vacuity floor, both drift directions,
source-order cases, and accessor-origin cases. Ruff lint, Ruff formatting, and
`ty` pass. A fresh external-`/tmp` mutmut 3.7.0 run selected 472 mutants,
killed 462, left 10 individually reviewed inert survivors, and produced no
other outcomes in approximately 58.2 seconds. The survivors are limited to an
impossible taxonomy placeholder, declaration/rationale exclusion equivalents,
valid nested-span equivalents, an impossible equal AST position, a
current-taxonomy subset equivalent, and the `UTF-8` codec alias. No mutation
score was calculated or used.

The superseded off-lane gate, its shrink-only `PENDING_UNDECLARED` list, and
the rejected parallel declaration symbol are absent. No mock, monkeypatch,
suppression, baseline, threshold, exclusion, skip, xfail, or unchecked
allowlist closes this class.

S118 is approved. No critical or high finding remains.
