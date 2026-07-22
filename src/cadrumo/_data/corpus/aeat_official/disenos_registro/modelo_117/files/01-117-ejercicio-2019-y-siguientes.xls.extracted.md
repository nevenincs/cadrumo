# DR 11700

 | Agencia Tributaria
Modelo 117
versión 1.4 |  | Diseño de registro
 |  | Impuesto sobre la Renta de las Personas Físicas.
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Constante. |  | "<T"
2 | 3 | 3 | An | Modelo |  | "117"
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
15 | *** | 18 | An | Constante. </T1170+Ejercicio+periodo+0000> |  | "</T1170AAAAPP0000>"
Total |  | Variable
Nota 1 | A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
Nota 2
El número máximo de ocurrencias de la página 2 son 6 para las actividades del régimen agrícolas, ganaderas y forestales; y 6 para las actividades
del régimen simplificado(excepto agrícolas, ganaderas y forestales). Por lo que el número máximo de páginas 2 será 3.

# DR 11701

 | Agencia Tributaria
Modelo 117 |  | Diseño de registro.
 |  | Impuesto sobre la Renta de las Personas Físicas.
IRPF e Impuesto sobre Sociedades e Impuestos sobre la Renta de no residentes. Retenciones e ingresos a cuenta/pago a cuenta sobre rentas o ganancias patrimoniales obtenidas como consecuencia de las transmisiones o reembolsos de acciones y participaciones representativas del capital o del patrimonio de las instituciones de inversión colectiva y de las transmisiones de derechos de suscripción.
Nº | Posic. | Lon. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página |  | Constante "<T"
2 | 3 | 3 | Num | Modelo |  | Constante "117"
3 | 6 | 2 | Num | Página |  | Constante "01"
4 | 8 | 4 | An | Fin de identificador de modelo |  | Constante "000>"
5 | 12 | 1 | A | Indicador de página complementaria |  | En blanco
6 | 13 | 1 | A | Tipo de declaración |  | Ver nota 1
7 | 14 | 9 | An | Identificación. Sujeto pasivo. NIF | obligatorio
8 | 23 | 60 | An | Identificación. Sujeto pasivo. Razón o denominación social/Apellidos | obligatorio
9 | 83 | 20 | An | Identificación. Sujeto pasivo. Nombre
10 | 103 | 4 | Num | Identificación. Ejercicio | obligatorio
11 | 107 | 2 | An | Identificación. Periodo | obligatorio | "01" ... "12" o "1T" … "4T"
12 | 109 | 15 | Num | Retenciones e ingresos a cuenta. Número perceptores. Transmisiones del capital [01]
13 | 124 | 17 | Num | Retenciones e ingresos a cuenta. Base de retenciones e ingresos a cuenta. Transmisiones del capital [02] |  | [quince enteros + dos decimales]
14 | 141 | 17 | Num | Retenciones e ingresos a cuenta. Retenciones e ingresos a cuenta. Transmisiones del capital [03] |  | [quince enteros + dos decimales]
15 | 158 | 15 | Num | Retenciones e ingresos a cuenta. Número perceptores. Transmisiones derechos de suscripción [04]
16 | 173 | 17 | Num | Retenciones e ingresos a cuenta. Base de retenciones e ingresos a cuenta. Transmisiones derechos de suscripción [05] |  | [quince enteros + dos decimales]
17 | 190 | 17 | Num | Retenciones e ingresos a cuenta. Retenciones e ingresos a cuenta. Transmisiones derechos de suscripción [06] |  | [quince enteros + dos decimales]
18 | 207 | 17 | Num | Pago a cuenta. Base de retenciones e ingresos a cuenta [07] |  | [quince enteros + dos decimales]
19 | 224 | 17 | Num | Pago a cuenta. Retenciones e ingresos a cuenta [08] |  | [quince enteros + dos decimales]
20 | 241 | 17 | Num | Total liquidación. Suma de retenciones e ingresos a cuenta. ([03] + [06] + [08])  [09] |  | [quince enteros + dos decimales]
21 | 258 | 17 | Num | Total liquidación. Resultado de anteriores declaraciones [10] |  | [quince enteros + dos decimales]
22 | 275 | 17 | Num | Total liquidación. Resultado a ingresar. ([09] - [10]) [11] |  | [quince enteros + dos decimales]
23 | 292 | 1 | An | Declaración complementaria. |  | X o blanco
24 | 293 | 13 | An | Número de justificante de la declaración anterior
25 | 306 | 34 | An | Domiciliación IBAN
26 | 340 | 136 | An | Reservado AEAT
27 | 476 | 13 | An | Reservado para la Administración. Sello electronico
28 | 489 | 12 | An | Indicador de fin de registro. | obligatorio | Constante "</T11701000>"
 | TOTAL | 500 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: I (ingreso), U (domiciliación), G (ingreso a anotar en CCT) y N (negativa)
2. Para facilitar la incorporación de datos al formulario se espera que el fichero esté localizado en C:\AEAT\ y que su nombre sea 117.txt
3. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
4. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
6. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  | POSICIONES