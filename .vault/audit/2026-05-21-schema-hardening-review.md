---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-21'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
  - '[[2026-05-21-schema-hardening-semantic-role-sidecar-audit]]'
  - '[[2026-05-21-schema-hardening-reference]]'
---

# `schema-hardening` Code Review

REVIEW-001 | LOW | Pre-existing dangling schema-hardening wiki-links remain outside this slice

`uv run vaultspec-core vault check dangling --feature schema-hardening` reports
nine dangling `related:` links in older 2026-05-19 audit files. The current
slice did not create those files or links, and the new plan, reference, audit,
and exec records link to existing vault documents. This is not blocking for the
semantic-role sidecar continuation, but a future vault-curation pass should
resolve the old references.

REVIEW-002 | INFO | Current slice is documentation and policy only

No registry source files were edited. The review verified that the plan is
closed through `vaultspec-core`, the current slice has step records, and the
guard reference preserves legally meaningful bases rather than instructing a
blind semantic-role rewrite.

REVIEW-003 | INFO | P06 suffix grammar inventory remains evidence-bounded

The P06 continuation records exact counts from committed registry fragments
and does not define legal concepts beyond visible lexical markers in role
names and labels. The unmatched set is explicitly deferred rather than folded
into the first mechanical parser.

REVIEW-004 | INFO | P07 repeated-label inventory rejects cross-family merging

The P07 continuation records exact Modelo 100 2025 repeated-label records by
section and current role. It explicitly limits future extraction to approved
family-local boundaries and does not propose registry role rewrites.

REVIEW-005 | INFO | P08 keeps generated/pending extraction allowlist-based

The P08 continuation identifies possible family-local generated/pending
patterns but records blockers for generic CCAA-prefix parsing. It leaves only
the already grounded `c_valenciana_autoconsumo` family approved for
implementation planning.

REVIEW-006 | INFO | P09 municipality-code label is not a global merge target

The P09 continuation records exact municipality-code repeated-label records
and flags the blank-versus-text data-type split. It blocks a global
`municipality_code` role merge until source and type policy are reviewed.

REVIEW-007 | INFO | W02.P10.S17 allowlist separates complete and near-complete bases

The allowlist records 23 complete 8-axis Modelo 200 base stems separately from
13 near-complete 7-axis stems. The near-complete set is marked review-needed,
so the future implementation is not authorized to treat missing axes as
semantically irrelevant without a source check.

REVIEW-008 | INFO | W02.P10.S18 mismatch guard is keyed by casilla ID

The mismatch exclusion guard is recorded as a future extractor contract keyed
by `(modelo, revision, casilla_id)`. This avoids the unsafe alternative of
excluding entire role names where the same role may also appear on valid
permanent-label records.

REVIEW-009 | INFO | W02.P10.S19 avoids tautological tests

The legal-base preservation checks are recorded as a future extractor test
contract rather than as tests against the existing typo-warning helper. This
keeps the verification tied to future behavior that will actually extract
sidecar axes.

REVIEW-010 | INFO | W03.P11.S20 grounds the approved M100 pilot in manual text

The C Valenciana autoconsumo pilot is now tied to the Renta 2025 manual title
and Anexo B.12 references for `hasta 2022` and `a partir de 2023`. The audit
does not promote other generated/pending families by analogy.

REVIEW-011 | INFO | W03.P11.S21-S22 keep the M100 pilot exact-ID allowlisted

The C Valenciana metadata and test contracts apply only to IDs `1963`, `1964`,
and `1965`, while `1114` and `1962` remain legal year-window concepts. The
contracts reject generic generated/pending suffix parsing across Modelo 100.

REVIEW-012 | INFO | W04.P12 promotes Murcia infraestructuras only as exact-ID family

The Murcia infraestructuras candidate is grounded in the Renta 2025 manual and
promoted for future planning, but only for IDs `2162`, `2163`, and `2164`.
The audit blocks merges with other Murcia vehicle or generic generated/pending
roles.

REVIEW-013 | INFO | W04.P13 promotes Madrid nuevos contribuyentes only as exact-ID family

The Madrid candidate is grounded in the Renta 2025 manual and promoted for
future planning, but only for IDs `2031` and `2032`. The audit blocks merges
with generic Madrid generated/pending rows and adjacent investment deductions.

REVIEW-014 | INFO | W04.P14 blocks La Rioja until the base role is family-specific

The La Rioja pair is source identified but not promoted. The current role base
is CCAA-generic, so any extraction would preserve the wrong base unless a
separate semantic-role correction lands first.

REVIEW-015 | INFO | W04.P15 blocks Catalunya until the base role is family-specific

The Catalunya pair is source identified against the Renta 2025 manual and
registry adjacency, but the current generated/pending role stems do not
preserve the cooperative-society family. The audit correctly blocks extraction
until a separate semantic-role correction can preserve a family-specific base.

REVIEW-016 | INFO | W05 discovery records candidates without promoting them

The W05 scan surfaces additional high-volume grids in Modelo 100 and Modelo
200, but each candidate is recorded with source requirements and no-go
conditions. No newly discovered surface is promoted because none has completed
official source lookup.

REVIEW-017 | INFO | Final execution review passes with pre-existing dangling-link caveat

The plan is closed at 33 of 33 steps through the vault plan CLI. Frontmatter is
clean. The dangling-link check still reports the nine older 2026-05-19
schema-hardening links already recorded in REVIEW-001; this execution did not
create those links and did not modify those older audit files.

REVIEW-018 | INFO | W06.P17 promotes financial-expense grid with legal branch guard

The financial-expense carryforward grid is source-grounded in the official
Modelo 200 manual and promoted only as an exact-ID table-axis candidate. The
audit preserves the distinction between `Por límite 16.5 y 83 LIS` and `Resto`
and blocks treating `Total` rows as generation-year rows.

REVIEW-019 | INFO | W06.P18 blocks BIN single-role extraction due to split roles

The general BIN compensation table is source-grounded, but the registry splits
the official table across `is_bin_detalle_compensacion` and
`is_compensacion_bases_negativas`. The audit correctly blocks single-role
sidecar extraction until an exact-ID inventory and semantic-role policy
decision handles that split.

REVIEW-020 | INFO | W06.P19 promotes cooperative quota grid as legally separate

The cooperative quota compensation grid is source-grounded in the official
Modelo 200 manual and kept separate from general BIN compensation. The audit
promotes it only as exact-ID metadata on `is_cooperativa_compensacion_cuotas`
and preserves `Total` and `2025(*)` guards.

REVIEW-021 | INFO | W07.P20 promotes general donations with reiteration preserved

The general donations grid is source-grounded in the official Modelo 200
manual and promoted only with the `sin_reiteracion` versus `con_reiteracion`
axis preserved. The audit blocks merging with priority patronage donations and
keeps subtotal, total, and `2025(*)` rows out of ordinary year handling.

REVIEW-022 | INFO | W07.P21 blocks Canarias investment single-role extraction

The Canarias investment deduction table is source-grounded, but the registry
splits future-pending rows across `is_deduccion_inversion_canarias_importe`
and `is_deduccion_inversion_canarias_pendiente`. The audit also preserves
legally meaningful subfamilies, including La Palma, La Gomera, and El Hierro
limit-marker rows.

REVIEW-023 | INFO | W07.P22 promotes I+D+i excluded-limit grids branch-separated

The I+D+i excluded-limit grids are source-grounded in the official Modelo 200
manual and promoted only as branch-separated exact-ID candidates. The audit
preserves investigation/development, technological innovation, the art. 39.2
option, reduced deduction, applied amount, and abono states.

REVIEW-024 | INFO | W08.P23 promotes Anexo C axes with basket preservation

The Anexo C carryforward audit is grounded in the Renta 2025 manual and the
official Modelo 100 declaration dictionary. It promotes only `origin_year` and
`carryforward_state` metadata under exact-ID, basket-preserving boundaries.
It explicitly blocks merging negative gains/losses, capital-mobiliario,
social-prevision, protected-patrimony, deportista, negative-base, and
energy-efficiency baskets by shared labels.

REVIEW-025 | INFO | W08.P24 promotes deferred-imputation slots branch-separated

The deferred-imputation audit is grounded in the Renta 2025 manual's
element-by-element Anexo C.1 wording and the official declaration dictionary.
It promotes slot metadata only while preserving ordinary patrimonial,
cryptocurrency, and immovable-property branches, and while keeping pending
gain and pending loss as distinct fields.

REVIEW-026 | INFO | W08.P25 blocks global cadastral-reference normalization

The cadastral-reference audit is grounded in the Renta 2025 manual and the
official declaration and toma-de-datos dictionaries. It correctly blocks a
single global cadastral-reference semantic role because the source fields span
text references and logical no-reference markers across many unrelated
property, Anexo A, Anexo B, FEAC, gain/loss, and regional deduction contexts.

REVIEW-027 | INFO | W08 execution review passes with inherited dangling-link caveat

The plan is closed at 51 of 51 steps through the vault plan CLI. Frontmatter is
clean. The dangling-link check still reports the nine older 2026-05-19
schema-hardening links already recorded in REVIEW-001 and REVIEW-017; W08 did
not create those links and did not modify those older audit files.

REVIEW-028 | INFO | W09.P26 implements audited warning-sidecar guards without registry rewrites

The validator now suppresses typo-twin warnings only for source-grounded
Anexo C same-basket carryforward state roles and deferred-imputation same-branch
slot roles. The registry TOML `semantic_role` values were not edited.

REVIEW-029 | INFO | W09.P26 tests preserve legal non-normalization boundaries

Regression coverage proves that `gyp_general` and `gyp_ahorro`,
`exceso_eeficiencia` and `exceso_eficiencia_energetica`, ordinary and
cryptocurrency branches, gain and loss polarity, and cadastral reference text
versus no-reference marker roles remain non-siblings.

REVIEW-030 | INFO | W09.P27 supporting docs align implementation to W08 source audit

The reference and sidecar audit documents now map the W08 source-grounded
decisions to the W09 validator behavior, including the allowed warning-sidecar
axis suppressions and the no-go conditions for cross-basket, cross-branch,
gain/loss, and cadastral normalization.

REVIEW-031 | INFO | W09 execution review passes with inherited dangling-link caveat

The plan is closed at 54 of 54 steps through the vault plan CLI. The focused
registry tests and ruff check pass, and the frontmatter check is clean. The
dangling-link check still reports the same nine older 2026-05-19
schema-hardening links already recorded in REVIEW-001, REVIEW-017, and
REVIEW-027; W09 did not create those links and did not modify those older audit
files.

REVIEW-032 | INFO | W10.P28 adds balance-only correction warning axes

The Modelo 200 warning-sidecar guard now includes `saldo_inicial` and
`saldo_final` as audited correction-table axes for typo-warning suppression
when the preserved base stem is identical. This fills the gap between the
reference contract and the previous suffix list.

REVIEW-033 | INFO | W10.P28 keeps mismatch bucket out of metadata extraction

The mismatch-bucket regression keeps the known
`is_correccion_libertad_amortizacion_vehiculos_*` warning pair quiet without
rewriting registry roles or deriving correction metadata from the disputed
`permanente_*` suffix. The source-backed mismatch policy remains a future
registry correction or label-derived metadata decision.

REVIEW-034 | INFO | W10 execution review passes with inherited dangling-link caveat

The plan is closed at 57 of 57 steps through the vault plan CLI. The focused
registry tests and ruff check pass, and the frontmatter check is clean. The
dangling-link check still reports the same nine older 2026-05-19
schema-hardening links already recorded in REVIEW-001, REVIEW-017, REVIEW-027,
and REVIEW-031; W10 did not create those links and did not modify those older
audit files.

REVIEW-035 | INFO | W11.P30 implements exact-family generated/pending warning guard

The generated/pending guard is limited to the source-approved
`c_valenciana_autoconsumo`, `murcia_infraestructuras`, and
`madrid_nuevos_contribuyentes` family bases. It suppresses typo warnings only
inside those bases and does not rewrite registry semantic roles.

REVIEW-036 | INFO | W11.P30 preserves blocked generic and legal-window boundaries

Regression coverage keeps La Rioja and Catalunya generated/pending pairs
non-siblings while their preserved bases are CCAA-generic. It also keeps the C
Valenciana `hasta_2022` and `desde_2023` roles as legal-window concepts rather
than generated/pending axes.

REVIEW-037 | INFO | W11 execution review passes with inherited dangling-link caveat

The plan is closed at 60 of 60 steps through the vault plan CLI. The focused
registry tests and ruff check pass, and the frontmatter check is clean. The
dangling-link check still reports the same nine older 2026-05-19
schema-hardening links already recorded in REVIEW-001, REVIEW-017, REVIEW-027,
REVIEW-031, and REVIEW-034; W11 did not create those links and did not modify
those older audit files.

REVIEW-038 | INFO | W12.P32 removes broad CCAA typo-warning equivalence

The validator no longer treats autonomous-community tokens as a generic axis
for typo-warning suppression. This aligns the code with the sidecar audit
finding that repeated cross-CCAA wording is not legal equivalence.

REVIEW-039 | INFO | W12.P32 replaces hidden CCAA suppression with explicit singleton policy

The four current Modelo 100 roles exposed by removing the broad guard are now
marked as source-grounded intentional singletons in the registry:
`irpf_deduccion_madrid_generado_pendiente_aplicacion`,
`irpf_deduccion_murcia_vehiculo_matricula`,
`irpf_deduccion_murcia_vehiculo_importe`, and
`irpf_deduccion_canarias_acciones_participaciones`.

REVIEW-040 | INFO | W12 execution review passes with inherited dangling-link caveat

The plan is closed at 64 of 64 steps through the vault plan CLI. The focused
semantic-role tests, Modelo 100 registry tests, committed-registry tests, and
ruff check pass, and the frontmatter check is clean. The dangling-link check
still reports the same nine older 2026-05-19 schema-hardening links already
recorded in REVIEW-001, REVIEW-017, REVIEW-027, REVIEW-031, REVIEW-034, and
REVIEW-037; W12 did not create those links and did not modify those older audit
files.

REVIEW-041 | INFO | W13.P34 removes broad legal-reference typo-warning equivalence

The validator no longer strips `art*`, `dt*`, `rdleg`, or `lis` tokens as a
generic typo-warning comparison step. Legal-reference markers remain part of
the preserved role stem unless a later source-backed policy authorizes a
narrower family-specific rule.

REVIEW-042 | INFO | W13.P34 replaces hidden legal-marker suppression with explicit singleton policy

The 13 current Modelo 200 roles exposed by removing the broad guard are now
marked as source-grounded intentional singletons in the registry. The set
covers `art11_4` and `dt1` operaciones-a-plazos correction rows and the
historic `rdleg` DI internacional pending row.

REVIEW-043 | INFO | W13 execution review passes with inherited dangling-link caveat

The plan is closed at 68 of 68 steps through the vault plan CLI. The focused
semantic-role tests, Modelo 200 registry tests, committed-registry tests, and
ruff check pass, and the feature-scoped frontmatter check is clean. The
dangling-link check still reports the same nine older 2026-05-19
schema-hardening links already recorded in REVIEW-001, REVIEW-017, REVIEW-027,
REVIEW-031, REVIEW-034, REVIEW-037, and REVIEW-040; W13 did not create those
links and did not modify those older audit files.

REVIEW-044 | INFO | W14.P36 identifies remaining broad warning suppressors

The post-W13 suppressor audit finds that the exact W08-W13 helpers are not the
current legal-risk surface. The remaining broad surfaces are the legacy
`optional_or_numeric_token_strip` helper and the mixed `axis_token_group`
helper; both require source-specific burn-down rather than another generic
normalization rule.

REVIEW-045 | INFO | W14.P37 ranks optional/numeric stripping as next control target

The fresh Modelo 100/200 census has zero emitted warnings, 454 unmarked
singletons, and 28 intentional singletons. Disabling optional/numeric stripping
would expose 36 independent warnings across year, line, catastral, quoted-fund,
generated/pending, and `con/sin mantenimiento de empleo` surfaces. This is the
next best legal-risk reduction slice.

REVIEW-046 | INFO | W14 execution review passes with inherited dangling-link caveat

The plan is closed at 72 of 72 steps through the vault plan CLI. W14 is an
audit and planning-control slice only; it does not edit validator code or
registry source TOML. The feature-scoped frontmatter check is clean and
`git diff --check` reports no whitespace errors beyond existing CRLF warnings.
The dangling-link check still reports the same nine older 2026-05-19
schema-hardening links already recorded in REVIEW-001, REVIEW-017, REVIEW-027,
REVIEW-031, REVIEW-034, REVIEW-037, REVIEW-040, and REVIEW-043; W14 did not
create those links and did not modify those older audit files.

REVIEW-047 | INFO | 2026-05-22 sub-plan removes `sin` from broad optional stripping

The optional/numeric sub-plan source lookup confirms that Modelo 200
`con/sin mantenimiento de empleo` is a legally meaningful regime distinction:
the official Sociedades manual separates `RDL 6/2010` con mantenimiento from
`RDL 13/2010` sin mantenimiento, both under `DT 13a.2 LIS`. The validator no
longer treats `sin` as a globally optional typo-warning token.

REVIEW-048 | INFO | Source-backed singleton policy replaces hidden maintenance-employment suppression

The 12 current Modelo 200 correction rows exposed by removing `sin` are marked
as intentional singletons: `02631`, `02632`, `02633`, `02636`, `02637`,
`02638`, `02641`, `02642`, `02643`, `02646`, `02647`, and `02648`. Quoted-fund
`coti`, generated/pending year and line rows, cadastral slots, `agr`, `aav`,
`b`, `anio`, and `precio` remain blocked for future family-local source slices.

REVIEW-049 | INFO | 2026-05-22 optional/numeric execution review passes with inherited dangling-link caveat

The 2026-05-22 optional/numeric sub-plan is closing through the vault plan CLI.
Focused semantic-role tests, touched-file ruff, cross-revision singleton drift,
Modelo 200 registry tests, committed-registry tests, and direct Modelo 100/200
warning probe pass. Plan structure and feature-scoped frontmatter checks are
clean. The dangling-link check still reports the same nine older 2026-05-19
schema-hardening links already recorded in REVIEW-001, REVIEW-017, REVIEW-027,
REVIEW-031, REVIEW-034, REVIEW-037, REVIEW-040, REVIEW-043, and REVIEW-046;
this sub-plan did not create those links and did not modify those older audit
files.

REVIEW-050 | INFO | Coti sub-plan removes quoted-fund token from broad optional stripping

The `schema-hardening-coti` sub-plan confirms that Modelo 100 2025
`gp_fondos_coti` is a source-visible quoted-fund section, not an optional role
spelling fragment. The validator no longer treats `coti` as globally optional.

REVIEW-051 | INFO | Source-backed singleton policy replaces hidden coti suppression

The six current Modelo 100 `gp_fondos_coti` warning-exposed rows are now
intentional singletons: `2227`, `2228`, `2229`, `2230`, `2231`, and `2234`.
Related row `2233` is intentionally out of scope because prior audit flagged a
possible rename concern.

REVIEW-052 | INFO | Coti execution review passes

The `schema-hardening-coti` plan is closing through the vault plan CLI. Focused
semantic-role tests, touched-file ruff, cross-revision singleton drift, Modelo
100 registry tests, committed-registry tests, and direct Modelo 100/200 warning
probe pass. The coti plan structure, feature-scoped frontmatter check, and
feature-scoped dangling-link check are clean. `git diff --check` reports no
whitespace errors, only CRLF warnings from the dirty worktree.
