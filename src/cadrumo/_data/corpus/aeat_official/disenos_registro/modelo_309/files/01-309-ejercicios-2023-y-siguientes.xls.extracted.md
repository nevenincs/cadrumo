# M30900

 | Agencia Tributaria
Modelo 309
versión 1.4 |  | Diseño de registro
 |  | Declaración - Liquidación no periódica
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Constante. |  | "<T"
2 | 3 | 3 | An | Modelo |  | "309"
3 | 6 | 1 | An | Constante. |  | "0"
4 | 7 | 4 | An | Ejercicio devengo. (AAAA)
5 | 11 | 2 | An | Período. (PP) |  | "1T" .."4T" ó "0A"
6 | 13 | 5 | An | Constante. |  | "0000>"
7 | 18 | 5 | An | Constante |  | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
9 | 93 | 4 | An | Versión del Programa (Nota 1)
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
11 | 101 | 9 | An | NIF Empresa Desarrollo (Nota 1)
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
13 | 323 | 6 | An | Constante |  | "</AUX>"
14 | 329 | Variable | An | Contenido del fichero.  Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T3090+Ejercicio+periodo+0000> |  | "</3090AAAAPP0000>"
Total |  | Variable
Nota 1 | A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW

# M30901

 | Agencia Tributaria
Modelo 309 |  | Diseño de registro. Castellano.
versión 1.4 |  | IVA. Declaración - Liquidación no periódica
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | Num | Modelo | Constante "309"
3 | 6 | 2 | An | Página | Constante "01"
4 | 8 | 4 | An | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An | Reservado para la Administración | En blanco
6 | 13 | 1 | A | Tipo de declaración | Ver nota 1
7 | 14 | 9 | An | Identificación (1) - NIF
8 | 23 | 60 | An | Identificación (1) -  Apellidos o Denominación Social
9 | 83 | 20 | An | Identificación (1) -  Nombre
10 | 103 | 4 | Num | Devengo (2) - Ejercicio
11 | 107 | 2 | An | Devengo (2) - Periodo | "1T" .."4T" ó "0A"
12 | 109 | 9 | An | Transmitente (3) - NIF
13 | 118 | 60 | An | Transmitente (3) - Apellidos o Denominación Social
14 | 178 | 20 | An | Transmitente (3) - Nombre
15 | 198 | 2 | An | Transmitente (3) - País
16 | 200 | 1 | Num | Situación tributaria (5): | 1. Sujeto acogido a régimen especial de agric. …
2. Sujeto acogido a régimen especial recargo equiv.
3. Sujeto pasivo sin derecho a deducción.
4. Persona jurídica no empresario o profesional
5. Persona física no empresario o profesional
6. Otras situaciones tributarias no contempladas anteriormente
17 | 201 | 1 | Num | Hecho imponible (6): | 1. Adquisición intracomunitaria de bienes
2. Adquisición intracomunitaria medios tte. Nuevos
3. Inversión sujeto pasivo
4. Entregas bienes inversión natural. Inmobiliaria
5. Entregas bienes y prestac.servicio en proc. Admin, y judiciales
6. Otros supuestos no contemplados anteriormente
18 | 202 | 40 | An | Características y datos técnicos (7) - Vehículos - Marca
19 | 242 | 40 | An | Características y datos técnicos (7) - Vehículos - Tipo
20 | 282 | 40 | An | Características y datos técnicos (7) - Vehículos - Modelo (denominación comercial):
21 | 322 | 22 | An | Características y datos técnicos (7) - Vehículos - Nº identificación (bastidor)
22 | 344 | 6 | An | Características y datos técnicos (7) - Vehículos - Clasificación
23 | 350 | 40 | An | Características y datos técnicos (7) - Embarcaciones - Fabricante
24 | 390 | 80 | An | Características y datos técnicos (7) - Embarcaciones - Tipo-Modelo
25 | 470 | 22 | An | Características y datos técnicos (7) - Embarcaciones - Identificación (Nº construcción)
26 | 492 | 5 | Num | Características y datos técnicos (7) - Embarcaciones - Eslora máxima | [tres enteros + dos decimales]
27 | 497 | 40 | An | Características y datos técnicos (7) - Aeronaves - Fabricante
28 | 537 | 80 | An | Características y datos técnicos (7) - Aeronaves - Marca - Tipo - Modelo
29 | 617 | 22 | An | Características y datos técnicos (7) - Aeronaves - Nº Serie
30 | 639 | 4 | Num | Características y datos técnicos (7) - Aeronaves - Año fabricación
31 | 643 | 10 | Num | Características y datos técnicos (7) - Aeronaves - Peso máximo despegue (en Kg.)
32 | 653 | 17 | N | Liquidación (8) - Régimen General - Base imponible  [01] | [quince enteros + dos decimales]
33 | 670 | 5 | Num | Liquidación (8) - Régimen General - Tipo %  [02] | [tres enteros + dos decimales]
34 | 675 | 17 | N | Liquidación (8) - Régimen General - Cuota  [03] | [quince enteros + dos decimales]
35 | 692 | 17 | N | Liquidación (8) - Régimen General - Base imponible  [25] | [quince enteros + dos decimales]
36 | 709 | 5 | Num | Liquidación (8) - Régimen General - Tipo %  [26] | [tres enteros + dos decimales]
37 | 714 | 17 | N | Liquidación (8) -Régimen General - Cuota  [27] | [quince enteros + dos decimales]
38 | 731 | 17 | N | Liquidación (8) - Régimen General - Base imponible  [04] | [quince enteros + dos decimales]
39 | 748 | 5 | Num | Liquidación (8) - Régimen General - Tipo %  [05] | [tres enteros + dos decimales]
40 | 753 | 17 | N | Liquidación (8) - Régimen General - Cuota  [06] | [quince enteros + dos decimales]
41 | 770 | 17 | N | Liquidación (8) - Régimen General - Base imponible  [07] | [quince enteros + dos decimales]
42 | 787 | 5 | Num | Liquidación (8) - Régimen General - Tipo %  [08] | [tres enteros + dos decimales]
43 | 792 | 17 | N | Liquidación (8) - Régimen General - Cuota  [09] | [quince enteros + dos decimales]
44 | 809 | 17 | N | Liquidación (8) - Recargo equivalencia - Base imponible  [10] | [quince enteros + dos decimales]
45 | 826 | 5 | Num | Liquidación (8) - Recargo equivalencia - Tipo %  [11] | [tres enteros + dos decimales]
46 | 831 | 17 | N | Liquidación (8) - Recargo equivalencia - Cuota  [12] | [quince enteros + dos decimales]
47 | 848 | 17 | N | Liquidación (8) - Recargo equivalencia - Base imponible  [13] | [quince enteros + dos decimales]
48 | 865 | 5 | Num | Liquidación (8) - Recargo equivalencia - Tipo %  [14] | [tres enteros + dos decimales]
49 | 870 | 17 | N | Liquidación (8) - Recargo equivalencia - Cuota  [15] | [quince enteros + dos decimales]
50 | 887 | 17 | N | Liquidación (8) - Recargo equivalencia - Base imponible  [16] | [quince enteros + dos decimales]
51 | 904 | 5 | Num | Liquidación (8) - Recargo equivalencia - Tipo %  [17] | [tres enteros + dos decimales]
52 | 909 | 17 | N | Liquidación (8) - Recargo equivalencia - Cuota  [18] | [quince enteros + dos decimales]
53 | 926 | 17 | N | Liquidación (8) - Recargo equivalencia - Base imponible  [19] | [quince enteros + dos decimales]
54 | 943 | 5 | Num | Liquidación (8) - Recargo equivalencia - Tipo %  [20] | [tres enteros + dos decimales]
55 | 948 | 17 | N | Liquidación (8) - Recargo equivalencia - Cuota  [21] | [quince enteros + dos decimales]
56 | 965 | 17 | N | Liquidación (8) - Total cuota devengada ([03]+[27]+[06]+[09]+[12]+[15]+[18]+[21])  [22] | [quince enteros + dos decimales]
57 | 982 | 17 | N | Liquidación (8) - A deducir  [23] | [quince enteros + dos decimales]
58 | 999 | 17 | Num | Liquidación (8) - Resultado a ingresar [22]-[23]  [24] | [quince enteros + dos decimales]
59 | 1016 | 1 | An | Declaración complementaria (9) | blanco o "X"
60 | 1017 | 13 | An | Número de justificante de la declaración anterior (9)
61 | 1030 | 34 | An | IBAN (10)
62 | 1064 | 15 | An | Transmitente (3)- NIF-IVA
63 | 1079 | 9 | An | Adjudicatario (4) - NIF
64 | 1088 | 60 | An | Adjudicatario (4) - Apellidos o Denominación Social
65 | 1148 | 20 | An | Adjudicatario (4) - Nombre
66 | 1168 | 308 | An | Reservado para la Administración | En blanco
67 | 1476 | 13 | An | Reservado para el sello electrónico de la AEAT | En blanco
68 | 1489 | 12 | An | Indicador de fin de registro | Constante "</T30901000>"
 | TOTAL | 1500 | POSICIONES
1. El tipo de declaración puede ser: 

I (Ingreso), y, en caso de declaraciones trimestrales, también  U (Domiciliación del ingreso) y G (Anotación de ingreso en cuenta corriente tributaria).

En predeclaraciones sólo se admite I (Ingreso).
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  | POSICIONES