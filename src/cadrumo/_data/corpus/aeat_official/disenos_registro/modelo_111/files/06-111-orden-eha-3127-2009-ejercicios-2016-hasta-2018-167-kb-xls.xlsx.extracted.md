# M11100

 | Agencia Tributaria
Modelo 111
vers 1.7 |  | Diseño de registro
 |  | IMPUESTO SOBRE LA RENTA DE LAS PERSONAS FÍSICAS (retenciones e ingresos a cuenta)
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Constante. |  | "<T"
2 | 3 | 3 | An | Modelo |  | "111"
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
15 | *** | 18 | An | Constante. </T1110+Ejercicio+periodo+0000> |  | "</T1110AAAAPP0000>"
16 | *** | 2 | An | Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total |  | Variable
Nota 1 | A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW

# dr M11101

 | Agencia Tributaria
Modelo111 |  | Diseño de registro.
 |  | IMPUESTO SOBRE LA RENTA DE LAS PERSONAS FÍSICAS (retenciones e ingresos a cuenta)
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | Num | Modelo | Constante "111"
3 | 6 | 2 | Num | Página | Constante "01"
4 | 8 | 4 | An | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | A | Indicador de página complementaria | En blanco
6 | 13 | 1 | A | Tipo de declaración | Ver nota
7 | 14 | 9 | An | Identificación. Sujeto pasivo. NIF
8 | 23 | 60 | An | Identificación. Sujeto pasivo. Denominación o Apellidos
9 | 83 | 20 | An | Identificación. Sujeto pasivo. Nombre
10 | 103 | 4 | Num | Identificación. Ejercicio
11 | 107 | 2 | An | Identificación. Periodo | "01" ... "12" o "1T" … "4T"
12 | 109 | 8 | N | Rendim. del trabajo - Rendimientos dinerarios - Nº de perceptores
13 | 117 | 17 | N | Rendim. del trabajo - Rendimientos dinerarios - Importe percepciones | [quince enteros + dos decimales]
14 | 134 | 17 | N | Rendim. del trabajo - Rendimientos dinerarios - Importe retenciones | [quince enteros + dos decimales]
15 | 151 | 8 | N | Rendim. del trabajo - Rendimientos en especie- Nº de perceptores
16 | 159 | 17 | N | Rendim. del trabajo - Rendimientos en especie- Valor percepciones en especie | [quince enteros + dos decimales]
17 | 176 | 17 | N | Rendim. del trabajo - Rendimientos en especie- Importe ingresos a cuenta | [quince enteros + dos decimales]
18 | 193 | 8 | N | Rendim. actividades económicas - Rendimientos dinerarios -Nº de perceptores
19 | 201 | 17 | N | Rendim. actividades económicas - Rendimientos dinerarios -Importe percepciones | [quince enteros + dos decimales]
20 | 218 | 17 | N | Rendim. actividades económicas - Rendimientos dinerarios -Importe retenciones | [quince enteros + dos decimales]
21 | 235 | 8 | N | Rendim. actividades económicas - Rendimientos en especie -Nº de perceptores
22 | 243 | 17 | N | Rendim. actividades económicas - Rendimientos en especie-Valor percepciones en especie | [quince enteros + dos decimales]
23 | 260 | 17 | N | Rendim. actividades económicas - Rendimientos en especie- Importe de los ingresos a cuenta | [quince enteros + dos decimales]
24 | 277 | 8 | N | Premios- Premios dinerarios - Nº  de perceptores
25 | 285 | 17 | N | Premios - Premios dinerarios - Importe de las percepciones | [quince enteros + dos decimales]
26 | 302 | 17 | N | Premios - Premios dinerarios - Importe de las retenciones | [quince enteros + dos decimales]
27 | 319 | 8 | N | Premios - Premios en especie - Nº de perceptores
28 | 327 | 17 | N | Premios - Premios en especie - Valor percepciones en especie | [quince enteros + dos decimales]
29 | 344 | 17 | N | Premios - Premios en especie - Importe de los ingresos a cuenta | [quince enteros + dos decimales]
30 | 361 | 8 | N | Ganancias patrim. Aprovecham. Forestales - Percep. dinerarias - Nº perceptores
31 | 369 | 17 | N | Ganancias patrim. Aprovecham. Forestales - Percep. dinerarias - Importe percepciones | [quince enteros + dos decimales]
32 | 386 | 17 | N | Ganancias patrim. Aprovecham. Forestales - Percep. dinerarias - Importe retenciones | [quince enteros + dos decimales]
33 | 403 | 8 | N | Ganancias patrim. Aprovecham. Forestales - Percep. en especie - Nº perceptores
34 | 411 | 17 | N | Ganancias patrim. Aprovecham. Forestales - Percep. en especie - Importe percepciones | [quince enteros + dos decimales]
35 | 428 | 17 | N | Ganancias patrim. Aprovecham. Forestales - Percep. en especie - Importe ingresos a cuenta | [quince enteros + dos decimales]
36 | 445 | 8 | N | Contraprest. cesión dchos. imagen - Nº de perceptores -
37 | 453 | 17 | N | Contraprest. cesión dchos. imagen - Contraprestaciones satisfechas | [quince enteros + dos decimales]
38 | 470 | 17 | N | Contraprest. cesión dchos. imagen - Importe de los ingresos a cuenta | [quince enteros + dos decimales]
39 | 487 | 17 | N | Total liquidación - Suma retenciones e ingresos a cuenta | [quince enteros + dos decimales]
40 | 504 | 17 | N | Total liquidación - Resultado de anteriores declaraciones | [quince enteros + dos decimales]
41 | 521 | 17 | N | Total liquidación - Resultado a ingresar | [quince enteros + dos decimales]
42 | 538 | 1 | An | Declaración complementaria | "X" o blanco
43 | 539 | 13 | An | Número de justificante de la declaración anterior
44 | 552 | 1 | An | Reservado. Administración presentando declaración de Colegio Concertado (CC) | "X" o blanco
45 | 553 | 34 | An | Domiciliación - IBAN
46 | 587 | 389 | An | Reservado para la Administración | En blanco
47 | 976 | 13 | An | Reservado para el sello electrónico de la AEAT
48 | 989 | 12 | An | Indicador de fin de registro | Constante "</T11101000>"
 | TOTAL | 1000 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: I (ingreso), U (domiciliación), G (ingreso a anotar en CCT) y N (negativa)
2. Para facilitar la incorporación de datos al formulario se espera que el fichero esté localizado en C:\AEAT\ y que su nombre sea 111.txt
3. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
4. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
6. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  | POSICIONES