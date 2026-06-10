# Glossary

This glossary defines the Spanish tax terms used throughout the `aeat`
documentation.

AEAT (Agencia Estatal de Administración Tributaria)
: Spain's tax authority. You file with the AEAT yourself, through its official
  channels. `aeat` never submits anything on your behalf.

asesor fiscal / gestor
: Spanish tax professionals. `aeat` is not one and does not replace one. For
  advice on your situation, consult a qualified professional.

autónomo
: A self-employed person who files taxes with the AEAT.

binding
: A registry rule that maps a ledger entry or a profile fact to a casilla, so the
  calculation knows which input feeds which box on the form.

borrador
: A draft calculation of a modelo. `aeat` saves a borrador each time you
  calculate, and keeps every draft.

casilla
: A single numbered field on a modelo.

censo
: Your AEAT census: the registration data the AEAT holds about you, such as your
  activities, address, and tax obligations. It is declared on Modelo 036 or 037,
  and `aeat` can sync it into a profile.

declaración
: A tax return you file with the AEAT. A modelo is the form; the declaración is
  the return you submit on it.

expediente
: An AEAT case file. `aeat` can read expedientes when AEAT authentication is
  configured for read-only access; it never writes to them.

fichero-BOE
: The fixed-width text file format the AEAT accepts for upload. `aeat` writes
  this file when you export. It is named after the Boletín Oficial del Estado
  (BOE), which publishes the format.

formula (formula_id)
: A registry formula that computes a casilla's value. Its `formula_id` travels
  with the result, so every computed figure names the formula behind it.

IRPF (Impuesto sobre la Renta de las Personas Físicas)
: Spanish personal income tax. Modelo 100 is the annual return; Modelo 130 is the
  quarterly instalment for autónomos under direct estimation.

IVA (Impuesto sobre el Valor Añadido)
: Spanish value-added tax. Modelo 303 is the quarterly return; Modelo 390 is the
  annual summary.

justificante
: The receipt PDF the AEAT issues after you file. It carries the verification
  code and the figures you filed.

ledger
: Your record of money movements inside `aeat`. You import transactions into the
  ledger and classify each one for tax.

legal_refs and source_refs
: The provenance attached to each casilla. `legal_refs` cite the BOE and AEAT law
  behind a value; `source_refs` record where in the registry it came from.

modelo
: An Agencia Estatal de Administración Tributaria (AEAT) tax form, identified by
  a three-digit code such as 100 (personal income tax), 130 (quarterly
  income-tax instalment), or 303 (value-added tax, IVA).

NIF, CIF, DNI, and NIE
: Spanish tax and identity identifiers. The Número de Identificación Fiscal
  (NIF) is the tax identifier for everyone. For Spanish citizens the NIF is
  their Documento Nacional de Identidad (DNI) number; for foreign individuals
  it is their Número de Identidad de Extranjero (NIE). Companies and other
  legal entities also use a NIF; older records may call a company identifier
  Código de Identificación Fiscal (CIF). DNI and NIE on their own are identity
  documents - Cl@ve registration asks for them directly.

preflight
: A readiness check on the ledger for a period. It reports rows missing a
  category, a base amount, an IVA rate, a currency, or a prorrata reference
  before you calculate a modelo.

presentado
: The filed lifecycle state. `aeat` marks a verified revision presentado to record
  that you consider it final. It never submits to the AEAT.

prorrata
: The business-versus-personal split recorded on a transaction, so the
  calculation applies only the deductible proportion.

revision
: The version of a modelo's rules that applies to a given period, named in the
  registry. For example, `2019-y-siguientes` covers 2019 and later filings.

sede electrónica
: The AEAT's electronic filing portal, where you upload your exported file to
  file it yourself.

verificado completo
: The verified-complete lifecycle state. A draft reaches it once it passes the
  `verify` gate's completeness contract.

VIES (VAT Information Exchange System)
: The European Union system `aeat` can query, read-only, to check a VAT number.

work unit
: A handle over one calculation of a single modelo, year, period, and revision.
  `aeat` tracks each filing you prepare as a work unit.
