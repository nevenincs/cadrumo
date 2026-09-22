# RETENCIONES-01 annual3 Modelo 190 public-screen gap

The sole annual3 retry used the isolated root
`C:\Users\hello\AppData\Local\Temp\retenciones-cli-to-tui-d0bdd2a36da147beb60da1d9ef1e76b5\annual3`.
The monitored process chain exited. No annual4 process was started.

Pinned identities are unchanged from annual2: source revision
`d2858767eafdbbeef073972e2cb8cd1271b31f97`; wheel SHA-256
`6c8d926c0e4274233cba86eb961bb29f1cce8890b92d2d9fc0b845e1b24c951b`;
source and installed launcher SHA-256
`65d3c58c861844ae0b6f65c327f72d7a6af3173e5843b6a0231d8974f0b80ea4`;
authority logical generation
`db354561492ec6670dc775f9dd7fa24526098b74ab6b86dac0d5134df16430b4`.

Results:

- The installed TUI capture child is `proven`.
- Modelo 180 completed its independently parsed annual export before Modelo
  190 started.
- The public Modelo 190 verify result was refused. Its sanitized receipt is
  `status=failed`, `stage=annual_continuation`, and
  `code=tui-190-annual_verification_not_complete`.
- Retained safe identifiers are
  `kind:missing_required_casilla`, `casilla_id:perc.ceuta-melilla`, and
  `kind:advisory`; the retained missing-casilla identifier is
  `perc.ceuta-melilla`.

The routed Withholding screen exposes professional annual fields for clave,
subclave, province, and percentage, but no public territorial-deduction or
Ceuta/Melilla field. Its professional-detail mapper consequently has no
`territorial_deduction_clave` input, while the selected Modelo 190 registry
binding maps that required source field to `perc.ceuta-melilla`. The binding
defines territorial deduction as a payer-supplied value; it cannot be inferred
from province. Supplying a zero from this acceptance driver would invent a
taxpayer fact, and changing the screen is outside this driver's ownership.
This is therefore a precise public screen/product gap, not a fixture omission.
No live submission, Modelo 190 export, fresh reopen, or TUI-only lifecycle is
claimed.
