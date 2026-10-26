# Pág. 0

 | Agencia Tributaria
Modelo 131 |  | Diseño de registro.
vers.1.01 |  | IRPF. Empresarios y profesionales en Estimación Objetiva. Pago fraccionado.
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
Nota1:
A cumplimentar por las entidades desarrolladoras (EEDD):
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
Nota2:
EEEE indica las cuatro cifras del ejercicio en curso
Nota3:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.

# Pág. 1

 | Agencia Tributaria
Modelo 131 |  | Diseño de registro.
vers.1.01 |  | IRPF. Empresarios y profesionales en Estimación Objetiva. Pago fraccionado.
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
12 | 109 | 4 | An | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad (epígrafe I.A.E.) - 1
13 | 113 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Rdto. neto actividad - 1 |  | 15 enteros y 2 decimales
14 | 130 | 5 | Num | Liquidación (3) - I. Activ. económicas estimac. objetiva - Porcentaje aplicable 1 |  | 3 enteros y 2 decimales
15 | 135 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Resultado aplicación porcentaje a cada actividad - 1 |  | 15 enteros y 2 decimales
16 | 152 | 4 | An | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad (epígrafe I.A.E.) - 2
17 | 156 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Rdto. neto actividad - 2 |  | 15 enteros y 2 decimales
18 | 173 | 5 | Num | Liquidación (3) - I. Activ. económicas estimac. objetiva - Porcentaje aplicable 2 |  | 3 enteros y 2 decimales
19 | 178 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Resultado aplicación porcentaje a cada actividad - 2 |  | 15 enteros y 2 decimales
20 | 195 | 4 | An | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad (epígrafe I.A.E.) - 3
21 | 199 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Rdto. neto actividad - 3 |  | 15 enteros y 2 decimales
22 | 216 | 5 | Num | Liquidación (3) - I. Activ. económicas estimac. objetiva - Porcentaje aplicable 3 |  | 3 enteros y 2 decimales
23 | 221 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Resultado aplicación porcentaje a cada actividad - 3 |  | 15 enteros y 2 decimales
24 | 238 | 4 | An | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad (epígrafe I.A.E.) - 4
25 | 242 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Rdto. neto actividad - 4 |  | 15 enteros y 2 decimales
26 | 259 | 5 | Num | Liquidación (3) - I. Activ. económicas estimac. objetiva - Porcentaje aplicable 4 |  | 3 enteros y 2 decimales
27 | 264 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Resultado aplicación porcentaje a cada actividad - 4 |  | 15 enteros y 2 decimales
28 | 281 | 4 | An | Liquidación (3) - I. Activ. económicas estimac. objetiva - Actividad (epígrafe I.A.E.) - 5
29 | 285 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Rdto. neto actividad - 5 |  | 15 enteros y 2 decimales
30 | 302 | 5 | Num | Liquidación (3) - I. Activ. económicas estimac. objetiva - Porcentaje aplicable 5 |  | 3 enteros y 2 decimales
31 | 307 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Resultado aplicación porcentaje a cada actividad - 5 |  | 15 enteros y 2 decimales
32 | 324 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Suma de rendimientos netos [01] |  | 15 enteros y 2 decimales
33 | 341 | 17 | N | Liquidación (3) - I. Activ. económicas estimac. objetiva - Pago fraccionado previo: suma de resultados [02] |  | 15 enteros y 2 decimales
34 | 358 | 17 | N | Liquidación (3) - II. Activ. económicas estimac. objetiva distintas - Volumen de ventas o ingresos [03] |  | 15 enteros y 2 decimales
35 | 375 | 17 | N | Liquidación (3) - II. Activ. económicas estimac. objetiva distintas - Pago fraccionado previo [04] |  | 15 enteros y 2 decimales
36 | 392 | 17 | N | Liquidación (3) - III. Activ. agrícolas, ganaderas estimac. objet. - Volumen ingresos trimestre [05] |  | 15 enteros y 2 decimales
37 | 409 | 17 | N | Liquidación (3) - III. Activ. agrícolas, ganaderas estimac. objet. - Pago fraccionado previo del trimestre [06] |  | 15 enteros y 2 decimales
38 | 426 | 17 | N | Liquidación (3) - IV. Total liquidación - Suma de los pagos fraccionados previos del trimestre [07] |  | 15 enteros y 2 decimales
39 | 443 | 17 | N | Liquidación (3) - IV. Total liquidación - A deducir: retenciones e ingresos a cuenta [08] |  | 15 enteros y 2 decimales
40 | 460 | 17 | N | Liquidación (3) - IV. Total liquidación - Minoración por aplicación de la deducción. Artículo 110.3.c de la Ley [09] |  | 15 enteros y 2 decimales
41 | 477 | 17 | N | Liquidación (3) - IV. Total liquidación - Diferencia [10] |  | 15 enteros y 2 decimales
42 | 494 | 17 | N | Liquidación (3) - IV. Total liquidación - A deducir: Resultados negativos de trimestres anteriores [11] |  | 15 enteros y 2 decimales
43 | 511 | 17 | N | Liquidación (3) - IV. Total liquidación - Pago de préstamos para la adquisición de vivienda habitual [12] |  | 15 enteros y 2 decimales
44 | 528 | 17 | N | Liquidación (3) - IV. Total liquidación - Total [13] |  | 15 enteros y 2 decimales
45 | 545 | 17 | N | Liquidación (3) - IV. Total liquidación - A deducir - Resultado a ingresar de las anteriores declaraciones [14] |  | 15 enteros y 2 decimales
46 | 562 | 17 | N | Liquidación (3) - IV. Total liquidación - Resultado de la declaración [15] |  | 15 enteros y 2 decimales
47 | 579 | 34 | An | Domiciliación - IBAN
48 | 613 | 1 | An | Complementaria (7) - Declaración complementaria |  | blanco o "X"
49 | 614 | 13 | An | Complementaria (7) - Número justificante declaración anterior
50 | 627 | 1 | An | RESERVADO PARA LA A.E.A.T. |  | "0" o blanco
51 | 628 | 99 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
52 | 727 | 13 | An | SELLO ELECTRONICO RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
53 | 740 | 12 | An | Indicador de fin de registro | Obligatorio | Constante "</T13101000>"
TOTAL |  | 751 | POSICIONES
Nota1: El tipo de autoliquidación puede ser: I (ingreso) N (negativa) G (ingreso a anotar en CCT) U (domiciliación del ingreso en CCC) B (Resultado a deducir)
Nota2:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.