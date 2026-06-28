---
tags:
  - '#reference'
  - '#quadlingual-i18n-ccaa'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-05-01-quadlingual-i18n-research]]"
  - "[[2026-05-01-quadlingual-i18n-adr]]"
  - "[[2026-05-01-quadlingual-i18n-reference]]"
---

# `quadlingual-i18n-ccaa` reference: comunidad-autónoma label catalogue across es / en / ca / hu

This is the canonical quad-lingual rendering for every Comunidad
Autónoma (CCAA) and the two foral regimes the project recognises.
The catalogue is consulted when wiring `Translatable` literals for
CCAA fields in the CLI, the deadline engine, and the residence
profile.

## sourcing principles

- **`es`** is taken from the official `Estatuto de Autonomía` of
  each community as published in the BOE; the long form (e.g.
  *Comunidad Autónoma del Principado de Asturias*) is the legally
  correct one but the common short form is what AEAT uses on its
  forms, so the short form is what we render to users by default.
- **`en`** uses the rendering AEAT itself uses on the
  English-language pages of `agenciatributaria.gob.es`. Where AEAT
  is silent, the EU Publications Office style guide
  (publications.europa.eu) is the secondary source.
- **`ca`** uses the autonomous-community's own official Catalan
  name (`Catalunya`, `Illes Balears`, `Comunitat Valenciana`) and
  the `Generalitat de Catalunya` rendering of every other community,
  taken from DOGC publications that name the other autonomies
  (e.g. cross-border tax-residence rules).
- **`hu`** uses the Hungarian-language Spanish-geography catalogue
  used by NAV when it cross-references Spanish administrative
  divisions in EU directive-implementing instruments. Where NAV
  is silent, the standard Hungarian geographic rendering applies
  (e.g. `Andalúzia`, `Katalónia`).

## ordinary CCAA short labels

The short label is what the CLI renders by default in tables and
help text. The long label is held for cases where disambiguation
matters (legal text, audit trails).

| Identifier | `es` (short) | `en` (short) | `ca` (short) | `hu` (short) |
| --- | --- | --- | --- | --- |
| `andalucia` | Andalucía | Andalusia | Andalusia | Andalúzia |
| `aragon` | Aragón | Aragon | Aragó | Aragónia |
| `asturias` | Asturias | Asturias | Astúries | Asztúria |
| `baleares` | Illes Balears | Balearic Islands | Illes Balears | Baleár-szigetek |
| `canarias` | Canarias | Canary Islands | Canàries | Kanári-szigetek |
| `cantabria` | Cantabria | Cantabria | Cantàbria | Kantábria |
| `castilla-la-mancha` | Castilla-La Mancha | Castile–La Mancha | Castella-la Manxa | Kasztília-La Mancha |
| `castilla-y-leon` | Castilla y León | Castile and León | Castella i Lleó | Kasztília és León |
| `cataluna` | Cataluña | Catalonia | Catalunya | Katalónia |
| `comunidad-valenciana` | Comunitat Valenciana | Valencian Community | Comunitat Valenciana | Valenciai Közösség |
| `extremadura` | Extremadura | Extremadura | Extremadura | Extremadura |
| `galicia` | Galicia | Galicia | Galícia | Galícia |
| `la-rioja` | La Rioja | La Rioja | La Rioja | La Rioja |
| `madrid` | Madrid | Madrid | Madrid | Madrid |
| `murcia` | Región de Murcia | Region of Murcia | Regió de Múrcia | Murciai Régió |

## ordinary CCAA long labels

| Identifier | `es` (long) | `en` (long) | `ca` (long) | `hu` (long) |
| --- | --- | --- | --- | --- |
| `andalucia` | Comunidad Autónoma de Andalucía | Autonomous Community of Andalusia | Comunitat Autònoma d'Andalusia | Andalúzia Autonóm Közösség |
| `aragon` | Comunidad Autónoma de Aragón | Autonomous Community of Aragon | Comunitat Autònoma d'Aragó | Aragónia Autonóm Közösség |
| `asturias` | Principado de Asturias | Principality of Asturias | Principat d'Astúries | Asztúriai Hercegség |
| `baleares` | Comunidad Autónoma de las Illes Balears | Autonomous Community of the Balearic Islands | Comunitat Autònoma de les Illes Balears | Baleár-szigetek Autonóm Közösség |
| `canarias` | Comunidad Autónoma de Canarias | Autonomous Community of the Canary Islands | Comunitat Autònoma de Canàries | Kanári-szigetek Autonóm Közösség |
| `cantabria` | Comunidad Autónoma de Cantabria | Autonomous Community of Cantabria | Comunitat Autònoma de Cantàbria | Kantábria Autonóm Közösség |
| `castilla-la-mancha` | Comunidad Autónoma de Castilla-La Mancha | Autonomous Community of Castile–La Mancha | Comunitat Autònoma de Castella-la Manxa | Kasztília-La Mancha Autonóm Közösség |
| `castilla-y-leon` | Comunidad Autónoma de Castilla y León | Autonomous Community of Castile and León | Comunitat Autònoma de Castella i Lleó | Kasztília és León Autonóm Közösség |
| `cataluna` | Generalitat de Catalunya | Government of Catalonia | Generalitat de Catalunya | Katalónia Autonóm Közösség (Generalitat) |
| `comunidad-valenciana` | Generalitat Valenciana | Valencian Government | Generalitat Valenciana | Valenciai Közösség (Generalitat Valenciana) |
| `extremadura` | Comunidad Autónoma de Extremadura | Autonomous Community of Extremadura | Comunitat Autònoma d'Extremadura | Extremadura Autonóm Közösség |
| `galicia` | Comunidad Autónoma de Galicia | Autonomous Community of Galicia | Comunitat Autònoma de Galícia | Galícia Autonóm Közösség |
| `la-rioja` | Comunidad Autónoma de La Rioja | Autonomous Community of La Rioja | Comunitat Autònoma de La Rioja | La Rioja Autonóm Közösség |
| `madrid` | Comunidad de Madrid | Community of Madrid | Comunitat de Madrid | Madridi Közösség |
| `murcia` | Comunidad Autónoma de la Región de Murcia | Autonomous Community of the Region of Murcia | Comunitat Autònoma de la Regió de Múrcia | Murciai Régió Autonóm Közösség |

## foral regimes (out of scope for #452)

País Vasco and Navarra operate under separate `regímenes forales`
with their own tax administrations (Diputaciones Forales /
Hacienda Foral de Navarra). The project explicitly excludes them
from the ordinary-CCAA RENTA flow until #452 expands scope.

| Identifier | `es` (short) | `en` (short) | `ca` (short) | `hu` (short) |
| --- | --- | --- | --- | --- |
| `pais-vasco` | País Vasco | Basque Country | País Basc | Baszkföld |
| `navarra` | Navarra | Navarre | Navarra | Navarra |

| Identifier | `es` (long) | `en` (long) | `ca` (long) | `hu` (long) |
| --- | --- | --- | --- | --- |
| `pais-vasco` | Comunidad Autónoma del País Vasco | Autonomous Community of the Basque Country | Comunitat Autònoma del País Basc | Baszkföld Autonóm Közösség |
| `navarra` | Comunidad Foral de Navarra | Chartered Community of Navarre | Comunitat Foral de Navarra | Navarrai Foral Közösség |

## foral diputaciones (referenced for cross-border RENTA cases)

| `es` | `en` | `ca` | `hu` |
| --- | --- | --- | --- |
| Diputación Foral de Bizkaia | Provincial Council of Biscay | Diputació Foral de Biscaia | Bizkaiai Foral Tartomány |
| Diputación Foral de Gipuzkoa | Provincial Council of Gipuzkoa | Diputació Foral de Guipúscoa | Guipuzkoai Foral Tartomány |
| Diputación Foral de Álava | Provincial Council of Álava | Diputació Foral d'Àlaba | Álavai Foral Tartomány |
| Hacienda Foral de Navarra | Foral Treasury of Navarre | Hisenda Foral de Navarra | Navarrai Foral Adóhivatal |

## diacritic + capitalisation notes

- Catalan capitalises `Catalunya`, `Illes Balears`, and `Comunitat
  Valenciana` exactly as the autonomous communities themselves
  publish them. The lowercase article `de`/`del`/`d'`/`de la` is
  preserved.
- The Spanish renderings keep the diacritics on `Aragón`, `León`,
  `Cataluña`, `Galicia`, `Cantabria`, `Castilla y León`,
  `Comunidad`, and `Comunitat` exactly as the BOE publishes them.
  The script `Region of Murcia` renders `Región` with the acute
  accent because the BOE form does so.
- Hungarian renderings add `i` for the genitive form
  (`Madridi Közösség`, `Murciai Régió`) following standard
  Hungarian geographic naming. Cardinal points and proper-noun
  diacritics (`Asztúria`, `Baszkföld`) follow `Magyar Helyesírási
  Szabályzat` (the official Hungarian orthography rule book).
- The catalogue keeps the long form `Generalitat de Catalunya`
  unchanged across `es`, `en`, and `ca`; the institution name is
  proper noun and is left untranslated. The Hungarian slot does
  the same and adds an explanatory parenthetical on first use.

## consumption protocol

Code that needs a CCAA label looks the identifier up in this
catalogue and constructs the corresponding `Translatable`. New
labels must be added here first; the perpetual i18n audit loop
flags any code-side `Translatable` carrying a CCAA name not
sourced from this document.

The `KentTaxResidence` profile records the identifier (kebab-case
short id), not the rendered label; rendering happens at CLI
emission time so the operator's `AEAT_OUTPUT_LANGUAGE` setting
governs which slot is shown.
