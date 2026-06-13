---
tags:
  - '#research'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` research: `calculation authority evidence tiering`

This research clarifies whether AEAT provides authoritative calculation
references and how those references should govern the registry-backed
calculation engine. It complements the central registry ADR by separating legal
authority, official filing guidance, safe parity evidence, and record-layout
evidence.

## Findings

### BOE law and regulations are the primary legal authority

BOE consolidated legal texts are the controlling legal basis for rates,
thresholds, taxable bases, reductions, deductions, withholding regimes, and
payment-on-account rules. Registry calculation definitions must therefore carry
BOE legal references wherever the calculation is filing-grade.

Relevant source references:

- Ley 35/2006, del IRPF, BOE consolidated PDF:
  https://www.boe.es/buscar/pdf/2006/BOE-A-2006-20764-consolidado.pdf
- Real Decreto 439/2007, Reglamento del IRPF, BOE consolidated text:
  https://boe.es/buscar/act.php?id=BOE-A-2007-6820
- Ley 37/1992, del IVA, BOE consolidated text:
  https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740
- Ley 37/1992, del IVA, BOE consolidated PDF:
  https://www.boe.es/buscar/pdf/1992/BOE-A-1992-28740-consolidado.pdf

### AEAT model instructions are official filing and casilla guidance

AEAT model instructions provide official filing guidance and often state the
casilla-level operations needed to complete a model. They are valid source
evidence for model-specific casilla relationships, but they do not replace BOE
legal basis for the underlying tax rule.

Modelo 130 instructions explicitly point to Ley 35/2006 and Real Decreto
439/2007 as the Law and Regulation references, then describe casilla operations
such as subtracting casilla 02 from casilla 01, zero-clamping negative outcomes,
and applying the payment-on-account rules.

Relevant source reference:

- AEAT Modelo 130 instructions:
  https://sede.agenciatributaria.gob.es/Sede/impuestos-tasas/impuesto-sobre-renta-personas-fisicas/modelo-130-irpf______esionales-estimacion-directa-fraccionado_/instrucciones.html

Modelo 303 instructions identify the official help/presentation flow and the
Pre303 service. They provide filing guidance for IVA autoliquidation and should
be used as source evidence for model-specific behaviour, while Ley 37/1992 and
its regulations remain the legal basis for the tax rules.

Relevant source reference:

- AEAT Modelo 303 instructions 2025:
  https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/iva/modelo-303-iva-autoliquidacion_/instrucciones-2025.html
- AEAT Modelo 303 instructions PDF 2025:
  https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G414/Inst_mod_303_2025.pdf

### AEAT manuals are official guidance, but their legal weight must be explicit

AEAT practical manuals can contain extensive calculation guidance, especially
for Renta. They are important source evidence and can explain model behaviour,
but their own text may state informational limits. The registry must record the
manual as source evidence and still attach the BOE legal basis for filing-grade
calculation rules.

Relevant source references:

- AEAT Manual práctico de Renta 2025:
  https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/manual-practico-renta-2025.html
- AEAT Manual práctico de Renta 2025, Parte 1:
  https://sede.agenciatributaria.gob.es/Sede/Ayuda/25Manual/100.html
- AEAT Manual práctico de Renta 2025, Parte 1 PDF:
  https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf

### AEAT web/help programs are parity evidence, not source law

AEAT presentation/help services and Open simulators can provide strong
executable parity evidence when they can be used safely. They must not be used
as the legal source of a calculation. Authenticated presentation flows and any
surface that could write AEAT remote state are unsafe for synthetic tests unless
there is an explicitly authorized integration-test service.

Relevant source references:

- AEAT Modelo 303 service page, including Pre303 and Simulador 303 OPEN:
  https://sede.agenciatributaria.gob.es/Sede/empresas/impuesto-sobre-valor-anadido/presentar-declaracion-iva/modelo-303-iva-autoliquidacion.html
- AEAT simulators index:
  https://sede.agenciatributaria.gob.es/Sede/procedimientoini/ZZ08.shtml

### Record-design XLS/XLSX files are layout evidence, not calculation proof

AEAT record designs are authoritative for import/export file layout, field
positions, record structure, and format constraints. They are not calculation
authority unless a specific artefact also contains a reviewed tax calculation
formula surface and is classified separately as a formula-form workbook.

Local verification converted every committed binary XLS record-design artefact
to XLSX through LibreOffice in isolated storage. Conversion succeeded for all
25 XLS files, but the formulas observed were record-position helpers such as
row counters and cumulative field-position formulas, not tax calculation rules.
The committed XLSX record designs showed the same pattern.

Relevant source reference:

- AEAT Modelo 130 record design PDF:
  https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/ant_100_199/archivos/dr130.pdf

## Recommendation

The registry should implement a multi-tier evidence model:

1. Legal authority: BOE law, BOE regulations, and other binding legal texts.
2. Official calculation/source guidance: AEAT model instructions and AEAT
   manuals, with legal-weight caveats recorded per source.
3. Executable parity evidence: AEAT Open simulators, authorized test services,
   and true formula-form workbooks, only with remote-state guards and identical
   synthetic inputs.
4. Layout authority: AEAT record designs and file-format XLS/XLSX/PDF
   artefacts, usable for import/export schema and format verification, never as
   calculation proof.

The ADR should codify this hierarchy and the plan should roll it out as an
extended verification state before concrete modelo implementation waves.
