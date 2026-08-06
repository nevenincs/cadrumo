# M34100

 | Agencia Tributaria
Modelo 341
versión 1.0 |  | Diseño de registro
 |  | Declaración - Liquidación no periódica
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Constante. |  | "<T"
2 | 3 | 3 | An | Modelo |  | "341"
3 | 6 | 1 | An | Constante. |  | "0"
4 | 7 | 4 | An | Ejercicio devengo. (AAAA)
5 | 11 | 2 | An | Período. (PP) |  | "1T", "2T", "3T", "4T"
6 | 13 | 5 | An | Constante. |  | "0000>"
7 | 18 | 5 | An | Constante |  | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
9 | 93 | 4 | An | Versión del Programa (Nota 1)
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
11 | 101 | 9 | An | NIF Empresa Desarrollo (Nota 1)
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
13 | 323 | 6 | An | Constante |  | "</AUX>"
14 | 329 | Variable | An | Contenido del fichero.  Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T3410+Ejercicio+periodo+0000> |  | "</3410AAAAPP0000>"
Total |  | Variable
Nota 1 | A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW

# M34101

 | Agencia Tributaria
Modelo 341 |  | Diseño de registro. Castellano.
 |  | IVA. Declaración - Liquidación no periódica
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | Num | Modelo | Constante "341"
3 | 6 | 2 | An | Página | Constante "01"
4 | 8 | 4 | An | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An | Reservado para la Administración | En blanco
6 | 13 | 1 | A | Tipo de declaración | Ver nota 1
7 | 14 | 9 | An | Identificación - NIF
8 | 23 | 60 | An | Identificación -  Apellidos o Denominación Social
9 | 83 | 20 | An | Identificación-  Nombre
10 | 103 | 4 | Num | Devengo - Ejercicio
11 | 107 | 2 | An | Devengo - Periodo | "1T", "2T", "3T", "4T"
12 | 109 | 17 | Num | Compensación: Importe de las operaciones     [01] | [quince enteros + dos decimales]
13 | 126 | 17 | Num | Compensación: Importe de las operaciones     [02] | [quince enteros + dos decimales]
14 | 143 | 17 | Num | Compensación: Importe de las operaciones     [03] | [quince enteros + dos decimales]
15 | 160 | 5 | Num | Compensación: Porcentaje de compensación  [04] | [tres enteros + dos decimales]
16 | 165 | 5 | Num | Compensación: Porcentaje de compensación  [05] | [tres enteros + dos decimales]
17 | 170 | 5 | Num | Compensación: Porcentaje de compensación  [06] | [tres enteros + dos decimales]
18 | 175 | 17 | Num | Compensación: Importe de la compensación   [07] | [quince enteros + dos decimales]
19 | 192 | 17 | Num | Compensación: Importe de la compensación   [08] | [quince enteros + dos decimales]
20 | 209 | 17 | Num | Compensación: Importe de la compensación   [09] | [quince enteros + dos decimales]
21 | 226 | 17 | Num | Compensación: Importe total [07]+[08]+[09]… [10] | [quince enteros + dos decimales]
22 | 243 | 34 | An | IBAN
23 | 277 | 11 | An | SWIFT
24 | 288 | 488 | An | Reservado para la Administración | En blanco
25 | 776 | 13 | An | Reservado para el sello electrónico de la AEAT | En blanco
26 | 789 | 12 | An | Indicador de fin de registro | Constante "</T34101000>"
 | TOTAL | 800 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: D (Devolución)
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  | POSICIONES