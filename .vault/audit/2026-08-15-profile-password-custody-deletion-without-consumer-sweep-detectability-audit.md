---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:dd8c8567069254003b9de5cb82c5a767eb63d57b9c91d8294ab901ea117911de'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `deletion without consumer sweep detectability`

## Scope

Whether a deletion that lands without its consumer sweep should be
mechanically detectable, and if so by what. Commissioned because three such
removals shipped the deletion in one commit and the repair in another or not at
all, blocking collection tree-wide until somebody noticed. The premise
reproduced twice more while this audit was being written, so the evidence below
is primary rather than reconstructed.

## Findings

### The defect is a whole-tree question, and only a whole-tree check can answer it

A deletion without its sweep breaks an edge between two files. The commit
contains one end. The other end — the consumer left pointing at nothing, or the
module left with nobody pointing at it — lives in a file the commit does not
touch and often does not name. No per-file gate can see it, and a pre-commit
hook scoped to changed files structurally cannot: the file it would have to
read is not in its input. This is not a tooling shortfall to be fixed by a
better hook; it is a property of the defect.

Two consequences follow. First, any real answer runs over the complete tree.
Second, the check has two directions and they are not interchangeable: a
consumer pointing at a deleted module, and a module whose last consumer is
gone. A mechanism covering only one reports the other as clean.

### Capability already exists for the import channel, and is enrolled

Three tree-wide mechanisms already compute parts of this fact.

The type checker is the broadest. `pyproject.toml` sets
`[tool.ty.rules] all = "error"` with `[tool.ty.analysis]
allowed-unresolved-imports = []`, and the accompanying comment states the
mandate plainly: every unresolved import is a hard failure. It runs over all of
`src`, so it reaches production modules no test imports, and it reads
`TYPE_CHECKING`-guarded imports that no execution ever evaluates. It is
enrolled twice — as the `ty` hook in `prek.toml` with `pass_filenames = false`,
which means whole-tree rather than changed-file, and in CI as `just
check-types`.

The full-corpus collectability proof at
`src/cadrumo/tests/test_full_corpus_collectability_harness.py` covers the
runtime side, including dynamic `importlib` targets the type checker cannot
see. It is mutation-tested — `test_detector_reports_a_module_it_cannot_import`
and `test_detector_reports_every_broken_module_not_only_the_first` in its
sibling module plant real broken modules and assert the detector reports them —
and it is enrolled both in the `test-harness` recipe and in a dedicated CI job,
`cadrumo-test-harness`, which runs that recipe. The earlier framing that this
job is "separately-named" and therefore ignored understates it: the job exists
and gates. What is true is that no routine local lane runs it, because every
corpus-walking lane excludes its members by construction.

The generated API reference has its own drift gate, `python -m dev.docs.apidocs
scaffold --check`, covering orphaned documentation stubs.

So the answer to "should this be detectable" is that for the import channel it
already is, by enrolled mechanisms. Building a second import resolver beside
them would be duplication.

### But the mechanism with full capability is red at rest, so it cannot bite

Measured at commit `fd3586c3f8`, the enrolled `check-types` harness exits 1
with 283 diagnostics — 188 from ty, 27 from pyrefly, 68 from BasedPyright. Of
the 188 ty diagnostics, exactly four were `unresolved-import`.

Those four were a live deletion-without-sweep:
`src/cadrumo/entrypoints/cli/tests/test_active_profile_env_override_name.py`
imported `BUCKET_MANIFEST_SCHEMA_VERSION`, `BucketKeySchedule`,
`BucketManifest` and `write_manifest` from
`cadrumo.adapters.persistence.storage.bucket`, which no longer exports any of
them. The mechanism detected the defect, reported it, and the defect shipped
anyway.

This is the actual gap, and it is neither capability nor enrolment. A ratchet
carrying 283 standing diagnostics moves from red to red when a new defect
arrives. There is no verdict change for anyone to notice, and no clean state a
reviewer can be asked to preserve. The check is enrolled and running and
functionally inert for this purpose.

### The live reproductions, with shas

`26ba385a83` ("refactor(user_profile): fold the setup package into
user_profile, continue registry sweep") deleted `src/cadrumo/application/setup/`
and `src/cadrumo/application/filing/_m303_prorrata_activity_rows.py`. The
generated stubs `docs/api/cadrumo.application.setup*.rst` and
`docs/api/cadrumo.application.filing._m303_prorrata_activity_rows.rst`, and
their toctree entries, survived that commit. They were removed only in
`de045bd45a`, a separate commit whose subject describes itself as a "scaffold
catch-up". Between the two, the nitpicky `-n -W` documentation build carried
stubs for deleted modules — the exact hard-crash shape the documentation rule
names.

The same commit left `dev/quality/error_code_default_recovery_rehoming.toml`
and `dev/quality/fixture_ownership.toml` naming deleted source paths. Both were
still dangling at `f964f2062a`, a full day later. These are string references,
not imports: no type checker and no collection run reads them.

The bucket-export repair described above landed in `f964f2062a`, whose subject
is "registry: continue export-layout registry sweep across modelos
038/156/165/181/185/186/576/714/763 (round 50)". A CLI test's import repair
shipped inside an unrelated registry sweep. The repair is real and the tree is
better for it, but nothing in the commit record connects it to the removal it
answers, which is how the split becomes invisible in history as well as in the
gates.

### Ruling

A deletion landing without its consumer sweep should be mechanically
detectable, and it can be. Do not build a second import resolver: extract from
the standing type debt the one rule that can hold a clean floor, and gate that
rule on its own.

The extraction is worth stating precisely, because it is the difference between
this and duplication. The type checker answers hundreds of questions at once
and cannot be brought to zero in the near term. The single question "does every
first-party import target still resolve" can be at zero today and was measured
at zero. A gate scoped to exactly that question changes verdict the moment the
defect appears, which is the property the broad checker has lost. It is the
same fact, extracted to where it can be enforced.

Both directions are gated, because a check that sees one end reports the split
as clean half the time.

## Recommendations

Families 8 and 9 in `dev/quality/import_hygiene_scan.py` implement the ruling
and are gated in `src/cadrumo/tests/test_import_hygiene_gate.py`. Family 8
holds a hard zero over first-party import targets; family 9 holds a hard zero
over orphaned re-export bridges and reports the wider orphan set without gating
it.

Three items are left open, each named rather than absorbed.

String-path references remain uncovered. `dev/quality/*.toml` census files and
`docs/api/*.rst` stubs name source paths as strings; no mechanism validates
that those paths exist. Two live dangling rows are recorded above. The
documentation half has a gate already in `scaffold --check`; the census half
has none. This is the one genuine capability gap the audit found, and it is
outside the import-hygiene scanner's subject.

The export half of family 8 cannot judge a PEP 562 lazy facade, because its
export set is not statically enumerable. Nineteen of the package's 258 facades
resolve lazily, `cadrumo.core` among them, and an import of a dropped name from
any of them is declined rather than reported. Declining is correct — guessing
would report every lazily-resolved export as dangling — but the coverage
boundary should be stated wherever this gate is cited, not discovered later.

The standing type debt is the root condition and is untouched by this work. As
long as `check-types` sits at 283 diagnostics, it will keep detecting defects
that ship. Bringing it to a clean floor is the durable fix; families 8 and 9
are the part of it that could be made to bite now.
