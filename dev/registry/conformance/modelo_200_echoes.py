"""Official Modelo 200 cells that repeat an amount from another sheet."""

from __future__ import annotations

# Cells that print another sheet's box number because they repeat that box's
# amount. Each design line names the echo itself: a detail sheet's total
# "aplicado en esta liquidación" (or "importe aplicado", "reducción B.I.
# aplicada", "importe adicionado"), the nivelación detail's current-generation minoración, the DID summary's
# "Liquidación - Base imponible / Cuota íntegra", and the AIE/UTE datos
# económicos base imponible before and after nivelación.
MODELO_200_ECHO_CELLS: frozenset[tuple[str, str]] = frozenset(
    {
        ("DP200008", "DP200012:00500"),
        ("DP200009", "DP200012:00500"),
        ("DP200015", "DP200014:00547"),
        ("DP200015", "DP200014:01887"),
        ("DP200015", "DP200014:01890"),
        ("DP200015B", "DP200014:00570"),
        ("DP200015B", "DP200014:00572"),
        ("DP200015B", "DP200014:01280"),
        ("DP200015B", "DP200014:01344"),
        ("DP200016", "DP200014:00571"),
        ("DP200016", "DP200014:00573"),
        ("DP200016", "DP200014B:00584"),
        ("DP200016", "DP200014B:00585"),
        ("DP200016B", "DP200014B:00590"),
        ("DP200018B", "DP200014B:01039"),
        ("DP200018B", "DP200014B:01319"),
        ("DP200018B", "DP200014B:01892"),
        ("DP200018B", "DP200014B:02314"),
        ("DP200018B", "DP200014B:02315"),
        ("DP200018C", "DP200014B:00565"),
        ("DP200019", "DP200014B:00082"),
        ("DP200019", "DP200014B:01040"),
        ("DP200019", "DP200014B:01041"),
        ("DP200019", "DP200014B:01234"),
        ("DP200020B", "DP200013:00417"),
        ("DP200020B", "DP200013:00418"),
        ("DP200020B", "DP200014:01032"),
        ("DP200020B", "DP200014:01033"),
        ("DP200020B", "DP200014:01034"),
        ("DP200022", "DP200014:00561"),
        ("DP200024", "DP200014:00552"),
        ("DP200024", "DP200014:01330"),
        ("DP200DID", "DP200014:00552"),
        ("DP200DID", "DP200014:00562"),
        ("DP200DID", "DP200014B:00621"),
        ("DP200DID", "DP200014B:01586"),
        ("DP200DID", "DP200014B:02489"),
        ("DP200DID", "DP200015:02490"),
        ("DP200DID", "DP200015:02493"),
        ("DP200DID", "DP200015:03318"),
    }
)
