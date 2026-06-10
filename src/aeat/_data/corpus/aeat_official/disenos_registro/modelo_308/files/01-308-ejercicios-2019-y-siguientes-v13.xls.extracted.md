# M30800

 | Agencia Tributaria
Modelo 308
vers 1.3 |  | Diseño de registro
 |  | IVA. Régimen especial recargo de equivalencia, art. 30bis RIVA, art. 21.4º, párrafo 2º LIVA y sujetos pasivos ocasionales.
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Constante. |  | "<T"
2 | 3 | 3 | An | Modelo |  | "308"
3 | 6 | 1 | An | Constante. |  | "0"
4 | 7 | 4 | An | Ejercicio devengo. (AAAA)
5 | 11 | 2 | An | Período. (PP) |  | "1T","2T","3T", "4T" o "0A"
6 | 13 | 5 | An | Constante. |  | "0000>"
7 | 18 | 5 | An | Constante |  | "<AUX>"
8 | 23 | 70 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
9 | 93 | 4 | An | Versión del Programa (Nota 1)
10 | 97 | 4 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
11 | 101 | 9 | An | NIF Empresa Desarrollo (Nota 1)
12 | 110 | 213 | An | Reservado para la Administración. Rellenar con blancos |  | BLANCOS
13 | 323 | 6 | An | Constante |  | "</AUX>"
14 | 329 | Variable | An | Contenido del fichero.  Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
15 | *** | 18 | An | Constante. </T3080+Ejercicio+periodo+0000> |  | "</T3080AAAAPP0000>"
Total |  | Variable
Nota 1 | A cumplimentar por las entidades desarrolladoras (EEDD)
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW

# M30801

 | Agencia Tributaria
Modelo 308 |  | Diseño de registro. Castellano.
 |  | IVA. Régimen especial recargo de equivalencia, art. 30bis RIVA, art. 21.4º, párrafo 2º LIVA y sujetos pasivos ocasionales.
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página | Constante "<T"
2 | 3 | 3 | An | Modelo | Constante "308"
3 | 6 | 2 | An | Página | Constante "01"
4 | 8 | 4 | An | Fin de identificador de modelo | Constante "000>"
5 | 12 | 1 | An | Reservado para la Administración | En blanco
6 | 13 | 1 | A | Tipo de declaración | Ver nota 1
7 | 14 | 9 | An | Identificación - NIF
8 | 23 | 60 | An | Identificación -  Apellidos o Denominación Social
9 | 83 | 20 | An | Identificación -  Nombre
10 | 103 | 4 | An | Devengo - Ejercicio
11 | 107 | 2 | An | Devengo - Periodo | "1T... 4T", "01 … 12" o "0A" (según Tipo Tributación)
12 | 109 | 1 | Num | Tipo de tributación según el sujeto pasivo | 1 - Tributa como sujeto pasivo que realiza a título ocasional entregas intracomunitarias de medios de transporte nuevos exentas del Impuesto
2- Tributa como sujeto pasivo que realiza exclusivamente actividades a las que sea de aplicación el régimen especial del recargo de equivalencia
3 - Tributa como sujeto pasivo que ejerce la actividad de transporte de viajeros o de mercancías por carretera
4 - Tributa como sujeto pasivo que tiene la consideración de Ente público o de establecimiento privado de carácter social (art. 21.4 LIVA)
13 | 110 | 9 | An | Medios transporte nuevos (MTN) - Adquirente - NIF
14 | 119 | 60 | An | MTN - Adquirente - Apellidos ó Razón social
15 | 179 | 20 | An | MTN - Adquirente - Nombre
16 | 199 | 2 | An | MTN - Adquirente - País
17 | 201 | 40 | An | MTN - Vehículos - Marca
18 | 241 | 40 | An | MTN - Vehículos - Tipo
19 | 281 | 40 | An | MTN - Vehículos - Modelo (denominación comercial)
20 | 321 | 22 | An | MTN - Vehículos - Nº Id. Bastidor
21 | 343 | 6 | An | MTN - Vehículos - Clasificación
22 | 349 | 40 | An | MTN - Embarcaciones - Fabricante
23 | 389 | 80 | An | MTN - Embarcaciones - Tipo
24 | 469 | 22 | An | MTN - Embarcaciones - Identificación
25 | 491 | 5 | Num | MTN - Embarcaciones - Eslora máxima | [tres enteros + dos decimales]
26 | 496 | 40 | An | MTN - Aeronaves - Fabricante
27 | 536 | 80 | An | MTN - Aeronaves - Marca
28 | 616 | 22 | An | MTN - Aeronaves - Nº serie
29 | 638 | 4 | Num | MTN - Aeronaves - Año fabricación
30 | 642 | 10 | Num | MTN - Aeronaves - Peso máximo despegue
31 | 652 | 17 | Num | MTN - Liquidación - Precio Adquisición [01] | [quince enteros + dos decimales]
32 | 669 | 5 | Num | MTN - Liquidación - Tipo (%) [02] | [tres enteros + dos decimales]
33 | 674 | 17 | Num | MTN - Liquidación - IVA soportado [03] | [quince enteros + dos decimales]
34 | 691 | 17 | Num | MTN - Liquidación - Precio de venta [04] | [quince enteros + dos decimales]
35 | 708 | 5 | Num | MTN - Liquidación - Tipo (%) [05] | [tres enteros + dos decimales]
36 | 713 | 17 | Num | MTN - Liquidación - Máximo a devolver [06] | [quince enteros + dos decimales]
37 | 730 | 17 | Num | MTN - Liquidación - IVA a devolver por entregas intracomunitarias [07] | [quince enteros + dos decimales]
38 | 747 | 17 | Num | MTN - Liquidación - IVA a devolver actividad de transporte[18] | [quince enteros + dos decimales]
39 | 764 | 17 | Num | MTN - Liquidación - IVA soportado art. 21.4º, párrafo 2º LIVA [19] | [quince enteros + dos decimales]
40 | 781 | 17 | Num | MTN - Liquidación - IVA a devolver art. 21.4º, párrafo 2º LIVA [20] | [quince enteros + dos decimales]
41 | 798 | 17 | Num | Rég. Espec. recargo equival. (REQ) - Liquidación - Base Imponible [08] | [quince enteros + dos decimales]
42 | 815 | 5 | Num | REQ - Liquidación - Tipo (%) [09] | [tres enteros + dos decimales]
43 | 820 | 17 | Num | REQ - Liquidación - Cuota [10] | [quince enteros + dos decimales]
44 | 837 | 17 | Num | REQ - Liquidación - Base Imponible [11] | [quince enteros + dos decimales]
45 | 854 | 5 | Num | REQ - Liquidación - Tipo (%) [12] | [tres enteros + dos decimales]
46 | 859 | 17 | Num | REQ - Liquidación - Cuota [13] | [quince enteros + dos decimales]
47 | 876 | 17 | Num | REQ - Liquidación - Base Imponible [14] | [quince enteros + dos decimales]
48 | 893 | 5 | Num | REQ - Liquidación - Tipo (%) [15] | [tres enteros + dos decimales]
49 | 898 | 17 | Num | REQ - Liquidación - Cuota [16] | [quince enteros + dos decimales]
50 | 915 | 17 | Num | REQ - Liquidación - IVA a devolver [17] | [quince enteros + dos decimales]
51 | 932 | 34 | An | Devolución - IBAN
52 | 966 | 11 | An | Devolución - SWIFT-BIC
53 | 977 | 499 | An | Reservado para la Administración | En blanco
54 | 1476 | 13 | An | Reservado para el sello electrónico de la AEAT | En blanco
55 | 1489 | 12 | An | Indicador de fin de registro | Constante "</T30801000>"
 | TOTAL | 1500 | POSICIONES
1. El tipo de declaración para la presentación por lotes puede ser: D (Devolución)
2. Los campos alfanuméricos (An) sólo admiten letras, números y blancos. Deberán estar alineados a la izquierda, rellenando con blancos por la derecha.
3. Los campos numéricos (Num) sólo admiten números. Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
4. Los campos numéricos con signo (N) admiten números más el carácter N . Los datos numéricos deberán estar alineados a la derecha rellenando con ceros por la izquierda.
5. Los datos numéricos negativos llevarán una N en la primera posición del campo.
 | TOTAL: | -1 |  | POSICIONES