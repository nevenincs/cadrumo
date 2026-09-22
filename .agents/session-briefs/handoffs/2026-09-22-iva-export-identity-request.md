# IVA-01 Modelo 303 export identity — exact external evidence request

The installed 2025 Modelo 303 calculation/verification works, but its official EEDD export remains blocked. This note does not request a made-up value or reopen the unchanged source trace. The user identified themselves as Cadrumo's developer and stated that Cadrumo has no official/reviewer-approved values for these header fields; treat them as unavailable.

| Required 2025 DP30300 header field | Governing design | Who can provide it | Required project evidence |
|---|---|---|---|
| `Versión del Programa`, positions 93–96, exactly four characters | Official AEAT 2025 Modelo 303 record design, Note 1: development entity completes the EEDD fields; AEAT does not assign the four-character release code in that note | Cadrumo developer/release owner, **only if** a genuine release identifier or reviewed derivation has been approved | Reviewer-approved release registry/configuration entry, derivation rule if any, source reference and digest bound to the exact package/release |
| `NIF del desarrollador`, positions 101–109, validated nine-character Spanish NIF | Same official 2025 DP30300 design and Note 1 | Actual Cadrumo development legal entity/developer, not the taxpayer, filing presenter or Modelo 100 producer | Authoritative developer identity record plus reviewer approval/reference/digest; validation of NIF syntax and ownership |

Official source listing: [AEAT prior-year Modelo 300–399 record designs](https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/ejercicios-anteriores-modelos-300-399.html), 2025 Modelo 303 DP30300 workbook. The exact positions and Note 1 were previously traced in the IVA checkpoint; no new authority generation or publication is implied.

If Cadrumo does not have these values, the responsible developer/release approver must either (a) establish and review genuine values with provenance, or (b) supply official evidence of a valid non-EEDD export path and obtain an accepted product-authority decision. Until then, preserve the installed export-readiness refusal. Do not use taxpayer/presenter NIF, M100's three-byte `PACKAGE_VERSION` encoding, a placeholder, blank bytes, an unreviewed package version, or a fabricated authority descriptor. `verificado_completo` remains calculation verification only. No live AEAT submission is authorized.

Acquisition state: user confirms values unavailable/unapproved. There is no pending request to derive them internally; external value/approval and any non-EEDD authority decision are **not received**. This blocker applies to official 303 export, not local calculation, verification, annual reconciliation or allowed frontend continuation.
