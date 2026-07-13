# DR23200

 | Agencia Tributaria
Modelo 232 |  | Diseño de registro. Castellano.
version 1.4 |  | Declaración informativa de operaciones vinculadas y de operaciones y situaciones relacionadas con países o territorios considerados paraísos fiscales.
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 2 | An | Inicio del identificador de modelo y página. |  | Constante "<T"
2 | 3 | 3 | An | Modelo. |  | Constante "232"
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
15 | *** | 18 | An | Constante. </T+ modelo+discriminante+Ejercicio+periodo+Tipo+> |  | "</T2320EEEE0A0000>"
Total |  | Variable
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

# DR23201

 | Agencia Tributaria
Modelo 232 |  | Diseño de registro. Castellano.
 |  | Declaración informativa de operaciones vinculadas y de operaciones y situaciones relacionadas con países o territorios considerados paraísos fiscales.
Nº | Posic. | Lon | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Indicador de inicio de registro | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "232"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "01"
4 | 8 | 4 | An |  | Indicador de inicio de registro | Obligatorio | Constante "000>"
5 | 12 | 1 | A |  | Indicador de página complementaria | Obligatorio | C o blanco
6 | 13 | 1 | An |  | Reservado AEAT (No hay Forma de Pago) |  | Blanco
7 | 14 | 9 | An |  | 1.Identificación - NIF Entidad | Obligatorio
8 | 23 | 60 | An |  | 1.Identificación - Apellidos o Razón social | Obligatorio
9 | 83 | 20 | An |  | 1.Identificación - Nombre
10 | 103 | 4 | Num |  | 2.Devengo - Ejercicio | Obligatorio
11 | 107 | 2 | An |  | 2.Devengo - Período (Uso Interno) | Obligatorio | Constante "0A"
12 | 109 | 1 | Num |  | 2.Devengo - Tipo de Ejercicio |  | 1 - 12 meses dentro del año natural
2 - 12 meses (365 días)
3 -  inferior a 12 meses
13 | 110 | 8 | Num |  | 2.Devengo - Fecha de inicio del período impositivo | Obligatorio | ddmmaaaa
14 | 118 | 8 | Num |  | 2.Devengo - Fecha de fin del período impositivo | Obligatorio | ddmmaaaa
15 | 126 | 4 | Num |  | 2.Devengo - C.N.A.E. actividad principal | Obligatorio
16 | 130 | 1 | An |  | Declaración complementaria o sustitutiva |  | S, C o blanco
17 | 131 | 13 | An |  | Declaración complementaria. Número de justificante de la declaración anterior
18 | 144 | 15 | An | C | 3.Información operaciones con personas o entidades vinculadas 1 - NIF Persona o entidad vinculada
19 | 159 | 1 | An | C | 3.Información operaciones con personas o entidades vinculadas 1 - F/J/O
20 | 160 | 60 | An | C | 3.Información operaciones con personas o entidades vinculadas 1 - Apellidos y nombre o Razón social
21 | 220 | 20 | An | C | 3.Información operaciones con personas o entidades vinculadas 1 - Reservado AEAT (Nombre) |  | Blancos
22 | 240 | 1 | An | C | 3.Información operaciones con personas o entidades vinculadas 1 - Tipo Vinculación |  | (Tabla A)
23 | 241 | 2 | An | C | 3.Información operaciones con personas o entidades vinculadas 1 - Código Provincia / País
24 | 243 | 2 | An | C | 3.Información operaciones con personas o entidades vinculadas 1 - Tipo Operación |  | (Tabla C)
25 | 245 | 1 | An | C | 3.Información operaciones con personas o entidades vinculadas 1 - Ingreso / Pago |  | "I" - Ingreso o "P" - Pago
26 | 246 | 2 | An | C | 3.Información operaciones con personas o entidades vinculadas 1 - Método Valoración |  | (Tabla B)
27 | 248 | 17 | Num | C | 3.Información operaciones con personas o entidades vinculadas 1 - Importe Operación |  | 15 ent + 2 dec
28 | 265 | 15 | An | C | 3.Información operaciones con personas o entidades vinculadas 2 - NIF Persona o entidad vinculada
29 | 280 | 1 | An | C | 3.Información operaciones con personas o entidades vinculadas 2 - F/J/O
30 | 281 | 60 | An | C | 3.Información operaciones con personas o entidades vinculadas 2 - Apellidos y nombre o Razón social
31 | 341 | 20 | An | C | 3.Información operaciones con personas o entidades vinculadas 2 - Reservado AEAT (Nombre) |  | Blancos
32 | 361 | 1 | An | C | 3.Información operaciones con personas o entidades vinculadas 2 - Tipo Vinculación |  | (Tabla A)
33 | 362 | 2 | An | C | 3.Información operaciones con personas o entidades vinculadas 2 - Código Provincia / País
34 | 364 | 2 | An | C | 3.Información operaciones con personas o entidades vinculadas 2 - Tipo Operación |  | (Tabla C)
35 | 366 | 1 | An | C | 3.Información operaciones con personas o entidades vinculadas 2 - Ingreso / Pago |  | "I" - Ingreso o "P" - Pago
36 | 367 | 2 | An | C | 3.Información operaciones con personas o entidades vinculadas 2 - Método Valoración |  | (Tabla B)
37 | 369 | 17 | Num | C | 3.Información operaciones con personas o entidades vinculadas 2 - Importe Operación |  | 15 ent + 2 dec
38 | 386 | 15 | An | C | 3.Información operaciones con personas o entidades vinculadas 3 - NIF Persona o entidad vinculada
39 | 401 | 1 | An | C | 3.Información operaciones con personas o entidades vinculadas 3 - F/J/O
40 | 402 | 60 | An | C | 3.Información operaciones con personas o entidades vinculadas 3 - Apellidos y nombre o Razón social
41 | 462 | 20 | An | C | 3.Información operaciones con personas o entidades vinculadas 3 - Reservado AEAT (Nombre) |  | Blancos
42 | 482 | 1 | An | C | 3.Información operaciones con personas o entidades vinculadas 3 - Tipo Vinculación |  | (Tabla A)
43 | 483 | 2 | An | C | 3.Información operaciones con personas o entidades vinculadas 3 - Código Provincia / País
44 | 485 | 2 | An | C | 3.Información operaciones con personas o entidades vinculadas 3 - Tipo Operación |  | (Tabla C)
45 | 487 | 1 | An | C | 3.Información operaciones con personas o entidades vinculadas 3 - Ingreso / Pago |  | "I" - Ingreso o "P" - Pago
46 | 488 | 2 | An | C | 3.Información operaciones con personas o entidades vinculadas 3 - Método Valoración |  | (Tabla B)
47 | 490 | 17 | Num | C | 3.Información operaciones con personas o entidades vinculadas 3 - Importe Operación |  | 15 ent + 2 dec
48 | 507 | 15 | An | C | 3.Información operaciones con personas o entidades vinculadas 4 - NIF Persona o entidad vinculada
49 | 522 | 1 | An | C | 3.Información operaciones con personas o entidades vinculadas 4 - F/J/O
50 | 523 | 60 | An | C | 3.Información operaciones con personas o entidades vinculadas 4 - Apellidos y nombre o Razón social
51 | 583 | 20 | An | C | 3.Información operaciones con personas o entidades vinculadas 4 - Reservado AEAT (Nombre) |  | Blancos
52 | 603 | 1 | An | C | 3.Información operaciones con personas o entidades vinculadas 4 - Tipo Vinculación |  | (Tabla A)
53 | 604 | 2 | An | C | 3.Información operaciones con personas o entidades vinculadas 4 - Código Provincia / País
54 | 606 | 2 | An | C | 3.Información operaciones con personas o entidades vinculadas 4 - Tipo Operación |  | (Tabla C)
55 | 608 | 1 | An | C | 3.Información operaciones con personas o entidades vinculadas 4 - Ingreso / Pago |  | "I" - Ingreso o "P" - Pago
56 | 609 | 2 | An | C | 3.Información operaciones con personas o entidades vinculadas 4 - Método Valoración |  | (Tabla B)
57 | 611 | 17 | Num | C | 3.Información operaciones con personas o entidades vinculadas 4 - Importe Operación |  | 15 ent + 2 dec
58 | 628 | 15 | An | C | 3.Información operaciones con personas o entidades vinculadas 5 - NIF Persona o entidad vinculada
59 | 643 | 1 | An | C | 3.Información operaciones con personas o entidades vinculadas 5 - F/J/O
60 | 644 | 60 | An | C | 3.Información operaciones con personas o entidades vinculadas 5 - Apellidos y nombre o Razón social
61 | 704 | 20 | An | C | 3.Información operaciones con personas o entidades vinculadas 5 - Reservado AEAT (Nombre) |  | Blancos
62 | 724 | 1 | An | C | 3.Información operaciones con personas o entidades vinculadas 5 - Tipo Vinculación |  | (Tabla A)
63 | 725 | 2 | An | C | 3.Información operaciones con personas o entidades vinculadas 5 - Código Provincia / País
64 | 727 | 2 | An | C | 3.Información operaciones con personas o entidades vinculadas 5 - Tipo Operación |  | (Tabla C)
65 | 729 | 1 | An | C | 3.Información operaciones con personas o entidades vinculadas 5 - Ingreso / Pago |  | "I" - Ingreso o "P" - Pago
66 | 730 | 2 | An | C | 3.Información operaciones con personas o entidades vinculadas 5 - Método Valoración |  | (Tabla B)
67 | 732 | 17 | Num | C | 3.Información operaciones con personas o entidades vinculadas 5 - Importe Operación |  | 15 ent + 2 dec
68 | 749 | 15 | An |  | 4.Operaciones con personas o entidades vinculadas - Nº identifi cación de la matriz
69 | 764 | 60 | An |  | 4.Operaciones con personas o entidades vinculadas - Razón social (matriz)
70 | 824 | 15 | An | C | 4.Operaciones con personas o entidades vinculadas 1 - NIF Persona o entidad vinculada
71 | 839 | 1 | An | C | 4.Operaciones con personas o entidades vinculadas 1 -F/J/O
72 | 840 | 60 | An | C | 4.Operaciones con personas o entidades vinculadas 1 - Apellidos y nombre o Razón social
73 | 900 | 20 | An | C | 4.Operaciones con personas o entidades vinculadas 1 - Reservado AEAT (Nombre) |  | Blancos
74 | 920 | 2 | An | C | 4.Operaciones con personas o entidades vinculadas 1 - Código Provincia / País
75 | 922 | 1 | An | C | 4.Operaciones con personas o entidades vinculadas 1 - Tipo Vinculación |  | (Tabla A)
76 | 923 | 17 | Num | C | 4.Operaciones con personas o entidades vinculadas 1 - Importe Operación |  | 15 ent + 2 dec
77 | 940 | 15 | An | C | 4.Operaciones con personas o entidades vinculadas 2 - NIF Persona o entidad vinculada
78 | 955 | 1 | An | C | 4.Operaciones con personas o entidades vinculadas 2 - F/J/O
79 | 956 | 60 | An | C | 4.Operaciones con personas o entidades vinculadas 2 - Apellidos y nombre o Razón social
80 | 1016 | 20 | An | C | 4.Operaciones con personas o entidades vinculadas 2 - Reservado AEAT (Nombre) |  | Blancos
81 | 1036 | 2 | An | C | 4.Operaciones con personas o entidades vinculadas 2 - Código Provincia / País
82 | 1038 | 1 | An | C | 4.Operaciones con personas o entidades vinculadas 2 - Tipo Vinculación |  | (Tabla A)
83 | 1039 | 17 | Num | C | 4.Operaciones con personas o entidades vinculadas 2 - Importe Operación |  | 15 ent + 2 dec
84 | 1056 | 15 | An | C | 4.Operaciones con personas o entidades vinculadas 3 - NIF Persona o entidad vinculada
85 | 1071 | 1 | An | C | 4.Operaciones con personas o entidades vinculadas 3 - F/J/O
86 | 1072 | 60 | An | C | 4.Operaciones con personas o entidades vinculadas 3 - Apellidos y nombre o Razón social
87 | 1132 | 20 | An | C | 4.Operaciones con personas o entidades vinculadas 3 - Reservado AEAT (Nombre) |  | Blancos
88 | 1152 | 2 | An | C | 4.Operaciones con personas o entidades vinculadas 3 - Código Provincia / País
89 | 1154 | 1 | An | C | 4.Operaciones con personas o entidades vinculadas 3 - Tipo Vinculación |  | (Tabla A)
90 | 1155 | 17 | Num | C | 4.Operaciones con personas o entidades vinculadas 3 - Importe Operación |  | 15 ent + 2 dec
91 | 1172 | 317 | An |  | Reservado para la Administración |  | Blancos
92 | 1489 | 3 | An |  | Indicador de fin de registro | Obligatorio | Constante "</T"
93 | 1492 | 3 | Num |  | Modelo | Obligatorio | Constante "232"
94 | 1495 | 2 | Num |  | Página | Obligatorio | Constante "01"
95 | 1497 | 4 | An |  | Indicador de fin de registro | Obligatorio | Constante "000>"
 | TOTAL | 1500 | POSICIONES
 | TOTAL: | -1 |  |  | POSICIONES

# DR23202

 | Agencia Tributaria
Modelo 232 |  | Diseño de registro. Castellano.
 |  | Declaración informativa de operaciones vinculadas y de operaciones y situaciones relacionadas con países o territorios considerados paraísos fiscales.
Nº | Posic. | Lon | Tipo | Comp | Descripción | Validación | Contenido
1 | 1 | 2 | An |  | Indicador de inicio de registro | Obligatorio | Constante "<T"
2 | 3 | 3 | Num |  | Modelo | Obligatorio | Constante "232"
3 | 6 | 2 | Num |  | Página | Obligatorio | Constante "02"
4 | 8 | 4 | An |  | Indicador de inicio de registro | Obligatorio | Constante "000>"
5 | 12 | 1 | A |  | Indicador de página complementaria | Obligatorio | C o blanco
6 | 13 | 50 | An | C | 5.Operaciones relacionadas con paraísos fiscales 1 - Descripción de la operación
7 | 63 | 60 | An | C | 5.Operaciones relacionadas con paraísos fiscales 1 - Persona o entidad residente en paraíso fiscal
8 | 123 | 20 | An | C | 5.Operaciones relacionadas con paraísos fiscales 1 - Reservado AEAT (Nombre) |  | Blancos
9 | 143 | 1 | An | C | 5.Operaciones relacionadas con paraísos fiscales 1 - F/J/O
10 | 144 | 2 | An | C | 5.Operaciones relacionadas con paraísos fiscales 1 - Clave País o territorio
11 | 146 | 17 | Num | C | 5.Operaciones relacionadas con paraísos fiscales 1 - Importe |  | 15 ent + 2 dec
12 | 163 | 50 | An | C | 5.Operaciones relacionadas con paraísos fiscales 2 - Descripción de la operación
13 | 213 | 60 | An | C | 5.Operaciones relacionadas con paraísos fiscales 2 - Persona o entidad residente en paraíso fiscal
14 | 273 | 20 | An | C | 5.Operaciones relacionadas con paraísos fiscales 2 - Reservado AEAT (Nombre) |  | Blancos
15 | 293 | 1 | An | C | 5.Operaciones relacionadas con paraísos fiscales 2 - F/J/O
16 | 294 | 2 | An | C | 5.Operaciones relacionadas con paraísos fiscales 2 - Clave País o territorio
17 | 296 | 17 | Num | C | 5.Operaciones relacionadas con paraísos fiscales 2 - Importe |  | 15 ent + 2 dec
18 | 313 | 50 | An | C | 5.Operaciones relacionadas con paraísos fiscales 3 - Descripción de la operación
19 | 363 | 60 | An | C | 5.Operaciones relacionadas con paraísos fiscales 3 - Persona o entidad residente en paraíso fiscal
20 | 423 | 20 | An | C | 5.Operaciones relacionadas con paraísos fiscales 3 - Reservado AEAT (Nombre) |  | Blancos
21 | 443 | 1 | An | C | 5.Operaciones relacionadas con paraísos fiscales 3 - F/J/O
22 | 444 | 2 | An | C | 5.Operaciones relacionadas con paraísos fiscales 3 - Clave País o territorio
23 | 446 | 17 | Num | C | 5.Operaciones relacionadas con paraísos fiscales 3 - Importe |  | 15 ent + 2 dec
24 | 463 | 50 | An | C | 5.Operaciones relacionadas con paraísos fiscales 4 - Descripción de la operación
25 | 513 | 60 | An | C | 5.Operaciones relacionadas con paraísos fiscales 4 - Persona o entidad residente en paraíso fiscal
26 | 573 | 20 | An | C | 5.Operaciones relacionadas con paraísos fiscales 4 - Reservado AEAT (Nombre) |  | Blancos
27 | 593 | 1 | An | C | 5.Operaciones relacionadas con paraísos fiscales 4 - F/J/O
28 | 594 | 2 | An | C | 5.Operaciones relacionadas con paraísos fiscales 4 - Clave País o territorio
29 | 596 | 17 | Num | C | 5.Operaciones relacionadas con paraísos fiscales 4 - Importe |  | 15 ent + 2 dec
30 | 613 | 50 | An | C | 5.Operaciones relacionadas con paraísos fiscales 5 - Descripción de la operación
31 | 663 | 60 | An | C | 5.Operaciones relacionadas con paraísos fiscales 5 - Persona o entidad residente en paraíso fiscal
32 | 723 | 20 | An | C | 5.Operaciones relacionadas con paraísos fiscales 5 - Reservado AEAT (Nombre) |  | Blancos
33 | 743 | 1 | An | C | 5.Operaciones relacionadas con paraísos fiscales 5 - F/J/O
34 | 744 | 2 | An | C | 5.Operaciones relacionadas con paraísos fiscales 5 - Clave País o territorio
35 | 746 | 17 | Num | C | 5.Operaciones relacionadas con paraísos fiscales 5 - Importe |  | 15 ent + 2 dec
36 | 763 | 50 | An | C | 5.Operaciones relacionadas con paraísos fiscales 6 - Descripción de la operación
37 | 813 | 60 | An | C | 5.Operaciones relacionadas con paraísos fiscales 6 - Persona o entidad residente en paraíso fiscal
38 | 873 | 20 | An | C | 5.Operaciones relacionadas con paraísos fiscales 6 - Reservado AEAT (Nombre) |  | Blancos
39 | 893 | 1 | An | C | 5.Operaciones relacionadas con paraísos fiscales 6 - F/J/O
40 | 894 | 2 | An | C | 5.Operaciones relacionadas con paraísos fiscales 6 - Clave País o territorio
41 | 896 | 17 | Num | C | 5.Operaciones relacionadas con paraísos fiscales 6 - Importe |  | 15 ent + 2 dec
42 | 913 | 50 | An | C | 5.Operaciones relacionadas con paraísos fiscales 7 - Descripción de la operación
43 | 963 | 60 | An | C | 5.Operaciones relacionadas con paraísos fiscales 7 - Persona o entidad residente en paraíso fiscal
44 | 1023 | 20 | An | C | 5.Operaciones relacionadas con paraísos fiscales 7 - Reservado AEAT (Nombre) |  | Blancos
45 | 1043 | 1 | An | C | 5.Operaciones relacionadas con paraísos fiscales 7 - F/J/O
46 | 1044 | 2 | An | C | 5.Operaciones relacionadas con paraísos fiscales 7 - Clave País o territorio
47 | 1046 | 17 | Num | C | 5.Operaciones relacionadas con paraísos fiscales 7 - Importe |  | 15 ent + 2 dec
48 | 1063 | 50 | An | C | 5.Operaciones relacionadas con paraísos fiscales 8 - Descripción de la operación
49 | 1113 | 60 | An | C | 5.Operaciones relacionadas con paraísos fiscales 8 - Persona o entidad residente en paraíso fiscal
50 | 1173 | 20 | An | C | 5.Operaciones relacionadas con paraísos fiscales 8 - Reservado AEAT (Nombre) |  | Blancos
51 | 1193 | 1 | An | C | 5.Operaciones relacionadas con paraísos fiscales 8 - F/J/O
52 | 1194 | 2 | An | C | 5.Operaciones relacionadas con paraísos fiscales 8 - Clave País o territorio
53 | 1196 | 17 | Num | C | 5.Operaciones relacionadas con paraísos fiscales 8 - Importe |  | 15 ent + 2 dec
54 | 1213 | 50 | An | C | 5.Operaciones relacionadas con paraísos fiscales 9 - Descripción de la operación
55 | 1263 | 60 | An | C | 5.Operaciones relacionadas con paraísos fiscales 9 - Persona o entidad residente en paraíso fiscal
56 | 1323 | 20 | An | C | 5.Operaciones relacionadas con paraísos fiscales 9 - Reservado AEAT (Nombre) |  | Blancos
57 | 1343 | 1 | An | C | 5.Operaciones relacionadas con paraísos fiscales 9 - F/J/O
58 | 1344 | 2 | An | C | 5.Operaciones relacionadas con paraísos fiscales 9 - Clave País o territorio
59 | 1346 | 17 | Num | C | 5.Operaciones relacionadas con paraísos fiscales 9 - Importe |  | 15 ent + 2 dec
60 | 1363 | 50 | An | C | 5.Operaciones relacionadas con paraísos fiscales 10 - Descripción de la operación
61 | 1413 | 60 | An | C | 5.Operaciones relacionadas con paraísos fiscales 10 - Persona o entidad residente en paraíso fiscal
62 | 1473 | 20 | An | C | 5.Operaciones relacionadas con paraísos fiscales 10 - Reservado AEAT (Nombre) |  | Blancos
63 | 1493 | 1 | An | C | 5.Operaciones relacionadas con paraísos fiscales 10 - F/J/O
64 | 1494 | 2 | An | C | 5.Operaciones relacionadas con paraísos fiscales 10 - Clave País o territorio
65 | 1496 | 17 | Num | C | 5.Operaciones relacionadas con paraísos fiscales 10 - Importe |  | 15 ent + 2 dec
66 | 1513 | 50 | An | C | 5.Operaciones relacionadas con paraísos fiscales 11 - Descripción de la operación
67 | 1563 | 60 | An | C | 5.Operaciones relacionadas con paraísos fiscales 11 - Persona o entidad residente en paraíso fiscal
68 | 1623 | 20 | An | C | 5.Operaciones relacionadas con paraísos fiscales 11 - Reservado AEAT (Nombre) |  | Blancos
69 | 1643 | 1 | An | C | 5.Operaciones relacionadas con paraísos fiscales 11 - F/J/O
70 | 1644 | 2 | An | C | 5.Operaciones relacionadas con paraísos fiscales 11 - Clave País o territorio
71 | 1646 | 17 | Num | C | 5.Operaciones relacionadas con paraísos fiscales 11 - Importe |  | 15 ent + 2 dec
72 | 1663 | 50 | An | C | 5.Operaciones relacionadas con paraísos fiscales 12- Descripción de la operación
73 | 1713 | 60 | An | C | 5.Operaciones relacionadas con paraísos fiscales 12 - Persona o entidad residente en paraíso fiscal
74 | 1773 | 20 | An | C | 5.Operaciones relacionadas con paraísos fiscales 12 - Reservado AEAT (Nombre) |  | Blancos
75 | 1793 | 1 | An | C | 5.Operaciones relacionadas con paraísos fiscales 12 - F/J/O
76 | 1794 | 2 | An | C | 5.Operaciones relacionadas con paraísos fiscales 12 - Clave País o territorio
77 | 1796 | 17 | Num | C | 5.Operaciones relacionadas con paraísos fiscales 12 - Importe |  | 15 ent + 2 dec
36 | 1813 | 1 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 1 - Tipo |  | (Tabla D)
37 | 1814 | 60 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 1 - Entidad participada o emisora de los valores
38 | 1874 | 20 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 1 - Reservado AEAT (Nombre) |  | Blancos
39 | 1894 | 2 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 1 - Clave País o territorio
40 | 1896 | 17 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 1 - Valor de adquisición |  | 15 ent + 2 dec
41 | 1913 | 5 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 1 - % Participación |  | 3 ent + 2 dec
42 | 1918 | 1 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 2 - Tipo |  | (Tabla D)
43 | 1919 | 60 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 2 - Entidad participada o emisora de los valores
44 | 1979 | 20 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 2 -  Reservado AEAT (Nombre) |  | Blancos
45 | 1999 | 2 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 2 -  Clave País o territorio
46 | 2001 | 17 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 2 - Valor de adquisición |  | 15 ent + 2 dec
47 | 2018 | 5 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 2 - % Participación |  | 3 ent + 2 dec
48 | 2023 | 1 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 3 - Tipo |  | (Tabla D)
49 | 2024 | 60 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 3 - Entidad participada o emisora de los valores
50 | 2084 | 20 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 3 -  Reservado AEAT (Nombre) |  | Blancos
51 | 2104 | 2 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 3 -  Clave País o territorio
52 | 2106 | 17 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 3 - Valor de adquisición |  | 15 ent + 2 dec
53 | 2123 | 5 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 3 - % Participación |  | 3 ent + 2 dec
54 | 2128 | 1 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 4 - Tipo |  | (Tabla D)
55 | 2129 | 60 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 4 - Entidad participada o emisora de los valores
56 | 2189 | 20 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 4 - Reservado AEAT (Nombre) |  | Blancos
57 | 2209 | 2 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 4 - Clave País o territorio
58 | 2211 | 17 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 4 - Valor de adquisición |  | 15 ent + 2 dec
59 | 2228 | 5 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 4 - % Participación |  | 3 ent + 2 dec
60 | 2233 | 1 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 5 - Tipo |  | (Tabla D)
61 | 2234 | 60 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 5 - Entidad participada o emisora de los valores
62 | 2294 | 20 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 5 - Reservado AEAT (Nombre) |  | Blancos
63 | 2314 | 2 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 5 -  Clave País o territorio
64 | 2316 | 17 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 5 - Valor de adquisición |  | 15 ent + 2 dec
65 | 2333 | 5 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 5 - % Participación |  | 3 ent + 2 dec
66 | 2338 | 1 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 6 - Tipo |  | (Tabla D)
67 | 2339 | 60 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 6 - Entidad participada o emisora de los valores
68 | 2399 | 20 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 6 - Reservado AEAT (Nombre) |  | Blancos
69 | 2419 | 2 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 6 -  Clave País o territorio
70 | 2421 | 17 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 6 - Valor de adquisición |  | 15 ent + 2 dec
71 | 2438 | 5 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 6 - % Participación |  | 3 ent + 2 dec
72 | 2443 | 1 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 7 - Tipo |  | (Tabla D)
73 | 2444 | 60 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 7 - Entidad participada o emisora de los valores
74 | 2504 | 20 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 7 - Reservado AEAT (Nombre) |  | Blancos
75 | 2524 | 2 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 7 - Clave País o territorio
76 | 2526 | 17 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 7 - Valor de adquisición |  | 15 ent + 2 dec
77 | 2543 | 5 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 7 - % Participación |  | 3 ent + 2 dec
78 | 2548 | 1 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 8 - Tipo |  | (Tabla D)
79 | 2549 | 60 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 8 - Entidad participada o emisora de los valores
80 | 2609 | 20 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 8 -  Reservado AEAT (Nombre) |  | Blancos
81 | 2629 | 2 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 8 -  Clave País o territorio
82 | 2631 | 17 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 8 - Valor de adquisición |  | 15 ent + 2 dec
83 | 2648 | 5 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 8 - % Participación |  | 3 ent + 2 dec
84 | 2653 | 1 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 9 - Tipo |  | (Tabla D)
85 | 2654 | 60 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 9 - Entidad participada o emisora de los valores
86 | 2714 | 20 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 9 -  Reservado AEAT (Nombre) |  | Blancos
87 | 2734 | 2 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 9 -  Clave País o territorio
88 | 2736 | 17 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 9 - Valor de adquisición |  | 15 ent + 2 dec
89 | 2753 | 5 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 9 - % Participación |  | 3 ent + 2 dec
90 | 2758 | 1 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 10 - Tipo |  | (Tabla D)
91 | 2759 | 60 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 10 - Entidad participada o emisora de los valores
92 | 2819 | 20 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 10 - Reservado AEAT (Nombre) |  | Blancos
93 | 2839 | 2 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 10 - Clave País o territorio
94 | 2841 | 17 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 10 - Valor de adquisición |  | 15 ent + 2 dec
95 | 2858 | 5 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 10 - % Participación |  | 3 ent + 2 dec
96 | 2863 | 1 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 11 - Tipo |  | (Tabla D)
97 | 2864 | 60 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 11 - Entidad participada o emisora de los valores
98 | 2924 | 20 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 11 - Reservado AEAT (Nombre) |  | Blancos
99 | 2944 | 2 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 11 -  Clave País o territorio
100 | 2946 | 17 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 11 - Valor de adquisición |  | 15 ent + 2 dec
101 | 2963 | 5 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 11 - % Participación |  | 3 ent + 2 dec
102 | 2968 | 1 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 12 - Tipo |  | (Tabla D)
103 | 2969 | 60 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 12 - Entidad participada o emisora de los valores
104 | 3029 | 20 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 12 - Reservado AEAT (Nombre) |  | Blancos
105 | 3049 | 2 | An | C | 6.Tenencia de valores relacionadas con paraísos fiscales 12 -  Clave País o territorio
106 | 3051 | 17 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 12 - Valor de adquisición |  | 15 ent + 2 dec
107 | 3068 | 5 | Num | C | 6.Tenencia de valores relacionadas con paraísos fiscales 12 - % Participación |  | 3 ent + 2 dec
108 | 3073 | 403 | An |  | Reservado para la Administración |  | Blancos
109 | 3476 | 13 | An |  | Reservado para el sello electrónico de la AEAT |  | Blancos
110 | 3489 | 3 | An |  | Indicador de fin de registro | Obligatorio | Constante "</T"
111 | 3492 | 3 | Num |  | Modelo | Obligatorio | Constante "232"
112 | 3495 | 2 | Num |  | Página | Obligatorio | Constante "02"
113 | 3497 | 4 | An |  | Indicador de fin de registro | Obligatorio | Constante "000>"
 | TOTAL | 3500 | POSICIONES
 | TOTAL: | -1 |  |  | POSICIONES

# TABLAS

TABLA DE TIPOS DE VINCULACIÓN (Tabla A)
A | Una entidad y sus socios o partícipes
B | Una entidad y sus consejeros o administradores
C | Una entidad y los cónyuges o personas unidas por relaciones de parentesco...de los socios o partícipes, consejeros o administradores (art. 18.3.c).LIS)
D | Dos entidades que pertenezcan a un grupo
E | Una entidad y los consejeros o administradores de otra entidad, cuando ambas entidades pertenezcan a un grupo
F | Una entidad y otra entidad participada por la primera indirectamente en, al menos, el 25 por ciento del capital social o de los fondos propios
G | Dos entidades en las cuales los mismos socios, partícipes o sus cónyuges, o personas unidas por relaciones de parentesco... participen, directa o indirectamente en, al menos, el 25 por ciento del capital social o los fondos propios
H | Una entidad residente en territorio español y sus establecimientos permanentes en el extranjero
TABLA DE METODOS DE VALORACIÓN (Tabla B)
1A | Método del precio libre comparable... (art. 18.4.1º. a) LIS)
1B | Método del coste incrementado... (art. 18.4.1º. b) LIS)
1C | Método del precio de reventa... (art. 18.4.1º. c) LIS)
1D | Método de la distribución del resultado... (art. 18.4.1º. d) LIS)
1E | Método del margen neto operacional del conjunto de operaciones... (art. 18.4.1º. e) LIS).
TABLA DE TIPO DE OPERACIÓN (Tabla C)
01 | – Clave 1: Adquisición/Transmisión de bienes tangibles (existencias, inmovilizados materiales, etc.)
02 | – Clave 2: Adquisición/Transmisión/Cesión de uso de intangibles: cánones y otros ingresos/pagos por utilización de tecnología,
 patentes, marcas, know-how, etc.
03 | – Clave 3: Adquisición/Transmisión de activos financieros representativos de fondos propios.
04 | – Clave 4: Adquisición/Transmisión de derechos de crédito y activos financieros representativos de deuda (excluidas operaciones tipo 5).
05 | – Clave 5: Operaciones financieras de deuda: constitución/amortización de créditos o préstamos, emisión/amortización de obligaciones
 y bonos, etc. (excluidos intereses).
06 | – Clave 6: Servicios entre personas o entidades vinculadas (artículo 18.5 LIS) (incluidos rendimientos de actividades profesionales,
 artísticas, deportivas, etc.).
07 | – Clave 7: Acuerdos de reparto de costes de bienes o servicios (artículo 18.7 LIS).
08 | – Clave 8: Alquileres y otros rendimientos por cesión de uso de inmuebles. No incluye rendimientos derivados de 
transmisiones/adquisiciones (plusvalías o minusvalías).
09 | – Clave 9: Intereses de créditos, préstamos y demás activos financieros representativos de deuda (obligaciones, bonos, etc.). 
No incluye rendimientos derivados de transmisiones/adquisiciones de estos activos financieros (plusvalías o minusvalías).
10 | – Clave 10: Rendimientos del trabajo, pensiones y aportaciones a fondos de pensiones y a otros sistemas de capitalización o 
retribución diferida, entrega de acciones u opciones sobre las mismas, etc.
11 | – Clave 11: Otras operaciones.
TABLA de tipo  de situaciones relacionadas con países o territorios calificados reglamentariamente como paraísos fiscales (Tabla D)
A | – Clave A: Tenencia de valores representativos de fondos propios de entidades residentes en países o 
territorios calificados reglamentariamente como paraísos fiscales.
B | – Clave B: Tenencia de valores de instituciones de inversión colectiva constituidas en los citados países o territorios.
C | – Clave C: Tenencia de valores de renta fija que estén admitidos a cotización en mercados secundarios en dichos países o territorios.