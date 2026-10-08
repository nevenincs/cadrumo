---
tags:
  - '#research'
  - '#google-outbound-review'
date: '2026-10-05'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:b3de363723ad3b8d52ef3fb6c49d179d038ad36e077277d4979ab4eb0b7e74e7'
related: []
---

# `google-outbound-review` research: `Provider containment limits and scoped audit obligations`

## Findings

### Direct native creation is supported, folder authorization is not

Fetched official Google documentation on 2026-10-05. Drive files.create accepts a parents field; native spreadsheets use application/vnd.google-apps.spreadsheet. drive.file grants per-file access, not a parent-folder sandbox. Sheets spreadsheets.get names a spreadsheet ID and offers ranges/field filtering, with no expected-parent condition. Inference: an application ancestry check followed by a Sheets request cannot atomically prevent access if a user moves the file in between. Admission before every request, narrowly scoped metadata probes and a postcheck can reduce and detect some races, but cannot truthfully promise no request ever crosses a concurrently changed folder boundary. Do not widen OAuth scope as a remedy.

### Invoice retention concerns source documents, not workbook styling

AEAT's current invoice-retention guidance requires preserving invoices/justifications with authenticity, integrity, legibility and access without unjustified delay. RD 1619/2012 articles 19-23 govern document conservation, electronic legibility, location and access. These obligations motivate original payloads and associated signature/verification material; a Sheet URL or digest alone cannot supply them. This is a general invoice-retention baseline, not a certification of any Modelo audit package.

### A single four-year deletion rule is insufficient

LGT articles 66, 66 bis and 70 distinguish prescription from continuing evidentiary obligations and checks involving deductions or offsets. Determine relevant tax, period, later effects and any open request before retention/deletion decisions. This session neither sets an automatic deletion schedule nor certifies satisfaction of a particular authority request. Further research must pin the requested Modelo/period, procedure, required records and submission format, plus special regimes and any relevant commercial retention duties.

## Sources

- https://developers.google.com/workspace/drive/api/guides/folder
- https://developers.google.com/workspace/drive/api/guides/api-specific-auth
- https://developers.google.com/workspace/sheets/api/guides/create
- https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/get
- https://sede.agenciatributaria.gob.es/Sede/iva/facturacion-registro/facturacion-iva/obligacion-conservar-facturas.html
- https://www.boe.es/buscar/act.php?id=BOE-A-2012-14696
- https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186
