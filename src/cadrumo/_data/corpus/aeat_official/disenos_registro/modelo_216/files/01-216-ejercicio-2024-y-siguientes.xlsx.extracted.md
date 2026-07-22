# Pág. 0

 | Agencia Tributaria
Modelo 216 |  | Diseño de registro. Castellano.
 |  | RETENCIONES E INGRESOS A CUENTA IMPUESTO SOBRE LA RENTA DE NO RESIDENTES. RENTAS OBTENIDAS SIN MEDIACIÓN DE ESTABLECIMIENTO PERMANENTE
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. |  | Constante "<T"
2 | 3 | 3 | An | Modelo. |  | Constante "216"
3 | 6 | 1 | An | Discriminante |  | Constante "0"
4 | 7 | 4 | An | Ejercicio de devengo (AAAA) |  | >= 2024
5 | 11 | 2 | An | Periodo (PP) |  | 01.."12" o "1T".."4T"
6 | 13 | 5 | An | Tipo y cierre |  | "0000>"
7 | 18 | 5 | An | Constante |  | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
9 | 93 | 4 | An | Versión del Programa (**)
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos
11 | 101 | 9 | An | NIF Empresa Desarrollo (**)
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
13 | 323 | 6 | An | Constante |  | "</AUX>"
14 | 329 | variable | An | Contenido del fichero. Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T+ modelo+discriminante+Ejercicio+periodo+Tipo+> |  | "</T2160AAAAPP0000>"
TOTAL |  | variable | POSICIONES
 |  |  |  | (**) A cumplimentar por las entidades desarrolladoras (EEDD)
 |  |  |  | Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
 |  |  |  | NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
Nota2:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.

# Pág. 1

 | Agencia Tributaria
Modelo 216 |  | Diseño de registro. Castellano.
 |  | RETENCIONES E INGRESOS A CUENTA IMPUESTO SOBRE LA RENTA DE NO RESIDENTES. RENTAS OBTENIDAS SIN MEDIACIÓN DE ESTABLECIMIENTO PERMANENTE
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. | Obligatorio | Constante "<T"
2 | 3 | 3 | An | Modelo. | Obligatorio | Constante "216"
3 | 6 | 5 | An | Página. | Obligatorio | Constante "01000"
4 | 11 | 1 | An | Fin de identificador de modelo. | Obligatorio | Constante ">"
5 | 12 | 1 | A | Indicador de página complementaria. |  | En blanco
6 | 13 | 1 | A | Tipo de autoliquidación | Obligatorio | Ver Nota1
7 | 14 | 9 | An | Identificación  - Nif [03] | Obligatorio
8 | 23 | 80 | An | Identificación - Apellidos y nombre o razón social [04] | Obligatorio
9 | 103 | 4 | Num | Devengo - Ejercicio [01] | Obligatorio | >= 2024
10 | 107 | 2 | An | Devengo - Período [02] | Obligatorio | "01".."12" o "1T".."4T"
11 | 109 | 17 | Num | Liquidación - I Rentas sometidas a retención o ingreso a cuenta - Dividendos y otras rentas de participación en fondos propios de entidades - Número Rentas [05] |  | [entero 17 posiciones]
12 | 126 | 17 | Num | Liquidación - I Rentas sometidas a retención o ingreso a cuenta - Resto de rentas - Número Rentas [06] |  | [entero 17 posiciones]
13 | 143 | 17 | Num | Liquidación - I Rentas sometidas a retención o ingreso a cuenta - Totales - Número Rentas [07] |  | [entero 17 posiciones]
14 | 160 | 17 | Num | Liquidación - I Rentas sometidas a retención o ingreso a cuenta - Dividendos y otras rentas de participación en fondos propios de entidades - Base de retenciones e ingresos a cuenta [08] |  | [15 enteros + 2 decimales]
15 | 177 | 17 | Num | Liquidación - I Rentas sometidas a retención o ingreso a cuenta - Resto de rentas - Base de retenciones e ingresos a cuenta [09] |  | [15 enteros + 2 decimales]
16 | 194 | 17 | Num | Liquidación - I Rentas sometidas a retención o ingreso a cuenta - Totales - Base de retenciones e ingresos a cuenta [10] |  | [15 enteros + 2 decimales]
17 | 211 | 17 | Num | Liquidación - I Rentas sometidas a retención o ingreso a cuenta - Dividendos y otras rentas de participación en fondos propios de entidades - Retenciones e ingresos a cuenta [11] |  | [15 enteros + 2 decimales]
18 | 228 | 17 | Num | Liquidación - I Rentas sometidas a retención o ingreso a cuenta - Resto de rentas - Retenciones e ingresos a cuenta [12] |  | [15 enteros + 2 decimales]
19 | 245 | 17 | Num | Liquidación - I Rentas sometidas a retención o ingreso a cuenta - Totales - Retenciones e ingresos a cuenta [13] |  | [15 enteros + 2 decimales]
20 | 262 | 17 | Num | Liquidación - II Rentas no sometidas a retención o ingreso a cuenta - Dividendos y otras rentas de participación en fondos propios de entidades - Número Rentas [14] |  | [entero 17 posiciones]
21 | 279 | 17 | Num | Liquidación - II Rentas no sometidas a retención o ingreso a cuenta - Resto de rentas - Número Rentas [15] |  | [entero 17 posiciones]
22 | 296 | 17 | Num | Liquidación - II Rentas no sometidas a retención o ingreso a cuenta - Totales - Número Rentas [16] |  | [entero 17 posiciones]
23 | 313 | 17 | Num | Liquidación - II Rentas no sometidas a retención o ingreso a cuenta - Dividendos y otras rentas de participación en fondos propios de entidades - Base de retenciones e ingresos a cuenta [17] |  | [15 enteros + 2 decimales]
24 | 330 | 17 | Num | Liquidación - II Rentas no sometidas a retención o ingreso a cuenta - Resto de rentas - Base de retenciones e ingresos a cuenta [18] |  | [15 enteros + 2 decimales]
25 | 347 | 17 | Num | Liquidación - II Rentas no sometidas a retención o ingreso a cuenta - Totales - Base de retenciones e ingresos a cuenta [19] |  | [15 enteros + 2 decimales]
26 | 364 | 17 | Num | Liquidación - Resultados a ingresar de anteriores autoliquidaciones por el mismo concepto, ejercicio y período [20] |  | [15 enteros + 2 decimales]
27 | 381 | 17 | Num | Liquidación - Resultado a ingresar ([13] - [20]) [21] |  | [15 enteros + 2 decimales]
28 | 398 | 34 | An | Domiciliación - IBAN
29 | 432 | 1 | An | Complementaria - Declaración complementaria |  | blanco o "X"
30 | 433 | 13 | An | Complementaria - Número justificante declaración anterior
31 | 446 | 143 | An | RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
32 | 589 | 12 | An | Indicador de fin de registro | Obligatorio | Constante "</T21601000>"
TOTAL |  | 600 | POSICIONES
Nota1: El tipo de declaración puede ser: I (ingreso) N (negativa) G (ingreso a anotar en CCT) U (domiciliación del ingreso en CCC)
Nota2:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.