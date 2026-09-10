# How to publish a validated runtime authority

Use this guide when you release Cadrumo's tax-rule authority. Publication turns
validated Agencia Estatal de Administración Tributaria (AEAT) modelo rules into
the signed artifact the runtime expects for calculations and filing exports.
It is a release operation, not an `aeat` command for taxpayers. Complete the
isolated-package gate before treating an artifact as released.

For the artifact format, validation receipt, runtime checks, error classes, and
Python application programming interface (API), see [Registry, legal sources, and Python API](../reference/registry-legal-api.md).
For an ordinary installed-command failure, use [Diagnose and repair](troubleshooting.md).

## Prepare the release inputs

1. Start with a clean development candidate that passes the registry validation
   suite. Supply its registry root and its source-evidence root to the
   publisher.
2. Select the package destination for the authority artifact. The runtime
   looks for `registry/authority/authority.json` in its bundled data.
3. Arrange for your organization's approved release-secret system to provide
   the matching Ed25519 private key only to the release process. Cadrumo does
   doesn't configure a secret provider for this key.
4. Confirm that the release integration provides all four publisher inputs:
   `registry_root`, `source_root`, `artifact_path`, and
   `signing_private_key_hex`.

Never write, print, commit, or attach the private key to a release record.
The package's public verification key is compiled into runtime code, not
stored beside the artifact as a replaceable key file.

## Publish

1. Have the release integration obtain the private key at process execution
   time through the approved secret system.
2. Call `publish_authority_candidate_workflow` with the four prepared inputs.
   The publisher validates the exact candidate and signs the authority
   artifact. It then replaces the destination atomically.
3. If validation is refused or the candidate receipt changes, treat the
   publication as failed. Don't replace the existing artifact by hand. Correct the
   candidate, then start a new publication.

The publisher never records a private key. It refuses a candidate that changes
during validation or before publication, and leaves the previous artifact
unchanged.

## Verify the release

1. Build an isolated installed package that contains the new artifact. Treat
   this as an outstanding release gate until the package includes the artifact.
2. Run a supported command-line interface (CLI) calculation or filing workflow
   against that installation.
3. Confirm the `bundled_authority()` load used by that workflow does not fall
   back to authoring validation, source compilation, or repair.
4. If development registry sources change after publication, repeat the
   installed workflow before republishing. The artifact-backed registry
   authority must remain unchanged. Only a later successful validation and
   publication can change that authority.

## Recover from an invalid authority

When an installed workflow refuses an unavailable, malformed, altered,
untrusted, or unsupported-version artifact, stop the workflow. The
`bundled_authority()` load doesn't compile authoring sources or repair an
artifact as a fallback.

1. Preserve the failed artifact when it is present, plus the package version,
   artifact digest, error class, and redacted logs.
2. Correct the development candidate or release configuration. Do not modify
   the installed artifact to bypass the refusal.
3. Repeat development validation and the secret-backed publication.
4. Repeat the isolated installed-package workflow before releasing the
   replacement.

Escalate through the [project issue tracker](https://github.com/nevenincs/cadrumo/issues)
with the release version, artifact digest, error class, and redacted log
context. Never include a private key or taxpayer data.
