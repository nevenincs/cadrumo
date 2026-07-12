# Pag. 0

 | Agencia Tributaria
Modelo 036 |  | Diseño de registro. Castellano
vers. 4.3 |  | Declaración Censal/Declaración Censal Simplifica de alta, modificación y baja en el Censo de Empresarios, Profesionales y Retenedores
Nº | Posic. | Lon | Tipo | Descripción | Contenido
1 | 1 | 2 | An | Constante. | "<T"
2 | 3 | 3 | An | Modelo | "036"
3 | 6 | 1 | An | Constante. | "0"
4 | 7 | 4 | An | Ejercicio devengo. (AAAA)
5 | 11 | 2 | An | Período. (PP) | "0A"
6 | 13 | 5 | An | Constante. | "0000>"
7 | 18 | 5 | An | Constante | "<AUX>"
8 | 23 | 14 | An | Constante | 0000000000000W
9 | 37 | 9 | An | NIF de la declaración (posición 19 a 27 del DR) | Ej: 89890001K
10 | 46 | 3 | An | Tres primeras letras de Apellido/Razón Social (posición 28 a 30 del DR) | Ej: CER
11 | 49 | 274 | An | Reservado para la Administración. Rellenar con blancos | BLANCOS
12 | 323 | 6 | An | Constante | "</AUX>"
13 | 329 | 8 | An | Constante | "<VECTOR>"
14 | 337 | 300 | An | 01002A02B02C030… (se indicarán las páginas de las que se componen el fichero y se repetirá el código de la página tantas veces como páginas complementarias se hayan creado de la misma.)FIN + resto de espacios en blanco hasta completar 300 posiciones | Ej: 01002A040040100FIN        para indicar que se envían una página 1 (010), una página 2A (02A), dos páginas 4 (040) y una página 10 (100)
15 | 637 | 9 | An | Constante | "</VECTOR>"
16 | 646 | Variable | An | Contenido del fichero.  Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito para cada página en este mismo documento
17 | *** | 18 | An | Constante. </T+ modelo+discriminante+Ejercicio+periodo+Constante> | "</T0360AAAAPP0000>"
Total |  | Variable

# Pag. 1

 | Agencia Tributaria
Modelo 036 |  | Diseño de registro. Castellano
vers. 4.3 |  | Declaración Censal/Declaración Censal Simplifica de alta, modificación y baja en el Censo de Empresarios, Profesionales y Retenedores
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 9 | An | Inicio del identificador de modelo y página | obligatorio | <T036010>
2 | 10 | 1 | A | Indicador de página complementaria | obligatorio | blanco
3 | 11 | 8 | Num | VERSION AAAMMDD (AÑO MES DIA - FECHA ENTRADA EN VIGOR 036- 20250203 ) | obligatorio | 20250203 para modelo 036
4 | 19 | 9 | An | Datos identificativos. NIF  [101] | obligatorio
5 | 28 | 125 | An | Datos identificativos. Si fisica , Apellidos SIN  nombre; si juridicas,  denominación social  [102] | obligatorio
6 | 153 | 13 | An | Reservado (Número de justificante)
7 | 166 | 1 | An | Alta. Solicitud del Número de Identificación Fiscal (N.I.F.)  [110] |  | "S" o blanco
8 | 167 | 1 | An | Alta. Alta en el censo de empresarios, profesionales y retenedores  [111] |  | "S" o blanco
9 | 168 | 1 | An | Modificación. Solicitud de N.I.F. Definitivo, disponiendo del NIF provisional.  [120] |  | "S" o blanco
10 | 169 | 1 | An | Modificación. Solicitud de nueva tarjeta acreditativa del N.I.F.  [121] |  | "S" o blanco
11 | 170 | 1 | An | Modificación. Modificación domicilio fiscal. (pág. 2A, 2B y 2C)  [122] |  | "S" o blanco
12 | 171 | 1 | An | Modificación. Modificación domicilio social o de gestión admva. (pág. 2A y 2B)  [123] |  | "S" o blanco
13 | 172 | 1 | An | Modificación. Modificación domicilio a efectos de notificaciones. (pág. 2A, 2B y 2C)  [124] |  | "S" o blanco
14 | 173 | 1 | An | Modificación. Modificación otros datos identificativos /dominio. (pág. 2A, 2B y 2C)  [125] |  | "S" o blanco
15 | 174 | 1 | An | Modificación. Modificación datos representantes (pág. 3)  [126] |  | "S" o blanco
16 | 175 | 1 | An | Modificación. Modificación datos relativos a act. económicas y locales. (pág. 4)  [127] |  | "S" o blanco
17 | 176 | 1 | An | Modificación. Modificación de la condición de G.E. o Admón. Púb. de presup. sup. a 6 mill € (pág. 5)  [128] |  | "S" o blanco
18 | 177 | 1 | An | Modificación. Solicitud de inscripción/baja en el registro de devolución mensual. (pág. 5) [129] |  | "S" o blanco
19 | 178 | 1 | An | Modificación. Solicitud de ata/baja en el registro de operadores intracomunitarios. (pág. 5)  [130] |  | "S" o blanco
20 | 179 | 1 | An | Modificación. Modificación datos relativos al Impuesto sobre el Valor Añadido. (pág. 5)   [131] |  | "S" o blanco
21 | 180 | 1 | An | Modificación. Modificación datos relativos al Impuesto sobre la Renta de las Personas Físicas. (pág. 6)  [132] |  | "S" o blanco
22 | 181 | 1 | An | Modificación. Modificación datos relativos al impuesto sobre Sociedades. (pág. 6)   [133] |  | "S" o blanco
23 | 182 | 1 | An | Modificación. Modificación datos relativos al Imp. Renta no Residentes correspondientes a establ. permant. o a entidades en atrib. de rentas constituidas en el extranjero con presencia en territorio español. (pág. 6) [134] |  | "S" o blanco
24 | 183 | 1 | An | Opción/renuncia por el Regimen fiscal especial del Título II de la Ley 49/2002. (pag. 6)  [135] |  | "S" o blanco
25 | 184 | 1 | An | Modificación. Modificación datos relativos a retenciones e ingresos a cuenta. (pág. 7)  [136] |  | "S" o blanco
26 | 185 | 1 | An | Modificación. Modificación datos relativos a otros impuestos y registros. (pág. 7)  [137] |  | "S" o blanco
27 | 186 | 1 | An | Modificación. Modificación datos relativos a regímenes especiales del comercio intracomunit. (pág. 7/7b)  [138] |  | "S" o blanco
28 | 187 | 1 | An | Modificación. Modificación datos relativos a la relación de socios, miembros o partícipes. (pág. 8)  [139] |  | "S" o blanco
29 | 188 | 1 | An | Modificación. Dejar de ejercer todas las activ. empr. y/o prof. (pers jcas y entidades, sin disolución).  [140] |  | "S" o blanco
30 | 189 | 2 | Num | Modificación. Fecha efectiva del cese. Día  [141]
31 | 191 | 2 | Num | Modificación. Fecha efectiva del cese. Mes [141]
32 | 193 | 4 | Num | Modificación. Fecha efectiva del cese. Año [141]
33 | 197 | 1 | An | Baja. Baja en el censo de empresarios, profesionales y retenedores  [150] |  | "S" o blanco
34 | 198 | 1 | An | Baja. Causa  [151]
35 | 199 | 2 | Num | Baja. Fecha efectiva de la baja. Día  [152]
36 | 201 | 2 | Num | Baja. Fecha efectiva de la baja. Mes  [152]
37 | 203 | 4 | Num | Baja. Fecha efectiva de la baja. Año  [152]
38 | 207 | 40 | An | Lugar, fecha y firma. Lugar
39 | 247 | 2 | Num | Lugar, fecha y firma. Fecha. Dia
40 | 249 | 2 | Num | Lugar, fecha y firma. Fecha. Mes
41 | 251 | 4 | Num | Lugar, fecha y firma. Fecha. Año
42 | 255 | 1 | An | Lugar, fecha y firma. Firma en calidad
43 | 256 | 125 | An | Firmado: D./D.ª
44 | 381 | 1 | An | Modificación de datos de telefonos y direcciones electronicas para recibir avisos de la AEAT  (paginas 2a,2b,2c)  [142] |  | "S" o blanco
45 | 382 | 1 | An | comunicación de opcion y renuncia a la llevanza libros de iva a traves sede electronica de aeat  (pagina 5)  [143] |  | "S" o blanco
46 | 383 | 25 | An | nombre en caso de fisicas   [103]
47 | 408 | 1 | An | Solicitud de rehabilitación de NIF [144] |  | "S" o blanco
48 | 409 | 1 | An | Modificación datos relativos a titulares reales [145] |  | "S" o blanco
49 | 410 | 1 | An | Modificación entidades en liquidación  [146] |  | "S" o blanco
50 | 411 | 78 | An | Reservado para la Agencia Tributaria
50 | 489 | 1 | An | Reservado para la Agencia Tributaria
51 | 490 | 1 | An | Reservado para la Agencia Tributaria
52 | 491 | 10 | An | Identificador de fin de registro. | obligatorio | </T036010>
53 | 501 |  | An | Salto de línea. Constante CRLF. | obligatorio
TOTAL |  | 500 | Posiciones

# Pag. 2A

 | Agencia Tributaria
Modelo 036 |  | Diseño de registro. Castellano
 |  | Declaración Censal/Declaración Censal Simplifica de alta, modificación y baja en el Censo de Empresarios, Profesionales y Retenedores
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 9 | An | Inicio del identificador de modelo y página. | obligatorio | <T03602A>
2 | 10 | 1 | A | Tipo declaración | obligatorio | blanco
3 | 11 | 1 | An | Persona Física. Persona física residente en España / no residente en España  [A1) |  | S, N ,2 (art.10),4 (art 9.), blanco
4 | 12 | 2 | An | Persona Física. Persona física no residente en España. Nacionalidad  [A3] |  | (codigo iso)
5 | 14 | 9 | An | Persona Física. Identificación. N.I.F./N.I.E. [A4]
6 | 23 | 50 | An | Persona Física. Identificación. Apellido 1 [A5]
7 | 73 | 50 | An | Persona Física. Identificación. Apellido 2 [A6]
8 | 123 | 25 | An | Persona Física. Identificación. Nombre [A7]
9 | 148 | 25 | An | Persona Física. Identificación. Nombre comercial [A8]
10 | 173 | 5 | An | Persona fisica.  Domicilio fiscal en España. Tipo de vía  [A11]
11 | 178 | 5 | Num | Persona fisica.  Domicilio fiscal en España. Código via INE |  | Cod. via ine. De momento reservado a ceros
12 | 183 | 50 | An | Persona fisica.  Domicilio fiscal en España. Nombre de la vía pública  [A12]
13 | 233 | 3 | An | Persona fisica.  Domicilio fiscal en España.Tipo Num.  [A13]
14 | 236 | 5 | Num | Persona fisica.  Domicilio fiscal en España. Núm casa  [A14]
15 | 241 | 3 | An | Persona fisica.  Domicilio fiscal en España. Calif. Un  [A15]
16 | 244 | 3 | An | Persona fisica.  Domicilio fiscal en España. Bloque  [A16]
17 | 247 | 3 | An | Persona fisica.  Domicilio fiscal en España. Portal  [A17]
18 | 250 | 3 | An | Persona fisica.  Domicilio fiscal en España. Escal.  [A18]
19 | 253 | 3 | An | Persona fisica.  Domicilio fiscal en España. Planta  [A19]
20 | 256 | 3 | An | Persona fisica.  Domicilio fiscal en España. Puerta  [A20]
21 | 259 | 40 | An | Persona fisica.  Domicilio fiscal en España. Complemento domicilio (ej. Urbanización, Pol. Ind, C.C...)  [A21]
22 | 299 | 30 | An | Persona fisica.  Domicilio fiscal en España. Localidad / Población (si es distinta de municipio)  [A22]
23 | 329 | 5 | Num | Persona fisica.  Domicilio fiscal en España. C. Postal  [A23]
24 | 334 | 5 | Num | Persona fisica.  Domicilio fiscal en España. Código Municipio INE |  | C. Municipio ine (00000 - si no consta)
25 | 339 | 30 | An | Persona fisica.  Domicilio fiscal en España. Nombre del municipio  [A24]
26 | 369 | 2 | An | Persona fisica.  Domicilio fiscal en España. Código de Provincia  [A25] |  | ('01', '02',...'52')
27 | 371 | 100 | An | Persona fisica.  Datos telefonos y direccione para recibir avisos.. E-mail  [A26]
28 | 471 | 1 | An | Persona fisica.  Datos telefonos y direccione para recibir avisos. AEAT Alta |  | S o blanco
29 | 472 | 1 | An | Persona fisica.  Datos telefonos y direccione para recibir avisos. AEAT Baja |  | S o blanco
30 | 473 | 1 | An | Persona fisica.  Datos telefonos y direccione para recibir avisos. TEA Alta |  | S o blanco
31 | 474 | 1 | An | Persona fisica.  Datos telefonos y direccione para recibir avisos. TEA Baja |  | S o blanco
32 | 475 | 1 | An | Persona fisica.  Datos telefonos y direccione para recibir avisos. DGT Alta |  | S o blanco
33 | 476 | 1 | An | Persona fisica.  Datos telefonos y direccione para recibir avisos. DGT Baja |  | S o blanco
34 | 477 | 1 | An | Persona fisica.  Datos telefonos y direccione para recibir avisos. E-mail Alta/Modificación |  | S o blanco
35 | 478 | 1 | An | Persona fisica.  Datos telefonos y direccione para recibir avisos. E-mail Baja |  | S o blanco
36 | 479 | 19 | An | Reservado para la Agencia Tributaria
37 | 498 | 50 | An | Persona fisica.  Domicilio fiscal en el Est. de resid. (no resid). Domicilio (Adress)  [A31]
38 | 548 | 40 | An | Persona fisica.  Domicilio fiscal en el Est. de resid. (no resid). Compl. de domicilio (si fuese necesario)  [A32]
39 | 588 | 30 | An | Persona fisica.  Domicilio fiscal en el Est. de resid. (no residentes). Población / Ciudad  [A34]
40 | 618 | 100 | An | Persona fisica.  Identificacion . Dominio o direccion de internet .  [A27]
41 | 718 | 10 | An | Persona fisica.  Domicilio fiscal en el Est. de resid. (no residentes). C. Postal (ZIP)  [A33]
42 | 728 | 30 | An | Persona fisica.  Domicilio fiscal en el Est. de resid. (no residentes). Provincia/ Región/ Estado  [A35]
43 | 758 | 30 | An | Persona fisica.  Domicilio fiscal en el Est. de resid. (no residentes). País RESERVADO  [A36]
44 | 788 | 2 | An | Persona fisica.  Domicilio fiscal en el Est. de resid. (no residentes). Cod. Pais  [A37]
45 | 790 | 4 | An | Persona fisica.  Datos telefonos y direcciones aviso . Prefijo pais de movil (a28) |  | blancos si el movil es español
46 | 794 | 15 | An | Persona fisica. Datos telefonos y direcciones aviso . Tfno. Móvil    [A29]
47 | 809 | 1 | An | Persona fisica.  Datos telefonos y direccione para recibir avisos. Tfno. Móvil Alta/Modificación |  | S o blanco
48 | 810 | 1 | An | Persona fisica.  Datos telefonos y direccione para recibir avisos. Tfno. Móvil Baja |  | S o blanco
49 | 811 | 1 | An | Persona fisica.  Datos telefonos y direccione para recibir avisos. Aplicación Móvil AEAT Alta |  | S o blanco
50 | 812 | 1 | An | Persona fisica.  Datos telefonos y direccione para recibir avisos. Aplicación Móvil AEAT Baja |  | S o blanco
51 | 813 | 22 | An | Reservado para la Agencia Tributaria
52 | 835 | 5 | An | Persona fisica.  Domicilio a efectos de notificaciones. 1)  Tipo de vía  [A41]
53 | 840 | 5 | Num | Persona fisica.  Domicilio a efectos de notificaciones. |  | Cod. via ine. De momento reservado a ceros
54 | 845 | 50 | An | Persona fisica.  Domicilio a efectos de notificaciones. 1)  Nombre de la vía pública  [A42]
55 | 895 | 3 | An | Persona fisica.  Domicilio a efectos de notificaciones. 1) Tipo Num.  [A43]
56 | 898 | 5 | Num | Persona fisica.  Domicilio a efectos de notificaciones. 1)  Núm casa  [A44]
57 | 903 | 3 | An | Persona fisica.  Domicilio a efectos de notificaciones. 1)  Calif. Un  [A45]
58 | 906 | 3 | An | Persona fisica.  Domicilio a efectos de notificaciones. 1)  Bloque  [A46]
59 | 909 | 3 | An | Persona fisica.  Domicilio a efectos de notificaciones. 1)  Portal  [A47]
60 | 912 | 3 | An | Persona fisica.  Domicilio a efectos de notificaciones. 1)  Escal.  [A48]
61 | 915 | 3 | An | Persona fisica.  Domicilio a efectos de notificaciones. 1)  Planta  [A49]
62 | 918 | 3 | An | Persona fisica.  Domicilio a efectos de notificaciones. 1)  Puerta  [A50]
63 | 921 | 40 | An | Persona fisica.  Domicilio a efectos de notificaciones. 1)  Compl. Domicilio (ej. Urb, Pol. Ind, C.C...)  [A51]
64 | 961 | 30 | An | Persona fisica.  Domicilio a efectos de notificaciones. 1)  Localidad / Población (si es dist. de munic.)  [A52]
65 | 991 | 5 | Num | Persona fisica.  Domicilio a efectos de notificaciones. 1)  C. Postal  [A53]
66 | 996 | 5 | Num | Persona fisica.  Domicilio a efectos de notificaciones. Código Municipio INE |  | C. Municipio ine (00000 - si no consta)
67 | 1001 | 30 | An | Persona fisica.  Domicilio a efectos de notificaciones. 1)  Nombre del municipio  [A54]
68 | 1031 | 2 | An | Persona fisica.  Domicilio a efectos de notificaciones. 1)  Código de Provincia  [A55] |  | ('01', '02',...'52')
69 | 1033 | 100 | An | Persona fisica. Identificacion. dominio o direccion de internet [ A38]
70 | 1133 | 27 | An | Reservado para la Agencia Tributaria
71 | 1160 | 50 | An | Persona Física. Domicilio a efecto de notificaciones. 1) Destinatario (si es distinto del declarante)  [A59]
72 | 1210 | 2 | An | Persona Física. Domicilio a efecto de notificaciones. 1) En calidad de: (represent, apoder, familiar, etc.) [A60]
73 | 1212 | 10 | Num | Persona Física. Domicilio a efecto de notificaciones. 2) Apartado de Correos Número:  [A61]
74 | 1222 | 30 | An | Persona Física. Domicilio a efecto de notificaciones. 2) Población / Ciudad  [A62]
75 | 1252 | 5 | Num | Persona Física. Domicilio a efecto de notificaciones. 2) Código Postal  [A63]
76 | 1257 | 2 | An | Persona Física. Domicilio a efecto de notificaciones. 2) Código de Provincia  [A64] |  | ('01', '02',...'52')
77 | 1259 | 27 | An | Reservado para la Agencia Tributaria
78 | 1286 | 50 | An | Persona Física. Domicilio a efecto de notificaciones. 2) Destinatario (si es distinto del declarante)  [A68]
79 | 1336 | 2 | An | Persona Física. Domicilio a efecto de notificaciones. En calidad de: (represent, apoder, familiar, etc.)  [A69]
80 | 1338 | 5 | An | Persona fisica.  Domicilio gestión administrativa (si distinto del fiscal).  Tipo de vía [A71]
81 | 1343 | 5 | Num | Persona fisica.  Domicilio gestión administrativa (si distinto del fiscal). |  | Cod. via ine. De momento reservado a ceros
82 | 1348 | 50 | An | Persona fisica.  Domicilio gestión administrativa (si distinto del fiscal).  Nombre de la vía pública  [A72]
83 | 1398 | 3 | An | Persona fisica.  Domicilio gestión administrativa (si distinto del fiscal). Tipo Num.  [A73]
84 | 1401 | 5 | Num | Persona fisica.  Domicilio gestión administrativa (si distinto del fiscal).  Núm casa  [A74]
85 | 1406 | 3 | An | Persona fisica.  Domicilio gestión administrativa (si distinto del fiscal).  Calif. Un  [A75]
86 | 1409 | 3 | An | Persona fisica.  Domicilio gestión administrativa (si distinto del fiscal).  Bloque  [A76]
87 | 1412 | 3 | An | Persona fisica.  Domicilio gestión administrativa (si distinto del fiscal).  Portal  [A77]
88 | 1415 | 3 | An | Persona fisica.  Domicilio gestión administrativa (si distinto del fiscal).  Escal.  [A78]
89 | 1418 | 3 | An | Persona fisica.  Domicilio gestión administrativa (si distinto del fiscal).  Planta  [A79]
90 | 1421 | 3 | An | Persona fisica.  Domicilio gestión administrativa (si distinto del fiscal).  Puerta  [A80]
91 | 1424 | 40 | An | Persona fisica.  Domicilio gestión administrativa (si dist. del fiscal). Compl. domic (ej. Urb, Pol. Ind, C.C...) [A81]
92 | 1464 | 30 | An | Persona fisica.  Domicilio gestión administrativa (si dist. del fiscal). Local. / Poblac. (si es dist. de munic.) [A82]
93 | 1494 | 5 | Num | Persona fisica.  Domicilio gestión administrativa (si distinto del fiscal).  C. Postal  [A83]
94 | 1499 | 5 | Num | Persona fisica.  Domicilio gestión administrativa (si distinto del fiscal).  Código Municipio INE |  | C. Municipio ine (00000 - si no consta)
95 | 1504 | 30 | An | Persona fisica.  Domicilio gestión administrativa (si distinto del fiscal).  Nombre del municipio  [A84]
96 | 1534 | 2 | An | Persona fisica.  Domicilio gestión administrativa (si distinto del fiscal).  Código de Provincia  [A85] |  | ('01', '02',...'52')
97 | 1536 | 127 | An | Reservado para la Agencia Tributaria
98 | 1663 | 1 | An | P.F. Establecimientos Permanentes. ¿Opera en España a través de establec. permanente?  [A91] |  | S, N o blanco
99 | 1664 | 3 | Num | Persona Física. Establecimientos Permanentes. ¿Cuántos?  [A92]
100 | 1667 | 40 | An | Persona Física. Establecimientos Permanentes. Denominación 1  [A94]
101 | 1707 | 40 | An | Persona Física. Establecimientos Permanentes. Denominación 2  [A96]
102 | 1747 | 40 | An | Persona Física. Establecimientos Permanentes. Denominación 3  [A98]
103 | 1787 | 1 | An | Persona Física. Identificación. Empresario de Responsabilidad Limitada. Alta y baja [A9] |  | A, B o blanco
104 | 1788 | 2 | Num | Persona Física. Identificación. Empresario de Responsabilidad Limitada. Alta y baja. Fecha. Día  [A10]
105 | 1790 | 2 | Num | Persona Física. Identificación. Empresario de Responsabilidad Limitada. Alta y baja. Fecha. Mes  [A10]
106 | 1792 | 4 | Num | Persona Física. Identificación. Empresario de Responsabilidad Limitada. Alta y baja. Fecha. Año  [A10]
107 | 1796 | 20 | An | Persona fisica.  Domicilio fiscal en España. Referencia Catastral  [A30] *
108 | 1816 | 25 | An | Persona fisica.  Identificación. Código de identificación fiscal del Estado de residencia/NIF-IVA (NVAT)  [A90]
109 | 1841 | 2 | An | Persona fisica.  Identificación. Codigo pais en estado de residencia . (no residentes). Cod. Pais  [A2]
110 | 1843 | 1 | An | Persona fisica. Baja de domicilio de  notificaciones  [A40] |  | S o blanco
111 | 1844 | 2 | An | Reservado para la Agencia Tributaria
112 | 1846 | 2 | Num | Persona Física. Identificación. Fecha de efectos residencia fiscal .  Día  [A3B]
113 | 1848 | 2 | Num | Persona Física. Identificación. Fecha de efectos residencia fiscal .  Mes [A3B]
114 | 1850 | 4 | Num | Persona Física. Identificación. Fecha de efectos residencia fiscal .  Año [A3B]
115 | 1854 | 1 | An | indicador referencia catastral del domicilio fiscal  [A39] |  | blanco, '1','2','3','4' (Ver nota1)
116 | 1855 | 1 | An | Indcador  de baja domicilio gestion administrativa [A70] |  | S o blanco
117 | 1856 | 135 | An | Reservado para la Agencia Tributaria
118 | 1991 | 10 | An | Identificador de fin de registro. | obligatorio | </T03602A>
119 | 2001 |  | An | Salto de línea. Constante CRLF. | obligatorio
TOTAL |  | 2000 | Posiciones
 |  |  | Nota 1 | blanco, valor sin informar 
1. Inmueble con referencia catastral, situado en cualquier punto de territorio común con excepción de País Vasco y Navarra  
2.  Inmueble con referencia catastral, situado en la Comunidad Autónoma del Pais Vasco 
3. Inmueble con referencia catastral, situado en la Comunidad Autónoma de Navarra 
4. Inmueble sin referencia catastral asignada situado en cualquier punto del territorio común.

# Pag. 2B

 | Agencia Tributaria
Modelo 036 |  | Diseño de registro. Castellano
 |  | Declaración Censal/Declaración Censal Simplifica de alta, modificación y baja en el Censo de Empresarios, Profesionales y Retenedores
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 9 | An | Inicio del identificador de modelo y página. | obligatorio | <T03602B>
2 | 10 | 1 | A | Tipo declaración | obligatorio | blanco
3 | 11 | 1 | An | Pers. jcas. o entidades. Pers. jca o ent. residente o constit. en España/no resid. o constit. en el extr.  [B1,B2] |  | S, N o blanco
4 | 12 | 2 | An | Pers. jcas. o entidades. pers. jca. o ent. no residente o constituida en el extrj.  [B3] |  | Código País Iso
5 | 14 | 9 | An | Pers. jcas. o entidades. Identificación. N.I.F.  [B4]
6 | 23 | 125 | An | Pers. jcas. o entidades. Identificación. Razón o denominación social  [B5]
7 | 148 | 25 | An | Pers. jcas. o entidades. Identificación. Anagrama  [B6]
8 | 173 | 40 | An | Pers. jcas. o entidades. Identificación. NIF otros paises  [B7]
9 | 213 | 2 | Num | Pers. jcas. o entidades. Identificación. Fecha acuerdo voluntades. Día [B8]
10 | 215 | 2 | Num | Pers. jcas. o entidades. Identificación. Fecha acuerdo voluntades. Mes  [B8]
11 | 217 | 4 | Num | Pers. jcas. o entidades. Identificación. Fecha acuerdo voluntades. Año  [B8]
12 | 221 | 2 | Num | Pers. jcas. o entidades. Identificación. Fecha constitución. Día  [B9]
13 | 223 | 2 | Num | Pers. jcas. o entidades. Identificación. Fecha constitución. Mes  [B9]
14 | 225 | 4 | Num | Pers. jcas. o entidades. Identificación. Fecha constitución. Año  [B9]
15 | 229 | 2 | Num | Pers. jcas. o entidades. Identificación. Fecha inscripción registral. Día  [B10]
16 | 231 | 2 | Num | Pers. jcas. o entidades. Identificación. Fecha inscripción registral. Mes  [B10]
17 | 233 | 4 | Num | Pers. jcas. o entidades. Identificación. Fecha inscripción registral. Año  [B10]
18 | 237 | 5 | An | Pers.jcas. o entidades.  Domicilio fiscal en España. Tipo de vía  [B11]
19 | 242 | 5 | Num | Pers.jcas. o entidades.  Domicilio fiscal en España. |  | Cod. via ine. De momento reservado a ceros
20 | 247 | 50 | An | Pers.jcas. o entidades.  Domicilio fiscal en España. Nombre de la vía pública  [B12]
21 | 297 | 3 | An | Pers.jcas. o entidades.  Domicilio fiscal en España.Tipo Num.  [B13]
22 | 300 | 5 | Num | Pers.jcas. o entidades.  Domicilio fiscal en España. Núm casa  [B14]
23 | 305 | 3 | An | Pers.jcas. o entidades.  Domicilio fiscal en España. Calif. Un  [B15]
24 | 308 | 3 | An | Pers.jcas. o entidades.  Domicilio fiscal en España. Bloque  [B16]
25 | 311 | 3 | An | Pers.jcas. o entidades.  Domicilio fiscal en España. Portal  [B17]
26 | 314 | 3 | An | Pers.jcas. o entidades.  Domicilio fiscal en España. Escal.  [B18]
27 | 317 | 3 | An | Pers.jcas. o entidades.  Domicilio fiscal en España. Planta  [B19]
28 | 320 | 3 | An | Pers.jcas. o entidades.  Domicilio fiscal en España. Puerta  [B20]
29 | 323 | 40 | An | Pers.jcas. o entidades.  Domicilio fiscal en España. Compl domicilio (ej. Urbanización, Pol. Ind, C.C.)  [B21]
30 | 363 | 30 | An | Pers.jcas. o entidades.  Domicilio fiscal en España. Localidad / Población (si es distinta de municipio)  [B22]
31 | 393 | 5 | Num | Pers.jcas. o entidades.  Domicilio fiscal en España. C. Postal  [B23]
32 | 398 | 5 | Num | Pers.jcas. o entidades.  Domicilio fiscal en España.Código Municipio INE |  | C. Municipio ine (00000 - si no consta)
33 | 403 | 30 | An | Pers.jcas. o entidades.  Domicilio fiscal en España. Nombre del municipio  [B24]
34 | 433 | 2 | An | Pers.jcas. o entidades.  Domicilio fiscal en España. Código de Provincia  [B25] |  | ('01', '02',...'52')
35 | 435 | 100 | An | Pers.jcas. o entidades.    Datos de telefonos y direcciones electronicas para recibir avisos. E-mail  [B38]
36 | 535 | 1 | An | Persona jurídica.  Datos telefonos y direccione para recibir avisos. AEAT Alta |  | S o blanco
37 | 536 | 1 | An | Persona jurídica.  Datos telefonos y direccione para recibir avisos. AEAT Baja |  | S o blanco
38 | 537 | 1 | An | Persona jurídica.  Datos telefonos y direccione para recibir avisos. TEA Alta |  | S o blanco
39 | 538 | 1 | An | Persona jurídica.  Datos telefonos y direccione para recibir avisos. TEA Baja |  | S o blanco
40 | 539 | 1 | An | Persona jurídica.  Datos telefonos y direccione para recibir avisos. DGT Alta |  | S o blanco
41 | 540 | 1 | An | Persona jurídica.  Datos telefonos y direccione para recibir avisos. DGT Baja |  | S o blanco
42 | 541 | 1 | An | Persona  jurídica.  Datos telefonos y direccione para recibir avisos. E-mail Alta/Modificación |  | S o blanco
43 | 542 | 1 | An | Persona  jurídica.  Datos telefonos y direccione para recibir avisos. E-mail Baja |  | S o blanco
44 | 543 | 19 | An | Reservado para la Agencia Tributaria
45 | 562 | 50 | An | Pers.jcas. o entidades.  Domicilio fiscal-Social en el Est. de resid. (no resid). Domicilio (Adress)  [B31]
46 | 612 | 40 | An | Pers.jcas. o entidades.  Domicilio fiscal-social en el Est. de resid. (no resid). Compl. de domic. (si fuese nec.)  [B32]
47 | 652 | 30 | An | Pers.jcas. o entidades.  Domicilio fiscal-social en el Est. de resid. (no residentes). Población / Ciudad  [B34]
48 | 682 | 100 | An | Pers.jcas. o entidades.  Datos identificacion. Dominio o direccion de internet [B28]
49 | 782 | 10 | An | Pers.jcas. o entidades.  Domicilio fiscal-social en el Est. de resid. (no residentes). C. Postal (ZIP)  [B33]
50 | 792 | 30 | An | Pers.jcas. o entidades.  Domicilio fiscal-social en el Est. de resid. (no residentes). Provincia/ Región/ Estado  [B35]
51 | 822 | 30 | An | Pers.jcas. o entidades.  Domicilio fiscal-social en el Est. de resid. (no residentes). País RESERVADO  [B36]
52 | 852 | 2 | An | Pers.jcas. o entidades.  Domicilio fiscal-social en el Est. de resid. (no residentes). Cod. Pais  [B37]
53 | 854 | 4 | An | Pers.jcas. o entidades. Datos de telefonos y direcciones electronicas para recibir avisos . Prefijo pais movil  [B26] |  | blancos si el movil es español
54 | 858 | 15 | An | Pers.jcas. o entidades. Datos de telefonos y direcciones electronicas para recibir avisos . Tfno. Móvil  [B27]
55 | 873 | 1 | An | Persona jurídica.  Datos telefonos y direccione para recibir avisos. Tfno. Móvil Alta/Modificación |  | S o blanco
56 | 874 | 1 | An | Persona jurídica.  Datos telefonos y direccione para recibir avisos. Tfno. Móvil Baja |  | S o blanco
57 | 875 | 1 | An | Persona jurídica.  Datos telefonos y direccione para recibir avisos. Aplicación Móvil AEAT Alta |  | S o blanco
58 | 876 | 1 | An | Persona jurídica.  Datos telefonos y direccione para recibir avisos. Aplicación Móvil AEAT Baja |  | S o blanco
59 | 877 | 22 | An | Reservado para la Agencia Tributaria
60 | 899 | 5 | An | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. 1)  Tipo de vía  [B41]
61 | 904 | 5 | Num | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. Código Municipio INE |  | Cod. via ine. De momento reservado a ceros
62 | 909 | 50 | An | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. 1)  Nombre de la vía pública  [B42]
63 | 959 | 3 | An | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. 1) Tipo Num.  [B43]
64 | 962 | 5 | Num | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. 1)  Núm casa  [B44]
65 | 967 | 3 | An | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. 1)  Calif. Un  [B45]
66 | 970 | 3 | An | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. 1)  Bloque  [B46]
67 | 973 | 3 | An | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. 1)  Portal  [B47]
68 | 976 | 3 | An | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. 1)  Escal.  [B48]
69 | 979 | 3 | An | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. 1)  Planta  [B49]
70 | 982 | 3 | An | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. 1)  Puerta  [B50]
71 | 985 | 40 | An | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. 1) Compl. Domic. (ej. Urb, Pol. Ind, C. C...)  [B51]
72 | 1025 | 30 | An | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. 1) Local. / Poblac. (si es dist. de munic.)  [B52]
73 | 1055 | 5 | Num | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. 1)  C. Postal  [B53]
74 | 1060 | 5 | Num | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. Código Municipio INE |  | C. Municipio ine (00000 - si no consta)
75 | 1065 | 30 | An | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. 1)  Nombre del municipio  [B54]
76 | 1095 | 2 | An | Pers.jcas. o entidades.  Domicilio a efectos de notificaciones. 1)  Código de Provincia  [B55] |  | ('01', '02',...'52')
77 | 1097 | 100 | An | Pers.jcas. o entidades.  Datos identificacion. Dominio o direccion de internet [B29]
78 | 1197 | 27 | An | Reservado para la Agencia Tributaria
79 | 1224 | 50 | An | Pers.jcas. o entidades. Domicilio a efecto de notificaciones. 1) Destinatario (si es distinto del declarante)  [B59]
80 | 1274 | 2 | An | Pers.jcas. o entidades.Domicilio a efecto de notificaciones. 1) En calidad de: (represent, apod, familiar, etc...)  [B60]
81 | 1276 | 10 | Num | Pers.jcas. o entidades.Domicilio a efecto de notificaciones. 2) Apartado de Correos Número:  [B61]
82 | 1286 | 30 | An | Pers.jcas. o entidades. Domicilio a efecto de notificaciones. 2) Población / Ciudad  [B62]
83 | 1316 | 5 | Num | Pers.jcas. o entidades. Domicilio a efecto de notificaciones. 2) Código Postal  [B63]
84 | 1321 | 2 | An | Pers.jcas. o entidades. Domicilio a efecto de notificaciones. 2) Código de Provincia  [B64] |  | ('01', '02',...'52')
85 | 1323 | 27 | An | Reservado para la Agencia Tributaria
86 | 1350 | 50 | An | Pers.jcas. o entidades.Domicilio a efecto de notificaciones. 2) Destinatario (si es distinto del declarante)  [B68]
87 | 1400 | 2 | An | Pers.jcas. o entidades. Domicilio a efecto de notificaciones. En calidad de: (represent, apod, familiar, etc...)  [B69]
88 | 1402 | 5 | An | Pers.jcas. o entidades.  Domicilio social (si distinto del fiscal).  Tipo de vía  [B71]
89 | 1407 | 5 | Num | Pers.jcas. o entidades.  Domicilio social en España(si distinto del fiscal). |  | Cod. via ine. De momento reservado a ceros
90 | 1412 | 50 | An | Pers.jcas. o entidades.  Domicilio social en España (si distinto del fiscal).  Nombre de la vía pública  [B72]
91 | 1462 | 3 | An | Pers.jcas. o entidades.  Domicilio social en España(si distinto del fiscal). Tipo Num.  [B73]
92 | 1465 | 5 | Num | Pers.jcas. o entidades.  Domicilio social en España (si distinto del fiscal).  Núm casa  [B74]
93 | 1470 | 3 | An | Pers.jcas. o entidades.  Domicilio social en España(si distinto del fiscal).  Calif. Un  [B75]
94 | 1473 | 3 | An | Pers.jcas. o entidades.  Domicilio social en España (si distinto del fiscal).  Bloque  [B76]
95 | 1476 | 3 | An | Pers.jcas. o entidades.  Domicilio social en España (si distinto del fiscal).  Portal  [B77]
96 | 1479 | 3 | An | Pers.jcas. o entidades.  Domicilio social en España (si distinto del fiscal).  Escal.  [B78]
97 | 1482 | 3 | An | Pers.jcas. o entidades.  Domicilio social en España (si distinto del fiscal).  Planta  [B79]
98 | 1485 | 3 | An | Pers.jcas. o entidades.  Domicilio social en España (si distinto del fiscal).  Puerta  [B80]
99 | 1488 | 40 | An | Pers.jcas. o entidades.  Domicilio social en España(si distinto del fiscal). Complem. Domic. (ej. Urb, Pol. Ind, C.C...)  [B81]
100 | 1528 | 30 | An | Pers.jcas. o entidades.  Domicilio social en España (si distinto del fiscal).  Local. / Población (si es dist de munic)  [B82]
101 | 1558 | 5 | Num | Pers.jcas. o entidades.  Domicilio social en España(si distinto del fiscal).  C. Postal  [B83]
102 | 1563 | 5 | Num | Pers.jcas. o entidades.  Domicilio social en España (si distinto del fiscal).  Código Municipio INE |  | C. Municipio ine (00000 - si no consta)
103 | 1568 | 30 | An | Pers.jcas. o entidades.  Domicilio social en España (si distinto del fiscal).  Nombre del municipio  [B84]
104 | 1598 | 2 | An | Pers.jcas. o entidades.  Domicilio social en España (si distinto del fiscal).  Código de Provincia  [B85] |  | ('01', '02',...'52')
105 | 1600 | 127 | An | Reservado para la Agencia Tributaria
106 | 1727 | 1 | An | Pers. jcas. o entidades. ¿Tiene personalidad jca.?  [65] |  | S, N o blanco
107 | 1728 | 1 | An | Pers. jcas. o entidades. Persona Jurídica [68] |  | "S" o blanco
108 | 1729 | 2 | An | Pers. jcas. o entidades. Forma jurídica  [69]
109 | 1731 | 1 | An | Pers. jcas. o entidades. Entidad en atribución de rentas constituida en España con activ. económica  [70] |  | "S" o blanco
110 | 1732 | 2 | An | Pers. jcas. o entidades. Clase de entidad  [71]
111 | 1734 | 1 | An | Pers. jcas. o entidades. Entidad en atribución de rentas constituida en España sin activ. económica  [B72] |  | "S" o blanco
112 | 1735 | 2 | An | Pers. jcas. o entidades. Clase de entidad  [73]
113 | 1737 | 1 | An | Pers. jcas. o entidades. Entidad en atribución de rentas constituida en el extrj. con presencia en España  [B74] |  | "S" o blanco
114 | 1738 | 2 | An | Pers. jcas. o entidades. Clase de entidad  [75]
115 | 1740 | 1 | An | Pers. jcas. o entidades. Entidad en atribución de rentas constituida en el extrj. sin presencia en España  [B76] |  | "S" o blanco
116 | 1741 | 2 | An | Pers. jcas. o entidades. Clase de entidad  [77]
117 | 1743 | 1 | An | Pers. jcas. o entidades. Otras entidades  [78] |  | "S" o blanco
118 | 1744 | 2 | An | Pers. jcas. o entidades. Otras entidades. Clase de entidad  [79]
119 | 1746 | 1 | An | Pers. jcas. o entidades. Establec. Permanent. ¿Opera en españa a traves de establec. permanente?  [B91] |  | S, N o blanco
120 | 1747 | 3 | Num | Pers. jcas. o entidades. Establec. Permanent. ¿Cuántos?  [B92]
121 | 1750 | 9 | An | Pers. jcas. o entidades. Establec. Permanent. N.I.F. 1  [B93]
122 | 1759 | 40 | An | Pers. jcas. o entidades. Establec. Permanent. Denominación 1  [B94]
123 | 1799 | 9 | An | Pers. jcas. o entidades. Establec. Permanent. N.I.F. 2  [B95]
124 | 1808 | 40 | An | Pers. jcas. o entidades. Establec. Permanent. Denominación 2  [B96]
125 | 1848 | 9 | An | Pers. jcas. o entidades. Establec. Permanent. N.I.F. 3  [B97]
126 | 1857 | 40 | An | Pers. jcas. o entidades. Establec. Permanent. Denominación 3  [B98]
127 | 1897 | 20 | An | Pers.jcas. o entidades.  Domicilio fiscal en España. Referencia Catastral [B30]
128 | 1917 | 25 | An | Pers.jcas. o entidades.  Identificación. Código de identificación fiscal del Estado de residencia/NIF-IVA (NVAT)  [B90]
129 | 1942 | 1 | An | indicador de domicilio fiscal en el extranjero/social en el extranjero |  | F- fiscal extranjero, S-social extranjero, A- ambos  o  '  ' - no consta
130 | 1943 | 1 | An | indicador baja de domicilio de notificaciones (b40) |  | S- si o blanco
131 | 1944 | 2 | An | Reservado para la Agencia Tributaria
132 | 1946 | 2 | Num | Pers.jcas. o entidades. Identificación. Fecha de efectos residencia fiscal .  Día  [B3B]
133 | 1948 | 2 | Num | Pers.jcas. o entidades. Identificación. Fecha de efectos residencia fiscal .  Mes [B3B]
134 | 1950 | 4 | Num | Pers.jcas. o entidades. Identificación. Fecha de efectos residencia fiscal .  Año [B3B]
135 | 1954 | 1 | An | indicador referencia catastral del domicilio fiscal  [B39] |  | blanco, '1','2','3','4' (Ver nota1)
136 | 1955 | 136 | An | Reservado para la Agencia Tributaria
137 | 2091 | 10 | An | Identificador de fin de registro. | obligatorio | </T03602B>
138 | 2101 |  | An | Salto de línea. Constante CRLF. | obligatorio
TOTAL |  | 2100 | Posiciones
 |  |  | Nota 1 | blanco, valor sin informar 
1. Inmueble con referencia catastral, situado en cualquier punto de territorio común con excepción de País Vasco y Navarra  
2.  Inmueble con referencia catastral, situado en la Comunidad Autónoma del Pais Vasco 
3. Inmueble con referencia catastral, situado en la Comunidad Autónoma de Navarra 
4. Inmueble sin referencia catastral asignada situado en cualquier punto del territorio común.

# Pag. 2C

 | Agencia Tributaria
Modelo 036 |  | Diseño de registro. Castellano
 |  | Declaración Censal/Declaración Censal Simplifica de alta, modificación y baja en el Censo de Empresarios, Profesionales y Retenedores
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 9 | An | Inicio del identificador de modelo y página. | obligatorio | <T03602C>
2 | 10 | 1 | A | Tipo declaración | obligatorio | blanco
3 | 11 | 9 | An | Establecimiento perm. de una per. jca. o ent. no residente. N.I.F.  [C1]
4 | 20 | 125 | An | Establecimiento perm. de una per. jca. o ent. no residente. Razón o denominación social  [C2]
5 | 145 | 25 | An | Establecimiento perm. de una per. jca. o ent. no residente. Anagrama  [C3]
6 | 170 | 2 | An | Establecimiento perm. de una per. jca. o ent. no residente. Tipo de establ. permanente  [C4]
7 | 172 | 1 | An | Establecimiento perm. de una per. jca. o ent. no residente. ¿Es una sucursal de la entidad no residente?  [C5] |  | S, N o blanco
8 | 173 | 9 | An | Establ. perm. de una per. jca. o ent. no resid. Pers. o ent. no resid. de la que depende. N.I.F. (si dispone) [C6]
9 | 182 | 125 | An | Establ. perm. de una per. jca. o ent. no resid. Pers. o ent. no resid. de la que dep. Razón o denom. Social  [C7]
10 | 307 | 2 | An | Establ. perm. de una per. jca. o ent. no resid. Pers. o ent. no resid. de la que depende. Estado de resid. [C8] |  | codigo iso
11 | 309 | 5 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio fiscal en España. Tipo de vía  [C11]
12 | 314 | 5 | Num | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio fiscal en España. |  | Cod. via ine. De momento reservado a ceros
13 | 319 | 50 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio fiscal en España. Nombre de la vía públ  [C12]
14 | 369 | 3 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio fiscal en España.Tipo Num.  [C13]
15 | 372 | 5 | Num | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio fiscal en España. Núm casa  [C14]
16 | 377 | 3 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio fiscal en España. Calif. Un  [C15]
17 | 380 | 3 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio fiscal en España. Bloque  [C16]
18 | 383 | 3 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio fiscal en España. Portal  [C17]
19 | 386 | 3 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio fiscal en España. Escal.  [C18]
20 | 389 | 3 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio fiscal en España. Planta  [C19]
21 | 392 | 3 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio fiscal en España. Puerta  [C20]
22 | 395 | 40 | An | Establec perm. de una per.jca. o ent. no resid. Domic fiscal en España. Compl domic (ej. Urb, Pol. Ind...)  [C21]
23 | 435 | 30 | An | Establec perm. de una per.jca. o ent. no resid. Domic fisc en España. Local / Poblac (si dist. de munic) [C22]
24 | 465 | 5 | Num | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio fiscal en España. C. Postal  [C23]
25 | 470 | 5 | Num | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio fiscal en España. Código Municipio INE |  | C. Municipio ine (00000 - si no consta)
26 | 475 | 30 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio fiscal en España. Nombre del municipio  [C24]
27 | 505 | 2 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio fiscal en España. Código de Provincia  [C25] |  | ('01', '02',...'52')
28 | 507 | 100 | An | Establecimiento perm. de una per.jca. o ent. no resid. Datos de telefonos y direcciones para avisos. E-mail  [C29]
29 | 607 | 1 | An | Establecimiento perm. de una per.jca. o ent. no resid.  Datos telefonos y direccione para recibir avisos. AEAT Alta |  | S o blanco
30 | 608 | 1 | An | Establecimiento perm. de una per.jca. o ent. no resid.  Datos telefonos y direccione para recibir avisos. AEAT Baja |  | S o blanco
31 | 609 | 1 | An | Establecimiento perm. de una per.jca. o ent. no resid.  Datos telefonos y direccione para recibir avisos. TEA Alta |  | S o blanco
32 | 610 | 1 | An | Establecimiento perm. de una per.jca. o ent. no resid.  Datos telefonos y direccione para recibir avisos. TEA Baja |  | S o blanco
33 | 611 | 1 | An | Establecimiento perm. de una per.jca. o ent. no resid.  Datos telefonos y direccione para recibir avisos. DGT Alta |  | S o blanco
34 | 612 | 1 | An | Establecimiento perm. de una per.jca. o ent. no resid.  Datos telefonos y direccione para recibir avisos. DGT Baja |  | S o blanco
35 | 613 | 1 | An | Establecimiento perm. de una per.jca. o ent. no resid.  Datos telefonos y direccione para recibir avisos. E-mail Alta/Modificación |  | S o blanco
36 | 614 | 1 | An | Establecimiento perm. de una per.jca. o ent. no resid.  Datos telefonos y direccione para recibir avisos. E-mail Baja |  | S o blanco
37 | 615 | 19 | An | Reservado para la Agencia Tributaria
38 | 634 | 5 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio a efectos de notificaciones. 1) Tipo de vía [C41]
39 | 639 | 5 | Num | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio a efectos de notificaciones. |  | Cod. via ine. De momento reservado a ceros
40 | 644 | 50 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domic a efect de notific. 1) Nombre de la vía públ.  [C42]
41 | 694 | 3 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio a efectos de notificaciones. 1) Tipo Num.  [C43]
42 | 697 | 5 | Num | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio a efectos de notificaciones. 1) Núm casa  [C44]
43 | 702 | 3 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio a efectos de notificaciones. 1) Calif. Un  [C45]
44 | 705 | 3 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio a efectos de notificaciones. 1) Bloque [C46]
45 | 708 | 3 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio a efectos de notificaciones. 1) Portal  [C47]
46 | 711 | 3 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio a efectos de notificaciones. 1) Escal.  [C48]
47 | 714 | 3 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio a efectos de notificaciones. 1) Planta  [C49]
48 | 717 | 3 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio a efectos de notificaciones. 1) Puerta  [C50]
49 | 720 | 40 | An | Establec perm. de una per.jca. o ent. no resid. Domic a efectos de notfi. 1) Complemento domicilio  [C51]
50 | 760 | 30 | An | Establec perm. de una per.jca. o ent. no resid. Domic a efect. de notif. 1) Local / Pobl (si dist. de munic)  [C52]
51 | 790 | 5 | Num | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio a efectos de notificaciones. 1) C. Postal  [C53]
52 | 795 | 5 | Num | Establecimiento perm. de una per.jca. o ent. no resid. Domicilio a efectos de notificaciones. Código Municipio INE |  | C. Municipio ine (00000 - si no consta)
53 | 800 | 30 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domic. a efectos de notif. 1) Nombre del municipio  [C54]
54 | 830 | 2 | An | Establecimiento perm. de una per.jca. o ent. no resid. Domic. a efectos de notificaciones. 1) Código de Provincia  [C55] |  | ('01', '02',...'52')
55 | 832 | 100 | An | Establecimiento perm. de una per.jca. o ent. no resid.Datos identificacion.Dominio o direccion internet  [C27]
56 | 932 | 4 | An | Establecimiento perm. de una per.jca. o ent. no resid. Datos  tfnos y direc. electronicas para recibir avisos . Prefijo pais movil  [C10] |  | blancos si el movil es español
57 | 936 | 15 | An | Establecimiento perm. de una per.jca. o ent. no resid. Datos  tfnos y direc. electronicas para recibir avisos . Tfno. Móvil  [C26]
58 | 951 | 1 | An | Establecimiento perm. de una per.jca. o ent. no resid.  Datos telefonos y direccione para recibir avisos. Tfno. Móvil Alta/Modificación |  | S o blanco
59 | 952 | 1 | An | Establecimiento perm. de una per.jca. o ent. no resid.  Datos telefonos y direccione para recibir avisos. Tfno. Móvil Baja |  | S o blanco
60 | 953 | 1 | An | Establecimiento perm. de una per.jca. o ent. no resid.  Datos telefonos y direccione para recibir avisos. Aplicación Móvil AEAT Alta |  | S o blanco
61 | 954 | 1 | An | Establecimiento perm. de una per.jca. o ent. no resid.  Datos telefonos y direccione para recibir avisos. Aplicación Móvil AEAT Baja |  | S o blanco
62 | 955 | 4 | An | Reservado para la Agencia Tributaria
63 | 959 | 50 | An | Establ.perm. de una per.jca. o ent. no resid. Domicilio a efecto de notificaciones. 1) Destinatario (si es distinto del declarante)  [C59]
64 | 1009 | 2 | An | Establ.perm. de una per.jca. o ent. no resid.. Domicilio a efecto de notificaciones. 1) En calidad de: (represent, apod, familiar, etc...)  [C60]
65 | 1011 | 10 | Num | Establ. perm. de una per.jca. o ent. no resid.Domicilio a efecto de notificaciones. 2) Apartado de Correos Número:  [C61]
66 | 1021 | 30 | An | Establ. perm. de una per.jca. o ent. no resid.Domicilio a efecto de notificaciones. 2) Población / Ciudad  [C62]
67 | 1051 | 5 | Num | Establ. perm. de una per.jca. o ent. no resid. Domicilio a efecto de notificaciones. 2) Código Postal  [C63]
68 | 1056 | 2 | An | Establ. perm. de una per.jca. o ent. no resid.. Domicilio a efecto de notificaciones. 2) Código de Provincia  [C64] |  | ('01', '02',...'52')
69 | 1058 | 27 | An | Reservado para la Agencia Tributaria
70 | 1085 | 50 | An | Persona Física. Domicilio a efecto de notificaciones. 2) Destinatario (si es distinto del declarante)  [C68]
71 | 1135 | 2 | An | Persona Física. Domicilio a efecto de notificaciones. En calidad de: (represent, apod, familiar, etc...) [C69]
72 | 1137 | 20 | An | Establecimiento perm. de una per. jca. o ent. no residente.  Domicilio fiscal en España. Referencia Catastral [C30]
73 | 1157 | 25 | An | Establecimiento perm. de una per. jca. o ent. no residente. 
Código de identificación fiscal del Estado de residencia/NVAT  [C9]
74 | 1182 | 1 | An | indicador de baja domicilio de notificaciones [C40] |  | S -  si o blanco
75 | 1183 | 100 | An | Establecimiento perm. de una per.jca. o ent. no resid.Datos identificacion.Dominio o direccion internet  [C28]
76 | 1283 | 2 | An | Reservado para la Agencia Tributaria
77 | 1285 | 1 | An | Indicador referencia catastral del domicilio fiscal [C39] |  | blanco, '1','2','3','4' (ver Nota 1)
78 | 1286 | 2 | Num | Establecimiento perm. de una per.jca. o ent. no resid. Identificación. Fecha inscripción registro mercantil. Día  [C70]
79 | 1288 | 2 | Num | Establecimiento perm. de una per.jca. o ent. no resid.. Fecha inscripción registro mercantil.. Mes   [C70]
80 | 1290 | 4 | Num | Establecimiento perm. de una per.jca. o ent. no resid.  Fecha inscripción registro mercantil. Año   [C70]
81 | 1294 | 2 | Num | Establecimiento perm. de una per.jca. o ent. no resid.. Fecha de constitucion. Día  [C71]
82 | 1296 | 2 | Num | Establecimiento perm. de una per.jca. o ent. no resid.. Fecha de constitucion.. Mes   [C71]
83 | 1298 | 4 | Num | Establecimiento perm. de una per.jca. o ent. no resid. Fecha de constitucion Año   [C71]
84 | 1302 | 89 | An | Reservado para la Agencia Tributaria
85 | 1391 | 10 | An | Identificador de fin de registro. | obligatorio | </T03602C>
86 | 1401 |  | An | Salto de línea. Constante CRLF. | obligatorio
TOTAL |  | 1400 | Posiciones
 |  |  | Nota 1 | blanco, valor sin informar 
1. Inmueble con referencia catastral, situado en cualquier punto de territorio común con excepción de País Vasco y Navarra  
2.  Inmueble con referencia catastral, situado en la Comunidad Autónoma del Pais Vasco 
3. Inmueble con referencia catastral, situado en la Comunidad Autónoma de Navarra 
4. Inmueble sin referencia catastral asignada situado en cualquier punto del territorio común.

# Pag. 3

 | Agencia Tributaria
Modelo 036 |  | Diseño de registro. Castellano
 |  | Declaración Censal/Declaración Censal Simplifica de alta, modificación y baja en el Censo de Empresarios, Profesionales y Retenedores
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 9 | An | Inicio del identificador de modelo y página. | obligatorio | <T036030>
2 | 10 | 1 | A | Tipo declaración | obligatorio | blanco o "C" (compl.)
3 | 11 | 1 | An | 3.1.- Causa de la presentación. Alta, Baja o Modificación del representante [300,301,302] |  | A, B, M o blanco
4 | 12 | 2 | Num | 3.1.- Causa de la presentación. Alta, Baja o Modificación del representante. Día  [303]
5 | 14 | 2 | Num | 3.1.- Causa de la presentación. Alta, Baja o Modificación del representante. Mes  [303]
6 | 16 | 4 | Num | 3.1.- Causa de la presentación. Alta, Baja o Modificación del representante. Año  [303]
7 | 20 | 9 | An | 3.1.- Identificación del representante. NIF  [304]
8 | 29 | 125 | An | 3.1.- Identificación del representante. Apellidos y nombre o razón social  [305]
9 | 154 | 1 | An | 3.1.- Identificación del representante. Residente: sí/no [306] |  | S, N o blanco
10 | 155 | 1 | An | 3.1.- Identificacion persona fisica designada.Causa de la presentación. Alta, Baja  [311,312] |  | A, B, o blanco
11 | 156 | 2 | Num | 3.1.- Identificacion persona fisica designada- Causa de la presentación. Alta, Baja  Día   [313]
12 | 158 | 2 | Num | 3.1.- Identificacion persona fisica designada Causa de la presentación. Alta, Baja . Mes  [313]
13 | 160 | 4 | Num | 3.1.- Identificacion persona fisica designada Causa de la presentación. Alta, Baja. Año  [313]
14 | 164 | 9 | An | 3.1.  Identificacion persona fisica designada. NIF  [307]
15 | 173 | 40 | An | 3.1.  Identificacion persona fisica designada. Apellido 1  [308]
16 | 213 | 40 | An | 3.1.  Identificacion persona fisica designada. Apellido 2  [309]
17 | 253 | 45 | An | 3.1.  Identificacion persona fisica designada. Nombre  [310]
18 | 298 | 182 | An | Reservado para la Agencia Tributaria
19 | 480 | 1 | An | 3.2.- Causa de la representación.  [330 332] |  | (L= legal /V = voluntaria)
20 | 481 | 2 | Num | 3.1.- Causa de la representación. Legal. Clave  [331]
21 | 483 | 2 | Num | 3.1.- Tipo de representación. Clave  [333]
22 | 485 | 2 | Num | 3.1.- Título de representación. Clave  [334]
23 | 487 | 1 | An | 3.2.- Causa de la presentación. Alta, Baja o Modificación del representante  [350,351,352] |  | A, B, M o blanco
24 | 488 | 2 | Num | 3.2.- Causa de la presentación. Alta, Baja o Modificación del representante. Día  [353]
25 | 490 | 2 | Num | 3.2.- Causa de la presentación. Alta, Baja o Modificación del representante. Mes  [353]
26 | 492 | 4 | Num | 3.2.- Causa de la presentación. Alta, Baja o Modificación del representante. Año  [353]
27 | 496 | 9 | An | 3.2.- Identificación del representante. NIF  [354]
28 | 505 | 125 | An | 3.2.- Identificación del representante. Apellidos y nombre o razón social  [355]
29 | 630 | 1 | An | 3.2.- Identificación del representante. Residente: sí/no  [356] |  | S, N o blanco
30 | 631 | 1 | An | 3.2.- Identificacion persona fisica designada.Causa de la presentación. Alta, Baja  [361,362] |  | A, B, o blanco
31 | 632 | 2 | Num | 3.2.- Identificacion persona fisica designada- Causa de la presentación. Alta, Baja  Día   [363]
32 | 634 | 2 | Num | 3.2.- Identificacion persona fisica designada Causa de la presentación. Alta, Baja . Mes  [363]
33 | 636 | 4 | Num | 3.2.- Identificacion persona fisica designada Causa de la presentación. Alta, Baja. Año  [363]
34 | 640 | 9 | An | 3.2.  Identificacion persona fisica designada. NIF  [357]
35 | 649 | 40 | An | 3.2.  Identificacion persona fisica designada. Apellido 1  [358]
36 | 689 | 40 | An | 3.2.  Identificacion persona fisica designada. Apellido 2  [359]
37 | 729 | 45 | An | 3.2..  Identificacion persona fisica designada. Nombre  [360]
38 | 774 | 182 | An | Reservado para la Agencia Tributaria
39 | 956 | 1 | An | 3.2.- Causa de la representación.  [380 382] |  | (L= legal /V = voluntaria)
40 | 957 | 2 | Num | 3.2.- Causa de la representación. Legal. Clave  [381]
41 | 959 | 2 | Num | 3.2.- Tipo de representación. Clave  [383]
42 | 961 | 2 | Num | 3.2.- Título de representación. Clave  [384]
43 | 963 | 228 | An | Reservado para la Agencia Tributaria
44 | 1191 | 10 | An | Identificador de fin de registro. | obligatorio | </T036030>
45 | 1201 |  | An | Salto de línea. Constante CRLF. | obligatorio
TOTAL |  | 1200 | Posiciones

# Pag. 4

 | Agencia Tributaria
Modelo 036 |  | Diseño de registro. Castellano
 |  | Declaración Censal/Declaración Censal Simplifica de alta, modificación y baja en el Censo de Empresarios, Profesionales y Retenedores
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 9 | An | Inicio del identificador de modelo y página. | obligatorio | <T036040>
2 | 10 | 1 | A | Tipo declaración | obligatorio | blanco o "C" (compl.)
3 | 11 | 60 | An | Actividad. Descripción de la actividad. [400]
4 | 71 | 1 | An | Actividad. Sección I.A.E.  [402] |  | Tabla
5 | 72 | 4 | An | Actividad. Grupo o epígrafe.  [402] |  | Tabla
6 | 76 | 3 | An | Actividad. Tipo de actividad.  [403] |  | Tabla
7 | 79 | 1 | An | La actividad se desarrolla fuera de un local determinado. Alta  [405] |  | "S" o blanco
8 | 80 | 2 | Num | La actividad se desarrolla fuera de un local determinado. Fecha. Dia.  [406]
9 | 82 | 2 | Num | La actividad se desarrolla fuera de un local determinado. Fecha. Mes.  [406]
10 | 84 | 4 | Num | La actividad se desarrolla fuera de un local determinado. Fecha. Año.  [406]
11 | 88 | 1 | An | La actividad se desarrolla fuera de un local determinado. Baja  [408] |  | "S" o blanco
12 | 89 | 2 | Num | La actividad se desarrolla fuera de un local determinado. Fecha. Dia.  [409]
13 | 91 | 2 | Num | La actividad se desarrolla fuera de un local determinado. Fecha. Mes.  [409]
14 | 93 | 4 | Num | La actividad se desarrolla fuera de un local determinado. Fecha. Año.  [409]
15 | 97 | 13 | An | La actividad se desarrolla fuera de un local determinado. Nº referencia.  [410]
16 | 110 | 25 | An | La actividad se desarrolla fuera de un local determinado. Municipio.  [411]
17 | 135 | 2 | An | La actividad se desarrolla fuera de un local determinado. Código de Provincia |  | ('01', '02',...'52')
18 | 137 | 6 | Num | La actividad se desarrolla fuera de un local determinado. Código de Municipio. Reservado
19 | 143 | 20 | An | La actividad se desarrolla en local determinado. Referencia catastral.  [412]
20 | 163 | 17 | An | La actividad se desarrolla en local determinado. S.G.  [413] |  | Tabla
21 | 180 | 25 | An | La actividad se desarrolla en local determinado. Nombre de la vía pública  [414]
22 | 205 | 5 | Num | La actividad se desarrolla en local determinado. Núm  [415]
23 | 210 | 2 | An | La actividad se desarrolla en local determinado. Piso  [416]
24 | 212 | 2 | An | La actividad se desarrolla en local determinado. Prta  [417]
25 | 214 | 5 | Num | La actividad se desarrolla en local determinado. Código Postal  [418]
26 | 219 | 25 | An | La actividad se desarrolla en local determinado. Municipio  [419]
27 | 244 | 2 | An | La actividad se desarrolla en local determinado. Código de Provincia  [420] |  | ('01', '02',...'52')
28 | 246 | 6 | Num | La actividad se desarrolla en local determinado. Código de Municipio. Reservado
29 | 252 | 7 | Num | La actividad se desarrolla en local determinado. Superficie (m2)  [422]
30 | 259 | 3 | Num | La actividad se desarrolla en local determinado. Grado de afec. [423]
31 | 262 | 1 | An | La actividad se desarrolla en local determinado. Alta  [424] |  | "S" o blanco
32 | 263 | 2 | Num | La actividad se desarrolla en local determinado. Fecha. Dia.  [425]
33 | 265 | 2 | Num | La actividad se desarrolla en local determinado. Fecha. Mes.  [425]
34 | 267 | 4 | Num | La actividad se desarrolla en local determinado. Fecha. Año.  [425]
35 | 271 | 1 | An | La actividad se desarrolla en local determinado. Baja  [427] |  | "S" o blanco
36 | 272 | 2 | Num | La actividad se desarrolla en local determinado. Fecha. Dia.  [428]
37 | 274 | 2 | Num | La actividad se desarrolla en local determinado. Fecha. Mes.  [428]
38 | 276 | 4 | Num | La actividad se desarrolla en local determinado. Fecha. Año.  [428]
39 | 280 | 13 | An | La actividad se desarrolla en local determinado. Nº referencia alta.  [429]
40 | 293 | 1 | An | La actividad se desarrolla en local determinado. Variación  [430] |  | "S" o blanco
41 | 294 | 2 | Num | La actividad se desarrolla en local determinado. Fecha. Dia.  [431]
42 | 296 | 2 | Num | La actividad se desarrolla en local determinado. Fecha. Mes.  [431]
43 | 298 | 4 | Num | La actividad se desarrolla en local determinado. Fecha. Año.  [431]
44 | 302 | 13 | An | La actividad se desarrolla en local determinado. Nº referencia alta.  [432]
45 | 315 | 20 | An | La actividad se desarrolla en local determinado. Referencia catastral.  [433]
46 | 335 | 17 | An | La actividad se desarrolla en local determinado. S.G.  [434] |  | Tabla
47 | 352 | 25 | An | La actividad se desarrolla en local determinado. Nombre de la vía pública  [435]
48 | 377 | 5 | Num | La actividad se desarrolla en local determinado. Núm  [436]
49 | 382 | 2 | An | La actividad se desarrolla en local determinado. Piso  [437]
50 | 384 | 2 | An | La actividad se desarrolla en local determinado. Prta  [438]
51 | 386 | 5 | Num | La actividad se desarrolla en local determinado. Código Postal  [439]
52 | 391 | 25 | An | La actividad se desarrolla en local determinado. Municipio  [440]
53 | 416 | 2 | An | La actividad se desarrolla en local determinado. Código de Provincia  [441] |  | ('01', '02',...'52')
54 | 418 | 6 | Num | La actividad se desarrolla en local determinado. Código de Municipio. Reservado
55 | 424 | 7 | Num | La actividad se desarrolla en local determinado. Superficie (m2)  [443]
56 | 431 | 3 | Num | La actividad se desarrolla en local determinado. Grado de afec.  [444]
57 | 434 | 1 | An | La actividad se desarrolla en local determinado. Alta  [445] |  | "S" o blanco
58 | 435 | 2 | Num | La actividad se desarrolla en local determinado. Fecha. Dia.  [446]
59 | 437 | 2 | Num | La actividad se desarrolla en local determinado. Fecha. Mes.  [446]
60 | 439 | 4 | Num | La actividad se desarrolla en local determinado. Fecha. Año.  [446]
61 | 443 | 1 | An | La actividad se desarrolla en local determinado. Baja  [448] |  | "S" o blanco
62 | 444 | 2 | Num | La actividad se desarrolla en local determinado. Fecha. Dia.  [449]
63 | 446 | 2 | Num | La actividad se desarrolla en local determinado. Fecha. Mes.  [449]
64 | 448 | 4 | Num | La actividad se desarrolla en local determinado. Fecha. Año.  [449]
65 | 452 | 13 | An | La actividad se desarrolla en local determinado. Nº referencia alta.  [450]
66 | 465 | 1 | An | La actividad se desarrolla en local determinado. Variación  [451] |  | "S" o blanco
67 | 466 | 2 | Num | La actividad se desarrolla en local determinado. Fecha. Dia.  [452]
68 | 468 | 2 | Num | La actividad se desarrolla en local determinado. Fecha. Mes.  [452]
69 | 470 | 4 | Num | La actividad se desarrolla en local determinado. Fecha. Año.  [452]
70 | 474 | 13 | An | La actividad se desarrolla en local determinado. Nº referencia alta.  [453]
71 | 487 | 20 | An | Locales indirectamente afectos a la actividad. Referencia catastral.  [454]
72 | 507 | 17 | An | Locales indirectamente afectos a la actividad. S.G.  [455] |  | Tabla
73 | 524 | 25 | An | Locales indirectamente afectos a la actividad. Nombre de la vía pública  [456]
74 | 549 | 5 | Num | Locales indirectamente afectos a la actividad. Núm  [457]
75 | 554 | 2 | An | Locales indirectamente afectos a la actividad. Piso  [458]
76 | 556 | 2 | An | Locales indirectamente afectos a la actividad. Prta  [459]
77 | 558 | 5 | Num | Locales indirectamente afectos a la actividad. Código Postal  [460]
78 | 563 | 25 | An | Locales indirectamente afectos a la actividad. Municipio  [461]
79 | 588 | 2 | An | Locales indirectamente afectos a la actividad. Código de Provincia  [462] |  | ('01', '02',...'52')
80 | 590 | 6 | Num | Locales indirectamente afectos a la actividad. Código de Municipio. Reservado.
81 | 596 | 7 | Num | Locales indirectamente afectos a la actividad. Superficie (m2)  [464]
82 | 603 | 3 | Num | Locales indirectamente afectos a la actividad. Grado de afec.  [465]
83 | 606 | 2 | An | Locales indirectamente afectos a la actividad. Uso o destino.  [466] |  | Tabla
84 | 608 | 1 | An | Locales indirectamente afectos a la actividad. Alta  [468] |  | "S" o blanco
85 | 609 | 2 | Num | Locales indirectamente afectos a la actividad. Fecha. Dia.  [469]
86 | 611 | 2 | Num | Locales indirectamente afectos a la actividad. Fecha. Mes.  [469]
87 | 613 | 4 | Num | Locales indirectamente afectos a la actividad. Fecha. Año.  [469]
88 | 617 | 1 | An | Locales indirectamente afectos a la actividad. Baja  [471] |  | "S" o blanco
89 | 618 | 2 | Num | Locales indirectamente afectos a la actividad. Fecha. Dia.  [472]
90 | 620 | 2 | Num | Locales indirectamente afectos a la actividad. Fecha. Mes.  [472]
91 | 622 | 4 | Num | Locales indirectamente afectos a la actividad. Fecha. Año.  [472]
92 | 626 | 13 | An | Locales indirectamente afectos a la actividad. Nº referencia alta.  [473]
93 | 639 | 1 | An | Locales indirectamente afectos a la actividad. Variación  [474] |  | "S" o blanco
94 | 640 | 2 | Num | Locales indirectamente afectos a la actividad. Fecha. Dia.  [475]
95 | 642 | 2 | Num | Locales indirectamente afectos a la actividad. Fecha. Mes.  [475]
96 | 644 | 4 | Num | Locales indirectamente afectos a la actividad. Fecha. Año.  [475]
97 | 648 | 13 | An | Locales indirectamente afectos a la actividad. Nº referencia alta.  [476]
98 | 661 | 20 | An | Locales indirectamente afectos a la actividad. Referencia catastral.  [477]
99 | 681 | 17 | An | Locales indirectamente afectos a la actividad. S.G.  [478] |  | Tabla
100 | 698 | 25 | An | Locales indirectamente afectos a la actividad. Nombre de la vía pública  [479]
101 | 723 | 5 | Num | Locales indirectamente afectos a la actividad. Núm  [480]
102 | 728 | 2 | An | Locales indirectamente afectos a la actividad. Piso  [481]
103 | 730 | 2 | An | Locales indirectamente afectos a la actividad. Prta  [482]
104 | 732 | 5 | Num | Locales indirectamente afectos a la actividad. Código Postal  [483]
105 | 737 | 25 | An | Locales indirectamente afectos a la actividad. Municipio  [484]
106 | 762 | 2 | An | Locales indirectamente afectos a la actividad. Código de Provincia  [485] |  | ('01', '02',...'52')
107 | 764 | 6 | Num | Locales indirectamente afectos a la actividad. Código de Municipio. Reservado
108 | 770 | 7 | Num | Locales indirectamente afectos a la actividad. Superficie (m2)  [487]
109 | 777 | 3 | Num | Locales indirectamente afectos a la actividad. Grado de afec.  [488]
110 | 780 | 2 | An | Locales indirectamente afectos a la actividad. Uso o destino.  [489] |  | Tabla
111 | 782 | 1 | An | Locales indirectamente afectos a la actividad. Alta  [491] |  | "S" o blanco
112 | 783 | 2 | Num | Locales indirectamente afectos a la actividad. Fecha. Dia.  [492]
113 | 785 | 2 | Num | Locales indirectamente afectos a la actividad. Fecha. Mes.  [492]
114 | 787 | 4 | Num | Locales indirectamente afectos a la actividad. Fecha. Año.  [492]
115 | 791 | 1 | An | Locales indirectamente afectos a la actividad. Baja  [494] |  | "S" o blanco
116 | 792 | 2 | Num | Locales indirectamente afectos a la actividad. Fecha. Dia.  [495]
117 | 794 | 2 | Num | Locales indirectamente afectos a la actividad. Fecha. Mes.  [495]
118 | 796 | 4 | Num | Locales indirectamente afectos a la actividad. Fecha. Año.  [495]
119 | 800 | 13 | An | Locales indirectamente afectos a la actividad. Nº referencia alta.  [496]
120 | 813 | 1 | An | Locales indirectamente afectos a la actividad. Variación  [497] |  | "S" o blanco
121 | 814 | 2 | Num | Locales indirectamente afectos a la actividad. Fecha. Dia.  [498]
122 | 816 | 2 | Num | Locales indirectamente afectos a la actividad. Fecha. Mes.  [498]
123 | 818 | 4 | Num | Locales indirectamente afectos a la actividad. Fecha. Año.  [498]
124 | 822 | 13 | An | Locales indirectamente afectos a la actividad. Nº referencia alta.  [499]
125 | 835 | 1 | An | Locales directamente afectos a la actividad.Indicador referencia catastral  [412bis]
126 | 836 | 1 | An | Locales directamente afectos a la actividad.Indicador referencia catastral  [433bis]
127 | 837 | 1 | An | Locales indirectamente afectos a la actividad.Indicador referencia catastral  [454bis]
128 | 838 | 1 | An | Locales indirectamente afectos a la actividad.Indicador referencia catastral  [4774bis]
129 | 839 | 52 | An | Reservado para la Agencia tributaria
130 | 891 | 10 | An | Identificador de fin de registro. | obligatorio | </T036040>
131 | 901 |  | An | Salto de línea. Constante CRLF. | obligatorio
TOTAL |  | 900 | Posiciones
 |  |  |  | pasa de 844 a  900 posiciones

# Pag. 5

 | Agencia Tributaria
Modelo 036 |  | Diseño de registro. Castellano
 |  | Declaración Censal/Declaración Censal Simplifica de alta, modificación y baja en el Censo de Empresarios, Profesionales y Retenedores
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 9 | An | Inicio del identificador de modelo y página. | obligatorio | <T036050>
2 | 10 | 1 | A | Tipo declaración | obligatorio | blanco
3 | 11 | 1 | An | Suj. Pasivo Gran Empresa y Admones. Publicas. ¿Tiene la condición de Gran Empresa? Si/No  [541] |  | S, N o blanco
4 | 12 | 2 | Num | Suj. Pasivo Gran Empresa y Admones. Publicas. ¿Tiene la condición de G.E.?. Fecha. Dia  [545]
5 | 14 | 2 | Num | Suj. Pasivo Gran Empresa y Admones. Publicas. ¿Tiene la condición de G.E.?. Fecha. Mes  [545]
6 | 16 | 4 | Num | Suj. Pasivo Gran Empresa y Admones. Publicas. ¿Tiene la condición de G.E.?. Fecha. Año  [545]
7 | 20 | 1 | An | Suj. Pasivo G.E. y Admones. Publicas. ¿Es A.Publ. cuyo último presup. anual aprobado supera. 6 mill. €?  [577] |  | S, N o blanco
8 | 21 | 2 | Num | Suj. Pasivo G.E. y A.P. ¿Es Admon. Publ. cuyo último presup. anual aprob sup. 6 mill.€?. Fecha. Día  [578]
9 | 23 | 2 | Num | Suj. Pasivo G.E. y A.P. ¿Es Admon. Publ. cuyo último presup. anual aprob sup. 6 mill.€?. Fecha. Mes  [578]
10 | 25 | 4 | Num | Suj. Pasivo G.E. y A.P. ¿Es Admon. Publ. cuyo último presup. anual aprob sup. 6 mill.€?. Fecha. Año  [578]
11 | 29 | 1 | An | I.V.A. Informac. obligaciones. ¿Está establ. en el territorio de aplic. del IVA o tiene en él un est. permte?  [500] |  | S, N o blanco
12 | 30 | 1 | An | I.V.A. Informac. oblig. ¿Realiza excl. oper. no suj. o exentas q no obligan a presentar autoliq. periodica? [501] |  | S, N o blanco
13 | 31 | 1 | An | I.V.A. B) Comunicac. Inicio de activ. Entregas de bienes o prest. de serv. previa o simultanea...  [502] |  | "S" o blanco
14 | 32 | 2 | Num | I.V.A. B) Comunicac. Inicio de activ. Entregas de bienes o prest. de serv. previa o simult... Fecha. Día [503]
15 | 34 | 2 | Num | I.V.A. B) Comunicac. Inicio de activ. Entregas de bienes o prest. de serv. previa o simult... Fecha. Mes  [503]
16 | 36 | 4 | Num | I.V.A. B) Comunicac. Inicio de activ. Entregas de bienes o prest. de serv. previa o simult... Fecha. Año  [503]
17 | 40 | 1 | An | I.V.A. B) Comunicac. Inicio de activ. Entregas de bienes o prest. de serv. posterior a adq...  [504] |  | "S" o blanco
18 | 41 | 2 | Num | I.V.A. B) Comunicac. Inicio de activ. Entregas de bienes o prest. de serv. posterior a adq... Fecha. Día  [505]
19 | 43 | 2 | Num | I.V.A. B) Comunicac. Inicio de activ. Entregas de bienes o prest. de serv. posterior a adq... Fecha. Mes  [505]
20 | 45 | 4 | Num | I.V.A. B) Comunicac. Inicio de activ. Entregas de bienes o prest. de serv. posterior a adq... Fecha. Año  [505]
21 | 49 | 1 | An | I.V.A. B) Comunic. Inicio de nueva activ. q constituya sector diferenciado...  [506] |  | "S" o blanco
22 | 50 | 2 | Num | I.V.A. B) Comunic. Inicio de nueva activ. q constituya sector diferenciado... Fecha. Día  [507]
23 | 52 | 2 | Num | I.V.A. B) Comunic. Inicio de nueva activ. q constituya sector diferenciado... Fecha. Mes  [507]
24 | 54 | 4 | Num | I.V.A. B) Comunic. Inicio de nueva activ. q constituya sector diferenciado... Fecha. Año  [507]
25 | 58 | 1 | An | I.V.A. B) Comuinic. de comienzo habitual de entregas de bienes o prest. de serv...  [508] |  | "S" o blanco
26 | 59 | 2 | Num | I.V.A. B) Comuinic. de comienzo habitual de entregas de bienes o prest. de serv...Fecha. Día  [509]
27 | 61 | 2 | Num | I.V.A. B) Comuinic. de comienzo habitual de entregas de bienes o prest. de serv...Fecha. Mes  [509]
28 | 63 | 4 | Num | I.V.A. B) Comuinic. de comienzo habitual de entregas de bienes o prest. de serv...Fecha. Año  [509]
29 | 67 | 1 | An | I.V.A. C) General  [510] |  | A, B o blanco
30 | 68 | 6 | An | I.V.A. C) General. Grupo o epígr./sec. I.A.E. o cód. act.  [511]
31 | 74 | 2 | Num | I.V.A. C) General. Día  [512]
32 | 76 | 2 | Num | I.V.A. C) General. Mes  [512]
33 | 78 | 4 | Num | I.V.A. C) General. Año  [512]
34 | 82 | 1 | An | I.V.A. C) Reg. Esp. Recargo de equivalencia.  [514] |  | A, B o blanco
35 | 83 | 6 | An | I.V.A. C) Reg. Esp. Recargo de equivalencia. G. o epígr./sec. I.A.E. o cód. act.  [515]
36 | 89 | 2 | Num | I.V.A. C) Reg. Esp. Recargo de equivalencia. Fecha. Día.  [516]
37 | 91 | 2 | Num | I.V.A. C) Reg. Esp. Recargo de equivalencia. Fecha. Mes.  [516]
38 | 93 | 4 | Num | I.V.A. C) Reg. Esp. Recargo de equivalencia. Fecha. Año.  [516]
39 | 97 | 1 | An | I.V.A. C) Reg. Esp. Bienes usados operación por operación   [518] |  | A, B o blanco
40 | 98 | 6 | An | I.V.A. C) Reg. Esp. Bienes usados operación por operación. G. o epígr./sec. I.A.E. o cód. act.  [519]
41 | 104 | 2 | Num | I.V.A. C) Reg. Esp. Bienes usados operación por operación. Fecha. Día  [520]
42 | 106 | 2 | Num | I.V.A. C) Reg. Esp. Bienes usados operación por operación. Fecha. Mes  [520]
43 | 108 | 4 | Num | I.V.A. C) Reg. Esp. Bienes usados operación por operación. Fecha. Año  [520]
44 | 112 | 1 | An | I.V.A. C) Reg. Esp. Bienes usados margen de beneficio global.  [522] |  | A, B o blanco
45 | 113 | 6 | An | I.V.A. C) Reg. Esp. Bienes usados margen de beneficio global. G. o epígr./sec. I.A.E. o cód. act.  [523]
46 | 119 | 2 | Num | I.V.A. C) Reg. Esp. Bienes usados margen de beneficio global. Fecha. Día  [524]
47 | 121 | 2 | Num | I.V.A. C) Reg. Esp. Bienes usados margen de beneficio global. Fecha. Mes  [524]
48 | 123 | 4 | Num | I.V.A. C) Reg. Esp. Bienes usados margen de beneficio global. Fecha. Año  [524]
49 | 127 | 1 | An | I.V.A.C) Reg. Esp. Agencias de viajes, determinación operación por operación  [526] |  | A, B o blanco
50 | 128 | 6 | An | I.V.A.C) Reg. Esp. Agencias de viajes, determ. operación por operac. G. o epígr./sec. I.A.E. o cód. act.  [527]
51 | 134 | 2 | Num | I.V.A.C) Reg. Esp. Agencias de viajes, determinación operación por operación. Fecha. Día  [528]
52 | 136 | 2 | Num | I.V.A.C) Reg. Esp. Agencias de viajes, determinación operación por operación. Fecha. Mes  [528]
53 | 138 | 4 | Num | I.V.A.C) Reg. Esp. Agencias de viajes, determinación operación por operación. Fecha. Año  [528]
54 | 142 | 15 | An | Reservado para la Agencia Tributaria
55 | 157 | 1 | An | I.V.A. C) Reg. Esp. Agricultura, ganadería y pesca.  [534,538,542,546,570] |  | 1 - incluido/2- excluido/3- renuncia/4-revocacion/5-baja/ blanco - no consta
56 | 158 | 6 | An | I.V.A. C) Reg. Esp. Agricultura, ganadería y pesca. epigrafe./sec. I.A.E. o cód. activ.  [535,539,543,547,571]
57 | 164 | 2 | Num | I.V.A. C) Reg. Esp. Agricultura, ganadería y pesca.  Fecha. Día  [536,540,544,548,572]
58 | 166 | 2 | Num | I.V.A. C) Reg. Esp. Agricultura, ganadería y pesca.  Fecha. Mes  [536,540,544,548,572]
59 | 168 | 4 | Num | I.V.A. C) Reg. Esp. Agricultura, ganadería y pesca.  Fecha. Año  [536,540,544,548,572]
60 | 172 | 1 | An | I.V.A. C) Reg. Esp. Simplificado.  [550,554,558,562,566] |  | 1 - incluido/2- excluido/3- renuncia/4-revocacion/5-baja/ blanco - no consta
61 | 173 | 6 | An | I.V.A. C) Reg. Esp. Simplificado. Incluido. G. o epígr./sec. I.A.E. o cód. activ.  [551,555,559,563,567]
62 | 179 | 2 | Num | I.V.A. C) Reg. Esp. Simplificado. Fecha. Día  [552,556,560,564,568]
63 | 181 | 2 | Num | I.V.A. C) Reg. Esp. Simplificado. Fecha. Mes  [552,556,560,564,568]
64 | 183 | 4 | Num | I.V.A. C) Reg. Esp. Simplificado. Fecha. Año  [552,556,560,564,568]
65 | 187 | 1 | An | I.V.A. C) Reg. Esp. Oro de inversión.  [574] |  | A, B o blanco
66 | 188 | 6 | An | I.V.A. C) Reg. Esp. Oro de inversión. G. o epígr./sec. I.A.E. o cód. activ  [575]
67 | 194 | 2 | Num | I.V.A. C) Reg. Esp. Oro de inversión. Fecha. Día  [576]
68 | 196 | 2 | Num | I.V.A. C) Reg. Esp. Oro de inversión. Fecha. Mes  [576]
69 | 198 | 4 | Num | I.V.A. C) Reg. Esp. Oro de inversión. Fecha. Año  [576]
70 | 202 | 1 | An | I.V.A. D) Solicita alta/baja en el Reg. de devolucion mensual   [579, 580] |  | A, B o blanco
71 | 203 | 1 | An | I.V.A. D) Solicita alta/baja en el Reg. de operadores intracomunitarios  [582,583] |  | A, B o blanco
72 | 204 | 2 | Num | I.V.A. D) Solicita alta/baja en el Reg. de operadores intracomunitarios. Fecha. Día  [584]
73 | 206 | 2 | Num | I.V.A. D) Solicita alta/baja en el Reg. de operadores intracomunitarios. Fecha. Mes  [584]
74 | 208 | 4 | Num | I.V.A. D) Solicita alta/baja en el Reg. de operadores intracomunitarios. Fecha. Año  [584]
75 | 212 | 5 | Num | I.V.A. E) Propone porcentaje provisional de deducción (3 enteros y 2 decimales)  [586]
76 | 217 | 1 | An | I.V.A. E) No tiene sectores diferenciados  [587] |  | S, N o blanco
77 | 218 | 3 | Num | I.V.A. E) Sector I. Código C.N.A.E.  [588]
78 | 221 | 3 | Num | I.V.A. E) Sector I. Código C.N.A.E.  [589]
79 | 224 | 3 | Num | I.V.A. E) Sector I. Código C.N.A.E.  [590]
80 | 227 | 1 | An | I.V.A. E) Sector I. Código C.N.A.E. Opción prorrata especial  [591] |  | S, N o blanco
81 | 228 | 3 | Num | I.V.A. E) Sector II. Código C.N.A.E.  [592]
82 | 231 | 3 | Num | I.V.A. E) Sector II. Código C.N.A.E.  [593]
83 | 234 | 3 | Num | I.V.A. E) Sector II. Código C.N.A.E.  [594]
84 | 237 | 1 | An | I.V.A. E) Sector II. Código C.N.A.E. Opción prorrata especial  [595] |  | S, N o blanco
85 | 238 | 3 | Num | I.V.A. E) Sector III. Código C.N.A.E.  [596]
86 | 241 | 3 | Num | I.V.A. E) Sector III. Código C.N.A.E.  [597]
87 | 244 | 3 | Num | I.V.A. E) Sector III. Código C.N.A.E.  [598]
88 | 247 | 1 | An | I.V.A. E) Sector III. Código C.N.A.E. Opción prorrata especial  [599] |  | S, N o blanco
89 | 248 | 1 | An | I.V.A. C) Régimen especial del criterio de Caja.  [517,529,549,573,561] |  | 1 - incluido/2- excluido/3- renuncia/4-revocacion/5-baja/ blanco - no consta
90 | 249 | 6 | An | I.V.A. C) Régimen especial del criterio de Caja. G. o epígr./sec. I.A.E. o cód. activ.  [521,533,553,581,565]
91 | 255 | 2 | Num | I.V.A. C) Régimen especial del criterio de Caja. Fecha. Día  [525,537,557,585,569]
92 | 257 | 2 | Num | I.V.A. C) Régimen especial del criterio de Caja. Fecha. Mes  [525,537,557,585,569]
93 | 259 | 4 | Num | I.V.A. C) Régimen especial del criterio de Caja. Fecha. Año  [525,537,557,585,569]
94 | 263 | 1 | An | I.V.A. Informac. Obligaciones A). ¿Tiene la condición de revendedor de telefónos móviles
consolas de videojuegos, ordenadores portátiles y tabletas digitales
de acuerdo co el art. 84 Uno 2º)LIVA?  [513] |  | S, N o blanco
95 | 264 | 1 | An | I.V.A. F) Ingreso IVA Importación. Opción/Renuncia/Revocación/Baja [530,531] |  | 1 - opción / 3-renuncia / blanco - no consta
96 | 265 | 2 | Num | I.V.A. F) Ingreso IVA Importación. Fecha. Día [736]
97 | 267 | 2 | Num | I.V.A. F) Ingreso IVA Importación. Fecha. Mes [736]
98 | 269 | 4 | Num | I.V.A. F) Ingreso IVA Importación. Fecha. Año [736]
99 | 273 | 1 | An | I.V.A.F) llevanza Libros de Registro del Iva a traves de la sede electronica de la AEAT .(532,737) |  | 1 - opción / 3-renuncia / blanco - no consta
100 | 274 | 2 | Num | I.V.A.F) llevanza Libros de Registro del Iva a traves de la sede electronica de la AEAT . Fecha. Día [738]
101 | 276 | 2 | Num | I.V.A. F) llevanza Libros de Registro del Iva a traves de la sede electronica de la AEAT . Fecha. Mes [738]
102 | 278 | 4 | Num | I.V.A. F) llevanza Libros de Registro del Iva a traves de la sede electronica de la AEAT . Fecha. Año [738]
103 | 282 | 1 | An | I.V.A.A) comunicación cumplimiento de obligacion expedir factura se realiza por los destinatarios o por terceros  [740] |  | S, N o blanco
104 | 283 | 2 | Num | I.V.A. A) comunicación cumplimiento de obligacion expedir factura se realiza por los destinatarios o por terceros. Fecha. Día [739]
105 | 285 | 2 | Num | I.V.A. A) comunicación cumplimiento de obligacion expedir factura se realiza por los destinatarios o por terceros. Fecha. Mes [739]
106 | 287 | 4 | Num | I.V.A. A) comunicación cumplimiento de obligacion expedir factura se realiza por los destinatarios o por terceros Fecha. Año [739]
107 | 291 | 1 | An | I.V.A. G) Forales IVA Importación. Opción/Renuncia [741,742] |  | 1 - opción / 3-renuncia / blanco - no consta
108 | 292 | 2 | Num | I.V.A. G) Forales IVA Importación. Fecha. Día [743]
109 | 294 | 2 | Num | I.V.A. G) Forales IVA Importación. Fecha. Mes [743]
110 | 296 | 4 | Num | I.V.A.G)Forales IVA Importación. Fecha. Año [743]
111 | 300 | 2 | Num | Alta / baja revendedores telefonos moviles, consolas. Fecha. Día [744]
112 | 302 | 2 | Num | Alta / baja revendedores telefonos moviles, consolas. Fecha. Mes [744]
113 | 304 | 4 | Num | Alta / baja revendedores telefonos moviles, consolas. Fecha. Año [744]
114 | 308 | 63 | An | Reservado para la Agencia Tributaria
115 | 371 | 10 | An | Identificador de fin de registro. | obligatorio | </T036050>
116 | 381 |  | An | Salto de línea. Constante CRLF. | obligatorio
TOTAL |  | 380 | Posiciones

# Pag. 6

 | Agencia Tributaria
Modelo 036 |  | Diseño de registro. Castellano
 |  | Declaración Censal/Declaración Censal Simplifica de alta, modificación y baja en el Censo de Empresarios, Profesionales y Retenedores
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 9 | An | Inicio del identificador de modelo y página. | obligatorio | <T036060>
2 | 10 | 1 | A | Tipo declaración | obligatorio | blanco
3 | 11 | 1 | An | 7.A) IRPF. Obligación de realizar pagos frac. derivados del desarrollo de activ. ec. propias  [600] |  | A, B o blanco
4 | 12 | 2 | Num | 7.A) IRPF. Obligación de realizar pagos frac. derivados del desarrollo de activ. ec. propias. Fecha. Día  [602]
5 | 14 | 2 | Num | 7.A) IRPF. Obligación de realizar pagos frac. derivados del desarrollo de activ. ec. propias. Fecha. Mes [602]
6 | 16 | 4 | Num | 7.A) IRPF. Obligación de realizar pagos frac. derivados del desarrollo de activ. ec. propias. Fecha. Año [602]
7 | 20 | 1 | An | 7.A) IRPF. Oblig. de realizar pagos frac. derivados de cond. de miembro de ent. en atrib. de rentas  [601] |  | A, B o blanco
8 | 21 | 2 | Num | 7.A) IRPF. Oblig. de realizar pagos fr. deriv. de cond. de miemb. de ent. en atrib. de rentas. Fecha. Dia [603]
9 | 23 | 2 | Num | 7.A) IRPF. Oblig. de realizar pagos fr. deriv. de cond. de miemb. de ent. en atrib. de rentas. Fecha. Mes [603]
10 | 25 | 4 | Num | 7.A) IRPF. Oblig. de realizar pagos fr. deriv. de cond. de miemb. de ent. en atrib. de rentas. Fecha. Año [603]
11 | 29 | 1 | An | 7.A) IRPF. Estimación objetiva.  [604,605,606,607,615] |  | 1- inclusión/2- exlcusión/3-renuncia/4-revocación/5-baja/ blanco-no consta
12 | 30 | 2 | Num | 7.A) IRPF. Estimación objetiva. Fecha. Día  [616]
13 | 32 | 2 | Num | 7.A) IRPF. Estimación objetiva. Fecha. Mes  [616]
14 | 34 | 4 | Num | 7.A) IRPF. Estimación objetiva. Fecha. Año  [616]
15 | 38 | 1 | An | 7.A) IRPF. Estimación directa normal.  [608,617] |  | 1- inclusión /5-baja/ blanco -no consta
16 | 39 | 2 | Num | 7.A) IRPF. Estimación directa normal. Fecha. Día  [618]
17 | 41 | 2 | Num | 7.A) IRPF. Estimación directa normal. Fecha. Mes  [618]
18 | 43 | 4 | Num | 7.A) IRPF. Estimación directa normal. Fecha. Año  [618]
19 | 47 | 1 | An | 7.A) IRPF. Estimación directa simplificada.  [609,610,611,612,619] |  | 1- inclusión/2- exlcusión/3-renuncia/4-revocación/5-baja/ blanco-no consta
20 | 48 | 2 | Num | 7.A) IRPF. Estimación directa simplificada. Fecha. Día  [650]
21 | 50 | 2 | Num | 7.A) IRPF. Estimación directa simplificada. Fecha. Mes  [650]
22 | 52 | 4 | Num | 7.A) IRPF. Estimación directa simplificada. Fecha. Año  [650]
23 | 56 | 1 | An | 7.A) IRPF. (1) Si determinaba el rendimiento neto por el método de E.O... 1. Sección I.A.E.  [613]
24 | 57 | 4 | An | 7.A) IRPF. (1) Si determinaba el rendimiento neto por el método de E.O... 1. Grupo o epígrafe  [613]
25 | 61 | 3 | An | 7.A) IRPF. (1) Si determinaba el rendimiento neto por el método de E.O... 1. Tipo de actividad  [613]
26 | 64 | 1 | An | 7.A) IRPF. (1) Si determinaba el rendimiento neto por el método de E.O... 2. Sección I.A.E.  [613]
27 | 65 | 4 | An | 7.A) IRPF. (1) Si determinaba el rendimiento neto por el método de E.O... 2. Grupo o epígrafe  [613]
28 | 69 | 3 | An | 7.A) IRPF. (1) Si determinaba el rendimiento neto por el método de E.O... 2. Tipo de actividad  [613]
29 | 72 | 1 | An | 7.A) IRPF. (1) Si determinaba el rendimiento neto por el método de E.O... 3. Sección I.A.E.  [613]
30 | 73 | 4 | An | 7.A) IRPF. (1) Si determinaba el rendimiento neto por el método de E.O... 3. Grupo o epígrafe  [613]
31 | 77 | 3 | An | 7.A) IRPF. (1) Si determinaba el rendimiento neto por el método de E.O... 3. Tipo de actividad  [613]
32 | 80 | 1 | An | 7.A) IRPF. (1) Si determinaba el rendimiento neto por el método de E.O... 4. Sección I.A.E.  [613]
33 | 81 | 4 | An | 7.A) IRPF. (1) Si determinaba el rendimiento neto por el método de E.O... 4. Grupo o epígrafe  [613]
34 | 85 | 3 | An | 7.A) IRPF. (1) Si determinaba el rendimiento neto por el método de E.O... 4. Tipo de actividad  [613]
35 | 88 | 1 | An | 7.A) IRPF. (2) Si determinaba el rendimiento neto por la modalidad simplificada... 1. Sección I.A.E.  [614]
36 | 89 | 4 | An | 7.A) IRPF. (2) Si determinaba el rendimiento neto por la modalidad simplificada... 1. Grupo o epígrafe  [614]
37 | 93 | 3 | An | 7.A) IRPF. (2) Si determinaba el rendimiento neto por la modalidad simplificada... 1. Tipo de actividad  [614]
38 | 96 | 1 | An | 7.A) IRPF. (2) Si determinaba el rendimiento neto por la modalidad simplificada... 2. Sección I.A.E.  [614]
39 | 97 | 4 | An | 7.A) IRPF. (2) Si determinaba el rendimiento neto por la modalidad simplificada... 2. Grupo o epígrafe  [614]
40 | 101 | 3 | An | 7.A) IRPF. (2) Si determinaba el rendimiento neto por la modalidad simplificada... 2. Tipo de actividad  [614]
41 | 104 | 1 | An | 7.A) IRPF. (2) Si determinaba el rendimiento neto por la modalidad simplificada... 3. Sección I.A.E.  [614]
42 | 105 | 4 | An | 7.A) IRPF. (2) Si determinaba el rendimiento neto por la modalidad simplificada... 3. Grupo o epígrafe  [614]
43 | 109 | 3 | An | 7.A) IRPF. (2) Si determinaba el rendimiento neto por la modalidad simplificada... 3. Tipo de actividad  [614]
44 | 112 | 1 | An | 7.A) IRPF. (2) Si determinaba el rendimiento neto por la modalidad simplificada... 4. Sección I.A.E.  [614]
45 | 113 | 4 | An | 7.A) IRPF. (2) Si determinaba el rendimiento neto por la modalidad simplificada... 4. Grupo o epígrafe  [614]
46 | 117 | 3 | An | 7.A) IRPF. (2) Si determinaba el rendimiento neto por la modalidad simplificada... 4. Tipo de actividad  [614]
47 | 120 | 1 | An | 7.B) I.S. Obligación de presentar declaración por el Impuesto sobre Sociedades  [620] |  | A,B o blanco
48 | 121 | 2 | Num | 7.B) I.S. Obligación de presentar declaración por el Impuesto sobre Sociedades. Fecha. Día  [641]
49 | 123 | 2 | Num | 7.B) I.S. Obligación de presentar declaración por el Impuesto sobre Sociedades. Fecha. Mes  [641]
50 | 125 | 4 | Num | 7.B) I.S. Obligación de presentar declaración por el Impuesto sobre Sociedades. Fecha. Año  [641]
51 | 129 | 2 | Num | 7.B) I.S. Fecha de cierre del ejercicio económico. Día  [640]
52 | 131 | 2 | Num | 7.B) I.S. Fecha de cierre del ejercicio económico. Mes  [640]
53 | 133 | 1 | An | 7.B) I.S. Opción por el sistema de cálculo del art. 40.3 Ley I.S. para la realización de los pagos fracc...  [621] |  | A,B o blanco
54 | 134 | 2 | Num | 7.B) I.S. Opción por el sistema de cálculo del art. 40.3 Ley I.S... Fecha. Día  [642]
55 | 136 | 2 | Num | 7.B) I.S. Opción por el sistema de cálculo del art. 40.3 Ley I.S... Fecha. Mes  [642]
56 | 138 | 4 | Num | 7.B) I.S. Opción por el sistema de cálculo del art. 40.3 Ley I.S... Fecha. Año  [642]
57 | 142 | 1 | An | 7.B) I.S. Condición de entidad exenta en el Impuesto sobre Sociedades  [622] |  | A,B o blanco
58 | 143 | 1 | An | 7.B) I.S. Exención  [623,624,625,627] |  | 1- total / 3- parcial art.9.2/ 2- parcial art 9.3 le I.s / blanco-no consta /4 - parcial art.9.4
59 | 144 | 2 | Num | 7.B) I.S. Exención  Fecha. Día  [643,644,645,647]
60 | 146 | 2 | Num | 7.B) I.S. Exención. Fecha. Mes  [643,644,645,647]
61 | 148 | 4 | Num | 7.B) I.S. Exención. Fecha. Año  [643,644,645,647]
62 | 152 | 1 | An | 7.B) I.S. Ejercitada la opción por el régimen de consolidación fiscal, renuncia a su aplicación  [626] |  | "S", "N" o blanco
63 | 153 | 2 | Num | 7.B) I.S. Ejercitada la opción por el régimen de consolidación fiscal, renuncia a su aplicación. Fecha. Día  [646]
64 | 155 | 2 | Num | 7.B) I.S. Ejercitada la opción por el régimen de consolidación fiscal, renuncia a su aplicación. Fecha. Mes [646]
65 | 157 | 4 | Num | 7.B) I.S. Ejercitada la opción por el régimen de consolidación fiscal, renuncia a su aplicación. Fecha. Año [646]
66 | 161 | 1 | An | 7.C) IRNR. Modalidad de establecimiento permanente.  [630,631,632] |  | 1-reg.general/ 2-art18.3/ 3-art 18.4/ blanco-no consta
67 | 162 | 1 | An | 7.C) IRNR. Modalidad de establ. perm. Opción por el rég. general en los términos...  [633] |  | A, B o blanco
68 | 163 | 2 | Num | 7.C) IRNR. Modalidad de establ. perm.  Fecha. Día  [636]
69 | 165 | 2 | Num | 7.C) IRNR. Modalidad de establ. perm.  Fecha. Mes  [636]
70 | 167 | 4 | Num | 7.C) IRNR. Modalidad de establ. perm.  Fecha. Año  [636]
71 | 171 | 1 | An | 7.C) IRNR. Modalidad de establ. perm. Obligación de presentar declaración por el I.R.N.R...  [634] |  | A, B o blanco
72 | 172 | 2 | Num | 7.C) IRNR. Modalidad de establ. perm. Obligación de presentar declaración por el I.R.N.R... Fecha. Día  [637]
73 | 174 | 2 | Num | 7.C) IRNR. Modalidad de establ. perm. Obligación de presentar declaración por el I.R.N.R... Fecha. Mes  [637]
74 | 176 | 4 | Num | 7.C) IRNR. Modalidad de establ. perm. Obligación de presentar declaración por el I.R.N.R... Fecha. Año  [637]
75 | 180 | 1 | An | 7.C) IRNR. Modalidad de establ. perm. Opción por el sist. de cálculo previsto en el art. 40.3...  [635] |  | A, B o blanco
76 | 181 | 2 | Num | 7.C) IRNR. Modalidad de establ. perm. Opción por el sist. de cálculo previsto en el art. 40.3... Fecha. Día  [638]
77 | 183 | 2 | Num | 7.C) IRNR. Modalidad de establ. perm. Opción por el sist. de cálculo previsto en el art. 40.3... Fecha. Mes  [638]
78 | 185 | 4 | Num | 7.C) IRNR. Modalidad de establ. perm. Opción por el sist. de cálculo previsto en el art. 40.3... Fecha. Año  [638]
79 | 189 | 1 | An | 8. Ejerce la opción por el Régimen fiscal especial del Tit. II Ley 49/2002  [651] |  | "S" o blanco
80 | 190 | 2 | Num | 8. Ejerce la opción por el Régimen fiscal especial del Tit. II Ley 49/2002. Fecha. Día  [653]
81 | 192 | 2 | Num | 8. Ejerce la opción por el Régimen fiscal especial del Tit. II Ley 49/2002. Fecha. Mes  [653]
82 | 194 | 4 | Num | 8. Ejerce la opción por el Régimen fiscal especial del Tit. II Ley 49/2002. Fecha. Año  [653]
83 | 198 | 1 | An | 8. Ejercitada la opción por el Régimen fiscal especial del Tit. II Ley 49/2002, renuncia a su aplicación  [652] |  | "S" o blanco
84 | 199 | 2 | Num | 8. Ejercitada la opción por el Rég. fiscal esp. del Tit. II Ley 49/2002, renuncia a su aplicación. Fecha. Día  [654]
85 | 201 | 2 | Num | 8. Ejercitada la opción por el Rég. fiscal esp. del Tit. II Ley 49/2002, renuncia a su aplicación. Fecha. Mes [654]
86 | 203 | 4 | Num | 8. Ejercitada la opción por el Rég. fiscal esp. del Tit. II Ley 49/2002, renuncia a su aplicación. Fecha. Año [654]
87 | 207 | 184 | An | Reservado para la Agencia Tributaria
88 | 391 | 10 | An | Identificador de fin de registro. | obligatorio | </T036060>
89 | 401 |  | An | Salto de línea. Constante CRLF. | obligatorio
TOTAL |  | 400 | Posiciones

# Pag. 7

 | Agencia Tributaria
Modelo 036 |  | Diseño de registro. Castellano
 |  | Declaración Censal/Declaración Censal Simplifica de alta, modificación y baja en el Censo de Empresarios, Profesionales y Retenedores
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 9 | An | Inicio del identificador de modelo y página. | obligatorio | <T036070>
2 | 10 | 1 | A | Tipo declaración | obligatorio | blanco
3 | 11 | 1 | An | 9. Oblig. de realizar retenc. o ing. cta. sobre rend. de trabajo personal  [700] |  | A, B o blanco
4 | 12 | 2 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rend. de trabajo personal. Fecha. Día  [720]
5 | 14 | 2 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rend. de trabajo personal. Fecha. Mes  [720]
6 | 16 | 4 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rend. de trabajo personal. Fecha. Año  [720]
7 | 20 | 1 | An | 9. Oblig. de realizar retenc. o ing. cta. sobre rend. de activ. profesionales...  [701] |  | A, B o blanco
8 | 21 | 2 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rend. de activ. profesionales... Fecha. Día  [721]
9 | 23 | 2 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rend. de activ. profesionales... Fecha. Mes  [721]
10 | 25 | 4 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rend. de activ. profesionales... Fecha. Año  [721]
11 | 29 | 1 | An | 9. Oblig. de realizar retenc. o ing. cta. sobre rend. Procedentes del arrendamiento o subarrend...  [702] |  | A, B o blanco
12 | 30 | 2 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rend. Procedentes del arrend. o subarrend... Fecha. Día  [722]
13 | 32 | 2 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rend. Procedentes del arrend. o subarrend... Fecha. Mes  [722]
14 | 34 | 4 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rend. Procedentes del arrend. o subarrend... Fecha. Año  [722]
15 | 38 | 1 | An | 9. Oblig. de realizar retenc. o ing. cta. sobre las transmisiones o reembolsos de acc. o participaciones...  [703] |  | A, B o blanco
16 | 39 | 2 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre las transm. o reembolsos de acc. o participac... Fecha. Día [723]
17 | 41 | 2 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre las transm. o reembolsos de acc. o participac... Fecha. Mes [723]
18 | 43 | 4 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre las transm. o reembolsos de acc. o participac... Fecha. Año [723]
19 | 47 | 1 | An | 9. Oblig. de realizar retenc. o ing. cta. sobre rentas o rend. de capital mob. derivados de la transmisión... [704] |  | A, B o blanco
20 | 48 | 2 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rentas o r.c.m. derivados de la transmisión... Fecha. Día  [724]
21 | 50 | 2 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rentas o r.c.m. derivados de la transmisión... Fecha. Mes  [724]
22 | 52 | 4 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rentas o r.c.m. derivados de la transmisión... Fecha. Año  [724]
23 | 56 | 1 | An | 9. Oblig. de realizar retenc. o ing. cta. sobre rentas o rend. de capital mob. obtenidos por la contrapr... [705] |  | A, B o blanco
24 | 57 | 2 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rentas o r.c.m.. obtenidos por la contraprest... Fecha. Día [725]
25 | 59 | 2 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rentas o r.c.m.. obtenidos por la contraprest... Fecha. Mes [725]
26 | 61 | 4 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rentas o r.c.m.. obtenidos por la contraprest... Fecha Año [725]
27 | 65 | 1 | An | 9. Oblig. de realizar retenc. o ing. cta. sobre rentas o rend. de cap. mob. Procedentes de operaciones... [706] |  | A, B o blanco
28 | 66 | 2 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rentas o r.c.m. Procedentes de operaciones... Fecha. Día [726]
29 | 68 | 2 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rentas o r.c.m. Procedentes de operaciones... Fecha. Mes [726]
30 | 70 | 4 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre rentas o r.c.m. Procedentes de operaciones... Fecha. Año [726]
31 | 74 | 1 | An | 9. Oblig. de realizar retenc. o ing. cta. sobre otras rentas o rendimientos de capital mobiliario  [707] |  | A, B o blanco
32 | 75 | 2 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre otras rentas o rendimientos de capital mob. Fecha. Día [727]
33 | 77 | 2 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre otras rentas o rendimientos de capital mob. Fecha. Mes [727]
34 | 79 | 4 | Num | 9. Oblig. de realizar retenc. o ing. cta. sobre otras rentas o rendimientos de capital mob. Fecha. Año [727]
35 | 83 | 1 | An | 10. IIEE. Obligac. de inscribir sus establ. en el reg. territorial de la oficina gestora...  [710] |  | A, B o blanco
36 | 84 | 2 | Num | 10. IIEE. Obligac. de inscribir sus establ. en el reg. territorial de la oficina gestora... Fecha. Día  [730]
37 | 86 | 2 | Num | 10. IIEE. Obligac. de inscribir sus establ. en el reg. territorial de la oficina gestora... Fecha. Mes  [730]
38 | 88 | 4 | Num | 10. IIEE. Obligac. de inscribir sus establ. en el reg. territorial de la oficina gestora... Fecha. Año  [730]
39 | 92 | 1 | An | 10. IIEE. Obligado a presentar autoliquidación por el Impuesto sobre la Electricidad (Modelo 560) [711] |  | A, B o blanco
40 | 93 | 2 | Num | 10. IIEE. Obligado a presentar autoliquidación por el Impuesto sobre la Electricidad (Modelo 560). Fecha. Día [731]
41 | 95 | 2 | Num | 10. IIEE. Obligado a presentar autoliquidación por el Impuesto sobre la Electricidad (Modelo 560). Fecha. Mes [731]
42 | 97 | 4 | Num | 10. IIEE. Obligado a presentar autoliquidación por el Impuesto sobre la Electricidad (Modelo 560). Fecha. Año [731]
43 | 101 | 1 | An | 10. IIEE. Obligado a presentar decl. resumen anual de operaciones del I.E. sobre el Carbón.  [712] |  | A, B o blanco
44 | 102 | 2 | Num | 10. IIEE. Obligado a presentar decl. resumen anual de operaciones del I.E. sobre el Carbón. Fecha. Día [732]
45 | 104 | 2 | Num | 10. IIEE. Obligado a presentar decl. resumen anual de operaciones del I.E. sobre el Carbón. Fecha. Mes [732]
46 | 106 | 4 | Num | 10. IIEE. Obligado a presentar decl. resumen anual de operaciones del I.E. sobre el Carbón. Fecha. Año [732]
47 | 110 | 1 | An | 10. B) Obligación de presentar declaración por el Impuesto Esp. sobre Primas de Seguros  [713] |  | A, B o blanco
48 | 111 | 2 | Num | 10. B) Obligación de presentar declaración por el Impuesto Esp. sobre Primas de Seguros. Fecha. Día  [733]
49 | 113 | 2 | Num | 10. B) Obligación de presentar declaración por el Impuesto Esp. sobre Primas de Seguros. Fecha. Mes  [733]
50 | 115 | 4 | Num | 10. B) Obligación de presentar declaración por el Impuesto Esp. sobre Primas de Seguros. Fecha. Año  [733]
51 | 119 | 82 | An | Reservado para la Agencia Tributaria |  | blancos
52 | 201 | 1 | An | 11. B) Opción por el régimen general del I.V.A. Sujeción o no sujeción  [910,911] |  | S, N o blanco
53 | 202 | 1 | An | 11. B) ¿Ha superado el umbral de 10.000 € en sus adquisiciones intracomunitarias?  [912,913] |  | S, N o blanco
54 | 203 | 3 | An | Reservado para la Agencia Tributaria |  | blancos
55 | 206 | 1 | An | 10. C) Obligación de presentar declaración por Impuestos Mediaoambientales  [708] |  | A, B o blanco
56 | 207 | 2 | Num | 10. C) Obligación de presentar declaración por Impuestos Mediaoambientales.  Fecha. Día  [709]
57 | 209 | 2 | Num | 10. C) Obligación de presentar declaración por Impuestos Mediaoambientales. Fecha. Mes  [709]
58 | 211 | 4 | Num | 10. C) Obligación de presentar declaración por Impuestos Mediaoambientales. Fecha. Año  [709]
59 | 215 | 1 | An | 10. D) Obligado a presentar autoliquidación por el Impuesto sobre Determinados Servicios Digitales[714] |  | A, B o blanco
60 | 216 | 2 | Num | 10. D) Obligado a presentar autoliquidación por el Impuesto sobre Determinados Servicios Digitales. Fecha. Día  [715]
61 | 218 | 2 | Num | 10. D) Obligado a presentar autoliquidación por el Impuesto sobre Determinados Servicios Digitales. Fecha. Mes  [715]
62 | 220 | 4 | Num | 10. D) Obligado a presentar autoliquidación por el Impuesto sobre Determinados Servicios Digitales. Fecha. Año  [715]
63 | 224 | 1 | An | serv.telecom radiotv y via electronica prestados a particulares desde otros estados miembros(art.70. Uno.4.a) .
 Excede de 10.000 / No Excede   [750,751] |  | "S", "N" o blanco
64 | 225 | 1 | An | serv.telecom radiotv y via electronica prestados a particulares desde otros estados miembros(art.70. Uno.4.a) . Destino       [752] |  | "S" o blanco
65 | 226 | 1 | An | serv.telecom radiotv y via electronica prestados a particulares desde otros estados miembros(art.70. Uno.4.a) .Revocacion       [753] |  | "S" o blanco
66 | 227 | 2 | Num | serv.telecom radiotv y via electronica prestados a particulares desde otros estados miembros(art.70. Uno.4.a) .fecha efectos Dia   [754]
67 | 229 | 2 | Num | serv.telecom radiotv y via electronica prestados a particulares desde otros estados miembros(art.70. Uno.4.a) .fecha efectos Mes   [754]
68 | 231 | 4 | Num | serv.telecom radiotv y via electronica prestados a particulares desde otros estados miembros(art.70. Uno.4.a) .fecha efectos Año  [754]
69 | 235 | 1 | An | serv.telecom radiotv y via electronica prestados a particulares desde otros estados miembros(art.70. Uno.8) . 
Excede de 10.000 / No Excede   [755,756] |  | "S", "N" o blanco
70 | 236 | 1 | An | serv.telecom radiotv y via electronica prestados a particulares desde otros estados miembros(art.70. Uno.8) . Destino       [757] |  | "S" o blanco
71 | 237 | 1 | An | serv.telecom radiotv y via electronica prestados a particulares desde otros estados miembros(art.70. Uno.8) .Revocacion       [758] |  | "S" o blanco
72 | 238 | 2 | Num | serv.telecom radiotv y via electronica prestados a particulares desde otros estados miembros(art.70. Uno.8) .fecha efectos Dia   [759]
73 | 240 | 2 | Num | serv.telecom radiotv y via electronica prestados a particulares desde otros estados miembros(art.70. Uno.8) .fecha efectos Mes   [759]
74 | 242 | 4 | Num | serv.telecom radiotv y via electronica prestados a particulares desde otros estados miembros(art.70. Uno.8) .fecha efectos Año  [759]
75 | 246 | 1 | An | I.V.A. A) Solicita alta/baja en el Registro de extractores de depósitos fiscales de productos incluidos en los
ámbitos objetivos de los Impuestos sobre el alcohol y bebidas derivadas [716.a] |  | A, B o blanco
76 | 247 | 2 | Num | I.V.A. A) Solicita alta/baja en el Registro de extractores de depósitos fiscales de productos incluidos en los
ámbitos objetivos de los Impuestos sobre el alcohol y bebidas derivadas Fecha. Día  [717.a]
77 | 249 | 2 | Num | I.V.A. A) Solicita alta/baja en el Registro de extractores de depósitos fiscales de productos incluidos en los
ámbitos objetivos de los Impuestos sobre el alcohol y bebidas derivadas .Fecha. Mes  [717.a]
78 | 251 | 4 | Num | I.V.A. A)Solicita alta/baja en el Registro de extractores de depósitos fiscales de productos incluidos en los
ámbitos objetivos de los Impuestos sobre el alcohol y bebidas derivadas. Fecha. Año  [717.a]
79 | 255 | 1 | An | I.V.A. A) Solicita alta/baja en el Registro de extractores de depósitos fiscales de productos incluidos en los
ámbitos objetivos de los Impuestos sobre  Hidrocarburos [716.b] |  | A, B o blanco
80 | 256 | 2 | Num | I.V.A. A) Solicita alta/baja en el Registro de extractores de depósitos fiscales de productos incluidos en los
ámbitos objetivos de los Impuestos sobre Hidrocarburos Fecha. Día  [717.b]
81 | 258 | 2 | Num | I.V.A. A) Solicita alta/baja en el Registro de extractores de depósitos fiscales de productos incluidos en los
ámbitos objetivos de los Impuestos sobre HidrocarburosFecha. Mes  [717.b]
82 | 260 | 4 | Num | I.V.A. A)Solicita alta/baja en el Registro de extractores de depósitos fiscales de productos incluidos en los
ámbitos objetivos de los Impuestos sobre  Hidrocarburos. Fecha. Año  [717.b]
83 | 264 | 127 | An | Reservado para la Agencia Tributaria
84 | 391 | 10 | An | Identificador de fin de registro. | obligatorio | </T036070>
85 | 401 |  | An | Salto de línea. Constante CRLF. | obligatorio
TOTAL |  | 400 | Posiciones

# Pag. 8

 | Agencia Tributaria
Modelo 036 |  | Diseño de registro. Castellano
 |  | Declaración Censal/Declaración Censal Simplifica de alta, modificación y baja en el Censo de Empresarios, Profesionales y Retenedores
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 9 | An | Inicio del identificador de modelo y página. | obligatorio | <T036080>
2 | 10 | 1 | A | Tipo declaración | obligatorio | blanco o "C" (compl.)
3 | 11 | 1 | An | 12a. Relación de socios, miembros o partícipes. Causa de la presentación.  [802,803,804] |  | A, B, M o blanco
4 | 12 | 2 | Num | 12a. Relación de socios, miembros o partícipes. Causa de la presentación. Fecha. Día  [805]
5 | 14 | 2 | Num | 12a. Relación de socios, miembros o partícipes. Causa de la presentación. Fecha. Mes  [805]
6 | 16 | 4 | Num | 12a. Relación de socios, miembros o partícipes. Causa de la presentación. Fecha. Año  [805]
7 | 20 | 9 | An | 12a. Relación de socios, miembros o partícipes.  N.I.F.  [800]
8 | 29 | 125 | An | 12a. Relac. de socios, miembros o partícipes.  Apellidos y nombre, razón o denom. social  [801]
9 | 154 | 1 | An | 12a. Relac. de soc.miemb. o part. Domic. fisc. en Est. de resid. IRPF. Estimac. obj. Renunc o Revocac [819,820] |  | S, N o blanco
10 | 155 | 1 | An | 12a. Relac. de soc.miemb. o part. Domic. fisc. en Est. de resid. IRPF. E.D.S. Renunc o Revoc. [821,822] |  | S, N o blanco
11 | 156 | 1 | An | 12a. Relac. de soc, miemb. o part. Domic. Fisc. en el Est. de resid. IVA. Rég. Simplif. Renunc o Revoc. [823,824] |  | S, N o blanco
12 | 157 | 1 | An | 12a. Relac. de soc, miemb. o part. Domic. Fisc. en el Est. de resid. IVA. R.E.A.G.P. Renunc o Revoc. [825,826] |  | S, N o blanco
13 | 158 | 5 | Num | 12a. Relac. de soc.miemb. o part. Domic. fisc. en el Est. de resid. Cuota o % de partic. (3 ent + 2 decim.) [818]
14 | 163 | 5 | Num | 12a. Relac. de soc.miemb. o part. Domic. fisc. en el Est. de resid. Cuota o % de atribuc. (3 ent + 2 decim.) [859]
15 | 168 | 200 | An | Reservado para la Agencia Tributaria
16 | 368 | 1 | An | 12b. Relación de socios, miembros o partícipes. Causa de la presentación.  [802,803,804]
17 | 369 | 2 | Num | 12b. Relación de socios, miembros o partícipes. Causa de la presentación. Fecha. Día  [805]
18 | 371 | 2 | Num | 12b. Relación de socios, miembros o partícipes. Causa de la presentación. Fecha. Mes  [805]
19 | 373 | 4 | Num | 12b. Relación de socios, miembros o partícipes. Causa de la presentación. Fecha. Año  [805]
20 | 377 | 9 | An | 12b. Relación de socios, miembros o partícipes.  N.I.F.  [800]
21 | 386 | 125 | An | 12b. Relac. de socios, miembros o partícipes.  Apellidos y nombre, razón o denom. social  [801]
22 | 511 | 1 | An | 12b. Relac. de soc.miemb. o part. Domic. fisc. en Est. de resid. IRPF. Estimac. obj. Renunc o Revocac [819,820] |  | S, N o blanco
23 | 512 | 1 | An | 12b. Relac. de soc.miemb. o part. Domic. fisc. en Est. de resid. IRPF. E.D.S. Renunc o Revoc. [821,822] |  | S, N o blanco
24 | 513 | 1 | An | 12b. Relac. de soc, miemb. o part. Domic. Fisc. en el Est. de resid. IVA. Rég. Simplif. Renunc o Revoc. [823,824] |  | S, N o blanco
25 | 514 | 1 | An | 12b. Relac. de soc, miemb. o part. Domic. Fisc. en el Est. de resid. IVA. R.E.A.G.P. Renunc o Revoc. [825,826] |  | S, N o blanco
26 | 515 | 5 | Num | 12b. Relac. de soc.miemb. o part. Domic. fisc. en el Est. de resid. Cuota o % de partic. (3 ent + 2 decim.) [818]
27 | 520 | 5 | Num | 12b. Relac. de soc.miemb. o part. Domic. fisc. en el Est. de resid. Cuota o % de atribuc. (3 ent + 2 decim.) [859]
28 | 525 | 200 | An | Reservado para la Agencia Tributaria
29 | 725 | 1 | An | 12c. Relación de socios, miembros o partícipes. Causa de la presentación.  [802,803,804]
30 | 726 | 2 | Num | 12c. Relación de socios, miembros o partícipes. Causa de la presentación. Fecha. Día  [805]
31 | 728 | 2 | Num | 12c. Relación de socios, miembros o partícipes. Causa de la presentación. Fecha. Mes  [805]
32 | 730 | 4 | Num | 12c. Relación de socios, miembros o partícipes. Causa de la presentación. Fecha. Año  [805]
33 | 734 | 9 | An | 12c. Relación de socios, miembros o partícipes.  N.I.F.  [800]
34 | 743 | 125 | An | 12c. Relac. de socios, miembros o partícipes.  Apellidos y nombre, razón o denom. social  [801]
35 | 868 | 1 | An | 12c. Relac. de soc.miemb. o part. Domic. fisc. en Est. de resid. IRPF. Estimac. obj. Renunc o Revocac [819,820] |  | S, N o blanco
36 | 869 | 1 | An | 12c. Relac. de soc.miemb. o part. Domic. fisc. en Est. de resid. IRPF. E.D.S. Renunc o Revoc. [821,822] |  | S, N o blanco
37 | 870 | 1 | An | 12c. Relac. de soc, miemb. o part. Domic. Fisc. en el Est. de resid. IVA. Rég. Simplif. Renunc o Revoc. [823,824] |  | S, N o blanco
38 | 871 | 1 | An | 12c. Relac. de soc, miemb. o part. Domic. Fisc. en el Est. de resid. IVA. R.E.A.G.P. Renunc o Revoc. [825,826] |  | S, N o blanco
39 | 872 | 5 | Num | 12c. Relac. de soc.miemb. o part. Domic. fisc. en el Est. de resid. Cuota o % de partic. (3 ent + 2 decim.) [818]
40 | 877 | 5 | Num | 12c. Relac. de soc.miemb. o part. Domic. fisc. en el Est. de resid. Cuota o % de atribuc. (3 ent + 2 decim.) [859]
41 | 882 | 200 | An | Reservado para la Agencia Tributaria
42 | 1082 | 1 | An | 12d. Relación de socios, miembros o partícipes. Causa de la presentación.  [802,803,804]
43 | 1083 | 2 | Num | 12d. Relación de socios, miembros o partícipes. Causa de la presentación. Fecha. Día  [805]
44 | 1085 | 2 | Num | 12d. Relación de socios, miembros o partícipes. Causa de la presentación. Fecha. Mes  [805]
45 | 1087 | 4 | Num | 12d. Relación de socios, miembros o partícipes. Causa de la presentación. Fecha. Año  [805]
46 | 1091 | 9 | An | 12d. Relación de socios, miembros o partícipes.  N.I.F.  [800]
47 | 1100 | 125 | An | 12d. Relac. de socios, miembros o partícipes.  Apellidos y nombre, razón o denom. social  [801]
48 | 1225 | 1 | An | 12d. Relac. de soc.miemb. o part. Domic. fisc. en Est. de resid. IRPF. Estimac. obj. Renunc o Revocac [819,820] |  | S, N o blanco
49 | 1226 | 1 | An | 12d. Relac. de soc.miemb. o part. Domic. fisc. en Est. de resid. IRPF. E.D.S. Renunc o Revoc. [821,822] |  | S, N o blanco
50 | 1227 | 1 | An | 12d. Relac. de soc, miemb. o part. Domic. Fisc. en el Est. de resid. IVA. Rég. Simplif. Renunc o Revoc. [823,824] |  | S, N o blanco
51 | 1228 | 1 | An | 12d. Relac. de soc, miemb. o part. Domic. Fisc. en el Est. de resid. IVA. R.E.A.G.P. Renunc o Revoc. [825,826] |  | S, N o blanco
52 | 1229 | 5 | Num | 12d. Relac. de soc.miemb. o part. Domic. fisc. en el Est. de resid. Cuota o % de partic. (3 ent + 2 decim.) [818]
53 | 1234 | 5 | Num | 12d. Relac. de soc.miemb. o part. Domic. fisc. en el Est. de resid. Cuota o % de atribuc. (3 ent + 2 decim.) [859]
54 | 1239 | 552 | An | Reservado para la Agencia Tributaria
55 | 1791 | 10 | An | Identificador de fin de registro. | obligatorio | </T036080>
56 | 1801 |  | An | Salto de línea. Constante CRLF. | obligatorio
TOTAL |  | 1800 | Posiciones

# Pag. 9

 | Agencia Tributaria
Modelo 036 |  | Diseño de registro. Castellano
 |  | Declaración Censal/Declaración Censal Simplifica de alta, modificación y baja en el Censo de Empresarios, Profesionales y Retenedores
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 9 | An | Inicio del identificador de modelo y página. | obligatorio | <T036090>
2 | 10 | 1 | A | Tipo declaración (maximo 12 sucesores en total - 2 paginas) | obligatorio | blanco o "C" (compl.)
3 | 11 | 9 | An | 13a  Relación de sucesores. Sucesor o beneficiario.  N.I.F.  [920]
4 | 20 | 125 | An | 13a  Relación de sucesores. Sucesor o beneficiario.  Apellidos y nombre, razón o denom. social  921]
5 | 145 | 5 | Num | 13a  Relación de sucesores. Sucesor o beneficiario.  % de liquidacion,participacion,herencia c. (3 ent + 2 decim.) 922]
6 | 150 | 14 | Num | 13a  Relación de sucesores. Sucesor o beneficiario.  Cuota de liquidacion /patrimonio/caudal hereditario. (12 ent + 2 decim.) 923]
7 | 164 | 50 | An | Reservado para la Agencia Tributaria
8 | 214 | 9 | An | 13b  Relación de sucesores. Sucesor o beneficiario.  N.I.F.  [924]
9 | 223 | 125 | An | 13b  Relación de sucesores. Sucesor o beneficiario.  Apellidos y nombre, razón o denom. social  925]
10 | 348 | 5 | Num | 13b  Relación de sucesores. Sucesor o beneficiario.  % de liquidacion,participacion,herencia c. (3 ent + 2 decim.) 926]
11 | 353 | 14 | Num | 13b  Relación de sucesores. Sucesor o beneficiario.  Cuota de liquidacion /patrimonio/caudal hereditario. (12 ent + 2 decim.) 927]
12 | 367 | 50 | An | Reservado para la Agencia Tributaria
13 | 417 | 9 | An | 13c  Relación de sucesores. Sucesor o beneficiario.  N.I.F.  [928]
14 | 426 | 125 | An | 13c  Relación de sucesores. Sucesor o beneficiario.  Apellidos y nombre, razón o denom. social  929]
15 | 551 | 5 | Num | 13c  Relación de sucesores. Sucesor o beneficiario.  % de liquidacion,participacion,herencia c. (3 ent + 2 decim.) 930]
16 | 556 | 14 | Num | 13c  Relación de sucesores. Sucesor o beneficiario.  Cuota de liquidacion /patrimonio/caudal hereditario (12 ent + 2 decim.) 931]
17 | 570 | 50 | An | Reservado para la Agencia Tributaria
18 | 620 | 9 | An | 13d  Relación de sucesores. Sucesor o beneficiario.  N.I.F.  [932]
19 | 629 | 125 | An | 13d  Relación de sucesores. Sucesor o beneficiario.  Apellidos y nombre, razón o denom. social  933]
20 | 754 | 5 | Num | 13d  Relación de sucesores. Sucesor o beneficiario.  % de liquidacion,participacion,herencia c. (3 ent + 2 decim.) 934]
21 | 759 | 14 | Num | 13d  Relación de sucesores. Sucesor o beneficiario.  Cuota de liquidacion /patrimonio/caudal hereditario (12 ent + 2 decim.) 935]
22 | 773 | 50 | An | Reservado para la Agencia Tributaria
23 | 823 | 9 | An | 13e  Relación de sucesores. Sucesor o beneficiario.  N.I.F.  [936]
24 | 832 | 125 | An | 13e  Relación de sucesores. Sucesor o beneficiario.  Apellidos y nombre, razón o denom. social  937]
25 | 957 | 5 | Num | 13e  Relación de sucesores. Sucesor o beneficiario.  % de liquidacion,participacion,herencia c. (3 ent + 2 decim.) 938]
26 | 962 | 14 | Num | 13e  Relación de sucesores. Sucesor o beneficiario.   Cuota de liquidacion /patrimonio/caudal hereditario (12 ent + 2 decim.) 939]
27 | 976 | 50 | An | Reservado para la Agencia Tributaria
28 | 1026 | 9 | An | 13f  Relación de sucesores. Sucesor o beneficiario.  N.I.F.  [940]
29 | 1035 | 125 | An | 13f  Relación de sucesores. Sucesor o beneficiario.  Apellidos y nombre, razón o denom. social  941]
30 | 1160 | 5 | Num | 13f  Relación de sucesores. Sucesor o beneficiario.  % de liquidacion,participacion,herencia c. (3 ent + 2 decim.) 942]
31 | 1165 | 14 | Num | 13f  Relación de sucesores. Sucesor o beneficiario.   Cuota de liquidacion /patrimonio/caudal hereditario(12 ent + 2 decim.) 943]
32 | 1179 | 112 | An | Reservado para la Agencia Tributaria
33 | 1291 | 10 | An | Identificador de fin de registro. | obligatorio | </T036090>
34 | 1301 |  | An | Salto de línea. Constante CRLF. | obligatorio
TOTAL |  | 1300 | Posiciones

# Pag. 10

 | Agencia Tributaria
Modelo 036 |  | Diseño de registro. Castellano
 |  | Declaración Censal/Declaración Censal Simplifica de alta, modificación y baja en el Censo de Empresarios, Profesionales y Retenedores
Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido
1 | 1 | 9 | An | Inicio del identificador de modelo y página. | obligatorio | <T036100>
2 | 10 | 1 | A | Tipo declaración (maximo 40 titulares en total - 7 paginas) (espacio para 42 aunque solo pueden venir 40) | obligatorio | blanco o "C" (compl.)
3 | 11 | 1 | An | 14a. Relación de titulares reales. Causa de la presentación.  [1000,1001, 1002] |  | A, B, M o blanco
4 | 12 | 2 | Num | 14a. Relación de titulares reales. Causa de la presentación. Fecha. Día  [1003]
5 | 14 | 2 | Num | 14a. Relación de titulares reales. Causa de la presentación. Fecha. Mes  [1003]
6 | 16 | 4 | Num | 14a. Relación de titulares reales. Causa de la presentación. Fecha. Año  [1003]
7 | 20 | 4 | An | 14a. Relación de titulares reales. Tipo de documento identificativo |  | ver nota a pie
8 | 24 | 102 | An | 14a. Relación de titulares reales.NIF / Código de identificación extranjero
9 | 126 | 125 | An | 14a. Relación de titulares reales.  Apellidos y nombre
10 | 251 | 2 | An | 14a. Relación de titulares reales. País de expedición del documento de identificación |  | código iso
11 | 253 | 2 | Num | 14a. Relación de titulares reales. Fecha de nacimiento. Día
12 | 255 | 2 | Num | 14a. Relación de titulares reales. Fecha de nacimiento. Mes
13 | 257 | 4 | Num | 14a. Relación de titulares reales. Fecha de nacimiento. Año
14 | 261 | 2 | An | 14a. Relación de titulares reales. País de residencia |  | código iso
15 | 263 | 2 | An | 14a. Relación de titulares reales. Nacionalidad |  | código iso
16 | 265 | 30 | An | Reservado para la Agencia Tributaria
17 | 295 | 1 | An | 14b. Relación de titulares reales. Causa de la presentación.  [1004,1005, 1006] |  | A, B, M o blanco
18 | 296 | 2 | Num | 14b. Relación de titulares reales. Causa de la presentación. Fecha. Día  [1007]
19 | 298 | 2 | Num | 14b. Relación de titulares reales. Causa de la presentación. Fecha. Mes  [1007]
20 | 300 | 4 | Num | 14b. Relación de titulares reales. Causa de la presentación. Fecha. Año  [1007]
21 | 304 | 4 | An | 14b. Relación de titulares reales. Tipo de documento identificativo
22 | 308 | 102 | An | 14b. Relación de titulares reales.NIF / Código de identificación extranjero
23 | 410 | 125 | An | 14b. Relación de titulares reales.  Apellidos y nombre
24 | 535 | 2 | An | 14b. Relación de titulares reales. País de expedición del documento de identificación |  | código iso
25 | 537 | 2 | Num | 14b. Relación de titulares reales. Fecha de nacimiento. Día
26 | 539 | 2 | Num | 14b. Relación de titulares reales. Fecha de nacimiento. Mes
27 | 541 | 4 | Num | 14b. Relación de titulares reales. Fecha de nacimiento. Año
28 | 545 | 2 | An | 14b. Relación de titulares reales. País de residencia |  | código iso
29 | 547 | 2 | An | 14b. Relación de titulares reales. Nacionalidad |  | código iso
30 | 549 | 30 | An | Reservado para la Agencia Tributaria
31 | 579 | 1 | An | 14c. Relación de titulares reales. Causa de la presentación.  [1008,1009, 1010] |  | A, B, M o blanco
32 | 580 | 2 | Num | 14c. Relación de titulares reales. Causa de la presentación. Fecha. Día  [1011]
33 | 582 | 2 | Num | 14c. Relación de titulares reales. Causa de la presentación. Fecha. Mes  [1011]
34 | 584 | 4 | Num | 14c. Relación de titulares reales. Causa de la presentación. Fecha. Año  [1011]
35 | 588 | 4 | An | 14c. Relación de titulares reales. Tipo de documento identificativo
36 | 592 | 102 | An | 14c. Relación de titulares reales.NIF / Código de identificación extranjero
37 | 694 | 125 | An | 14c. Relación de titulares reales.  Apellidos y nombre
38 | 819 | 2 | An | 14c. Relación de titulares reales. País de expedición del documento de identificación |  | código iso
39 | 821 | 2 | Num | 14c. Relación de titulares reales. Fecha de nacimiento. Día
40 | 823 | 2 | Num | 14c. Relación de titulares reales. Fecha de nacimiento. Mes
41 | 825 | 4 | Num | 14c. Relación de titulares reales. Fecha de nacimiento. Año
42 | 829 | 2 | An | 14c. Relación de titulares reales. País de residencia |  | código iso
43 | 831 | 2 | An | 14c. Relación de titulares reales. Nacionalidad |  | código iso
44 | 833 | 30 | An | Reservado para la Agencia Tributaria
45 | 863 | 1 | An | 14d. Relación de titulares reales. Causa de la presentación.  [1012,1013, 1014] |  | A, B, M o blanco
46 | 864 | 2 | Num | 14d. Relación de titulares reales. Causa de la presentación. Fecha. Día  [1015]
47 | 866 | 2 | Num | 14d. Relación de titulares reales. Causa de la presentación. Fecha. Mes  [1015]
48 | 868 | 4 | Num | 14d. Relación de titulares reales. Causa de la presentación. Fecha. Año  [1015]
49 | 872 | 4 | An | 14d. Relación de titulares reales. Tipo de documento identificativo
50 | 876 | 102 | An | 14d. Relación de titulares reales.NIF / Código de identificación extranjero
51 | 978 | 125 | An | 14d. Relación de titulares reales.  Apellidos y nombre
52 | 1103 | 2 | An | 14d. Relación de titulares reales. País de expedición del documento de identificación |  | código iso
53 | 1105 | 2 | Num | 14d. Relación de titulares reales. Fecha de nacimiento. Día
54 | 1107 | 2 | Num | 14d. Relación de titulares reales. Fecha de nacimiento. Mes
55 | 1109 | 4 | Num | 14d. Relación de titulares reales. Fecha de nacimiento. Año
56 | 1113 | 2 | An | 14d. Relación de titulares reales. País de residencia |  | código iso
57 | 1115 | 2 | An | 14d. Relación de titulares reales. Nacionalidad |  | código iso
58 | 1117 | 30 | An | Reservado para la Agencia Tributaria
59 | 1147 | 1 | An | 14e. Relación de titulares reales. Causa de la presentación.  [1016,1017, 1018] |  | A, B, M o blanco
60 | 1148 | 2 | Num | 14e. Relación de titulares reales. Causa de la presentación. Fecha. Día  [1019]
61 | 1150 | 2 | Num | 14e. Relación de titulares reales. Causa de la presentación. Fecha. Mes  [1019]
62 | 1152 | 4 | Num | 14e. Relación de titulares reales. Causa de la presentación. Fecha. Año  [1019]
63 | 1156 | 4 | An | 14e. Relación de titulares reales. Tipo de documento identificativo
64 | 1160 | 102 | An | 14e. Relación de titulares reales.NIF / Código de identificación extranjero
65 | 1262 | 125 | An | 14e. Relación de titulares reales.  Apellidos y nombre
66 | 1387 | 2 | An | 14e. Relación de titulares reales. País de expedición del documento de identificación |  | código iso
67 | 1389 | 2 | Num | 14e. Relación de titulares reales. Fecha de nacimiento. Día
68 | 1391 | 2 | Num | 14e. Relación de titulares reales. Fecha de nacimiento. Mes
69 | 1393 | 4 | Num | 14e. Relación de titulares reales. Fecha de nacimiento. Año
70 | 1397 | 2 | An | 14e. Relación de titulares reales. País de residencia |  | código iso
71 | 1399 | 2 | An | 14e. Relación de titulares reales. Nacionalidad |  | código iso
72 | 1401 | 30 | An | Reservado para la Agencia Tributaria
73 | 1431 | 1 | An | 14f. Relación de titulares reales. Causa de la presentación.  [1020,1021, 1022] |  | A, B, M o blanco
74 | 1432 | 2 | Num | 14f. Relación de titulares reales. Causa de la presentación. Fecha. Día  [1023]
75 | 1434 | 2 | Num | 14f. Relación de titulares reales. Causa de la presentación. Fecha. Mes  [1023]
76 | 1436 | 4 | Num | 14f. Relación de titulares reales. Causa de la presentación. Fecha. Año  [1023]
77 | 1440 | 4 | An | 14f. Relación de titulares reales. Tipo de documento identificativo
78 | 1444 | 102 | An | 14f. Relación de titulares reales.NIF / Código de identificación extranjero
79 | 1546 | 125 | An | 14f. Relación de titulares reales.  Apellidos y nombre
80 | 1671 | 2 | An | 14f. Relación de titulares reales. País de expedición del documento de identificación |  | código iso
81 | 1673 | 2 | Num | 14f. Relación de titulares reales. Fecha de nacimiento. Día
82 | 1675 | 2 | Num | 14f. Relación de titulares reales. Fecha de nacimiento. Mes
83 | 1677 | 4 | Num | 14f. Relación de titulares reales. Fecha de nacimiento. Año
84 | 1681 | 2 | An | 14f. Relación de titulares reales. País de residencia |  | código iso
85 | 1683 | 2 | An | 14f. Relación de titulares reales. Nacionalidad |  | código iso
86 | 1685 | 30 | An | Reservado para la Agencia Tributaria
87 | 1715 | 1 | An | Declaración de no variación de datos |  | S' o blanco
88 | 1716 | 1 | An | Entidad sin obligación de identificar al titular real |  | 'S' o blanco
88 | 1717 | 24 | An | Reservado para la Agencia Tributaria
89 | 1741 | 10 | An | Identificador de fin de registro. | obligatorio | </T036100>
90 | 1751 |  | An | Salto de línea. Constante CRLF. | obligatorio
TOTAL |  | 1750 | Posiciones
 |  |  | nota | Valores admitidos para el Tipo de documento identificativo:
NIF
TIN
PASA (pasaporte)