# Pag. 1

Agencia Tributaria
Modelo111 Diseño de registro.
vers. 1.6 IMPUESTO SOBRE LA RENTA DE LAS PERSONAS FÍSICAS (retenciones e ingresos a cuenta)
Nº Posic. Lon Tipo Descripción Contenido
1 1 2 An Inicio del identificador de modelo y página Constante "<T"
2 3 3 Num Modelo Constante "111"
3 6 2 Num Página Constante "01"
4 8 1 An Fin de identificador de modelo Constante ">"
5 9 1 A Indicador de página complementaria En blanco
6 10 1 A Tipo de declaración Ver nota
7 11 9 An Identificación. Sujeto pasivo. NIF
8 20 45 An Identificación. Sujeto pasivo. Denominación (o Apellidos y Nombre)
9 65 4 Num Identificación. Ejercicio
10 69 2 An Identificación. Periodo "01" ... "12" o "1T" … "4T"
11 71 8 N Rendim. del trabajo - Rendimientos dinerarios - Nº de perceptores
12 79 17 N Rendim. del trabajo - Rendimientos dinerarios - Importe percepciones [quince enteros + dos decimales]
13 96 17 N Rendim. del trabajo - Rendimientos dinerarios - Importe retenciones [quince enteros + dos decimales]
14 113 8 N Rendim. del trabajo - Rendimientos en especie- Nº de perceptores
15 121 17 N Rendim. del trabajo - Rendimientos en especie- Valor percepciones en especie [quince enteros + dos decimales]
16 138 17 N Rendim. del trabajo - Rendimientos en especie- Importe ingresos a cuenta [quince enteros + dos decimales]
17 155 8 N Rendim. actividades económicas - Rendimientos dinerarios -Nº de perceptores
18 163 17 N Rendim. actividades económicas - Rendimientos dinerarios -Importe percepciones [quince enteros + dos decimales]
19 180 17 N Rendim. actividades económicas - Rendimientos dinerarios -Importe retenciones [quince enteros + dos decimales]
20 197 8 N Rendim. actividades económicas - Rendimientos en especie -Nº de perceptores
21 205 17 N Rendim. actividades económicas - Rendimientos en especie-Valor percepciones en especie [quince enteros + dos decimales]
22 222 17 N Rendim. actividades económicas - Rendimientos en especie- Importe de los ingresos a cuenta [quince enteros + dos decimales]
23 239 8 N Premios- Premios dinerarios - Nº de perceptores
24 247 17 N Premios - Premios dinerarios - Importe de las percepciones [quince enteros + dos decimales]
25 264 17 N Premios - Premios dinerarios - Importe de las retenciones [quince enteros + dos decimales]
26 281 8 N Premios - Premios en especie - Nº de perceptores
27 289 17 N Premios - Premios en especie - Valor percepciones en especie [quince enteros + dos decimales]
28 306 17 N Premios - Premios en especie - Importe de los ingresos a cuenta [quince enteros + dos decimales]
29 323 8 N Ganancias patrim. Aprovecham. Forestales - Percep. dinerarias - Nº perceptores
30 331 17 N Ganancias patrim. Aprovecham. Forestales - Percep. dinerarias - Importe percepciones [quince enteros + dos decimales]
31 348 17 N Ganancias patrim. Aprovecham. Forestales - Percep. dinerarias - Importe retenciones [quince enteros + dos decimales]
32 365 8 N Ganancias patrim. Aprovecham. Forestales - Percep. en especie - Nº perceptores
33 373 17 N Ganancias patrim. Aprovecham. Forestales - Percep. en especie - Importe percepciones [quince enteros + dos decimales]
34 390 17 N Ganancias patrim. Aprovecham. Forestales - Percep. en especie - Importe ingresos a cuenta [quince enteros + dos decimales]
35 407 8 N Contraprest. cesión dchos. imagen - Nº de perceptores -
36 415 17 N Contraprest. cesión dchos. imagen - Contraprestaciones satisfechas [quince enteros + dos decimales]
37 432 17 N Contraprest. cesión dchos. imagen - Importe de los ingresos a cuenta [quince enteros + dos decimales]
38 449 17 N Total liquidación - Suma retenciones e ingresos a cuenta [quince enteros + dos decimales]
39 466 17 N Total liquidación - Resultado de anteriores declaraciones [quince enteros + dos decimales]
40 483 17 N Total liquidación - Resultado a ingresar [quince enteros + dos decimales]
41 500 4 An Código cuenta cliente - entidad
Página 1 de 2

# Pag. 2

Nº Posic. Lon Tipo Descripción Contenido
42 504 4 An Código cuenta cliente - sucursal
43 508 2 An Código cuenta cliente - DC
44 510 10 An Código cuenta cliente - Número de cuenta
45 520 1 Num Declaración complementaria "0" - "1"
46 521 13 An Número de justificante de la declaración anterior
47 534 16 An Reservado para la Administración
48 550 100 An Nombre y apellidos de la persona de contacto
49 650 9 An Teléfono fijo de contacto
50 659 9 An Teléfono móvil de contacto
51 668 50 An Dirección de correo electrónico
52 718 13 An Reservado para el sello electrónico de la AEAT En blanco
53 731 1 An Reservado para la Administración En blanco
54 732 1 An Reservado. Administración presentando declaración de Colegio Concertado (CC) "X" o blanco
55 733 459 An Reservado para la Administración En blanco
56 1192 9 An Indicador de fin de registro Constante "</T11101>"
TOTAL 1200 POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: I (ingreso), U (domiciliación), G (ingreso a anotar en CCT) y N (negativa)
2. Para facilitar la incorporación de datos al formulario se espera que el fichero esté localizado en C:\AEAT\ y que su nombre sea 111.txt
3. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
4. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
6. Los datos numéricos negativos llevarán una N en la primera posición del campo.
Página 2 de 2