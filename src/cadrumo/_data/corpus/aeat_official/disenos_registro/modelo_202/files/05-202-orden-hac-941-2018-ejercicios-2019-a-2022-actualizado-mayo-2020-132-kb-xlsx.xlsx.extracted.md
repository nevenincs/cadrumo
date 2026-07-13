# dr M202 (0)

 | Agencia Tributaria
Modelo 202 |  | Diseño de registro. Castellano.
Versión 5,2 |  | Impuesto sobre Sociedades. Impuesto sobre la Renta de no Residentes. Pago fraccionado
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
 |  | Impuesto sobre Sociedades. Impuesto sobre la Renta de no Residentes. Pago fraccionado
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | Num | Modelo | Constante "202"
3 | 6 | 2 | Num | Página | Constante "01"
4 | 8 | 4 | An | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An | Reservado para la Administración | En blanco
6 | 13 | 1 | A | Tipo de declaración | Ver nota 1
7 | 14 | 9 | An | Identificación (1). NIF
8 | 23 | 60 | An | Identificación (1). Denominación o apellidos
9 | 83 | 20 | An | Identificación (1). Nombre
10 | 103 | 4 | Num | Devengo (2). Ejercicio
11 | 107 | 2 | An | Devengo (2). Periodo | "1P", "2P", "3P" o "0A"
12 | 109 | 8 | Num | Devengo (2). Fecha de inicio del período impositivo | ddmmaaaa
13 | 117 | 4 | Num | Devengo (2). C.N.A.E. actividad principal
14 | 121 | 1 | An | Datos adicionales (3) - Entidad que aplica el régimen de la Ley 49/2002 de 23 de diciembre | X o blanco
15 | 122 | 1 | An | Datos adicionales (3) - Entidad que aplica el régimen de la Ley 11/2009 de 26 de octubre | X o blanco
16 | 123 | 1 | An | Datos adicionales (3) - Entidad que aplica el régimen de las entidades navieras en función del tonelaje | X o blanco
17 | 124 | 1 | An | Datos adicionales (3) - Entidad que cumpla los requisitos del art. 101 LIS y apliquen tipo de gravamen art.29.1 1er párrafo LIS | X o blanco
18 | 125 | 1 | An | Datos adicionales (3) - Cifra de negocios de los 12 meses anteriores a la fecha de inicio del período impositivo > 6.000.000  € | X o blanco
19 | 126 | 1 | Num | Datos adicionales (3) - Cooperativa fiscalmente protegida u Otras entidades con posibilidad de aplicar dos tipos impositivos (ej. entidades ZEC) | "0" No consta, 
"1" Cooperativa, 
"2" Otras entidades
20 | 127 | 5 | An | Datos adicionales (3) - Tipo de gravamen del Impuesto sobre Sociedades del ejercicio en curso | Cadena alfanumérica de 5 posiciones para permitir consignar dos tipos. 
Ver Nota 3
21 | 132 | 1 | Num | Datos adicionales (3) - Importe neto de la cifra de negocios | "0" No consta, 
"1" (>= 10 M y < 20 M €), 
"2" (>= 20  M y < 60 M €), 
"3" (>= 60 M €)
22 | 133 | 1 | An | Datos adicionales (3) - Marca instrumental (ver nota 7) | X o blanco (ver Nota 7)
23 | 134 | 17 | Num | A) Liquidación. Mod. 40.2 LIS - Base del pago fraccionado [01] | 15 enteros + 2 decimales
24 | 151 | 17 | Num | A) Liquidación. Mod. 40.2 LIS - Resultado de la declaración anterior (complementarias) [02] | 15 enteros + 2 decimales
25 | 168 | 17 | Num | A) Liquidación. Mod. 40.2 LIS - A Ingresar [03] | 15 enteros + 2 decimales
26 | 185 | 17 | N | B) Liquidación. Mod. 40.3 LIS - Resultado contable después del IS [04] | 15 enteros + 2 decimales
27 | 202 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Correcciones al resultado contable - por Impuesto sobre Sociedades - Aumentos [05] | 15 enteros + 2 decimales
28 | 219 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Correcciones al resultado contable - por Impuesto sobre Sociedades - Disminuciones [06] | 15 enteros + 2 decimales
29 | 236 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - 30% gastos amortiz - Disminuciones [37] | 15 enteros + 2 decimales
30 | 253 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Resto correcciones al resultado contable, excepto comp. - Aumentos [07] | 15 enteros + 2 decimales
31 | 270 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Resto correcciones al resultado contable, excepto comp. - Disminuciones [08] | 15 enteros + 2 decimales
32 | 287 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - TOTAL. - Aumentos [38] | 15 enteros + 2 decimales
33 | 304 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - TOTAL - Disminuciones [39] | 15 enteros + 2 decimales
34 | 321 | 17 | N | B) Liquidación. Mod. 40.3 LIS - Base imponible previa [13] | 15 enteros + 2 decimales
35 | 338 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Remanente reserva de capitalización no aplicada por insuficiencia de base [44] | 15 enteros + 2 decimales
36 | 355 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Compensación de bases negativas de ejercicios anteriores [14] | 15 enteros + 2 decimales
37 | 372 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Reserva de nivelación (art. 105 LIS) (Solo entidades del art. 101 LIS) - Aumentos [45] | 15 enteros + 2 decimales
38 | 389 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Reserva de nivelación (art. 105 LIS) (Solo entidades del art. 101 LIS) - Disminuciones [46] | 15 enteros + 2 decimales
39 | 406 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B1 - Caso general (porcentaje único) -  Base pago fraccionado [16] | 15 enteros + 2 decimales
40 | 423 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B1 - Caso general (porcentaje único) -  Porcentaje [17] | 3 enteros + 2 decimales
41 | 428 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B1 - Caso general - Dotaciones del art. 11.12 LIS (DF 4ª LIS) [47] | 15 enteros + 2 decimales
42 | 445 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B1 - Caso general - Compensación de cuotas negativas ejer. anteriores
 (sólo cooperativas) [40] | 15 enteros + 2 decimales
43 | 462 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B1 -Reserva de nivelación (105 LIS) convertido en cuotas - Aumentos [48] | 15 enteros + 2 decimales
44 | 479 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B1 -Reserva de nivelación (105 LIS) convertido en cuotas - Disminuciones [49] | 15 enteros + 2 decimales
45 | 496 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B1 - Caso general  -  Resultado previo (clave ([16] x [17]) + [47]-[40]+[48]-[49]) [18] | 15 enteros + 2 decimales
46 | 513 | 1 | An | Discriminante para declaraciones Negativas. Liquidación de modalidad A ó B | A ó B ó blanco
47 | 514 | 1 | An | Identificación (1) - Contribuyente sometido a normativa de Territorio Foral de Navarra, Guipúzcoa, Vizcaya o Álava | Nota 2
48 | 515 | 1 | An | Datos adicionales (3). Entidad de capital-riesgo que aplica el régimen fiscal especial del art. 50 LIS | X o blanco. Nota 1
49 | 516 | 1 | An | Reservado para la Administración | En blanco
50 | 517 | 172 | An | Reservado para la Administración | En blanco
51 | 689 | 12 | An | Indicador de fin de registro | Constante "</T20201000>"
 | TOTAL | 700 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: I (ingreso), U (domiciliación), G (Ingreso en C.C.T.) y N(Negativa/Sin actividad/Resultado cero)
2. Para facilitar la incorporación de datos al formulario se espera que el fichero esté localizado en C:\AEAT\ y que su nombre sea 202.txt
3. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
4. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
6. Los datos numéricos negativos llevarán una N en la primera posición del campo.
7. Este valor debe ser X si la Entidad:
 | a) Aplica la reserva para inversiones en Canarias o tiene derecho a la bonificación del art. 26 Ley 19/1994
 | b) Aplica el régimen ZEC
 | c) Aplica la bonificación de Ceuta y Melilla art. 33 LIS
 | d) Tiene resultados positivos por operaciones de aumento de capital o fondos propios por compensación de créditos que no se integran en la BI por aplicación del art. 17.2 LIS
 | e) Está parcialmente exenta por aplicar el régimen especial Cap XIV Titulo VII LIS
 | f) Aplica la bonificación del art. 34 LIS
Nota 1: Esta nueva marca no será aplicable para el periodo 1P del ejercicio 2018
Nota 2: Valores posibles
 | Blanco | Sin contenido
 | 1 | Navarra
 | 2 | Guipúzcoa
 | 3 | Vizcaya
 | 4 | Álava
Nota 3: | Valores posibles
 | Con Porcentaje único
 |  |  | 00
 |  |  | 01
 |  |  | 04
 |  |  | 10
 |  |  | 15
 |  |  | 25
 |  |  | 30
 | Con porcentaje doble
 |  |  | 00/25
 |  |  | 04/25
 |  |  | 20/25
 |  |  | 25/25
 |  |  | 25/30
 | TOTAL: | -1 |  | POSICIONES

# dr M202 (2)

 | Agencia Tributaria
Modelo 202 |  | Diseño de registro. Castellano.
 |  | Impuesto sobre Sociedades. Impuesto sobre la Renta de no Residentes. Pago fraccionado
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | Num | Modelo | Constante "202"
3 | 6 | 2 | Num | Página | Constante "02"
4 | 8 | 4 | An | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An | Reservado para la Administración | En blanco
6 | 13 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) - Base del pago fraccionado [19] | 15 enteros + 2 decimales
7 | 30 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) - Base a tipo 1 [20] | 15 enteros + 2 decimales
8 | 47 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Porcentaje [21] | 3 enteros + 2 decimales
9 | 52 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Importe pago fraccionado [22] | 15 enteros + 2 decimales
10 | 69 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) - Base a tipo 2 [23] | 15 enteros + 2 decimales
11 | 86 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Porcentaje [24] | 3 enteros + 2 decimales
12 | 91 | 17 | N | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Importe pago fraccionado [25] | 15 enteros + 2 decimales
13 | 108 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje) -  Dotac. art. 11.12 LIS (solo cooperativas) (DF 4 LIS) [50] | 15 enteros + 2 decimales
14 | 125 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje). Compensación de cuotas negativas de períodos anteriores (sólo cooperativas) [42] | 15 enteros + 2 decimales
15 | 142 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje)-Reserva de nivelación (art. 105 LIS) (sólo entidades del art. 101 LIS). Aumentos [51] | 15 enteros + 2 decimales
16 | 159 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje)-Reserva de nivelación (art. 105 LIS) (sólo entidades del art. 101 LIS). Disminuciones [52] | 15 enteros + 2 decimales
17 | 176 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - B2 - Casos específicos (más de un porcentaje)-Resultado previo(claves [22]+[25]+[50]-[42]+[51]-[52]) [26] | 15 enteros + 2 decimales
18 | 193 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Bonificaciones correspondientes al periodo computado (total) [27] | 15 enteros + 2 decimales
19 | 210 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Retenciones e ingresos a cuenta practicados sobre ingresos periodo computado [28] | 15 enteros + 2 decimales
20 | 227 | 5 | Num | B) Liquidación. Mod. 40.3 LIS - Volumen operaciones en Territorio Común (%) [29] | 3 enteros + 2 decimales
21 | 232 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Pagos fraccionados de periodos anteriores en Territorio Común [30] | 15 enteros + 2 decimales
22 | 249 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Resultado de la declaración anterior (exclusivamente si ésta es complementaria) [31] | 15 enteros + 2 decimales
23 | 266 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Resultado [32] | 15 enteros + 2 decimales
24 | 283 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Mínimo a ingresar (sólo para empresas con CN igual o superior a 10 millones euros) [33] | 15 enteros + 2 decimales
25 | 300 | 17 | Num | B) Liquidación. Mod. 40.3 LIS - Cantidad a ingresar (mayor de claves [32] y [33] )  [34] | 15 enteros + 2 decimales
26 | 317 | 1 | An | Información adicional  (5). Comunicación de datos adicionales a la declaración | X o blanco
27 | 318 | 22 | An | Información adicional  (5). Numero de Referencia de Sociedades (NRS)
28 | 340 | 17 | Num | Información adicional  (5). Importe excluido por operaciones de quita o espera | 15 enteros + 2 decimales
29 | 357 | 17 | Num | Información adicional  (5). Parte integrada en la base imponible por operaciones de quita o espera | 15 enteros + 2 decimales
30 | 374 | 17 | Num | Información adicional  (5). Parte integrada en la base imponible a nivel cuota por op. de quita o espera (sólo cooperativas) | 15 enteros + 2 decimales
31 | 391 | 17 | Num | Información adicional  (5). Rentas de reversión de deterioros que se integran en la base imponible | 15 enteros + 2 decimales
32 | 408 | 17 | Num | Información adicional  (5). Importe correspondiente a la reserva para inversiones en Canarias | 15 enteros + 2 decimales
33 | 425 | 17 | Num | Información adicional  (5). Importe correspondiente a la bonificación prevista en el art. 26 de la Ley 19/1994 | 15 enteros + 2 decimales
34 | 442 | 17 | Num | Información adicional  (5). Importe no computable por aplicación del régimen fiscal de la ZEC | 15 enteros + 2 decimales
35 | 459 | 17 | Num | Información adicional  (5). Importe de la minoración correspondiente a las rentas que tengan derecho a la bonificación art. 33 LIS | 15 enteros + 2 decimales
36 | 476 | 17 | Num | Información adicional  (5). Importe excluido por operaciones de aumento de capital o fondos propios por compensación de créditos que no se integren en la base imponible por aplicación del art. 17.2 LIS | 15 enteros + 2 decimales
37 | 493 | 17 | Num | Información adicional  (5). Importe renta exenta de las entidades que aplican el régimen fiscal especial Cap. XIV del Tit. VII LIS | 15 enteros + 2 decimales
38 | 510 | 17 | Num | Información adicional  (5). Importe de la bonificación prevista en el art. 34 LIS | 15 enteros + 2 decimales
39 | 527 | 1 | An | Declaración complementaria (6) | X o blanco
40 | 528 | 13 | An | Declaración complementaria (6). Número de justificante de la declaración anterior
41 | 541 | 34 | An | Domiciliación - IBAN | nota 7
42 | 575 | 101 | An | Reservado para la Administración | En blanco
43 | 676 | 13 | An | Reservado para el sello electrónico de la AEAT
44 | 689 | 12 | An | Indicador de fin de registro | Constante "</T20202000>"
 | TOTAL | 700 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: I (ingreso), U (domiciliación), G (Ingreso en C.C.T.) y N(Negativa/Sin actividad/Resultado cero)
2. Para facilitar la incorporación de datos al formulario se espera que el fichero esté localizado en C:\AEAT\ y que su nombre sea 202.txt
3. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
4. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
6. Los datos numéricos negativos llevarán una N en la primera posición del campo.
7. Para el IBAN español deberá empezar por ES y únicamente se usan las primeras 24 posiciones.
 | TOTAL: | -1 |  | POSICIONES