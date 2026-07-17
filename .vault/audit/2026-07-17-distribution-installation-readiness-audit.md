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

## S68 review scope

Reviewed commit `08a038ed24` and `W02.P06.S68` against the accepted bilingual MCP
product-description decision and its research record. The review covered the production
description verifier, its direct real-surface tests, the generated Claude plugin and
marketplace metadata, both MCPB product-description fields, and the S68 execution record.
The commit does not mutate any identifier, description source, generator output, or
model-facing operational copy. Focused Ruff passed and the direct production test module
passed `5/5`; the production verifier reproduced exit status `1` and the execution
record's report digest
`6102d5a48d3c162b95776757ec813e271721d9713d9200463188f3ec9f375205`.

## S68 findings

### bilingual-claim-semantics | high | Keyword presence can approve the inverse of every required product claim

`_product_description_observation` treats each claim as present when a small set of
unscoped regular expressions matches. It does not account for negation, subject, or
relationship between the matched phrases. A direct review probe using the production
function supplied labeled English and Spanish sections that explicitly deny Cadrumo's
tax capability, read-only safety, provider privacy boundary, on-host storage, human
confirmation, and never-files-live boundary. All six claim rows and the complete
observation nevertheless returned compliant. This is a release-gate false-pass for the
decision's semantic parity requirement. The five focused tests cover only today's
English-only failure and do not exercise a compliant description or an adversarial
semantic contradiction.

### language-label-contract | medium | The parser rejects natural Spanish-language section labels without an approved label grammar

The label parser accepts only `English`, `EN`, `Spanish`, and `ES`. A schema-supported
single string labeled `English:` and `Español:` is reported as having no Spanish
section, while `Inglés:` and `Español:` produces no recognized sections at all. The
accepted decision requires explicitly distinguishable English and Spanish text but does
not prescribe English-only label words. This undocumented grammar can reject valid
approved bilingual copy and is not covered by tests of the success path.

### model-facing-boundary | medium | The English-only operational-description boundary is declared but not observed

The report emits a constant list saying MCP argument, prompt, resource, and tool
descriptions are not localization targets. It never inventories those real production
descriptions or makes their English-only state participate in the verdict. The focused
test therefore proves only that the constant serializes. A later drift in any actual
model-facing description would remain invisible even though S68 expressly preserves
that existing contract.

## S68 disposition

**Revision required.** The current shipped descriptions are correctly reported as
English-only and the implementation is read-only, but the verifier is not yet safe as a
blocking bilingual-parity gate. Resolve the high-severity semantic false-pass, define
and test the accepted language-label grammar, and bind the model-facing exclusion to the
real operational description inventory. Add direct success, semantic-contradiction, and
supported-label tests before treating the S68 evidence as reviewed.

## S68 final remediation disposition

**Pass.** A read-only re-review of the remediated shared implementation found no
remaining S68 code-review finding. The earlier rolling findings are retained above as
the audit history; their final dispositions are:

- `bilingual-claim-semantics`: resolved. A client-display field can pass only when its
  exact extracted English and Spanish pair is present in the product-review approval
  set for that specific surface and field. The accepted verification-only scope has no
  approved pairs, so keyword matches cannot approve any copy. The direct adversarial
  test supplies semantically inverted text matching the claim vocabulary and confirms
  that all six parity verdicts and the observation remain false.
- `language-label-contract`: resolved. The closed grammar now supports `English` and
  `Spanish`, `EN` and `ES`, accented `Inglés` and `Español`, and unaccented `Ingles` and
  `Espanol`. Direct review probes confirmed all four pairs extract exactly one nonempty
  English section and one nonempty Spanish section; the focused tests exercise the
  natural localized form.
- `model-facing-boundary`: resolved. The isolated production MCP projection inventories
  the real tool, prompt, resource, and nested argument descriptions. The report contains
  1,625 nonempty rows (296 tool, 35 prompt, 54 resource, and 1,240 argument rows), rejects
  language-section labels, and freezes the canonical inventory at SHA-256
  `5eaa233019daecfffc215ec482fa36dfdc4763a03b412c00f615cfd45496d9a0`.
  This observed contract participates in `DistributionIdentityReport.ok`.

Final focused verification: Ruff passed; the direct production test module passed
`7/7`; the production verifier exited `1` and emitted report SHA-256
`8ac51513f603545fcaf26142efd0388508413aac65ac1be5050a6feea81c3fdc`.
The five shipped client-display fields still correctly fail because the accepted
verification-only scope has zero approved translation pairs. The implementation review
passes; it does not approve copy, close S68, or change the required failed distribution
verdict.

## S69 evidence review scope

Reviewed the retained `W03.P08.S69` Claude-client identity record, its execution
record, and only the source files cited by the retained record. The review re-hashed
the retained JSON and every readable cited source, inspected the installed plugin and
MCPB metadata used for identifier and description observations, and checked the
Desktop local-agent transcript evidence used to classify the Cowork surface. The
retained JSON itself matches the execution record's SHA-256
`294a4705d312dcda5ba68d2d5b0676aa2d74519b72a3f6807aa25b66679cdd12`.
Its failure verdicts are conservative: no client receives an identity or bilingual
false pass, missing inventories remain incomplete, and absent Spanish copy remains a
failure.

## S69 findings

### cowork-source-digest-mismatch | high | The retained Cowork transcript source does not match its recorded digest

The Cowork row cites `audit.jsonl` with SHA-256
`529496d6248d05651cabdc81c73b00edf663ed355c14187e99f42b160cd56c49`,
but a shared-read re-hash of that exact completed file produced
`bc31dcb613b0422a8c757f232068c4e1281e0e3cd10656e2d5abdae74a9eca67`.
The cited digest belongs to the separate Claude project transcript
`.claude/projects/.../e7affa71-a0e9-4ec1-ac77-9e001b3413d3.jsonl`, not to the named
local-agent `audit.jsonl`; S69 assigned the project-transcript digest to a different
concrete source path. This invalidates the source-integrity claim for the only direct
evidence behind the Cowork row. The
transcript content does support the proposed surface classification—`desktop_app`,
local-agent-mode storage, Cowork MCP tools, Cowork plugin-management commands, and the
Cadrumo calls are all present—but S69 cannot retain it as verified evidence under a
mismatched digest.

### claude-code-observation-provenance | high | Several Claude Code observations have no cited or digested source

The Claude Code row cites only the aggregate plugin-evidence JSON and installed
`plugin.json`. Neither cited file contains client version `2.1.211`, MCP server version
`1.28.1`, installed-plugin commit `d5d6c34661fe4dd4ad365be8faf53e51682559c3`,
or the claimed complete seven-agent and 34-skill inventories. Those values exist in
other retained run files—the client transcript/debug log, `installed_plugins.json`,
and installed agent and skill trees—but the S69 record neither names nor digests those
sources and supplies no artifact or tree digest covering them. Consequently the listed
observations may be correct, but the evidence record does not meet the decision's
requirement to bind observed identifiers, client identity, and artifact identity to
retained exact bytes.

## S69 disposition

**Revision required.** The overall noncompliant matrix verdict is honest, the MCP
server and bilingual verdicts do not fabricate a pass, and treating the Desktop
local-agent host-loop session as the Cowork surface is supported by the transcript.
However, the mismatched Cowork digest and uncited Claude Code observation sources make
the retained evidence set unverifiable. Re-capture or re-hash the exact Cowork source,
cite and digest every Claude Code source from which recorded fields are derived, then
regenerate the S69 record and execution-record digest. Keep the S69 plan row unchecked.

## S69 final remediation disposition

**Pass.** A read-only re-review of the remediated S69 evidence found no remaining
review finding. The earlier rolling findings remain above as audit history; their final
dispositions are:

- `cowork-source-digest-mismatch`: resolved. The Cowork row now cites the exact main
  Claude project transcript beneath the local-agent session. A shared-read SHA-256 of
  that named file matches
  `529496d6248d05651cabdc81c73b00edf663ed355c14187e99f42b160cd56c49`.
  The transcript identifies `desktop_app`, the local-agent host-loop, Cowork tools and
  plugin-management commands, the connected 16-tool Cadrumo surface, and the real tax
  operation. The installed Desktop evidence binds the same session identifiers to the
  exact MCPB and root-wheel digests, so the Cowork surface and cohort classification is
  supported without treating `audit.jsonl` as the retained source.
- `claude-code-observation-provenance`: resolved. The row now cites and byte-digests
  the plugin evidence, installed plugin manifest, Claude debug log,
  `installed_plugins.json`, and installed `.mcp.json`. Those files support the client
  version, server name and version, client-generated installed-plugin commit, product
  description, and real behavior. The record expressly marks that generated commit as
  unequal to the accepted source commit and leaves exact-cohort compliance false.
  The installed tree independently contains exactly seven agent files and 34 skill
  directories matching the recorded lists. Their specified sorted compact-JSON
  canonicalization reproduces SHA-256
  `f35c5a0a05600984b7945623ad4444c6c97d8c9bd4b602e2a41bb8fd7ac5a7fe`.

Every cited source digest re-hashed successfully. The final retained evidence JSON and
execution record agree on SHA-256
`ddda9b49c91ea173858e26c684804c181569c0ab0505bcf7e62985d34b72ff76`.
The per-field Desktop and Cowork claim maps accurately distinguish the limited short
description from the complete English long description; both remain Spanish-empty.
No identity, bilingual, inventory-completeness, or exact-cohort false pass remains.
This evidence review passes while the S69 delivery row correctly remains unchecked
because all observed clients fail the requested product contract and the capture is not
yet an executable workflow.

## S23 Homebrew source-install review scope

Reviewed `W02.P05.S23`, the Homebrew source-install harness, the generated formula,
its direct real-behavior tests, the retained three-archive cohort, the WSL2 command
logs, both installed tax oracles, cleanup evidence, and the S23 execution record. The
review distinguishes this one local Linux x86-64 tap snapshot from the hosted Linux and
macOS matrix owned by S24.

## S23 initial finding

### retained-cohort-digest-drift | high | The retained root archive did not reproduce the tested formula input

The formula pinned root source digest
`6d1b0980c3102ed8445a44f1eeeb6ea8f219290641577cf1980262ca5ca948c2`,
but the retained cohort initially contained root archive digest
`d781f40491f012aa767f69d8778cd9f764798cd52e3bd5fa0d74aaf3515a9722`.
The historical WSL2 run was real because Homebrew's cache still contained and used the
formula-pinned bytes, but its recorded local inputs were not self-contained or
reproducible. S23 could not close on that evidence.

## S23 final remediation disposition

**Pass.** The exact formula-pinned root archive was restored beside the already matching
manuals and official companion archives. The harness now hashes each local cohort
archive against the digest adjacent to its formula URL before starting Homebrew; a
stale or substituted archive fails before localization. Its structured evidence also
records the filename, SHA-256, and byte size of all three inputs. A direct negative test
proves digest drift is rejected, and the complete focused Homebrew suite passed `10/10`.

A fresh post-remediation WSL2 source-install run passed with retained evidence SHA-256
`5c81176443c837cc43db724f0e7e4aef0bf7d633134cd4c5a323ac274cda63ca`.
Strict audit, source installation, formula test, installed CLI oracle, and installed MCP
oracle all exited successfully. Both installed surfaces returned
`DP200014:00562 == 23000.00` under `modelo-200-cuota-integra` with the required legal
and authoritative-source grounding, and the MCP evidence binds its child invocation to
the Cellar-owned CLI identity. Cleanup removed the formula, installed prefix, and tap
with no retained formulas, taps, or errors. No blocking S23 finding remains. Hosted
Linux and macOS coverage remains open under S24.

## S28 MCPB runtime-requirement review

**Pass.** Reviewed the MCPB v0.4 manifest, bundle builder, emitted runtime
project, complete real-cohort archive tests, retained provisioned runtime, and
installed MCP oracle. The compatibility declaration advertises only Python
`>=3.13,<3.14`; it makes no operating-system or client-support claim. The
bundle launches UV against its own project and `src/server.py`, with all three
`0.2.1` product distributions resolved from bundle-local wheels and bound to
their stamped digests.

The retained virtual environment is CPython 3.13.11. Retained evidence SHA-256
`d2106e7e227fe876ea5bd2628d26276f15dec51c36f9e97cc004780f889f890c`
binds MCPB SHA-256
`8615c66cc05441a8b60f82ccef7f5a1374af81dd37890acf03a6341c62f24cd2`
to source commit `11c82d2f030c1e75d6b34606e3373421c4f5bce5` and the exact embedded
cohort. The installed MCP oracle returned `DP200014:00562 == 23000.00` under
`modelo-200-cuota-integra`. Focused Ruff passed and all eight real-cohort MCPB
archive tests passed. No S28 finding remains. This disposition does not approve
S29 signing/cohort acceptance, S30 per-client installation, or the English-only
descriptions that keep S68 open.
