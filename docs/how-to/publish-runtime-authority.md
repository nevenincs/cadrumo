# How to publish a validated runtime authority

Use this guide when you change Cadrumo's tax-rule registry or its legal
evidence. Publication turns validated Agencia Estatal de Administración
Tributaria (AEAT) modelo rules into the authority the runtime reads for
calculations and filing exports. It is a development and release operation,
not an `aeat` command for taxpayers.

The publication is generated output. It consists of one small descriptor and
one content-addressed SQLite database. The descriptor records the database
byte count and digest plus the logical generation; the database manifest and
component rows record the complete source/compiler receipts and dependency
closure. The descriptor is the only cutover edge, so an installed process can
admit one exact generation and retain it for an in-flight operation.
It is also the sole shipped runtime source: installed code does not open the
authored registry tree, parse profile TOML, or maintain a parallel cache of
tables parsed from it.

For the publication format, runtime checks, error classes, and Python application
programming interface (API), see [Registry, legal sources, and Python API](../reference/registry-legal-api.md).
For an ordinary installed-command failure, use [Diagnose and repair](troubleshooting.md).

## Publish

1. Start from a registry whose declarations and exact legal-evidence closure
   are ready for the full registry conformance gate.
2. From the repository root, run:

   ```powershell
   uv run --no-sync python -m dev.registry.pipeline publish-authority
   ```

   The command compiles every modelo, profile declaration, catalogue, fact,
   export layout, and legal/source evidence projection into one complete
   authority, materializes authoring deltas into complete typed revisions,
   runs full registry conformance against the exact evidence closure, and
   installs a content-addressed SQLite candidate at
   `.authority/authority-<database_sha256>.sqlite3`.
   Only after the database has been independently admitted and traversed does
   it atomically replace `.authority/authority.current.json`.
   The command prints the descriptor path and logical generation it recorded.
   `--registry-root`, `--source-root`, `--profile-schema`, and `--destination`
   select other inputs or an isolated candidate destination. Custom registry or
   source roots must provide `--profile-schema` explicitly. Without
   `--destination` the publication writes to the configured authority root and
   refuses rather than guessing a location when none is configured.
   There is no facts-only publication command and no component-selective reuse:
   every successful publication is a fresh, full generation.
   `--if-stale` publishes only when the existing artifact no longer records the
   live registry and source evidence, and prints `published=skipped-current`
   when it already does. Asking that question reads content without compiling,
   so it costs seconds where a publication costs minutes, which makes the
   paired recipe safe to run after every registry edit:

   ```powershell
   just registry-publish-authority-if-authority-stale
   ```
3. Do not commit the result. The descriptor and its content-addressed
   database are generated output, and the directory they are published into
   is excluded from version control: the registry change is committed on its
   own, and every checkout publishes its own authority from it. Do not rename
   a database or edit the descriptor by hand.

## Where the authority lives

The published authority is generated output, so a checkout keeps it outside
the packaged tree, in `.authority/` at the repository root. That directory is
excluded from version control: it is regenerated from the committed registry,
it is large, and it changes with every registry edit.

`CADRUMO_AUTHORITY_ROOT` names the directory to resolve it from. Whether you
set it depends on how you start the process:

| How you run | The variable |
| --- | --- |
| `just` recipes, `python -m dev.*`, `pytest` | Set for you, to `.authority/` in the repository you are in. |
| The `aeat` command from a checkout | You set it yourself. |
| The `aeat` command from an installed Cadrumo | Never set. The distribution carries the authority. |

The seeding is deliberate rather than incidental: the development tooling
knows where a repository is, and the product does not. Cadrumo's runtime never
imports its development tooling and never searches upwards for a repository
root, so nothing in the installed code can discover a checkout's `.authority/`
on its own. To run the `aeat` command against a checkout's own authority, name
it in the environment:

```powershell
$env:CADRUMO_AUTHORITY_ROOT = "$PWD\.authority"
```

An explicit value always wins, so a release verification pointed at another
authority tree is never overridden by the checkout's own.

An installed Cadrumo needs no variable at all. The distribution carries the
descriptor and the exact database it names at
`cadrumo/_data/registry/authority/`, and an unset `CADRUMO_AUTHORITY_ROOT`
resolves there.

### The candidate directory is not the runtime location

For an isolated package or installed-cohort check, set
`CADRUMO_AUTHORITY_CANDIDATE_DIR` to the directory holding an accepted but
not yet promoted candidate: its descriptor and the database that descriptor
selects. The packaging checks copy only those two files into a private source
snapshot; they never mutate the checkout, and they never fall back to a
promoted pair when the variable is set.

This is a development and release-verification variable. A product operator
never sets it, and it is deliberately not part of the application's
configuration, so it does not appear in the environment reference.

It is not an alternative spelling of `CADRUMO_AUTHORITY_ROOT`, and the two
must not be pointed at the same directory. `CADRUMO_AUTHORITY_ROOT` names
where the product resolves the authority it may read;
`CADRUMO_AUTHORITY_CANDIDATE_DIR` names bytes the runtime must *not* resolve
until they are promoted. Aiming the runtime root at an unpromoted candidate
during a release build is exactly the confusion the second variable exists to
prevent.

Publication holds the destination lock while it captures the input receipt,
validates and serializes the complete component set, stages and flushes the
SQLite bytes, verifies the full database digest, checks manifest/global
closure, opens a fresh read-only candidate, and checks the receipt again
immediately before descriptor replacement. If validation or admission is
refused, a content-addressed collision is found, or any registry, evidence,
compiler, or dependency input drifts, the command fails and leaves the
previous descriptor byte-for-byte in place. Correct the input, then publish
again.

Publication also projects the shared `floor`, `horizon`, and optional
`hard_ceiling` support envelope and the typed runtime catalogues for IVA rules,
place of supply, countries and territories, recargo bands, and apoderamiento
scopes. Every required catalogue must be populated. Modelo and tax-domain
identifiers accept their stable syntax in code, but membership belongs to this
validated authority; an identifier absent from its published vocabulary is not
silently admitted.

## Verify a release candidate

Verify the descriptor-selected SQLite generation directly. The publication
must admit every component through the indexed reader, match the current
compiler receipt, and pass the packaging boundary checks. There is no eager
JSON runtime backend or runtime fallback.

The packaging checks stage only the descriptor and its selected database into
their private cohort. Superseded content-addressed files retained by a source
checkout are not members of the candidate package.

The development-only paired benchmark accepts that same isolated descriptor
and an explicit JSON baseline produced from the same validated
`AuthorityArtifact` that produced the candidate database. The development
baseline helper is
`dev.registry.eager_authority_baseline.write_eager_authority_baseline`; invoke
it from the checkpoint driver with that exact artifact and keep the resulting
file outside shipped package resources. Run the paired measurement with:

```powershell
uv run --no-sync python -m dev.registry.indexed_authority_benchmark `
  --descriptor <candidate>\authority.current.json `
  --json-baseline <work>\authority-eager-baseline.json `
  --backend both --runs 10
```

The baseline is development evidence only: it is generated from the exact
validated in-memory authority, eagerly decodes the complete graph, and carries
the candidate's logical identity. The runner verifies the descriptor's exact
database bytes before either side is measured; it does not read the shipped
package, discover a default JSON file, or become a runtime fallback. Each
M100, M200, and M303 workload is reported independently; the ADR admission,
incremental-memory, and warm-context thresholds remain pending until
checkpoint C runs on one stable candidate cohort.

## Check that the publication is current

Run the registry gate:

```powershell
just check-registry
```

Its authority step admits the descriptor and its named database in read-only
mode. It exits 1 with a refusal on standard error when either selector or
database is stale, unreadable, malformed, tampered, or no longer matches the
live candidate. The refusal names the recorded and expected identity digests
and the command that republishes the authority.

The source receipt depends on file content and paths relative to the registry
and source roots, including manually maintained evidence sidecars. The compiler
receipt covers the compiler and relevant Cadrumo code, `pyproject.toml`,
`uv.lock`, the Python major/minor version, and the installed `pydantic` and
`pydantic-core` versions. A fresh clone in the same declared environment is
stable; an incompatible interpreter, dependency set, manifest, or compiler
change makes the publication stale and requires republication. The component
receipt binds those source and compiler receipts to the complete-authority
generation. The database digest independently protects all stored component
bytes, while each on-demand component load checks its own payload digest and
dependency closure.

## Recover from an invalid authority

When an installed workflow refuses an unavailable, malformed, altered, or
unreadable authority, stop the workflow. The
`IndexedRegistryAuthority.operation()` path is artifact-only: it doesn't
compile authoring sources, parse raw TOML, repair a database, or fall back to
the retired JSON frame. Runtime loads typed components on demand through the
generation-pinned operation and keeps only bounded, generation-scoped values;
a descriptor replacement starts a new authority generation while existing
operations retain their admitted reader.

On Windows, publication removes an older content-addressed database only after
it can acquire an exclusive handle, so an in-flight reader defers cleanup until
a later publication. On POSIX systems publication retains superseded database
files: unlinking an open file succeeds there and does not provide a safe
cross-process lease signal. The immutable filename prevents those retained
bytes from being selected by the current descriptor.

1. Preserve the failed descriptor/database pair when present, plus the package
   version, logical and physical digests, error class, and redacted logs.
2. Republish from a validated registry, and confirm that `just check-registry`
   passes.
3. Rebuild the package so it contains the replacement descriptor and the
   exact database named by it. The package must not contain the authored
   registry, profile schema TOML, or retired JSON frame.

Escalate through the [project issue tracker](https://github.com/nevenincs/cadrumo/issues)
with the release version, authority digests, error class, and redacted log
context. Never include taxpayer data.
