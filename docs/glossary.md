# Glossary

The Spanish tax terms used throughout the `aeat` documentation.

modelo
: An Agencia Estatal de Administración Tributaria (AEAT) tax form, identified by
  a three-digit code such as 100 (personal income tax), 130 (quarterly
  income-tax instalment), or 303 (value-added tax, IVA).

casilla
: A single numbered field on a modelo.

autónomo
: A self-employed person who files taxes with the AEAT.

justificante
: The receipt PDF the AEAT issues after you file. It carries the verification
  code and the figures you filed.

borrador
: A draft calculation of a modelo. `aeat` saves a borrador each time you
  calculate, and keeps every draft.

sede electrónica
: The AEAT's electronic filing portal, where you upload your exported file to
  file it yourself.

NIF (Número de Identificación Fiscal)
: The Spanish tax identification number that identifies each taxpayer.

fichero-BOE
: The fixed-width text file format the AEAT accepts for upload. `aeat` writes
  this file when you export. It is named after the Boletín Oficial del Estado
  (BOE), which publishes the format.

revision
: The version of a modelo's rules that applies to a given period, named in the
  registry. For example, `2019-y-siguientes` covers 2019 and later filings.

work unit
: A handle over one calculation of a single modelo, year, period, and revision.
  `aeat` tracks each filing you prepare as a work unit.

ledger
: Your record of money movements inside `aeat`. You import transactions into the
  ledger and classify each one for tax.
