"""Test-owned representative AEAT write actions for guard proofs."""

AEAT_WRITE_FORBIDDEN_ACTIONS: tuple[str, ...] = (
    "server-side-save",
    "signing",
    "presentation",
    "payment",
    "amendment",
    "cancellation",
    "document-submission",
    "declaration-submission",
)
