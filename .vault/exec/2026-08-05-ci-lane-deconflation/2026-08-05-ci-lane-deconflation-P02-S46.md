---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:ebefc0074fdce936818476dbf74718dca73e8457ebb8e194570d8fe3691c4bea'
step_id: 'S46'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Classify the twelve unclassified open-coded write sites and propose the instrument that would keep them classified

## Scope

- `src/cadrumo/adapters/persistence/storage`
- `src/cadrumo/application/user_profile`
- `src/cadrumo/application/bucket_maintenance`
- `src/cadrumo/core`
- `src/cadrumo/domain/calculations/registry/_compiled_cache.py`
- `dev/registry/_generated_tree_publication.py`
- `dev/write_site_census.py`

## Description

- Resolve the population before classifying it, because the row's own count was
  approximate and approximate counts are what this campaign keeps paying for.
- Classify each site as delegating to a core atomic-write tier or re-implementing
  one, by reading the site rather than counting pattern hits.
- Propose the instrument that would keep the distinction measurable. Build
  neither the reclassification nor the instrument.

## Outcome

**The population was wrong in the row and is corrected here.** The row says
"twelve unclassified". The grep that produced it returned **thirteen** modules,
but one of those is `dev/write_site_census.py`, which names `mkstemp` in its
**primitive table** at line 198 and calls nothing. It is the scanner, not a write
site, and it leaves the population entirely. So: **twelve write sites, of which
one was already read, leaving eleven** — not twelve unclassified.

**ZERO genuine re-implementations remain. S39 was the only one.** Every one of
the twelve is legitimate, in four distinct ways:

**Seven delegate, and their `os.replace` is PROSE.** In `_manifest_io.py`,
`_recovery.py`, `_recovery_facade.py`, `_secret_store.py`,
`core/corpus_manifest/__init__.py`, `_catalogue_cache.py` and `_compiled_cache.py`
the only occurrence of `os.replace` is inside a docstring or comment describing
what the core tier does — "Delegates to `atomic_write_...`", "standard tier:
tempfile + fsync + `os.replace` + parent-dir". There is no call.

**One is the worked example.** `application/user_profile/_bundle_export.py`
stages through `atomic_write_hardened_bytes`, names that tier in its own docstring
as "the reviewed home", then publishes with `os.replace` under a lock and emits
its lifecycle event. That is the two-phase publish the architecture rule
prescribes: delegate to the primitive, emit the surface event in addition.

**One is a docstring about its sibling.** `_bundle_export_operation.py:103`
mentions `os.replace` while explaining why a prepared operation's digest equals
the published target's. Not a write site.

**Three are a different concept, and no core tier applies to any of them.**
`_sealed_archive_writer.py:149` publishes a **tar archive built incrementally**
via `archive.addfile`; the core tiers take `data: bytes`, and `atomic_write_stream`
takes a chunk iterable while `tarfile` needs a file object. `bucket_maintenance`
`_service.py:1336` replaces a **directory** after `shutil.copytree`.
`dev/registry/_generated_tree_publication.py` performs nine replaces, every one on
a **directory root** inside a journaled, locked tree cutover with backup and
recovery. A file-write primitive cannot express any of these.

## Verification

Classification is a reading, and each verdict rests on the line rather than on a
count:

    seven delegating sites   first `os.replace` occurrence read in context;
                             each sits inside a docstring naming the core tier
    _bundle_export.py        `atomic_write_hardened_bytes(staged_path, data)`
    _sealed_archive_writer   `os.replace(staging_path, target_path)` after a
                             `tarfile` member loop
    bucket_maintenance       `os.replace(restored, target)` after `copytree`
    generated_tree_pub       replaces on `target/backup/candidate_export_root`
    write_site_census.py     `"mkstemp": None` — a table entry, not a call

No test was run and none is owed: this row classifies, and the sites it clears
are cleared by what they contain rather than by a passing gate.

## Notes

**THE INSTRUMENT, PROPOSED AND NOT BUILT.** A text scan cannot do this job, and
the reason is specific and worth keeping: **the correct sites document themselves
by naming the primitive they delegate to, which makes them look exactly like the
defect.** Seven of twelve tripped the grep purely by explaining that they
delegate. An instrument for this must parse, not match — resolve `os.replace` and
`mkstemp` as *called* names via the AST, then ask whether the enclosing module
also imports a core tier, and classify the residue by what the replace's operand
is: a file the module wrote, or a directory.

**This is the second time in one session that a text scan misread a docstring as
code, in this same domain.** The first was my own unused-import guard for S39,
which refused on the new docstring's `` :func:`os.link` `` cross-reference and had
to be rewritten over the AST. Same confusion, same fix, twice — which is the
argument for the instrument being AST-based from the start rather than a
refinement of the grep.

**The existing census is not that instrument and is not deficient for it.**
`dev/write_site_census.py` quantifies over write primitives in the source
specifically so it can see a site the taxonomy has not enrolled, and its own
docstring records two selector corrections whose symptom was "a confident wrong
number" — `.save` returning 138 of 235, `.replace` reporting 267 sites where
roughly 99 existed. But its question is **where each site's path originates**,
not whether the site duplicates a write path. The provenance-manifest defect S39
fixed was never within its reach, and saying so is not a criticism of it.

**A census shrank a row again, and this time to nothing.** The honest headline is
that the fragmentation this row was opened to size does not exist: one defect
existed, it was found by a semantic search rather than by this census, and it is
already fixed. **An overcount ships a sweep** — had the twelve been taken at face
value, eleven correct modules would have been rewritten to "delegate" to tiers
that cannot express what they do.
