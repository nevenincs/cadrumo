# DP30300

 | Agencia Tributaria
Modelo 303
versión 2.1 |  | Diseño de registro
 |  | Impuesto sobre el Valor Añadido
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Constante. |  | "<T"
2 | 3 | 3 | An | Modelo |  | "303"
3 | 6 | 1 | An | Constante. |  | "0"
4 | 7 | 4 | An | Ejercicio devengo. (AAAA)
5 | 11 | 2 | An | Período. (PP) |  | "01"..."12" o "1T"…"4T"
6 | 13 | 5 | An | Constante. |  | "0000>"
7 | 18 | 5 | An | Constante |  | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
9 | 93 | 4 | An | Versión del Programa (Nota 2)
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
11 | 101 | 9 | An | NIF Empresa Desarrollo (Nota 2)
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
13 | 323 | 6 | An | Constante |  | "</AUX>"
14 | 329 | 8 | An | Constante |  | "<VECTOR>"
15 | 337 | 300 | An | Se utilizarn 3 posiciones para la página y 4 para indicar el número de ocurrencias de ésta. Ej.<VECTOR>00100030020030....</VECTOR> |  | Nota 1
16 | 637 | 9 | An | Constante |  | "</VECTOR>"
17 | 646 | Variable | An | Contenido del fichero.  Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
18 | *** | 18 | An | Constante. </T3030+Ejercicio+periodo+0000> |  | "</T3030AAAAPP0000>"
19 | *** | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total |  | Variable
Nota 1
Vector de páginas. Se utilizarán 3 posiciones para la página y 4 para indicar el número de ocurrencias de ésta.
Después de la última página se pondrá el dentificador "FIN".
Por ejemplo, en un fichero que contenga una página 1, tres páginas 2 y una página 3 debería rellenarse el vector
con el siguiente contenido:001000100200030030001FIN (y el resto a blancos hasta completar las 300 posiciones)
Por ejemplo, en un fichero que contenga una página 1, ninguna página 2 y una página 3 debería rellenarse el vector
con el siguiente contenido:00100010030001FIN (y el resto a blancos hasta completar 300 posiciones).
Nota 2 | A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
Nota 3
El número máximo de ocurrencias de la página 2 son 6 para las actividades del régimen agrícolas, ganaderas y forestales; y 6 para las actividades
del régimen simplificado(excepto agrícolas, ganaderas y forestales). Por lo que el número máximo de páginas 2 será 3.

# DP30301

 | Agencia Tributaria
Modelo 303 |  | Diseño de registro.
 |  | Impuesto sobre el Valor Añadido
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | Obligatorio | Constante "<T"
2 | 3 | 3 | Num | Modelo. | Obligatorio | Constante "303"
3 | 6 | 2 | Num | Página. | Obligatorio | Constante "01"
4 | 8 | 1 | An | Fin de identificador de modelo. | Obligatorio | Constante ">"
5 | 9 | 1 | A | Tipo Declaración | Obligatorio PI | Nota 1
6 | 10 | 9 | An | Identificación (1) - NIF | Obligatorio
7 | 19 | 30 | An | Identificación (1) - Apellidos o Razón Social | Obligatorio
8 | 49 | 15 | A | Identificación (1) - Nombre | Obligatorio P.F.
9 | 64 | 1 | Num | Identificación (1) - Inscrito en el Registro de devolución mensual (Art. 30 RIVA) |  | "1" SI, "2" NO
10 | 65 | 1 | Num | Identificación (1) - Tributa exclusivamente en régimen simplificado |  | "1" SI, "2" NO
11 | 66 | 1 | Num | Identificación (1) - Autoliquidación conjunta |  | "1" SI, "2" NO
12 | 67 | 1 | Num | Identificación (1) - Declarado en concurso de acreedores en el presente período de liquidación |  | "1" SI, "2" NO
13 | 68 | 8 | An | Identificación (1) - Fecha en que se dictó el auto de declaración de concurso
14 | 76 | 1 | An | Identificación (1) - Auto de declaración de concurso dictado en el período |  | blanco NO,"1" SI Preconcursal, 
"2" SI Postconcursal
15 | 77 | 1 | Num | Identificación (1) - Opción por el régimen especial de criterio de Caja |  | "1" SI, "2" NO
16 | 78 | 1 | Num | Identificación (1) - Destinatario de las operaciones a las que se aplique el régimen especial del criterio de Caja |  | "1" SI, "2" NO
17 | 79 | 1 | Num | Identificación (1) - Opción por la aplicación de la prorrata especial |  | "1" SI, "2" NO
18 | 80 | 1 | Num | Identificación (1) - Revocación de la opción por la aplicación de la prorrata especial |  | "1" SI, "2" NO
19 | 81 | 4 | Num | Devengo (2) - Ejercicio | Obligatorio
20 | 85 | 2 | An | Devengo (2) - Período | Obligatorio | "01",..., "12" o "1T" … "4T"
21 | 87 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Base imponible [01] |  | 15 enteros y 2 decimales
22 | 104 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Tipo % [02] |  | 3 enteros y 2 decimales
23 | 109 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Cuota [03] |  | 15 enteros y 2 decimales
24 | 126 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Base imponible [04] |  | 15 enteros y 2 decimales
25 | 143 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Tipo % [05] |  | 3 enteros y 2 decimales
26 | 148 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Cuota [06] |  | 15 enteros y 2 decimales
27 | 165 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Base imponible [07] |  | 15 enteros y 2 decimales
28 | 182 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Tipo % [08] |  | 3 enteros y 2 decimales
29 | 187 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Cuota [09] |  | 15 enteros y 2 decimales
30 | 204 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Adquisiciones intracomunitarias de bienes y servicios - Base imponible  [10] |  | 15 enteros y 2 decimales
31 | 221 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Adquisiciones intracomunitarias de bienes y servicios - Cuota [11] |  | 15 enteros y 2 decimales
32 | 238 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Otras operaciones con inversión del sujeto pasivo (excepto. adq. intracom) - Base imponible  [12] |  | 15 enteros y 2 decimales
33 | 255 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Otras operaciones con inversión del sujeto pasivo (excepto. adq. intracom) - Cuota [13] |  | 15 enteros y 2 decimales
34 | 272 | 17 | N | Liquidación (3) - Regimen General - IVA Devengado - Modificación bases y cuotas- Base imponible  [14] |  | 15 enteros y 2 decimales
35 | 289 | 17 | N | Liquidación (3) - Regimen General - IVA Devengado - Modificación bases y cuotas - Cuota [15] |  | 15 enteros y 2 decimales
36 | 306 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia- Base imponible [16] |  | 15 enteros y 2 decimales
37 | 323 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Tipo % [17] |  | 3 enteros y 2 decimales
38 | 328 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Cuota [18] |  | 15 enteros y 2 decimales
39 | 345 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Base imponible [19] |  | 15 enteros y 2 decimales
40 | 362 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Tipo % [20] |  | 3 enteros y 2 decimales
41 | 367 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Cuota [21] |  | 15 enteros y 2 decimales
42 | 384 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Base imponible [22] |  | 15 enteros y 2 decimales
43 | 401 | 5 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Tipo % [23] |  | 3 enteros y 2 decimales
44 | 406 | 17 | Num | Liquidación (3) - Regimen General - IVA Devengado - Recargo equivalencia - Cuota [24] |  | 15 enteros y 2 decimales
45 | 423 | 17 | N | Liquidación (3) - Regimen General - IVA Devengado - Modificaciones bases y cuotas del recargo de equivalencia - Base imponible [25] |  | 15 enteros y 2 decimales
46 | 440 | 17 | N | Liquidación (3) - Regimen General - IVA Devengado - Modificaciones bases y cuotas del recargo de equivalencia - Cuota [26] |  | 15 enteros y 2 decimales
47 | 457 | 17 | N | Liquidación (3) - Regimen General - IVA Devengado - Total cuota devengada ( [03] + [06] + [09] + [11] + [13] + [15] + [18] + [21] + [24] + [26]) [27] |  | 15 enteros y 2 decimales
48 | 474 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en operaciones interiores corrientes - Base [28] |  | 15 enteros y 2 decimales
49 | 491 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en operaciones interiores corrientes - Cuota [29] |  | 15 enteros y 2 decimales
50 | 508 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en operaciones interiores con bienes de inversión - Base [30] |  | 15 enteros y 2 decimales
51 | 525 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible - Por cuotas soportadas en operaciones interiores con bienes de inversión - Cuota [31] |  | 15 enteros y 2 decimales
52 | 542 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible -Por cuotas soportadas en las importaciones de bienes corrientes - Base [32] |  | 15 enteros y 2 decimales
53 | 559 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible -Por cuotas soportadas en las importaciones de bienes corrientes - Cuota [33] |  | 15 enteros y 2 decimales
54 | 576 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible -Por cuotas soportadas en las importaciones de bienes de inversión - Base [34] |  | 15 enteros y 2 decimales
55 | 593 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible -Por cuotas soportadas en las importaciones de bienes de inversión - Cuota [35] |  | 15 enteros y 2 decimales
56 | 610 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible -En adquisiciones intracomunitarias de bienes y servicios corrientes - Base [36] |  | 15 enteros y 2 decimales
57 | 627 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible -En adquisiciones intracomunitarias de bienes y servicios corrientes - Cuota [37] |  | 15 enteros y 2 decimales
58 | 644 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible -En adquisiciones intracomunitarias de bienes de inversión - Base [38] |  | 15 enteros y 2 decimales
59 | 661 | 17 | Num | Liquidación (3) - Regimen General - IVA Deducible -En adquisiciones intracomunitarias de bienes de inversión - Cuota [39] |  | 15 enteros y 2 decimales
60 | 678 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible -Rectificación de deducciones - Base [40] |  | 15 enteros y 2 decimales
61 | 695 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible -Rectificación de deducciones - Cuota [41] |  | 15 enteros y 2 decimales
62 | 712 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Compensaciones Régimen Especial A.G. y P. - Cuota [42] |  | 15 enteros y 2 decimales
63 | 729 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Regularización inversiones - Cuota [43] |  | 15 enteros y 2 decimales
64 | 746 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Regularización por aplicación del porcentaje definitivo de prorrata - Cuota [44] |  | 15 enteros y 2 decimales
65 | 763 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible - Total a deducir ( [29] + [31] + [33] + [35] + [37] + [39] + [41] + [42] + [43] + [44] ) - Cuota [45] |  | 15 enteros y 2 decimales
66 | 780 | 17 | N | Liquidación (3) - Regimen General - IVA Deducible -Resultado régimen general ( [27] - [45] ) - Cuota [46] |  | 15 enteros y 2 decimales
67 | 797 | 80 | An | Reservado para la AEAT
68 | 877 | 13 | An | Reservado para la AEAT - Sello electrónico reservado para la AEAT
69 | 890 | 9 | An | Indicador de fin de registro | Obligatorio | Constante "</T30301>"
70 | 899 | 2 | An | Fin de Registro. Constante CRLF (Hexadecimal 0D0A, Decimal 1310)
TOTAL |  | 900 | POSICIONES
Nota 1:
 | El uso MI significa que sólo se tiene en cuenta en el módulo de impresión y el uso PI significa que sólo tiene utilidad en las presentaciones por Internet.
 | PI :El tipo de declaración puede ser: C (solicitud de compensación) D (devolución) G (cuenta corriente tributaria-ingreso) I (ingreso) N (sin actividad/resultado cero) V (cuenta corriente tributaria -devolución)
 | U (domiciliacion del ingreso en CCC)
 | MI: En caso de declaración Sin Actividad (resultado cero) consígnese "N". En el caso contrario se considerará válido cualquier otro carácter alfanumérico
Nota 2:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izqda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.

# DP30302

 | Agencia Tributaria
Modelo 303 |  | Diseño de registro.
 |  | Impuesto sobre el Valor Añadido
Nº | Posic. | Lon | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página. | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo. | Obligatorio | Constante "303"
3 | 6 | 2 | Num |  | Página. | Obligatorio | Constante "02"
4 | 8 | 1 | An |  | Fin de identificador de modelo. | Obligatorio | Constante ">"
5 | 9 | 1 | A | C | Indicador de página complementaria. Blanco (No complementaria) o "C" (Complementaria) |  | Nota 1
6 | 10 | 2 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - Código
7 | 12 | 17 | N | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - Volumen de ingresos |  | 15 enteros y 2 decimales
8 | 29 | 6 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - Indice de cuota |  | 1 entero y 5 decimales
9 | 35 | 17 | N | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - Cuota devengada |  | 15 enteros y 2 decimales
10 | 52 | 5 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - 1T/2T/3T - Porcentaje trimestral |  | 3 enteros y 2 decimales
11 | 57 | 17 | N | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - 1T/2T/3T - Ingreso a cuenta [A] |  | 15 enteros y 2 decimales
12 | 74 | 17 | N | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 - 4T - Cuota soportada |  | 15 enteros y 2 decimales
13 | 91 | 17 | N | C | Liquidación (3) - RS- (A) Actividades agrícolas, ganaderas y forestales - Actividad 1 
- 4T - Cuota anual derivada del regimen simplificado [B] |  | 15 enteros y 2 decimales
14 | 108 | 4 | An | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1- Epigrafe IAE
15 | 112 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 1 - Nº Unidades |  | 8 enteros y 2 decimales
16 | 122 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 1 - Importe |  | 15 enteros y 2 decimales
17 | 139 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 2 - Nº Unidades |  | 8 enteros y 2 decimales
18 | 149 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 2 - Importe |  | 15 enteros y 2 decimales
19 | 166 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 3 - Nº Unidades |  | 8 enteros y 2 decimales
20 | 176 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 3 - Importe |  | 15 enteros y 2 decimales
21 | 193 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 4 - Nº Unidades |  | 8 enteros y 2 decimales
22 | 203 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 4 - Importe |  | 15 enteros y 2 decimales
23 | 220 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 5 - Nº Unidades |  | 8 enteros y 2 decimales
24 | 230 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 5 - Importe |  | 15 enteros y 2 decimales
25 | 247 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 6 - Nº Unidades |  | 8 enteros y 2 decimales
26 | 257 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 6 - Importe |  | 15 enteros y 2 decimales
27 | 274 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 7 - Nº Unidades |  | 8 enteros y 2 decimales
28 | 284 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Módulo 7 - Importe |  | 15 enteros y 2 decimales
29 | 301 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Cuota devengada operaciones corrientes [C] |  | 15 enteros y 2 decimales
30 | 318 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Reducciones [D] |  | 15 enteros y 2 decimales
31 | 335 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 1T/2T/3T - Indice corrector activ. de temporada [Z] |  | 1 entero y 2 decimales
32 | 338 | 5 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 1T/2T/3T - Porcentaje ingreso a cuenta [E] |  | 3 enteros y 2 decimales
33 | 343 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 1T/2T/3T - Ingreso a cuenta ( ([C] - [D] ) x [E]) [F] |  | 15 enteros y 2 decimales
34 | 360 | 2 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - Código
35 | 362 | 17 | N | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - Volumen de ingresos |  | 15 enteros y 2 decimales
36 | 379 | 6 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - Indices de cuota |  | 1 entero y 5 decimales
37 | 385 | 17 | N | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - Cuota devengada |  | 15 enteros y 2 decimales
38 | 402 | 5 | Num | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - 1T/2T/3T - Porcentaje trimestral |  | 3 enteros y 2 decimales
39 | 407 | 17 | N | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - 1T/2T/3T - Ingreso a cuenta [A] |  | 15 enteros y 2 decimales
40 | 424 | 17 | N | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - 4T - Cuota soportada |  | 15 enteros y 2 decimales
41 | 441 | 17 | N | C | Liquidación (3) - RS - (A) Actividades agrícolas, ganaderas y forestales - Actividad 2 - 4T 
- Cuota anual derivada del regimen simplificado [B] |  | 15 enteros y 2 decimales
42 | 458 | 4 | An | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2- Epigrafe IAE
43 | 462 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 1 - Nº Unidades |  | 8 enteros y 2 decimales
44 | 472 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 1 - Importe |  | 15 enteros y 2 decimales
45 | 489 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 2 - Nº Unidades |  | 8 enteros y 2 decimales
46 | 499 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 2 - Importe |  | 15 enteros y 2 decimales
47 | 516 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 3 - Nº Unidades |  | 8 enteros y 2 decimales
48 | 526 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 3 - Importe |  | 15 enteros y 2 decimales
49 | 543 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 4 - Nº Unidades |  | 8 enteros y 2 decimales
50 | 553 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 4 - Importe |  | 15 enteros y 2 decimales
51 | 570 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 5 - Nº Unidades |  | 8 enteros y 2 decimales
52 | 580 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 5 - Importe |  | 15 enteros y 2 decimales
53 | 597 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 6 - Nº Unidades |  | 8 enteros y 2 decimales
54 | 607 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 6 - Importe |  | 15 enteros y 2 decimales
55 | 624 | 10 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 7 - Nº Unidades |  | 8 enteros y 2 decimales
56 | 634 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Módulo 7 - Importe |  | 15 enteros y 2 decimales
57 | 651 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Cuota devengada operaciones corrientes [C] |  | 15 enteros y 2 decimales
58 | 668 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - Reducciones [D] |  | 15 enteros y 2 decimales
59 | 685 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 1T/2T/3T - Indice corrector activ. de temporada [Z] |  | 1 entero y 2 decimales
60 | 688 | 5 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 1T/2T/3T - Porcentaje ingreso a cuenta [E] |  | 3 enteros y 2 decimales
61 | 693 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 1T/2T/3T - Ingreso a cuenta ( ([C] - [D] ) x [E]) [F] |  | 15 enteros y 2 decimales
62 | 710 | 17 | Num |  | Liquidación (3) - RS - (B) Actividades en RS - 1T/2T/3T
 - Suma de ingresos a cuenta del conjunto de actividades (A1 + A2 + A3 + … + F1 + F2 + F3 + ...) [47] |  | 15 enteros y 2 decimales
63 | 727 | 17 | N | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 4T - Cuotas soportadas operaciones corrientes [G] |  | 15 enteros y 2 decimales
64 | 744 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 4T - Índice corrector 
de actividades de temporada [H] |  | 1 entero y 2 decimales
65 | 747 | 17 | N | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 4T - RESULTADO (( [C] - [D] - [G] ) x [H]) [I] |  | 15 enteros y 2 decimales
66 | 764 | 5 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 4T - Porcentaje cuota mínima [J] |  | 3 enteros y 2 decimales
67 | 769 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 4T - Devolución cuotas soportadas otros países [K] |  | 15 enteros y 2 decimales
68 | 786 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 4T - Cuota mínima [L] |  | 15 enteros y 2 decimales
69 | 803 | 17 | N | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - 4T - Cuota anual derivada RS [M] |  | 15 enteros y 2 decimales
70 | 820 | 17 | N | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 4T - Cuotas soportadas operaciones corrientes [G] |  | 15 enteros y 2 decimales
71 | 837 | 3 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 4T - Índice corrector de actividades de temporada [H] |  | 1 entero y 2 decimales
72 | 840 | 17 | N | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 4T - RESULTADO (( [C] - [D] - [G] ) x [H]) [I] |  | 15 enteros y 2 decimales
73 | 857 | 5 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 4T - Porcentaje cuota mínima [J] |  | 3 enteros y 2 decimales
74 | 862 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 4T - Devolución cuotas soportadas otros países [K] |  | 15 enteros y 2 decimales
75 | 879 | 17 | Num | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 4T - Cuota mínima [L] |  | 15 enteros y 2 decimales
76 | 896 | 17 | N | C | Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 2 - 4T - Cuota anual derivada RS [M] |  | 15 enteros y 2 decimales
77 | 913 | 17 | N |  | Liquidación (3) - RS - (A+B) Actividades en RS - 4T 
- Suma de cuotas derivadas RS del conjunto de actividades ( B1 + B2 + ... + M1 + M2 + ... ) [48] |  | 15 enteros y 2 decimales
78 | 930 | 17 | Num |  | Liquidación (3) - RS - (A+B) Actividades en RS - 4T 
- Suma de ingresos a cuenta realizados en el ejercicio [49] |  | 15 enteros y 2 decimales
79 | 947 | 17 | N |  | Liquidación (3) - RS - (A+B) Actividades en RS - 4T - Resultado ( [48] - [49] ) [50] |  | 15 enteros y 2 decimales
80 | 964 | 17 | N |  | Liquidación (3) - RS - Cuotas devengadas - Adquisiciones intracomunitarias de bienes [51] |  | 15 enteros y 2 decimales
81 | 981 | 17 | N |  | Liquidación (3) - RS - Cuotas devengadas - Entregas de activos fijos [52] |  | 15 enteros y 2 decimales
82 | 998 | 17 | N |  | Liquidación (3) - RS - Cuotas devengadas - IVA devengado por inversión del sujeto pasivo [53] |  | 15 enteros y 2 decimales
83 | 1015 | 17 | N |  | Liquidación (3) - RS - Cuotas devengadas - Total cuota resultante
Si 1T, 2T, 3T: ( [47] + [51] + [52] + [53] ) [54]
Si 4T: ( [50] + [51] + [52] + [53] ) [54] |  | 15 enteros y 2 decimales
84 | 1032 | 17 | N |  | Liquidación (3) - RS - IVA deducible - Adquisición o importación de activos fijos [55] |  | 15 enteros y 2 decimales
85 | 1049 | 17 | N |  | Liquidación (3) - RS - IVA deducible - Regularización bienes de inversión [56] |  | 15 enteros y 2 decimales
86 | 1066 | 17 | N |  | Liquidación (3) - RS - IVA deducible - Total IVA deducible ( [55] + [56] ) [57] |  | 15 enteros y 2 decimales
87 | 1083 | 17 | N |  | Liquidación (3) - RS - Resultado RS ( [54] - [57] ) [58] |  | 15 enteros y 2 decimales
88 | 1100 | 90 | An |  | Reservado para la AEAT
89 | 1190 | 9 | An |  | Indicador de fin de registro | Obligatorio | Constante "</T30302>"
90 | 1199 | 2 | An |  | Fin de Registro. Constante CRLF (Hexadecimal 0D0A, Decimal 1310)
TOTAL |  | 1200 | POSICIONES
Nota 1:
El campo indicador de página complementaria se cumplimentará cuando en el fichero van más de una página del mismo tipo.
La C de la columna Comp indica los campos que pueden tener contenido en las páginas complementarias
Nota 2:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izqda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
Nota abreviaturas:
RS - Régimen Simplificado
exc. - excepto
inc. - incluido
a, g y f - agrícolas, ganaderas y forestales

# DP30303

 | Agencia Tributaria
Modelo 303 |  | Diseño de registro.
 |  | Impuesto sobre el Valor Añadido
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | Obligatorio | Constante "<T"
2 | 3 | 3 | Num | Modelo. | Obligatorio | Constante "303"
3 | 6 | 2 | Num | Página. | Obligatorio | Constante "03"
4 | 8 | 1 | An | Fin de identificador de modelo. | Obligatorio | Constante ">"
5 | 9 | 17 | N | Información adicional - Entregas intracomunitarias de bienes y servicios [59] |  | 15 enteros y 2 decimales
6 | 26 | 17 | N | Información adicional - Exportaciones y operaciones asimiladas [60] |  | 15 enteros y 2 decimales
7 | 43 | 17 | N | Información adicional - Operaciones no sujetas o con inversión del sujeto pasivo que originan el derecho a deducción [61] |  | 15 enteros y 2 decimales
8 | 60 | 17 | N | Resultado - Suma de resultados ( [46] + [58] + [76] ) [64] |  | 15 enteros y 2 decimales
9 | 77 | 5 | Num | Resultado - % Atribuible a la Administración del Estado [65] |  | 3 enteros y 2 decimales
10 | 82 | 17 | N | Resultado - Atribuible a la Administración del Estado [66] |  | 15 enteros y 2 decimales
11 | 99 | 17 | Num | Resultado - Cuotas a compensar de periodos anteriores [67] |  | 15 enteros y 2 decimales
12 | 116 | 17 | N | Resultado - Exclusivamente para sujetos pasivos que tributan conjuntamente a la Administración del Estado y a las Diputaciones Forales Resultado de la regularización anual [68] |  | 15 enteros y 2 decimales
13 | 133 | 17 | N | Resultado - Resultado ( [66] + [77] - [67] ± [68] ) [69] |  | 15 enteros y 2 decimales
14 | 150 | 17 | N | Resultado - A deducir [70] |  | 15 enteros y 2 decimales
15 | 167 | 17 | N | Resultado - Resultado de la liquidación ( [69] - [70] ) [71] |  | 15 enteros y 2 decimales
16 | 184 | 17 | N | Información adicional - Exclusivamente para operaciones de entrega de bienes y prestaciones de servicios
a las que resulte de aplicación el régimen especial del criterio de Caja.
Importes devengados en período de liquidación según art. 75 LIVA. - Base Imponible [62] |  | 15 enteros y 2 decimales
17 | 201 | 17 | N | Información adicional - Exclusivamente para operaciones de entrega de bienes y prestaciones de servicios
a las que resulte de aplicación el régimen especial del criterio de Caja.
Importes devengados en período de liquidación según art. 75 LIVA. - Cuota [63] |  | 15 enteros y 2 decimales
18 | 218 | 17 | N | Información adicional - Exclusivamente para operaciones de entrega de bienes y prestaciones de servicios
a las que resulte de aplicación el régimen especial del criterio de Caja.
Cuotas de IVA soportados en operaciones que tributen por el régimen especial del criterio de caja
conforme a la regla general de devengo contenida en el artículo 75 LIVA. - Base Imponible [74] |  | 15 enteros y 2 decimales
19 | 235 | 17 | N | Información adicional - Exclusivamente para operaciones de entrega de bienes y prestaciones de servicios
a las que resulte de aplicación el régimen especial del criterio de Caja.
Cuotas totales de IVA soportados en operaciones que tributen por el régimen especial del criterio de caja
conforme a la regla general de devengo contenida en el artículo 75 de LIVA. - Cuota [75] |  | 15 enteros y 2 decimales
20 | 252 | 1 | An | Declaración complementaria |  | X o blanco
21 | 253 | 13 | An | Número justificante declaración anterior
22 | 266 | 1 | An | Declaración Sin actividad |  | X o blanco
23 | 267 | 34 | An | Domiciliación/Devolución - IBAN |  | nota 6.
24 | 301 | 1 | Num | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resúmen anual de IVA: B - Clave - Principal |  | Nota 1
25 | 302 | 4 | An | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resúmen anual de IVA: C - Epígrafe IAE - Principal |  | Nota 1
26 | 306 | 1 | Num | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resúmen anual de IVA: B - Clave - Otras - 1ª |  | Nota 1
27 | 307 | 4 | An | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resúmen anual de IVA: C - Epígrafe IAE - Otras - 1ª |  | Nota 1
28 | 311 | 1 | Num | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resúmen anual de IVA: B - Clave - Otras - 2ª |  | Nota 1
29 | 312 | 4 | An | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resúmen anual de IVA: C - Epígrafe IAE - Otras - 2ª |  | Nota 1
30 | 316 | 1 | Num | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resúmen anual de IVA: B - Clave - Otras - 3ª |  | Nota 1
31 | 317 | 4 | An | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resúmen anual de IVA: C - Epígrafe IAE - Otras - 3ª |  | Nota 1
32 | 321 | 1 | Num | Información adicional - Exclusivamente a cumplimentar en el último periodo
exonerados de la Declaración-resúmen anual de IVA: B - Clave - Otras - 4ª |  | Nota 1
33 | 322 | 4 | An | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resúmen anual de IVA: C - Epígrafe IAE - Otras - 4ª |  | Nota 1
34 | 326 | 1 | Num | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resúmen anual de IVA: B - Clave - Otras - 5ª |  | Nota 1
35 | 327 | 4 | An | Información adicional - Exclusivamente a cumplimentar en el último periodo 
exonerados de la Declaración-resúmen anual de IVA: C - Epígrafe IAE - Otras - 5ª |  | Nota 1
36 | 331 | 1 | An | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resúmen anual de IVA: 
D - Marque si ha efectuado operaciones por las que tenga obligación de presentar la declaración anual de operaciones 
con terceras personas. |  | X o blanco
37 | 332 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resúmen anual de IVA - Operaciones realizadas en el ejercicio - Operaciones en régimen general [80] |  | 15 enteros y 2 decimales
38 | 349 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resúmen anual de IVA - Operaciones realizadas en el ejercicio - Operaciones en régimen especial del criterio de caja conforme art. 75 LIVA [81] |  | 15 enteros y 2 decimales
39 | 366 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resúmen anual de IVA - Operaciones realizadas en el ejercicio - Exportaciones, entregas intracomunitarias  y otras operaciones con derecho a deducción [82] |  | 15 enteros y 2 decimales
40 | 383 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resúmen anual de IVA - Operaciones realizadas en el ejercicio - Operaciones exentas sin derecho a deducción [83] |  | 15 enteros y 2 decimales
41 | 400 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resúmen anual de IVA - Operaciones realizadas en el ejercicio - Operaciones no sujetas por reglas de localización o con inversión del sujeto pasivo [84] |  | 15 enteros y 2 decimales
42 | 417 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resúmen anual de IVA - Operaciones realizadas en el ejercicio - Entregas de bienes objeto de instalación o montaje en otros Estados miembros [85] |  | 15 enteros y 2 decimales
43 | 434 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resúmen anual de IVA - Operaciones realizadas en el ejercicio - Operaciones en régimen simplificado [86] |  | 15 enteros y 2 decimales
44 | 451 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resúmen anual de IVA - Operaciones realizadas en el ejercicio - Entregas de bienes inmuebles y de inversión y operaciones financieras no habituales  [87] |  | 15 enteros y 2 decimales
45 | 468 | 17 | N | Información adicional - Exclusivamente a cumplimentar en el último periodo exonerados de la Declaración-resúmen anual de IVA - Operaciones realizadas en el ejercicio - Total volumen de operaciones ([80]+[81]+[82]+[83]+[84]+[85]+[86] - [87]) [88] |  | 15 enteros y 2 decimales
46 | 485 | 17 | N | Resultado - Regualarización cuotas art. 80.cinco.5ª LIVA  [76] RESERVADO EN DECLARACIONES EJERCICIO 2014 |  | 15 enteros y 2 decimales
47 | 502 | 17 | N | Resultado - IVA a la importación liquidado por la Aduana pendiente de ingreso  [77] RESERVADO EN DECLARACIONES EJERCICIO 2014 |  | 15 enteros y 2 decimales
48 | 519 | 71 | An | Reservado para la AEAT
49 | 590 | 9 | An | Indicador de fin de registro | Obligatorio | Constante "</T30303>"
50 | 599 | 2 | An | Fin de Registro. Constante CRLF (Hexadecimal 0D0A, Decimal 1310)
TOTAL |  | 600 | POSICIONES
Nota 1:
Las casillas B (Clave) y C (Epígrafe IAE) podrán tomar los siguientes valores:
B | C
1 | Epígrafes correspondientes a: Actividades en régimen simplificado excepto las agrícolas, ganaderas y pesqueras (AGP)
1 | Epígrafes correspondientes a: Actividades AGP con IAE
3 | Epígrafe 861.1 correspondiente a: Alquiler de viviendas.
3 | Epígrafe 861.2 corresondiente a: Alquiler de locales industriales.
4 | Sin epígrafe, correspondiente a: Actividades AGP, no sujetas al IAE
Nota 2:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izqda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
6. Para el IBAN español deberá empezar por ES y únicamente se usan las primeras 24 posiciones.
Nota 3:
Este Diseño de Registro, que se ha modificado para incluir información que debe declararse en el 4T, debe no obstante ser utilizado para presentaciones de todos
los periodos de 2014 realizadas a partir del 1 de enero de 2015 (4T, 12 y extemporáneas del resto de periodos).
Por lo tanto, los nuevos campos numéricos deberán cumplimentarse con ceros para estas presentaciones extemporáneas del resto de periodos.