# dr M202 (1)

 | Agencia Tributaria
Modelo 202 |  | Diseño de registro. Castellano.
vers. 4.4 |  | Impuesto sobre Sociedades. Impuesto sobre la Renta de no Residentes. Pago fraccionado
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | Num | Modelo | Constante "202"
3 | 6 | 2 | Num | Página | Constante "01"
4 | 8 | 1 | An | Fin de identificador de modelo | Constante ">"
5 | 9 | 1 | An | Reservado para la Administración | En blanco
6 | 10 | 1 | A | Tipo de declaración | Ver nota 1
7 | 11 | 9 | An | Identificación (1). NIF
8 | 20 | 60 | An | Identificación (1). Apellidos y nombre o razón social
9 | 80 | 20 | An | Reservado para la Administración
10 | 100 | 4 | Num | Devengo (2). Ejercicio
11 | 104 | 2 | An | Devengo (2). Periodo | "1P", "2P" o "3P"
12 | 106 | 8 | Num | Devengo (2). Fecha de inicio del período impositivo | ddmmaaaa
13 | 114 | 4 | Num | Devengo (2). C.N.A.E. actividad principal
14 | 118 | 1 | An | Datos adicionales (3) - Entidad que aplica el régimen de la Ley 49/2002 de 23 de diciembre | X o blanco
15 | 119 | 1 | An | Datos adicionales (3) - Entidad que aplica el régimen de la Ley 11/2009 de 26 de octubre | X o blanco
16 | 120 | 1 | An | Datos adicionales (3) - Volumen de operaciones superior a 6.010.121 euros | X o blanco
17 | 121 | 1 | An | Datos adicionales (3) - Entidad que aplica el régimen de las entidades navieras en función del tonelaje | X o blanco
18 | 122 | 1 | An | Datos adicionales (3) - Entidades que aplican incentivos de empresa de reducida dimensión | X o blanco
19 | 123 | 1 | An | Datos adicionales (3) - Cifra de negocios de los 12 meses anteriores a la fecha de inicio del período impositivo > 6.000.000  € | X o blanco
20 | 124 | 1 | Num | Datos adicionales (3) - Cooperativa fiscalmente protegida u Otras entidades con posibilidad de aplicar dos tipos impositivos (ej. entidades ZEC) | "0" No consta, 
"1" Cooperativa, 
"2" Otras entidades
21 | 125 | 5 | An | Datos adicionales (3) - Tipo de gravamen del Impuesto sobre Sociedades del ejercicio en curso | Cadena alfanumérica de 5 posiciones para permitir consignar dos tipos. Ejemplos: "00", "01", "25", "20/25"
22 | 130 | 1 | Num | Datos adicionales (3) - Importe neto de la cifra de negocios | "0" No consta, 
"1" (>= 10 M y < 20 M €), 
"2" (>= 20  M y < 60 M €), 
"3" (>= 60 M €)
23 | 131 | 1 | An | Datos adicionales (3) - Marca instrumental (ver nota 7) | X o blanco (ver Nota 7)
24 | 132 | 17 | Num | A) Liquidación. Mod. 40.2 LIS - Base del pago fraccionado [01] | 15 enteros + 2 decimales
25 | 149 | 17 | Num | A) Liquidación. Mod. 40.2 LIS - Resultado de la declaración anterior (complementarias) [02] | 15 enteros + 2 decimales
26 | 166 | 17 | Num | A) Liquidación. Mod. 40.2 LIS - A Ingresar [03] | 15 enteros + 2 decimales
27 | 183 | 17 | N | B) Liquidación. Mod. 40.3 LIS - Resultado contable después del IS [04] | 15 enteros + 2 decimales
28 | 200 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Correcciones al resultado contable - por Impuesto sobre Sociedades - Aumentos [05] | 15 enteros + 2 decimales
29 | 217 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Correcciones al resultado contable - por Impuesto sobre Sociedades - Disminuciones [06] | 15 enteros + 2 decimales
30 | 234 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - 30% gastos amortiz (exc.  emp. reducidas) - Aumentos [36] | 15 enteros + 2 decimales
31 | 251 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - 30% gastos amortiz (exc.  emp. reducidas) - Disminuciones [37] | 15 enteros + 2 decimales
32 | 268 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Resto correcciones al resultado contable, excepto comp. - Aumentos [07] | 15 enteros + 2 decimales
33 | 285 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Resto correcciones al resultado contable, excepto comp. - Disminuciones [08] | 15 enteros + 2 decimales
34 | 302 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - TOTAL. - Aumentos [38] | 15 enteros + 2 decimales
35 | 319 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - TOTAL - Disminuciones [39] | 15 enteros + 2 decimales
36 | 336 | 17 | An | Reservado para la Administración
37 | 353 | 17 | An | Reservado para la Administración
38 | 370 | 17 | N | B) Liquidación. Mod. 40.3 LIS - Base imponible previa [13] | 15 enteros + 2 decimales
39 | 387 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Remanente reserva de capitalización no aplicada por insuficiencia de base [44] | 15 enteros + 2 decimales
40 | 404 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Compensación de bases negativas de ejercicios anteriores [14] | 15 enteros + 2 decimales
41 | 421 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Reserva de nivelación (art. 105 LIS) (Solo entidades del art. 101 LIS) - Aumentos [45] | 15 enteros + 2 decimales
42 | 438 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Reserva de nivelación (art. 105 LIS) (Solo entidades del art. 101 LIS) - Disminuciones [46] | 15 enteros + 2 decimales
43 | 455 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B1 - Caso general (porcentaje único) -  Base pago fraccionado [16] | 15 enteros + 2 decimales
44 | 472 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B1 - Caso general (porcentaje único) -  Porcentaje [17] | 3 enteros + 2 decimales
45 | 477 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B1 - Caso general - Dotaciones del art. 11.12 LIS (DF 4ª LIS) [47] | 15 enteros + 2 decimales
46 | 494 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B1 - Caso general - Compensación de cuotas negativas ejer. anteriores
 (sólo cooperativas) [40] | 15 enteros + 2 decimales
47 | 511 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B1 -Reserva de nivelación (105 LIS) convertido en cuotas - Aumentos [48] | 15 enteros + 2 decimales
48 | 528 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B1 -Reserva de nivelación (105 LIS) convertido en cuotas - Disminuciones [49] | 15 enteros + 2 decimales
49 | 545 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B1 - Caso general  -  Resultado previo (clave ([16] x [17]) - [47]-[40]+[48]-[49]) [18] | 15 enteros + 2 decimales
50 | 562 | 130 | An | Reservado para la Administración | En blanco
51 | 692 | 9 | An | Indicador de fin de registro | Constante "</T20201>"
 | TOTAL | 700 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: I (ingreso), U (domiciliación), G (Ingreso en C.C.T.) y N(Negativa/Sin actividad/Resultado cero)
2. Para facilitar la incorporación de datos al formulario se espera que el fichero esté localizado en C:\AEAT\ y que su nombre sea 202.txt
3. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
4. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
6. Los datos numéricos negativos llevarán una N en la primera posición del campo.
7. Casos para los que se debe activar la marca:
 | a) Tiene resultados positivos consecuencia de operaciones de aumento de capital o fondos propios por compensación de créditos que no se integren en la base imponible
 | por aplicación del apartado 2 del artículo 17 de la LIS
 | b) Se trata de una entidad parcialmente exenta a la que resulta de aplicación el régimen fiscal especial establecido en el Capítulo XIV del título VII
 | c) Se trata de una entidad a la que resulte de aplicación la bonificación del artículo 34 de la LIS
 | d) Ha realizado dotaciones a la RIC en el ejercicio o tiene derecho a la bonificación del art. 26 Ley 19/94.
 | e) Se trata de una entidad a la que resulta de aplicación el régimen especial ZEC y tiene resultados a los que es de aplicación el tipo de gravamen especial
 | f) Entidad con rentas que den derecho a la bonificación prevista en el artículo 33 LIS
 | TOTAL: | -1 |  | POSICIONES

# dr M202 (2)

 | Agencia Tributaria
Modelo 202 |  | Diseño de registro. Castellano.
 |  | Impuesto sobre Sociedades. Impuesto sobre la Renta de no Residentes. Pago fraccionado
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | Num | Modelo | Constante "202"
3 | 6 | 2 | Num | Página | Constante "02"
4 | 8 | 1 | An | Fin de identificador de modelo | Constante ">"
5 | 9 | 1 | An | Reservado para la Administración | En blanco
6 | 10 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) - Base del pago fraccionado [19] | 15 enteros + 2 decimales
7 | 27 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) - Base a tipo 1 [20] | 15 enteros + 2 decimales
8 | 44 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Porcentaje [21] | 3 enteros + 2 decimales
9 | 49 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Importe pago fraccionado [22] | 15 enteros + 2 decimales
10 | 66 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) - Base a tipo 2 [23] | 15 enteros + 2 decimales
11 | 83 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Porcentaje [24] | 3 enteros + 2 decimales
12 | 88 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Importe pago fraccionado [25] | 15 enteros + 2 decimales
13 | 105 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje). Dotaciones del art. 11.12 de la LIS (sólo cooperativas) (DF 4ª LIS) [50] | 15 enteros + 2 decimales
14 | 122 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje). Compensación de cuotas negativas de períodos anteriores (sólo cooperativas) [42] | 15 enteros + 2 decimales
15 | 139 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje)-Reserva de nivelación (art. 105 LIS) (sólo entidades del art. 101 LIS). Aumentos [51] | 15 enteros + 2 decimales
16 | 156 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje)-Reserva de nivelación (art. 105 LIS) (sólo entidades del art. 101 LIS). Disminuciones [52] | 15 enteros + 2 decimales
17 | 173 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje)-Resultado previo(claves [22]+[25]-[50]-[42]+[51]-[52]) [26] | 15 enteros + 2 decimales
18 | 190 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Bonificaciones correspondientes al periodo computado (total) [27] | 15 enteros + 2 decimales
19 | 207 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Retenciones e ingresos a cuenta practicados sobre ingresos periodo computado [28] | 15 enteros + 2 decimales
20 | 224 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - Volumen operaciones en Territorio Común (%) [29] | 3 enteros + 2 decimales
21 | 229 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Pagos fraccionados de periodos anteriores en Territorio Común [30] | 15 enteros + 2 decimales
22 | 246 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Resultado de la declaración anterior (exclusivamente si ésta es complementaria) [31] | 15 enteros + 2 decimales
23 | 263 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Resultado [32] | 15 enteros + 2 decimales
24 | 280 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Mínimo a ingresar (sólo para empresas con CN igual o superior a 10 millones euros) [33] | 15 enteros + 2 decimales
25 | 297 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Cantidad a ingresar (mayor de claves [32] y [33] )  [34] | 15 enteros + 2 decimales
26 | 314 | 1 | An | Información adicional  (5). Comunicación de datos adicionales a la declaración | X o blanco
27 | 315 | 22 | An | Información adicional  (5). Numero de Referencia de Sociedades (NRS)
28 | 337 | 17 | Num | Información adicional  (5). Importe excluido por operaciones de quita o espera | 15 enteros + 2 decimales
29 | 354 | 17 | Num | Información adicional  (5). Parte integrada en la base imponible por operaciones de quita o espera | 15 enteros + 2 decimales
30 | 371 | 1 | An | Declaración complementaria (6) | X o blanco
31 | 372 | 13 | An | Declaración complementaria (6). Número de justificante de la declaración anterior
32 | 385 | 34 | An | Domiciliación - IBAN | nota 7
33 | 419 | 160 | An | Reservado para la Administración | En blanco
34 | 579 | 13 | An | Reservado para el sello electrónico de la AEAT
35 | 592 | 9 | An | Indicador de fin de registro | Constante "</T20202>"
 | TOTAL | 600 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: I (ingreso), U (domiciliación), G (Ingreso en C.C.T.) y N(Negativa/Sin actividad/Resultado cero)
2. Para facilitar la incorporación de datos al formulario se espera que el fichero esté localizado en C:\AEAT\ y que su nombre sea 202.txt
3. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
4. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
6. Los datos numéricos negativos llevarán una N en la primera posición del campo.
7. Para el IBAN español deberá empezar por ES y únicamente se usan las primeras 24 posiciones.
 | TOTAL: | -1 |  | POSICIONES