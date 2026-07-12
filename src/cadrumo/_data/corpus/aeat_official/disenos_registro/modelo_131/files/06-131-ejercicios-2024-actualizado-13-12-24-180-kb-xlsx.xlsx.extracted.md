# Pág. 0

 | Agencia Tributaria
Modelo 131 |  | Diseño de registro.
 |  | IRPF. Empresarios y profesionales en Estimación Objetiva. Pago fraccionado.
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. |  | Constante "<T"
2 | 3 | 3 | An | Modelo. |  | Constante "131"
3 | 6 | 1 | An | Discriminante |  | Constante "0"
4 | 7 | 4 | An | Ejercicio de devengo (EEEE) |  | Nota 2
5 | 11 | 2 | An | Periodo (PP) |  | "1T", "2T", "3T","4T"
6 | 13 | 5 | An | Tipo y cierre |  | "0000>"
7 | 18 | 5 | An | Constante |  | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
9 | 93 | 4 | An | Versión del Programa |  | Nota 1
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
11 | 101 | 9 | An | NIF Empresa Desarrollo |  | Nota 1
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
13 | 323 | 6 | An | Constante |  | "</AUX>"
14 | 329 | variable | An | Contenido del fichero. Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T+ modelo+discriminante+Ejercicio+periodo+Tipo+> |  | "</T1310EEEEPP0000>"
TOTAL |  | variable | POSICIONES
Nota 1:
A cumplimentar por las entidades desarrolladoras (EEDD):
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
Nota 2:
EEEE indica las cuatro cifras del ejercicio de devengo
Nota 3:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.

# Pág. 1

 | Agencia Tributaria
Modelo 131 |  | Diseño de registro.
 |  | IRPF. Empresarios y profesionales en Estimación Objetiva. Pago fraccionado.
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | Obligatorio | Constante "<T"
2 | 3 | 3 | An | Modelo. | Obligatorio | Constante "131"
3 | 6 | 5 | An | Página. | Obligatorio | Constante "01000"
4 | 11 | 1 | An | Fin de identificador de modelo. | Obligatorio | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 1 | A | Tipo de autoliquidación | Obligatorio | Ver Nota1
7 | 14 | 9 | An | Declarante (1) - Nif | Obligatorio
8 | 23 | 60 | An | Declarante (1) - Apellidos | Obligatorio
9 | 83 | 20 | An | Declarante (1) - Nombre (solo personas físicas) | Obligatorio
10 | 103 | 4 | Num | Devengo (2) - Ejercicio | Obligatorio | Constante
11 | 107 | 2 | An | Devengo (2) - Período | Obligatorio | "1T".."4T"
12 | 109 | 1 | An | Declarante (1) - Contribuyente tiene un grado de discapacidad igual o superior al 33 por 100 |  | blanco o "X"
13 | 110 | 4 | An | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 1 - Epígrafe IAE
14 | 114 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 1 - Rdto. neto actividad |  | 15 enteros y 2 decimales
15 | 131 | 5 | Num | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 1 - Porcentaje aplicable |  | 3 enteros y 2 decimales
16 | 136 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 1 - Resultado aplicación porcentaje a cada actividad |  | 15 enteros y 2 decimales
17 | 153 | 4 | An | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 2 - Epígrafe IAE
18 | 157 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 2 - Rdto. neto actividad |  | 15 enteros y 2 decimales
19 | 174 | 5 | Num | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 2 - Porcentaje aplicable |  | 3 enteros y 2 decimales
20 | 179 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 2 - Resultado aplicación porcentaje a cada actividad |  | 15 enteros y 2 decimales
21 | 196 | 4 | An | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 3 - Epígrafe IAE
22 | 200 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 3 - Rdto. neto actividad |  | 15 enteros y 2 decimales
23 | 217 | 5 | Num | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 3 - Porcentaje aplicable |  | 3 enteros y 2 decimales
24 | 222 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 3 - Resultado aplicación porcentaje a cada actividad |  | 15 enteros y 2 decimales
25 | 239 | 4 | An | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 4 - Epígrafe IAE
26 | 243 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 4 - Rdto. neto actividad |  | 15 enteros y 2 decimales
27 | 260 | 5 | Num | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 4 - Porcentaje aplicable |  | 3 enteros y 2 decimales
28 | 265 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 4 - Resultado aplicación porcentaje a cada actividad |  | 15 enteros y 2 decimales
29 | 282 | 4 | An | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 5 - Epígrafe IAE
30 | 286 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 5 - Rdto. neto actividad |  | 15 enteros y 2 decimales
31 | 303 | 5 | Num | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 5 - Porcentaje aplicable |  | 3 enteros y 2 decimales
32 | 308 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad 5 - Resultado aplicación porcentaje a cada actividad |  | 15 enteros y 2 decimales
33 | 325 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Suma de rendimientos netos [01] |  | 15 enteros y 2 decimales
34 | 342 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Pago fraccionado previo: suma de resultados [02] |  | 15 enteros y 2 decimales
35 | 359 | 1 | Num | Actividades sin posibilidad de determinar datos base - Deducción por rentas obtenidas en Ceuta y Melilla y por residentes en la Isla de la Palma |  | "0" BLANCO, "1" SI, "2" NO.
36 | 360 | 10 | Num | Actividades sin posibilidad de determinar datos base - Volumen de ventas o ingresos del trimestre |  | 8 enteros y 2 decimales
37 | 370 | 4 | Num | Actividades sin posibilidad de determinar datos base - Si para el cálculo del pago fraccionado desea aplicar un porcentaje superior al que establece la normativa, indique el porcentaje que desea aplicar |  | 2 enteros y 2 decimales
38 | 374 | 10 | Num | Actividades sin posibilidad de determinar datos base - Deducción por destinar cantidades al pago de préstamos para la adquisición o rehabilitación de la vivienda habitual: Volumen de ingresos del primer trimestre o, si la actividad se ha iniciado en el ejercicio de devengo, del trimestre en el que se haya comenzado su ejercicio |  | 8 enteros y 2 decimales
39 | 384 | 3 | Num | Actividades sin posibilidad de determinar datos base - Deducción por destinar cantidades al pago de préstamos para la adquisición o rehabilitación de la vivienda habitual: Número de días en los que ha ejercido la actividad en el primer trimestre /no, si la actividad se ha iniciado en el ejercicio de devengo, del trimestre en el que se haya comenzado su ejercicio |  | 3 enteros
40 | 387 | 3 | Num | Actividades sin posibilidad de determinar datos base - Deducción por destinar cantidades al pago de préstamos para la adquisición o rehabilitación de la vivienda habitual: Número de días en los que previsiblemente ejercerá la actividad durante el año |  | 3 enteros
41 | 390 | 17 | N | Liquidación (3) - II. Activ. económicas estimac. objetiva distintas - Volumen de ventas o ingresos [03] |  | 15 enteros y 2 decimales
42 | 407 | 17 | N | Liquidación (3) - II. Activ. económicas estimac. objetiva distintas - Pago fraccionado previo [04] |  | 15 enteros y 2 decimales
43 | 424 | 10 | Num | Actividades agrícolas, ganaderas y forestales - A) VOLUMEN DE INGRESOS DEL TRIMESTRE (excepto Ceuta y Melilla y por residentes en la Isla de La Palma) (incluye subvenciones corrientes y compensación IVA) - Ingresos de explotaciones ordinarias |  | 8 enteros y 2 decimales
44 | 434 | 10 | Num | Actividades agrícolas, ganaderas y forestales - A) VOLUMEN DE INGRESOS DEL TRIMESTRE (excepto Ceuta y Melilla y por residentes en la Isla de La Palma) (incluye subvenciones corrientes y compensación IVA) - Ingresos de explotaciones prioritarias (Reducción 25% agricultores jóvenes D.A. sexta Ley IRPF) |  | 8 enteros y 2 decimales
45 | 444 | 4 | Num | Actividades agrícolas, ganaderas y forestales - A) VOLUMEN DE INGRESOS DEL TRIMESTRE (excepto Ceuta y Melilla y por residentes en la Isla de La Palma) (incluye subvenciones corrientes y compensación IVA) - Si para el cálculo del pago fraccionado desea aplicar un porcentaje superior al que establece la normativa, indique el porcentaje que desea aplicar |  | 2 enteros y 2 decimales
46 | 448 | 10 | Num | Actividades agrícolas, ganaderas y forestales - B) RENTAS OBTENIDAS EN CEUTA Y MELILLA Y POR RESIDENTES EN LA ISLA DE LA PALMA (deducción art. 68.4 Ley IRPF) - Ingresos de explotaciones ordinarias |  | 8 enteros y 2 decimales
47 | 458 | 10 | Num | Actividades agrícolas, ganaderas y forestales - B) RENTAS OBTENIDAS EN CEUTA Y MELILLA Y POR RESIDENTES EN LA ISLA DE LA PALMA (deducción art. 68.4 Ley IRPF) - Ingresos de explotaciones prioritarias (Reducción 25% agricultores jóvenes D.A. sexta Ley IRPF) |  | 8 enteros y 2 decimales
48 | 468 | 4 | Num | Actividades agrícolas, ganaderas y forestales - B) RENTAS OBTENIDAS EN CEUTA Y MELILLA Y POR RESIDENTES EN LA ISLA DE LA PALMA (deducción art. 68.4 Ley IRPF) - Si para el cálculo del pago fraccionado desea aplicar un porcentaje superior al que establece la normativa, indique el porcentaje que desea aplicar |  | 2 enteros y 2 decimales
49 | 472 | 10 | Num | Actividades agrícolas, ganaderas y forestales - C) Deducción por destinar cantidades al pago de préstamos para la adquisición o rehabilitación de la vivienda habitual: Volumen de ingresos del primer trimestre o, si la actividad se ha iniciado en el ejercicio de devengo, del trimestre en el que se haya comenzado su ejercicio |  | 8 enteros y 2 decimales
50 | 482 | 3 | Num | Actividades agrícolas, ganaderas y forestales - C) Deducción por destinar cantidades al pago de préstamos para la adquisición o rehabilitación de la vivienda habitual: Número de días en los que ha ejercido la actividad en el primer trimestre o, si la actividad se ha iniciado en el ejercicio de devengo, del trimestre en el que se haya comenzado su ejercicio |  | 3 enteros
51 | 485 | 3 | Num | Actividades agrícolas, ganaderas y forestales - C) Deducción por destinar cantidades al pago de préstamos para la adquisición o rehabilitación de la vivienda habitual: Número de días en los que previsiblemente ejercerá la actividad durante el año |  | 3 enteros
52 | 488 | 17 | N | Liquidación (3) - III. Activ. agrícolas, ganaderas estimac. objet. - Volumen ingresos trimestre [05] |  | 15 enteros y 2 decimales
53 | 505 | 17 | N | Liquidación (3) - III. Activ. agrícolas, ganaderas estimac. objet. - Pago fraccionado previo del trimestre [06] |  | 15 enteros y 2 decimales
54 | 522 | 17 | N | Liquidación (3) - IV. Total liquidación - Suma de los pagos fraccionados previos del trimestre [07] |  | 15 enteros y 2 decimales
55 | 539 | 17 | N | Liquidación (3) - IV. Total liquidación - A deducir: retenciones e ingresos a cuenta [08] |  | 15 enteros y 2 decimales
56 | 556 | 1 | Num | Liquidación (3) - IV. Total liquidación - Deducción del art. 110.3.c) del Reglamento del Impuesto - Cuantía de los rendimientos netos de actividades económicas del ejercicio anterior al de devengo, en el caso de que no excedieran de 12.000 euros |  | Nota 3
57 | 557 | 5 | Num | Liquidación (3) - IV. Total liquidación - Deducción del art. 110.3.c) del Reglamento del Impuesto - En el caso excepcional de que en el trimestre deba presentar tambien el modelo 130 de pago fraccionado, indique la cantidad reflejada en él por la presente deducción |  | 3 enteros y 2 decimales
58 | 562 | 17 | N | Liquidación (3) - IV. Total liquidación - Minoración por aplicación de la deducción. Artículo 110.3.c de la Ley [09] |  | 15 enteros y 2 decimales
59 | 579 | 17 | N | Liquidación (3) - IV. Total liquidación - Diferencia [10] |  | 15 enteros y 2 decimales
60 | 596 | 17 | N | Liquidación (3) - IV. Total liquidación - A deducir: Resultados negativos de trimestres anteriores [11] |  | 15 enteros y 2 decimales
61 | 613 | 1 | An | Liquidación (3) - IV. Total liquidación - Deducción por vivienda - Marque X si tiene derecho a aplicar la deducción por destinar cantidades a la adquisición o rehabilitación de su vivienda habitual utilizando financiación ajena, por las que vaya a tener derecho a deducción por inversión en vivienda habitual (no existe derecho a la deducción si la adquisición o rehabilitación se ha efectuado a partir de 1 de enero de 2013 y no se han efectuado pagos para la construcción o rehabilitación de la vivienda con anterioridad a esa fecha) |  | blanco o "X"
62 | 614 | 10 | Num | Liquidación (3) - IV. Total liquidación - Deducción por vivienda - Suma de los importes de la deducción aplicada (casilla 12 del modelo 131) en los trimestres anteriores del ejercicio de devengo |  | 8 enteros y 2 decimales
63 | 624 | 17 | N | Liquidación (3) - IV. Total liquidación - Pago de préstamos para la adquisición de vivienda habitual [12] |  | 15 enteros y 2 decimales
64 | 641 | 17 | N | Liquidación (3) - IV. Total liquidación - Total [13] |  | 15 enteros y 2 decimales
65 | 658 | 17 | N | Liquidación (3) - IV. Total liquidación - A deducir - Resultado a ingresar de las anteriores declaraciones [14] |  | 15 enteros y 2 decimales
66 | 675 | 17 | N | Liquidación (3) - IV. Total liquidación - Resultado de la declaración [15] |  | 15 enteros y 2 decimales
67 | 692 | 1 | An | Complementaria (7) - Declaración complementaria |  | blanco o "X"
68 | 693 | 13 | An | Complementaria (7) - Número justificante declaración anterior
69 | 706 | 101 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
70 | 807 | 13 | An | SELLO ELECTRONICO RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
71 | 820 | 12 | An | Indicador de fin de registro | Obligatorio | Constante "</T13101000>"
TOTAL |  | 831 | POSICIONES
Nota 1: El tipo de autoliquidación puede ser: I (ingreso) N (negativa) G (ingreso a anotar en CCT) U (domiciliación del ingreso en CCC) B (Resultado a deducir)
Nota 2:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
Nota 3:
Cuantía de los rendimientos netos de actividades económicas del ejercicio anterior al de devengo, en el caso de que no excedieran de 12.000 euros
Valor | Descripción
0 | Blanco
1 | Rendimientos netos de actividades económicas iguales o inferiores a 9.000 euros
2 | Rendimientos netos de actividades económicas comprendidos entre 9.000,01 y 10.000 euros
3 | Rendimientos netos de actividades económicas comprendidos entre 10.000,01 y 11.000 euros
4 | Rendimientos netos de actividades económicas comprendidos entre 11.000,01 y 12.000 euros

# DPA

 | Agencia Tributaria
Modelo 131 |  | Diseño de registro.
 |  | IRPF. Empresarios y profesionales en Estimación Objetiva. Pago fraccionado.
Nº | Posic. | Lon | Tipo | Com | Descripción | Validación | Contenido
1 | 1 | 2 | An | C | Inicio del identificador de modelo y página. | Obligatorio | Constante "<T"
2 | 3 | 3 | An | C | Modelo. | Obligatorio | Constante "131"
3 | 6 | 5 | An | C | Página. | Obligatorio | Constante "DPA00"
4 | 11 | 1 | An | C | Fin de identificador de modelo. | Obligatorio | Constante ">"
5 | 12 | 1 | A | C | Indicador de página complementaria. |  | Blanco (No complementaria) o "C" (Complementaria)
6 | 13 | 4 | An | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Epigrafe IAE
7 | 17 | 1 | An | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Epigrafe IAE
 - Indicador auxiliar de actividad en el caso de epígrafes 659.4 y 691.9 |  | blanco, "1" o "2"  (Nota 2)
8 | 18 | 4 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Comunidad, sociedad civil o similar: porcentaje de participación |  | 2 enteros y 2 decimales
9 | 22 | 3 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Actividad de temporada: nº de días de ejercicio en el año anterior |  | 3 enteros
10 | 25 | 4 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Nuevas actividades iniciadas a partir del 1 de enero del ejercicio anterior al devengo: Año de inicio |  | 4 enteros
11 | 29 | 1 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Deducción por rentas obtenidas en Ceuta y Melilla y por residentes en la isla de la Palma |  | "0" BLANCO, "1" SI, "2" NO.
12 | 30 | 1 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Ejerce la actividad en un solo local o sin él |  | "0" BLANCO, "1" SI, "2" NO.
13 | 31 | 2 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Indique el número de vehículos afectos a la actividad |  | 2 enteros
14 | 33 | 1 | An | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Si la actividad se realiza con tractocamiones y el titular carece de semirremolques, marque esta casilla |  | blanco o "X"
15 | 34 | 1 | An | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Si la actividad se realiza con un único tractocamión y sin semirremolques, marque esta casilla |  | blanco o "X"
16 | 35 | 1 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - La capacidad de carga del vehículo es superior a 1000 Kg. |  | "0" BLANCO, "1" SI, "2" NO.
17 | 36 | 1 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Municipio donde se ejerce la actividad |  | Nota 3
18 | 37 | 1 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Número de bateas y de barcos auxiliares de la empresa |  | Nota 4
19 | 38 | 3 | An | C | RESERVADO PARA LA A.E.A.T. (Dejar en blanco) |  | blanco
20 | 41 | 1 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Si en el año de devengo realiza la actividad en LORCA, seleccione lo que proceda |  | 0, 1 o 2. Nota 5
21 | 42 | 1 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Si en el año de devengo realiza la actividad en la Isla de La Palma, seleccione lo que proceda |  | 0, 1 o 2. Nota 5
22 | 43 | 4 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Si para el cálculo del pago fraccionado desea aplicar un porcentaje superior al que establece la normativa, indique el porcentaje que desea aplicar |  | 2 enteros y 2 decimales
23 | 47 | 7 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Personal asalariado o Personal asalariado de fabricación - Horas anuales - Mayores de 19 años |  | 7 enteros
24 | 54 | 7 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Personal asalariado o Personal asalariado de fabricación - Horas anuales - Menores de 19 años y trabajadores con contratos de aprendizaje o formación que no sean discapacitados |  | 7 enteros
25 | 61 | 7 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Personal asalariado o Personal asalariado de fabricación - Horas anuales - Discapacitados con grado de minusvalía igual o superior al 33 por 100 |  | 7 enteros
26 | 68 | 4 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Personal asalariado o Personal asalariado de fabricación - Horas anuales - Horas anuales fijadas en el convenio colectivo vigente |  | 4 enteros
27 | 72 | 7 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Resto personal asalariado - Horas anuales - Mayores de 19 años |  | 7 enteros. Nota 6
28 | 79 | 7 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Resto personal asalariado - Horas anuales - Menores de 19 años y trabajadores con contratos de aprendizaje o formación que no sean discapacitados |  | 7 enteros. Nota 6
29 | 86 | 7 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Resto personal asalariado - Horas anuales - Discapacitados con grado de minusvalía igual o superior al 33 por 100 |  | 7 enteros. Nota 6
30 | 93 | 4 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Resto personal asalariado - Horas anuales - Horas anuales fijadas en el convenio colectivo vigente |  | 4 enteros. Nota 6
31 | 97 | 4 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Personal Empleado - Personal No Asalariado - Horas anuales: titular |  | 4 enteros. Nota 7
32 | 101 | 4 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Personal Empleado - Personal No Asalariado - Horas anuales: cónyuge |  | 4 enteros. Nota 7
33 | 105 | 7 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Personal Empleado - Personal No Asalariado - Horas anuales: hijos menores de 18 años |  | 7 enteros. Nota 7
34 | 112 | 2 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Mesas - Capacidad |  | 2 enteros
35 | 114 | 4 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Mesas - Mesas |  | 4 enteros
36 | 118 | 2 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Mesas - Capacidad |  | 2 enteros
37 | 120 | 4 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Mesas - Mesas |  | 4 enteros
38 | 124 | 2 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Mesas - Capacidad |  | 2 enteros
39 | 126 | 4 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Mesas - Mesas |  | 4 enteros
40 | 130 | 2 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Mesas - Capacidad |  | 2 enteros
41 | 132 | 4 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo Mesas - Mesas |  | 4 enteros
42 | 136 | 10 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo 1 - Nº Unidades |  | 8 enteros y 2 decimales. Nota 8
43 | 146 | 17 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo 1 - Rendimiento neto por módulo |  | 15 enteros y 2 decimales. Nota 8
44 | 163 | 10 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo 2 - Nº Unidades |  | 8 enteros y 2 decimales. Nota 8
45 | 173 | 17 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo 2 - Rendimiento neto por módulo |  | 15 enteros y 2 decimales. Nota 8
46 | 190 | 10 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo 3 - Nº Unidades |  | 8 enteros y 2 decimales. Nota 8
47 | 200 | 17 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo 3 - Rendimiento neto por módulo |  | 15 enteros y 2 decimales. Nota 8
48 | 217 | 10 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo 4 - Nº Unidades |  | 8 enteros y 2 decimales. Nota 8
49 | 227 | 17 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo 4 - Rendimiento neto por módulo |  | 15 enteros y 2 decimales. Nota 8
50 | 244 | 10 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo 5 - Nº Unidades |  | 8 enteros y 2 decimales. Nota 8
51 | 254 | 17 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo 5 - Rendimiento neto por módulo |  | 15 enteros y 2 decimales. Nota 8
52 | 271 | 10 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo 6 - Nº Unidades |  | 8 enteros y 2 decimales. Nota 8
53 | 281 | 17 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo 6 - Rendimiento neto por módulo |  | 15 enteros y 2 decimales. Nota 8
54 | 298 | 10 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo 7 - Nº Unidades |  | 8 enteros y 2 decimales. Nota 8
55 | 308 | 17 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Módulo 7 - Rendimiento neto por módulo |  | 15 enteros y 2 decimales. Nota 8
56 | 325 | 10 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - B. Rendimiento a efectos de pagos fraccionados - Incentivos al empleo |  | 8 enteros y 2 decimales
57 | 335 | 10 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - B. Rendimiento a efectos de pagos fraccionados - Incentivos a la inversión |  | 8 enteros y 2 decimales
58 | 345 | 4 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - B1. Índices correctores - 1. Especiales |  | 2 enteros y 2 decimales
59 | 349 | 4 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - B1. Índices correctores - 2. Empresas de pequeña dimensión |  | 2 enteros y 2 decimales
60 | 353 | 4 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - B1. Índices correctores - 3. De temporada |  | 2 enteros y 2 decimales
61 | 357 | 4 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - B1. Índices correctores - 4. De exceso |  | 2 enteros y 2 decimales
62 | 361 | 4 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - B1. Índices correctores - 5. De inicio de nueva actividad |  | 2 enteros y 2 decimales
63 | 365 | 10 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Reducción para actividades económicas realizadas en el término municipal de Lorca |  | 8 enteros y 2 decimales
64 | 375 | 10 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Reducción para actividades económicas realizadas en la Isla de La Palma |  | 8 enteros y 2 decimales
65 | 385 | 2 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Días de ejercicio en el trimestre |  | 2 enteros
66 | 387 | 1 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Si la actividad se realizó en alguno de los municipios afectados por la DANA entre el 28 de octubre y el 4 de noviembre de 2024 (RD-l 6/2024), seleccione lo que proceda |  | 0, 1 o 2. Nota 5
67 | 388 | 10 | Num | C | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad - Reducción para actividades económicas DANA entre 28 de octubre y  4 de noviembre de 2024 (RD-l 6/2024) |  | 8 enteros y 2 decimales
68 | 398 | 189 | An | C | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
69 | 587 | 12 | An | C | Indicador de fin de registro | Obligatorio | Constante "</T131DPA00>"
TOTAL |  | 598 | POSICIONES
Nota 1:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
Nota 2:
La cumplimentación de estos campos deberá realizarse de la siguiente forma:
blanco | Cuando el epígrafe de la actividad correspondiente sea distinto de 659,4 o 691.9 (o no esté cumplimentada esa actividad).
Epígrafe I.A.E.: 659.4
1 | Actividad: Comercio al por menor de libros, periódicos, artículos de papelería y escritorio y artículos de dibujo y bellas artes, excepto en quioscos situados en la vía pública.
2 | Actividad: Comercio al por menor de prensa, revistas y libros en quioscos situados en la vía pública.
Epígrafe I.A.E.: 691.9
1 | Actividad: Reparación de calzado.
2 | Actividad: Reparación de otros bienes de consumo n.c.o.p. (excepto reparación de calzado, restauración de obras de arte, muebles, antigüedades e instrumentos musicales).
Nota 3:
Municipio donde se ejerce la actividad
Epígrafe 659.4 quioscos
Valor | Descripción
0 | Blanco
1 | Madrid o Barcelona
2 | Más de 100.000 habitantes
3 | Entre 5.001 y 100.000 habitantes
4 | Entre 2.001 y 5.000 habitantes
5 | Hasta 2.000 habitantes
Epígrafe 721.2 Transporte por autotaxis
Valor | Descripción
0 | Blanco
1 | Más de 100.000 habitantes
2 | De 50.001 hasta 100.000 habitantes
3 | De 10.001 y 50.000 habitantes
4 | Entre 2.001 y 10.000 habitantes
5 | Hasta 2.000 habitantes
Resto de epígrafes
Valor | Descripción
0 | Blanco
1 | Hasta 2000 habitantes
2 | Desde 2.001 hasta 5.000
3 | Más de 5.000 habitantes
Nota 4:
Número de bateas y de barcos auxiliares de la empresa (epígrafe --- Producción de mejillón en batea)
Valor | Descripción
0 | Blanco
1 | Una batea y ningún barco
2 | Una batea y un barco de menos de 15 TRB
3 | Una batea y un barco de 15 a 30 TRB
4 | Una batea y un barco de más de 30 TRB
5 | Dos bateas y ningún barco
6 | Dos bateas y un barco de menos de 15 TRB
7 | Otros: número de bateas, barcos o TRB distintos de los anteriores
Nota 5:
Si en el año de devengo realiza la actividad en LORCA, seleccione lo que proceda
Valor | Descripción
0 | Blanco
1 | Actividad realizada esclusivamente en Lorca
2 | Actividad realizada en Lorca y en otros municipios
Si en el año de devengo realiza la actividad en la Isla de La Palma, seleccione lo que proceda
Valor | Descripción
0 | Blanco
1 | Actividad realizada esclusivamente en la Isla de la Palma
2 | Actividad realizada en la Isla de la Palma y en otros municipios
Si la actividad se realizó en alguno de los municipios afectados por la DANA entre el 28 de octubre y el 4 de noviembre de 2024 (RD-l 6/2024)
Valor | Descripción
0 | Blanco
1 | Actividad realizada exclusivamente en municipios afectados por la DANA.
2 | ActividActividad realizada en municipios afectados por la DANA y en otros municipios (vea la Ayuda).
Nota 6:
Exclusivamente para los epígrafes 644.1, 644.2, 644.3 y 644.6
Nota 7:
Para determinar el módulo de personal no asalariado:
En el caso del titular de la actividad, las horas deben consignarse sin la reducción por discapacidad.
En el caso del cónyuge y el hijo menor, las horas deben consignarse aplicando previamente la reducción del 75% sobre las horas trabajadas.
Nota 8:
El orden en el que se deben incluir los módulos debe ser el que se indique en la Orden de módulos correspondiente.

# DID

 | Agencia Tributaria
Modelo 131 |  | Diseño de registro.
 |  | IRPF. Empresarios y profesionales en Estimación Objetiva. Pago fraccionado.
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | Obligatorio | Constante "<T"
2 | 3 | 3 | An | Modelo. | Obligatorio | Constante "131"
3 | 6 | 5 | An | Página. | Obligatorio | Constante "DID00"
4 | 11 | 1 | An | Fin de identificador de modelo. | Obligatorio | Constante ">"
5 | 12 | 34 | An | Domiciliación - IBAN
6 | 46 | 200 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
7 | 246 | 12 | An | Indicador de fin de registro | Obligatorio | Constante "</T131DID00>"
TOTAL |  | 257 | POSICIONES