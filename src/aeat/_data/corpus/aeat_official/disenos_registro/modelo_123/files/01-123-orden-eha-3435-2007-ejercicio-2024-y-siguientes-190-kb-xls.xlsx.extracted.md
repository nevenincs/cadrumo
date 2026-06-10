# DR 12300

 | Agencia Tributaria
Modelo 123
versión 2.0 |  | Diseño de registro
 |  | Impuesto sobre la Renta de las Personas Físicas
Retenciones e ingresos a cuenta sobre determinados rendimientos del capital mobiliario
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes)
Retenciones e ingresos a cuenta sobre determinadas rentas
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Constante. |  | "<T"
2 | 3 | 3 | An | Modelo |  | "123"
3 | 6 | 1 | An | Constante. |  | "0"
4 | 7 | 4 | An | Ejercicio devengo. (AAAA)
5 | 11 | 2 | An | Período. (PP) |  | "01" ... "12" o "1T" … "4T"
6 | 13 | 5 | An | Constante. |  | "0000>"
7 | 18 | 5 | An | Constante |  | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
9 | 93 | 4 | An | Versión del Programa (Nota 1)
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
11 | 101 | 9 | An | NIF Empresa Desarrollo (Nota 1)
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
13 | 323 | 6 | An | Constante |  | "</AUX>"
14 | 329 | Variable | An | Contenido del fichero.  Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T1230+Ejercicio+periodo+0000> |  | "</T1230AAAAPP0000>"
Total |  | Variable
Nota 1 | A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW

# DR 12301

 | Agencia Tributaria
Modelo 123 |  | Diseño de registro.
versión 2.0 |  | Impuesto sobre la Renta de las Personas Físicas
Retenciones e ingresos a cuenta sobre determinados rendimientos del capital mobiliario
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes)
Retenciones e ingresos a cuenta sobre determinadas rentas
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | Num | Modelo | Constante "123"
3 | 6 | 2 | Num | Página | Constante "01"
4 | 8 | 4 | An | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | A | Indicador de página complementaria | En blanco
6 | 13 | 1 | A | Tipo de declaración | Ver nota 1
7 | 14 | 9 | An | Identificación(1). Sujeto pasivo. NIF
8 | 23 | 80 | An | Identificación(1). Sujeto pasivo. Razón/denominación social, apellidos y nombre
9 | 103 | 4 | Num | Devengo(2). Ejercicio
10 | 107 | 2 | An | Devengo(2). Periodo | "01" ... "12" o "1T" … "4T"
11 | 109 | 15 | Num | Liquidación(3). Número de rentas. Dividendos y otras rentas (...) [01]
12 | 124 | 15 | Num | Liquidación(3). Número de rentas. Resto de rentas [02]
13 | 139 | 15 | Num | Liquidación(3). Número de rentas. Totales [03]
14 | 154 | 17 | Num | Liquidación(3). Base de retenciones e ingresos a cuenta. Dividendos y otras rentas (...) [04] | [quince enteros + dos decimales]
15 | 171 | 17 | Num | Liquidación(3). Base de retenciones e ingresos a cuenta. Resto de rentas [05] | [quince enteros + dos decimales]
16 | 188 | 17 | Num | Liquidación(3). Base de retenciones e ingresos a cuenta. Totales [06] | [quince enteros + dos decimales]
17 | 205 | 17 | Num | Liquidación(3). Retenciones e ingresos a cuenta. Dividendos y otras rentas (...) [07] | [quince enteros + dos decimales]
18 | 222 | 17 | Num | Liquidación(3). Retenciones e ingresos a cuenta. Resto de rentas [08] | [quince enteros + dos decimales]
19 | 239 | 17 | Num | Liquidación(3). Retenciones e ingresos a cuenta. Totales [09] | [quince enteros + dos decimales]
20 | 256 | 17 | Num | Liquidación(3). Periodificación. Ingresos ejercicios anteriores [10] | [quince enteros + dos decimales]
21 | 273 | 17 | Num | Liquidación(3). Periodificación. Regularización. [11] | [quince enteros + dos decimales]
22 | 290 | 17 | Num | Liquidación(3). Suma de retenciones e ingresos a cuenta y regularización, en su caso ( [09] + [11] ) [12] | [quince enteros + dos decimales]
23 | 307 | 17 | Num | Liquidación(3). Resultados a ingresar de anteriores autoliquidaciones por el mismo concepto, ejercicio y periodo [13] | [quince enteros + dos decimales]
24 | 324 | 17 | Num | Liquidación(3). Resultado a ingresar ( [12] - [13] ) [14] | [quince enteros + dos decimales]
25 | 341 | 1 | An | Declaración complementaria. | blanco o "X"
26 | 342 | 13 | An | Número de justificante de la declaración anterior
27 | 355 | 34 | An | Domiciliación IBAN
28 | 389 | 200 | An | Reservado AEAT | En blanco
29 | 589 | 12 | An | Indicador de fin de registro. | Constante "</T12301000>"
 | TOTAL | 600 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: I (ingreso), U (domiciliación), G (ingreso a anotar en CCT) y N (negativa)
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  | POSICIONES