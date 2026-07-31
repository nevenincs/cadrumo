---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
body_hash: 'sha256:705a40c3bef6226c75c0195369e0aed4ae716de7f722a441629648872d0c7641'
step_id: 'S04'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Classify external package, repository, marketplace, executable, domain, and trademark reservations

## Scope

- `issue #476 external reservation register`

## Description

- Re-read the accepted rename ADR, its research, the approved L4 plan, and current `HEAD` before checking external names.
- Query primary public package, account, repository, registration-data, and trademark-search surfaces without creating or reserving external state.
- Check the current workstation for executable collisions and classify marketplace identity according to its repository-scoped publication model.
- Separate transient availability observations from reservation, ownership, and legal clearance, and preserve every unresolved item as a release blocker.

## Outcome

### Governing release rule

An HTTP `404`, an empty exact-name search, an `NXDOMAIN` response, or absence from
the current `PATH` is an availability signal only. It neither reserves the name nor
proves ownership, registrability, freedom to operate, or absence of confusingly
similar prior rights. Public release remains blocked until an authorised operator
controls each required identifier and qualified trademark review clears the intended
territories, classes, and goods or services. No reservation or publication occurred
during this Step.

All observations below were made on **2026-07-12** from `HEAD`
`cf0ad9430c0bfe655d792f64af4f595905b9e647`.

### External reservation register

| Surface | Required identifier | Direct locator and observed result | Classification | Release condition |
| --- | --- | --- | --- | --- |
| Root Python distribution | `cadrumo` | `https://pypi.org/pypi/cadrumo/json` returned HTTP 404 | Appears unclaimed; not reserved | Blocked until the project exists under operator control and its publication credentials or Trusted Publisher are configured and verified |
| Manuals companion distribution | `cadrumo-data-manuals` | `https://pypi.org/pypi/cadrumo-data-manuals/json` returned HTTP 404 | Appears unclaimed; not reserved | Same; reserve and verify independently because PyPI ownership is per project |
| Official-data companion distribution | `cadrumo-data-official` | `https://pypi.org/pypi/cadrumo-data-official/json` returned HTTP 404 | Appears unclaimed; not reserved | Same; reserve and verify independently because PyPI ownership is per project |
| GitHub account or organisation | `cadrumo` | `https://api.github.com/users/cadrumo` returned HTTP 404 | Exact account appears absent; not reserved | Blocked until the operator chooses and controls the publisher account or organisation; account creation policy and recovery ownership must be recorded |
| GitHub repository | `cadrumo` under the chosen publisher | `https://api.github.com/repos/cadrumo/cadrumo` returned HTTP 404 | That exact owner/repository pair is absent, but the owner is also absent | Blocked until the canonical repository is created or renamed under the approved publisher, redirects and release integrations are reviewed, and control is evidenced |
| Claude marketplace publisher | Existing independently named `neve` marketplace | `packaging/marketplace/README.md` records marketplace `neve` served from `nevenincs/neve-marketplace` | Publisher identity may remain; control was not externally re-proven by this Step | Blocked until the operator confirms continuing control of the publisher repository and its release path |
| Claude plugin entry and source path | `cadrumo`, `plugins/cadrumo`, installed as `cadrumo@neve` | The current generated contract records `aeat`, `plugins/aeat`, and `aeat@neve`; Claude plugin names are scoped by the marketplace repository rather than allocated by a demonstrated global registry | Required repository-scoped rename; no separate global reservation mechanism evidenced | Blocked until the controlled marketplace contains and validates the exact Cadrumo entry; do not claim global exclusivity |
| Human executable | `cadrumo` | `Get-Command cadrumo -All` returned no command on the current Windows workstation | No local collision observed; not an ecosystem-wide clearance | Blocked until clean-install smoke tests prove the installed script resolves to the intended distribution on supported platforms; document remediation for pre-existing user commands |
| MCP executable | `cadrumo-mcp` | `Get-Command cadrumo-mcp -All` returned no command on the current Windows workstation | No local collision observed; not an ecosystem-wide clearance | Same clean-install and supported-platform collision gate; plugin launch configuration must resolve the intended executable |
| Primary global domain | `cadrumo.com` | `https://rdap.verisign.com/com/v1/domain/cadrumo.com` returned HTTP 404 and DNS returned `NXDOMAIN` | Appears unregistered at observation time; not reserved | Blocked if selected as the canonical public domain until registered under operator control with recovery, renewal, DNS, and certificate ownership established |
| Spanish domain | `cadrumo.es` | DNS returned `NXDOMAIN`; no authoritative `.es` registration-result endpoint was captured | DNS absence only; availability unknown | Blocked if selected until checked and registered through an accredited `.es` registrar or the official Dominios.es channel |
| EU domain | `cadrumo.eu` | `https://rdap.org/domain/cadrumo.eu` returned HTTP 404 and DNS returned `NXDOMAIN` | Appears unregistered through the RDAP bootstrap result; not reserved | Blocked if selected until registered by an eligible operator and renewal ownership is established |
| Defensive organisation domain | `cadrumo.org` | `https://rdap.org/domain/cadrumo.org` returned HTTP 404 and DNS returned `NXDOMAIN` | Appears unregistered; not reserved | Product owner must explicitly reserve it or document acceptance of the defensive-registration risk |
| Defensive developer domain | `cadrumo.dev` | `https://rdap.org/domain/cadrumo.dev` returned HTTP 404 and DNS returned `NXDOMAIN` | Appears unregistered; not reserved; `.dev` deployment also implies HTTPS expectations | Product owner must explicitly reserve it or document acceptance of the defensive-registration risk |

The minimum required domain decision is one canonical product domain plus an explicit
decision on the defensive `.es`, `.eu`, `.org`, and `.dev` set. Availability can
change at any time, so these observations must be repeated immediately before an
authorised registration transaction.

### Trademark evidence and limitations

| Register or guidance | Direct locator and observation | What this Step establishes | Remaining blocker |
| --- | --- | --- | --- |
| OEPM national and Spain-effective marks | `https://consultas2.oepm.es/LocalizadorWeb/index.jsp` was reachable and describes searches for Spanish national marks, trade names, and international marks designating Spain | OEPM is a required primary search surface; its own notice says a complete Spain-effective search also requires EU marks | No reproducible exact/fuzzy result set for `Cadrumo` was exported. A qualified search must cover exact, phonetic, visual, and conceptually similar signs plus relevant Nice classes |
| EUIPO EU marks | `https://www.euipo.europa.eu/en/trade-marks/before-applying/availability` and `https://www.euipo.europa.eu/es/search-ip` were reachable; EUIPO directs applicants to TMview/eSearch plus and warns that similar signs and unregistered earlier rights can conflict | EUIPO/TMview is the required EU-wide primary search surface; a simple exact web query is insufficient | No application was filed and no legal clearance was obtained. Counsel or a qualified professional must search intended goods/services, owners, territories, similarity, status, priority, and unregistered rights |

Search-engine queries restricted to OEPM and EUIPO produced no indexed exact
`Cadrumo` record, but this is **not** recorded as a clean trademark result: official
register applications are interactive, indexed search is incomplete, similar marks
matter, and trademark risk depends on goods and services. Likely software and hosted
service coverage makes Nice classes 9 and 42 obvious starting points; tax, financial,
education, or business-service positioning may require additional classes selected by
qualified counsel. This Step does not provide legal advice.

### Release blockers carried forward

1. Reserve and prove operator control of all three exact PyPI projects; configure the approved publication path for each.
2. Choose and control the GitHub publisher account or organisation and canonical `cadrumo` repository.
3. Confirm control of `nevenincs/neve-marketplace`, then publish and strictly validate the repository-scoped `cadrumo` plugin entry only after implementation is ready.
4. Choose the canonical domain, register it, and explicitly accept or mitigate the defensive-domain risk for `.es`, `.eu`, `.org`, and `.dev`.
5. Obtain reproducible OEPM and EUIPO/TMview searches plus qualified Spanish/EU trademark clearance for the intended classes, similar signs, and unregistered rights.
6. Prove `cadrumo` and `cadrumo-mcp` on clean supported systems; current-workstation `PATH` absence is not a release proof.
7. Repeat every availability check immediately before reservation because none of the observations creates priority or ownership.

## Notes

- The general web fetcher reported primary-endpoint 404 responses as fetch errors; direct read-only HTTP requests confirmed the status codes recorded above.
- The `.es` registration position remains deliberately `unknown`, rather than inferred from DNS absence.
- OEPM/EUIPO interactive databases did not yield an exportable exact-result report in this pass; that limitation is a release blocker, not a passing result.
- The worktree contains extensive unrelated concurrent changes. Only this Step Record and the parent plan checkbox are owned by S04.
