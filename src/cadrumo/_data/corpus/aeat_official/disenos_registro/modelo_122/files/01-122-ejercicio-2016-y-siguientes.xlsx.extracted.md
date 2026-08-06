# Pag. 0

 | Agencia Tributaria
Modelo 122 |  | Diseño de registro. Castellano.
vers.18.13 |  | Impuesto sobre la Renta de las Personas Físicas
Deducciones por familia numerosa, por personas con discapacidad a cargo o por cada descendiente con dos hijos separado legalment o sin vinculo matrimonial.
Regularización del derecho a la deducción por contribuyentes no obligados a presentar declaración.
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. |  | Constante "<T"
2 | 3 | 3 | An | Modelo. |  | Constante "122"
3 | 6 | 1 | An | Discriminante |  | Constante "0"
4 | 7 | 4 | An | Ejercicio de devengo (EEEE)
5 | 11 | 2 | An | Periodo |  | "0A"
6 | 13 | 5 | An | Tipo y cierre |  | "0000>"
7 | 18 | 5 | An | Constante |  | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
9 | 93 | 4 | An | Versión del Programa (Nota 1)
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
11 | 101 | 9 | An | NIF Empresa Desarrollo (Nota 1)
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
13 | 323 | 6 | An | Constante |  | "</AUX>"
14 | 329 | variable | An | Contenido del fichero. Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T+ modelo+discriminante+Ejercicio+periodo+Tipo+> |  | "</T1220EEEE0A0000>"
TOTAL |  | variable | POSICIONES
Nota 1:
A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
Nota2:
1. Los campos deben ser A (Alfabético) An (Alfanumérico), Num (Numérico sin signo) o N (Numérico con signo).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.

# Pag. 1

 | Agencia Tributaria
Modelo 122 |  | Diseño de registro. Castellano.
 |  | Impuesto sobre la Renta de las Personas Físicas
Deducciones por familia numerosa, por personas con discapacidad a cargo o por cada descendiente con dos hijos separado legalment o sin vinculo matrimonial.
Regularización del derecho a la deducción por contribuyentes no obligados a presentar declaración.
Nº | Posic. | Lon | Tipo | Comp | Descripción | Contenido
1 | 1 | 2 | An |  | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Constante "122"
3 | 6 | 2 | Num |  | Página | Constante "01"
4 | 8 | 4 | An |  | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | A |  | Indicador de página complementaria | C o blanco
6 | 13 | 1 | A |  | Tipo de declaración | Ver nota 1
7 | 14 | 9 | An |  | 1.Contribuyente no obligado a presentar declaración - N.I.F.
8 | 23 | 60 | An |  | 1.Contribuyente no obligado a presentar declaración - Apellidos
9 | 83 | 20 | An |  | 1.Contribuyente no obligado a presentar declaración - Nombre
10 | 103 | 4 | Num |  | Periodo Impositivo. Ejercicio.
11 | 107 | 2 | An |  | Reservado AEAT (Periodo) | Constante "0A"
12 | 109 | 129 | An |  | Reservado AEAT
13 | 238 | 17 | Num |  | 2.Regularización deducciones. Cónyuge no separado con discapacidad - Importe de la deducción. [574]
14 | 255 | 17 | Num |  | 2.Regularización deducciones. Cónyuge no separado con discapacidad -  Importe del abono anticipado. [575]
15 | 272 | 9 | An | C | 2.Regularización abono anticipado deducciones. Descendientes discapacidad - N.I.F. [548]
16 | 281 | 60 | An | C | 2.Regularización deducciones. Descendientes discapacidad - Apellidos y nombre. [549]
17 | 341 | 20 | An |  | Reservado para la Administracion
18 | 361 | 17 | Num | C | 2.Regularización deducciones. Descendientes discapacidad - Importe de la deducción. [557]
19 | 378 | 17 | Num | C | 2.Regularización deducciones. Descendientes discapacidad - Importe del abono anticipado. [558]
20 | 395 | 9 | An | C | 2.Regularización deducciones. Ascendientes discapacidad - N.I.F. [561]
21 | 404 | 60 | An | C | 2.Regularización deducciones. Ascendientes discapacidad - Apellidos y nombre. [562]
22 | 464 | 20 | An |  | Reservado para la Administracion
23 | 484 | 17 | Num | C | 2.Regularización deducciones. Ascendientes discapacidad - Importe de la deducción. [572]
24 | 501 | 17 | Num | C | 2.Regularización deducciones. Ascendientes discapacidad -  Importe del abono anticipado. [573]
25 | 518 | 30 | An | C | 2.Regularización deducciones. Familia numerosa - Nº identificación titulo familia numerosa. [576]
26 | 548 | 17 | Num | C | 2.Regularización deducciones. Familia numerosa - Importe de la deducción. [588]
27 | 565 | 17 | Num | C | 2.Regularización deducciones. Familia numerosa -  Importe del abono anticipado. [589]
28 | 582 | 17 | Num | C | 2.Regularización deducciones. Separado o sin vinculo, dos hijos -  Importe de la deducción. [590]
29 | 599 | 17 | Num | C | 2.Regularización deducciones. Separado o sin vinculo, dos hijos -  Imp del abono anticipado. [591]
30 | 616 | 17 | Num |  | 3.Resultado de la regularización a ingresar (558-557+573-572+589-588+591-590) [595]
31 | 633 | 34 | An |  | 4.(Solo para Predeclaraciones). Ingreso. IBAN
32 | 667 | 1 | An |  | 5.Autoliquidación complementaria - Autoliquidación anterior. | X o blanco
33 | 668 | 13 | An |  | 5.Autoliquidación complementaria - Nº de justificante.
34 | 681 | 9 | An |  | 6.Representante. N.I.F.
35 | 690 | 60 | An |  | 6.Representante. Apellidos  o razón social.
36 | 750 | 20 | An |  | 6.Representante. Nombre.
37 | 770 | 206 | An |  | Reservado para la Administracion
38 | 976 | 13 | An |  | Reservado para el sello electrónico de la AEAT
39 | 989 | 12 | An |  | Indicador de fin de registro | Constante "</T12201000>"
 | TOTAL | 1000 | POSICIONES
1. El tipo de declaración para la presentación puede ser: I (ingreso)
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  |  | POSICIONES