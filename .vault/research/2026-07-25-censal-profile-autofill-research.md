---
tags:
  - '#research'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
related: []
---

# `censal-profile-autofill` research: `where the taxpayer's censal data actually lives`

The profile TUI exists so an operator does not retype what AEAT already
holds. That promise needs two things the codebase does not have: the
credentials to authenticate as the taxpayer, and a read surface carrying
their current censal position. A first implementation assumed the second
was the declarations register and derived censal state from filed Modelo
036 rows. A live authenticated run against the real Sede disproved that.
This records what the run showed, where the data actually is, and what is
missing between here and there.

## Findings

### The declarations register carries no censal data, and the codebase's censal pull was built on it

A live Cl@ve Móvil session (real credentials, real Playwright browser,
`live-filed-read` gate open) walked the declarations register for six
modelos across 2023-2025:

| modelo | rows |
| --- | --- |
| 100 | 1 |
| 303 | 10 |
| 130 | 8 |
| 111 | 10 |
| 390 | 2 |
| 036 | 0 |

The walk works: every other modelo returned real rows carrying real
expediente ids (`202430313520389Q`, `202511113520436S`). 036 returned
zero for every year 2022-2026. This is a true negative about the surface,
not about the taxpayer, who is demonstrably enrolled - they file 303 and
130 quarterly.

The reason is categorical. Modelo 036 is the declaración censal: the form
a person or entity files to communicate that their position or status in
the tax system has changed. It is not a periodic return, so it does not
appear in a register of returns. `application/live/_censo_036_pull.py`
derives censal facts by walking that register, so it returns "no censal
filing found" unconditionally, for every taxpayer.

### The current censal state is published at "mis datos censales"

AEAT's own bundled material names the surface. The Renta manuals state
that "el obligado tributario podrá acceder a la opción «mis datos
censales» disponible en la Sede electrónica"
(`src/cadrumo/_data/corpus/manuals/renta/2021/part1/source.pdf.extracted.md`),
and the bundled 036 procedure page links
`/Sede/ayuda/consultas-informaticas/presentacion-declaraciones-ayuda-tecnica/modelo-036/consulta-modificacion-datos-censales.html`
(`src/cadrumo/_data/corpus/aeat_official/instructions/modelo_036/files/presentacion-papel-modelo-036.html`).

This is state held by the authority, not a document to locate: it is what
the census currently says about the taxpayer, which is exactly the shape
the profile wants to be filled from.

### No censal endpoint exists in the outbound adapter

`src/cadrumo/adapters/outbound/aeat/sede/` carries declarations,
notifications, the IVA compensation wallet, NIF-IVA and GROI checks, and
Renta Web Open. There is no censal module, and `env/.env.example`
configures no censal path - the only sede paths are
`AEAT_SEDE_EXPEDIENTES_PATH`, `AEAT_STATUS_DETAIL_URL_TEMPLATE` and
`AEAT_STATUS_NOTIFICACIONES_PATH`. The capability must be built, not
rewired.

### The read sits next to a write tool, which is why it was retired before

The bundled procedure page titles the area "Consulta y modificación de
datos censales", and the same instructions link
`/wlpl/BU36-M036/MOD036/index` - the 036 filing tool.
`2026-07-11-censo-operator-manual-enrolment-adr` retired the earlier
censo scrape for precisely this adjacency: the only path it had to
current census state was the modification tool, and a read one accidental
submit away from mutating AEAT state is a live-write path with extra
steps. Any new reader has to be pinned to the consulta view and provably
unable to reach the modificación action - the constraint the ADR must
settle, not a reason to abandon the read.

### Authentication credentials have no home on the profile

Cl@ve authenticates a natural person with their DNI/NIE plus the número
de soporte printed on that document; the certificate provider instead
uses an installed certificate. Today the Cl@ve pair is read only from
`CADRUMO_CLAVE_MOVIL_DNI_NIE` and `CADRUMO_CLAVE_MOVIL_NIE_SOPORTE` in a
dotenv file. The user-profile schema had no `auth` section at all, so an
operator setting up through the TUI has no way to supply them, and a
second profile on the same machine cannot carry different ones.

`_assert_active_profile_identity_matches_provider`
(`src/cadrumo/application/auth/_sessions.py:563`) already fails closed
when the Cl@ve identity does not match the active profile's tax id, so
the two are contractually coupled already - the profile simply has
nowhere to store its half.

### The live path has real prerequisites that were never exercised

Reaching a live read needs, in order: an active profile bucket; that
bucket unlocked in-process (`no active bucket session` otherwise); the
profile's `identity.tax_id` matching the Cl@ve DNI/NIE; and
`CADRUMO_LIVE_TESTS_ENABLED`. The dotenv carried `AEAT_LIVE_TESTS_ENABLED`,
a name the settings loader explicitly did not read, so that flag was
inert. Each of these produced a distinct refusal before any browser
opened, and none had ever been exercised end to end.

### Not investigated

The censal page's DOM, its authenticated URL after the access selector,
and whether it exposes a structured export were not inspected - that
needs a live session pointed at the consulta view, which is the first
implementation step rather than a research one. Which censal fields map
onto which profile schema paths is likewise unresolved beyond the two
`censo.*` paths already declared.

## Sources

- `src/cadrumo/application/live/_censo_036_pull.py`
- `src/cadrumo/adapters/outbound/aeat/sede/`
- `src/cadrumo/application/auth/_sessions.py:563`
- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `src/cadrumo/_data/corpus/aeat_official/instructions/modelo_036/files/presentacion-papel-modelo-036.html`
- `src/cadrumo/_data/corpus/manuals/renta/2021/part1/source.pdf.extracted.md`
- `env/.env.example`
- Live authenticated register walk, 2026-07-25, this worktree; the table above is that run's output.
