# How to publish a validated runtime authority

Use this guide when you change Cadrumo's tax-rule registry or its legal
evidence. Publication turns validated Agencia Estatal de Administración
Tributaria (AEAT) modelo rules into the artifact the runtime reads for
calculations and filing exports. It is a development and release operation,
not an `aeat` command for taxpayers.

The artifact is generated output. It records a digest of its own content and
the identity of the registry and evidence it
was compiled from, so the registry gate can tell when it is out of date.

For the artifact format, runtime checks, error classes, and Python application
programming interface (API), see [Registry, legal sources, and Python API](../reference/registry-legal-api.md).
For an ordinary installed-command failure, use [Diagnose and repair](troubleshooting.md).

## Publish

1. Start from a registry that passes the registry validation suite.
2. From the repository root, run:

   ```powershell
   uv run --no-sync python -m dev.registry.pipeline publish-authority
   ```

   The command validates the bundled registry and its source evidence, then
   atomically replaces `src/cadrumo/_data/registry/authority/authority.json`.
   It prints the artifact path and the identity digest it recorded.
   `--registry-root`, `--source-root`, and `--artifact` select other trees or
   another destination.
3. Commit the regenerated `authority.json` together with the registry change
   that required it.

If validation is refused, or the registry changes while it is being
validated, publication fails and leaves the previous artifact byte-for-byte in
place. Don't edit the artifact by hand. Correct the registry, then publish again.

## Check that the artifact is current

Run the registry gate:

```powershell
just check-registry
```

Its first step, `python -m dev.registry.conformance integrity`, exits 1 with a
refusal on standard error when the artifact is stale, unreadable, or in an
earlier format. The refusal names the recorded and the expected identity
digests and the command that republishes the artifact.

The identity depends only on file content and on paths relative to the
registry and source roots. A fresh clone on any platform therefore agrees with
the publisher. A change to the compiler's code that doesn't touch the registry
or its evidence doesn't make the artifact stale. The full-registry publication
round-trip test covers the compiler itself.

## Recover from an invalid authority

When an installed workflow refuses an unavailable, malformed, altered, or
unsupported-version artifact, stop the workflow. The `bundled_authority()`
load doesn't compile authoring sources or repair an artifact as a fallback.

1. Preserve the failed artifact when it is present, plus the package version,
   artifact digest, error class, and redacted logs.
2. Republish from a validated registry, and confirm that `just check-registry`
   passes.
3. Rebuild the package so it contains the replacement artifact.

Escalate through the [project issue tracker](https://github.com/nevenincs/cadrumo/issues)
with the release version, artifact digest, error class, and redacted log
context. Never include taxpayer data.
