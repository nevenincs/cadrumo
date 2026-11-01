"""Modelo 200 casilla identifiers shared by the base-determination, cuota-integra and tipo-gravamen tests."""

from __future__ import annotations

from .....core.casilla_id import CasillaId, validated_casilla_id

M200_RESULTADO_CONTABLE_CASILLA: CasillaId = validated_casilla_id(
    "DP200012:00501", surface="M200_RESULTADO_CONTABLE_CASILLA"
)
M200_CORRECCIONES_AUMENTO_CASILLA: CasillaId = validated_casilla_id(
    "DP200013:00417",
    surface="M200_CORRECCIONES_AUMENTO_CASILLA",
)
M200_CORRECCIONES_DISMINUCION_CASILLA: CasillaId = validated_casilla_id(
    "DP200013:00418",
    surface="M200_CORRECCIONES_DISMINUCION_CASILLA",
)
M200_RESERVA_CAPITALIZACION_CASILLA: CasillaId = validated_casilla_id(
    "01032",
    surface="M200_RESERVA_CAPITALIZACION_CASILLA",
)
M200_BIN_APLICADA_CASILLA: CasillaId = validated_casilla_id("DP200014:00547", surface="M200_BIN_APLICADA_CASILLA")
M200_DEDUCCION_DOBLE_IMPOSICION_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:01033",
    surface="M200_DEDUCCION_DOBLE_IMPOSICION_CASILLA",
)
M200_BONIFICACIONES_CASILLA: CasillaId = validated_casilla_id("DP200014:01034", surface="M200_BONIFICACIONES_CASILLA")
M200_CUOTA_LIQUIDA_POSITIVA_CASILLA: CasillaId = validated_casilla_id(
    "DP200014B:01766",
    surface="M200_CUOTA_LIQUIDA_POSITIVA_CASILLA",
)
M200_CUOTA_LIQUIDA_NEGATIVA_CASILLA: CasillaId = validated_casilla_id(
    "DP200014B:01784",
    surface="M200_CUOTA_LIQUIDA_NEGATIVA_CASILLA",
)
M200_CUOTA_INTEGRA_CASILLA: CasillaId = validated_casilla_id("DP200014:00562", surface="M200_CUOTA_INTEGRA_CASILLA")
