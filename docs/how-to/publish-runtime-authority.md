# How to publish a validated runtime authority

Use this guide when you change Cadrumo's tax-rule registry or its legal
evidence. Publication turns validated Agencia Estatal de Administración
Tributaria (AEAT) modelo rules into the artifact the runtime reads for
calculations and filing exports. It is a development and release operation,
not an `aeat` command for taxpayers.

The artifact is generated output. Its versioned frame records a payload digest
and separate receipts for its source inputs, compiler, and complete-authority
component dependencies, so the registry gate can tell when either its payload
or the inputs that produced it have changed.
It is also the sole shipped runtime source: installed code does not open the
authored registry tree or maintain a parallel cache of tables parsed from it.

For the artifact format, runtime checks, error classes, and Python application
programming interface (API), see [Registry, legal sources, and Python API](../reference/registry-legal-api.md).
For an ordinary installed-command failure, use [Diagnose and repair](troubleshooting.md).

## Publish

1. Start from a registry whose declarations and exact legal-evidence closure
   are ready for the full registry conformance gate.
2. From the repository root, run:

   ```powershell
   uv run --no-sync python -m dev.registry.pipeline publish-authority
   ```

   The command compiles every modelo and catalogue into one complete authority,
   materializes authoring deltas into complete typed revisions, runs full
   registry conformance against the exact evidence closure, then
   atomically replaces `src/cadrumo/_data/registry/authority/authority.json`.
   It prints the artifact path and the identity digest it recorded.
   `--registry-root`, `--source-root`, and `--artifact` select other trees or
   another destination.
   There is no facts-only publication command and no component-selective reuse:
   every successful publication is a fresh, full generation.
3. Commit the regenerated `authority.json` together with the registry change
   that required it.

Publication holds the destination lock while it captures the input receipt,
validates, serializes and admits the canonical bytes through the runtime
decoder, stages and flushes them to durable storage, and checks the receipt
again immediately before atomic replacement. If validation or admission is
refused, or any registry, evidence, compiler, or dependency input drifts, the
command fails and leaves the previous artifact byte-for-byte in place. Don't
edit the artifact by hand. Correct the input, then publish again.

Publication also projects the shared `floor`, `horizon`, and optional
`hard_ceiling` support envelope and the typed runtime catalogues for IVA rules,
place of supply, countries and territories, recargo bands, and apoderamiento
scopes. Every required catalogue must be populated. Modelo and tax-domain
identifiers accept their stable syntax in code, but membership belongs to this
validated authority; an identifier absent from its published vocabulary is not
silently admitted.

## Check that the artifact is current

Run the registry gate:

```powershell
just check-registry
```

Its first step, `python -m dev.registry.conformance integrity`, exits 1 with a
refusal on standard error when the artifact is stale, unreadable, or in a
malformed format. The refusal names the recorded and the expected identity
digests and the command that republishes the artifact.

The source receipt depends on file content and paths relative to the registry
and source roots, including manually maintained evidence sidecars. The compiler
receipt covers the compiler and relevant Cadrumo code, `pyproject.toml`,
`uv.lock`, the Python major/minor version, and the installed `pydantic` and
`pydantic-core` versions. A fresh clone in the same declared environment is
stable; an incompatible interpreter, dependency set, manifest, or compiler
change makes the artifact stale and requires republication. The component
receipt binds those source and compiler receipts to the complete-authority
generation, while the payload digest independently protects the shipped bytes.

## Recover from an invalid authority

When an installed workflow refuses an unavailable, malformed, altered, or
unreadable artifact, stop the workflow. The `bundled_authority()` load is
artifact-only: it doesn't compile authoring sources, parse raw TOML, repair an
artifact, or fall back to a separately cached runtime table. Runtime shares
deeply immutable model graphs for one verified artifact identity and keeps only
bounded, generation-scoped projections; a replacement artifact starts a new
authority generation.

1. Preserve the failed artifact when it is present, plus the package version,
   artifact digest, error class, and redacted logs.
2. Republish from a validated registry, and confirm that `just check-registry`
   passes.
3. Rebuild the package so it contains the replacement artifact.

Escalate through the [project issue tracker](https://github.com/nevenincs/cadrumo/issues)
with the release version, artifact digest, error class, and redacted log
context. Never include taxpayer data.
