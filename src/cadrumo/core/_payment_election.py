"""The operator's positive-result payment-method election.

``PaymentElection`` is deliberately separate from :class:`RefundElection`.
The latter applies only to a negative Modelo 303 credit (``C`` versus ``D``),
whereas this closed axis selects how an otherwise payable positive result
(``I``) is settled. Keeping the two axes distinct means a direct-debit
election can never be mistaken for a refund request or affect compensation
carry-forward.
"""

from __future__ import annotations

from enum import StrEnum


class PaymentElection(StrEnum):
    """The semantic settlement choice for a positive result.

    ``CUENTA_CORRIENTE`` remains typed but capability-refused until its filing
    semantics are officially grounded; it must never infer a charge account.
    """

    INGRESO = "ingreso"
    DOMICILIACION = "domiciliacion"
    CUENTA_CORRIENTE = "cuenta_corriente"


__all__ = ["PaymentElection"]
