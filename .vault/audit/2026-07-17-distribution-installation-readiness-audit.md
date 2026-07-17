---
tags:
  - '#audit'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace distribution-installation-readiness with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `distribution-installation-readiness` audit: `S67 distribution identity verifier code review`

## Scope

Reviewed `W02.P06.S67` against the accepted distribution-harness identity decision and
its research record. The review was limited to
`dev/packaging/verify_distribution_identity.py` and
`dev/packaging/tests/test_verify_distribution_identity.py`, with read-only inspection
of the production generators and MCP projections needed to judge the verifier. The
three focused real-behavior tests passed. They import production code directly and use
no fake, mock, stub, patch, monkeypatch, skip, or expected-failure shortcut.

## Findings

### mixed-revision-projection | medium | Repository selection does not isolate every inspected projection

`verify_distribution_identity(repo_root)` reads `pyproject.toml`, the MCPB manifest,
and the child-process projection from the supplied root, but authored inventory and all
three generated trees come from the already-imported `cadrumo` package. The child
process also inherits the ambient environment. A caller can therefore request one
repository root while receiving a report that combines identifiers from another
imported revision, and the tests exercise only the same-checkout case. That weakens the
revision boundary required for retained distribution evidence.

### generated-parity-not-enforced | high | Missing generated surfaces can produce a passing verdict

The report verdict is only `all(row.compliant ...)` over observations that happened to
exist. It never requires the workspace, plugin, marketplace, prompt, and resource sets
to equal the authored persona, skill, and rule inventories. A generator that omits a
prefixed agent, skill, or rule, or an MCP projection that returns an empty list, can
therefore pass once the remaining source names are prefixed. The tests assert today's
counts, but that does not make the production verifier fail closed on absent rows. This
contradicts the accepted identity-parity requirement and is a release-gate false-pass.

### mcp-projection-sampling | high | Tool-prefix and embedded-resource checks do not cover the actual complete MCP surface

The tool-prefix check validates only the synthesized
`modelo.work.calculate` mapping. It does not inventory the actual server tool registry
or the MCPB tool declarations and distinguish the decision's approved generic
progressive-discovery operations from tools that must carry `cadrumo_`. Separately,
embedded prompt resource URIs with a wrong scheme, malformed path, or unknown harness
kind are silently ignored rather than recorded as failures. A drifted public tool or
embedded resource projection can consequently escape the S67 verdict even though the
sample and surviving observations pass.

## Recommendations

1. Add explicit expected-set comparisons for every authored-to-generated projection,
   including required non-empty MCP prompt/resource surfaces, and incorporate those
   parity checks into `DistributionIdentityReport.ok`.
2. Enumerate the real MCP server tools and MCPB-declared tools, validate every name
   against `cadrumo_` or a closed set of decision-approved generic operations, and fail
   on every malformed or non-Cadrumo embedded harness URI instead of filtering it out.
3. Make one repository revision authoritative for imported harness data, generators,
   MCP runtime projection, project scripts, and MCPB metadata; sanitize the child
   process environment and add a real subprocess test proving that ambient package and
   Cadrumo configuration state cannot change the inspected revision.

## Follow-up review outcome

**Revision required.** The focused test module passes (`3 passed`) and Ruff reports no
violations, but all three rolling findings remain relevant after remediation. The
generated-set work narrows the first finding; it does not yet establish field-level
projection parity. The other two findings remain open without qualification.

### Finding disposition

- `generated-parity-not-enforced`: partially addressed, still open at high severity.
  `InventoryParityCheck` now fails on missing or duplicate workspace, plugin,
  marketplace, MCP prompt, MCP resource, and embedded-skill rows. However, the checks
  compare only each row's primary file or directory identifier. Generated agent
  frontmatter names and generated skill metadata names are merely checked for the
  `cadrumo-` prefix, not equality with their authored values. Prompt-to-embedded-resource
  association is likewise reduced to a global identifier multiset. A generator can
  therefore substitute a different prefixed metadata identifier, or swap prefixed
  embedded skill references between prompts, while the report passes.
- `mcp-projection-sampling`: open at high severity. The subprocess assembles
  `server_tools` from command descriptors and four Cadrumo-specific constants, but does
  not include the real server's `build_meta_sdk_tools()` result. The approved generic
  operations `search`, `execute`, `toolsets`, and `describe` are consequently absent
  from the report rather than explicitly accepted. The verifier also does not read or
  compare the MCPB `tools` declarations; its currently declared generic `search` and
  `execute` entries are unrepresented. Resource rows still check scheme and prefixed
  leaves independently without requiring the URI kind and leaf to equal the resource's
  declared kind and name.
- `mixed-revision-projection`: open at medium severity. Authored inventory and all
  materialisers still execute from the module imported before `repo_root` is evaluated.
  The child uses `sys.executable`, inherits the ambient environment, and reports
  `package_file` without validating that it belongs to `repo_root`. `repo_root` remains
  authoritative only for `pyproject.toml`, the MCPB manifest, and the child working
  directory, so a report can still combine multiple revisions.

### Updated recommendations

1. Compare every generated frontmatter and skill-metadata identity to the corresponding
   authored identity, and compare each prompt's embedded harness references to that
   prompt's expected authored references rather than only comparing global sets.
2. Inventory `build_meta_sdk_tools()` and MCPB `tools`, classify every observed name
   against the closed approved generic set or `cadrumo_`, and validate complete resource
   URI structure against each row's declared kind and name.
3. Execute the entire inventory and generation probe from the requested repository's
   isolated environment, reject any reported package path outside that revision, and
   pass a deliberately minimal allowlisted environment to the child process.

## Final remediation disposition

**Pass.** A read-only re-review of the final shared implementation found no remaining
S67 code-review finding. The earlier rolling findings are retained above as the audit
history; their final dispositions are:

- `generated-parity-not-enforced`: resolved. Eighteen exact parity checks now cover
  authored-to-workspace, plugin, marketplace, MCP prompt, MCP resource, agent
  frontmatter, skill metadata, and per-prompt embedded-skill associations. Missing,
  duplicate, substituted, or reassociated projections participate in
  `DistributionIdentityReport.ok` and fail the verifier.
- `mcp-projection-sampling`: resolved. The runtime inventory includes the real
  `build_meta_sdk_tools()` surface, explicitly classifies the closed generic set
  (`search`, `execute`, `toolsets`, and `describe`), and applies the same classification
  to every MCPB tool declaration. Concrete resource URIs must equal their declared
  `cadrumo://{kind}/{name}` identity, resource-template names and URI grammars are
  checked together, and malformed embedded harness URIs become failing observations.
- `mixed-revision-projection`: resolved. The requested root must equal the imported
  package root, the child receives the requested source tree through `PYTHONPATH`, the
  reported package path must resolve inside that tree, and inherited Cadrumo and Python
  environment variables are removed before the isolated runtime root is supplied.

Final focused verification: Ruff passed; the direct production test module passed
`4/4`; the production verifier exited `1` for the accurately reported current
unprefixed harness while all 18 projection-parity checks and every accepted MCP product
identity check passed. This is the intended S67 verification-only outcome and does not
approve or perform the later rename.
