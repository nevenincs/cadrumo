# DR22200

 | Agencia Tributaria
Modelo 222 |  | Diseño de registro. Castellano.
Versión 1.4 |  | Impuesto sobre Sociedades. Impuesto sobre la Renta de no Residentes. Pago fraccionado
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Constante. | "<T"
2 | 3 | 3 | An | Modelo | "222"
3 | 6 | 1 | An | Constante. | "0"
4 | 7 | 4 | An | Ejercicio devengo. (AAAA)
5 | 11 | 2 | An | Período. (PP) | "1P", "2P", "3P" o "0A"
6 | 13 | 5 | An | Constante. | "0000>"
7 | 18 | 5 | An | Constante | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos | BLANCOS
9 | 93 | 4 | An | Versión del Programa (Nota 1)
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos | BLANCOS
11 | 101 | 9 | An | NIF Empresa Desarrollo (Nota 1)
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos | BLANCOS
13 | 323 | 6 | An | Constante | "</AUX>"
14 | 329 | Variable | An | Contenido del fichero.  Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T2220+Ejercicio+periodo+0000> | "</T2220AAAAPP0000>"
Total |  | Variable
Nota 1 | A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
Nota 2
El número máximo de ocurrencias de la página 2 son 6 para las actividades del régimen agrícolas, ganaderas y forestales; y 6 para las actividades
del régimen simplificado(excepto agrícolas, ganaderas y forestales). Por lo que el número máximo de páginas 2 será 3.

# DR22201

 | Agencia Tributaria
Modelo 222 |  | Diseño de registro. Castellano.
Versión 1.4 |  | Impuesto sobre Sociedades. Impuesto sobre la Renta de no Residentes. Pago fraccionado
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | Num | Modelo | Constante "222"
3 | 6 | 2 | Num | Página | Constante "01"
4 | 8 | 4 | An | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An | Reservado para la Administración | En blanco
6 | 13 | 1 | A | Tipo de declaración | Ver nota 1
7 | 14 | 9 | An | Identificación (1). NIF Entidad Representante / Dominante
8 | 23 | 60 | An | Identificación (1). Razón social Entidad Representante / Dominante
9 | 83 | 9 | An | Identificación (1). Teléfono
10 | 92 | 7 | An | Identificación (1). Número de grupo | Ver nota 8
11 | 99 | 1 | An | Identificación (1). Representante (entidad no dominante) / Dominante (incluida en el grupo fiscal) | Ver nota 11
12 | 100 | 1 | An | Identificación (1) - Contribuyente sometido a normativa de Territorio Foral de Navarra, Guipúzcoa, Vizcaya o Álava | Ver nota 10
13 | 101 | 20 | An | Reservado para la Administración
14 | 121 | 15 | An | Identificación (2). Nº de Identificación Entidad Dominante
15 | 136 | 2 | An | Identificación (2). Pais / territorio foral de la Entidad Dominante | Ver nota 13
16 | 138 | 60 | An | Identificación (2). Razón social Entidad Dominante
17 | 198 | 12 | An | Reservado para la Administración
18 | 210 | 4 | Num | Devengo (3). Ejercicio
19 | 214 | 2 | An | Devengo (3). Periodo | "1P", "2P", "3P" o "0A". Ver nota 12
20 | 216 | 8 | Num | Devengo (3). Fecha de inicio del período impositivo | ddmmaaaa
21 | 224 | 4 | Num | Devengo (3). C.N.A.E. actividad principal | Nota 16
21 | 228 | 1 | An | Datos adicionales (4) - Grupo de entidades en el que es aplicable el régimen de las entidades navieras en función del tonelaje | X o blanco
22 | 229 | 1 | An | Datos adicionales (4) -Grupo fiscal que cumpla los requisitos para la aplicación de los incentivos de empresa de reducida dimensión (art. 101 LIS) y apliquen el tipo de gravamen específico previsto para estas entidades | X o blanco
23 | 230 | 1 | An | Datos adicionales (4) - Importe neto de la cifra de negocios del grupo fiscal de los doce menses anteriores a la fecha de inicio del período impositivo es superior a 6.000.000 euros. | X o blanco
24 | 231 | 1 | An | Datos adicionales (4) - Grupo de coperativas fiscalmente protegida | X o blanco
25 | 232 | 1 | An | Datos adicionales (4). Grupo fiscal formado exclusivamente por entidades de capital-riesgo que apliquen el régimen fiscal especial del art. 50 LIS | X o blanco
26 | 233 | 1 | An | Datos adicionales (4) - Marque esta casilla si concurre ALGUNA de las siguientes circunstancias: | X o blanco.  Ver Nota 7
27 | 234 | 1 | An | Datos adicionales (4) - Grupo fiscal con importe neto de la cifra de negocios del período impositivo inmediato anterior inferior a 1 millón de euros | X o blanco
28 | 235 | 1 | An | Datos adicionales (4) - Otros grupos fiscales con posibilidad de aplicar dos tipos impositivos | X o blanco
29 | 236 | 15 | An | Datos adicionales (4) - Tipo de gravamen del Impuesto sobre Sociedades del ejercicio en curso. | Cadena alfanumérica de 15 posiciones para permitir consignar varios tipos. 
Ver Nota 14
30 | 251 | 1 | Num | Datos adicionales (4) - Importe neto de la cifra de negocios en los doce meses anteriores a la fecha de inicio del período impositivo: | "0" No consta, 
"1" (>= 10 M y < 20 M €), 
"2" (>= 20  M y < 60 M €), 
"3" (>= 60 M €)
31 | 252 | 1 | An | Liquidación de modalidad A ó B | A ó B.  Ver Nota 15
32 | 253 | 17 | Num | A) Liquidación (5). Mod. 40.2 LIS - Base del pago fraccionado [01] | 15 enteros + 2 decimales
33 | 270 | 17 | Num | A) Liquidación (5). Mod. 40.2 LIS - Resultado de la declaración anterior (exclusivamente si ésta es complementaria) [02] | 15 enteros + 2 decimales
34 | 287 | 17 | Num | A) Liquidación (5). Mod. 40.2 LIS - A Ingresar [03] | 15 enteros + 2 decimales
35 | 304 | 17 | N | B) Liquidación (5). Mod. 40.3 LIS - Suma de resultados contables individuales (después del IS e IC) [04] | 15 enteros + 2 decimales
36 | 321 | 17 | Num | B) Liquidación (5). Mod. 40.3 LIS - Corrección por Impuesto sobre Sociedades (IS) - Aumentos [05] | 15 enteros + 2 decimales
37 | 338 | 17 | Num | B) Liquidación (5). Mod. 40.3 LIS - Corrección por Impuesto sobre Sociedades (IS) - Disminuciones [06] | 15 enteros + 2 decimales
38 | 355 | 17 | Num | B) Liquidación (5). Mod. 40.3 LIS - Corrección por Impuesto Complementario (IC) - Aumentos [67] | 15 enteros + 2 decimales
39 | 372 | 17 | Num | B) Liquidación (5). Mod. 40.3 LIS - Reversión del 30% del importe de los gastos amortiz (exc.  emp. reducidas) - Disminuciones [37] | 15 enteros + 2 decimales
40 | 389 | 17 | Num | B) Liquidación (5). Mod. 40.3 LIS - Resto correcciones al resultado contable, excepto comp. BI Negativa ej. Ant. - Aumentos [07] | 15 enteros + 2 decimales
41 | 406 | 17 | Num | B) Liquidación (5). Mod. 40.3 LIS - Resto correcciones al resultado contable, excepto comp. BI Negativa ej. Ant. - Disminuciones [08] | 15 enteros + 2 decimales
42 | 423 | 17 | Num | B) Liquidación (5). Mod. 40.3 LIS - TOTAL. - Aumentos [38] | 15 enteros + 2 decimales
43 | 440 | 17 | Num | B) Liquidación (5). Mod. 40.3 LIS - TOTAL - Disminuciones [39] | 15 enteros + 2 decimales
44 | 457 | 17 | Num | B) Liquidación (5). Mod. 40.3 LIS - Ajustes para la determinación de la base imponible del grupo (DA 19ª LIS) - Aumentos [59] | 15 enteros + 2 decimales
45 | 474 | 17 | Num | B) Liquidación (5). Mod. 40.3 LIS - Ajustes para la determinación de la base imponible del grupo (DA 19ª LIS) - Disminuciones [60] | 15 enteros + 2 decimales
46 | 491 | 17 | N | B) Liquidación (5). Mod. 40.3 LIS - Suma de bases imponibles individuales antes de compensar bases negativas de periodos anteriores [10] | 15 enteros + 2 decimales
47 | 508 | 17 | Num | B) Liquidación (5). Mod.40.3 LIS - Correcciones diferimiento resultados internos y otras correcc. Consolidacion - Aumentos[11] | 15 enteros + 2 decimales
48 | 525 | 17 | Num | B) Liquidación (5). Mod. 40.3 LIS- Correcciones diferimiento resultados internos y otras correcc. Consolidacion - Disminuciones [12] | 15 enteros + 2 decimales
49 | 542 | 17 | N | B) Liquidación (5). Mod. 40.3 LIS - Base imponible previa [13] | 15 enteros + 2 decimales
50 | 559 | 17 | N | B) Liquidación (5). Mod. 40.3 LIS - Dotaciones del art. 11.12 de la LIS del grupo [44] | 15 enteros + 2 decimales
51 | 576 | 17 | N | B) Liquidación (5). Mod. 40.3 LIS - Dotaciones del art. 11.12 de la LIS generados a nivel individual o de grupo previo a la incorporación al grupo (art. 67 y 74.3 LIS) [45] | 15 enteros + 2 decimales
52 | 593 | 17 | Num | B) Liquidación (5). Mod. 40.3 LIS - Remanente reserva de capitalización no aplicada por insuficiencia de base [46] | 15 enteros + 2 decimales
53 | 610 | 17 | Num | B) Liquidación (5). Mod. 40.3 LIS - Compensación de bases imponibles negativas del grupo de períodos anteriores [14] | 15 enteros + 2 decimales
54 | 627 | 17 | Num | B) Liquidación (5). Mod. 40.3 LIS - Compensación de bases imponibles negativas de entidades o de grupos previos a la integracion al grupo (art.67 y 74.3 LIS) [15] | 15 enteros + 2 decimales
55 | 644 | 17 | Num | B) Liquidación (5). Mod. 40.3 LIS - Reserva de nivelación (art. 105 LIS) (sólo grupos que cumplan los requisitos para la aplicación de los incentivos de empresa de reducida dimensión (art. 101 LIS) y apliquen el tipo de gravamen específico previsto para estas entidades)  Aumentos [47] | 15 enteros + 2 decimales
56 | 661 | 17 | Num | B) Liquidación (5). Mod. 40.3 LIS - Reserva de nivelación (art. 105 LIS) (sólo grupos que cumplan los requisitos para la aplicación de los incentivos de empresa de reducida dimensión (art. 101 LIS) y apliquen el tipo de gravamen específico previsto para estas entidades) - Disminuciones [48] | 15 enteros + 2 decimales
57 | 678 | 198 | An | Reservado para la Administración | En blanco
58 | 876 | 13 | An | Reservado para el sello electrónico de la AEAT | En blanco
59 | 889 | 12 | An | Indicador de fin de registro | Constante "</T22201000>"
 | TOTAL | 900 | POSICIONES
Nota 1. El tipo de declaración para la presentación por lotes puede ser: I (ingreso), U (domiciliación), G (Ingreso en C.C.T.) y N(Negativa/Sin actividad/Resultado cero)
Nota 2. Para facilitar la incorporación de datos al formulario se espera que el fichero esté localizado en C:\AEAT\ y que su nombre sea 222.txt
Nota 3. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
Nota 4. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
Nota 5. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
Nota 6. Los datos numéricos negativos llevarán una N en la primera posición del campo.
Nota 7. Este valor debe ser X si la Entidad:
 | - Grupo fiscal que aplica la Reserva para inversiones en Canarias o tenga derecho a la bonificación del art. 26 Ley 19/1994
 | - Grupo fiscal que aplica el régimen ZEC
 | - Grupo fiscal que aplica la bonificación de Ceuta y Melilla art. 33 LIS
 | - Grupo fiscal con resultados positivos por operaciones de aumento de capital o fondos propios por compensación de créditos que no se
 | integran en la base imponible por aplicación del art. 17.2 LIS
 | - Grupo fiscal parcialmente exento que aplica el régimen fiscal especial Cap. XIV Tít. VII LIS
 | - Grupo fiscal que aplica la bonificación del art. 34 LIS
Nota 8.          Si es estatal: Formato:  - - - - / - -
 | Si es foral: Formato:  - - -  / - - A,    - - -  / - - G,   - - - - - B,    - - - - - - N
Nota 9. Esta nueva marca no será aplicable para el periodo 1P del ejercicio 2018
Nota 10. Valores posibles
 | Blanco | Sin contenido
 | 1 | Navarra
 | 2 | Guipúzcoa
 | 3 | Vizcaya
 | 4 | Álava
Nota 11. Valores posibles
 | 1 | Representante (entidad no dominante)
 | 2 | Dominante (incluida en el grupo fiscal)
Nota 12. La opción "0A" solo podrá seleccionarse cuando el contribuyente esté sometido a la normativa foral de Guipuzcoa, Vizcaya o Álava. 
Cuando el contribuyente esté sometido a la normativa foral de Navarra se deberá seleccionar la opción "2P"
Nota 13. Tabla con códigos de paises ISO 3166-1 incrementada inicialmente con los códigos provinciales: 01-Álava / 20-Guipúzcoa / 31-Navarra / 48-Vizcaya
Nota 14. Valores posibles | Para la consulta de tipos impositivos aplicables en Impuesto sobre Sociedades, periodos impositivos 2025 y siguientes, puede consultar el siguiente enlace:
 | https://sede.agenciatributaria.gob.es/Sede/impuesto-sobre-sociedades/que-base-imponible-se-determina-sociedades/tipo-impositivo.html
Nota 15  Valores posibles
 |  |  | A | Liquidación modalidad artículo 40.2 LIS
 |  |  | B | Liquidación modalidad artículo 40.3 LIS
Nota 16
 | Ejercicio 2025: CNAE-2009
 | Ejercicio 2026 y ss: CNAE-2025

# DR22202

 | Agencia Tributaria
Modelo 222 |  | Diseño de registro. Castellano.
Versión 1.4 |  | Impuesto sobre Sociedades. Impuesto sobre la Renta de no Residentes. Pago fraccionado
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | Num | Modelo | Constante "222"
3 | 6 | 2 | Num | Página | Constante "02"
4 | 8 | 4 | An | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An | Reservado para la Administración | En blanco
6 | 13 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.1) - Caso general. Base del pago fraccionado [16] | 15 enteros + 2 decimales
7 | 30 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B.1) - Caso general. Porcentaje [17] | 3 enteros + 2 decimales
8 | 35 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B.1) - Caso general. Dotaciones del art. 11.12 LIS del grupo (DF 4ª LIS) [49] | 15 enteros + 2 decimales
9 | 52 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B.1) - Caso general. Dotaciones del art. 11.12 LIS generadas previa  a la incorporación al grupo (DF 4ª LIS) [50] | 15 enteros + 2 decimales
10 | 69 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.1) - Caso general. Compensación de cuotas negativas del grupo de períodos anteriores (sólo cooperativas)  [51] | 15 enteros + 2 decimales
11 | 86 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.1 - Caso general. Compensación de cuotas negativas individuales de períodos anteriores a la incorporación al grupo (sólo cooperativas) [58] | 15 enteros + 2 decimales
12 | 103 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.1) - Caso general. Reserva de nivelación (art. 105 LIS) convertido en cuotas sólo grupos que cumplan los requisitos para la aplicación de los incentivos de empresa de reducida dimensión
(art. 101 LIS) y apliquen el tipo de gravamen específico previsto para estas entidades)  - Aumentos [52] | 15 enteros + 2 decimales
13 | 120 | 17 | Num | B) Liquidación. Mod.40.3 LIS- B.1) - Caso general. Reserva de nivelación (art. 105 LIS) convertido en cuotas - sólo grupos que cumplan los requisitos para la aplicación de los incentivos de empresa de reducida dimensión (art. 101 LIS) y apliquen el tipo de gravamen específico previsto para estas entidades) - Disminuciones [53] | 15 enteros + 2 decimales
14 | 137 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.1) - Caso general. Resutlado previo (clave ([16] x [17]) - [49] - [50] - [51] + [52] - [53] [18] | 15 enteros + 2 decimales
15 | 154 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Base del pago fraccionado [19] | 15 enteros + 2 decimales
16 | 171 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Base a tipo 1 [20] | 15 enteros + 2 decimales
17 | 188 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Porcentaje 1 [21] | 3 enteros + 2 decimales
18 | 193 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Importe del pago fraccionado 1 [22] | 15 enteros + 2 decimales
19 | 210 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Base a tipo 2 [23] | 15 enteros + 2 decimales
20 | 227 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Porcentaje 2 [24] | 3 enteros + 2 decimales
21 | 232 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Importe del pago fraccionado 2 [25] | 15 enteros + 2 decimales
22 | 249 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Base a tipo 3 [61] | 15 enteros + 2 decimales
23 | 266 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Porcentaje 3 [62] | 3 enteros + 2 decimales
24 | 271 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Importe del pago fraccionado 3 [63] | 15 enteros + 2 decimales
25 | 288 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Base a tipo 4 [64] | 15 enteros + 2 decimales
26 | 305 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Porcentaje 4 [65] | 3 enteros + 2 decimales
27 | 310 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Importe del pago fraccionado 4 [66] | 15 enteros + 2 decimales
28 | 327 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Dotaciones del art. 11.12 LIS del grupo (DF 4ª LIS) [54] | 15 enteros + 2 decimales
29 | 344 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Dotaciones del art. 11.12 LIS generadas previa a la incorporación al grupo (DF 4ª LIS) [57] | 15 enteros + 2 decimales
30 | 361 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Compensación de cuotas negativas del grupo de períodos anteriores(sólo cooperativas) [42] | 15 enteros + 2 decimales
31 | 378 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Compensación de cuotas negativas individuales de períodos anteriores a la incorporación al grupo(sólo cooperativas) [43] | 15 enteros + 2 decimales
32 | 395 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) - Reserva de nivelación (art. 105 LIS) (solo grupos que cumplan los requisitos para la aplicación de los incentivos de empresa de reducida dimensión (art. 101 LIS) y apliquen el tipo de gravamen específico previsto para estas entidades) - Aumentos [55] | 15 enteros + 2 decimales
33 | 412 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) - Reserva de nivelación (art.105 LIS) (solo grupos que cumplan los requisitos
para la aplicación de los incentivos de empresa de reducida dimensión (art. 101 LIS)
y apliquen el tipo de gravamen específico previsto para estas entidades) - Disminuciones [56] | 15 enteros + 2 decimales
34 | 429 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Resultado previo (claves [22]+[25]+[63]+[66]+[54]+[57]-[42]-[43]+[55]-[56]) [26] | 15 enteros + 2 decimales
35 | 446 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Bonificaciones correspondientes al período computado (total) [27] | 15 enteros + 2 decimales
36 | 463 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Retenciones e ingresos a cuenta (totales) practicados sobre ingresos del período computado [28] | 15 enteros + 2 decimales
37 | 480 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Volumen de operaciones en Territorio Común (%) [29] | 3 enteros + 2 decimales
38 | 485 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Pagos fraccionados anteriores correspondientes al período computado en Territorio Común (total) [30] | 15 enteros + 2 decimales
39 | 502 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Resultado de la declaración anterior (exclusivamente si ésta es complementaria) [31] | 15 enteros + 2 decimales
40 | 519 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) - Casos específicos. Resultado [32] | 15 enteros + 2 decimales
41 | 536 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B.2) Mínimo a ingresar (sólo para empresas con CN igual o superior a 10 millones euros) [33] | 15 enteros + 2 decimales
42 | 553 | 17 | Num | B) Liquidación. Mod.40.3 LIS - B.2) - Casos específicos. Cantidad a ingresar (mayor de claves [32] y [33]) [34] | 15 enteros + 2 decimales
43 | 570 | 17 | N | Información adicional  (6). Resultado consolidado del período [35] | 15 enteros + 2 decimales
44 | 587 | 1 | An | Información adicional  (6). Comunicación de datos adicionales a la declaración | X o blanco
45 | 588 | 22 | An | Información adicional  (6). Numero de Referencia de Sociedades (NRS)
46 | 610 | 1 | An | Información adicional  (6). Comunicación de variación en la composición del grupo fiscal | X o blanco
47 | 611 | 22 | An | Información adicional  (6). Numero de Referencia de Sociedades (NRS)
48 | 633 | 17 | Num | Información adicional  (6). Importe excluido por operacioens de quita o espera | 15 enteros + 2 decimales
49 | 650 | 17 | Num | Información adicional  (6). Parte integrada en la base imponible por operacioens de quita o espera | 15 enteros + 2 decimales
50 | 667 | 17 | Num | Información adicional  (6). Parte integrada en la base imponible a nivel cuota por op. de quita o espera (sólo cooperativas) | 15 enteros + 2 decimales
51 | 684 | 17 | Num | Información adicional  (6). Rentas de reversión de deterioros que se integran en la base imponible | 15 enteros + 2 decimales
52 | 701 | 17 | Num | Información adicional  (6). Importe correspondiente a la reserva para inversiones en Canarias | 15 enteros + 2 decimales
53 | 718 | 17 | Num | Información adicional  (6). Importe correspondiente a la bonificación prevista en el art. 26 de la Ley 19/1994 | 15 enteros + 2 decimales
54 | 735 | 17 | Num | Información adicional  (6). Importe no computable por aplicación del régimen fiscal de la ZEC | 15 enteros + 2 decimales
55 | 752 | 17 | Num | Información adicional  (6). Importe de la minoración correspondiente a las rentas que tengan derecho a la bonificación art. 33 LIS | 15 enteros + 2 decimales
56 | 769 | 17 | Num | Información adicional  (6). Importe excluido por operaciones de aumento de capital o fondos propios por compensación de créditos que no se integren en la base imponible por aplicación del art. 17.2 LIS | 15 enteros + 2 decimales
57 | 786 | 17 | Num | Información adicional  (6). Importe renta exenta de las entidades que aplican el régimen fiscal especial Cap. XIV del Tit. VII LIS | 15 enteros + 2 decimales
58 | 803 | 17 | Num | Información adicional  (6). Importe de la bonificación prevista en el art. 34 LIS | 15 enteros + 2 decimales
59 | 820 | 1 | An | Declaración complementaria (7) | X o blanco
60 | 821 | 13 | An | Declaración complementaria (7). Número de justificante de la declaración anterior
61 | 834 | 34 | An | Domiciliación - IBAN | nota 7
62 | 868 | 121 | An | Reservado para la Administración | En blanco
63 | 989 | 12 | An | Indicador de fin de registro | Constante "</T22202000>"
 | TOTAL | 1000 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: I (ingreso), U (domiciliación), G (Ingreso en C.C.T.) y N(Negativa/Sin actividad/Resultado cero)
2. Para facilitar la incorporación de datos al formulario se espera que el fichero esté localizado en C:\AEAT\ y que su nombre sea 222.txt
3. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
4. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
6. Los datos numéricos negativos llevarán una N en la primera posición del campo.
7. Para el IBAN español deberá empezar por ES y únicamente se usan las primeras 24 posiciones.
 | TOTAL: | -1 |  | POSICIONES