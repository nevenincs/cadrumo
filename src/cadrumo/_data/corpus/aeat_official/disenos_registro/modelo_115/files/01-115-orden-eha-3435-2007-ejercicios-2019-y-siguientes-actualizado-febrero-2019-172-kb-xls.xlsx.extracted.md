# DR 11500

 | Agencia Tributaria
Modelo 115
versión 1.3 |  | Diseño de registro
 |  | Impuesto sobre el Valor Añadido
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Constante. |  | "<T"
2 | 3 | 3 | An | Modelo |  | "115"
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
15 | *** | 18 | An | Constante. </T1150+Ejercicio+periodo+0000> |  | "</T1150AAAAPP0000>"
Total |  | Variable
Nota 1 | A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
Nota 2
El número máximo de ocurrencias de la página 2 son 6 para las actividades del régimen agrícolas, ganaderas y forestales; y 6 para las actividades
del régimen simplificado(excepto agrícolas, ganaderas y forestales). Por lo que el número máximo de páginas 2 será 3.

# DR 11501

 | Agencia Tributaria
Modelo 115 |  | Diseño de registro.
 |  | IRPF e Impuesto sobre Sociedades e Impuestos sobre la Renta de no residentes (establecimientos permanentes). Retenciones e ingresos a cuenta sobre rendimientos procedentes del arrendamiento de inmuebles urbanos.
Nº | Posic. | Lon. | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página |  | Constante "<T"
2 | 3 | 3 | Num | Modelo |  | Constante "115"
3 | 6 | 2 | Num | Página |  | Constante "01"
4 | 8 | 4 | An | Fin de identificador de modelo |  | Constante "000>"
5 | 12 | 1 | A | Reservado página complementaria |  | Blanco o C
6 | 13 | 1 | A | Tipo de declaración |  | Ver nota 1
7 | 14 | 9 | An | Identificación. Sujeto pasivo. NIF | obligatorio
8 | 23 | 60 | An | Identificación. Sujeto pasivo. Razón o denominación social/Apellidos | obligatorio
9 | 83 | 20 | An | Identificación. Sujeto pasivo. Nombre
10 | 103 | 4 | Num | Identificación. Ejercicio | obligatorio
11 | 107 | 2 | An | Identificación. Periodo | obligatorio | "01" ... "12" o "1T" … "4T"
12 | 109 | 15 | Num | Retenciones e ingresos a cuenta. Número perceptores [01]
13 | 124 | 17 | Num | Retenciones e ingresos a cuenta. Base retenciones e ingresos a cuenta [02] |  | [quince enteros + dos decimales]
14 | 141 | 17 | Num | Retenciones e ingresos a cuenta. Retenciones e ingresos a cuenta [03] |  | [quince enteros + dos decimales]
15 | 158 | 17 | Num | Retenciones e ingresos a cuenta. Resultado anteriores declaraciones [04] |  | [quince enteros + dos decimales]
16 | 175 | 17 | Num | Retenciones e ingresos a cuenta. Resultado a ingresar [03] - [04] |  | [quince enteros + dos decimales]
17 | 192 | 1 | An | Declaración complementaria. |  | blanco o "X"
18 | 193 | 13 | An | Número de justificante de la declaración anterior
19 | 206 | 34 | An | Domiciliación IBAN
20 | 240 | 236 | An | Reservado AEAT |  | En blanco
21 | 476 | 13 | An | Reservado para la Administración. Sello electronico |  | En blanco
22 | 489 | 12 | An | Identificador de fin de registro. | obligatorio | Constante "</T11501000>"
 | TOTAL | 500 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: I (ingreso), U (domiciliación), G (ingreso a anotar en CCT) y N (negativa)
2. Para facilitar la incorporación de datos al formulario se espera que el fichero esté localizado en C:\AEAT\ y que su nombre sea 115.txt
3. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
4. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
6. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  | POSICIONES