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
        # The aeat-dr-200-2022 design prints the liquidación blocks one record earlier,
        # so its echoes repeat the 2022 ids; each row cites its design field, its line in
        # the extracted design and the closing words of its caption.
        # DP200015 field 85, line 1666: TOTAL - Aplicado en esta liquidación [00547]
        ("DP200015", "DP200013:00547"),
        # DP200015 field 102, line 1683: Aplicado en esta liquidación [01887]
        ("DP200015", "DP200013:01887"),
        # DP200015 field 105, line 1686: Aplicado en esta liquidación [01890]
        ("DP200015", "DP200013:01890"),
        # DP200016 field 134, line 2000: Deducciones DT 24ª.1 LIS - Total - Aplicado en esta liquidación [00584]
        ("DP200016", "DP200014:00584"),
        # DP200016 field 111, line 1977: Aplicado en esta liquidación [00585]
        ("DP200016", "DP200014:00585"),
        # DP200016B field 144, line 2155: Total - Aplicado en esta liquidación [00590]
        ("DP200016B", "DP200014:00590"),
        # DP200018B field 106, line 2664: Total - Aplicado en esta liquidación [01039]
        ("DP200018B", "DP200014:01039"),
        # DP200018B field 146, line 2704: Total - Aplicado en esta liquidación [02314]
        ("DP200018B", "DP200014:02314"),
        # DP200018B field 67, line 2625: Total - Aplicado en esta liquidación [02315]
        ("DP200018B", "DP200014:02315"),
        # DP200018C field 155, line 2871: Aplicado en esta liquidación [00565]
        ("DP200018C", "DP200014:00565"),
        # DP200019 field 198, line 3081: Total - Aumentos [00417]
        ("DP200019", "DP200013:00417"),
        # DP200019 field 199, line 3082: Total - Disminuciones [00418]
        ("DP200019", "DP200013:00418"),
        # DP200019 field 188, line 3071: Total - Aplicado en esta liquidación [00082]
        ("DP200019", "DP200014:00082"),
        # DP200019 field 44, line 2927: Total - Importe aplicado [01040]
        ("DP200019", "DP200014:01040"),
        # DP200019 field 84, line 2967: Total - Importe aplicado [01041]
        ("DP200019", "DP200014:01041"),
        # DP200020B field 18, line 3230: Reserva Capitalización - Total - Reducción B.I. aplicada [01032]
        ("DP200020B", "DP200013:01032"),
        # DP200020B field 47, line 3259: Total - Importe adicionado base imponible en periodo [01033]
        ("DP200020B", "DP200013:01033"),
        # DP200020B field 44, line 3256: Importe minoración B.I. periodo/pendiente adicionar inicio periodo [01034]
        ("DP200020B", "DP200013:01034"),
        # DP200024 field 10, line 3835: Modelo de información - Base imponible [00552]
        ("DP200024", "DP200013:00552"),
        # DP200DID field 18, line 6865: Liquidación - Base imponible [00552]
        ("DP200DID", "DP200013:00552"),
        # DP200DID field 33, line 6880: Resultado de conversión de AID tras regularización: Compensación [02490]
        ("DP200DID", "DP200014B:02490"),
        # DP200DID field 34, line 6881: Resultado de conversión de AID tras regularización: A ingresar [02493]
        ("DP200DID", "DP200014B:02493"),
        # DP200DID field 32, line 6879: Resultado de conversión de AID tras regularización: Abono [03318]
        ("DP200DID", "DP200014B:03318"),
    }
)
