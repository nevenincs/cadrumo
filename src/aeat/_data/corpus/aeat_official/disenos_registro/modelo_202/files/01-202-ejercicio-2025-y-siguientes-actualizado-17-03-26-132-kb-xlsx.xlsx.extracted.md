# dr M202 (0)

 | Agencia Tributaria
Modelo 202 |  | Diseño de registro. Castellano.
versión 1.2 |  | Impuesto sobre Sociedades. Impuesto sobre la Renta de no Residentes. Pago fraccionado
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Constante. | "<T"
2 | 3 | 3 | An | Modelo | "202"
3 | 6 | 1 | An | Constante. | "0"
4 | 7 | 4 | An | Ejercicio devengo. (AAAA)
5 | 11 | 2 | An | Período. (PP) | "1P", "2P", "3P"  o "0A"
6 | 13 | 5 | An | Constante. | "0000>"
7 | 18 | 5 | An | Constante | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos | BLANCOS
9 | 93 | 4 | An | Versión del Programa (Nota 1)
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos | BLANCOS
11 | 101 | 9 | An | NIF Empresa Desarrollo (Nota 1)
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos | BLANCOS
13 | 323 | 6 | An | Constante | "</AUX>"
14 | 329 | Variable | An | Contenido del fichero.  Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T2020+Ejercicio+periodo+0000> | "</T2020AAAAPP0000>"
Total |  | Variable
Nota 1 | A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW

# dr M202 (1)

 | Agencia Tributaria
Modelo 202 |  | Diseño de registro. Castellano.
versión 1.2 |  | Impuesto sobre Sociedades. Impuesto sobre la Renta de no Residentes. Pago fraccionado
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | Num | Modelo | Constante "202"
3 | 6 | 2 | Num | Página | Constante "01"
4 | 8 | 4 | An | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An | Reservado para la Administración | En blanco
6 | 13 | 1 | A | Tipo de declaración | (ver Nota 1)
7 | 14 | 9 | An | Identificación (1). NIF
8 | 23 | 60 | An | Identificación (1). Denominación o apellidos
9 | 83 | 20 | An | Identificación (1). Nombre
10 | 103 | 1 | An | Identificación (1) - Contribuyente sometido a normativa de Territorio Foral de Navarra, Guipúzcoa, Vizcaya o Álava | (ver Nota 9)
11 | 104 | 4 | Num | Devengo (2). Ejercicio
12 | 108 | 2 | An | Devengo (2). Periodo | "1P", "2P", "3P" o "0A"
13 | 110 | 8 | Num | Devengo (2). Fecha de inicio del período impositivo | ddmmaaaa
14 | 118 | 4 | Num | Devengo (2). C.N.A.E. actividad principal | Nota 12
15 | 122 | 1 | An | Datos adicionales (3) - Entidad que aplica el régimen de la Ley 49/2002 de 23 de diciembre | X o blanco
16 | 123 | 1 | An | Datos adicionales (3) - Entidad que aplica el régimen de la Ley 11/2009 de 26 de octubre | X o blanco
17 | 124 | 1 | An | Datos adicionales (3) - Entidad de capital-riesgo que aplica el régimen fiscal especial del art. 50 LIS | X o blanco (ver Nota 8)
18 | 125 | 1 | An | Datos adicionales (3) - Entidad que aplica el régimen de las entidades navieras en función del tonelaje | X o blanco
19 | 126 | 1 | An | Datos adicionales (3) - Entidad que cumpla los requisitos para la aplicación de los incentivos de empresa de reducida dimensión (art. 101 LIS) y apliquen el tipo de gravamen específico previsto para estas entidades | X o blanco
20 | 127 | 1 | An | Datos adicionales (3) - Importe neto de la cifra de negocios de los doce meses anteriores a la fecha de inicio del período impositivo es superior a 6.000.000 euros | X o blanco
21 | 128 | 1 | An | Datos adicionales (3) - Cooperativa fiscalmente protegida | X o blanco
22 | 129 | 1 | An | Datos adicionales (3) - Marque esta casilla si concurre ALGUNA de las siguientes circunstancias: | X o blanco (ver Nota 7)
23 | 130 | 1 | An | Datos adicionales (3) - Entidad con importe neto de la cifra de negocios del período impositivo inmediato anterior inferior a 1 millón de euros | X o blanco
24 | 131 | 1 | An | Datos adicionales (3) - Otras entidades con posibilidad de aplicar más de un tipo impositivo. | X o blanco
25 | 132 | 15 | An | Datos adicionales (3) - Tipo de gravamen del Impuesto sobre Sociedades del ejercicio en curso | Cadena alfanumérica de 15 posiciones para permitir consignar los tipos. 
(ver Nota 10)
26 | 147 | 1 | Num | Datos adicionales (3) - Importe neto de la cifra de negocios en los doce meses anteriores a la fecha de inicio del período impositivo: | "0" No consta, 
"1" (>= 10 M y < 20 M €), 
"2" (>= 20  M y < 60 M €), 
"3" (>= 60 M €)
27 | 148 | 1 | An | Liquidación de modalidad A ó B | A ó B. (ver Nota 11)
28 | 149 | 17 | Num | A) Liquidación. Mod. 40.2 LIS - Base del pago fraccionado [01] | 15 enteros + 2 decimales
29 | 166 | 17 | Num | A) Liquidación. Mod. 40.2 LIS - Resultado de la declaración anterior (complementarias) [02] | 15 enteros + 2 decimales
30 | 183 | 17 | Num | A) Liquidación. Mod. 40.2 LIS - A Ingresar [03] | 15 enteros + 2 decimales
31 | 200 | 17 | N | B) Liquidación. Mod. 40.3 LIS - Resultado contable después del IS e IC [04] | 15 enteros + 2 decimales
32 | 217 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Correcciones al resultado contable - por Impuesto sobre Sociedades (IS) - Aumentos [05] | 15 enteros + 2 decimales
33 | 234 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Correcciones al resultado contable - por Impuesto sobre Sociedades (IS) - Disminuciones [06] | 15 enteros + 2 decimales
34 | 251 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Correcciones al resultado contable - por Impuesto Complementario (IC) - Aumentos  [67] | 15 enteros + 2 decimales
35 | 268 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - 30% gastos amortiz - Disminuciones [37] | 15 enteros + 2 decimales
36 | 285 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Resto correcciones al resultado contable, excepto comp. - Aumentos [07] | 15 enteros + 2 decimales
37 | 302 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Resto correcciones al resultado contable, excepto comp. - Disminuciones [08] | 15 enteros + 2 decimales
38 | 319 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - TOTAL. - Aumentos [38] | 15 enteros + 2 decimales
39 | 336 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - TOTAL - Disminuciones [39] | 15 enteros + 2 decimales
40 | 353 | 17 | N | B) Liquidación. Mod. 40.3 LIS - Base imponible previa [13] | 15 enteros + 2 decimales
41 | 370 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Remanente reserva de capitalización no aplicada por insuficiencia de base [44] | 15 enteros + 2 decimales
42 | 387 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Compensación de bases negativas de ejercicios anteriores [14] | 15 enteros + 2 decimales
43 | 404 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Reserva de nivelación (art. 105 LIS) (solo entidades que cumplan los requisitos para la aplicación de los incentivos de empresa de reducida dimensión (art. 101 LIS) y apliquen el tipo de gravamen específico previsto para estas entidades) - Aumentos [45] | 15 enteros + 2 decimales
44 | 421 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Reserva de nivelación (art. 105 LIS) (solo entidades que cumplan los requisitos para la aplicación de los incentivos de empresa de reducida dimensión (art. 101 LIS) y apliquen el tipo de gravamen específico previsto para estas entidades) - Disminuciones [46] | 15 enteros + 2 decimales
45 | 438 | 251 | An | Reservado para la Administración | En blanco
46 | 689 | 12 | An | Indicador de fin de registro | Constante "</T20201000>"
 | TOTAL | 700 | POSICIONES
Nota 1. El tipo de declaración para la presentación por lotes puede ser: I (ingreso), U (domiciliación), G (Ingreso en C.C.T.) y N(Negativa/Sin actividad/Resultado cero)
Nota 2. Para facilitar la incorporación de datos al formulario se espera que el fichero esté localizado en C:\AEAT\ y que su nombre sea 202.txt
Nota 3. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
Nota 4. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
Nota 5. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
Nota 6. Los datos numéricos negativos llevarán una N en la primera posición del campo.
Nota 7. Este valor debe ser X si la Entidad:
 | a) Aplica la reserva para inversiones en Canarias o tiene derecho a la bonificación del art. 26 Ley 19/1994
 | b) Aplica el régimen ZEC
 | c) Aplica la bonificación de Ceuta y Melilla art. 33 LIS
 | d) Tiene resultados positivos por operaciones de aumento de capital o fondos propios por compensación de créditos que no se integran en la BI por aplicación del art. 17.2 LIS
 | e) Está parcialmente exenta por aplicar el régimen especial Cap XIV Titulo VII LIS
 | f) Aplica la bonificación del art. 34 LIS
Nota 8: | Esta nueva marca no será aplicable para el periodo 1P del ejercicio 2018
Nota 9: Valores posibles
 | Blanco | Sin contenido
 | 1 | Navarra
 | 2 | Guipúzcoa
 | 3 | Vizcaya
 | 4 | Álava
Nota 10: | Valores posibles para ejercicio 2026 y siguientes: consultar en Sede.
 | Valores posibles para ejercicio 2025:
 |  | Con porcentaje único
 |  |  | 00
 |  |  | 01
 |  |  | 04
 |  |  | 10
 |  |  | 15
 |  |  | 23
 |  |  | 24
 |  |  | 25
 |  |  | 30
 |  | Con más de un porcentaje
 |  |  | 00/23
 |  |  | 00/21/22
 |  |  | 00/24
 |  |  | 00/25
 |  |  | 21/22
 |  |  | 20/23
 |  |  | 20/24
 |  |  | 20/25
 |  |  | 18/19/21/22
 |  |  | 12/15
 |  |  | 25/30
 |  |  | 23/30
 |  |  | 24/30
 |  |  | 21/22/30
 |  |  | 15/30
 |  |  | 04/23
 |  |  | 04/21/22
 |  |  | 04/24
 |  |  | 04/25
 |  |  | 23/23N
 |  |  | 24/24N
 |  |  | 25/25N
 |  |  | 21/22/21N/22N
Nota 11 | Valores posibles
 |  | A | Liquidación modalidad artículo 40.2 LIS
 |  | B | Liquidación modalidad artículo 40.3 LIS
Nota 12
 | Ejercicio 2025: CNAE-2009
 | Ejercicio 2026 y ss: CNAE-2025
 | TOTAL: | -1 |  | POSICIONES

# dr M202 (2)

 | Agencia Tributaria
Modelo 202 |  | Diseño de registro. Castellano.
versión 1.2 |  | Impuesto sobre Sociedades. Impuesto sobre la Renta de no Residentes. Pago fraccionado
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | Num | Modelo | Constante "202"
3 | 6 | 2 | Num | Página | Constante "02"
4 | 8 | 4 | An | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An | Reservado para la Administración | En blanco
6 | 13 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B1 - Caso general (porcentaje único) -  Base pago fraccionado [16] | 15 enteros + 2 decimales
7 | 30 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B1 - Caso general (porcentaje único) -  Porcentaje [17] | 3 enteros + 2 decimales
8 | 35 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B1 - Caso general - Dotaciones del art. 11.12 LIS (DF 4ª LIS) [47] | 15 enteros + 2 decimales
9 | 52 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B1 - Caso general - Compensación de cuotas negativas ejer. anteriores
 (sólo cooperativas) [40] | 15 enteros + 2 decimales
10 | 69 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B1 -Reserva de nivelación (105 LIS) convertido en cuotas (solo entidades que cumplan los requisitos para la aplicación de los incentivos de empresa de reducida dimensión (art. 101 LIS) y apliquen el tipo de gravamen específico previsto para estas entidades) - Aumentos [48] | 15 enteros + 2 decimales
11 | 86 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B1 -Reserva de nivelación (105 LIS) convertido en cuotas (solo entidades que cumplan los requisitos para la aplicación de los incentivos de empresa de reducida dimensión (art. 101 LIS) y apliquen el tipo de gravamen específico previsto para estas entidades) - Disminuciones [49] | 15 enteros + 2 decimales
12 | 103 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B1 - Caso general  -  Resultado previo (clave ([16] x [17]) + [47]-[40]+[48]-[49]) [18] | 15 enteros + 2 decimales
13 | 120 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) - Base del pago fraccionado [19] | 15 enteros + 2 decimales
14 | 137 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) - Base a tipo 1 [20] | 15 enteros + 2 decimales
15 | 154 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Porcentaje [21] | 3 enteros + 2 decimales
16 | 159 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Importe pago fraccionado [22] | 15 enteros + 2 decimales
17 | 176 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) - Base a tipo 2 [23] | 15 enteros + 2 decimales
18 | 193 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Porcentaje [24] | 3 enteros + 2 decimales
19 | 198 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Importe pago fraccionado [25] | 15 enteros + 2 decimales
20 | 215 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) - Base a tipo 3 [61] | 15 enteros + 2 decimales
21 | 232 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Porcentaje [62] | 3 enteros + 2 decimales
22 | 237 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Importe pago fraccionado [63] | 15 enteros + 2 decimales
23 | 254 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) - Base a tipo 4 [64] | 15 enteros + 2 decimales
24 | 271 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Porcentaje [65] | 3 enteros + 2 decimales
25 | 276 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Importe pago fraccionado [66] | 15 enteros + 2 decimales
26 | 293 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Dotac. art. 11.12 LIS (solo cooperativas) (DF 4 LIS) [50] | 15 enteros + 2 decimales
27 | 310 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje). Compensación de cuotas negativas de períodos anteriores (sólo cooperativas) [42] | 15 enteros + 2 decimales
28 | 327 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje)-Reserva de nivelación (art. 105 LIS) (solo entidades que cumplan los requisitos para la aplicación de los incentivos de empresa de reducida dimensión (art. 101 LIS) y apliquen el tipo de gravamen específico previsto para estas entidades). Aumentos [51] | 15 enteros + 2 decimales
29 | 344 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje)-Reserva de nivelación (art. 105 LIS) (solo entidades que cumplan los requisitos para la aplicación de los incentivos de empresa de reducida dimensión (art. 101 LIS) y apliquen el tipo de gravamen específico previsto para estas entidades). Disminuciones [52] | 15 enteros + 2 decimales
30 | 361 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje)-Resultado previo(claves [22]+[25]+[63]+[66]+[50]-[42]+[51]-[52]) [26] | 15 enteros + 2 decimales
31 | 378 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Bonificaciones correspondientes al periodo computado (total) [27] | 15 enteros + 2 decimales
32 | 395 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Retenciones e ingresos a cuenta practicados sobre ingresos periodo computado [28] | 15 enteros + 2 decimales
33 | 412 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - Volumen operaciones en Territorio Común (%) [29] | 3 enteros + 2 decimales
34 | 417 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Pagos fraccionados de periodos anteriores en Territorio Común [30] | 15 enteros + 2 decimales
35 | 434 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Resultado de la declaración anterior (exclusivamente si ésta es complementaria) [31] | 15 enteros + 2 decimales
36 | 451 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Resultado [32] | 15 enteros + 2 decimales
37 | 468 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Mínimo a ingresar (sólo para empresas con CN igual o superior a 10 millones euros) [33] | 15 enteros + 2 decimales
38 | 485 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Cantidad a ingresar (mayor de claves [32] y [33] )  [34] | 15 enteros + 2 decimales
39 | 502 | 1 | An | Información adicional  (5). Comunicación de datos adicionales a la declaración | X o blanco
40 | 503 | 22 | An | Información adicional  (5). Numero de Referencia de Sociedades (NRS)
41 | 525 | 17 | Num | Información adicional  (5). Importe excluido por operaciones de quita o espera | 15 enteros + 2 decimales
42 | 542 | 17 | Num | Información adicional  (5). Parte integrada en la base imponible por operaciones de quita o espera | 15 enteros + 2 decimales
43 | 559 | 17 | Num | Información adicional  (5). Parte integrada en la base imponible a nivel cuota por op. de quita o espera (sólo cooperativas) | 15 enteros + 2 decimales
44 | 576 | 17 | Num | Información adicional  (5). Rentas de reversión de deterioros que se integran en la base imponible | 15 enteros + 2 decimales
45 | 593 | 17 | Num | Información adicional  (5). Importe correspondiente a la reserva para inversiones en Canarias | 15 enteros + 2 decimales
46 | 610 | 17 | Num | Información adicional  (5). Importe correspondiente a la bonificación prevista en el art. 26 de la Ley 19/1994 | 15 enteros + 2 decimales
47 | 627 | 17 | Num | Información adicional  (5). Importe no computable por aplicación del régimen fiscal de la ZEC | 15 enteros + 2 decimales
48 | 644 | 17 | Num | Información adicional  (5). Importe de la minoración correspondiente a las rentas que tengan derecho a la bonificación art. 33 LIS | 15 enteros + 2 decimales
49 | 661 | 17 | Num | Información adicional  (5). Importe excluido por operaciones de aumento de capital o fondos propios por compensación de créditos que no se integren en la base imponible por aplicación del art. 17.2 LIS | 15 enteros + 2 decimales
50 | 678 | 17 | Num | Información adicional  (5). Importe renta exenta de las entidades que aplican el régimen fiscal especial Cap. XIV del Tit. VII LIS | 15 enteros + 2 decimales
51 | 695 | 17 | Num | Información adicional  (5). Importe de la bonificación prevista en el art. 34 LIS | 15 enteros + 2 decimales
52 | 712 | 1 | An | Declaración complementaria (6) | X o blanco
53 | 713 | 13 | An | Declaración complementaria (6). Número de justificante de la declaración anterior
54 | 726 | 34 | An | Domiciliación - IBAN | nota 7
55 | 760 | 116 | An | Reservado para la Administración | En blanco
56 | 876 | 13 | An | Reservado para el sello electrónico de la AEAT
57 | 889 | 12 | An | Indicador de fin de registro | Constante "</T20202000>"
 | TOTAL | 900 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: I (ingreso), U (domiciliación), G (Ingreso en C.C.T.) y N(Negativa/Sin actividad/Resultado cero)
2. Para facilitar la incorporación de datos al formulario se espera que el fichero esté localizado en C:\AEAT\ y que su nombre sea 202.txt
3. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
4. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
6. Los datos numéricos negativos llevarán una N en la primera posición del campo.
7. Para el IBAN español deberá empezar por ES y únicamente se usan las primeras 24 posiciones.
 | TOTAL: | -1 |  | POSICIONES