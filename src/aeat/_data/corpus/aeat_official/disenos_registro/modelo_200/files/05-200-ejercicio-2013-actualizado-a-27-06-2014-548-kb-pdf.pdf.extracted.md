# Pag. 1

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 17 An Constante. <T + modelo + discriminante (*) + Ejercicio devengo + periodo + tipo + > "<T200020130A0000>"
2 18 5 An Constante "<AUX>"
3 23 70 An Reservado para la Administración. Rellenar con blancos BLANCOS
4 93 4 An Versión del programa (**)
5 97 4 An Reservado para la Administración. Rellenar con blancos
66 110011 99 AAnn NNIIFF EEmmpprreessaa DDeessaarrrroolllloo ((****))
7 110 213 An Reservado para la Administración. Rellenar con blancos
8 323 6 An Constante "</AUX>"
9 329 8 An Constante "<VECTOR>"
Vector de páginas. Para su cumplimentación se debe indicar de forma secuencial las páginas que forman parte de esta declaración.
Cada página se indicará con 3 digitos. Después de la última página se pondrá el identificador "FIN". Por ejemplo, en un fichero que
contenga una página 1, dos 2, una 3, una 4, una 5, una 6, una 7, una 8, una 9, una 10, una 11, una 12, una 13, una 14, una 15, una
16, una 17, una 18, una 18 bis, dos 19, una DID debería rellenarse el vector con el siguiente
contenido:01002002003004005006007008009010011012013014015016017018018B190190DIDFIN (y el resto a blancos hasta
10 337 600 An completar las 600 posiciones)
11 937 9 An Constante "</VECTOR>"
Contenido del fichero. Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito
12 946Variable An para cada página en este mismo documento
13*** 18 An Constante. </T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > "</T200020130A0000>"
14*** 2An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total Variable
(*) NOTA. Valor discriminante: "0" Normal, Abreviado y PYMES; "A" Aseguradoras; "E" Entidades de crédito; "I" Inversión colectiva; "G" Garantía recíproca.
Debe rellenarse en función del estado de cuentas que se cumplimenta.
(**) A cumplimentar por las entidades desarrolladoras (EEDD):
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
Página 1

# Pag. 2

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "010"
4 9 1 An Fin de identificador de modelo y página. Constante ">". OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria. En blanco
66 1111 44 NNuumm PPeerriiooddoo IImmppoossiittiivvoo - AAññoo iinniicciioo
7 15 2 Num Periodo Impositivo - Mes inicio
8 17 2 Num Periodo Impositivo - Día Inicio
9 19 4 Num Periodo Impositivo - Año final
10 23 2 Num Periodo Impositivo - Mes final
11 25 2 Num Periodo Impositivo - Día final
12 27 1 Num Identificación - Tipo de ejercicio "1", "2" ó "3"
13 28 4 Num Identificación - C.N.A.E. Actividad principal Incluido en el fichero CNAE.TXT.
14 32 9 An Identificación - NIF
15 41 40 An Identificación - Apellidos y nombre o Razón Social
16 81 9 An Identificación - Teléfono 1
17 90 9 An Identificación - Teléfono 2
18 99 4 Num Ejercicio
1199 110033 11 NNuumm EEnnttiiddaadd ssiinn áánniimmoo ddee lluuccrroo aaccooggiiddaa rrééggiimmeenn ffiissccaall TTííttuulloo IIII LLeeyy 4499//22000022 [[000011]]
20 104 1 Num Entidad parcialmente exenta [002]
21 105 1 Num Sociedad de inversión de capital variable o fondo de inversión de carácter financiero [003]
22 106 1 Num Sociedad de inversión inmobiliaria o fondo de inversión inmobiliaria [004]
23 107 1 Num Comunidades titulares de montes vecinales en mano común [005]
24 108 1 Num Entidad de tenencia de valores extranjeros [011]
25 109 1 Num Agrupación de interés económico española o U.T.E. [013]
26 110 1 Num Agrupación europea de interés económico [014]
27 111 1 Num Cooperativa protegida [017]
28 112 1 Num Cooperativa especialmente protegida [018]
29 113 1 Num Resto cooperativas [019]
30 114 1 Num Establecimiento permanente [021]
31 115 1 Num Gran empresa [023]
32 116 1 Num Entidad de crédito [024]
33 117 1 Num Entidad aseguradora [025]
34 118 1 Num Entidades de capital-riesgo [031]
35 119 1 Num Sociedades desarrollo industrial regional [032]
36 120 1 Num Sociedad de garantía recíproca o de reafianzamiento [036]
37 121 1 Num Fondo de Pensiones Real Decreto Legislativo 1/2002 de 29 de noviembre [048]
38 122 1 Num Mutua de seguros o Mutualidad de previsión social [058]
39 123 1 Num Fondos o activos de titulización [060]
40 124 1 Num Incentivos empresa de reducida dimensión ( cap XII, tít VII L.I.S ) [006]
41 125 1 Num Entidad ZEC [015]
42 126 1 Num Régimen entidades navieras en función del tonelaje [022]
43 127 1 Num Tributación conjunta Estado/Diput.Cdad.Forales [028]
4444 112288 11 NNuumm EEnnttiiddaaddeess ssoommeettiiddaass aa nnoorrmmaattiivvaa ffoorraall [[004477]]
45 129 1 Num Regímenes especiales de normativa foral [049]
46 130 1 Num Régimen especial Canarias [029]
47 131 1 Num Régimen especial minería [033]
48 132 1 Num Régimen especial hidrocarburos [034]
49 133 1 Num Entidad dedicada al arrend.viviendas [038]
50 134 1 Num Entidad en rég. atribución de rentas constituida en el extranjero con presencia en territorio español [046]
51 135 1 Num SOCIMI [012]
52 136 1 Num Entidades que aplican el régimen especial Ley 11/2009 (excepto SOCIMI) [057]
53 137 1 Num Otros regímenes especiales [020]
54 138 1 Num Tipo gravamen reducido mant.o creación empleo [056]
55 139 1 Num Inclusión en base imponible rentas positivas art. 107 L.I.S. [007]
56 140 1 Num Opción art. 107.6 L.I.S. [008]
5577 114411 11 NNuumm SSoocciieeddaadd ddoommiinnaannttee ddee ggrruuppoo ffiissccaall [[000099]]
58 142 1 Num Sociedad dependiente de grupo fiscal [010]
59 143 1 Num Opción art.51.2.b) L.I.S. [016]
60 144 1 Num Entidad inactiva [026]
61 145 1 Num Base imponible negativa o cero [027]
62 146 1 Num Transmisión elementos patrimoniales arts. 26.2.d) y 84.1 L.I.S. [030]
63 147 1 Num Opción art. 43.1 R.I.S. [035]
64 148 1 Num Opción art. 43.3 R.I.S. [037]
65 149 1 Num Entidad que forma parte de un grupo mercantil (art. 42 del Cód. Comercio) [039]
66 150 1 Num Obligación información art. 15 R.I.S. [043]
67 151 1 Num Obligación información art. 45 R.I.S. [044]
68 152 1 Num Inversiones anticipadas - reserva inversiones en Canarias (art. 27.11 Ley 19/1994) [045]
Régimen fiscal de operaciones de aportación de activos a sociedades para la gestión de activos (Ley 8/2012) [062]
6699 115533 11 NNum
70 154 1 Num Tipo de gravamen reducido para entidades de nueva creción (D.A. 19ª LIS) [063]
71 155 1 Num Opción art.44.2 LIS [059]
72 156 1 Num Balance y ECPN 0.No consta 1.Mod.normal 2.Mod.abreviado 3. Mod.PYMES
73 157 1 Num Pérdidas y ganancias 0.No consta 1.Mod.normal 2.Mod.abreviado 3. Mod.PYMES
74 158 1 Num Estados de cuentas de Instituciones de inversión colectiva [061]
75 159 7 An Nº de grupo fiscal al que pertenecen las entidades que hayan marcado las claves 009 ó 010 [040]
76 166 9 An N.I.F. de la sociedad dominante para entidades que hayan marcado la clave 010
77 175 9 Num Personal asalariado (cifra media del ejercicio) Personal fijo [041] 7enteros 2 decimales
78 184 9 Num Personal asalariado (cifra media del ejercicio) Personal no fijo [042] 7enteros 2 decimales
79 193 1 Num Declaración complementaria
80 194 13 Num Nº de justificante de la declaración anterior
81 207 21 An D. - Nombre o Razón social - Secretario del Consejjo de Administración
82 228 09 An N.I.F. - Secretario del Consejo de Administración
83 237 08 Num Fecha - Contribuyentes por el I.R.N.R. AAAAMMDD
84 245 36 An Declaración representantes legales entidad - 1 - Nombre y apellidos
85 281 9 An Declaración representantes legales entidad - 1 - N.I.F
Página 2

# Pag. 3

86 290 8 Num Declaración representantes legales entidad - 1 - Fecha Poder AAAAMMDD
87 298 12 An Declaración representantes legales entidad - 1 - Notaría
88 310 36 An Declaración representantes legales entidad - 2 - Nombre y apellidos
89 346 9 An Declaración representantes legales entidad - 2 - N.I.F
90 355 8 Num Declaración representantes legales entidad - 2 - Fecha Poder AAAAMMDD
91 363 12 An Declaración representantes legales entidad - 2 - Notaría
92 375 36 An Declaración representantes legales entidad - 3 - Nombre y apellidos
93 411 9 An Declaración representantes legales entidad - 3 - N.I.F
94 420 8 Num Declaración representantes legales entidad - 3 - Fecha Poder AAAAMMDD
95 428 12 An Declaración representantes legales entidad - 3 - Notaría
96 440 21 An RESERVADO PARA LA A.E.A.T. (Dejar en blanco) Incluye Nº Referencia
97 461 20 An Identificador cliente EEDD. RESERVADO PARA LAS EEDD.
9988 448811 5500 AAnn NNoommbbrree yy AAppeelllliiddooss ddee llaa ppeerrssoonnaa ddee ccoonnttaaccttoo ppaarraa iinncciiddeenncciiaass
99 531 9 Num Teléfono fijo de contacto para incidencias
100 540 9 Num Teléfono móvil de contacto para incidencias
101 549 50 An Dirección de correo electrónico para incidencias
102 599 13 An SELLO ELECTRONICO RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
103 612 10 An Identificador de fin de Registro. OBLIGATORIO </T200010>
Total: 621
NOTA: Los importes son de 15 enteros (o N + 14) y 2 decimales
Página 3

# Pag. 4

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas
vers. 1.0
constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An C Inicio del identificador de modelo y página. Constante "<T"
2 3 3 Num C Modelo. Constante "200"
3 6 3 An C Página. Constante "020"
4 9 1 An C Fin de identificador de modelo y página. Constante ">"
Indicador de página complementaria. Blanco (No
compplementaria)) o
5 10 1 An C "C" (Complementaria)
6 11 9 An C A. Relación de administradores .1 - N.I.F.
7 20 1 A C A. Relación de administradores. 1 - F/J "F" o "J"
8 21 1 Num C A. Relación de administradores. 1 - RPTE. ( "0", "1")
9 22 40 An C A. Relación de administradores. 1 - Apellidos y nombre / Razón social
10 62 17 An C A. Relación de administradores. 1 - Domicilio fiscal
11 79 2 An C A. Relación de administradores .1 - Código Provincial
12 81 9 An C A. Relación de administradores. 2 - N.I.F.
13 90 1 A C A. Relación de administradores. 2 - F/J "F" o "J"
14 91 1 Num C A. Relación de administradores. 2 - RPTE. ( "0", "1")
15 92 40 An C A. Relación de administradores. 2 - Apellidos y nombre / Razón social
16 132 17 An C A. Relación de administradores. 2 - Domicilio fiscal
1177 114499 22 AAn CC AA. RReellaacciióónn ddee aaddmmiinniissttrraaddoorreess. 22 - CCóóddiiggoo PPrroovviinncciiaall
18 151 9 An C A. Relación de administradores. 3 - N.I.F.
19 160 1 A C A. Relación de administradores. 3 - F/J "F" o "J"
20 161 1 Num C A. Relación de administradores. 3 - RPTE. ( "0", "1")
21 162 40 An C A. Relación de administradores. 3 - Apellidos y nombre / Razón social
22 202 17 An C A. Relación de administradores. 3 - Domicilio fiscal
23 219 2 An C A. Relación de administradores. 3 - Código Provincial
24 221 9 An C A. Relación de administradores. 4 - N.I.F.
25 230 1 A C A. Relación de administradores. 4 - F/J "F" o "J"
26 231 1 Num C A. Relación de administradores. 4 - RPTE. ( "0", "1")
27 232 40 An C A. Relación de administradores. 4 - Apellidos y nombre / Razón social
28 272 17 An C A. Relación de administradores. 4 - Domicilio fiscal
2299 228899 22 AAnn CC AA.. RReellaacciióónn ddee aaddmmiinniissttrraaddoorreess.. 44 - CCóóddiiggoo PPrroovviinncciiaall
30 291 9 An C A. Relación de administradores. 5 - N.I.F.
31 300 1 A C A. Relación de administradores. 5 - F/J "F" o "J"
32 301 1 Num C A. Relación de administradores. 5 - RPTE. ( "0", "1")
33 302 40 An C A. Relación de administradores. 5 - Apellidos y nombre / Razón social
34 342 17 An C A. Relación de administradores. 5 - Domicilio fiscal
35 359 2 An C A. Relación de administradores. 5 - Código Provincial
36 361 9 An C A. Relación de administradores. 6 - N.I.F.
37 370 1 A C A. Relación de administradores. 6 - F/J "F" o "J"
38 371 1 Num C A. Relación de administradores. 6 - RPTE. ( "0", "1")
39 372 40 An C A. Relación de administradores. 6 - Apellidos y nombre / Razón social
40 412 17 An C A. Relación de administradores. 6 - Domicilio fiscal
41 429 2 An C A. Relación de administradores. 6 - Código Provincial
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos participada -
42 431 15 An C N.I.F.
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos participada -
43 446 30 An C Nombre o razón social
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos participada -
44 476 2 An C Código provincia / país
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos de la
45 478 5 Num C declarante - Porcentaje de participación
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos de la
46 483 17 Num C declarante - Valor nominal total de la participación
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos de la
47 500 17 Num C declarante - Valor en libros (en el activo de la declarante) de la participación
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos de la
4488 551177 1177 NNuumm CC ddeeccllaarraannttee -- IInnggrreessooss ppoorr DDiivviiddeennddooss rreecciibbiiddooss eenn eell eejjeerrcciicciioo ddeeccllaarraaddoo
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Correcciones
49 534 17 N C valorativas - Corrección de valor pérdidas y ganancias ejercicio
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Correcciones
50 551 17 N C valorativas - Reversión de pérdidas por deterioro de valores
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Correcciones
51 568 17 N C valorativas - Efecto corrección valorativa en la BI del ejercicio
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Corrrecciones
valorativas - Saldo de correcciones fiscales (art. 12.3 LIS) pendientes a fin de ejercicio
52 585 17 N C
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos adicionales
53 602 17 Num C participada - Capital
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos adicionales
54 619 17 Num C participada - Reservas
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos adicionales
55 636 17 N C participada - Otras partidas del patrimonio neto
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 1 - Datos adicionales
56 653 17 N C participada - Resultado del último ejercicio
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos participada -
57 670 15 An C N.I.F.
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos participada -
58 685 30 An C Nombre o razón social
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos participada -
59 715 2 An C Código provincia / país
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos de la
60 717 5 Num C declarante - Porcentaje de participación
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos de la
6611 772222 1177 NNuumm CC ddeeccllaarraannttee -- VVaalloorr nnoommiinnaall ttoottaall ddee llaa ppaarrttiicciippaacciióónn
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos de la
62 739 17 Num C declarante - Valor en libros (en el activo de la declarante) de la participación
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos de la
63 756 17 Num C declarante - Ingresos por Dividendos recibidos en el ejercicio declarado
Página 4

# Pag. 5

B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Correcciones
64 773 17 N C valorativas - Corrección de valor pérdidas y ganancias ejercicio
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Correcciones
65 790 17 N C valorativas - Reversión de pérdidas por deterioro de valores
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Correcciones
66 807 17 N C valorativas - Efecto corrección valorativa en la BI del ejercicio
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Corrrecciones
valorativas - Saldo de correcciones fiscales (art. 12.3 LIS) pendientes a fin de ejercicio
67 824 17 N C
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos adicionales
68 841 17 Num C participada - Capital
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos adicionales
69 858 17 Num C participada - Reservas
BB. PPaarrttiicciippaacciioonneess ddiirreeccttaass -- BB.11. PPaarrttiicciippaacciioonneess ddeeccllaarraannttee eenn oottrraass eennttiiddaaddeess -- EEnnttiiddaadd 22 -- DDaattooss aaddiicciioonnaalleess
70 875 17 N C participada - Otras partidas del patrimonio neto
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 2 - Datos adicionales
71 892 17 N C participada - Resultado del último ejercicio
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos participada -
72 909 15 An C N.I.F.
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos participada -
73 924 30 An C Nombre o razón social
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos participada -
74 954 2 An C Código provincia / país
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos de la
75 956 5 Num C declarante - Porcentaje de participación
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos de la
76 961 17 Num C declarante - Valor nominal total de la participación
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos de la
77 978 17 Num C declarante - Valor en libros (en el activo de la declarante) de la participación
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos de la
78 995 17 Num C declarante - Ingresos por Dividendos recibidos en el ejercicio declarado
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Correcciones
79 1012 17 N C valorativas - Corrección de valor pérdidas y ganancias ejercicio
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Correcciones
80 1029 17 N C valorativas - Reversión de pérdidas por deterioro de valores
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Correcciones
81 1046 17 N C valorativas - Efecto corrección valorativa en la BI del ejercicio
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Corrrecciones
valorativas - Saldo de correcciones fiscales (art. 12.3 LIS) pendientes a fin de ejercicio
82 1063 17 N C
BB. PPaarrttiicciippaacciioonneess ddiirreeccttaass -- BB.11. PPaarrttiicciippaacciioonneess ddeeccllaarraannttee eenn oottrraass eennttiiddaaddeess -- EEnnttiiddaadd 33 -- DDaattooss aaddiicciioonnaalleess
83 1080 17 Num C participada - Capital
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos adicionales
84 1097 17 Num C participada - Reservas
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos adicionales
85 1114 17 N C participada - Otras partidas del patrimonio neto
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 3 - Datos adicionales
86 1131 17 N C participada - Resultado del último ejercicio
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos participada -
87 1148 15 An C N.I.F.
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos participada -
88 1163 30 An C Nombre o razón social
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos participada -
89 1193 2 An C Códiggo provincia / país
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos de la
90 1195 5 Num C declarante - Porcentaje de participación
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos de la
91 1200 17 Num C declarante - Valor nominal total de la participación
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos de la
92 1217 17 Num C declarante - Valor en libros (en el activo de la declarante) de la participación
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos de la
93 1234 17 Num C declarante - Ingresos por Dividendos recibidos en el ejercicio declarado
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Correcciones
94 1251 17 N C valorativas - Corrección de valor pérdidas y ganancias ejercicio
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Correcciones
95 1268 17 N C valorativas - Reversión de pérdidas por deterioro de valores
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Correcciones
9966 11228855 1177 NN CC vvaalloorraattiivvaass -- EEffeeccttoo ccoorrrreecccciióónn vvaalloorraattiivvaa eenn llaa BBII ddeell eejjeerrcciicciioo
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Correcciones
valorativas - Saldo de correcciones fiscales (art. 12.3 LIS) pendientes a fin de ejercicio
97 1302 17 N C
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos adicionales
98 1319 17 Num C participada - Capital
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos adicionales
99 1336 17 Num C participada - Reservas
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos adicionales
100 1353 17 N C participada - Otras partidas del patrimonio neto
B. Participaciones directas - B.1. Participaciones declarante en otras entidades - Entidad 4 - Datos adicionales
101 1370 17 N C participada - Resultado del último ejercicio
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - N.I.F.
102 1387 15 An C
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - RPTE.
103 1402 1 Num C ( "0", "1")
104 1403 1 A C B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - F/J "F" o "J"
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - Apellidos y
105 1404 37 An C nombre / Razón social
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - Código
106 1441 2 An C provincia / país
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - Nominal
107 1443 17 Num C
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 1 - % Particip.
108 1460 5 Num C
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - N.I.F.
109 1465 15 An C
BB. PPaarrttiicciippaacciioonneess ddiirreeccttaass - BB.22. PPaarrttiicciippaacciioonneess ddee ppeerrssoonnaass oo eennttiiddaaddeess eenn llaa ddeeccllaarraannttee - 22 - RRPPTTEE.
110 1480 1 Num C ( "0", "1")
111 1481 1 A C B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - F/J "F" o "J"
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - Apellidos y
112 1482 37 An C nombre / Razón social
Página 5

# Pag. 6

B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - Código
113 1519 2 An C provincia / país
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - Nominal
114 1521 17 Num C
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 2 - % Particip.
115 1538 5 Num C
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - N.I.F.
116 1543 15 An C
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - RPTE.
117 1558 1 Num C ( "0", "1")
118 1559 1 A C B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - F/J. "F" o "J"
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - Apellidos y
119 1560 37 An C nombre / Razón social
BB. PPaarrttiicciippaacciioonneess ddiirreeccttaass - BB.22. PPaarrttiicciippaacciioonneess ddee ppeerrssoonnaass oo eennttiiddaaddeess eenn llaa ddeeccllaarraannttee - 33 - CCóóddiiggoo
120 1597 2 An C provincia / país
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - Nominal
121 1599 17 Num C
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 3 - % Particip.
122 1616 5 Num C
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - N.I.F.
123 1621 15 An C
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - RPTE.
124 1636 1 Num C ( "0", "1")
125 1637 1 A C B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - F/J. "F" o "J"
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - Apellidos y
126 1638 37 An C nombre / Razón social
BB.. PPaarrttiicciippaacciioonneess ddiirreeccttaass - BB..22.. PPaarrttiicciippaacciioonneess ddee ppeerrssoonnaass oo eennttiiddaaddeess eenn llaa ddeeccllaarraannttee - 44 - CCóóddiiggoo
127 1675 2 An C provincia / país
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - Nominal
128 1677 17 Num C
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 4 - % Particip.
129 1694 5 Num C
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - N.I.F.
130 1699 15 An C
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - RPTE.
131 1714 1 Num C ( "0", "1")
132 1715 1 A C B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - F/J. "F" o "J"
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - Apellidos y
133 1716 37 An C nombre / Razón social.
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - Código
113344 11775533 22 AAn CC pprroovviinncciiaa // ppaaííss
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - Nominal
135 1755 17 Num C
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 5 - % Particip.
136 1772 5 Num C
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - N.I.F.
137 1777 15 An C
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - RPTE.
138 1792 1 Num C ( "0", "1")
139 1793 1 A C B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - F/J. "F" o "J"
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - Apellidos y
140 1794 37 An C nombre / Razón social
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - Código
114411 11883311 22 AAnn CC pprroovviinncciiaa // ppaaííss
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - Nominal
142 1833 17 Num C
B. Participaciones directas - B.2. Participaciones de personas o entidades en la declarante - 6 - % Particip.
143 1850 5 Num C
B .Participaciones directas - B.2. Suma de porcentajes de participación de personas o entidades en el capital
de la declarante inferiores al 5% o al 1% si se trata de valores que coticen en un mercado secundario
144 1855 5 Num organizado
B. Participaciones directas - B.2. Suma de porcentajes de participaciones en situaciones especiales
145 1860 5 Num
146 1865 10 An C Identificador de fin de Registro. OBLIGATORIO </T200020>
Total: 1874
Página 6

# Pag. 7

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas
vers. 1.0
constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "030"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN BBaallaannccee:: AAccttiivvoo ((II)) - AAccttiivvoo - AACCTTIIVVOO NNOO CCOORRRRIIEENNTTEE [[110011]]
7 28 17 N Balance: Activo (I) - Activo - Inmovilizado intangible [102]
8 45 17 N Balance: Activo (I) - Activo - Desarrollo [103]
9 62 17 N Balance: Activo (I) - Activo - Concesiones [104]
10 79 17 N Balance: Activo (I) - Activo - Patentes, licencias, marcas y similares [105]
11 96 17 N Balance: Activo (I) - Activo - Fondo de comercio [106]
12 113 17 N Balance: Activo (I) - Activo - Aplicaciones informáticas [107]
13 130 17 N Balance: Activo (I) - Activo - Investigación [108]
14 147 17 N Balance: Activo (I) - Activo - Propiedad intelectual [700]
15 164 17 N Balance: Activo (I) - Activo - Derechos de emisión de gases de efecto invernadero [701]
16 181 17 N Balance: Activo (I) - Activo - Otro inmovilizado intangible [109]
17 198 17 N Balance: Activo (I) - Activo - Resto [110]
1188 221155 1177 NN BBaallaannccee:: AAccttiivvoo ((II)) - AAccttiivvoo - IInnmmoovviilliizzaaddoo mmaatteerriiaall [[111111]]
19 232 17 N Balance: Activo (I) - Activo - Terrenos y construcciones [112]
20 249 17 N Balance: Activo (I) - Activo - Instalaciones técnicas y otro inmovilizado material [113]
21 266 17 N Balance: Activo (I) - Activo - Inmovilizado en curso y anticipos [114]
22 283 17 N Balance: Activo (I) - Activo - Inversiones inmobiliarias [115]
23 300 17 N Balance: Activo (I) - Activo - Terrenos [116]
24 317 17 N Balance: Activo (I) - Activo - Construcciones [117]
25 334 17 N Balance: Activo (I) - Activo - Inversiones en empresas del grupo y asociadas [118]
26 351 17 N Balance: Activo (I) - Activo - Instrumentos de patrimonio [119]
27 368 17 N Balance: Activo (I) - Activo - Créditos a empresas [120]
28 385 17 N Balance: Activo (I) - Activo - Valores representativos de deuda [121]
29 402 17 N Balance: Activo (I) - Activo - Derivados [122]
30 419 17 N Balance: Activo (I) - Activo - Otros activos financieros [123]
31 436 17 N Balance: Activo (I) - Activo - Otras inversiones [124]
32 453 17 N Balance: Activo (I) - Activo - Resto [125]
33 470 17 N Balance: Activo (I) - Activo - Inversiones financieras a largo plazo [126]
34 487 17 N Balance: Activo (I) - Activo - Instrumentos de patrimonio [127]
35 504 17 N Balance: Activo (I) - Activo - Créditos a terceros [128]
36 521 17 N Balance: Activo (I) - Activo - Valores representativos de deuda [129]
37 538 17 N Balance: Activo (I) - Activo - Derivados [130]
38 555 17 N Balance: Activo (I) - Activo - Otros activos financieros [131]
39 572 17 N Balance: Activo (I) - Activo - Otras inversiones [132]
40 589 17 N Balance: Activo (I) - Activo - Resto [133]
41 606 17 N Balance: Activo (I) - Activo - Activos por impuesto diferido [134]
42 623 17 N Balance: Activo (I) - Activo - Deudores comerciales no corrientes [135]
4433 664400 1177 NN BBaallaannccee:: AAccttiivvoo ((II)) -- AAccttiivvoo -- AACCTTIIVVOO CCOORRRRIIEENNTTEE [[113366]]
44 657 17 N Balance: Activo (I) - Activo - Activos no corrientes mantenidos para la venta [137]
45 674 17 N Balance: Activo (I) - Activo - Existencias [138]
46 691 17 N Balance: Activo (I) - Activo - Comerciales [139]
47 708 17 N Balance: Activo (I) - Activo - Materias primas y otros aprovisionamientos [140]
48 725 17 N Balance: Activo (I) - Activo - Productos en curso [141]
49 742 17 N Balance: Activo (I) - Activo - Productos en curso - De ciclo largo de producción [142]
50 759 17 N Balance: Activo (I) - Activo - Productos en curso - De ciclo corto de producción [143]
51 776 17 N Balance: Activo (I) - Activo - Productos terminados [144]
52 793 17 N Balance: Activo (I) - Activo - Productos terminados - De ciclo largo de producción [145]
53 810 17 N Balance: Activo (I) - Activo - Productos terminados - De ciclo corto de producción [146]
54 827 17 N Balance: Activo (I) - Activo - Subproductos, residuos y materiales recuperados [147]
55 844 17 N Balance: Activo ((I)) - Activo - Anticippos a pproveedores [[148]]
56 861 10 An Identificador de fin de registro OBLIGATORIO Constante </T200030>
Total: 870
Página 7

# Pag. 8

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. Constante "<T" . OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "040"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria. En blanco En blanco
66 1111 1177 NN BBaallaannccee:: AAccttiivvoo ((IIII)) - AAccttiivvoo - DDeeuuddoorreess ccoommeerrcciiaalleess yy oottrraass ccuueennttaass aa ccoobbrraarr [[114499]]
7 28 17 N Balance: Activo (II) - Activo - Clientes por ventas y prestaciones de servicios [150]
Balance: Activo (II) - Activo - Clientes por ventas y prestaciones de servicios - Clientes por ventas y prestaciones de
8 45 17 N servicios a largo plazo [151]
Balance: Activo (II) - Activo - Clientes por ventas y prestaciones de servicios - Clientes por ventas y prestaciones de
9 62 17 N servicios a corto plazo [152]
10 79 17 N Balance: Activo (II) - Activo - Clientes empresas del grupo y asociadas [153]
11 96 17 N Balance: Activo (II) - Activo - Deudores varios [154]
12 113 17 N Balance: Activo (II) - Activo - Personal [155]
13 130 17 N Balance: Activo (II) - Activo - Activos por impuesto corriente [156]
14 147 17 N Balance: Activo (II) - Activo - Otros créditos con las Administraciones Públicas [157]
15 164 17 N Balance: Activo (II) - Activo - Accionistas (socios) por desembolsos exigidos [158]
16 181 17 N Balance: Activo (II) - Activo - Otros deudores [159]
1177 119988 1177 NN BBaallaannccee:: AAccttiivvoo ((IIII)) -- AAccttiivvoo -- IInnvveerrssiioonneess eenn eemmpprreessaass ddeell ggrruuppoo yy aassoocciiaaddaass aa ccoorrttoo ppllaazzoo [[116600]]
18 215 17 N Balance: Activo (II) - Activo - Instrumentos de patrimonio [161]
19 232 17 N Balance: Activo (II) - Activo - Créditos a empresas [162]
20 249 17 N Balance: Activo (II) - Activo - Valores representativos de deuda [163]
21 266 17 N Balance: Activo (II) - Activo - Derivados [164]
22 283 17 N Balance: Activo (II) - Activo - Otros activos financieros [165]
23 300 17 N Balance: Activo (II) - Activo - Otras inversiones [166]
24 317 17 N Balance: Activo (II) - Activo - Resto [167]
25 334 17 N Balance: Activo (II) - Activo - Inversiones financieras a corto plazo [168]
26 351 17 N Balance: Activo (II) - Activo - Instrumentos de patrimonio [169]
27 368 17 N Balance: Activo (II) - Activo - Créditos a empresas [170]
28 385 17 N Balance: Activo (II) - Activo - Valores representativos de deuda [171]
29 402 17 N Balance: Activo (II) - Activo - Derivados [172]
30 419 17 N BBallance: AActtiivo ((IIII)) - AActtiivo - OOttros acttiivos ffiinanciieros [[117733]]
31 436 17 N Balance: Activo (II) - Activo - Otras inversiones [174]
32 453 17 N Balance: Activo (II) - Activo - Resto [175]
33 470 17 N Balance: Activo (II) - Activo - Periodificaciones a corto plazo [176]
34 487 17 N Balance: Activo (II) - Activo - Efectivo y otros activos líquidos equivalentes [177]
35 504 17 N Balance: Activo (II) - Activo - Tesorería [178]
36 521 17 N Balance: Activo (II) - Activo - Otros activos líquidos equivalentes [179]
37 538 17 N Balance: Activo (II) - Activo - TOTAL ACTIVO [180]
38 555 10 An Identificador de fin de registro OBLIGATORIO Constante </T200040>
Total: 564
Página 8

# Pag. 9

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "050"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN BBaallaannccee:: PPaattrriimmoonniioo nneettoo yy ppaassiivvoo ((II)) -- PPaattrriimmoonniioo nneettoo yy ppaassiivvoo -- PPAATTRRIIMMOONNIIOO NNEETTOO [[118855]]
7 28 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Fondos propios [186]
8 45 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Capital [187]
9 62 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Capital escriturado [188]
10 79 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Capital no exigido [189]
11 96 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Prima de emisión [190]
12 113 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Reservas [191]
13 130 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Legal y estatutarias [192]
14 147 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otras reservas [193]
15 164 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Reserva de revalorización [702]
Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Acciones y participaciones en patrimonio propias
16 181 17 N [194]
17 198 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Resultados de ejercicios anteriores [195]
1188 221155 1177 NN BBaallaannccee:: PPaattrriimmoonniioo nneettoo yy ppaassiivvoo ((II)) -- PPaattrriimmoonniioo nneettoo yy ppaassiivvoo -- RReemmaanneennttee [[119966]]
19 232 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Resultados negativos de ejercicios anteriores [197]
20 249 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otras aportaciones de socios [198]
21 266 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Resultado del ejercicio [199]
22 283 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Dividendo a cuenta [200]
23 300 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otros instrumentos de patrimonio neto [201]
24 317 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Ajustes por cambios de valor [202]
25 334 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Activos financieros disponibles para la venta [203]
26 351 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Operaciones de cobertura [204]
2277 336688 1177 NN BBaallaannccee:: PPaattrriimmoonniioo nneettoo yy ppaassiivvoo ((II)) -- PPaattrriimmoonniioo nneettoo yy ppaassiivvoo -- AAccttiivvooss nnoo ccoorrrriieenntteess yy ppaassiivvooss vviinnccuullaaddooss [[220055]]
28 385 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Diferencia de conversión [206]
29 402 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otros [207]
30 419 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Ajustes en patrimonio neto [208]
Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Subvenciones, donaciones y legados recibidos
31 436 17 N [209]
32 453 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - PASIVO NO CORRIENTE [210]
33 470 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Provisiones a largo plazo [211]
Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Obligaciones por prestaciones a largo plazo al
34 487 17 N personal [212]
35 504 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Actuaciones medioambientales [213]
36 521 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Provisiones por reestructuración [214]
37 538 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otras provisiones [215]
3388 555555 1177 NN BBaallaannccee:: PPaattrriimmoonniioo nneettoo yy ppaassiivvoo ((II)) -- PPaattrriimmoonniioo nneettoo yy ppaassiivvoo -- DDeeuuddaass aa llaarrggoo ppllaazzoo [[221166]]
39 572 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Obligaciones y otros valores negociables [217]
40 589 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Deudas con entidades de crédito [218]
41 606 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Acreedores por arrendamiento financiero [219]
42 623 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Derivados [220]
43 640 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otros pasivos financieros [221]
44 657 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Otras deudas a largo plazo [222]
Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Deudas con empresas del grupo y asociadas a
45 674 17 N largo plazo [223]
46 691 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Pasivos por impuesto diferido [224]
47 708 17 N Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Periodificaciones a largo plazo [225]
4488 772255 1177 NN BBaallaannccee:: PPaattrriimmoonniioo nneettoo yy ppaassiivvoo ((II)) -- PPaattrriimmoonniioo nneettoo yy ppaassiivvoo -- AAccrreeeeddoorreess ccoommeerrcciiaalleess nnoo ccoorrrriieenntteess [[222266]]
Balance: Patrimonio neto y pasivo (I) - Patrimonio neto y pasivo - Deuda con características especiales a largo plazo
49 742 17 N [227]
50 759 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200050>"
Total: 768
Página 9

# Pag. 10

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "060"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN BBaallaannccee:: PPaattrriimmoonniioo nneettoo yy ppaassiivvoo ((IIII)) -- PPaattrriimmoonniioo nneettoo yy ppaassiivvoo -- PPAASSIIVVOO CCOORRRRIIEENNTTEE [[222288]]
7 28 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Pasivos vinculados con activos no corrientes [229]
8 45 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Provisiones a corto plazo [230]
Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Provisiones por derechos emisión de gases de
9 62 17 N efecto invernadero [703]
10 79 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Otras provisiones [704]
11 96 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Deudas a corto plazo [231]
12 113 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Obligaciones y otros valores negociables [232]
13 130 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Deudas con entidades de crédito [233]
14 147 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Acreedores por arrendamiento financiero [234]
1155 116644 1177 NN Balance: Patrimonio neto yy ppasivo ((II)) - Patrimonio neto yy ppasivo - Derivados [[235]]
16 181 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Otros pasivos financieros [236]
17 198 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Otras deudas a corto plazo [237]
Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Deudas con empresas del grupo y asociadas a
18 215 17 N corto plazo [238]
Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Acreedores comerciales y otras cuentas a pagar
19 232 17 N [239]
20 249 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Proveedores [240]
21 266 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Proveedores - Proveedores a largo plazo [241]
22 283 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Proveedores - Proveedores a corto plazo [242]
Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Proveedores, empresas del grupo y asociadas
23 300 17 N [243]
24 317 17 N Balance: Patrimonio neto y pasivo ((II)) - Patrimonio neto y pasivo - Acreedores varios [244]
Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Personal (remuneraciones pendientes de pago)
25 334 17 N [245]
26 351 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Pasivos por impuesto corriente [246]
Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Otras deudas con las Administraciones Públicas
27 368 17 N [247]
28 385 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Anticipos de clientes [248]
29 402 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Otros acreedores [249]
30 419 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Periodificaciones a corto plazo [250]
Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - Deuda con características especiales a corto plazo
31 436 17 N [251]
32 453 17 N Balance: Patrimonio neto y pasivo (II) - Patrimonio neto y pasivo - TOTAL PATRIMONIO NETO Y PASIVO [252]
3333 447700 1100 AAn IIddenttiiffiicaddor dde ffiin dde regiisttro OOBBLLIIGGAATTOORRIIOO CConsttantte ""<//TT220000006600>""
Total: 479
Página 10

# Pag. 11

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "070"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN CCuueennttaa ddee ppéérrddiiddaass yy ggaannaanncciiaass ((II)) - OOppeerraacciioonneess ccoonnttiinnuuaaddaass - IImmppoorrttee nneettoo ddee llaa cciiffrraa ddee nneeggoocciiooss [[225555]]
7 28 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ventas [256]
8 45 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Prestaciones de servicios [257]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ingresos carácter financiero sociedades holding
9 62 17 N [705]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ingresos carácter financiero sociedades holding -
10 79 17 N De participaciones en instrumentos patrimonio [706]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ingresos carácter financiero sociedades holding -
11 96 17 N De valores negociables y otros instrumentos financieros [707]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ingresos carácter financiero sociedades holding -
12 113 17 N Resto [708]
13 130 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Variación de existencias [258]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Trabajos realizados por la empresa para su activo
1144 114477 1177 NN [[225599]]
15 164 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Aprovisionamientos [260]
16 181 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Consumo de mercaderías [261]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Consumo de materias primas y otras materias
17 198 17 N consumibles [262]
18 215 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Trabajos realizados por otras empresas [263]
19 232 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro de mercaderías, materias primas [264]
20 249 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Otros ingresos de explotación [265]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ingresos accesorios y otros de gestión corriente
21 266 17 N [266]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ingresos accesorios y otros de gestión corriente -
2222 228833 1177 NN IInnggrreessooss aarrrreennddaammiieennttooss [[226677]]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Ingresos accesorios y otros de gestión corriente -
23 300 17 N Resto [268]
24 317 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Subvenciones de explotación [269]
25 334 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Gastos de personal [270]
26 351 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Sueldos, salarios y asimilados [271]
27 368 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Indemnizaciones [273]
28 385 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Seguridad Social a cargo de la empresa [274]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Retribuciones a largo plazo por sistemas de
29 402 17 N aportación [275]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Retribuciones mediante instrumentos de
30 419 17 N patrimonio [276]
3311 443366 1177 NN CCuentta dde péérddiiddas y gananciias ((II)) - OOperaciiones conttiinuaddas - OOttros gasttos sociialles [[227777]]
32 453 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Provisiones [278]
33 470 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Otros gastos de explotación [279]
34 487 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Servicios exteriores [280]
35 504 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Tributos [281]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Pérdidas, deterioro y variación de provisiones por
36 521 17 N operaciones comerciales [282]
37 538 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Otros gastos de gestión corriente [283]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Gastos por emisión de gases de efecto
38 555 17 N invernadero [709]
39 572 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Amortización del inmovilizado [284]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Imputación de subvenciones de inmovilizado no
40 589 17 N financiero yy otras [[285]]
41 606 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Excesos de provisiones [286]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro y resultado por enajenaciones del
42 623 17 N inmovilizado [287]
43 640 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro y pérdidas [288]
44 657 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro y pérdidas - Deterioros [289]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro y pérdidas - Reversión de deterioros
45 674 17 N [290]
46 691 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Resultados por enajenaciones y otras [291]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Resultados por enajenaciones y otras - Beneficios
47 708 17 N [292]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Resultados por enajenaciones y otras - Pérdidas
48 725 17 N [[293]]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Deterioro y resultados por enajenaciones del
49 742 17 N inmovilizado de las sociedades holding [710]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Diferencia negativa de combinaciones de negocio
50 759 17 N [294]
51 776 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - Otros resultados [295]
52 793 17 N Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - RESULTADO DE EXPLOTACION [296]
53 810 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200070>"
Total: 819
Página 11

# Pag. 12

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "080"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN CCuueennttaa ddee ppéérrddiiddaass yy ggaannaanncciiaass ((II)) - OOppeerraacciioonneess ccoonnttiinnuuaaddaass - IInnggrreessooss ffiinnaanncciieerrooss [[229977]]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De participaciones en instrumentos de patrimonio
7 28 17 N [298]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De participaciones en instrumentos de patrimonio -
8 45 17 N En empresas del grupo y asociadas [299]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De participaciones en instrumentos de patrimonio -
9 62 17 N En terceros [300]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De valores negociables y otros instrumentos
10 79 17 N financieros [301]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De valores negociables y otros instrumentos
11 96 17 N financieros - De empresas del grupo y asociadas [302]
Cuenta de pérdidas y ganancias (I) - Operaciones continuadas - De valores negociables y otros instrumentos
12 113 17 N financieros - De terceros [303]
CCuueennttaa ddee ppéérrddiiddaass yy ggaannaanncciiaass ((II)) -- OOppeerraacciioonneess ccoonnttiinnuuaaddaass -- IImmppuuttaacciióónn ddee ssuubbvveenncciioonneess, ddoonnaacciioonneess yy
13 130 17 N legados [304]
14 147 17 N Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Gastos financieros [305]
Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Por deudas con empresas del grupo y asociadas
15 164 17 N [306]
16 181 17 N Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Por deudas con terceros [307]
17 198 17 N Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Por actualización de provisiones [308]
Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Variación de valor razonable en instrumentos
18 215 17 N financieros [309]
19 232 17 N Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Cartera de negociación y otros [310]
Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Imputación por activos financieros disponibles
20 249 17 N para la venta [311]
21 266 17 N Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Diferencias de cambio [312]
CCuueennttaa ddee ppéérrddiiddaass yy ggaannaanncciiaass ((IIII)) - OOppeerraacciioonneess ccoonnttiinnuuaaddaass - DDeetteerriioorroo yy rreessuullttaaddoo ppoorr eennaajjeennaacciioonneess ddee
22 283 17 N instrumentos financieros [313]
23 300 17 N Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioros y pérdidas [314]
Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioros y pérdidas - Deterioros, empresas del
24 317 17 N grupo, asociadas y vinculadas [315]
Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioros y pérdidas - Deterioros, otras
25 334 17 N empresas [316]
Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioros y pérdidas - Reversión de deterioros,
26 351 17 N empresas del grupo, asociadas y vinculadas [317]
Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Deterioros y pérdidas - Reversión de deterioros,
27 368 17 N otras empresas [318]
28 385 17 N Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resultados por enajenaciones y otras [319]
CCuueennttaa ddee ppéérrddiiddaass yy ggaannaanncciiaass ((IIII)) -- OOppeerraacciioonneess ccoonnttiinnuuaaddaass -- RReessuullttaaddooss ppoorr eennaajjeennaacciioonneess yy oottrraass --
29 402 17 N Beneficios, empresas del grupo, asociadas y vinculadas [320]
Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resultados por enajenaciones y otras -
30 419 17 N Beneficios, otras empresas [321]
Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resultados por enajenaciones y otras - Pérdidas,
31 436 17 N empresas del grupo, asociadas y vinculadas [322]
Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resultados por enajenaciones y otras - Pérdidas,
32 453 17 N otras empresas [323]
Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Otros ingresos y gastos de carácter financiero
33 470 17 N [329]
Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Incorporación al activo de gastos financieros
34 487 17 N [330]
Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Ingresos financieros derivados de convenios de
3355 550044 1177 NN aaccrreeeeddoorreess [[333311]]
36 521 17 N Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Resto de ingresos y gastos [332]
37 538 17 N Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - RESULTADO FINANCIERO [324]
38 555 17 N Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - RESULTADO ANTES DE IMPUESTOS [325]
39 572 17 N Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - Impuestos sobre beneficios [326]
Cuenta de pérdidas y ganancias (II) - Operaciones continuadas - RESULTADO DEL EJERCICIO PROCEDENTE
40 589 17 N DE OPERACIONES CONTINUADAS [327]
Cuenta de pérdidas y ganancias (II) - Operaciones interrumpidas - RESULTADO DEL EJERCICIO PROCEDENTE
41 606 17 N DE OPERACIONES INTERRUMPIDAS NETO DE IMPUESTOS [328]
Cuenta de pérdidas y ganancias (II) - Operaciones interrumpidas - RESULTADO DE LA CUENTA DE PÉRDIDAS
42 623 17 N Y GANANCIAS [500]
43 640 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200080>"
TToottaall:: 664499
Página 12

# Pag. 13

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "090"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((II)) - RReessuullttaaddoo ddee llaa ccuueennttaa ddee ppéérrddiiddaass yy ggaannaanncciiaass [[550000]]
Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Por valoración de
7 28 17 N instrumentos financieros [336]
Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Activos financieros
8 45 17 N disponibles para la venta [337]
Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Otros ingresos/gastos
9 62 17 N [338]
Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Por coberturas de flujos
10 79 17 N de efectivo [339]
Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Subvenciones,
11 96 17 N donaciones y legados recibidos [340]
Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Por ganancias y pérdidas
12 113 17 N actuariales [341]
EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((II)) -- IInnggrreessooss yy ggaassttooss iimmppuuttaaddooss aall ppaattrriimmoonniioo nneettoo -- PPoorr aaccttiivvooss nnoo ccoorrrriieenntteess
13 130 17 N y pasivos vinculados [342]
Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Diferencias de
14 147 17 N conversión [343]
15 164 17 N Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Efecto impositivo [344]
Estado de cambios patrimonio neto (I) - Ingresos y gastos imputados al patrimonio neto - Total ingresos y gastos
16 181 17 N imputados en el patrimonio neto [345]
Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Por valoración de
17 198 17 N instrumentos financieros [346]
Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Activos financieros
18 215 17 N disponibles para la venta [347]
1199 223322 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((II)) - TTrraannssffeerreenncciiaass aa llaa ccttaa. ppéérrddiiddaass yy ggaannaanncciiaass - OOttrrooss iinnggrreessooss//ggaassttooss [[334488]]
Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Por coberturas de flujos de
20 249 17 N efectivo [349]
Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Subvenciones, donaciones
21 266 17 N y legados recibidos [350]
Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Por activos no corrientes y
22 283 17 N pasivos vinculados [351]
Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Diferencias de conversión
23 300 17 N [352]
24 317 17 N Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Efecto impositivo [353]
Estado de cambios patrimonio neto (I) - Transferencias a la cta. pérdidas y ganancias - Total transferencia a la
25 334 17 N cuenta de pérdidas y ganancias [354]
EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((II)) -- TTrraannssffeerreenncciiaass aa llaa ccttaa. ppéérrddiiddaass yy ggaannaanncciiaass -- TTOOTTAALL DDEE IINNGGRREESSOOSS YY
26 351 17 N GASTOS RECONOCIDOS [355]
27 368 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200090>"
Total: 377
Página 13

# Pag. 14

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "100"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIII)) - SSaallddoo, ffiinnaall ddeell eejjeerrcciicciioo aanntteerriioorr - CCaappiittaall - EEssccrriittuurraaddoo [[338800]]
7 28 17 N Estado de cambios patrimonio neto (II) - Saldo, final del ejercicio anterior - Capital - No exigido [381]
8 45 17 N Estado de cambios patrimonio neto (II) - Saldo, final del ejercicio anterior - Prima de emisión [382]
9 62 17 N Estado de cambios patrimonio neto (II) - Saldo, final del ejercicio anterior - Reservas [383]
Estado de cambios patrimonio neto (II) - Saldo, final del ejercicio anterior - Acciones y participaciones propias
10 79 17 N [384]
11 96 17 N Estado de cambios patrimonio neto (II) - Saldo, final del ejercicio anterior - Resultados ejercicios anteriores [385]
12 113 17 N Estado de cambios patrimonio neto (II) - Saldo, final del ejercicio anterior - Otras aportaciones socios [386]
Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Capital -
13 130 17 N Escriturado [394]
Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Capital - No
1144 114477 1177 NN eexxiiggiiddoo [[339955]]
Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Prima de emisión
15 164 17 N [396]
16 181 17 N Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Reservas [397]
Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Acciones y
17 198 17 N participaciones propias [398]
Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Resultados
18 215 17 N ejercicios anteriores [399]
Estado de cambios patrimonio neto (II) - Ajustes por cambio de criterio de ejercicios anteriores - Otras
19 232 17 N aportaciones socios [400]
20 249 17 N Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Capital - Escriturado [408]
21 266 17 N Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Capital - No exigido [409]
22 283 17 N Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Prima de emisión [410]
23 300 17 N Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Reservas [411]
Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Acciones y participaciones
24 317 17 N propias [412]
Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Resultados ejercicios
25 334 17 N anteriores [413]
Estado de cambios patrimonio neto (II) - Ajustes por errores de ejercicios anteriores - Otras aportaciones socios
26 351 17 N [414]
27 368 17 N Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Capital - Escriturado [422]
28 385 17 N Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Capital - No exigido [423]
2299 440022 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIII)) - SSaallddoo aajjuussttaaddoo, iinniicciioo ddeell eejjeerrcciicciioo - PPrriimmaa ddee eemmiissiióónn [[442244]]
30 419 17 N Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Reservas [425]
Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Acciones y participaciones propias
31 436 17 N [426]
32 453 17 N Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Resultados ejercicios anteriores [427]
33 470 17 N Estado de cambios patrimonio neto (II) - Saldo ajustado, inicio del ejercicio - Otras aportaciones socios [428]
34 487 17 N Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Capital - Escriturado [436]
35 504 17 N Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Capital - No exigido [437]
36 521 17 N Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Prima de emisión [438]
37 538 17 N Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Reservas [439]
EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIII)) - TToottaall iinnggrreessooss yy ggaassttooss rreeccoonnoocciiddooss - AAcccciioonneess yy ppaarrttiicciippaacciioonneess pprrooppiiaass
38 555 17 N [440]
Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Resultados ejercicios anteriores
39 572 17 N [441]
40 589 17 N Estado de cambios patrimonio neto (II) - Total ingresos y gastos reconocidos - Otras aportaciones socios [442]
41 606 17 N Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Capital - Escriturado [450]
42 623 17 N Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Capital - No exigido [451]
43 640 17 N Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Prima de emisión [452]
44 657 17 N Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Reservas [453]
Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Acciones y participaciones
45 674 17 N propias [454]
Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Resultados ejercicios anteriores
4466 669911 1177 NN [[445555]]
47 708 17 N Estado de cambios patrimonio neto (II) - Resultado cuenta pérdidas y ganancias - Otras aportaciones socios [456]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Capital - Escriturado
48 725 17 N [464]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Capital - No exigido
49 742 17 N [465]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Prima de emisión
50 759 17 N [466]
51 776 17 N Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Reservas [467]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Acciones y
52 793 17 N participaciones propias [468]
EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIII)) - IInnggrreessooss yy ggaassttooss rreeccoonnoocciiddooss eenn ppaattrriimmoonniioo nneettoo - RReessuullttaaddooss eejjeerrcciicciiooss
53 810 17 N anteriores [469]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otras aportaciones
54 827 17 N socios [470]
Página 14

# Pag. 15

Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a
55 844 17 N distribuir en varios ejercicios - Capital - Escriturado [478]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a
56 861 17 N distribuir en varios ejercicios - Capital - No exigido [479]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a
57 878 17 N distribuir en varios ejercicios - Prima de emisión [480]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a
58 895 17 N distribuir en varios ejercicios - Reservas [481]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a
59 912 17 N distribuir en varios ejercicios - Acciones y participaciones propias [482]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a
60 929 17 N distribuir en varios ejercicios - Resultados ejercicios anteriores [483]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a
6611 994466 117 NN ddiisttriibbuiir en variios ejjerciiciios - OOttras aporttaciiones sociios [[448844]]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y
62 963 17 N gastos reconocidos en patrimonio neto - Capital - Escriturado [492]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y
63 980 17 N gastos reconocidos en patrimonio neto - Capital - No exigido [493]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y
64 997 17 N gastos reconocidos en patrimonio neto - Prima de emisión [494]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y
65 1014 17 N gastos reconocidos en patrimonio neto - Reservas [495]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y
66 1031 17 N gastos reconocidos en patrimonio neto - Acciones y participaciones propias [496]
Estado de cambios patrimonio neto (II) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y
67 1048 17 N gastos reconocidos en patrimonio neto - Resultados ejercicios anteriores [497]
EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIII)) - IInnggrreessooss yy ggaassttooss rreeccoonnoocciiddooss eenn ppaattrriimmoonniioo nneettoo - OOttrrooss iinnggrreessooss yy
68 1065 17 N gastos reconocidos en patrimonio neto - Otras aportaciones socios [498]
69 1082 17 N Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Capital - Escriturado [506]
70 1099 17 N Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Capital - No exigido [507]
71 1116 17 N Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Prima de emisión [508]
72 1133 17 N Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Reservas [509]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Acciones y participaciones
73 1150 17 N propias [510]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Resultados ejercicios anteriores
74 1167 17 N [511]
75 1184 17 N Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras aportaciones socios [512]
EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIII)) - OOppeerraacciioonneess ccoonn ssoocciiooss oo pprrooppiieettaarriiooss - AAuummeennttooss ddee ccaappiittaall - CCaappiittaall -
76 1201 17 N Escriturado [520]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Capital -
77 1218 17 N No exigido [521]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Prima de
78 1235 17 N emisión [522]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Reservas
79 1252 17 N [523]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Acciones y
80 1269 17 N participaciones propias [524]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Resultados
81 1286 17 N ejercicios anteriores [525]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Aumentos de capital - Otras
8822 11330033 1177 NN aappoorrttaacciioonneess ssoocciiooss [[552266]]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital -
83 1320 17 N Capital - Escriturado [534]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital -
84 1337 17 N Capital - No exigido [535]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital -
85 1354 17 N Prima de emisión [536]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital -
86 1371 17 N Reservas [537]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital -
87 1388 17 N Acciones y participaciones propias [538]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Reducciones de capital -
88 1405 17 N Resultados ejercicios anteriores [539]
EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIII)) -- OOppeerraacciioonneess ccoonn ssoocciiooss oo pprrooppiieettaarriiooss -- ((--)) RReedduucccciioonneess ddee ccaappiittaall -- OOttrraass
89 1422 17 N aportaciones socios [540]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim.
90 1439 17 N neto - Capital - Escriturado [548]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim.
91 1456 17 N neto - Capital - No exigido [549]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim.
92 1473 17 N neto - Prima de emisión [550]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim.
93 1490 17 N neto - Reservas [551]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim.
94 1507 17 N neto - Acciones y participaciones propias [552]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim.
9955 11552244 1177 NN nneettoo - RReessuullttaaddooss eejjeerrcciicciiooss aanntteerriioorreess [[555533]]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Conversión de pasivos en patrim.
96 1541 17 N neto - Otras aportaciones socios [554]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos -
97 1558 17 N Capital - Escriturado [562]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos -
98 1575 17 N Capital - No exigido [563]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos -
99 1592 17 N Prima de emisión [564]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos -
100 1609 17 N Reservas [565]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos -
101 1626 17 N Acciones y participaciones propias [566]
Estado de cambios ppatrimonio neto ((II)) - Opperaciones con socios o pproppietarios - ((-)) Distribución de dividendos -
102 1643 17 N Resultados ejercicios anteriores [567]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - (-) Distribución de dividendos -
103 1660 17 N Otras aportaciones socios [568]
Página 15

# Pag. 16

Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o
104 1677 17 N participaciones propias - Capital - Escriturado [576]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o
105 1694 17 N participaciones propias - Capital - No exigido [577]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o
106 1711 17 N participaciones propias - Prima de emisión [578]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o
107 1728 17 N participaciones propias - Reservas [579]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o
108 1745 17 N participaciones propias - Acciones y participaciones propias [580]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o
109 1762 17 N participaciones propias - Resultados ejercicios anteriores [581]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Operaciones con acciones o
111100 117799 117 NN parttiiciipaciiones propiias - OOttras aporttaciiones sociios [[558822]]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr.
111 1796 17 N neto de combinación de negocios - Capital - Escriturado [590]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr.
112 1813 17 N neto de combinación de negocios - Capital - No exigido [591]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr.
113 1830 17 N neto de combinación de negocios - Prima de emisión [592]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr.
114 1847 17 N neto de combinación de negocios - Reservas [593]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr.
115 1864 17 N neto de combinación de negocios - Acciones y participaciones propias [594]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Incremento (reducción) de patr.
116 1881 17 N neto de combinación de negocios - Resultados ejercicios anteriores [595]
EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIII)) - OOppeerraacciioonneess ccoonn ssoocciiooss oo pprrooppiieettaarriiooss - IInnccrreemmeennttoo ((rreedduucccciióónn)) ddee ppaattrr.
117 1898 17 N neto de combinación de negocios - Otras aportaciones socios [596]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o
118 1915 17 N propietarios - Capital - Escriturado [604]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o
119 1932 17 N propietarios - Capital - No exigido [605]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o
120 1949 17 N propietarios - Prima de emisión [606]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o
121 1966 17 N propietarios - Reservas [607]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o
122 1983 17 N propietarios - Acciones y participaciones propias [608]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o
112233 22000000 1177 NN pprrooppiieettaarriiooss -- RReessuullttaaddooss eejjeerrcciicciiooss aanntteerriioorreess [[660099]]
Estado de cambios patrimonio neto (II) - Operaciones con socios o propietarios - Otras operaciones con socios o
124 2017 17 N propietarios - Otras aportaciones socios [610]
125 2034 17 N Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Capital - Escriturado [618]
126 2051 17 N Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Capital - No exigido [619]
127 2068 17 N Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Prima de emisión [620]
128 2085 17 N Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Reservas [621]
Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Acciones y participaciones propias
129 2102 17 N [622]
Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Resultados ejercicios anteriores
130 2119 17 N [623]
131 2136 17 N Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras aportaciones socios [624]
EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIII)) - OOttrraass vvaarriiaacciioonneess ddeell ppaattrriimmoonniioo nneettoo - MMoovviimmiieennttoo rreesseerrvvaa rreevvaalloorriizzaacciióónn -
132 2153 17 N Capital - Escriturado [715]
Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización -
133 2170 17 N Capital - No exigido [716]
Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización -
134 2187 17 N Prima de emisión [717]
Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización -
135 2204 17 N Reservas [718]
Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización -
136 2221 17 N Acciones y participaciones propias [719]
Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización -
137 2238 17 N Resultados ejercicios anteriores [720]
Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización -
113388 22225555 1177 NN OOttrraass aappoorrttaacciioonneess ssoocciiooss [[772211]]
Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones - Capital -
139 2272 17 N Escriturado [729]
Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones - Capital - No
140 2289 17 N exigido [730]
Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones - Prima de
141 2306 17 N emisión [731]
Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones - Reservas
142 2323 17 N [732]
Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones - Acciones y
143 2340 17 N participaciones propias [733]
Estado de cambios patrimonio neto (II) - Otras variaciones del patrimonio neto - Otras variaciones - Resultados
144 2357 17 N ejercicios anteriores [734]
EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIII)) - OOttrraass vvaarriiaacciioonneess ddeell ppaattrriimmoonniioo nneettoo - OOttrraass vvaarriiaacciioonneess - OOttrraass
145 2374 17 N aportaciones socios [735]
146 2391 17 N Estado de cambios patrimonio neto (II) - Saldo, final ejercicio - Capital - Escriturado [632]
147 2408 17 N Estado de cambios patrimonio neto (II) - Saldo, final ejercicio - Capital - No exigido [633]
148 2425 17 N Estado de cambios patrimonio neto (II) - Saldo, final ejercicio - Prima de emisión [634]
149 2442 17 N Estado de cambios patrimonio neto (II) - Saldo, final ejercicio - Reservas [635]
150 2459 17 N Estado de cambios patrimonio neto (II) - Saldo, final ejercicio - Acciones y participaciones propias [636]
151 2476 17 N Estado de cambios patrimonio neto (II) - Saldo, final ejercicio - Resultados ejercicios anteriores [637]
152 2493 17 N Estado de cambios patrimonio neto (II) - Saldo, final ejercicio - Otras aportaciones socios [638]
153 2510 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200100>"
Total: 2519
Página 16

# Pag. 17

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "110"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIIIII)) - SSaallddoo ffiinnaall ddeell eejjeerrcciicciioo aanntteerriioorr - RReessuullttaaddoo ddeell eejjeerrcciicciioo [[338877]]
7 28 17 N Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Dividendo a cuenta [388]
Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Otros instrumentos patrimonio neto
8 45 17 N [389]
9 62 17 N Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Ajustes por cambios de valor [390]
10 79 17 N Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Ajustes en patrimonio neto [391]
Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Subvenciones, donaciones y legados
11 96 17 N recibidos [392]
12 113 17 N Estado de cambios patrimonio neto (III) - Saldo final del ejercicio anterior - Total [393]
Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Resultado del
13 130 17 N ejercicio [401]
EEsttaddo dde cambbiios pattriimoniio netto ((IIIIII)) - AAjjusttes por cambbiio dde criitteriio dde ejjerciiciios antteriiores - DDiiviiddenddo a
14 147 17 N cuenta [402]
Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Otros
15 164 17 N instrumentos patrimonio neto [403]
Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Ajustes por
16 181 17 N cambios de valor [404]
Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Ajustes en
17 198 17 N patrimonio neto [405]
Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Subvenciones,
18 215 17 N donaciones y legados recibidos [406]
19 232 17 N Estado de cambios patrimonio neto (III) - Ajustes por cambio de criterio de ejercicios anteriores - Total [407]
20 249 17 N EEsttaddo dde cambbiios pattriimoniio netto ((IIIIII)) - AAjjusttes por errores dde ejjerciiciios antteriiores - RResullttaddo ddell ejjerciiciio [[441155]]
21 266 17 N Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Dividendo a cuenta [416]
Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Otros instrumentos
22 283 17 N patrimonio neto [417]
Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Ajustes por cambios de
23 300 17 N valor [418]
Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Ajustes en patrimonio neto
24 317 17 N [419]
Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Subvenciones, donaciones y
25 334 17 N legados recibidos [420]
26 351 17 N Estado de cambios patrimonio neto (III) - Ajustes por errores de ejercicios anteriores - Total [421]
2277 336688 1177 NN EEsttaddo dde cambbiios pattriimoniio netto ((IIIIII)) - SSallddo ajjusttaddo, iiniiciio ddell ejjerciiciio - RResullttaddo ddell ejjerciiciio [[442299]]
28 385 17 N Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Dividendo a cuenta [430]
Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Otros instrumentos patrimonio neto
29 402 17 N [431]
30 419 17 N Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Ajustes por cambios de valor [432]
31 436 17 N Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Ajustes en patrimonio neto [433]
Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Subvenciones, donaciones y legados
32 453 17 N recibidos [434]
33 470 17 N Estado de cambios patrimonio neto (III) - Saldo ajustado, inicio del ejercicio - Total [435]
34 487 17 N Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Resultado del ejercicio [443]
3355 550044 1177 NN EEsttaddo dde cambbiios pattriimoniio netto ((IIIIII)) - TTottall iingresos y gasttos reconociiddos - DDiiviiddenddo a cuentta [[444444]]
Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Otros instrumentos patrimonio neto
36 521 17 N [445]
37 538 17 N Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Ajustes por cambios de valor [446]
Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Subvenciones, donaciones y
38 555 17 N legados recibidos [448]
39 572 17 N Estado de cambios patrimonio neto (III) - Total ingresos y gastos reconocidos - Total [449]
40 589 17 N Estado de cambios patrimonio neto (III) - Resultado cuenta pérdidas y ganancias - Resultado del ejercicio [457]
41 606 17 N Estado de cambios patrimonio neto (III) - Resultado cuenta pérdidas y ganancias - Dividendo a cuenta [458]
Estado de cambios patrimonio neto (III) - Resultado cuenta pérdidas y ganancias - Ajustes en patrimonio neto
4422 662233 1177 NN [[446611]]
Estado de cambios patrimonio neto (III) - Resultado cuenta pérdidas y ganancias - Subvenciones, donaciones y
43 640 17 N legados recibidos [462]
44 657 17 N Estado de cambios patrimonio neto (III) - Resultado cuenta pérdidas y ganancias - Total [463]
Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Resultado del
45 674 17 N ejercicio [471]
Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Dividendo a cuenta
46 691 17 N [472]
Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ajustes en patrimonio
47 708 17 N neto [475]
Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Subvenciones,
48 725 17 N donaciones y legados recibidos [476]
49 742 17 N Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Total [477]
EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIIIII)) - IInnggrreessooss yy ggaassttooss rreeccoonnoocciiddooss eenn ppaattrriimmoonniioo nneettoo - IInnggrreessooss ffiissccaalleess aa
50 759 17 N distribuir en varios ejercicios - Resultado del ejercicio [485]
Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a
51 776 17 N distribuir en varios ejercicios - Dividendo a cuenta [486]
Página 17

# Pag. 18

Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a
52 793 17 N distribuir en varios ejercicios - Ajustes en patrimonio neto [489]
Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a
53 810 17 N distribuir en varios ejercicios - Subvenciones, donaciones y legados recibidos [490]
Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Ingresos fiscales a
54 827 17 N distribuir en varios ejercicios - Total [491]
Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y
55 844 17 N gastos reconocidos en patrimonio neto - Resultado del ejercicio [499]
Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y
56 861 17 N gastos reconocidos en patrimonio neto - Dividendo a cuenta [502]
Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y
57 878 17 N gastos reconocidos en patrimonio neto - Ajustes en patrimonio neto [503]
EEsttaddo dde cambbiios pattriimoniio netto ((IIIIII)) - IIngresos y gasttos reconociiddos en pattriimoniio netto - OOttros iingresos y
58 895 17 N gastos reconocidos en patrimonio neto - Subvenciones, donaciones y legados recibidos [504]
Estado de cambios patrimonio neto (III) - Ingresos y gastos reconocidos en patrimonio neto - Otros ingresos y
59 912 17 N gastos reconocidos en patrimonio neto - Total [505]
60 929 17 N Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Resultado del ejercicio [513]
61 946 17 N Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Dividendo a cuenta [514]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otros instrumentos patrimonio
62 963 17 N neto [515]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Ajustes por cambios de valor
63 980 17 N [516]
6644 999977 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIIIII)) - OOppeerraacciioonneess ccoonn ssoocciiooss oo pprrooppiieettaarriiooss - AAjjuusstteess eenn ppaattrriimmoonniioo nneettoo [[551177]]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Subvenciones, donaciones y
65 1014 17 N legados recibidos [518]
66 1031 17 N Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Total [519]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Resultado
67 1048 17 N del ejercicio [527]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Dividendo
68 1065 17 N a cuenta [528]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Otros
69 1082 17 N instrumentos patrimonio neto [529]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Ajustes
70 1099 17 N por cambios de valor [530]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Ajustes en
7711 11111166 1177 NN ppaattrriimmoonniioo nneettoo [[553311]]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital -
72 1133 17 N Subvenciones, donaciones y legados recibidos [532]
73 1150 17 N Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Aumentos de capital - Total [533]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital -
74 1167 17 N Resultado del ejercicio [541]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital -
75 1184 17 N Dividendo a cuenta [542]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital -
76 1201 17 N Otros instrumentos patrimonio neto [543]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital -
77 1218 17 N Ajustes por cambios de valor [544]
EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIIIII)) -- OOppeerraacciioonneess ccoonn ssoocciiooss oo pprrooppiieettaarriiooss -- ((--)) RReedduucccciioonneess ddee ccaappiittaall --
78 1235 17 N Ajustes en patrimonio neto [545]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital -
79 1252 17 N Subvenciones, donaciones y legados recibidos [546]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Reducciones de capital - Total
80 1269 17 N [547]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en
81 1286 17 N patrim. neto - Resultado del ejercicio [555]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en
82 1303 17 N patrim. neto - Dividendo a cuenta [556]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en
83 1320 17 N patrim. neto - Otros instrumentos patrimonio neto [557]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en
8844 11333377 1177 NN ppaattrriimm.. nneettoo - AAjjuusstteess ppoorr ccaammbbiiooss ddee vvaalloorr [[555588]]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en
85 1354 17 N patrim. neto - Subvenciones, donaciones y legados recibidos [560]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Conversión de pasivos en
86 1371 17 N patrim. neto - Total [561]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos -
87 1388 17 N Resultado del ejercicio [569]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos -
88 1405 17 N Dividendo a cuenta [570]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos -
89 1422 17 N Otros instrumentos patrimonio neto [571]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos -
90 1439 17 N Ajustes por cambio de valor [572]
Estado de cambios ppatrimonio neto ((III)) - Opperaciones con socios o pproppietarios - ((-)) Distribución de dividendos -
91 1456 17 N Subvenciones, donaciones y legados recibidos [574]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - (-) Distribución de dividendos -
92 1473 17 N Total [575]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o
93 1490 17 N participaciones propias - Resultado del ejercicio [583]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o
94 1507 17 N participaciones propias - Dividendo a cuenta [584]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o
95 1524 17 N participaciones propias - Otros instrumentos patrimonio neto [585]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o
96 1541 17 N participaciones propias - Ajustes por cambio de valor [586]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o
97 1558 17 N participaciones propias - Subvenciones, donaciones y legados recibidos [588]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Operaciones con acciones o
98 1575 17 N participaciones propias - Total [589]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr.
99 1592 17 N neto de combinación de negocios - Resultado del ejercicio [597]
Página 18

# Pag. 19

Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr.
100 1609 17 N neto de combinación de negocios - Dividendo a cuenta [598]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr.
101 1626 17 N neto de combinación de negocios - Otros instrumentos patrimonio neto [599]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr.
102 1643 17 N neto de combinación de negocios - Ajustes por cambios de valor [600]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr.
103 1660 17 N neto de combinación de negocios - Subvenciones, donaciones y legados recibidos [602]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Incremento (reducción) de patr.
104 1677 17 N neto de combinación de negocios - Total [603]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o
105 1694 17 N propietarios - Resultado del ejercicio [611]
EEsttaddo dde cambbiios pattriimoniio netto ((IIIIII)) - OOperaciiones con sociios o propiiettariios - OOttras operaciiones con sociios o
106 1711 17 N propietarios - Dividendo a cuenta [612]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o
107 1728 17 N propietarios - Otros instrumentos patrimonio neto [ [613]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o
108 1745 17 N propietarios - Ajustes por cambios de valor [614]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o
109 1762 17 N propietarios - Ajustes en patrimonio neto [615]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o
110 1779 17 N propietarios - Subvenciones, donaciones y legados recibidos [616]
Estado de cambios patrimonio neto (III) - Operaciones con socios o propietarios - Otras operaciones con socios o
111 1796 17 N propietarios - Total [617]
111122 11881133 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIIIII)) - OOttrraass vvaarriiaacciioonneess ddeell ppaattrriimmoonniioo nneettoo - RReessuullttaaddoo ddeell eejjeerrcciicciioo [[662255]]
113 1830 17 N Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Dividendo a cuenta [626]
Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otros instrumentos patrimonio
114 1847 17 N neto [ [627]
Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Ajustes por cambios de valor
115 1864 17 N [628]
116 1881 17 N Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Ajustes en patrimonio neto [629]
Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Subvenciones, donaciones y
117 1898 17 N legados recibidos [630]
118 1915 17 N Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Total [631]
Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización
111199 11993322 1177 NN - RReessuullttaaddoo ddeell eejjeerrcciicciioo [[772222]]
Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización
120 1949 17 N - Dividendo a cuenta [723]
Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización
121 1966 17 N - Otros instrumentos patrimonio neto [ [724]
Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización
122 1983 17 N - Ajustes por cambios de valor [725]
Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización
123 2000 17 N - Ajustes en patrimonio neto [726]
Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización
124 2017 17 N - Subvenciones, donaciones y legados recibidos [727]
Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Movimiento reserva revalorización
125 2034 17 N - Total [728]
EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIIIII)) -- OOttrraass vvaarriiaacciioonneess ddeell ppaattrriimmoonniioo nneettoo -- OOttrraass vvaarriiaacciioonneess -- RReessuullttaaddoo ddeell
126 2051 17 N ejercicio [736]
Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Dividendo a
127 2068 17 N cuenta [737]
Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Otros
128 2085 17 N instrumentos patrimonio neto [ [738]
Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Ajustes por
129 2102 17 N cambios de valor [739]
Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Ajustes en
130 2119 17 N patrimonio neto [740]
Estado de cambios patrimonio neto (III) - Otras variaciones del patrimonio neto - Otras variaciones - Subvenciones,
131 2136 17 N donaciones y legados recibidos [741]
113322 22115533 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIIIII)) - OOttrraass vvaarriiaacciioonneess ddeell ppaattrriimmoonniioo nneettoo - OOttrraass vvaarriiaacciioonneess - TToottaall [[774422]]
133 2170 17 N Estado de cambios patrimonio neto (III) - Saldo, final ejercicio - Resultado del ejercicio [639]
134 2187 17 N Estado de cambios patrimonio neto (III) - Saldo, final ejercicio - Dividendo a cuenta [640]
135 2204 17 N Estado de cambios patrimonio neto (III) - Saldo, final ejercicio - Otros instrumentos patrimonio neto [641]
136 2221 17 N Estado de cambios patrimonio neto (III) - Saldo, final ejercicio - Ajustes por cambios de valor [642]
137 2238 17 N Estado de cambios patrimonio neto (III) - Saldo, final ejercicio - Ajustes en patrimonio neto [643]
138 2255 17 N [644]
139 2272 17 N Estado de cambios patrimonio neto (III) - Saldo, final ejercicio - Total [645]
140 2289 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200110>"
Total: 2298
Página 19

# Pag. 20

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "120"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
LLiiqquuiiddaacciióónn II - RReessuullttaaddoo ddee llaa ccuueennttaa ddee ppéérrddiiddaass yy ggaannaanncciiaass - RReessuullttaaddoo ddee llaa ccuueennttaa ddee ppéérrddiiddaass yy ggaannaanncciiaass
6 11 17 N [500]
Liquidación I - Resultado de la cuenta de pérdidas y ganancias - Correcciones por Impuesto Sociedades -
7 28 17 N Aumentos [301]
Liquidación I - Resultado de la cuenta de pérdidas y ganancias - Correcciones por Impuesto Sociedades -
8 45 17 N Disminuciones [302]
Liquidación I - Resultado de la cuenta de pérdidas y ganancias - Resultado cuenta pérdidas y ganancias antes de
9 62 17 N Impuesto Sociedades [501]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Diferencias entre amortización contable y
10 79 17 Num fiscal - Aumentos [303]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Diferencias entre amortización contable y
11 96 17 Num fiscal - Disminuciones [304]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - 30% importe gastos amortiz. contable -
1122 111133 1177 NNuumm AAuummeennttooss [[550044]]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - 30% importe gastos amortiz. contable -
13 130 17 Num Disminuciones [505]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Amortización inmovilizado afecto
14 147 17 Num investigación y desarrollo - Aumentos [305]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Amortización inmovilizado afecto
15 164 17 Num investigación y desarrollo - Disminuciones [306]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización de gastos de
16 181 17 Num investigación y desarrollo - Aumentos [307]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización de gastos de
17 198 17 Num investigación y desarrollo - Disminuciones [308]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización con
18 215 17 Num mantenimiento de empleo - Aumentos [514]
LLiiqquuiiddaacciióónn II - DDeettaallllee ccoorrrreecccciioonneess rreessuullttaaddoo ccttaa.. ppéérrddiiddaass yy ggaannaanncciiaass - LLiibbeerrttaadd ddee aammoorrttiizzaacciióónn ccoonn
19 232 17 Num mantenimiento de empleo - Disminuciones [509]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización sin
20 249 17 Num mantenimiento de empleo - Aumentos [516]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Libertad de amortización sin
21 266 17 Num mantenimiento de empleo - Disminuciones [551]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otros supuestos de libertad de
22 283 17 Num amortización - Aumentos [309]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otros supuestos de libertad de
23 300 17 Num amortización - Disminuciones [310]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas reducida dimensión:libertad
24 317 17 Num amortización - Aumentos [311]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas reducida dimensión:libertad
25 334 17 Num amortización - Disminuciones [[312]]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas reducida
26 351 17 Num dimensión:amortización acelerada - Aumentos [313]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas reducida
27 368 17 Num dimensión:amortización acelerada - Disminuciones [314]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Cesión de bienes con opción de compra -
28 385 17 Num Aumentos [315]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Cesión de bienes con opción de compra -
29 402 17 Num Disminuciones [316]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Arrendamiento financiero: régimen
30 419 17 Num especial - Aumentos [317]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Arrendamiento financiero: régimen
31 436 17 Num especial - Disminuciones [318]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro no justificadas
32 453 17 Num valor de fondos editoriales, fonográficos y audiovisuales - Aumentos [319]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro no justificadas
33 470 17 Num valor de fondos editoriales, fonográficos y audiovisuales - Disminuciones [320]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro de valor de
34 487 17 Num créditos derivadas de insolvencia deudores - Aumentos [321]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro de valor de
35 504 17 Num créditos derivadas de insolvencia deudores - Disminuciones [322]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas reducida dimensión: pérdidas
36 521 17 Num por deterioro créditos insolvencias - Aumentos [323]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Empresas reducida dimensión: pérdidas
37 538 17 Num por deterioro creditos insolvencias - Disminuciones [324]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por deterioro valores
38 555 17 Num representativos partic.capital o fondos propios - Aumentos [325]
LLiiquiiddaciióón II - DDettalllle correcciiones resullttaddo ctta. péérddiiddas y gananciias - AAjjusttes por ddetteriioro vallores
39 572 17 Num representativos partic.capital o fondos propios - Disminuciones [326]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro de valores
40 589 17 Num representativos de deuda - Aumentos [327]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro de valores
41 606 17 Num representativos de deuda - Disminuciones [328]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Adquisición de participaciones en
42 623 17 Num entidades no residentes - Aumentos [329]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Adquisición de participaciones en
43 640 17 Num entidades no residentes - Disminuciones [330]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Deducción del fondo de comercio -
44 657 17 Num Aumentos [331]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Deducción del fondo de comercio -
4455 667744 1177 NNuumm DDiissmmiinnuucciioonneess [[333322]]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Deducción del intangible de vida útil
46 691 17 Num indefinida - Aumentos [333]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Deducción del intangible de vida útil
47 708 17 Num indefinida - Disminuciones [334]
Página 20

# Pag. 21

Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Provisiones y gastos por pensiones -
48 725 17 Num Aumentos [335]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Provisiones y gastos por pensiones -
49 742 17 Num Disminuciones [336]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles
50 759 17 Num fiscalmente - Aumentos [337]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras provisiones no deducibles
51 776 17 Num fiscalmente - Disminuciones [338]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Gastos por donativos y liberalidades -
52 793 17 Num Aumentos [339]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones realizadas con paraísos
53 810 17 Num fiscales - Aumentos [341]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones realizadas con paraísos
544 88227 117 NNum ffiiscalles - DDiismiinuciiones [[334422]]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Gastos financieros derivados de deudas
55 844 17 Num con entidades del grupo - Aumentos [508]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro valores
56 861 17 Num representativos partic. capital o fondos propios - Aumentos [510]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Pérdidas por deterioro valores
57 878 17 Num representativos partic. capital o fondos propios - Disminuciones [511]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Rentas negativas obtenidas en el
58 895 17 Num extranjero a través de E.P - Aumentos [512]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Rentas negativas obtenidas en el
59 912 17 Num extranjero a través de E.P - Disminuciones [513]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otros gastos no deducibles - Aumentos
60 929 17 Num [343]
LLiiqquuiiddaacciióónn II - DDeettaallllee ccoorrrreecccciioonneess rreessuullttaaddoo ccttaa. ppéérrddiiddaass yy ggaannaanncciiaass - RReennttaass nneeggaattiivvaass oobbtteenniiddaass ppoorr
61 946 17 Num miembros de una UTE en el extranjero - Aumentos [184]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Revalorizaciones contables - Aumentos
62 963 17 Num [345]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Revalorizaciones contables -
63 980 17 Num Disminuciones [346]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Aplicación del valor normal de mercado -
64 997 17 Num Aumentos [347]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Aplicación del valor normal de mercado -
65 1014 17 Num Disminuciones [348]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ingresos por donaciones y legados
66 1031 17 Num otorgados por terceros - Aumentos [349]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ingresos por donaciones y legados
6677 11004488 1177 NNuumm oottoorrggaaddooss ppoorr tteerrcceerrooss -- DDiissmmiinnuucciioonneess [[335500]]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Correción de rentas por depreciación
68 1065 17 Num monetaria - Disminuciones [352]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Gastos por operaciones con acciones
69 1082 17 Num propias - Disminuciones [354]
70 1099 17 Num Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Errores contables - Aumentos [355]
71 1116 17 Num Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Errores contables - Disminuciones [356]
72 1133 17 Num Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones a plazos - Aumentos [357]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Operaciones a plazos - Disminuciones
73 1150 17 Num [358]
LLiiqquuiiddaacciióónn II -- DDeettaallllee ccoorrrreecccciioonneess rreessuullttaaddoo ccttaa.. ppéérrddiiddaass yy ggaannaanncciiaass -- RReevveerrssiióónn ddeell ddeetteerriioorroo ddeell vvaalloorr ddee
74 1167 17 Num elementos patrimoniales - Aumentos [359]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Reversión del deterioro del valor de
75 1184 17 Num elementos patrimoniales - Disminuciones [360]
76 1201 17 Num Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Rentas negativas - Aumentos [225]
77 1218 17 Num Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Rentas negativas - Disminuciones [226]
78 1235 17 Num Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes - Aumentos [415]
79 1252 17 Num Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes - Disminuciones [416]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputación temporal
80 1269 17 Num de ingresos y gastos - Aumentos [361]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Otras diferencias de imputación temporal
8811 11228866 1177 NNuumm ddee iinnggrreessooss yy ggaassttooss - DDiissmmiinnuucciioonneess [[336622]]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por limitación en deducibilidad
82 1303 17 Num en gastos financieros - Aumentos [363]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Ajustes por limitación en deducibilidad
83 1320 17 Num en gastos financieros - Disminuciones [364]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Reinversión de beneficios
84 1337 17 Num extraordinarios - Aumentos [365]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Gastos no deducibles por
85 1354 17 Num incompatibilidad con la deducción por reinversión - Aumentos [367]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Exención por doble imposición
86 1371 17 Num internacional (art.21 LIS) - Aumentos [369]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Exención por doble imposición
87 1388 17 Num internacional (art.21 LIS) - Disminuciones [370]
LLiiqquuiiddaacciióónn II - DDeettaallllee ccoorrrreecccciioonneess rreessuullttaaddoo ccttaa.. ppéérrddiiddaass yy ggaannaanncciiaass - EExxeenncciióónn ppoorr ddoobbllee iimmppoossiicciióónn
88 1405 17 Num internacional (art.22 LIS y DT 41) - Aumentos [256]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Exención por doble imposición
89 1422 17 Num internacional (art.22 LIS y DT 41) - Disminuciones [278]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Reducción de ingresos de activos
90 1439 17 Num intangibles - Disminuciones [372]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Obra benéfico-social cajas de ahorro y
91 1456 17 Num fundaciones bancarias - Aumentos [373]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Obra benéfico-social cajas de ahorro y
92 1473 17 Num fundaciones bancarias - Disminuciones [374]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Agrupaciones interés económico y UTE's -
93 1490 17 Num Aumentos [375]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Agrupaciones interés económico y UTE's -
94 1507 17 Num Disminuciones [376]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Soc. y fondos de capital-riesgo y soc.
95 1524 17 Num desarrollo industrial regional - Aumentos [377]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Soc. y fondos de capital-riesgo y soc.
96 1541 17 Num desarrollo industrial regional - Disminuciones [378]
Página 21

# Pag. 22

Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Valoración bienes y derechos. Régimen
97 1558 17 Num especial operaciones reestructuración - Aumentos [379]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Valoración bienes y derechos. Régimen
98 1575 17 Num especial operaciones reestructuración - Disminuciones [380]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Minería e hidrocarburos : factor
99 1592 17 Num agotamiento - Aumentos [381]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Minería e hidrocarburos : factor
100 1609 17 Num agotamiento - Disminuciones [382]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Hidrocarburos: Amortización inversiones
101 1626 17 Num intangibles y gastos de investigación - Aumentos [383]
Liquidación I - Detalle correcciones resultado cta. pérdidas y ganancias - Hidrocarburos: Amortización inversiones
102 1643 17 Num intangibles y gastos de investigación - Disminuciones [384]
103 1660 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200120>"
Total: 1669
Página 22

# Pag. 23

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "130"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
LLiiqquuiiddaacciióónn IIII -- DDeettaallllee ccoorrrreecccciioonneess rreessuullttaaddoo ccttaa. ppéérrddiiddaass yy ggaannaanncciiaass -- RRééggiimmeenn ffiissccaall eennttiiddaaddeess ddee tteenneenncciiaa
6 11 17 Num valores extranjeros - Aumentos [385]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen fiscal entidades de tenencia
7 28 17 Num valores extranjeros - Disminuciones [386]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Transparencia fiscal internacional -
8 45 17 Num Aumentos [387]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Transparencia fiscal internacional -
9 62 17 Num Disminuciones [388]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente
10 79 17 Num exentas - Aumentos [389]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen de entidades parcialmente
11 96 17 Num exentas - Disminuciones [390]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Aportaciones a favor entidades sin fines
1122 111133 1177 NNuumm lluuccrraattiivvooss -- AAuummeennttooss [[225500]]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Aportaciones a favor entidades sin fines
13 130 17 Num lucrativos - Disminuciones [251]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen fiscal entidades sin fines
14 147 17 Num lucrativos - Aumentos [391]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen fiscal entidades sin fines
15 164 17 Num lucrativos - Disminuciones [392]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Montes vecinales en mano común -
16 181 17 Num Disminuciones [396]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen entidades navieras - Aumentos
17 198 17 Num [397]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Régimen entidades navieras -
18 215 17 Num Disminuciones [398]
LLiiqquuiiddaacciióónn IIII - DDeettaallllee ccoorrrreecccciioonneess rreessuullttaaddoo ccttaa.. ppéérrddiiddaass yy ggaannaanncciiaass - CCooooppeerraattiivvaass:: FFoonnddoo ddee rreesseerrvvaa
19 232 17 Num obligatorio - Disminuciones [400]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Reservas inversiones en Canarias -
20 249 17 Num Aumentos [403]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Reservas inversiones en Canarias -
21 266 17 Num Disminuciones [404]
22 283 17 Num Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Diferimiento plusvalías - Aumentos [405]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Diferimiento plusvalías - Disminuciones
23 300 17 Num [406]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Entidades rég. atribución rentas
24 317 17 Num constituidas extranjero, presencia territorio español - Aumentos [409]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Entidades rég. atribución rentas
25 334 17 Num constituidas extranjjero, ppresencia territorio esppañol - Disminuciones [[410]]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Correcciones específicas entidades
26 351 17 Num sometidas normativa foral - Aumentos [411]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Correcciones específicas entidades
27 368 17 Num sometidas normativa foral - Disminuciones [412]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Exención transmisión bienes inmuebles -
28 385 17 Num Aumentos [518]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Exención transmisión bienes inmuebles -
29 402 17 Num Disminuciones [519]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Impuesto extranjero beneficios con cargo
30 419 17 Num a los cuales se pagan dividendos objeto deducción por doble imposición internacional - Aumentos [340]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Impuesto extranjero soportado por sujeto
31 436 17 Num pasiivo, no ddedduciibblle por affectar rentas con ddedducciióón ddobblle iimposiiciióón - AAumentos [[33511]]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Subvenciones públicas en el resultado
32 453 17 Num del ejercicio, no integrables en la base imponible - Disminuciones [368]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - SICAV: reducciones de capital y
33 470 17 Num distribución prima de emisión - Aumentos [371]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta.
34 487 17 Num pérdidas y ganancias - Aumentos [413]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Otras correcciones al resultado cta.
35 504 17 Num pérdidas y ganancias - Disminuciones [414]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Total correcciones al resultado cta.
36 521 17 Num pérdidas y ganancias - Aumentos [417]
Liquidación II - Detalle correcciones resultado cta. pérdidas y ganancias - Total correcciones al resultado cta.
37 538 17 Num pérdidas y ganancias - Disminuciones [418]
38 555 17 N Liquidación II - Entidades navieras en función del tonelaje - B.I. actividades o rentas en régimen general [578]
39 572 17 N Liquidación II - Entidades navieras en función del tonelaje - B.I. derivada del régimen especial [579]
40 589 17 N Liquidación II - Base imponible - B.I. antes de la compensación de bases imponibles negativas [550]
41 606 17 Num Liquidación II - Base imponible - Compensación de bases imponibles negativas períodos anteriores [547]
42 623 17 N Liquidación II - Base imponible - Base imponible [552]
43 640 17 N Liquidación II - Base imponible - Sólo cooperativas - Resultados cooperativos [553]
44 657 17 N Liquidación II - Base imponible - Sólo cooperativas - Resultados extracooperativos [554]
45 674 17 N Liquidación II - Base imponible - Sólo agrupaciones interés económico y UTE's - Socios residentes [555]
46 691 17 N Liquidación II - Base imponible - Sólo agrupaciones interés económico y UTE's - Socios no residentes [556]
47 708 17 N Liquidación II - Base imponible - Sólo entidades ZEC - B.I. a tipo de gravamen especial [559]
48 725 17 N Liquidación II - Base imponible - Sólo SOCIMIS - Parte B.I. del periodo impositivo que tributa al tipo general [520]
Página 23

# Pag. 24

49 742 17 N Liquidación II - Base imponible - Sólo SOCIMIS - Parte B.I. del periodo impositivo que tributa al tipo del 0% [521]
50 759 4 Num Liquidación II - Tipo de gravamen - Tipo de gravamen [558]
51 763 17 N Liquidación II - Sólo sociedades cooperativas - Cuota íntegra previa [560]
52 780 17 Num Liquidación II - Sólo sociedades cooperativas - Compensación de cuotas por pérdidas de cooperativas [561]
53 797 17 N Liquidación II - Cuota íntegra - Cuota íntegra [562]
54 814 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200130>"
Total: 823
Página 24

# Pag. 25

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "140"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria. En blanco En blanco
LLiiqquuiiddaacciióónn IIIIII - BBoonniiffiiccaacciioonneess//DDeedduucccciioonneess ddoobbllee iimmppoossiicciióónn - BBoonniiffiiccaacciióónn ppoorr rreennttaass oobbtteenniiddaass eenn CCeeuuttaa yy
6 11 17 Num Melilla [567]
Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificación actividades exportadoras y de
7 28 17 Num prestación de servicios [568]
Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificación rendimientos por venta de bienes
8 45 17 Num corporales producidos en Canarias [563]
Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificaciones sociedades cooperativas [566]
9 62 17 Num
Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificaciones entidades dedicadas al
10 79 17 Num arrendamiento de viviendas [576]
11 96 17 Num Liquidación III - Bonificaciones/Deducciones doble imposición - Otras bonificaciones [569]
Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición - D.I. interna de
12 113 17 Num periodos anteriores aplicada en el ejercicio [570]
LLiiqquuiiddaacciióónn IIIIII -- BBoonniiffiiccaacciioonneess//DDeedduucccciioonneess ddoobbllee iimmppoossiicciióónn -- DDeedduucccciioonneess ppoorr ddoobbllee iimmppoossiicciióónn -- DD.II. iinntteerrnnaa
13 130 17 Num generada y aplicada en el ejercicio actual [571]
Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición - D.I.
14 147 17 Num internacional periodos anteriores aplicada en el ejercicio [572]
Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición - D.I.
15 164 17 Num internacional generada y aplicada ejercicio actual [573]
Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición - Transparencia
16 181 17 Num fiscal internacional [575]
Liquidación III - Bonificaciones/Deducciones doble imposición - Deducciones por doble imposición - D.I. interna
17 198 17 Num intersocietaria al 5/10 % (cooperativas) [577]
Liquidación III - Bonificaciones/Deducciones doble imposición - Bonificaciones empresas navieras en Canarias
18 215 17 Num [581]
19 232 17 N Liquidación III - Bonificaciones/Deducciones doble imposición - Cuota íntegra ajustada positiva [582]
2200 224499 1177 NNuumm LLiiqquuiiddaacciióónn IIIIII -- OOttrraass ddeedduucccciioonneess -- AAppooyyoo ffiissccaall aa llaa iinnvveerrssiióónn yy oottrraass ddeedduucccciioonneess [[558833]]
21 266 17 Num Liquidación III - Otras deducciones - Deducción art.42 L.I.S. y art. 36 ter Ley 43/95 [585]
22 283 17 Num Liquidación III - Otras deducciones - Deducciones disposición transitoria octava L.I.S. [584]
23 300 17 Num Liquidación III - Otras deducciones - Deducciones con límite del Capítulo IV Título VI L.I.S. [588]
24 317 17 Num Liquidación III - Otras deducciones - Deducciones sin límite I+D+i [082]
25 334 17 Num Liquidación III - Otras deducciones - Deducción donaciones a entidades sin fines de lucro [565]
26 351 17 Num Liquidación III - Otras deducciones - Deducciones inversión Canarias (Ley 20/1991) [590]
Liquidación III - Otras deducciones - Deducciones especifícas de las entidades sometidas a normativa foral [399]
27 368 17 Num
28 385 17 N Liquidación III - Otras deducciones - Cuota líquida positiva [592]
Liquidación III - Cuota del ejercicio a ingresar o a devolver - Retenciones e ingresos a cuenta/pagos a cuenta
29 402 17 Num participaciones I.I.C. [595]
Liquidación III - Cuota del ejercicio a ingresar o a devolver - Ret. e ingr. a cuenta/pagos a cuenta participaciones
30 419 17 Num I.I.C. imputadas por agrup. de interés economico y UTES [596]
Liquidación III - Cuota del ejercicio a ingresar o a devolver - Retenciones sobre premios loterías y apuestas [597]
31 436 17 Num
Liquidación III - Cuota del ejercicio a ingresar o a devolver - Abono deducciones I+D+i por insuficiencia de cuota
32 453 17 Num [408]
Liquidación III - Cuota del ejercicio a ingresar o a devolver - Abono por conversión de activos por impuesto diferido
33 470 17 Num en crédito exigible [150]
Liquidación III - Cuota del ejercicio a ingresar o a devolver - Cuota del ejercicio a ingresar o a devolver - Estado
34 487 17 N [599]
Liquidación III - Cuota del ejercicio a ingresar o a devolver - Cuota del ejercicio a ingresar o a devolver - D.
35 504 17 N Forales/Navarra (Totales) [600]
36 521 17 Num Liquidación III - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 1 - Estado [601]
LLiiqquuiiddaacciióónn IIIIII -- PPaaggooss ffrraacccciioonnaaddooss//CCuuoottaa ddiiffeerreenncciiaall -- PPaaggooss ffrraacccciioonnaaddooss -- 11 -- DD. FFoorraalleess//NNaavvaarrrraa ((TToottaalleess)) [[660022]]
37 538 17 Num
38 555 17 Num Liquidación III - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 2 - Estado [603]
Liquidación III - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 2 - D. Forales/Navarra (Totales) [604]
39 572 17 Num
40 589 17 Num Liquidación III - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 3 - Estado [605]
Liquidación III - Pagos fraccionados/Cuota diferencial - Pagos fraccionados - 3 - D. Forales/Navarra (Totales) [606]
41 606 17 Num
42 623 17 N Liquidación III - Pagos fraccionados/Cuota diferencial - Cuota diferencial - Estado [611]
Liquidación III - Pagos fraccionados/Cuota diferencial - Cuota diferencial - D. Forales/Navarra (Totales) [612]
43 640 17 N
Liquidación III - Líquido a ingresar o a devolver - Incremento por pérdida beneficios fiscales períodos anteriores -
44 657 17 Num Estado [615]
LLiiquiiddaciióón IIIIII - LLííquiiddo a iingresar o a ddevollver - IIncrementto por péérddiidda bbeneffiiciios ffiiscalles perííoddos antteriiores -
45 674 17 Num D. Forales/Navarra (Totales) [616]
Liquidación III - Líquido a ingresar o a devolver - Incremento por incumplimiento de requisitos SOCIMI - Estado
46 691 17 Num [633]
Liquidación III - Líquido a ingresar o a devolver - Incremento por incumplimiento de requisitos SOCIMI - D.
47 708 17 Num Forales/Navarra (Totales) [642]
48 725 17 Num Liquidación III - Líquido a ingresar o a devolver - Intereses de demora - Estado [617]
Liquidación III - Líquido a ingresar o a devolver - Intereses de demora - D. Forales/Navarra (Totales) [618]
49 742 17 Num
Liquidación III - Líquido a ingresar o a devolver - Importe ingreso/devolución efectuada de la declaración originaria
50 759 17 N - Estado [619]
Liquidación III - Líquido a ingresar o a devolver - Importe ingreso/devolución efectuada de la declaración originaria
51 776 17 N - D. Forales/Navarra (Totales) [620]
52 793 17 N Liquidación III - Líquido a ingresar o a devolver - Estado [621]
53 810 17 N Liquidación III - Líquido a ingresar o a devolver - D. Forales/Navarra (Totales) [622]
54 827 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200140>"
Total: 836
Página 25

# Pag. 26

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas
vers. 1.0
constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. Constante "<T" . Campo OBLIGATORIO OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "150"
4 9 1 An Fin de identificador de modelo. Constante: ">" .Campo OBLIGATORIO OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria. En blanco
66 1111 1177 NNuumm DDeettaallllee ccoommppeennssaacciióónn bbaasseess iimmppoonniibblleess nneeggaattiivvaass - 11999977 - PPeennddiieennttee aapplliiccaacciióónn aa pprriinncciippiioo ppeerriiooddoo [[664400]]
7 28 17 Num Detalle compensación bases imponibles negativas - 1997 - Aplicado en esta liquidación [641]
8 45 17 Num Detalle compensación bases imponibles negativas - 1997 - Pendiente aplicación en periodos futuros [548]
9 62 17 Num Detalle compensación bases imponibles negativas - 1998 - Pendiente aplicación a principio periodo [643]
10 79 17 Num Detalle compensación bases imponibles negativas - 1998 - Aplicado en esta liquidación [644]
11 96 17 Num Detalle compensación bases imponibles negativas - 1998 - Pendiente aplicación en periodos futuros [645]
12 113 17 Num Detalle compensación bases imponibles negativas - 1999 - Pendiente aplicación a principio periodo [646]
13 130 17 Num Detalle compensación bases imponibles negativas - 1999 - Aplicado en esta liquidación [647]
14 147 17 Num Detalle compensación bases imponibles negativas - 1999 - Pendiente aplicación en periodos futuros [648]
15 164 17 Num Detalle compensación bases imponibles negativas - 2000 - Pendiente aplicación a principio periodo [649]
16 181 17 Num Detalle compensación bases imponibles negativas - 2000 - Aplicado en esta liquidación [650]
17 198 17 Num Detalle compensación bases imponibles negativas - 2000 - Pendiente aplicación en periodos futuros [651]
1188 221155 1177 NNuumm DDeettaallllee ccoommppeennssaacciióónn bbaasseess iimmppoonniibblleess nneeggaattiivvaass - 22000011 - PPeennddiieennttee aapplliiccaacciióónn aa pprriinncciippiioo ppeerriiooddoo [[665522]]
19 232 17 Num Detalle compensación bases imponibles negativas - 2001 - Aplicado en esta liquidación [653]
20 249 17 Num Detalle compensación bases imponibles negativas - 2001 - Pendiente aplicación en periodos futuros [654]
21 266 17 Num Detalle compensación bases imponibles negativas - 2002 - Pendiente aplicación a principio periodo [655]
22 283 17 Num Detalle compensación bases imponibles negativas - 2002 - Aplicado en esta liquidación [656]
23 300 17 Num Detalle compensación bases imponibles negativas - 2002 - Pendiente aplicación en periodos futuros [657]
24 317 17 Num Detalle compensación bases imponibles negativas - 2003 - Pendiente aplicación a principio periodo [658]
25 334 17 Num Detalle compensación bases imponibles negativas - 2003 - Aplicado en esta liquidación [659]
26 351 17 Num Detalle compensación bases imponibles negativas - 2003 - Pendiente aplicación en periodos futuros [660]
27 368 17 Num Detalle compensación bases imponibles negativas - 2004 - Pendiente aplicación a principio periodo [661]
28 385 17 Num Detalle compensación bases imponibles negativas - 2004 - Aplicado en esta liquidación [662]
29 402 17 Num Detalle compensación bases imponibles negativas - 2004 - Pendiente aplicación en periodos futuros [663]
30 419 17 Num Detalle compensación bases imponibles negativas - 2005 - Pendiente aplicación a principio periodo [664]
31 436 17 Num DDettalllle compensaciióón bbases iimponiibblles negattiivas - 22000055 - AAplliicaddo en estta lliiquiiddaciióón [[666655]]
32 453 17 Num Detalle compensación bases imponibles negativas - 2005 - Pendiente aplicación en periodos futuros [666]
33 470 17 Num Detalle compensación bases imponibles negativas - 2006 - Pendiente aplicación a principio periodo [667]
34 487 17 Num Detalle compensación bases imponibles negativas - 2006 - Aplicado en esta liquidación [668]
35 504 17 Num Detalle compensación bases imponibles negativas - 2006 - Pendiente aplicación en periodos futuros [669]
36 521 17 Num Detalle compensación bases imponibles negativas - 2007 - Pendiente aplicación a principio periodo [743]
37 538 17 Num Detalle compensación bases imponibles negativas - 2007 - Aplicado en esta liquidación [747]
38 555 17 Num Detalle compensación bases imponibles negativas - 2007 - Pendiente aplicación en periodos futuros [748]
39 572 17 Num Detalle compensación bases imponibles negativas - 2008 - Pendiente aplicación a principio periodo [275]
40 589 17 Num Detalle compensación bases imponibles negativas - 2008 - Aplicado en esta liquidación [276]
41 606 17 Num Detalle compensación bases imponibles negativas - 2008 - Pendiente aplicación en periodos futuros [277]
42 623 17 Num Detalle compensación bases imponibles negativas - 2009 - Pendiente de aplicación a principio del periodo [608]
4433 664400 1177 NNuumm DDeettaallllee ccoommppeennssaacciióónn bbaasseess iimmppoonniibblleess nneeggaattiivvaass -- 22000099 -- AApplliiccaaddoo eenn eessttaa lliiqquuiiddaacciióónn [[660099]]
44 657 17 Num Detalle compensación bases imponibles negativas - 2009 - Pendiente aplicación en periodos futuros [610]
45 674 17 Num Detalle compensación bases imponibles negativas - 2010 - Pendiente aplicación a principio periodo [704]
46 691 17 Num Detalle compensación bases imponibles negativas - 2010 - Aplicado en esta liquidación [705]
47 708 17 Num Detalle compensación bases imponibles negativas - 2010 - Pendiente aplicación en periodos futuros [706]
48 725 17 Num Detalle compensación bases imponibles negativas - 2011 - Pendiente aplicación a principio periodo [013]
49 742 17 Num Detalle compensación bases imponibles negativas - 2011 - Aplicado en esta liquidación [014]
50 759 17 Num Detalle compensación bases imponibles negativas - 2011 - Pendiente aplicación en periodos futuros [015]
51 776 17 Num Detalle compensación bases imponibles negativas - 2012 - Pendiente aplicación a principio periodo [725]
52 793 17 Num Detalle compensación bases imponibles negativas - 2012 - Aplicado en esta liquidación [726]
53 810 17 Num Detalle compensación bases imponibles negativas - 2012 - Pendiente aplicación en periodos futuros [727]
54 827 17 Num Detalle compensación bases imponibles negativas - 2013 (*) - Pendiente aplicación a principio periodo [534]
55 844 17 Num Detalle comppensación bases impponibles neggativas - 2013 ((*)) - Applicado en esta liqquidación [[535]]
56 861 17 Num Detalle compensación bases imponibles negativas - 2013 (*) - Pendiente aplicación en periodos futuros [536]
57 878 17 Num Detalle compensación bases imponibles negativas - TOTAL - Pendiente aplicación a principio periodo [670]
58 895 17 Num Detalle compensación bases imponibles negativas - TOTAL - Aplicado en esta liquidación [547]
59 912 17 Num Detalle compensación bases imponibles negativas - TOTAL - Pendiente de aplicación en periodos futuros [671]
60 929 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2006- Deducción pendiente/generada [101]
61 946 4 Num Deducciones doble imposición interna 2006-2013 - DI interna 2006 - Tipo de gravamen periodo generación [102]
62 950 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2006 - 2013 Deducción pendiente [696]
63 967 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2006 - Deducción aplicada en esta liquidación [697]
64 984 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2007 - Deducción pendiente/generada [104]
65 1001 4 Num Deducciones doble imposición interna 2006-2013 - DI interna 2007 - Tipo de gravamen periodo generación [105]
66 1005 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2007 - 2013 Deducción pendiente [846]
67 1022 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2007 - Deducción aplicada en esta liquidación [847]
6688 11003399 1177 NNumm DDeedduucccciioonneess ddoobbllee iimmppoossiicciióónn iinntteerrnnaa 22000066-22001133 - DDII iinntteerrnnaa 22000077 - DDeedduucccciióónn ppeennddiieennttee ppeerrííooddooss ffuuttuurrooss [[884488]]
69 1056 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2008 - Deducción pendiente/generada [106]
70 1073 4 Num Deducciones doble imposición interna 2006-2013 - DI interna 2008 - Tipo de gravamen periodo generación [107]
71 1077 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2008 - 2013 Deducción pendiente [282]
72 1094 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2008 - Deducción aplicada en esta liquidación [283]
73 1111 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2008 - Deducción pendiente períodos futuros [284]
74 1128 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2009 - Deducción pendiente/generada [108]
75 1145 4 Num Deducciones doble imposición interna 2006-2013 - DI interna 2009 - Tipo de gravamen periodo generación [109]
76 1149 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2009 - 2013 Deducción pendiente [702]
77 1166 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2009 - Deducción aplicada en esta liquidación [703]
78 1183 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2009 - Deducción pendiente períodos futuros [707]
79 1200 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2010 - Deducción pendiente/generada [110]
8800 11221177 44 NNuumm DDeedduucccciioonneess ddoobbllee iimmppoossiicciióónn iinntteerrnnaa 22000066-22001133 - DDII iinntteerrnnaa 22001100 - TTiippoo ddee ggrraavvaammeenn ppeerriiooddoo ggeenneerraacciióónn [[111111]]
81 1221 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2010 - 2013 Deducción pendiente [071]
82 1238 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2010 - Deducción aplicada en esta liquidación [187]
83 1255 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2010 - Deducción pendiente períodos futuros [300]
84 1272 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2011 - Deducción pendiente/generada [112]
85 1289 4 Num Deducciones doble imposición interna 2006-2013 - DI interna 2011 - Tipo de gravamen periodo generación [113]
86 1293 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2011 - 2013 Deducción pendiente [025]
87 1310 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2011 - Deducción aplicada en esta liquidación [026]
88 1327 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2011 - Deducción pendiente períodos futuros [027]
Página 26

# Pag. 27

89 1344 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2012 - Deducción pendiente/generada [114]
90 1361 4 Num Deducciones doble imposición interna 2006-2013 - DI interna 2012 - Tipo de gravamen periodo generación [115]
91 1365 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2012 - 2013 Deducción pendiente [714]
92 1382 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2012 - Deducción aplicada en esta liquidación [715]
93 1399 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2012 - Deducción pendiente períodos futuros [716]
94 1416 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2013 (*) - Deducción pendiente/generada [735]
95 1433 4 Num Deducciones doble imposición interna 2006-2013 - DI interna 2013 (*) - Tipo de gravamen periodo generación [920]
96 1437 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2013 (*) - 2013 Deducción pendiente [736]
97 1454 17 Num Deducciones doble imposición interna 2006-2013- DI interna 2013 (*) - Deducción aplicada en esta liquidación [737]
98 1471 17 Num Deducciones doble imposición interna 2006-2013 - DI interna 2013 (*) - Deducción pendiente períodos futuros [738]
99 1488 17 Num Deducciones doble imposición interna - Total 2006-2013 - Deducción pendiente/generada [116]
100 1505 17 Num Deducciones doble imposición interna - Total 2006-2013 - 2013 Deducción pendiente [117]
110011 11552222 1177 NNuumm DDeedduucccciioonneess ddoobbllee iimmppoossiicciióónn iinntteerrnnaa - TToottaall 22000066-22001133 - DDeedduucccciióónn aapplliiccaaddaa eenn eessttaa lliiqquuiiddaacciióónn [[557700]]
102 1539 17 Num Deducciones doble imposición interna - Total 2006-2013 - Deducción pendiente períodos futuros [118]
103 1556 7 Num Deducciones doble imposición interna - Tipo de gravamen 2013 [103]
104 1563 17 Num Deducciones doble imposición interna - DI interna 2013 - Intersoc.al 50% - Deducción pendiente/generada [119]
105 1580 17 Num Deducciones doble imposición interna - DI interna 2013 - Intersoc.al 50% - 2013 Deducción pendiente [120]
Deducciones doble imposición interna - DI interna 2013 - Intersoc.al 50% - Deducción aplicada en esta liquidación [121]
106 1597 17 Num
Deducciones doble imposición interna - DI interna 2013 - Intersoc.al 50% - Deducción pendiente períodos futuros [122]
107 1614 17 Num
108 1631 17 Num Deducciones doble imposición interna - DI interna 2013 - Intersoc.al 100% - Deducción pendiente/generada [123]
109 1648 17 Num Deducciones doble imposición interna - DI interna 2013 - Intersoc.al 100% - 2013 Deducción pendiente [124]
Deducciones doble imposición interna - DI interna 2013 - Intersoc.al 100% - Deducción aplicada en esta liquidación [125]
110 1665 17 Num
Deducciones doble imposición interna - DI interna 2013 - Intersoc.al 100% - Deducción pendiente períodos futuros [126]
111 1682 17 Num
Deducciones doble imposición interna - DI interna 2013 - Plusvalías fuente interna - Deducción pendiente/generada [127]
112 1699 17 Num
113 1716 17 Num Deducciones doble imposición interna - DI interna 2013 - Plusvalías fuente interna - 2013 Deducción pendiente [128]
Deducciones doble imposición interna - DI interna 2013 - Plusvalías fuente interna - Deducción aplicada en esta liquidación
114 1733 17 Num [129]
Deducciones doble imposición interna - DI interna 2013 - Plusvalías fuente interna - Deducción pendiente períodos futuros
115 1750 17 Num [130]
116 1767 17 Num Deducciones doble imposición interna - Total 2013 - Deducción pendiente/generada [131]
117 1784 17 Num Deducciones doble imposición interna - Total 2013 - 2013 Deducción pendiente [132]
118 1801 17 Num Deducciones doble imposición interna - Total 2013 - Deducción aplicada en esta liquidación [571]
119 1818 17 Num Deducciones doble imposición interna - Total 2013 - Deducción pendiente períodos futuros [133]
120 1835 17 Num Deducciones doble imposición internacional 2003-2013 - DI internacional 2003 - Deducción pendiente/generada [151]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2003 - Tipo de gravamen periodo generación [152]
121 1852 4 Num
122 1856 17 Num Deducciones doble imposición internacional 2003-2013 - DI internacional 2003 - 2013 Deducción pendiente [711]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2003 - Deducción aplicada en esta liquidación [712]
123 1873 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2004 - Deducción pendiente/generada [153]
124 1890 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2004 - Tipo de gravamen periodo generación [728]
125 1907 4 Num
126 1911 17 Num Deducciones doble imposición internacional 2003-2013 - DI internacional 2004 - 2013 Deducción pendiente [637]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2004 - Deducción aplicada en esta liquidación [638]
127 1928 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2004 - Deducción pendiente períodos futuros [639]
128 1945 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2005 - Deducción pendiente/generada [154]
129 1962 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2005 - Tipo de gravamen periodo generación [729]
130 1979 4 Num
131 1983 17 Num Deducciones doble imposición internacional 2003-2013 - DI internacional 2005 - 2013 Deducción pendiente [849]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2005 - Deducción aplicada en esta liquidación [894]
132 2000 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2005 - Deducción pendiente períodos futuros [197]
133 2017 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2006 - Deducción pendiente/generada [155]
134 2034 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2006 - Tipo de gravamen periodo generación [730]
135 2051 4 Num
136 2055 17 Num Deducciones doble imposición internacional 2003-2013 - DI internacional 2006 - 2013 Deducción pendiente [285]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2006 - Deducción aplicada en esta liquidación [286]
137 2072 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2006 - Deducción pendiente períodos futuros [287]
138 2089 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2007 - Deducción pendiente/generada [156]
139 2106 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2007 - Tipo de gravamen periodo generación [731]
140 2123 4 Num
141 2127 17 Num Deducciones doble imposición internacional 2003-2013 - DI internacional 2007 - 2013 Deducción pendiente [825]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2007 - Deducción aplicada en esta liquidación [826]
142 2144 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2007 - Deducción pendiente períodos futuros [827]
143 2161 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2008 - Deducción pendiente/generada [157]
144 2178 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2008 - Tipo de gravamen periodo generación [732]
145 2195 4 Num
146 2199 17 Num Deducciones doble imposición internacional 2003-2013 - DI internacional 2008 - 2013 Deducción pendiente [001]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2008 - Deducción aplicada en esta liquidación [002]
147 2216 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2008- Deducción pendiente períodos futuros [003]
148 2233 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2009 - Deducción pendiente/generada [158]
114499 22225500 1177 NNum
Deducciones doble imposición internacional 2003-2013 - DI internacional 2009 - Tipo de gravamen periodo generación [733]
150 2267 4 Num
151 2271 17 Num Deducciones doble imposición internacional 2003-2013 - DI internacional 2009 - 2013 Deducción pendiente [028]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2009 - Deducción aplicada en esta liquidación [029]
152 2288 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2009 - Deducción pendiente períodos futuros [030]
153 2305 17 Num
Página 27

# Pag. 28

Deducciones doble imposición internacional 2003-2013 - DI internacional 2010 - Deducción pendiente/generada [159]
154 2322 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2010 - Tipo de gravamen periodo generación [734]
155 2339 4 Num
156 2343 17 Num Deducciones doble imposición internacional 2003-2013 - DI internacional 2010 - 2013 Deducción pendiente [717]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2010 - Deducción aplicada en esta liquidación [718]
157 2360 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2010 - Deducción pendiente períodos futuros [719]
158 2377 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2011 - Deducción pendiente/generada [720]
159 2394 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2011 - Tipo de gravamen periodo generación [721]
160 2411 4 Num
161 2415 17 Num Deducciones doble imposición internacional 2003-2013 - DI internacional 2011 - 2013 Deducción pendiente [722]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2011 - Deducción aplicada en esta liquidación [723]
162 2432 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2011 - Deducción pendiente períodos futuros [724]
163 2449 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2012 - Deducción pendiente/generada [739]
164 2466 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2012 - Tipo de gravamen periodo generación [921]
165 2483 4 Num
166 2487 17 Num Deducciones doble imposición internacional 2003-2013 - DI internacional 2012 - 2013 Deducción pendiente [740]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2012 - Deducción aplicada en esta liquidación [741]
167 2504 17 Num
Deducciones doble imposición internacional 2003-2013 - DI internacional 2012 - Deducción pendiente períodos futuros [742]
168 2521 17 Num
169 2538 17 Num Deducciones doble imposición internacional 2003-2013 - DI internacional 2013 (*) - Deducción pendiente/generada [134]
170 2555 4 Num Deducciones doble imposición internacional 2003-2013 - DI internacional 2013 (*) - Tipo de gravamen periodo generación
171 2559 17 Num Deducciones doble imposición internacional 2003-2013 - DI internacional 2013 (*) - 2013 Deducción pendiente [135]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2013 (*) - Deducción aplicada en esta liquidación
172 2576 17 Num [136]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2013 (*) - Deducción pendiente períodos futuros
173 2593 17 Num [137]
174 2610 17 Num Deducciones doble imposición internacional - Total 2003-2013 - Deducción pendiente/generada [160]
175 2627 17 Num Deducciones doble imposición internacional - Total 2003-2013 - 2013 Deducción pendiente [161]
176 2644 17 Num Deducciones doble imposición internacional - Total 2003-2013 - Deducción aplicada en esta liquidación [572]
177 2661 17 Num Deducciones doble imposición internacional - Total 2003-2013 - Deducción pendiente ejercicios futuros [162]
117788 22667788 77 NNuumm DDeedduucccciioonneess ddoobbllee iimmppoossiicciióónn iinntteerrnnaacciioonnaall - TTiippoo ddee ggrraavvaammeenn 22001133 [[110033]]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2013 - Impuesto soportado sujeto pasivo -
179 2685 17 Num Deducción pendiente/generada [163]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2013 - Impuesto soportado sujeto pasivo - 2013
180 2702 17 Num Deducción pendiente [164]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2013 - Impuesto soportado sujeto pasivo -
181 2719 17 Num Deducción aplicada en esta liquidación [165]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2013 - Impuesto soportado sujeto pasivo -
182 2736 17 Num Deducción pendiente períodos futuros [166]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2013 - Dividendos y participaciones en beneficios -
183 2753 17 Num Deducción pendiente/generada [167]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2013 - Dividendos y participacionesen beneficios -
184 2770 17 Num 2013 Deducción pendiente [168]
Deducciones doble impposición internacional 2003-2013 - DI internacional 2013 - Dividendos yy pparticippaciones en beneficios -
185 2787 17 Num Deducción aplicada en esta liquidación [169]
Deducciones doble imposición internacional 2003-2013 - DI internacional 2013 - Dividendos y participaciones en beneficios -
186 2804 17 Num Deducción pendiente períodos futuros [170]
187 2821 17 Num Deducciones doble imposición internacional 2003-2013 - Total 2013 - Deducción pendiente/generada [171]
188 2838 17 Num Deducciones doble imposición internacional 2003-2013 - Total 2013 - 2013 Deducción pendiente [172]
189 2855 17 Num Deducciones doble imposición internacional 2003-2013 - Total 2013 - Deducción aplicada en esta liquidación [573]
190 2872 17 Num Deducciones doble imposición internacional 2003-2013 - Total 2013 - Deducción pendiente períodos futuros [174]
191 2889 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200150>"
Total: 2898
Página 28

# Pag. 29

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. Campo OBLIGATORIO OBLIGATORIO Constante "160"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria. En blanco
66 1111 1177 NNuumm DDeedduucccc.. AArrtt.. 3366 tteerr LLeeyy 4433 // 11999955.. 22000022 - DDeedduucccciióónn ppeennddiieennttee//ggeenneerraaddaa [[883355]]
7 28 17 Num Deducc. Art. 36 ter Ley 43 / 1995. 2002 - Aplicado en esta liquidación [836]
8 45 17 Num Deducc. Art. 36 ter Ley 43 / 1995. 2002 - Pendiente aplicación en periodos futuros [837]
9 62 17 Num Deducc. Art. 36 ter Ley 43 / 1995. 2003 - Deducción pendiente/generada [838]
10 79 17 Num Deducc. Art. 36 ter Ley 43 / 1995. 2003 - Aplicado en esta liquidación [839]
11 96 17 Num Deducc. Art. 36 ter Ley 43 / 1995. 2003 - Pendiente aplicación en periodos futuros [840]
12 113 17 Num Deducc. Art. 42 L.I.S. 2004 - Deducción pendiente/generada [932]
13 130 17 Num Deducc. Art. 42 L.I.S. 2004 - Aplicado en esta liquidación [933]
14 147 17 Num Deducc. Art. 42 L.I.S. 2004 - Pendiente aplicación en periodos futuros [934]
15 164 17 Num Deducc. Art. 42 L.I.S. 2005 - Deducción pendiente/generada [297]
16 181 17 Num Deducc. Art. 42 L.I.S. 2005 - Aplicado en esta liquidación [298]
17 198 17 Num Deducc. Art. 42 L.I.S. 2005 - Pendiente aplicación en periodos futuros [299]
18 215 17 Num Deducc. Art. 42 L.I.S. 2006 - Deducción pendiente/generada [090]
1199 223322 1177 NNuumm DDeedduucccc. AArrtt. 4422 LL.II.SS. 22000066 - AApplliiccaaddoo eenn eessttaa lliiqquuiiddaacciióónn [[009911]]
20 249 17 Num Deducc. Art. 42 L.I.S. 2006 - Pendiente aplicación en periodos futuros [092]
21 266 17 Num Deducc. Art. 42 L.I.S. 2007 - Deducción pendiente/generada [004]
22 283 17 Num Deducc. Art. 42 L.I.S. 2007 - Aplicado en esta liquidación [005]
23 300 17 Num Deducc. Art. 42 L.I.S. 2007 - Pendiente aplicación en periodos futuros [006]
24 317 17 Num Deducc. Art. 42 L.I.S. 2008 - Deducción pendiente/generada [031]
25 334 17 Num Deducc. Art. 42 L.I.S. 2008 - Aplicado en esta liquidación [032]
26 351 17 Num Deducc. Art. 42 L.I.S. 2008 - Pendiente aplicación en periodos futuros [033]
27 368 17 Num Deducc. Art. 42 L.I.S. 2009 - Deducción pendiente/generada [022]
28 385 17 Num Deducc. Art. 42 L.I.S. 2009 - Aplicado en esta liquidación [023]
29 402 17 Num Deducc. Art. 42 L.I.S. 2009 - Pendiente aplicación en periodos futuros [024]
30 419 17 Num Deducc. Art. 42 L.I.S. 2010 - Deducción pendiente/generada [040]
31 436 17 Num Deducc. Art. 42 L.I.S. 2010 - Aplicado en esta liquidación [041]
32 453 17 Num Deducc. Art. 42 L.I.S. 2010 - Pendiente aplicación en periodos futuros [042]
33 470 17 Num Deducc. Art. 42 L.I.S. 2011 - Deducción pendiente/generada [138]
34 487 17 Num Deducc. Art. 42 L.I.S. 2011 - Aplicado en esta liquidación [139]
35 504 17 Num Deducc. Art. 42 L.I.S. 2011 - Pendiente aplicación en periodos futuros [140]
36 521 17 Num Deducc. Art. 42 L.I.S. 2012 - Deducción pendiente/generada [141]
37 538 17 Num Deducc. Art. 42 L.I.S. 2012 - Aplicado en esta liquidación [142]
38 555 17 Num Deducc. Art. 42 L.I.S. 2012 - Pendiente aplicación en periodos futuros [143]
39 572 17 Num Deducc. Art. 42 L.I.S. 2013 - Deducción pendiente/generada [188]
40 589 17 Num Deducc. Art. 42 L.I.S. 2013 - Aplicado en esta liquidación [189]
41 606 17 Num Deducc. Art. 42 L.I.S. 2013 - Pendiente aplicación en periodos futuros [190]
42 623 17 Num Deducc. Art. 36 ter Ley 43 / 1995 y 42 L.I.S. Total Deducc. - Deducción pendiente/generada [841]
43 640 17 Num Deducc. Art. 36 ter Ley 43 / 1995 y 42 L.I.S. Total Deducc. - Aplicado en esta liquidación [585]
4444 665577 1177 NNuumm DDeedduucccc.. AArrtt.. 3366 tteerr LLeeyy 4433 // 11999955 yy 4422 LL..II..SS.. TToottaall DDeedduucccc.. - PPeennddiieennttee aapplliiccaacciióónn eenn ppeerriiooddooss ffuuttuurrooss [[884433]]
45 674 17 Num Deducciones DT octava L.I.S. - 2008 Periodificación - Deducción pendiente/generada [749]
46 691 17 Num Deducciones DT octava L.I.S. - 2008 Periodificación - Aplicado en esta liquidación [750]
47 708 17 Num Deducciones DT octava L.I.S. - 2009 Periodificación - Deducción pendiente/generada [752]
48 725 17 Num Deducciones DT octava L.I.S. - 2009 Periodificación - Aplicado en esta liquidación [753]
49 742 17 Num Deducciones DT octava L.I.S. - 2009 Periodificación - Pendiente de aplicación en periodos futuros [754]
50 759 17 Num Deducciones DT octava L.I.S. - 2010 Periodificación - Deducción pendiente/generada [755]
51 776 17 Num Deducciones DT octava L.I.S. - 2010 Periodificación - Aplicado en esta liquidación [756]
52 793 17 Num Deducciones DT octava L.I.S. - 2010 Periodificación - Pendiente de aplicación en periodos futuros [757]
53 810 17 Num Deducciones DT octava L.I.S. - 2011 Periodificación - Deducción pendiente/generada [758]
54 827 17 Num Deducciones DT octava L.I.S. - 2011 Periodificación - Aplicado en esta liquidación [759]
55 844 17 Num Deducciones DT octava L.I.S. - 2011 Periodificación - Pendiente de aplicación en periodos futuros [760]
56 861 17 Num Deducciones DT octava L.I.S. - 2012 Periodificación - Deducción pendiente/generada [761]
5577 887788 1177 NNuumm DDeedduucccciioonneess DDTT ooccttaavvaa LL.II.SS. - 22001122 PPeerriiooddiiffiiccaacciióónn - AApplliiccaaddoo eenn eessttaa lliiqquuiiddaacciióónn [[776622]]
58 895 17 Num Deducciones DT octava L.I.S. - 2012 Periodificación - Pendiente de aplicación en periodos futuros [763]
59 912 17 Num Deducciones DT octava L.I.S. - 2013 Periodificación - Deducción pendiente/generada [744]
60 929 17 Num Deducciones DT octava L.I.S. - 2013 Periodificación - Aplicado en esta liquidación [745]
61 946 17 Num Deducciones DT octava L.I.S. - 2013 Periodificación - Pendiente de aplicación en periodos futuros [746]
62 963 17 Num Deducciones DT octava L.I.S. Total deducciones - Deducción pendiente/generada [764]
63 980 17 Num Deducciones DT octava L.I.S. Total deducciones - Aplicado en esta liquidación [584]
64 997 17 Num Deducciones DT octava L.I.S. Total deducciones - Pendiente de aplicación en periodos futuros [765]
65 1014 17 Num Rég. especial reserva inversiones Canarias - RIC 2009 - Importe dotación [089]
Rég. especial reserva inversiones Canarias - RIC 2009 - Inversiones previstas A B D art. 27.4 Ley 19/94 [094]
66 1031 17 Num
Rég. especial reserva inversiones Canarias - RIC 2009 - Inversiones previstas C D art. 27.4 Ley 19/94 [095]
67 1048 17 Num
6688 11006655 1177 NNum RRéégg. eessppeecciiaall rreesseerrvvaa iinnvveerrssiioonneess CCaannaarriiaass - RRIICC 22001100 - IImmppoorrttee ddoottaacciióónn [[009977]]
Rég. especial reserva inversiones Canarias - RIC 2010 - Inversiones previstas A B D art. 27.4 Ley 19/94 [098]
69 1082 17 Num
Rég. especial reserva inversiones Canarias - RIC 2010 - Inversiones previstas C D art. 27.4 Ley 19/94 [047]
70 1099 17 Num
71 1116 17 Num Rég. especial reserva inversiones Canarias - RIC 2010 - Pendiente materializar [048]
72 1133 17 Num Rég. especial reserva inversiones Canarias - RIC 2011 - Importe dotación [524]
Rég. especial reserva inversiones Canarias - RIC 2011 - Inversiones previstas A B D art. 27.4 Ley 19/94 [525]
73 1150 17 Num
Rég. especial reserva inversiones Canarias - RIC 2011 - Inversiones previstas C D art. 27.4 Ley 19/94 [526]
74 1167 17 Num
75 1184 17 Num Rég. especial reserva inversiones Canarias - RIC 2011 - Pendiente materializar [527]
76 1201 17 Num Rég. especial reserva inversiones Canarias - RIC 2012 - Importe dotación [922]
RRéégg. eessppeecciiaall rreesseerrvvaa iinnvveerrssiioonneess CCaannaarriiaass -- RRIICC 22001122 -- IInnvveerrssiioonneess pprreevviissttaass AA BB DD aarrtt. 2277.44 LLeeyy 1199//9944 [[992233]]
77 1218 17 Num
Rég. especial reserva inversiones Canarias - RIC 2012 - Inversiones previstas C D art. 27.4 Ley 19/94 [924]
78 1235 17 Num
79 1252 17 Num Rég. especial reserva inversiones Canarias - RIC 2012 - Pendiente materializar [925]
Página 29

# Pag. 30

80 1269 17 Num Rég. especial reserva inversiones Canarias - RIC 2013 - Importe dotación [927]
Rég. especial reserva inversiones Canarias - RIC 2013 - Inversiones previstas A B D art. 27.4 Ley 19/94 [928]
81 1286 17 Num
Rég. especial reserva inversiones Canarias - RIC 2013 - Inversiones previstas C D art. 27.4 Ley 19/94 [938]
82 1303 17 Num
83 1320 17 Num Rég. especial reserva inversiones Canarias - RIC 2013 - Pendiente materializar [996]
Rég. especial reserva inversiones Canarias - Invers. anticipadas futuras dotaciones RIC en 2013 - Inversiones
84 1337 17 Num previstas A B D art. 27.4 Ley 19/94 (1) [020]
Rég. especial reserva inversiones Canarias - Invers. anticipadas futuras dotaciones RIC en 2013 - Inversiones
85 1354 17 Num previstas C y D art. 27.4 Ley 19/94 [021]
86 1371 17 Num Deducciones inversión Canarias - Activos fijos 2008 - Deducción pendiente/generada [854]
87 1388 17 Num Deducciones inversión Canarias - Activos fijos 2008 - Aplicado en esta liquidación [855]
88 1405 17 Num Deducciones inversión Canarias - Activos fijos 2009 - Deducción pendiente/generada [857]
89 1422 17 Num Deducciones inversión Canarias - Activos fijos 2009 - Aplicado en esta liquidación [858]
90 1439 17 Num Deducciones inversión Canarias - Activos fijos 2009 - Pendiente de aplicación en periodos futuros [859]
91 1456 17 Num Deducciones inversión Canarias - Activos fijos 2010 - Deducción pendiente/generada [860]
92 1473 17 Num Deducciones inversión Canarias - Activos fijos 2010 - Aplicado en esta liquidación [861]
93 1490 17 Num Deducciones inversión Canarias - Activos fijos 2010 - Pendiente de aplicación en periodos futuros [862]
94 1507 17 Num Deducciones inversión Canarias - Activos fijos 2011 - Deducción pendiente/generada [863]
95 1524 17 Num Deducciones inversión Canarias - Activos fijos 2011 - Aplicado en esta liquidación [864]
96 1541 17 Num Deducciones inversión Canarias - Activos fijos 2011 - Pendiente de aplicación en periodos futuros [865]
97 1558 17 Num Deducciones inversión Canarias - Activos fijos 2012 - Deducción pendiente/generada [883]
98 1575 17 Num Deducciones inversión Canarias - Activos fijos 2012 - Aplicado en esta liquidación [884]
99 1592 17 Num Deducciones inversión Canarias - Activos fijos 2012 - Pendiente de aplicación en periodos futuros [885]
100 1609 17 Num Deducciones inversión Canarias - Inversiones Canarias 1997 - Deducción pendiente/generada [088]
110011 11662266 1177 NNuumm DDeedduucccciioonneess iinnvveerrssiióónn CCaannaarriiaass - IInnvveerrssiioonneess CCaannaarriiaass 11999977 - AApplliiccaaddoo eenn eessttaa lliiqquuiiddaacciióónn [[556644]]
Deducciones inversión Canarias - Inversiones Canarias 1997 - Pendiente de aplicación en periodos futuros [801]
102 1643 17 Num
103 1660 17 Num Deducciones inversión Canarias - Inversiones Canarias 1998 - Deducción pendiente/generada [194]
104 1677 17 Num Deducciones inversión Canarias - Inversiones Canarias 1998 - Aplicado en esta liquidación [195]
Deducciones inversión Canarias - Inversiones Canarias 1998 - Pendiente de aplicación en periodos futuros [196]
105 1694 17 Num
106 1711 17 Num Deducciones inversión Canarias - Inversiones Canarias 1999 - Deducción pendiente/generada [868]
107 1728 17 Num Deducciones inversión Canarias - Inversiones Canarias 1999 - Aplicado en esta liquidación [869]
Deducciones inversión Canarias - Inversiones Canarias 1999 - Pendiente de aplicación en periodos futuros [834]
108 1745 17 Num
109 1762 17 Num Deducciones inversión Canarias - Inversiones Canarias 2000 - Deducción pendiente/generada [871]
110 1779 17 Num Deducciones inversión Canarias - Inversiones Canarias 2000 - Aplicado en esta liquidación [872]
Deducciones inversión Canarias - Inversiones Canarias 2000 - Pendiente de applicación en pperiodos futuros [[873]]
111 1796 17 Num
112 1813 17 Num Deducciones inversión Canarias - Inversiones Canarias 2001 - Deducción pendiente/generada [874]
113 1830 17 Num Deducciones inversión Canarias - Inversiones Canarias 2001 - Aplicado en esta liquidación [875]
Deducciones inversión Canarias - Inversiones Canarias 2001 - Pendiente de aplicación en periodos futuros [876]
114 1847 17 Num
115 1864 17 Num Deducciones inversión Canarias - Inversiones Canarias 2002 - Deducción pendiente/generada [877]
116 1881 17 Num Deducciones inversión Canarias - Inversiones Canarias 2002 - Aplicado en esta liquidación [878]
Deducciones inversión Canarias - Inversiones Canarias 2002 - Pendiente de aplicación en periodos futuros [879]
117 1898 17 Num
118 1915 17 Num Deducciones inversión Canarias - Inversiones Canarias 2003 - Deducción pendiente/generada [880]
119 1932 17 Num Deducciones inversión Canarias - Inversiones Canarias 2003 - Aplicado en esta liquidación [881]
Deducciones inversión Canarias - Inversiones Canarias 2003 - Pendiente de aplicación en periodos futuros [882]
120 1949 17 Num
121 1966 17 Num Deducciones inversión Canarias - Inversiones Canarias 2004 - Deducción pendiente/generada [866]
122 1983 17 Num Deducciones inversión Canarias - Inversiones Canarias 2004 - Aplicado en esta liquidación [867]
Deducciones inversión Canarias - Inversiones Canarias 2004 - Pendiente de aplicación en periodos futuros [870]
123 2000 17 Num
124 2017 17 Num Deducciones inversión Canarias - Inversiones Canarias 2005 - Deducción pendiente/generada [939]
125 2034 17 Num Deducciones inversión Canarias - Inversiones Canarias 2005 - Aplicado en esta liquidación [940]
Deducciones inversión Canarias - Inversiones Canarias 2005 - Pendiente de aplicación en periodos futuros [941]
126 2051 17 Num
127 2068 17 Num Deducciones inversión Canarias - Inversiones Canarias 2006 - Deducción pendiente/generada [191]
128 2085 17 Num Deducciones inversión Canarias - Inversiones Canarias 2006 - Aplicado en esta liquidación [192]
Deducciones inversión Canarias - Inversiones Canarias 2006 - Pendiente de aplicación en periodos futuros [193]
129 2102 17 Num
130 2119 17 Num Deducciones inversión Canarias - Inversiones Canarias 2007 - Deducción pendiente/generada [613]
131 2136 17 Num Deducciones inversión Canarias - Inversiones Canarias 2007 - Aplicado en esta liquidación [614]
Deducciones inversión Canarias - Inversiones Canarias 2007 - Pendiente de aplicación en periodos futuros [701]
132 2153 17 Num
133 2170 17 Num Deducciones inversión Canarias - Inversiones Canarias 2008 - Deducción pendiente/generada [200]
134 2187 17 Num Deducciones inversión Canarias - Inversiones Canarias 2008 - Aplicado en esta liquidación [257]
Deducciones inversión Canarias - Inversiones Canarias 2008 - Pendiente de aplicación en periodos futuros [011]
135 2204 17 Num
136 2221 17 Num Deducciones inversión Canarias - Inversiones Canarias 2009 - Deducción pendiente/generada [037]
137 2238 17 Num Deducciones inversión Canarias - Inversiones Canarias 2009 - Aplicado en esta liquidación [038]
Deducciones inversión Canarias - Inversiones Canarias 2009 - Pendiente de aplicación en periodos futuros [039]
138 2255 17 Num
139 2272 17 Num Deducciones inversión Canarias - Inversiones Canarias 2010 - Deducción pendiente/generada [044]
140 2289 17 Num Deducciones inversión Canarias - Inversiones Canarias 2010 - Aplicado en esta liquidación [045]
Deducciones inversión Canarias - Inversiones Canarias 2010 - Pendiente de aplicación en periodos futuros [046]
141 2306 17 Num
142 2323 17 Num Deducciones inversión Canarias - Inversiones Canarias 2011 - Deducción pendiente/generada [528]
143 2340 17 Num Deducciones inversión Canarias - Inversiones Canarias 2011 - Aplicado en esta liquidación [529]
Deducciones inversión Canarias - Inversiones Canarias 2011 - Pendiente de aplicación en periodos futuros [530]
144 2357 17 Num
145 2374 17 Num Deducciones inversión Canarias - Inversiones Canarias 2012 - Deducción pendiente/generada [144]
146 2391 17 Num Deducciones inversión Canarias - Inversiones Canarias 2012 - Aplicado en esta liquidación [145]
Deducciones inversión Canarias - Inversiones Canarias 2012 - Pendiente de aplicación en periodos futuros [146]
147 2408 17 Num
148 2425 17 Num Deducciones inversión Canarias - Inversiones Canarias 2013 - Deducción pendiente/generada [147]
149 2442 17 Num Deducciones inversión Canarias - Inversiones Canarias 2013 - Aplicado en esta liquidación [148]
Deducciones inversión Canarias - Inversiones Canarias 2013 - Pendiente de aplicación en periodos futuros [149]
115500 22445599 1177 NNum
151 2476 17 Num Deducciones inversión Canarias - Activos fijos 2013 - Deducción pendiente/generada [852]
152 2493 17 Num Deducciones inversión Canarias - Activos fijos 2013 - Aplicado en esta liquidación [853]
153 2510 17 Num Deducciones inversión Canarias - Activos fijos 2013 - Pendiente de aplicación en periodos futuros [856]
Página 30

# Pag. 31

154 2527 17 Num Deducciones inversión Canarias - Total deducciones - Deducción pendiente/generada [886]
155 2544 17 Num Deducciones inversión Canarias - Total deducciones - Aplicado en esta liquidación [590]
Deducciones inversión Canarias - Total deducciones - Pendiente de aplicación en periodos futuros [887]
156 2561 17 Num
157 2578 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200160>"
Total: 2587
Página 31

# Pag. 32

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas
vers. 1.0
constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "170"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
6 11 17 Num Deducc. para incentivar determ.actividades - 1997 Suma deducciones - Deducción pendiente/generada [842]
7 28 17 Num Deducc. para incentivar determ.actividades - 1997 Suma deducciones - Aplicado en esta liquidación [844]
8 45 17 Num Deducc. para incentivar determ.actividades - 1997 Suma deducciones - Pendiente de aplicación en periodos futuros [845]
9 62 17 Num Deducc. para incentivar determ.actividades - 1998 Suma deducciones - Deducción pendiente/generada [768]
10 79 17 Num Deducc. para incentivar determ.actividades - 1998 Suma deducciones - Aplicado en esta liquidación [769]
11 96 17 Num Deducc. para incentivar determ.actividades - 1998 Suma deducciones - Pendiente de aplicación en periodos futuros [770]
12 113 17 Num Deducc. para incentivar determ.actividades - 1999 Suma deducciones - Deducción pendiente/generada [774]
13 130 17 Num Deducc. para incentivar determ.actividades - 1999 Suma deducciones - Aplicado en esta liquidación [775]
14 147 17 Num Deducc. para incentivar determ.actividades - 1999 Suma deducciones - Pendiente de aplicación en periodos futuros [776]
15 164 17 Num Deducc. para incentivar determ.actividades - 2000 Suma deducciones - Deducción pendiente/generada [780]
16 181 17 Num Deducc. para incentivar determ.actividades - 2000 Suma deducciones - Aplicado en esta liquidación [781]
17 198 17 Num Deducc. para incentivar determ.actividades - 2000 Suma deducciones - Pendiente de aplicación en periodos futuros [782]
18 215 17 Num Deducc. para incentivar determ.actividades - 2001 Suma deducciones - Deducción pendiente/generada [786]
19 232 17 Num Deducc. para incentivar determ.actividades - 2001 Suma deducciones - Aplicado en esta liquidación [787]
20 249 17 Num Deducc. para incentivar determ.actividades - 2001 Suma deducciones - Pendiente de aplicación en periodos futuros [788]
21 266 17 Num Deducc. para incentivar determ.actividades - 2002 Suma deducciones - Deducción pendiente/generada [766]
22 283 17 Num Deducc. para incentivar determ.actividades - 2002 Suma deducciones - Aplicado en esta liquidación [767]
23 300 17 Num Deducc. para incentivar determ.actividades - 2002 Suma deducciones - Pendiente de aplicación en periodos futuros [833]
24 317 17 Num Deducc. para incentivar determ.actividades - 2003 Suma deducciones - Deducción pendiente/generada [198]
25 334 17 Num Deducc. para incentivar determ.actividades - 2003 Suma deducciones - Aplicado en esta liquidación [896]
26 351 17 Num Deducc. para incentivar determ.actividades - 2003 Suma deducciones - Pendiente de aplicación en periodos futuros [897]
27 368 17 Num Deducc. para incentivar determ.actividades - 2004 Suma deducciones - Deducción pendiente/generada [288]
28 385 17 Num Deducc. para incentivar determ.actividades - 2004 Suma deducciones - Aplicado en esta liquidación [289]
29 402 17 Num Deducc. para incentivar determ.actividades - 2004 Suma deducciones - Pendiente de aplicación en periodos futuros [290]
30 419 17 Num Deducc. para incentivar determ.actividades - 2005 Suma deducciones - Deducción pendiente/generada [466]
31 436 17 Num Deducc. para incentivar determ.actividades - 2005 Suma deducciones - Aplicado en esta liquidación [467]
32 453 17 Num Deducc. para incentivar determ.actividades - 2005 Suma deducciones - Pendiente de aplicación en periodos futuros [468]
33 470 17 Num Deducc. para incentivar determ.actividades - 2006 SSuma deducciones - Deduccióón pendiente//generada [061]
34 487 17 Num Deducc. para incentivar determ.actividades - 2006 Suma deducciones - Aplicado en esta liquidación [498]
35 504 17 Num Deducc. para incentivar determ.actividades - 2006 Suma deducciones - Pendiente de aplicación en periodos futuros [586]
36 521 17 Num Deducc. para incentivar determ.actividades - 2007 Suma deducciones - Deducción pendiente/generada [472]
37 538 17 Num Deducc. para incentivar determ.actividades - 2007 Suma deducciones - Aplicado en esta liquidación [473]
38 555 17 Num Deducc. para incentivar determ.actividades - 2007 Suma deducciones - Pendiente de aplicación en periodos futuros [478]
39 572 17 Num Deducc. para incentivar determ.actividades - 2008 Suma deducciones - Deducción pendiente/generada [180]
40 589 17 Num Deducc. para incentivar determ.actividades - 2008 Suma deducciones - Aplicado en esta liquidación [181]
41 606 17 Num Deducc. para incentivar determ.actividades - 2008 Suma deducciones - Pendiente de aplicación en periodos futuros [182]
42 623 17 Num Deducc. para incentivar determ.actividades - 2009 Suma deducciones - Deducción pendiente/generada [531]
43 640 17 Num Deducc. para incentivar determ.actividades - 2009 Suma deducciones - Aplicado en esta liquidación [532]
44 657 17 Num Deducc. para incentivar determ.actividades - 2009 Suma deducciones - Pendiente de aplicación en periodos futuros [533]
45 674 17 Num Deducc. para incentivar determ.actividades - 2010 Suma deducciones - Deducción pendiente/generada [945]
46 691 17 Num DDedducc. para iincentiivar ddeterm.actiiviiddaddes - 22001100 SSuma ddedducciiones - AAplliicaddo en esta lliiquiiddaciióón [[994466]]
47 708 17 Num Deducc. para incentivar determ.actividades - 2010 Suma deducciones - Pendiente de aplicación en periodos futuros [947]
48 725 17 Num Deducc. para incentivar determ.actividades - 2011 Suma deducciones - Deducción pendiente/generada [960]
49 742 17 Num Deducc. para incentivar determ.actividades - 2011 Suma deducciones - Aplicado en esta liquidación [961]
50 759 17 Num Deducc. para incentivar determ.actividades - 2011 Suma deducciones - Pendiente de aplicación en periodos futuros [962]
51 776 17 Num Deducc. para incentivar determ.actividades - 2012 Suma deducciones - Deducción pendiente/generada [183]
52 793 17 Num Deducc. para incentivar determ.actividades - 2012 Suma deducciones - Aplicado en esta liquidación [185]
53 810 17 Num Deducc. para incentivar determ.actividades - 2012 Suma deducciones - Pendiente de aplicación en periodos futuros [186]
Deducc. para incentivar determ.actividades - 2013 Inv.protección medio ambiente - Deducción pendiente/generada [792]
54 827 17 Num
Deducc. para incentivar determ.actividades - 2013 Inv. protección medio ambiente - Aplicado en esta liquidación [793]
55 844 17 Num
Deducc. para incentivar determ.actividades - 2013 Inv. protección medio ambiente - Pendiente de aplicación en periodos
5566 886611 1177 NNuumm ffuuttuurrooss [[779944]]
Deducc. para incentivar determ.actividades - 2013 Deducción creación empleo trabajadores discapacidad - Deducción
57 878 17 Num pendiente/generada [795]
Deducc. para incentivar determ.actividades - 2013 Deducción creación empleo trabajadores discapacidad - Deducción
58 895 17 Num pendiente/generada [796]
Deducc. para incentivar determ.actividades - 2013 Deducción creación empleo trabajadores discapacidad - Deducción
59 912 17 Num pendiente/generada [797]
60 929 17 Num Deducc. para incentivar determ.actividades - 2013 Gastos investigación y desarrollo - Deducción pendiente/generada [798]
61 946 17 Num Deducc. para incentivar determ.actividades - 2013 Gastos investigación y desarrollo - Aplicado en esta liquidación [799]
Deducc. para incentivar determ.actividades - 2013 Gastos investigación y desarrollo - Pendiente de aplicación en periodos
62 963 17 Num futuros [800]
63 980 17 Num Deducc. para incentivar determ.actividades - 2013 Gastos innovación tecnológica - Deducción pendiente/generada [096]
Deducc. para incentivar determ.actividades - 2013 Gastos innovación tecnológica - Aplicado en esta liquidación [698]
64 997 17 Num
DDedducc. para iincenttiivar ddetterm.acttiiviiddaddes - 22001133 GGasttos iinnovaciióón ttecnollóógiica - PPenddiientte dde aplliicaciióón en periioddos
65 1014 17 Num futuros [713]
Deducc. para incentivar determ.actividades - 2013 Deducción inversión beneficios - Deducción pendiente/generada [549]
66 1031 17 Num
Deducc. para incentivar determ.actividades - 2013 Deducción inversión beneficios - Aplicado en esta liquidación [888]
67 1048 17 Num
Deducc. para incentivar determ.actividades - 2013 Deducción inversión beneficios - Pendiente de aplicación en periodos
68 1065 17 Num futuros [889]
Deducc. para incentivar determ.actividades - 2013 Produc. cinematográficas - Deducción pendiente/generada [807]
69 1082 17 Num
Deducc. para incentivar determ.actividades - 2013 Produc. cinematográficas - Aplicado en esta liquidación [808]
70 1099 17 Num
Deducc. para incentivar determ.actividades - 2013 Produc. cinematográficas - Pendiente de aplicación en periodos futuros
71 1116 17 Num [809]
Deducc. para incentivar determ.actividades - 2013 Bienes interés cultural - Deducción pendiente/generada [810]
72 1133 17 Num
73 1150 17 Num Deducc. para incentivar determ.actividades - 2013 Bienes interés cultural - Aplicado en esta liquidación [811]
Deducc. para incentivar determ.actividades - 2013 Bienes interés cultural - Pendiente de aplicación en periodos futuros
74 1167 17 Num [812]
Página 32

# Pag. 33

Deducc. para incentivar determ.actividades - 2013 Gastos formación profesional - Deducción pendiente/generada [816]
75 1184 17 Num
Deducc. para incentivar determ.actividades - 2013 Gastos formación profesional - Aplicado en esta liquidación [817]
76 1201 17 Num
Deducc. para incentivar determ.actividades - 2013 Gastos formación profesional - Pendiente de aplicación en periodos
77 1218 17 Num futuros [818]
78 1235 17 Num Deducc. para incentivar determ.actividades - 2013 Edición libros - Deducción pendiente/generada [819]
79 1252 17 Num Deducc. para incentivar determ.actividades - 2013 Edición libros - Aplicado en esta liquidación [820]
Deducc. para incentivar determ.actividades - 2013 Edición libros - Pendiente de aplicación en periodos futuros [821]
80 1269 17 Num
Deducc. para incentivar determ.actividades - 2013 Creación empleo menores 30 años - Deducción pendiente/generada
81 1286 17 Num [963]
Deducc. para incentivar determ.actividades - 2013 Creación empleo menores 30 años - Aplicado en esta liquidación [964]
8822 11330033 1177 NNuumm
Deducc. para incentivar determ.actividades - 2013 Creación empleo menores 30 años - Pendiente de aplicación en periodos
83 1320 17 Num futuros [965]
Deducc. para incentivar determ.actividades - 2013 Creación empleo contratación desempleados con prestación desempleo -
84 1337 17 Num Deducción pendiente/generada [931]
Deducc. para incentivar determ.actividades - 2013 Creación empleo contratación desempleados con prestación desempleo -
85 1354 17 Num Aplicado en esta liquidación [502]
Deducc. para incentivar determ.actividades - 2013 Creación empleo contratación desempleados con prestación desempleo -
86 1371 17 Num Pendiente de aplicación en periodos futuros [751]
Deducc. para incentivar determ.actividades - 2013 Conmemoración Milenio fundación Reino de Granada - Deducción
87 1388 17 Num pendiente/generada [966]
Deducc. para incentivar determ.actividades - 2013 Conmemoración Milenio fundación Reino de Granada - Aplicado en esta
88 1405 17 Num liquidación [967]
Deducc. para incentivar determ.actividades - 2013 Conmemoración Milenio fundación Reino de Granada - Pendiente de
8899 11442222 1177 NNuumm aapplliiccaacciióónn eenn ppeerriiooddooss ffuuttuurrooss [[996688]]
90 1439 17 Num Deducc. para incentivar determ.actividades - 2013 Alicante 2011 - Deducción pendiente/generada [972]
91 1456 17 Num Deducc. para incentivar determ.actividades - 2013 Alicante 2011 - Aplicado en esta liquidación [973]
Deducc. para incentivar determ.actividades - 2013 Alicante 2011 - Pendiente de aplicación en periodos futuros [975]
92 1473 17 Num
93 1490 17 Num Deducc. para incentivar determ.actividades - 2013 Mundobasket 2014 - Deducción pendiente/generada [540]
94 1507 17 Num Deducc. para incentivar determ.actividades - 2013 Mundobasket 2014 - Aplicado en esta liquidación [541]
95 1524 17 Num Deducc. para incentivar determ.actividades - 2013 Mundobasket 2014 - Pendiente de aplicación en periodos futuros [542]
Deducc. para incentivar determ.actividades - 2013 Campeonato Mundo Balonmano Masculino 2013 - Deducción
96 1541 17 Num pendiente/generada [543]
Deducc. para incentivar determ.actividades - 2013 Campeonato Mundo Balonmano Masculino 2013 - Aplicado en esta
97 1558 17 Num liquidación [544]
Deducc. para incentivar determ.actividades - 2013 Campeonato Mundo Balonmano Masculino 2013 - Pendiente de
98 1575 17 Num aplicación en periodos futuros [545]
DDeedduucccc. ppaarraa iinncceennttiivvaarr ddeetteerrmm.aaccttiivviiddaaddeess - 22001133 IIVV CCeenntteennaarriioo ddeell ffaalllleecciimmiieennttoo ddee EEll GGrreeccoo - DDeedduucccciióónn
99 1592 17 Num pendiente/generada [901]
Deducc. para incentivar determ.actividades - 2013 IV Centenario del fallecimiento de El Greco - Aplicado en esta liquidación
100 1609 17 Num [902]
Deducc. para incentivar determ.actividades - 2013 IV Centenario del fallecimiento de El Greco - Pendiente de aplicación en
101 1626 17 Num periodos futuros [903]
Deducc. para incentivar determ.actividades - 2013 Vitoria-Gasteiz Capital Verde Europea 2012 - Deducción
102 1643 17 Num pendiente/generada [063]
Deducc. para incentivar determ.actividades - 2013 Vitoria-Gasteiz Capital Verde Europea 2012 - Aplicado en esta
103 1660 17 Num liquidación [064]
Deducc. para incentivar determ.actividades - 2013 Vitoria-Gasteiz Capital Verde Europea 2012 - Pendiente de aplicación en
104 1677 17 Num periodos futuros [065]
Deducc. para incentivar determ.actividades - 2013 Campeonato del Mundo de Vela Santander 2014 - Deducción
105 1694 17 Num pendiente/generada [067]
DDeedduucccc. ppaarraa iinncceennttiivvaarr ddeetteerrmm.aaccttiivviiddaaddeess - 22001133 CCaammppeeoonnaattoo ddeell MMuunnddoo ddee VVeellaa SSaannttaannddeerr 22001144 - AApplliiccaaddoo eenn eessttaa
106 1711 17 Num liquidación [068]
Deducc. para incentivar determ.actividades - 2013 Campeonato del Mundo de Vela Santander 2014 - Pendiente de
107 1728 17 Num aplicación en periodos futuros [069]
Deducc. para incentivar determ.actividades - 2013 Programa "El árbol es vida" - Deducción pendiente/generada [070]
108 1745 17 Num
Deducc. para incentivar determ.actividades - 2013 Programa "El árbol es vida" - Aplicado en esta liquidación [072]
109 1762 17 Num
Deducc. para incentivar determ.actividades - 2013 Programa "El árbol es vida" - Pendiente de aplicación en periodos futuros
110 1779 17 Num [073]
Deducc. para incentivar determ.actividades - 2013 Año de España en Japón - Deducción pendiente/generada [075]
111 1796 17 Num
Deducc. para incentivar determ.actividades - 2013 Año de España en Japón - Aplicado en esta liquidación [076]
112 1813 17 Num
DDeedduucccc. ppaarraa iinncceennttiivvaarr ddeetteerrmm.aaccttiivviiddaaddeess - 22001133 AAññoo ddee EEssppaaññaa eenn JJaappóónn - PPeennddiieennttee ddee aapplliiccaacciióónn eenn ppeerriiooddooss ffuuttuurrooss
113 1830 17 Num [077]
Deducc. para incentivar determ.actividades - 2013 Plan Director recuperación Patimonio Cultural Lorca - Deducción
114 1847 17 Num pendiente/generada [078]
Deducc. para incentivar determ.actividades - 2013 Plan Director recuperación Patimonio Cultural Lorca - Aplicado en esta
115 1864 17 Num liquidación [079]
Deducc. para incentivar determ.actividades - 2013 Plan Director recuperación Patimonio Cultural Lorca - Pendiente de
116 1881 17 Num aplicación en periodos futuros [080]
Deducc. para incentivar determ.actividades - 2013 Universiada de Invierno Granada 2015 - Deducción pendiente/generada
117 1898 17 Num [085]
Deducc. para incentivar determ.actividades - 2013 Universiada de Invierno Granada 2015 - Aplicado en esta liquidación
118 1915 17 Num [086]
Deducc. para incentivar determ.actividades - 2013 Universiada de Invierno Granada 2015 - Pendiente de aplicación en
119 1932 17 Num periodos futuros [087]
DDeedduucccc. ppaarraa iinncceennttiivvaarr ddeetteerrmm.aaccttiivviiddaaddeess - 22001133 CCaammppeeoonnaattoo ddeell MMuunnddoo ddee CCiicclliissmmoo eenn CCaarrrreetteerraa PPoonnffeerrrraaddaa 22001144 -
120 1949 17 Num Deducción pendiente/generada [093]
Deducc. para incentivar determ.actividades - 2013 Campeonato del Mundo de Ciclismo en Carretera Ponferrada 2014 -
121 1966 17 Num Aplicado en esta liquidación [057]
Deducc. para incentivar determ.actividades - 2013 Campeonato del Mundo de Ciclismo en Carretera Ponferrada 2014 -
122 1983 17 Num Pendiente de aplicación en periodos futuros [058]
Deducc. para incentivar determ.actividades - 2013 Barcelona World Jumping Challenge - Deducción pendiente/generada
123 2000 17 Num [207]
Deducc. para incentivar determ.actividades - 2013 Barcelona World Jumping Challenge - Aplicado en esta liquidación [208]
124 2017 17 Num
Deducc. para incentivar determ.actividades - 2013 Barcelona World Jumping Challenge - Pendiente de aplicación en
125 2034 17 Num periodos futuros [209]
Deducc. para incentivar determ.actividades - 2013 Campeonato del Mundo Natación Barcelona 2013 - Deducción
126 2051 17 Num pendiente/generada [210]
DDeedduucccc. ppaarraa iinncceennttiivvaarr ddeetteerrmm.aaccttiivviiddaaddeess - 22001133 CCaammppeeoonnaattoo ddeell MMuunnddoo NNaattaacciióónn BBaarrcceelloonnaa 22001133 - AApplliiccaaddoo eenn eessttaa
127 2068 17 Num liquidación [211]
Deducc. para incentivar determ.actividades - 2013 Campeonato del Mundo Natación Barcelona 2013 - Pendiente de
128 2085 17 Num aplicación en periodos futuros [212]
129 2102 17 Num Deducc. para incentivar determ.actividades - 2013 Barcelona Mobile World Capital - Deducción pendiente/generada [213]
Página 33

# Pag. 34

Deducc. para incentivar determ.actividades - 2013 Barcelona Mobile World Capital - Aplicado en esta liquidación [214]
130 2119 17 Num
Deducc. para incentivar determ.actividades - 2013 Barcelona Mobile World Capital - Pendiente de aplicación en periodos
131 2136 17 Num futuros [215]
132 2153 17 Num Deducc. para incentivar determ.actividades - 2013 3ª Edición Barcelona World Race - Deducción pendiente/generada [216]
Deducc. para incentivar determ.actividades - 2013 3ª Edición Barcelona World Race - Aplicado en esta liquidación [217]
133 2170 17 Num
Deducc. para incentivar determ.actividades - 2013 3ª Edición Barcelona World Race - Pendiente de aplicación en periodos
134 2187 17 Num futuros [218]
Deducc. para incentivar determ.actividades - 2013 Campeonato del Mundo Tiro Olímpico "Las Gabias" - Deducción
135 2204 17 Num pendiente/generada [222]
Deducc. para incentivar determ.actividades - 2013 Campeonato del Mundo Tiro Olímpico "Las Gabias" - Aplicado en esta
136 2221 17 Num liquidación [223]
DDeedduucccc.. ppaarraa iinncceennttiivvaarr ddeetteerrmm..aaccttiivviiddaaddeess - 22001133 CCaammppeeoonnaattoo ddeell MMuunnddoo TTiirroo OOllíímmppiiccoo "LLaass GGaabbiiaass" - PPeennddiieennttee ddee
137 2238 17 Num aplicación en periodos futuros [224]
Deducc. para incentivar determ.actividades - 2013 Año Santo Jubilar Mariano 2012-2013 en Almonte - Deducción
138 2255 17 Num pendiente/generada [240]
Deducc. para incentivar determ.actividades - 2013 Año Santo Jubilar Mariano 2012-2013 en Almonte - Aplicado en esta
139 2272 17 Num liquidación [241]
Deducc. para incentivar determ.actividades - 2013 Año Santo Jubilar Mariano 2012-2013 en Almonte - Pendiente de
140 2289 17 Num aplicación en periodos futuros [242]
Deducc. para incentivar determ.actividades - 2013 2014 Año Internacional Dieta Mediterránea - Deducción
141 2306 17 Num pendiente/generada [243]
Deducc. para incentivar determ.actividades - 2013 2014 Año Internacional Dieta Mediterránea - Aplicado en esta liquidación
142 2323 17 Num [244]
Deducc. para incentivar determ.actividades - 2013 2014 Año Internacional Dieta Mediterránea - Pendiente de aplicación en
143 2340 17 Num periodos futuros [245]
DDeedduucccc.. ppaarraa iinncceennttiivvaarr ddeetteerrmm..aaccttiivviiddaaddeess - 22001133 CCaannddiiddaattuurraa MMaaddrriidd 22002200 - DDeedduucccciióónn ppeennddiieennttee//ggeenneerraaddaa [[224466]]
144 2357 17 Num
Deducc. para incentivar determ.actividades - 2013 Candidatura Madrid 2020 - Aplicado en esta liquidación [247]
145 2374 17 Num
Deducc. para incentivar determ.actividades - 2013 Candidatura Madrid 2020 - Pendiente de aplicación en periodos futuros
146 2391 17 Num [248]
Deducc. para incentivar determ.actividades - 2013 Programa preparación deportistas españoles juegos "Río de Janeiro
147 2408 17 Num 2016" - Deducción pendiente/generada [204]
Deducc. para incentivar determ.actividades - 2013 Programa preparación deportistas españoles juegos "Río de Janeiro
148 2425 17 Num 2016" - Aplicado en esta liquidación [205]
Deducc. para incentivar determ.actividades - 2013 Programa preparación deportistas españoles juegos "Río de Janeiro
149 2442 17 Num 2016" - Pendiente de aplicación en periodos futuros [206]
Deducc. para incentivar determ.actividades - 2013 VIII Centenario Peregrinación San Francisco de Asís a Santiago de
150 2459 17 Num Compostela - Deducción pendiente/generada [219]
DDeedduucccc.. ppaarraa iinncceennttiivvaarr ddeetteerrmm..aaccttiivviiddaaddeess - 22001133 VVIIIIII CCeenntteennaarriioo PPeerreeggrriinnaacciióónn SSaann FFrraanncciissccoo ddee AAssííss aa SSaannttiiaaggoo ddee
151 2476 17 Num Compostela - Aplicado en esta liquidación [220]
Deducc. para incentivar determ.actividades - 2013 VIII Centenario Peregrinación San Francisco de Asís a Santiago de
152 2493 17 Num Compostela - Pendiente de aplicación en periodos futuros [221]
Deducc. para incentivar determ.actividades - 2013 V Centenario del Nacimiento Santa Teresa Avila 2015 - Deducción
153 2510 17 Num pendiente/generada [228]
Deducc. para incentivar determ.actividades - 2013 V Centenario del Nacimiento Santa Teresa Avila 2015 - Aplicado en
154 2527 17 Num esta liquidación [229]
Deducc. para incentivar determ.actividades - 2013 V Centenario del Nacimiento Santa Teresa Avila 2015 - Pendiente de
155 2544 17 Num aplicación en periodos futuros [230]
Deducc. para incentivar determ.actividades - 2013 Año Junipero Serra 2013 - Deducción pendiente/generada [231]
156 2561 17 Num
157 2578 17 Num Deducc. para incentivar determ.actividades - 2013 Año Junipero Serra 2013 - Aplicado en esta liquidación [232]
Deducc. para incentivar determ.actividades - 2013 Año Junipero Serra 2013 - Pendiente de aplicación en periodos futuros
115588 22559955 1177 NNuumm [[223333]]
Deducc. para incentivar determ.actividades - 2013 Año Santo Jubilar Mariano a celebrar ciudad de Sevilla - Deducción
159 2612 17 Num pendiente/generada [234]
Deducc. para incentivar determ.actividades - 2013 Año Santo Jubilar Mariano a celebrar ciudad de Sevilla - Aplicado en
160 2629 17 Num esta liquidación [235]
Deducc. para incentivar determ.actividades - 2013 Año Santo Jubilar Mariano a celebrar ciudad de Sevilla - Pendiente de
161 2646 17 Num aplicación en periodos futuros [236]
Deducc. para incentivar determ.actividades - 2013 Vuelta al mundo a vela Alicante 2014 - Deducción pendiente/generada
162 2663 17 Num [237]
Deducc. para incentivar determ.actividades - 2013 Vuelta al mundo a vela Alicante 2014 - Aplicado en esta liquidación [238]
163 2680 17 Num
Deducc. para incentivar determ.actividades - 2013 Vuelta al mundo a vela Alicante 2014 - Pendiente de aplicación en
164 2697 17 Num periodos futuros [239]
Deducc. para incentivar determ.actividades - 2013 Diferimiento Deducciones - Deducción pendiente/generada [828]
116655 22771144 1177 NNuumm
Deducc. para incentivar determ.actividades - 2013 Diferimiento deducciones - Aplicado en esta liquidación [829]
166 2731 17 Num
Deducc. para incentivar determ.actividades - 2013 Diferimiento deducciones - Pendiente de aplicación en periodos futuros
167 2748 17 Num [830]
Deducc. para incentivar determ.actividades - Total deducciones programas apoyo acontecimientos de excepcional interés
168 2765 17 Num público - Deducción pendiente/generada [634]
Deducc. para incentivar determ.actividades - Total deducciones programas apoyo acontecimientos de excepcional interés
169 2782 17 Num público - Aplicado en esta liquidación [635]
Deducc. para incentivar determ.actividades - Total deducciones programas apoyo acontecimientos de excepcional interés
170 2799 17 Num público - Pendiente de aplicación en periodos futuros [636]
Deducc. para incentivar determ.actividades - Total deducciones Cap.IV Tít.VI - Deducción pendiente/generada [831]
171 2816 17 Num
Deducc. para incentivar determ.actividades - Total deducciones Cap.IV Tít.VI - Aplicado en esta liquidación [588]
117722 22883333 1177 NNuumm
Deducc. para incentivar determ.actividades - Total deducciones Cap.IV Tít.VI - Pendiente de aplicación en periodos futuros
173 2850 17 Num [832]
174 2867 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200170>"
Total: 2876
Página 34

# Pag. 35

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "180"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NNuumm DDeedduucccciioonneess II++DD++ii eexxcclluuiiddaass ddee llíímmiittee - 22001133 IInnvveessttiiggaacciióónn yy ddeessaarrrroolllloo - DDeedduucccciióónn ggeenneerraaddaa [[991188]]
7 28 17 Num Deducciones I+D+i excluidas de límite - 2013 Investigación y desarrollo - Deducción reducida [919]
Deducciones I+D+i excluidas de límite - 2013 Investigación y desarrollo - Importe deducible en cuota [574]
8 45 17 Num
Deducciones I+D+i excluidas de límite - 2013 Investigación y desarrollo - Pendiente insuficiencia cuota [580]
9 62 17 Num
10 79 17 Num Deducciones I+D+i excluidas de límite - 2013 Innovación tecnológica - Deducción generada [589]
11 96 17 Num Deducciones I+D+i excluidas de límite - 2013 Innovación tecnológica - Deducción reducida [976]
Deducciones I+D+i excluidas de límite - 2013 Innovación tecnológica - Importe deducible en cuota [977]
12 113 17 Num
Deducciones I+D+i excluidas de límite - 2013 Innovación tecnológica - Pendiente insuficiencia cuota [978]
13 130 17 Num
14 147 17 Num Deducciones I+D+i excluidas de límite - Total - Deducción generada [517]
1155 116644 1177 NNum DDeedducccciioonneess II++DD++ii eexcclluiiddaass ddee llíímmiittee - TToottaall - DDeedducccciióónn rreedducciiddaa [[008811]]
16 181 17 Num Deducciones I+D+i excluidas de límite - Total - Importe deducible en cuota [082]
17 198 17 Num Deducciones I+D+i excluidas de límite - Total - Pendiente insuficiencia cuota [083]
18 215 17 Num Deducción donativos entidades sin fines lucro - 2003 - Deducción pendiente/generada [929]
19 232 17 Num Deducción donativos entidades sin fines lucro - 2003 - Aplicado en esta liquidación [930]
20 249 17 Num Deducción donativos entidades sin fines lucro - 2004 - Deducción pendiente/generada [942]
21 266 17 Num Deducción donativos entidades sin fines lucro - 2004 - Aplicado en esta liquidación [943]
Deducción donativos entidades sin fines lucro - 2004 - Pendiente de aplicación en periodos futuros [944]
22 283 17 Num
23 300 17 Num Deducción donativos entidades sin fines lucro - 2005 - Deducción pendiente/generada [294]
24 317 17 Num Deducción donativos entidades sin fines lucro - 2005 - Aplicado en esta liquidación [295]
Deducción donativos entidades sin fines lucro - 2005 - Pendiente de aplicación en periodos futuros [296]
25 334 17 Num
26 351 17 Num Deducción donativos entidades sin fines lucro - 2006 - Deducción pendiente/generada [066]
27 368 17 Num Deducción donativos entidades sin fines lucro - 2006 - Aplicado en esta liquidación [074]
Deducción donativos entidades sin fines lucro - 2006 - Pendiente de aplicación en periodos futuros [084]
28 385 17 Num
29 402 17 Num Deducción donativos entidades sin fines lucro - 2007 - Deducción pendiente/generada [008]
30 419 17 Num Deducción donativos entidades sin fines lucro - 2007 - Aplicado en esta liquidación [009]
Deducción donativos entidades sin fines lucro - 2007 - Pendiente de aplicación en periodos futuros [010]
31 436 17 Num
32 453 17 Num Deducción donativos entidades sin fines lucro - 2008 - Deducción pendiente/generada [034]
33 470 17 Num Deducción donativos entidades sin fines lucro - 2008 - Aplicado en esta liquidación [035]
Deducción donativos entidades sin fines lucro - 2008 - Pendiente de aplicación en periodos futuros [036]
34 487 17 Num
3355 550044 1177 NNuumm DDeedduucccciióónn ddoonnaattiivvooss eennttiiddaaddeess ssiinn ffiinneess lluuccrroo -- 22000099 -- DDeedduucccciióónn ppeennddiieennttee//ggeenneerraaddaa [[220011]]
36 521 17 Num Deducción donativos entidades sin fines lucro - 2009 - Aplicado en esta liquidación [202]
Deducción donativos entidades sin fines lucro - 2009 - Pendiente de aplicación en periodos futuros [203]
37 538 17 Num
38 555 17 Num Deducción donativos entidades sin fines lucro - 2010 - Deducción pendiente/generada [904]
39 572 17 Num Deducción donativos entidades sin fines lucro - 2010 - Aplicado en esta liquidación [905]
Deducción donativos entidades sin fines lucro - 2010 - Pendiente de aplicación en periodos futuros [906]
40 589 17 Num
41 606 17 Num Deducción donativos entidades sin fines lucro - 2011 - Deducción pendiente/generada [990]
42 623 17 Num Deducción donativos entidades sin fines lucro - 2011 - Aplicado en esta liquidación [991]
Deducción donativos entidades sin fines lucro - 2011 - Pendiente de aplicación en periodos futuros [992]
43 640 17 Num
44 657 17 Num Deducción donativos entidades sin fines lucro - 2012 - Deducción pendiente/generada [997]
4455 667744 1177 NNuumm DDeedduucccciióónn ddoonnaattiivvooss eennttiiddaaddeess ssiinn ffiinneess lluuccrroo - 22001122 - AApplliiccaaddoo eenn eessttaa lliiqquuiiddaacciióónn [[999988]]
Deducción donativos entidades sin fines lucro - 2012 - Pendiente de aplicación en periodos futuros [999]
46 691 17 Num
47 708 17 Num Deducción donativos entidades sin fines lucro - 2013 - Deducción pendiente/generada [993]
48 725 17 Num Deducción donativos entidades sin fines lucro - 2013 - Aplicado en esta liquidación [994]
Deducción donativos entidades sin fines lucro - 2013 - Pendiente de aplicación en periodos futuros [995]
49 742 17 Num
Deducción donativos entidades sin fines lucro - Total deducciones donaciones a entidades sin fines lucro -
50 759 17 Num Deducción pendiente/generada [598]
Deducción donativos entidades sin fines lucro - Total deducciones donaciones a entidades sin fines lucro -
51 776 17 Num Aplicado en esta liquidación [565]
Deducción donativos entidades sin fines lucro - Total deducciones donaciones a entidades sin fines lucro -
52 793 17 Num Pendiente de aplicación en periodos futuros [895]
DDeedduucccciióónn ddoonnaattiivvooss eennttiiddaaddeess ssiinn ffiinneess lluuccrroo - DDoonnaacciioonneess ddeell ppeerrííooddoo iimmppoossiittiivvoo eeffeeccttuuaaddaass aa eennttiiddaaddeess ssiinn
53 810 17 Num fines de lucro [974]
54 827 17 Num Aplicación de resultados - Base de reparto - Pérdidas y ganancias [650]
55 844 17 Num Aplicación de resultados - Base de reparto - Remanente [651]
56 861 17 Num Aplicación de resultados - Base de reparto - Reservas [652]
57 878 17 Num Aplicación de resultados - Base de reparto - Total [653]
58 895 17 Num Aplicación de resultados - Aplicación - A reservas [654]
59 912 17 Num Aplicación de resultados - Aplicación - Intereses aportaciones al capital (Cooperativas) [655]
60 929 17 Num Aplicación de resultados - Aplicación - A dividendos [656]
61 946 17 Num Aplicación de resultados - Aplicación - A dotación O.S. (Cajas de ahorro) [658]
62 963 17 Num Aplicación de resultados - Aplicación - A F.R.O y dotaciones voluntarias al F.E.P (Cooperativas) [659]
63 980 17 Num Aplicación de resultados - Aplicación - A retornos cooperativos (Cooperativas) [660]
6644 999977 1177 NNuumm AApplliiccaacciióónn ddee rreessuullttaaddooss - AApplliiccaacciióónn - PPaarrttíícciippeess ((IIIICC)) [[666622]]
65 1014 17 Num Aplicación de resultados - Aplicación - A remanente y otros [664]
66 1031 17 Num Aplicación de resultados - Aplicación - A compensación de pérdidas de ejercicios anteriores [665]
67 1048 17 Num Aplicación de resultados - Aplicación - Total [666]
Página 35

# Pag. 36

Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correcciones permanentes - Del
68 1065 17 Num ejercicio - Aumentos
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correcciones permanentes - Del
69 1082 17 Num ejercicio - Disminuciones
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
70 1099 17 Num ejercicio - Del ejercicio - Aumentos
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
71 1116 17 Num ejercicio - Del ejercicio - Disminuciones
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
72 1133 17 Num ejercicio - Saldo pendiente - Aumentos futuros
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
73 1150 17 Num ejercicio - Saldo pendiente - Disminuciones futuras
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
744 1111667 117 NNum ejjerciiciio - AAmorttiizaciiones - DDell ejjerciiciio - AAumenttos
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
75 1184 17 Num ejercicio - Amortizaciones - Del ejercicio - Disminuciones
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
76 1201 17 Num ejercicio - Amortizaciones - Saldo pendiente - Aumentos futuros
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
77 1218 17 Num ejercicio - Amortizaciones - Saldo pendiente - Disminuciones futuras
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
78 1235 17 Num ejercicio - Deterioros valor - Del ejercicio - Aumentos
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
79 1252 17 Num ejercicio - Deterioros valor - Del ejercicio - Disminuciones
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
80 1269 17 Num ejercicio - Deterioros valor - Saldo pendiente - Aumentos futuros
DDeettaallllee ccoorrrreecccciioonneess rreessuullttaaddoo ppéérrddiiddaass yy ggaannaanncciiaass - CCoorrrreecccciioonneess ffiissccaalleess - CCoorrrreecc. tteemmppoorraarriiaass oorriiggeenn
81 1286 17 Num ejercicio - Deterioros valor - Saldo pendiente - Disminuciones futuras
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
82 1303 17 Num ejercicio - Pensiones - Del ejercicio - Aumentos
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
83 1320 17 Num ejercicio - Pensiones - Del ejercicio - Disminuciones
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
84 1337 17 Num ejercicio - Pensiones - Saldo pendiente - Aumentos futuros
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
85 1354 17 Num ejercicio - Pensiones - Saldo pendiente - Disminuciones futuras
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
86 1371 17 Num ejercicio - Fondo de comercio - Del ejercicio - Aumentos
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
8877 11338888 1177 NNuumm eejjeerrcciicciioo -- FFoonnddoo ddee ccoommeerrcciioo -- DDeell eejjeerrcciicciioo -- DDiissmmiinnuucciioonneess
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
88 1405 17 Num ejercicio - Fondo de comercio - Saldo pendiente - Aumentos futuros
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
89 1422 17 Num ejercicio - Fondo de comercio - Saldo pendiente - Disminuciones futuras
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
90 1439 17 Num ejercicio - Resto - Aumentos
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
91 1456 17 Num ejercicio - Resto - Disminuciones
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
92 1473 17 Num ejercicio - Resto - Saldo pendiente - Aumentos futuros
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen
93 1490 17 Num ejercicio - Resto - Saldo pendiente - Disminuciones futuras
DDeettaallllee ccoorrrreecccciioonneess rreessuullttaaddoo ppéérrddiiddaass yy ggaannaanncciiaass -- CCoorrrreecccciioonneess ffiissccaalleess -- CCoorrrreecc.. tteemmppoorraarriiaass oorriiggeenn eejjeerrcc..
94 1507 17 Num anteriores - Del ejercicio - Aumentos
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
95 1524 17 Num anteriores - Del ejercicio - Disminuciones
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
96 1541 17 Num anteriores - Saldo pendiente - Aumentos futuros
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
97 1558 17 Num anteriores - Saldo pendiente - Disminuciones futuras
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
98 1575 17 Num anteriores - Amortizaciones - Del ejercicio - Aumentos
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
99 1592 17 Num anteriores - Amortizaciones - Del ejercicio - Disminuciones
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
110000 11660099 1177 NNuumm aanntteerriioorreess - AAmmoorrttiizzaacciioonneess - SSaallddoo ppeennddiieennttee - AAuummeennttooss ffuuttuurrooss
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
101 1626 17 Num anteriores - Amortizaciones - Saldo pendiente - Disminuciones futuras
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
102 1643 17 Num anteriores - Deterioros valor - Del ejercicio - Aumentos
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
103 1660 17 Num anteriores - Deterioros valor - Del ejercicio - Disminuciones
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
104 1677 17 Num anteriores - Deterioros valor - Saldo pendiente - Aumentos futuros
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
105 1694 17 Num anteriores - Deterioros valor - Saldo pendiente - Disminuciones futuras
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
106 1711 17 Num anteriores - Pensiones - Del ejercicio - Aumentos
Detalle correcciones resultado ppérdidas yy gganancias - Correcciones fiscales - Correc. tempporarias origgen ejjerc.
107 1728 17 Num anteriores - Pensiones - Del ejercicio - Disminuciones
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
108 1745 17 Num anteriores - Pensiones - Saldo pendiente - Aumentos futuros
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
109 1762 17 Num anteriores - Pensiones - Saldo pendiente - Disminuciones futuras
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
110 1779 17 Num anteriores - Fondo de comercio - Del ejercicio - Aumentos
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
111 1796 17 Num anteriores - Fondo de comercio - Del ejercicio - Disminuciones
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
112 1813 17 Num anteriores - Fondo de comercio - Saldo pendiente - Aumentos futuros
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
113 1830 17 Num anteriores - Fondo de comercio - Saldo pendiente - Disminuciones futuras
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
114 1847 17 Num anteriores - Resto - Del ejercicio - Aumentos
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
115 1864 17 Num anteriores - Resto - Del ejercicio - Disminuciones
Página 36

# Pag. 37

Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
116 1881 17 Num anteriores - Resto - Saldo pendiente - Aumentos futuros
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Correc. temporarias origen ejerc.
117 1898 17 Num anteriores - Resto - Saldo pendiente - Disminuciones futuras
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Total correcciones resultado de
118 1915 17 Num pérdidas y ganancias - Del ejercicio - Aumentos [417]
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Total correcciones resultado de
119 1932 17 Num pérdidas y ganancias - Del ejercicio - Disminuciones [418]
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Total correcciones resultado de
120 1949 17 Num pérdidas y ganancias - Saldo pendiente - Aumentos futuros
Detalle correcciones resultado pérdidas y ganancias - Correcciones fiscales - Total correcciones resultado de
121 1966 17 Num pérdidas y ganancias - Saldo pendiente - Disminuciones futuras
122 1983 22 An Presentación de documentación previa en la sede electrónica. NRS1
123 2005 22 An Presentación de documentación previa en la sede electrónica. NRS2
124 2027 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200180>"
Total: 2036
Página 37

# Pag. 38

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "18B"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
6 11 17 N LLiimiitaciióón ddedduciibbiilliiddadd gastos ffiinanciieros - a)) RResulltaddo expllotaciióón [[1175]]
7 28 17 N Limitación deducibilidad gastos financieros - b) Amortización del inmovilizado [176]
Limitación deducibilidad gastos financieros - c) Imputación subvenciones inmovilizado no financiero y otras
8 45 17 N [177]
Limitación deducibilidad gastos financieros - d) Deterioro y resultado enajenaciones inmovilizado [178]
9 62 17 N
Limitación deducibilidad gastos financieros - e) Ingresos financieros participaciones instrumentos de
10 79 17 N patrimonio [179]
11 96 17 Num Limitación deducibilidad gastos financieros - f) Límite deducción gastos financieros netos [043]
Limitación deducibilidad gastos financieros - g) Adición por límite beneficio operativo no aplicado en cinco
12 113 17 Num ejercicios anteriores [049]
Limitación deducibilidad gastos financieros - h) Gastos financieros periodo impositivo excluidos art. 14.1.h) LIS
1133 113300 1177 NNuumm [[249]]
Limitación deducibilidad gastos financieros - i) Ingresos financieros periodo impositivo derivados cesión
14 147 17 Num terceros de capitales propios [252]
15 164 17 Num Limitación deducibilidad gastos financieros - j) Gastos financieros netos del periodo [253]
Limitación deducibilidad gastos financieros - k) Gastos financieros netos del periodo deducibles [254]
16 181 17 Num
Limitación deducibilidad gastos financieros - l) Gastos financieros netos del periodo no deducibles [255]
17 198 17 Num
Limitación deducibilidad gastos financieros - m) Gastos financieros netos pendientes deducir de periodos
18 215 17 Num anteriores aplicados [258]
Limitación deducibilidad gastos financieros - n) Total gastos financieros netos deducibles en el periodo [259]
19 232 17 Num
Limitación deducibilidad gastos financieros - ñ) Total gastos financieros deducibles en el periodo [260]
2200 224499 1177 NNuumm
Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2012 -
21 266 17 Num Pendiente aplicación a principio del período [969]
Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2012 -
22 283 17 Num Aplicado en esta liquidación [970]
Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación 2012 -
23 300 17 Num Pendiente aplicación períodos futuros [971]
Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación
24 317 17 Num 2013(*) - Pendiente aplicación a principio del período [261]
Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación
25 334 17 Num 2013(*) - Aplicado en esta liquidación [262]
Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación
26 351 17 Num 2013(*) - Pendiente aplicación períodos futuros [263]
LLiimmiittaacciióónn ddeedduucciibbiilliiddaadd ggaassttooss ffiinnaanncciieerrooss, ggaassttooss ffiinnaanncciieerrooss ppeennddiieenntteess ddeedduucciirr -- EEjjeerrcciicciioo ggeenneerraacciióónn
27 368 17 Num 2013(**) - Pendiente aplicación a principio del período [264]
Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación
28 385 17 Num 2013(**) - Aplicado en esta liquidación [265]
Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Ejercicio generación
29 402 17 Num 2013(**) - Pendiente aplicación períodos futuros [266]
Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Total - Pendiente
30 419 17 Num aplicación a principio del período [267]
Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Total - Aplicado en esta
31 436 17 Num liquidación [268]
Limitación deducibilidad gastos financieros, gastos financieros pendientes deducir - Total - Pendiente
32 453 17 Num aplicación períodos futuros [269]
Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2012 - Pendiente aplicación
3333 447700 1177 NNuumm aa pprriinncciippiioo ddeell ppeerrííooddoo [[550033]]
Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2012 - Aplicado en esta
34 487 17 Num liquidación [522]
Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2012 - Pendiente aplicación
35 504 17 Num períodos futuros [523]
Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2013(*) - Pendiente
36 521 17 Num aplicación a principio del período [270]
Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2013(*) - Aplicado en esta
37 538 17 Num liquidación [271]
Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2013(*) - Pendiente
38 555 17 Num aplicación períodos futuros [272]
Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2013(**) - Pendiente
39 572 17 Num aplicación a principio del período [273]
PPeennddiieennttee aaddiicciióónn ppoorr llíímmiittee bbeenneeffiicciioo ooppeerraattiivvoo nnoo aapplliiccaaddoo - EEjjeerrcciicciioo ggeenneerraacciióónn 22001133((****)) - AApplliiccaaddoo eenn eessttaa
40 589 17 Num liquidación [274]
Pendiente adición por límite beneficio operativo no aplicado - Ejercicio generación 2013(**) - Pendiente
41 606 17 Num aplicación períodos futuros [537]
Pendiente adición por límite beneficio operativo no aplicado - Total - Pendiente aplicación a principio del
42 623 17 Num período [538]
Pendiente adición por límite beneficio operativo no aplicado - Total - Aplicado en esta liquidación [539]
43 640 17 Num
Pendiente adición por límite beneficio operativo no aplicado - Total - Pendiente aplicación períodos futuros
44 657 17 Num [546]
Dotaciones deterioro créditos u otros activos - Ejercicio generarción 2011 - Ingresado en esta liquidación [173]
45 674 17 Num
Dotaciones deterioro créditos u otros activos - Ejjercicio ggenerarción 2012 - Inggresado en esta liqquidación [[227]]
46 691 17 Num
Dotaciones deterioro créditos u otros activos - Ejercicio generarción 2013 (*) - Ingresado en esta liquidación
47 708 17 Num [291]
48 725 17 Num Dotaciones deterioro créditos u otros activos - Total - Ingresado en esta liquidación [344]
Dotaciones deterioro créditos u otros activos - Conversión activos impuesto diferido - Importe crédito exigible
49 742 17 Num [393]
Dotaciones deterioro créditos u otros activos - Conversión activos impuesto diferido - Opciones: Abono
50 759 1 Num

# Pag. 39

Dotaciones deterioro créditos u otros activos - Conversión activos impuesto diferido - Opciones:
51 760 1 Num Compensación
Dotaciones deterioro créditos u otros activos - Conversión activos impuesto diferido - Opciones: Canje Deuda
52 761 1 Num Pública
53 762 10 An Identificador de fin de registro OBLIGATORIO Constante "</T20018B>"
Total: 771

# Pag. 40

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An C Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num C Modelo. OBLIGATORIO Constante "200"
3 6 3 An C Página. OBLIGATORIO Constante "190"
4 9 1 An C Fin de identificador de modelo. OBLIGATORIO Constante ">"
Indicador de página complementaria
Blanco (No
compplementaria)) o
5 10 1 An C "C" (Complementaria)
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 1.
6 11 20 An C Descripción de la operación
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 1. Persona
7 31 20 An C o entidad
F - J
8 51 1 A C Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 1. F/J
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 1. Clave
9 52 2 A C país/territorio
10 54 17 N C Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 1. Importe
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 2.
11 71 20 An C Descripción de la operación
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 2. Persona
12 91 20 An C o entidad
F - J
13 111 1 A C Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 2. F/J
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 2. Clave
14 112 2 A C país/territorio
15 114 17 N C Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 2. Importe
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 3.
16 131 20 An C Descripción de la operación
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 3. Persona
17 151 20 An C o entidad
F - J
18 171 1 A CC OOperaciones y situaciones con paraísos ffiscales - OOperaciones relacionadas con paraísos ffiscales. 3. F//J
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 3. Clave
19 172 2 A C país/territorio
20 174 17 N C Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 3. Importe
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 4.
21 191 20 An C Descripción de la operación
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 4. Persona
22 211 20 An C o entidad
F - J
23 231 1 A C Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 4. F/J
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 4. Clave
24 232 2 A C país/territorio
25 234 17 N C Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 4. Importe
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 5.
26 251 20 An C Descripción de la operación
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 5. Persona
27 271 20 An C o entidad
F - J
28 291 1 A C Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 5. F/J
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 5. Clave
29 292 2 A C país/territorio
30 294 17 N C Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 5. Importe
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 6.
3311 331111 2200 AAn CC DDescriipciióón dde lla operaciióón
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 6. Persona
32 331 20 An C o entidad
F - J
33 351 1 A C Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 6. F/J
Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 6. Clave
34 352 2 A C país/territorio
35 354 17 N C Operaciones y situaciones con paraísos fiscales - Operaciones relacionadas con paraísos fiscales. 6. Importe
A - B - C
36 371 1 A C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 1. Tipo
Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 1. Entidad
37 372 23 An C participada
OOperaciiones y siittuaciiones con paraíísos ffiiscalles - TTenenciia vallores con paraíísos ffiiscalles. 11. CCllave
38 395 2 A C país/territorio
39 397 17 N C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 1. Valor adquisición
40 414 5 Num C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 1. % participación
A - B - C
41 419 1 A C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 2. Tipo
Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 2. Entidad
42 420 23 An C participada
Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 2. Clave
43 443 2 A C país/territorio
4444 444455 1177 NN CC OOppeerraacciioonneess yy ssiittuuaacciioonneess ccoonn ppaarraaííssooss ffiissccaalleess - TTeenneenncciiaa vvaalloorreess ccoonn ppaarraaííssooss ffiissccaalleess. 22. VVaalloorr aaddqquuiissiicciióónn
45 462 5 Num C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 2. % participación
A - B - C
46 467 1 A C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 3. Tipo
Página 40

# Pag. 41

Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 3. Entidad
47 468 23 An C participada
Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 3. Clave
48 491 2 A C país/territorio
49 493 17 N C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 3. Valor adquisición
50 510 5 Num C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 3. % participación
A - B - C
51 515 1 A C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 4. Tipo
Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 4. Entidad
52 516 23 An C participada
Opperaciones yy situaciones con pparaísos fiscales - Tenencia valores con pparaísos fiscales. 4. Clave
53 539 2 A C país/territorio
54 541 17 N C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 4. Valor adquisición
55 558 5 Num C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 4. % participación
A - B - C
56 563 1 A C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 5. Tipo
Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 5. Entidad
57 564 23 An C participada
Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 5. Clave
58 587 2 A C país/territorio
59 589 17 N C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 5. Valor adquisición
60 606 5 Num C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 5. % participación
A - B - C
61 611 1 A C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 6. Tipo
Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 6. Entidad
62 612 23 An C participada
Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 6. Clave
63 635 2 A C país/territorio
64 637 17 N C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 6. Valor adquisición
65 654 5 Num C Operaciones y situaciones con paraísos fiscales - Tenencia valores con paraísos fiscales. 6. % participación
66 659 17 N Comunicación importe neto cifra negocios - Grupos de sociedades. Importe neto cifra negocios [987]
67 676 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [1]
68 685 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [2]
69 694 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [3]
70 703 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [4]
71 712 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [5]
72 721 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [6]
73 730 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [7]
74 739 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [8]
75 748 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF de las entidades del grupo [9]
76 757 17 N Comunicación importe neto cifra negocios - No residentes más de un establecimiento. Importe neto [988]
77 774 3 Num Comunicación importe neto cifra negocios - No residentes más de un establecimiento. Nº establecimientos
Comunicación importe neto cifra negocios - No residentes más de un establecimiento. NIF de los
78 777 9 An C establecimientos permanentes [1]
Comunicación importe neto cifra negocios - No residentes más de un establecimiento. NIF de los
7799 778866 99 AAn CC esttabblleciimiienttos permanenttes [[22]]
Comunicación importe neto cifra negocios - No residentes más de un establecimiento. NIF de los
80 795 9 An C establecimientos permanentes [3]
Comunicación importe neto cifra negocios - No residentes más de un establecimiento. NIF de los
81 804 9 An C establecimientos permanentes [4]
Comunicación importe neto cifra negocios - No residentes más de un establecimiento. NIF de los
82 813 9 An C establecimientos permanentes [5]
Comunicación importe neto cifra negocios - Entidades de crédito, aseguradoras, I.I.C. y sociedades de garantía
83 822 17 N recíproca - Importe neto [989]
84 839 4 Num Rég. Entidades navieras en función del tonelaje. Nº de buques [N1]
85 843 17 Num Rég. Entidades navieras en función del tonelaje. Base imponible resultante de aplicar la escala [630]
86 860 17 Num Rég. Entidades navieras en función del tonelaje. Importe rentas generadas en trasmisiones de buques [631]
Rég. Entidades navieras en función del tonelaje. Compensación bases imponibles negativas períodos
87 877 17 Num anteriores [632]
88 894 17 Num Rég. Entidades navieras en función del tonelaje. Base imponible resultante de la aplicación del régimen [579]
89 911 10 An C Identificador de fin de registro OBLIGATORIO Constante "</T200190>"
Total: 920
Página 41

# Pag. 42

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas
vers. 1.0
constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "200"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
Indicador de página complementaria
Blanco (No
compplementaria)) o
5 10 1 An "C" (Complementaria)
6 11 15 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. NIF
7 26 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. F/J
8 27 40 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Apellidos y nombre
9 67 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Tipo vinculación A a L
10 68 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Código provincia/país
11 70 2 Num C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Tipo operación 1 a 11
12 72 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Ingreso/Pago "I" "P"
13 73 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Método valoración 1a 1b 1c 2a 2b
14 75 17 N C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Importe operación
15 92 15 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. NIF
16 107 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. F/J
17 108 40 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Apellidos y nombre
1188 114488 11 AA CC OOppeerraacciioonneess ccoonn ppeerrssoonnaass oo eennttiiddaaddeess vviinnccuullaaddaass - PPeerrssoonnaa oo eennttiiddaadd vviinnccuullaaddaa 22. TTiippoo vviinnccuullaacciióónn AA aa LL
19 149 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Código provincia/país
20 151 2 Num C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Tipo operación 1 a 11
21 153 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Ingreso/Pago "I" "P"
22 154 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Método valoración 1a 1b 1c 2a 2b
23 156 17 N C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Importe operación
24 173 15 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. NIF
25 188 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. F/J
26 189 40 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Apellidos y nombre
27 229 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Tipo vinculación A a L
28 230 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Código provincia/país
29 232 2 Num C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Tipo operación 1 a 11
30 234 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Ingreso/Pago "I" "P"
3311 223355 22 AAnn CC OOppeerraacciioonneess ccoonn ppeerrssoonnaass oo eennttiiddaaddeess vviinnccuullaaddaass -- PPeerrssoonnaa oo eennttiiddaadd vviinnccuullaaddaa 33.. MMééttooddoo vvaalloorraacciióónn 11aa 11bb 11cc 22aa 22bb
32 237 17 N C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Importe operación
33 254 15 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. NIF
34 269 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. F/J
35 270 40 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Apellidos y nombre
36 310 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Tipo vinculación A a L
37 311 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Código provincia/país
38 313 2 Num C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Tipo operación 1 a 11
39 315 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Ingreso/Pago "I" "P"
40 316 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Método valoración 1a 1b 1c 2a 2b
41 318 17 Num C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Importe operación
42 335 15 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. NIF
43 350 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. F/J
44 351 40 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. Apellidos y nombre
45 391 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. Tipo vinculación A a L
46 392 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. Código provincia/país
47 394 2 Num C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. Tipo operación 1 a 11
48 396 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. Ingreso/Pago "I" "P"
49 397 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. Método valoración 1a 1b 1c 2a 2b
50 399 17 N C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. Importe operación
51 416 15 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 6. NIF
52 431 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 6. F/J
53 432 40 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 6. Apellidos y nombre
54 472 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 6. Tipo vinculación A a L
55 473 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 6. Código provincia/país
56 475 2 Num C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 6. Tipo operación 1 a 11
57 477 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 6. Ingreso/Pago "I" "P"
5588 447788 22 AAn CC OOppeerraacciioonneess ccoonn ppeerrssoonnaass oo eennttiiddaaddeess vviinnccuullaaddaass - PPeerrssoonnaa oo eennttiiddaadd vviinnccuullaaddaa 66. MMééttooddoo vvaalloorraacciióónn 11aa 11bb 11cc 22aa 22bb
59 480 17 N C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 6. Importe operación
60 497 17 Num Rég. cooperativas - Determ. base imponible - Ingresos computables - Resultados cooperativos [C1]
61 514 17 Num Rég. cooperativas - Determ. base imponible - Ingresos computables - Resultados extracooperativos [E1]
62 531 17 Num Rég. cooperativas - Determ. base imponible - Gastos específicos - Resultados cooperativos [C2]
63 548 17 Num Rég. cooperativas - Determ. base imponible - Gastos específicos - Resultados extracooperativos [E2]
64 565 17 Num Rég. cooperativas - Determ. base imponible - Gastos generales - Resultados cooperativos [C3]
65 582 17 Num Rég. cooperativas - Determ. base imponible - Gastos generales - Resultados extracooperativos [E3]
Rég. cooperativas - Determ. base imponible - Gastos Fondo de Educación y Promoción - Resultados
66 599 17 Num cooperativos [C4]
Rég. cooperativas - Determ. base imponible - Gastos Fondo de Educación y Promoción - Resultados
67 616 17 Num extracooperativos [E4]
Rég. cooperativas - Determ. base imponible - Incrementos y disminuciones patrimoniales - Resultados
6688 663333 1177 NN extracooperativos [E5]
69 650 17 N Rég. cooperativas - Determ. base imponible - resultado - Resultados cooperativos [C6]
70 667 17 N Rég. cooperativas - Determ. base imponible - resultado - Resultados extracooperativos [E6]
71 684 17 Num Rég. cooperativas - Determ. base imponible - aumentos - Resultados cooperativos [C7]
72 701 17 Num Rég. cooperativas - Determ. base imponible - aumentos - Resultados extracooperativos [E7]
73 718 17 Num Rég. cooperativas - Determ. base imponible - disminuciones - Resultados cooperativos [C8]
74 735 17 Num Rég. cooperativas - Determ. base imponible - disminuciones - Resultados extracooperativos [E8]
75 752 17 Num Rég. cooperativas - Determ. base imponible - 50% Dotación obligatoria - Resultados cooperativos [C9]
76 769 17 Num Rég. cooperativas - Determ. base imponible - 50% Dotación obligatoria - Resultados extracooperativos [E9]
77 786 17 N Rég. cooperativas - Determ. base imponible - Reserva inversiones Canarias - Resultados cooperativos [C10]
78 803 17 N Rég. cooperativas - Determ. base imponible - Factor de agotamiento - Resultados cooperativos [C11]
79 820 17 N Rég. cooperativas - Determ. base imponible - Factor de agotamiento - Resultados extracooperativos [E11]
80 837 17 N Rég. cooperativas - Determ. base imponible - Base imponible - Resultados cooperativos [553]
81 854 17 N Rég. cooperativas - Determ. base imponible - Base imponible - Resultados extracooperativos [554]
82 871 17 Num RRéég. cooperattiivas - DDettalllle compensaciióón cuottas. 11999988 PPenddiientte aplliicaciióón all priinciipiio ddell periioddo [[667733]]
83 888 17 Num Rég. cooperativas - Detalle compensación cuotas. 1998 Aplicado en esta liquidación [674]
Rég. cooperativas - Detalle compensación cuotas. 1999 Pendiente aplicación al principio del periodo [676]
84 905 17 Num
Página 42

# Pag. 43

85 922 17 Num Rég. cooperativas - Detalle compensación cuotas. 1999 Aplicado en esta liquidación [677]
Rég. cooperativas - Detalle compensación cuotas. 1999 Pendiente aplicación en ejercicios futuros [678]
86 939 17 Num
Rég. cooperativas - Detalle compensación cuotas. 2000 Pendiente aplicación al principio del periodo [679]
87 956 17 Num
88 973 17 Num Rég. cooperativas - Detalle compensación cuotas. 2000 Aplicado en esta liquidación [680]
Rég. cooperativas - Detalle compensación cuotas. 2000 Pendiente aplicación en ejercicios futuros [681]
89 990 17 Num
Rég. cooperativas - Detalle compensación cuotas. 2001 Pendiente aplicación al principio del periodo [682]
90 1007 17 Num
91 1024 17 Num Rég. cooperativas - Detalle compensación cuotas. 2001 Aplicado en esta liquidación [683]
Rég. cooperativas - Detalle compensación cuotas. 2001 Pendiente aplicación en ejercicios futuros [684]
92 1041 17 Num
Rég. cooperativas - Detalle compensación cuotas. 2002 Pendiente aplicación al principio del periodo [685]
9933 11005588 1177 NNuumm
94 1075 17 Num Rég. cooperativas - Detalle compensación cuotas. 2002 Aplicado en esta liquidación [686]
Rég. cooperativas - Detalle compensación cuotas. 2002 Pendiente aplicación en ejercicios futuros [687]
95 1092 17 Num
Rég. cooperativas - Detalle compensación cuotas. 2003 Pendiente aplicación al principio del periodo [688]
96 1109 17 Num
97 1126 17 Num Rég. cooperativas - Detalle compensación cuotas. 2003 Aplicado en esta liquidación [689]
Rég. cooperativas - Detalle compensación cuotas. 2003 Pendiente aplicación en ejercicios futuros [690]
98 1143 17 Num
Rég. cooperativas - Detalle compensación cuotas. 2004 Pendiente aplicación al principio del periodo [691]
99 1160 17 Num
100 1177 17 Num Rég. cooperativas - Detalle compensación cuotas. 2004 Aplicado en esta liquidación [692]
Rég. cooperativas - Detalle compensación cuotas. 2004 Pendiente aplicación en ejercicios futuros [693]
101 1194 17 Num
RRéégg.. ccooooppeerraattiivvaass - DDeettaallllee ccoommppeennssaacciióónn ccuuoottaass.. 22000055 PPeennddiieennttee aapplliiccaacciióónn aall pprriinncciippiioo ddeell ppeerriiooddoo [[662233]]
102 1211 17 Num
103 1228 17 Num Rég. cooperativas - Detalle compensación cuotas. 2005 Aplicado en esta liquidación [624]
Rég. cooperativas - Detalle compensación cuotas. 2005 Pendiente aplicación en ejercicios futuros [672]
104 1245 17 Num
Rég. cooperativas - Detalle compensación cuotas. 2006 Pendiente aplicación al principio del periodo [279]
105 1262 17 Num
106 1279 17 Num Rég. cooperativas - Detalle compensación cuotas. 2006 Aplicado en esta liquidación [280]
Rég. cooperativas - Detalle compensación cuotas. 2006 Pendiente aplicación en ejercicios futuros [281]
107 1296 17 Num
Rég. cooperativas - Detalle compensación cuotas. 2007 Pendiente aplicación al principio del periodo [587]
108 1313 17 Num
109 1330 17 Num Rég. cooperativas - Detalle compensación cuotas. 2007 Aplicado en esta liquidación [515]
Rég. cooperativas - Detalle compensación cuotas. 2007 Pendiente aplicación en ejercicios futuros [900]
110 1347 17 Num
Rég. cooperativas - Detalle compensación cuotas. 2008 Pendiente aplicación al principio del periodo [059]
111 1364 17 Num
112 1381 17 Num Rég. cooperativas - Detalle compensación cuotas. 2008 Aplicado en esta liquidación [099]
Rég. cooperativas - Detalle compensación cuotas. 2008 Pendiente aplicación en ejercicios futuros [100]
113 1398 17 Num
Rég. cooperativas - Detalle compensación cuotas. 2009 Pendiente aplicación al principio del periodo [017]
114 1415 17 Num
115 1432 17 Num Rég. cooperativas - Detalle compensación cuotas. 2009 Aplicado en esta liquidación [018]
Rég. cooperativas - Detalle compensación cuotas. 2009 Pendiente aplicación en ejercicios futuros [019]
116 1449 17 Num
Rég. cooperativas - Detalle compensación cuotas. 2010 Pendiente aplicación al principio del periodo [772]
117 1466 17 Num
118 1483 17 Num Rég. cooperativas - Detalle compensación cuotas. 2010 Aplicado en esta liquidación [773]
Rég. cooperativas - Detalle compensación cuotas. 2010 Pendiente aplicación en ejercicios futuros [777]
111199 11550000 1177 NNuumm
Rég. cooperativas - Detalle compensación cuotas. 2011 Pendiente aplicación al principio del periodo [907]
120 1517 17 Num
121 1534 17 Num Rég. cooperativas - Detalle compensación cuotas. 2011 Aplicado en esta liquidación [908]
Rég. cooperativas - Detalle compensación cuotas. 2011 Pendiente aplicación en ejercicios futuros [909]
122 1551 17 Num
Rég. cooperativas - Detalle compensación cuotas. 2012 Pendiente aplicación al principio del periodo [910]
123 1568 17 Num
124 1585 17 Num Rég. cooperativas - Detalle compensación cuotas. 2012 Aplicado en esta liquidación [911]
Rég. cooperativas - Detalle compensación cuotas. 2012 Pendiente aplicación en ejercicios futuros [912]
125 1602 17 Num
Rég. cooperativas - Detalle compensación cuotas. 2013 (*) Pendiente aplicación al principio del periodo [935]
126 1619 17 Num
127 1636 17 Num Rég. cooperativas - Detalle compensación cuotas. 2013 (*) Aplicado en esta liquidación [936]
RRéégg.. ccooooppeerraattiivvaass - DDeettaallllee ccoommppeennssaacciióónn ccuuoottaass.. 22001133 ((*)) PPeennddiieennttee aapplliiccaacciióónn eenn eejjeerrcciicciiooss ffuuttuurrooss [[993377]]
128 1653 17 Num
Rég. cooperativas - Detalle compensación cuotas. Total. Pendiente aplicación al principio del periodo [694]
129 1670 17 Num
130 1687 17 Num Rég. cooperativas - Detalle compensación cuotas. Total. Aplicado en esta liquidación [561]
Rég. cooperativas - Detalle compensación cuotas. Total. Pendiente aplicación en ejercicios futuros [695]
131 1704 17 Num
132 1721 10 An C Identificador de fin de registro OBLIGATORIO Constante "</T200200>"
Total: 1730
Página 43

# Pag. 44

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas
vers. 1.0
constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An C Inicio del identificador de modelo y página. Constante "<T"
2 3 3 Num C Modelo. Constante "200"
3 6 3 An C Página. Constante "210"
4 9 1 An C Fin de identificador de modelo. Constante ">"
C Indicador de página complementaria.
Blanco (No
ccoommpplleemmeennttaarriiaa)) oo
5 10 1 An "C" (Complementaria)
6 11 1 A C Operaciones fusión, escisión, canje valores - 1. Tipo de operación
7 12 9 An C Operaciones fusión, escisión, canje valores - 1. Entidad transmitente. NIF
8 21 40 An C Operaciones fusión, escisión, canje valores - 1. Entidad transmitente.Denominación social
9 61 9 An C Operaciones fusión, escisión, canje valores - 1. Entidad adquirente. NIF
10 70 40 An C Operaciones fusión, escisión, canje valores - 1. Entidad adquirente.Denominación social
11 110 8 Num C Operaciones fusión, escisión, canje valores - 1. Fecha de los acuerdos sociales
12 118 17 N C Operaciones fusión, escisión, canje valores - 1. Valor acciones entregadas
13 135 17 N C Operaciones fusión, escisión, canje valores - 1. Valor acciones recibidas
14 152 17 N C Operaciones fusión, escisión, canje valores - 1. Importe rentas no integradas en la base imponible
15 169 1 A C Operaciones fusión, escisión, canje valores - 2. Tipo de operación
16 170 9 An C Operaciones fusión, escisión, canje valores - 2. Entidad transmitente. NIF
17 179 40 An C Operaciones fusión, escisión, canje valores - 2. Entidad transmitente.Denominación social
18 219 9 An C Operaciones fusión, escisión, canje valores - 2. Entidad adquirente. NIF
19 228 40 An C Operaciones fusión, escisión, canje valores - 2. Entidad adquirente.Denominación social
20 268 8 Num C Operaciones fusión, escisión, canje valores - 2. Fecha de los acuerdos sociales
21 276 17 N C Operaciones fusión, escisión, canje valores - 2. Valor acciones entregadas
22 293 17 N C Operaciones fusión, escisión, canje valores - 2. Valor acciones recibidas
23 310 17 N C Operaciones fusión, escisión, canje valores - 2. Importe rentas no integradas en la base imponible
24 327 1 A C Operaciones fusión, escisión, canje valores - 3. Tipo de operación
25 328 9 An C Operaciones fusión, escisión, canje valores - 3. Entidad transmitente. NIF
26 337 40 An C Operaciones fusión, escisión, canje valores - 3. Entidad transmitente.Denominación social
27 377 9 An C Operaciones fusión, escisión, canje valores - 3. Entidad adquirente. NIF
28 386 40 An C Operaciones fusión, escisión, canje valores - 3. Entidad adquirente.Denominación social
29 426 8 Num C Operaciones fusión, escisión, canje valores - 3. Fecha de los acuerdos sociales
30 434 17 N C Operaciones fusión, escisión, canje valores - 3. Valor acciones entregadas
3311 445511 1177 NN CC OOppeerraacciioonneess ffuussiióónn, eesscciissiióónn, ccaannjjee vvaalloorreess -- 33. VVaalloorr aacccciioonneess rreecciibbiiddaass
32 468 17 N C Operaciones fusión, escisión, canje valores - 3. Importe rentas no integradas en la base imponible
33 485 1 A C Operaciones fusión, escisión, canje valores - 4. Tipo de operación
34 486 9 An C Operaciones fusión, escisión, canje valores - 4. Entidad transmitente. NIF
35 495 40 An C Operaciones fusión, escisión, canje valores - 4. Entidad transmitente.Denominación social
36 535 9 An C Operaciones fusión, escisión, canje valores - 4. Entidad adquirente. NIF
37 544 40 An C Operaciones fusión, escisión, canje valores - 4. Entidad adquirente.Denominación social
38 584 8 Num C Operaciones fusión, escisión, canje valores - 4. Fecha de los acuerdos sociales
39 592 17 N C Operaciones fusión, escisión, canje valores - 4. Valor acciones entregadas
40 609 17 N C Operaciones fusión, escisión, canje valores - 4. Valor acciones recibidas
41 626 17 N C Operaciones fusión, escisión, canje valores - 4. Importe rentas no integradas en la base imponible
42 643 1 A C Operaciones fusión, escisión, canje valores - 5. Tipo de operación
43 644 9 An C Operaciones fusión, escisión, canje valores - 5. Entidad transmitente. NIF
44 653 40 An C Opperaciones fusión, escisión, canjje valores - 5. Entidad transmitente.Denominación social
45 693 9 An C Operaciones fusión, escisión, canje valores - 5. Entidad adquirente. NIF
46 702 40 An C Operaciones fusión, escisión, canje valores - 5. Entidad adquirente.Denominación social
47 742 8 Num C Operaciones fusión, escisión, canje valores - 5. Fecha de los acuerdos sociales
48 750 17 N C Operaciones fusión, escisión, canje valores - 5. Valor acciones entregadas
49 767 17 N C Operaciones fusión, escisión, canje valores - 5. Valor acciones recibidas
50 784 17 N C Operaciones fusión, escisión, canje valores - 5. Importe rentas no integradas en la base imponible
51 801 10 An C Identificador de fin de registro OBLIGATORIO Constante "</T200210>"
Total: 810
Página 44

# Pag. 45

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en
vers. 1.0
el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An C Inicio del identificador de modelo y página. Constante "<T"
2 3 3 Num C Modelo. Constante "200"
3 6 3 An C Página. Constante "220"
4 9 1 An C Fin de identificador de modelo. Constante ">"
C Indicador de página complementaria.
Blanco (No
ccoommpplleemmeennttaarriiaa)) oo
5 10 1 An "C" (Complementaria)
6 11 7 Num Agrup. interés económico y UTES - Porcentaje de imputación de bases imponibles [060]
7 18 17 N Agrup. interés económico y UTES - Modelo de información - Resultado contable [500]
8 35 17 N Agrup. interés económico y UTES - Modelo de información - Base imponible [552]
9 52 17 Num C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición interna 1. Base
10 69 40 An C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición interna 1. Tipo entidad
11 109 5 Num C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición interna 1. % participación
12 114 17 Num C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición interna 2. Base
13 131 40 An C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición interna 2. Tipo entidad
14 171 5 Num C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición interna 2. % participación
15 176 17 Num C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición interna 3. Base
16 193 40 An C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición interna 3. Tipo entidad
17 233 5 Num C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición interna 3. % participación
18 238 17 Num C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición interna 4. Base
19 255 40 An C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición interna 4. Tipo entidad
20 295 5 Num C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición interna 4. % participación
21 300 17 Num C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición internacional 1. Base
22 317 5 Num C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición internacional 1. % participación
23 322 17 Num C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición internacional 2. Base
24 339 5 Num C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición internacional 2. % participación
25 344 17 Num C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición internacional 3. Base
26 361 5 Num C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición internacional 3. % participación
27 366 17 Num C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición internacional 4. Base
28 383 5 Num C Agrup. interés económico y UTES - Modelo de información - Deduc. evitar doble imposición internacional 4. % participación
29 388 17 Num Agrup. interés económico y UTES - Modelo de información - Base bonificaciones
30 405 17 Num Agrup. interés económico y UTES - Modelo de información - Base deducciones
3311 442222 1177 NNuumm AAggrruupp. iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS -- MMooddeelloo ddee iinnffoorrmmaacciióónn -- RReetteenncciioonneess ee iinnggrreessooss aa ccuueennttaa [[006622]]
Agrup. interés económico y UTES - Modelo de información - Dividendos y participaciones. a) Ejercicios que no haya
32 439 17 Num tributado en régimen especial
Agrup. interés económico y UTES - Modelo de información - Dividendos y participaciones. b) Ejercicios que haya tributado
33 456 17 Num en régimen especial
34 473 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. NIF
35 482 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. Rpte. ( "0", "1")
36 483 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. F/J F -J
37 484 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. R/X R -X
38 485 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. Apellidos y nombre
39 519 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. Código provincia/país
40 521 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. Base imponible
41 538 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 1. % partic.
42 545 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. NIF
4433 555544 11 NNuumm CC AAggrruupp. iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS - MMooddeelloo ddee iinnffoorrmmaacciióónn - RReellaacciióónn ddee ssoocciiooss 22. RRppttee. (( ""00"", ""11""))
44 555 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. F/J F -J
45 556 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. R/X R -X
46 557 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. Apellidos y nombre
47 591 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. Código provincia/país
48 593 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. Base imponible
49 610 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 2. % partic.
50 617 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. NIF
51 626 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. Rpte. ( "0", "1")
52 627 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. F/J F -J
53 628 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. R/X R -X
54 629 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. Apellidos y nombre
55 663 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. Código provincia/país
5566 666655 1177 NN CC Aggrupp. interés económico yy UUTESS - Modelo de información - Relación de socios 33. Base impponible
57 682 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 3. % partic.
58 689 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. NIF
59 698 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. Rpte. ( "0", "1")
60 699 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. F/J F -J
61 700 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. R/X R -X
62 701 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. Apellidos y nombre
63 735 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. Código provincia/país
64 737 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. Base imponible
65 754 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 4. % partic.
66 761 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. NIF
67 770 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. Rpte. ( "0", "1")
68 771 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. F/J F -J
69 772 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. R/X R -X
7700 777733 3344 AAn CC AAgrup. iintteréés econóómiico y UUTTEESS - MModdello dde iinfformaciióón - RRellaciióón dde sociios 55. AApelllliiddos y nombbre
71 807 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. Código provincia/país
72 809 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. Base imponible
73 826 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 5. % partic.
74 833 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. NIF
75 842 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. Rpte. ( "0", "1")
76 843 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. F/J F -J
77 844 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. R/X R -X
78 845 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. Apellidos y nombre
79 879 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. Código provincia/país
80 881 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. Base imponible
81 898 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 6. % partic.
82 905 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. NIF
8833 991144 11 NNuumm CC AAggrruupp.. iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS - MMooddeelloo ddee iinnffoorrmmaacciióónn - RReellaacciióónn ddee ssoocciiooss 77.. RRppttee.. (( "00",, "11"))
84 915 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. F/J F -J
85 916 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. R/X R -X
Página 45

# Pag. 46

86 917 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. Apellidos y nombre
87 951 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. Código provincia/país
88 953 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. Base imponible
89 970 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 7. % partic.
90 977 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. NIF
91 986 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. Rpte. ( "0", "1")
92 987 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. F/J F -J
93 988 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. R/X R -X
94 989 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. Apellidos y nombre
95 1023 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. Código provincia/país
96 1025 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. Base imponible
97 1042 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 8. % partic.
98 1049 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. NIF
9999 11005588 11 NNuumm CC AAggrruupp.. iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS - MMooddeelloo ddee iinnffoorrmmaacciióónn - RReellaacciióónn ddee ssoocciiooss 99.. RRppttee.. (( "00",, "11"))
100 1059 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. F/J F -J
101 1060 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. R/X R -X
102 1061 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. Apellidos y nombre
103 1095 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. Código provincia/país
104 1097 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. Base imponible
105 1114 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 9. % partic.
106 1121 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. NIF
107 1130 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. Rpte. ( "0", "1")
108 1131 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. F/J F -J
109 1132 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. R/X R -X
110 1133 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. Apellidos y nombre
111 1167 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. Código provincia/país
112 1169 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 10. Base imponible
111133 11118866 77 NNuumm CC AAggrruupp. iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS -- MMooddeelloo ddee iinnffoorrmmaacciióónn -- RReellaacciióónn ddee ssoocciiooss 1100. %% ppaarrttiicc.
114 1193 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 11. NIF
115 1202 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 11. Rpte. ( "0", "1")
116 1203 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 11. F/J F -J
117 1204 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 11. R/X R -X
118 1205 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 11. Apellidos y nombre
119 1239 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 11. Código provincia/país
120 1241 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 11. Base imponible
121 1258 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 11. % partic.
122 1265 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 12. NIF
123 1274 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 12. Rpte. ( "0", "1")
124 1275 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 12. F/J F -J
125 1276 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 12. R/X R -X
126 1277 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 12. Apellidos y nombre
112277 11331111 22 AAnn CC AAggrruupp. iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS - MMooddeelloo ddee iinnffoorrmmaacciióónn - RReellaacciióónn ddee ssoocciiooss 1122. CCóóddiiggoo pprroovviinncciiaa//ppaaííss
128 1313 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 12. Base imponible
129 1330 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 12. % partic.
130 1337 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 13. NIF
131 1346 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 13. Rpte. ( "0", "1")
132 1347 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 13. F/J F -J
133 1348 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 13. R/X R -X
134 1349 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 13. Apellidos y nombre
135 1383 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 13. Código provincia/país
136 1385 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 13. Base imponible
137 1402 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 13. % partic.
138 1409 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 14. NIF
139 1418 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 14. Rpte. ( "0", "1")
140 1419 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 14. F/J F -J
141 1420 1 A CC AAgrup. iintteréés econóómiico y UUTTEESS - MModdello dde iinfformaciióón - RRellaciióón dde sociios 1144. RR//XX RR -XX
142 1421 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 14. Apellidos y nombre
143 1455 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 14. Código provincia/país
144 1457 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 14. Base imponible
145 1474 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 14. % partic.
146 1481 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 15. NIF
147 1490 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 15. Rpte. ( "0", "1")
148 1491 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 15. F/J F -J
149 1492 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 15. R/X R -X
150 1493 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 15. Apellidos y nombre
151 1527 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 15. Código provincia/país
152 1529 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 15. Base imponible
153 1546 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 15. % partic.
154 1553 9 An C Aggrupp. interés económico yy UTES - Modelo de información - Relación de socios 16. NIF
155 1562 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 16. Rpte. ( "0", "1")
156 1563 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 16. F/J F -J
157 1564 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 16. R/X R -X
158 1565 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 16. Apellidos y nombre
159 1599 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 16. Código provincia/país
160 1601 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 16. Base imponible
161 1618 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 16. % partic.
162 1625 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 17. NIF
163 1634 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 17. Rpte. ( "0", "1")
164 1635 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 17. F/J F -J
165 1636 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 17. R/X R -X
166 1637 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 17. Apellidos y nombre
167 1671 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 17. Código provincia/país
116688 11667733 1177 NN CC AAggrruupp.. iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS - MMooddeelloo ddee iinnffoorrmmaacciióónn - RReellaacciióónn ddee ssoocciiooss 1177.. BBaassee iimmppoonniibbllee
169 1690 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 17. % partic.
170 1697 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 18. NIF
171 1706 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 18. Rpte. ( "0", "1")
172 1707 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 18. F/J F -J
173 1708 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 18. R/X R -X
174 1709 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 18. Apellidos y nombre
175 1743 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 18. Código provincia/país
176 1745 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 18. Base imponible
177 1762 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 18. % partic.
178 1769 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 19. NIF
Página 46

# Pag. 47

179 1778 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 19. Rpte. ( "0", "1")
180 1779 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 19. F/J F -J
181 1780 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 19. R/X R -X
182 1781 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 19. Apellidos y nombre
183 1815 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 19. Código provincia/país
184 1817 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 19. Base imponible
185 1834 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 19. % partic.
186 1841 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 20. NIF
187 1850 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 20. Rpte. ( "0", "1")
188 1851 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 20. F/J F -J
189 1852 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 20. R/X R -X
190 1853 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 20. Apellidos y nombre
191 1887 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 20. Código provincia/país
119922 11888899 1177 NN CC AAggrruupp.. iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS - MMooddeelloo ddee iinnffoorrmmaacciióónn - RReellaacciióónn ddee ssoocciiooss 2200.. BBaassee iimmppoonniibbllee
193 1906 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 20. % partic.
194 1913 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 21. NIF
195 1922 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 21. Rpte. ( "0", "1")
196 1923 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 21. F/J F -J
197 1924 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 21. R/X R -X
198 1925 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 21. Apellidos y nombre
199 1959 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 21. Código provincia/país
200 1961 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 21. Base imponible
201 1978 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 21. % partic.
202 1985 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 22. NIF
203 1994 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 22. Rpte. ( "0", "1")
204 1995 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 22. F/J F -J
205 1996 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 22. R/X R -X
220066 11999977 3344 AAnn CC AAggrruupp. iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS -- MMooddeelloo ddee iinnffoorrmmaacciióónn -- RReellaacciióónn ddee ssoocciiooss 2222. AAppeelllliiddooss yy nnoommbbrree
207 2031 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 22. Código provincia/país
208 2033 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 22. Base imponible
209 2050 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 22. % partic.
210 2057 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 23. NIF
211 2066 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 23. Rpte. ( "0", "1")
212 2067 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 23. F/J F -J
213 2068 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 23. R/X R -X
214 2069 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 23. Apellidos y nombre
215 2103 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 23. Código provincia/país
216 2105 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 23. Base imponible
217 2122 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 23. % partic.
218 2129 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 24. NIF
219 2138 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 24. Rpte. ( "0", "1")
222200 22113399 11 AA CC AAggrruupp. iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS - MMooddeelloo ddee iinnffoorrmmaacciióónn - RReellaacciióónn ddee ssoocciiooss 2244. FF//JJ FF -JJ
221 2140 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 24. R/X R -X
222 2141 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 24. Apellidos y nombre
223 2175 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 24. Código provincia/país
224 2177 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 24. Base imponible
225 2194 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 24. % partic.
226 2201 9 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 25. NIF
227 2210 1 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 25. Rpte. ( "0", "1")
228 2211 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 25. F/J F -J
229 2212 1 A C Agrup. interés económico y UTES - Modelo de información - Relación de socios 25. R/X R -X
230 2213 34 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 25. Apellidos y nombre
231 2247 2 An C Agrup. interés económico y UTES - Modelo de información - Relación de socios 25. Código provincia/país
232 2249 17 N C Agrup. interés económico y UTES - Modelo de información - Relación de socios 25. Base imponible
233 2266 7 Num C Agrup. interés económico y UTES - Modelo de información - Relación de socios 25. % partic.
234 2273 10 An CC Identificador de fin de registro OBLIGATORIO Constante "</T200220>"
Total: 2282
Página 47

# Pag. 48

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas
vers. 1.0
constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An C Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num C Modelo. OBLIGATORIO Constante "200"
3 6 3 An C Página. OBLIGATORIO Constante "230"
4 9 1 An C Fin de identificador de modelo. OBLIGATORIO Constante ">"
C Indicador de página complementaria
BBllaannccoo ((NNoo
complementaria) o
5 10 1 An "C" (Complementaria)
6 11 40 An C Rég.transparencia fiscal internacional - 1. Nombre o razón social
7 51 40 An C Rég.transparencia fiscal internacional - 1. Domicilio social
8 91 2 An C Rég.transparencia fiscal internacional - 1. Clave país/territorio
9 93 17 Num C Rég.transparencia fiscal internacional - 1. Importe renta [A]
10 110 95 An C Rég.transparencia fiscal internacional - 1. Administradores. Línea 1
11 205 95 An C Rég.transparencia fiscal internacional - 1. Administradores. Línea 2
12 300 95 An C Rég.transparencia fiscal internacional - 1. Administradores. Línea 3
13 395 95 An C Rég.transparencia fiscal internacional - 1. Administradores. Línea 4
14 490 95 An C Rég.transparencia fiscal internacional - 1. Administradores. Línea 5
15 585 40 An C Rég.transparencia fiscal internacional - 2. Nombre o razón social
16 625 40 An C Régg.transpparencia fiscal internacional - 2. Domicilio social
17 665 2 An C Rég.transparencia fiscal internacional - 2. Clave país/territorio
18 667 17 Num C Rég.transparencia fiscal internacional - 2. Importe renta [B]
19 684 95 An C Rég.transparencia fiscal internacional - 2. Administradores. Línea 1
20 779 95 An C Rég.transparencia fiscal internacional - 2. Administradores. Línea 2
21 874 95 An C Rég.transparencia fiscal internacional - 2. Administradores. Línea 3
22 969 95 An C Rég.transparencia fiscal internacional - 2. Administradores. Línea 4
23 1064 95 An C Rég.transparencia fiscal internacional - 2. Administradores. Línea 5
24 1159 40 An C Rég.transparencia fiscal internacional - 3. Nombre o razón social
25 1199 40 An C Rég.transparencia fiscal internacional - 3. Domicilio social
26 1239 2 An C Rég.transparencia fiscal internacional - 3. Clave país/territorio
27 1241 17 Num C Rég.transparencia fiscal internacional - 3. Importe renta [C]
28 1258 95 An C Rég.transparencia fiscal internacional - 3. Administradores. Línea 1
2299 11335533 9955 AAnn C Régg.transpparencia fiscal internacional - 3. Administradores. Línea 2
30 1448 95 An C Rég.transparencia fiscal internacional - 3. Administradores. Línea 3
31 1543 95 An C Rég.transparencia fiscal internacional - 3. Administradores. Línea 4
32 1638 95 An C Rég.transparencia fiscal internacional - 3. Administradores. Línea 5
33 1733 40 An C Rég.transparencia fiscal internacional - 4. Nombre o razón social
34 1773 40 An C Rég.transparencia fiscal internacional - 4. Domicilio social
35 1813 2 An C Rég.transparencia fiscal internacional - 4. Clave país/territorio
36 1815 17 Num C Rég.transparencia fiscal internacional - 4. Importe renta [D]
37 1832 95 An C Rég.transparencia fiscal internacional - 4. Administradores. Línea 1
38 1927 95 An C Rég.transparencia fiscal internacional - 4. Administradores. Línea 2
39 2022 95 An C Rég.transparencia fiscal internacional - 4. Administradores. Línea 3
40 2117 95 An C Rég.transparencia fiscal internacional - 4. Administradores. Línea 4
41 2212 95 An C Rég.transparencia fiscal internacional - 4. Administradores. Línea 5
4422 22330077 4400 AAnn CC RRéégg..ttrraannssppaarreenncciiaa ffiissccaall iinntteerrnnaacciioonnaall - 55.. NNoommbbrree oo rraazzóónn ssoocciiaall
43 2347 40 An C Rég.transparencia fiscal internacional - 5. Domicilio social
44 2387 2 An C Rég.transparencia fiscal internacional - 5. Clave país/territorio
45 2389 17 Num C Rég.transparencia fiscal internacional - 5. Importe renta [E]
46 2406 95 An C Rég.transparencia fiscal internacional - 5. Administradores. Línea 1
47 2501 95 An C Rég.transparencia fiscal internacional - 5. Administradores. Línea 2
48 2596 95 An C Rég.transparencia fiscal internacional - 5. Administradores. Línea 3
49 2691 95 An C Rég.transparencia fiscal internacional - 5. Administradores. Línea 4
50 2786 95 An C Rég.transparencia fiscal internacional - 5. Administradores. Línea 5
51 2881 40 An C Rég.transparencia fiscal internacional - 6. Nombre o razón social
52 2921 40 An C Rég.transparencia fiscal internacional - 6. Domicilio social
53 2961 2 An C Rég.transparencia fiscal internacional - 6. Clave país/territorio
54 2963 17 Num C Rég.transparencia fiscal internacional - 6. Importe renta [F]
5555 22998800 9955 AAnn CC RRéégg..ttrraannssppaarreenncciiaa ffiissccaall iinntteerrnnaacciioonnaall -- 66.. AAddmmiinniissttrraaddoorreess.. LLíínneeaa 11
56 3075 95 An C Rég.transparencia fiscal internacional - 6. Administradores. Línea 2
57 3170 95 An C Rég.transparencia fiscal internacional - 6. Administradores. Línea 3
58 3265 95 An C Rég.transparencia fiscal internacional - 6. Administradores. Línea 4
59 3360 95 An C Rég.transparencia fiscal internacional - 6. Administradores. Línea 5
60 3455 17 Num Rég.transparencia fiscal internacional - Total importe [387]
61 3472 10 An C Identificador de fin de registro OBLIGATORIO Constante "</T200230>"
Total: 3481
Página 48

# Pag. 49

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "240"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NNuumm TTrriibbuuttaacciióónn ccoonnjjuunnttaa EEssttaaddoo yy AAddmm.FFoorraalleess - CCoonncciieerrttoo eeccoonnóómmiiccoo - VVoolluummeenn ttoottaall ddee ooppeerraacciioonneess [[005500]]
17 Num Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen operaciones en el extranjero [051]
7 28
17 Num Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen operaciones en Araba [052]
8 45
17 Num Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen operaciones en Gipuzkoa [053]
9 62
17 Num Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen operaciones en Bizkaia [054]
10 79
17 Num Tributación conjunta Estado y Adm.Forales - Convenio económico - Volumen operaciones en Navarra [055]
11 96
Tributación conjunta Estado y Adm.Forales - Concierto económico - Volumen operaciones en Territorio común
12 113 17 Num [056]
1133 113300 55 NNuumm TTrriibbuuttaacciióónn ccoonnjjuunnttaa EEssttaaddoo yy AAddmm.FFoorraalleess - CCáállccuulloo ppoorrcceennttaajjeess ttrriibbuuttaacciióónn - AArraabbaa [[662266]]
14 135 5 Num Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación - Gipuzkoa [627]
15 140 5 Num Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación - Bizkaia [628]
16 145 5 Num Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación - Navarra [629]
17 150 5 Num Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación - Admón.del Estado [625]
18 155 17 N Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver - Araba [420]
19 172 17 N Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver - Gipuzkoa [421]
20 189 17 N Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver - Bizkaia [426]
21 206 17 N Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver - Navarra [427]
22 223 17 N Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver - Total [600]
23 240 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1 - Araba [402]
24 257 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1 - Gipuzkoa [442]
2255 227744 1177 NNuumm TTrriibbuuttaacciióónn ccoonnjjuunnttaa EEssttaaddoo yy AAddmm..FFoorraalleess - PPaaggooss ffrraacccciioonnaaddooss 11 - BBiizzkkaaiiaa [[444433]]
26 291 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1 - Navarra [444]
27 308 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1 - Total [602]
28 325 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2 - Araba [445]
29 342 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2 - Gipuzkoa [446]
30 359 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2 - Bizkaia [447]
31 376 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2 - Navarra [448]
32 393 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2 - Total [604]
33 410 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3 - Araba [449]
34 427 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3 - Gipuzkoa [450]
35 444 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3 - Bizkaia [451]
36 461 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3 - Navarra [465]
37 478 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3 - Total [606]
38 495 17 N Tributación conjunta Estado y Adm.Forales - Cuota diferencial - Araba [474]
39 512 17 N Tributación conjunta Estado y Adm.Forales - Cuota diferencial - Gipuzkoa [475]
40 529 17 N Tributación conjunta Estado y Adm.Forales - Cuota diferencial - Bizkaia [476]
41 546 17 N Tributación conjunta Estado y Adm.Forales - Cuota diferencial - Navarra [477]
42 563 17 N Tributación conjunta Estado y Adm.Forales - Cuota diferencial - Total [612]
43 580 17 Num Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales - Araba [482]
44 597 17 Num Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales - Gipuzkoa [483]
45 614 17 Num Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales - Bizkaia [484]
46 631 17 Num Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales - Navarra [485]
47 648 17 Num Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales - Total [616]
17 Num Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI - Araba [913]
48 665
1177 NNuumm TTrriibbuuttaacciióónn ccoonnjjuunnttaa EEssttaaddoo yy AAddmm..FFoorraalleess -- IInnccrreemmeennttoo ppoorr iinnccuummpplliimmiieennttoo rreeqquuiissiittooss SSOOCCIIMMII -- GGiippuuzzkkooaa [[991144
49 682
17 Num Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI - Bizkaia [915]
50 699
17 Num Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI - Navarra [916]
51 716
17 Num Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI - Total [642]
52 733
53 750 17 Num Tributación conjunta Estado y Adm.Forales - Intereses demora - Araba [486]
54 767 17 Num Tributación conjunta Estado y Adm.Forales - Intereses demora - Gipuzkoa [487]
55 784 17 Num Tributación conjunta Estado y Adm.Forales - Intereses demora - Bizkaia [488]
56 801 17 Num Tributación conjunta Estado y Adm.Forales - Intereses demora - Navarra [489]
57 818 17 Num Tributación conjunta Estado y Adm.Forales - Intereses demora - Total [618]
1177 NN TTrriibbuuttaacciióónn ccoonnjjuunnttaa EEssttaaddoo yy AAddmm.FFoorraalleess -- IImmppoorrttee iinnggrreessoo//ddeevvoolluucciióónn ddeeccllaarraacciióónn oorriiggiinnaarriiaa -- AArraabbaa [[449900]]
58 835
17 N Tributación conjunta Estado y Adm.Forales - Importe ingreso/devolución declaración originaria - Gipuzkoa [491]
59 852
17 N Tributación conjunta Estado y Adm.Forales - Importe ingreso/devolución declaración originaria - Bizkaia [492]
60 869
17 N Tributación conjunta Estado y Adm.Forales - Importe ingreso/devolución declaración originaria - Navarra [493]
61 886
17 N Tributación conjunta Estado y Adm.Forales - Importe ingreso/devolución declaración originaria - Total [620]
62 903
63 920 17 N Tributación conjunta Estado y Adm.Forales - Líquido a ingresar o a devolver - Araba [494]
64 937 17 N Tributación conjunta Estado y Adm.Forales - Líquido a ingresar o a devolver - Gipuzkoa [495]
65 954 17 N Tributación conjunta Estado y Adm.Forales - Líquido a ingresar o a devolver - Bizkaia [496]
6666 997711 1177 NN TTrriibbuuttaacciióónn ccoonnjjuunnttaa EEssttaaddoo yy AAddmm.FFoorraalleess -- LLííqquuiiddoo aa iinnggrreessaarr oo aa ddeevvoollvveerr -- NNaavvaarrrraa [[449977]]
67 988 17 N Tributación conjunta Estado y Adm.Forales - Líquido a ingresar o a devolver - Total [622]
68 1005 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200240>"
Total: 1014
Página 49

# Pag. 50

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "250"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - BBaallaannccee ((II)) - AAccttiivvoo - CCaajjaa yy ddeeppóóssiittooss eenn bbaannccooss cceennttrraalleess [[110011]]
7 28 17 N Contabilidad Banco de España - Balance (I) - Activo - Cartera de negociación [102]
8 45 17 N Contabilidad Banco de España - Balance (I) - Activo - Depósitos en entidades de crédito [103]
9 62 17 N Contabilidad Banco de España - Balance (I) - Activo - Crédito a la clientela [104]
10 79 17 N Contabilidad Banco de España - Balance (I) - Activo - Valores representativos de deuda [105]
11 96 17 N Contabilidad Banco de España - Balance (I) - Activo - Otros instrumentos de capital [106]
12 113 17 N Contabilidad Banco de España - Balance (I) - Activo - Derivados de negociación [107]
Contabilidad Banco de España - Balance (I) - Activo - Otros activos financieros a valor razonable con cambios en
13 130 17 N pérdidas y ganancias [108]
14 147 17 N Contabilidad Banco de España - Balance (I) - Activo - Depósitos en entidades de crédito [109]
15 164 17 N Contabilidad Banco de España - Balance (I) - Activo - Crédito a la clientela [110]
16 181 17 N Contabilidad Banco de España - Balance (I) - Activo - Valores representativos de deuda [111]
17 198 17 N Contabilidad Banco de España - Balance (I) - Activo - Instrumentos de capital [112]
1188 221155 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - BBaallaannccee ((II)) - AAccttiivvoo - AAccttiivvooss ffiinnaanncciieerrooss ddiissppoonniibblleess ppaarraa llaa vveennttaa [[111133]]
19 232 17 N Contabilidad Banco de España - Balance (I) - Activo - Valores representativos de deuda [114]
20 249 17 N Contabilidad Banco de España - Balance (I) - Activo - Instrumentos de capital [115]
21 266 17 N Contabilidad Banco de España - Balance (I) - Activo - Inversiones crediticias [116]
22 283 17 N Contabilidad Banco de España - Balance (I) - Activo - Depósitos en entidades de crédito [117]
23 300 17 N Contabilidad Banco de España - Balance (I) - Activo - Crédito a la clientela [118]
24 317 17 N Contabilidad Banco de España - Balance (I) - Activo - Valores representativos de deuda [119]
25 334 17 N Contabilidad Banco de España - Balance (I) - Activo - Cartera de inversión a vencimiento [120]
Contabilidad Banco de España - Balance (I) - Activo - Ajustes a activos financieros por macro-coberturas [121]
26 351 17 N
27 368 17 N Contabilidad Banco de España - Balance (I) - Activo - Derivados de cobertura [122]
28 385 17 N Contabilidad Banco de España - Balance (I) - Activo - Activos no corrientes en venta [123]
29 402 17 N Contabilidad Banco de España - Balance (I) - Activo - Participaciones [124]
30 419 17 N CConttabbiilliiddadd BBanco dde EEspañña - BBallance ((II)) - AActtiivo - EEnttiiddaddes asociiaddas [[112255]]
31 436 17 N Contabilidad Banco de España - Balance (I) - Activo - Entidades multigrupo [126]
32 453 17 N Contabilidad Banco de España - Balance (I) - Activo - Entidades del grupo [127]
Contabilidad Banco de España - Balance (I) - Activo - Contratos de seguros vinculados a pensiones [128]
33 470 17 N
34 487 17 N Contabilidad Banco de España - Balance (I) - Activo - Activo material [129]
35 504 17 N Contabilidad Banco de España - Balance (I) - Activo - Inmovilizado material [130]
36 521 17 N Contabilidad Banco de España - Balance (I) - Activo - Inmovilizado material - De uso propio [131]
Contabilidad Banco de España - Balance (I) - Activo - Inmovilizado material - Cedido en arrendamiento operativo
37 538 17 N [132]
38 555 17 N Contabilidad Banco de España - Balance (I) - Activo - Inmovilizado material - Afecto a la Obra social [133]
39 572 17 N Contabilidad Banco de España - Balance (I) - Activo - Inversiones inmobiliarias [134]
40 589 17 N Contabilidad Banco de España - Balance (I) - Activo - Activo intangible [135]
41 606 17 N Contabilidad Banco de España - Balance (I) - Activo - Fondo de comercio [136]
42 623 17 N Contabilidad Banco de España - Balance (I) - Activo - Otro activo intangible [137]
43 640 17 N Contabilidad Banco de España - Balance (I) - Activo - Activos fiscales [138]
44 657 17 N Contabilidad Banco de España - Balance (I) - Activo - Corrientes [139]
45 674 17 N Contabilidad Banco de España - Balance (I) - Activo - Diferidos [140]
46 691 17 N Contabilidad Banco de España - Balance (I) - Activo - Resto de activos [141]
47 708 17 N Contabilidad Banco de España - Balance (I) - Activo - Total Activo - [142]
Contabilidad Banco de España - Balance (I) - Información adicional - Fondos insolvencias por cobertura específica
48 725 17 N [202]
Contabilidad Banco de España - Balance (I) - Información adicional - Fondos insolvencias por cobertura genérica
49 742 17 N [203]
50 759 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200250>"
Total: 768
Página 50

# Pag. 51

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "260"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
6 11 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Cartera de negociación [143]
7 28 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de bancos centrales [144]
8 45 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de entidades de crédito [145]
9 62 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de la clientela [146]
Contabilidad Banco de España - Balance (II) - Pasivo - Débitos representados por valores negociables [147]
10 79 17 N
11 96 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Derivados de negociación [148]
12 113 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Posiciones cortas de valores [149]
13 130 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Otros pasivos financieros [150]
Contabilidad Banco de España - Balance (II) - Pasivo - Otros pasivos financieros a valor razonable con cambios en
14 147 17 N pérdidas y ganancias [151]
15 164 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de bancos centrales [152]
16 181 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de entidades de crédito [153]
17 198 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de la clientela [154]
CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - BBaallaannccee ((IIII)) - PPaassiivvoo - DDéébbiittooss rreepprreesseennttaaddooss ppoorr vvaalloorreess nneeggoocciiaabblleess [[115555]]
18 215 17 N
19 232 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos subordinados [156]
20 249 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Otros pasivos financieros [157]
21 266 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos financieros a coste amortizado [158]
22 283 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de bancos centrales [159]
23 300 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de entidades de crédito [160]
24 317 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Depósitos de la clientela [161]
Contabilidad Banco de España - Balance (II) - Pasivo - Débitos representados por valores negociables [162]
25 334 17 N
26 351 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos subordinados [163]
27 368 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Otros pasivos financieros [164]
Contabilidad Banco de España - Balance (II) - Pasivo - Ajustes a pasivos financieros por macro-coberturas [165]
2288 338855 1177 NN
29 402 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Derivados de cobertura [166]
Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos asociados con activos no corrientes en venta [167]
30 419 17 N
31 436 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Provisiones [168]
Contabilidad Banco de España - Balance (II) - Pasivo - Fondo para pensiones y obligaciones similares [169]
32 453 17 N
Contabilidad Banco de España - Balance (II) - Pasivo - Provisiones para impuestos y otras contingencias legales
33 470 17 N [170]
Contabilidad Banco de España - Balance (II) - Pasivo - Provisiones para riesgos y compromisos contingentes [171]
34 487 17 N
35 504 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Otras provisiones [172]
36 521 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Pasivos fiscales [173]
37 538 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Corrientes [174]
3388 555555 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - BBaallaannccee ((IIII)) - PPaassiivvoo - DDiiffeerriiddooss [[117755]]
39 572 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Fondo de la Obra social [176]
40 589 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Resto de pasivos [177]
41 606 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Capital reembolsable a la vista [178]
42 623 17 N Contabilidad Banco de España - Balance (II) - Pasivo - Total pasivo [179]
43 640 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200260>"
Total: 649
Página 51

# Pag. 52

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de
vers. 1.0
atribución de rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "270"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
6 11 17 N Contabilidad Banco de España - Balance (III) - Patrimonio neto - Fondos propios [180]
CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa -- BBaallaannccee ((IIIIII)) -- PPaattrriimmoonniioo nneettoo -- CCaappiittaall//FFoonnddoo ddoottaacciióónn [[118811]]
7 28 17 N
Contabilidad Banco de España - Balance (III) - Patrimonio neto Capital/Fondo dotación - Escriturado
8 45 17 N [182]
Contabilidad Banco de España - Balance (III) - Patrimonio neto - Capital/Fondo dotación - Menos:
9 62 17 N capital no exigido [183]
10 79 17 N Contabilidad Banco de España - Balance (III) - Patrimonio neto - Prima de emisión [184]
11 96 17 N Contabilidad Banco de España - Balance (III) - Patrimonio neto - Reservas [185]
Contabilidad Banco de España - Balance (III) - Patrimonio neto - Reservas - Reserva de revalorización
12 113 17 N [203]
Contabilidad Banco de España - Balance (III) - Patrimonio neto - Otros instrumentos de capital [186]
13 130 17 N
Contabilidad Banco de España - Balance (III) - Patrimonio neto - Otros instrumentos de capital - De
14 147 17 N instrumentos financieros compuestos [187]
Contabilidad Banco de Esppaña - Balance ((III)) - Patrimonio neto - Otros instrumentos de cappital - Cuotas
15 164 17 N participativas y fondos asociados [188]
Contabilidad Banco de España - Balance (III) - Patrimonio neto - Otros instrumentos de capital - Resto
16 181 17 N de instrumentos de capital [189]
Contabilidad Banco de España - Balance (III) - Patrimonio neto - Menos: valores propios [190]
17 198 17 N
18 215 17 N Contabilidad Banco de España - Balance (III) - Patrimonio neto - Resultado del ejercicio [191]
Contabilidad Banco de España - Balance (III) - Patrimonio neto - Menos: Dividendos y retribuciones
19 232 17 N [192]
20 249 17 N Contabilidad Banco de España - Balance (III) - Patrimonio neto - Ajustes por valoración [193]
Contabilidad Banco de España - Balance (III) - Patrimonio neto - Activos financieros disponibles para la
21 266 17 N venta [194]
Contabilidad Banco de España - Balance (III) - Patrimonio neto - Coberturas de los flujos de efectivo
22 283 17 N [195]
Contabilidad Banco de España - Balance (III) - Patrimonio neto - Coberturas de inversiones netas en
2233 330000 1177 NN nneeggoocciiooss eenn eell eexxttrraannjjeerroo [[119966]]
24 317 17 N Contabilidad Banco de España - Balance (III) - Patrimonio neto - Diferencias de cambio [197]
Contabilidad Banco de España - Balance (III) - Patrimonio neto - Activos no corrientes en venta [198]
25 334 17 N
Contabilidad Banco de España - Balance (III) - Patrimonio neto - Resto de ajustes por valoración [199]
26 351 17 N
27 368 17 N Contabilidad Banco de España - Balance (III) - Patrimonio neto - Total patrimonio neto [200]
Contabilidad Banco de España - Balance (III) - Patrimonio neto - Total pasivo y patrimonio neto [201]
28 385 17 N
29 402 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200270>"
Total: 411
Página 52

# Pag. 53

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "280"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - PPéérrddiiddaass yy ggaannaanncciiaass - IInntteerreesseess yy rreennddiimmiieennttooss aassiimmiillaaddooss [[220044]]
7 28 17 N Contabilidad Banco de España - Pérdidas y ganancias - Intereses y cargas asimiladas [205]
Contabilidad Banco de España - Pérdidas y ganancias - Remuneración de capital reembolsable a la vista [206]
8 45 17 N
9 62 17 N Contabilidad Banco de España - Pérdidas y ganancias - Margen de intereses [207]
10 79 17 N Contabilidad Banco de España - Pérdidas y ganancias - Rendimiento de instrumentos de capital [208]
11 96 17 N Contabilidad Banco de España - Pérdidas y ganancias - Comisiones percibidas [209]
12 113 17 N Contabilidad Banco de España - Pérdidas y ganancias - Comisiones pagadas [210]
13 130 17 N Contabilidad Banco de España - Pérdidas y ganancias - Resultado de operaciones financieras [211]
14 147 17 N Contabilidad Banco de España - Pérdidas y ganancias - Cartera de negociación [212]
Contabilidad Banco de España - Pérdidas y ganancias - Otros instrumentos financieros a valor razonable con
15 164 17 N cambios en pérdidas y ganancias [213]
Contabilidad Banco de España - Pérdidas y ganancias - Instrumentos financieros no valorados a valor razonable con
1166 118811 1177 NN ccaammbbiiooss eenn ppéérrddiiddaass yy ggaannaanncciiaass [[221144]]
17 198 17 N Contabilidad Banco de España - Pérdidas y ganancias - Otros [215]
18 215 17 N Contabilidad Banco de España - Pérdidas y ganancias - Diferencias de cambio [216]
19 232 17 N Contabilidad Banco de España - Pérdidas y ganancias - Otros productos de explotación [217]
20 249 17 N Contabilidad Banco de España - Pérdidas y ganancias - Otras cargas de explotación [218]
21 266 17 N Contabilidad Banco de España - Pérdidas y ganancias - Margen bruto [219]
22 283 17 N Contabilidad Banco de España - Pérdidas y ganancias - Gastos de administración [220]
23 300 17 N Contabilidad Banco de España - Pérdidas y ganancias - Gastos de personal [221]
24 317 17 N Contabilidad Banco de España - Pérdidas y ganancias - Otros gastos generales de admón. [222]
25 334 17 N Contabilidad Banco de España - Pérdidas y ganancias - Amortización [223]
26 351 17 N Contabilidad Banco de España - Pérdidas y ganancias - Dotaciones a provisiones [224]
Contabilidad Banco de España - Pérdidas y ganancias - Pérdidas por deterioro de activos financieros [225]
27 368 17 N
2288 338855 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - PPéérrddiiddaass yy ggaannaanncciiaass - IInnvveerrssiioonneess ccrreeddiittiicciiaass [[222266]]
Contabilidad Banco de España - Pérdidas y ganancias - Otros instrumentos financieros no valorados a valor
29 402 17 N razonable con cambios en pérdidas y ganancias [227]
30 419 17 N Contabilidad Banco de España - Pérdidas y ganancias - Resultado de la actividad de explotación [228]
Contabilidad Banco de España - Pérdidas y ganancias - Pérdidas por deterioro del resto de activos [229]
31 436 17 N
Contabilidad Banco de España - Pérdidas y ganancias - Fondo de comercio y otro activo intangible [230]
32 453 17 N
33 470 17 N Contabilidad Banco de España - Pérdidas y ganancias - Otros activos [231]
Contabilidad Banco de España - Pérdidas y ganancias - Ganancias (pérdidas) en la baja de activos no clasificados
34 487 17 N como no corrientes en venta [232]
Contabilidad Banco de España - Pérdidas y ganancias - Diferencia negativa en combinaciones de negocios [233]
35 504 17 N
CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - PPéérrddiiddaass yy ggaannaanncciiaass - GGaannaanncciiaass ((ppéérrddiiddaass)) ddee aaccttiivvooss nnoo ccoorrrriieenntteess eenn vveennttaa nnoo
36 521 17 N clasificados como operaciones interrumpidas [234]
37 538 17 N Contabilidad Banco de España - Pérdidas y ganancias - Resultado antes de impuestos [235]
38 555 17 N Contabilidad Banco de España - Pérdidas y ganancias - Impuesto sobre beneficios [236]
Contabilidad Banco de España - Pérdidas y ganancias - Dotación obligatoria a obras y fondos sociales [237]
39 572 17 N
Contabilidad Banco de España - Pérdidas y ganancias - Resultado del ejercicio procedente de operaciones
40 589 17 N continuadas [238]
Contabilidad Banco de España - Pérdidas y ganancias - Resultado de operaciones interrumpidas [239]
41 606 17 N
42 623 17 N Contabilidad Banco de España - Pérdidas y ganancias - Resultado del ejercicio [500]
43 640 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200280>"
Total: 649
Página 53

# Pag. 54

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "290"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
66 1111 1177 NN RResullttaddo ddell ejjerciiciio [[550000]]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
7 28 17 N Otros ingresos y gastos reconocidos [256]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
8 45 17 N Activos financieros disponibles para la venta [257]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos
9 62 17 N Reconocidos.Ganancias (pérdidas) por valoración [258]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos
10 79 17 N Reconocidos.Importes transferidos a la cuenta de pérdidas y ganancias [259]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos
11 96 17 N Reconocidos.Otras reclasificaciones [260]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos
12 113 17 N Reconocidos.Coberturas de los flujos de efectivo [261]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos
1133 113300 1177 NN RReconociiddos.GGananciias ((péérddiiddas)) por valloraciióón [[226622]]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos
14 147 17 N Reconocidos.Importes transferidos a la cuenta de pérdidas y ganancias [263]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos
15 164 17 N Reconocidos.Importes transferidos al valor inicial de las partidas cubiertas [264]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
16 181 17 N Otras reclasificaciones [265]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos
17 198 17 N Reconocidos.Coberturas de inversiones netas en negocios en el extranjero [266]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos
18 215 17 N Reconocidos.Ganancias (pérdidas) por valoración [267]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
19 232 17 N Importes transferidos a la cuenta de pérdidas y ganancias [268]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
2200 224499 1177 NN OOttras recllasiiffiicaciiones [[226699]]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
21 266 17 N Diferencias de cambio [270]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
22 283 17 N Ganancias (pérdidas) por valoración [271]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
23 300 17 N Importes transferidos a la cuenta de pérdidas y ganancias [272]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
24 317 17 N Otras reclasificaciones [273]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
25 334 17 N Activos no corrientes en venta [274]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de Ingresos y gastos
26 351 17 N Reconocidos.Ganancias (pérdidas) por valoración [275]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
2277 336688 1177 NN IImporttes ttransfferiiddos a lla cuentta dde péérddiiddas y gananciias [[227766]]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
28 385 17 N Otras reclasificaciones [277]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
29 402 17 N Ganancias (pérdidas) actuariales en planes de pensiones [278]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
30 419 17 N Resto de ingresos y gastos reconocidos [279]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
31 436 17 N Impuesto sobre beneficios [280]
Contabilidad Banco de España - Estado cambios patrimonio neto (I) - Estado de ingresos y gastos reconocidos -
32 453 17 N Total ingresos y gastos reconocidos [281]
33 470 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200290>"
Total: 479
Página 54

# Pag. 55

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "300"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIII)) - EEssttaaddoo ttoottaall ccaammbbiiooss - SSaallddoo ffiinnaall eejjeerrcc..
6 11 17 N anterior - Capital/fondo dotación [282]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final ejerc.
7 28 17 N anterior -Prima emisión [283]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final ejerc.
8 45 17 N anterior -Reservas [284]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final ejerc.
9 62 17 N anterior -Otros instrumentos capital [285]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final ejerc.
10 79 17 N anterior -Menos: valores propios [286]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes cambio criterio
11 96 17 N contable - Capital/fondo dotación [292]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes cambio criterio
12 113 17 N contable - Prima emisión [293]
CConttabbiilliiddadd BBanco dde EEspañña - EEsttaddo cambbiios pattriimoniio netto ((IIII)) - EEsttaddo ttottall cambbiios - AAjjusttes cambbiio criitteriio
13 130 17 N contable - Reservas [294]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes cambio criterio
14 147 17 N contable - Otros instrumentos capital [295]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes cambio criterio
15 164 17 N contable - Menos: valores propios [296]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes por errores -
16 181 17 N Capital/fondo dotación [302]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes por errores -
17 198 17 N Prima emisión [303]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes por errores -
18 215 17 N Reservas [304]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes por errores -
1199 223322 1177 NN OOttrrooss iinnssttrruummeennttooss ccaappiittaall [[330055]]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Ajustes por errores -
20 249 17 N Menos: valores propios [306]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo inicial ajustado -
21 266 17 N Capital/fondo dotación [312]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo inicial ajustado -
22 283 17 N Prima emisión [313]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo inicial ajustado -
23 300 17 N Reservas [314]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo inicial ajustado -
24 317 17 N Otros instrumentos capital [315]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo inicial ajustado -
25 334 17 N Menos: valores propios [316]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Total ingresos y gastos
2266 335511 1177 NN rreeccoonnoocciiddooss - CCaappiittaall//ffoonnddoo ddoottaacciióónn [[332222]]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Total ingresos y gastos
27 368 17 N reconocidos - Prima emisión [323]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Total ingresos y gastos
28 385 17 N reconocidos - Reservas [324]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Total ingresos y gastos
29 402 17 N reconocidos - Otros instrumentos capital [325]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Total ingresos y gastos
30 419 17 N reconocidos - Menos: valores propios [326]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del
31 436 17 N patrimonio neto - Capital/fondo dotación [332]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del
32 453 17 N patrimonio neto - Prima emisión [333]
CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIII)) - EEssttaaddoo ttoottaall ccaammbbiiooss - OOttrraass vvaarriiaacciioonneess ddeell
33 470 17 N patrimonio neto - Reservas [334]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del
34 487 17 N patrimonio neto - Otros instrumentos capital [335]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Otras variaciones del
35 504 17 N patrimonio neto - Menos: valores propios [336]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumentos de capital/
36 521 17 N fondo de dotación - Capital/fondo dotación [342]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumentos de capital/
37 538 17 N fondo de dotación - Prima emisión [343]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumentos de capital/
38 555 17 N fondo de dotación - Reservas [344]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Aumentos de capital/
39 572 17 N fondo de dotación - Otros instrumentos capital [345]
CConttabbiilliiddadd BBanco dde EEspañña - EEsttaddo cambbiios pattriimoniio netto ((IIII)) - EEsttaddo ttottall cambbiios - AAumenttos dde capiittall//
40 589 17 N fondo de dotación - Menos: valores propios [346]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducciones de capital -
41 606 17 N Capital/fondo dotación [352]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducciones de capital -
42 623 17 N Prima emisión [353]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducciones de capital -
43 640 17 N Reservas [354]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducciones de capital -
44 657 17 N Otros instrumentos capital [355]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reducciones de capital -
45 674 17 N Menos: valores propios [356]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de pasivos
4466 669911 1177 NN ffiinnaanncciieerrooss eenn ccaappiittaall - CCaappiittaall//ffoonnddoo ddoottaacciióónn [[336622]]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de pasivos
47 708 17 N financieros en capital - Prima emisión [363]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de pasivos
48 725 17 N financieros en capital - Reservas [364]
Página 55

# Pag. 56

Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de pasivos
49 742 17 N financieros en capital - Otros instrumentos capital [365]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Conversión de pasivos
50 759 17 N financieros en capital - Menos: valores propios [366]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos de otros
51 776 17 N instrumentos de capital - Capital/fondo dotación [372]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos de otros
52 793 17 N instrumentos de capital - Prima emisión [373]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos de otros
53 810 17 N instrumentos de capital - Reservas [374]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos de otros
54 827 17 N instrumentos de capital - Otros instrumentos capital [375]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos de otros
5555 884444 1177 NN iinnssttrruummeennttooss ddee ccaappiittaall -- MMeennooss:: vvaalloorreess pprrooppiiooss [[337766]]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de
56 861 17 N pasivos financieros a otros instrumentos de capital - Capital/fondo dotación [382]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de
57 878 17 N pasivos financieros a otros instrumentos de capital - Prima emisión [383]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de
58 895 17 N pasivos financieros a otros instrumentos de capital - Reservas [384]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de
59 912 17 N pasivos financieros a otros instrumentos de capital - Otros instrumentos capital [385]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de
60 929 17 N pasivos financieros a otros instrumentos de capital - Menos: valores propios [386]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de otros
61 946 17 N instrumentos de capital a pasivos financieros - Capital/fondo dotación [392]
Contabilidad Banco de Esppaña - Estado cambios ppatrimonio neto ((II)) - Estado total cambios - Reclasificación de otros
62 963 17 N instrumentos de capital a pasivos financieros - Prima emisión [393]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de otros
63 980 17 N instrumentos de capital a pasivos financieros - Reservas [394]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de otros
64 997 17 N instrumentos de capital a pasivos financieros - Otros instrumentos capital [395]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Reclasificación de otros
65 1014 17 N instrumentos de capital a pasivos financieros - Menos: valores propios [396]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Distribución de
66 1031 17 N dividendos / Remuneración a los socios - Capital/fondo dotación [402]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Distribución de
67 1048 17 N dividendos / Remuneración a los socios - Prima emisión [403]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Distribución de
68 1065 17 N dividendos / Remuneración a los socios - Reservas [404]
CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa -- EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIII)) -- EEssttaaddoo ttoottaall ccaammbbiiooss -- DDiissttrriibbuucciióónn ddee
69 1082 17 N dividendos / Remuneración a los socios - Otros instrumentos capital [405]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Distribución de
70 1099 17 N dividendos / Remuneración a los socios - Menos: valores propios [406]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Operaciones con
71 1116 17 N instrumentos de capital propio (neto) - Capital/fondo dotación [412]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Operaciones con
72 1133 17 N instrumentos de capital propio (neto) - Prima emisión [413]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Operaciones con
73 1150 17 N instrumentos de capital propio (neto) - Reservas [414]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Operaciones con
74 1167 17 N instrumentos de capital propio (neto) - Otros instrumentos capital [415]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Operaciones con
75 1184 17 N instrumentos de capital propio (neto) - Menos: valores propios [416]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Traspasos entre
76 1201 17 N partidas de patrimonio neto - Capital/fondo dotación [422]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Traspasos entre
77 1218 17 N partidas de patrimonio neto - Prima emisión [423]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Traspasos entre
78 1235 17 N partidas de patrimonio neto - Reservas [424]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Traspasos entre
79 1252 17 N partidas de patrimonio neto - Otros instrumentos capital [425]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Traspasos entre
80 1269 17 N partidas de patrimonio neto - Menos: valores propios [426]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos
81 1286 17 N (reducciones) por combinaciones de negocios - Capital/fondo dotación [432]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos
8822 11330033 1177 NN ((rreedduucccciioonneess)) ppoorr ccoommbbiinnaacciioonneess ddee nneeggoocciiooss -- PPrriimmaa eemmiissiióónn [[443333]]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos
83 1320 17 N (reducciones) por combinaciones de negocios - Reservas [434]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos
84 1337 17 N (reducciones) por combinaciones de negocios - Otros instrumentos capital [435]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Incrementos
85 1354 17 N (reducciones) por combinaciones de negocios - Menos: valores propios [436]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dotación discrecional a
86 1371 17 N obras y fondos sociales - Capital/fondo dotación [442]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dotación discrecional a
87 1388 17 N obras y fondos sociales - Prima emisión [443]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dotación discrecional a
88 1405 17 N obras y fondos sociales - Reservas [444]
Contabilidad Banco de Esppaña - Estado cambios ppatrimonio neto ((II)) - Estado total cambios - Dotación discrecional a
89 1422 17 N obras y fondos sociales - Otros instrumentos capital [445]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Dotación discrecional a
90 1439 17 N obras y fondos sociales - Menos: valores propios [446]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Pagos con
91 1456 17 N instrumentos de capital - Capital/fondo dotación [452]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Pagos con
92 1473 17 N instrumentos de capital - Prima emisión [453]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Pagos con
93 1490 17 N instrumentos de capital - Reservas [454]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Pagos con
94 1507 17 N instrumentos de capital - Otros instrumentos capital [455]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Pagos con
95 1524 17 N instrumentos de capital - Menos: valores propios [456]
CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa -- EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIII)) -- EEssttaaddoo ttoottaall ccaammbbiiooss -- RReessttoo ddee iinnccrreemmeennttooss
96 1541 17 N (reducciones) de patrimonio neto - Capital/fondo dotación [462]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Resto de incrementos
97 1558 17 N (reducciones) de patrimonio neto - Prima emisión [463]
Página 56

# Pag. 57

Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Resto de incrementos
98 1575 17 N (reducciones) de patrimonio neto - Reservas [464]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Resto de incrementos
99 1592 17 N (reducciones) de patrimonio neto - Otros instrumentos capital [465]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Resto de incrementos
100 1609 17 N (reducciones) de patrimonio neto - Menos: valores propios [466]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final -
101 1626 17 N Capital/fondo dotación [472]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final - Prima
102 1643 17 N emisión [473]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final - Reservas
103 1660 17 N [474]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final - Otros
110044 11667777 1177 NN iinnssttrruummeennttooss ccaappiittaall [[447755]]
Contabilidad Banco de España - Estado cambios patrimonio neto (II) - Estado total cambios - Saldo final - Menos:
105 1694 17 N valores propios [476]
106 1711 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200300>"
Total: 1720
Página 57

# Pag. 58

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "310"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIIIII)) - EEssttaaddoo ttoottaall ccaammbbiiooss - SSaallddoo ffiinnaall eejjeerrcc.
6 11 17 N Anterior - Resultado ejercicio [287]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final ejerc.
7 28 17 N anterior - Menos:dividendos y retribuciones [288]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final ejerc.
8 45 17 N anterior - Total fondos propios [289]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final ejerc.
9 62 17 N anterior - Ajustes por valoración [290]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final ejerc.
10 79 17 N anterior - Total patrimonio neto [291]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por cambio
11 96 17 N de criterio contable - Resultado ejercicio [297]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por cambio
1122 111133 1177 NN ddee ccrriitteerriioo ccoonnttaabbllee -- MMeennooss::ddiivviiddeennddooss yy rreettrriibbuucciioonneess [[229988]]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por cambio
13 130 17 N de criterio contable - Total fondos propios [299]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por cambio
14 147 17 N de criterio contable - Ajustes por valoración [300]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por cambio
15 164 17 N de criterio contable - Total patrimonio neto [301]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por errores -
16 181 17 N Resultado ejercicio [307]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por errores -
17 198 17 N Menos:dividendos y retribuciones [308]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por errores -
18 215 17 N Total fondos propios [309]
CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIIIII)) - EEssttaaddoo ttoottaall ccaammbbiiooss - AAjjuusstteess ppoorr eerrrroorreess -
19 232 17 N Ajustes por valoración [310]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Ajustes por errores -
20 249 17 N Total patrimonio neto [311]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo inicial
21 266 17 N ajustado - Resultado ejercicio [317]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo inicial
22 283 17 N ajustado - Menos:dividendos y retribuciones [318]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo inicial
23 300 17 N ajustado - Total fondos propios [319]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo inicial
24 317 17 N ajustado - Ajustes por valoración [320]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo inicial
25 334 17 N ajjustado - Total ppatrimonio neto [[321]]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Total ingresos y
26 351 17 N gastos reconocidos - Resultado ejercicio [327]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Total ingresos y
27 368 17 N gastos reconocidos - Menos:dividendos y retribuciones [328]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Total ingresos y
28 385 17 N gastos reconocidos - Total fondos propios [329]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Total ingresos y
29 402 17 N gastos reconocidos - Ajustes por valoración [330]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Total ingresos y
30 419 17 N gastos reconocidos - Total patrimonio neto [331]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Otras variaciones
31 436 17 N del patrimonio neto - Resultado ejercicio [337]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Otras variaciones
3322 44533 117 NN ddell pattriimoniio netto - MMenos:ddiiviiddenddos y rettriibbuciiones [[333388]]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Otras variaciones
33 470 17 N del patrimonio neto - Total fondos propios [339]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Otras variaciones
34 487 17 N del patrimonio neto - Ajustes por valoración [340]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Otras variaciones
35 504 17 N del patrimonio neto - Total patrimonio neto [341]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Aumentos de
36 521 17 N capital/ fondo de dotacion - Resultado ejercicio [347]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Aumentos de
37 538 17 N capital/ fondo de dotacion - Menos:dividendos y retribuciones [348]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Aumentos de
38 555 17 N capital/ fondo de dotacion - Total fondos propios [349]
CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIIIII)) - EEssttaaddoo ttoottaall ccaammbbiiooss - AAuummeennttooss ddee
39 572 17 N capital/ fondo de dotacion - Ajustes por valoración [350]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Aumentos de
40 589 17 N capital/ fondo de dotacion - Total patrimonio neto [351]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reducciones de
41 606 17 N capital - Resultado ejercicio [357]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reducciones de
42 623 17 N capital - Menos:dividendos y retribuciones [358]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reducciones de
43 640 17 N capital - Total fondos propios [359]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reducciones de
44 657 17 N capital - Ajustes por valoración [360]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reducciones de
4455 667744 1177 NN ccaappiittaall -- TToottaall ppaattrriimmoonniioo nneettoo [[336611]]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Conversión de
46 691 17 N pasivos financieros en capital - Resultado ejercicio [367]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Conversión de
47 708 17 N pasivos financieros en capital - Menos:dividendos y retribuciones [368]
Página 58

# Pag. 59

Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Conversión de
48 725 17 N pasivos financieros en capital - Total fondos propios [369]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Conversión de
49 742 17 N pasivos financieros en capital - Ajustes por valoración [370]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Conversión de
50 759 17 N pasivos financieros en capital - Total patrimonio neto [371]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos de
51 776 17 N otros instrumentos de capital - Resultado ejercicio [377]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos de
52 793 17 N otros instrumentos de capital - Menos:dividendos y retribuciones [378]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos de
53 810 17 N otros instrumentos de capital - Total fondos propios [379]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos de
544 88227 117 NN ottros iinsttrumenttos dde capiittall - AAjjusttes por valloraciióón [[338800]]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos de
55 844 17 N otros instrumentos de capital - Total patrimonio neto [381]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de
56 861 17 N pasivos financieros a otros instrumentos de capital - Resultado ejercicio [387]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de
pasivos financieros a otros instrumentos de capital - Menos:dividendos y retribuciones [388]
57 878 17 N
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de
58 895 17 N pasivos financieros a otros instrumentos de capital - Total fondos propios [389]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de
59 912 17 N pasivos financieros a otros instrumentos de capital - Ajustes por valoración [390]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de
6600 992299 1177 NN ppaassiivvooss ffiinnaanncciieerrooss aa oottrrooss iinnssttrruummeennttooss ddee ccaappiittaall - TToottaall ppaattrriimmoonniioo nneettoo [[339911]]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de
61 946 17 N otros instrumentos de capital a pasivos financieros - Resultado ejercicio [397]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de
otros instrumentos de capital a pasivos financieros - Menos:dividendos y retribuciones [398]
62 963 17 N
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de
63 980 17 N otros instrumentos de capital a pasivos financieros - Total fondos propios [399]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de
64 997 17 N otros instrumentos de capital a pasivos financieros - Ajustes por valoración [400]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Reclasificación de
65 1014 17 N otros instrumentos de capital a pasivos financieros - Total patrimonio neto [401]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Distribución de
6666 11003311 1177 NN ddiivviiddeennddooss // RReemmuunneerraacciióónn aa llooss ssoocciiooss -- RReessuullttaaddoo eejjeerrcciicciioo [[440077]]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Distribución de
67 1048 17 N dividendos / Remuneración a los socios - Menos:dividendos y retribuciones [408]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Distribución de
68 1065 17 N dividendos / Remuneración a los socios - Total fondos propios [409]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Distribución de
69 1082 17 N dividendos / Remuneración a los socios - Ajustes por valoración [410]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Distribución de
70 1099 17 N dividendos / Remuneración a los socios - Total patrimonio neto [411]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Operaciones con
71 1116 17 N instrumentos de capital propio (neto) - Resultado ejercicio [417]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Operaciones con
72 1133 17 N instrumentos de capital propio (neto) - Menos:dividendos y retribuciones [418]
CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa -- EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo ((IIIIII)) -- EEssttaaddoo ttoottaall ccaammbbiiooss -- OOppeerraacciioonneess ccoonn
73 1150 17 N instrumentos de capital propio (neto) - Total fondos propios [419]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Operaciones con
74 1167 17 N instrumentos de capital propio (neto) - Ajustes por valoración [420]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Operaciones con
75 1184 17 N instrumentos de capital propio (neto) - Total patrimonio neto [421]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Traspasos entre
76 1201 17 N partidas de patrimonio neto - Resultado ejercicio [427]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Traspasos entre
77 1218 17 N partidas de patrimonio neto - Menos:dividendos y retribuciones [428]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Traspasos entre
78 1235 17 N partidas de patrimonio neto - Total fondos propios [429]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Traspasos entre
7799 11225522 1177 NN ppaarrttiiddaass ddee ppaattrriimmoonniioo nneettoo - AAjjuusstteess ppoorr vvaalloorraacciióónn [[443300]]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Traspasos entre
80 1269 17 N partidas de patrimonio neto - Total patrimonio neto [431]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos
81 1286 17 N (reducciones) por combinaciones de negocios - Resultado ejercicio [437]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos
82 1303 17 N (reducciones) por combinaciones de negocios - Menos:dividendos y retribuciones [438]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos
83 1320 17 N (reducciones) por combinaciones de negocios - Total fondos propios [439]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos
84 1337 17 N (reducciones) por combinaciones de negocios - Ajustes por valoración [440]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Incrementos
85 1354 17 N (reducciones) por combinaciones de negocios - Total patrimonio neto [441]
Contabilidad Banco de Esppaña - Estado cambios ppatrimonio neto ((III)) - Estado total cambios - Dotación
86 1371 17 N discrecional a obras y fondos sociales - Resultado ejercicio [447]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Dotación
87 1388 17 N discrecional a obras y fondos sociales - Menos:dividendos y retribuciones [448]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Dotación
88 1405 17 N discrecional a obras y fondos sociales - Total fondos propios [449]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Dotación
89 1422 17 N discrecional a obras y fondos sociales - Ajustes por valoración [450]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Dotación
90 1439 17 N discrecional a obras y fondos sociales - Total patrimonio neto [451]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Pagos con
91 1456 17 N instrumentos de capital - Resultado ejercicio [457]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Pagos con
92 1473 17 N instrumentos de capital - Menos:dividendos y retribuciones [458]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Pagos con
93 1490 17 N instrumentos de capital - Total fondos propios [459]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Pagos con
94 1507 17 N instrumentos de capital - Ajustes por valoración [460]
Página 59

# Pag. 60

Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Pagos con
95 1524 17 N instrumentos de capital - Total patrimonio neto [461]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Resto de
96 1541 17 N incrementos (reducciones) de patrimonio neto - Resultado ejercicio [467]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Resto de
97 1558 17 N incrementos (reducciones) de patrimonio neto - Menos:dividendos y retribuciones [468]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Resto de
98 1575 17 N incrementos (reducciones) de patrimonio neto - Total fondos propios [469]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Resto de
99 1592 17 N incrementos (reducciones) de patrimonio neto - Ajustes por valoración [470]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Resto de
100 1609 17 N incrementos (reducciones) de patrimonio neto - Total patrimonio neto [471]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final -
110011 11662266 117 NN RResullttaddo ejjerciiciio [[447777]]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final -
102 1643 17 N Menos:dividendos y retribuciones [478]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final - Total
103 1660 17 N fondos propios [479]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final - Ajustes
104 1677 17 N por valoración [480]
Contabilidad Banco de España - Estado cambios patrimonio neto (III) - Estado total cambios - Saldo final - Total
105 1694 17 N patrimonio neto [481]
106 1711 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200310>"
Total: 1720
Página 60

# Pag. 61

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "320"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
6 11 17 N Entidades aseguradoras - Balance - Activo (I) - Efectivo y otros activos líquidos equivalentes [101]
7 28 17 N Entidades aseguradoras - Balance - Activo (I) - Activos financieros mantenidos para negociar [102]
8 45 17 N Entidades aseguradoras - Balance - Activo (I) - Instrumentos de patrimonio [103]
9 62 17 N Entidades aseguradoras - Balance - Activo (I) - Valores representativos de deuda [104]
10 79 17 N Entidades aseguradoras - Balance - Activo (I) - Derivados [105]
11 96 17 N Entidades aseguradoras - Balance - Activo (I) - Otros [106]
Entidades aseguradoras - Balance - Activo (I) - Otros activos financieros a valor razonable con cambios en perdidas
12 113 17 N y ganancias [107]
13 130 17 N Entidades aseguradoras - Balance - Activo (I) - Instrumentos de patrimonio [108]
14 147 17 N Entidades aseguradoras - Balance - Activo (I) - Valores representativos de deuda [109]
15 164 17 N Entidades aseguradoras - Balance - Activo (I) - Instrumentos híbridos [110]
Entidades aseguradoras - Balance - Activo (I) - Inversiones por cuenta de tomadores seguros vida que asuman
16 181 17 N riesgo inversión [111]
17 198 17 N Entidades aseguradoras - Balance - Activo (I) - Otros [112]
1188 221155 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass - BBaallaannccee - AAccttiivvoo ((II)) - AAccttiivvooss ffiinnaanncciieerrooss ddiissppoonniibblleess ppaarraa llaa vveennttaa [[111133]]
19 232 17 N Entidades aseguradoras - Balance - Activo (I) - Instrumentos de patrimonio [114]
20 249 17 N Entidades aseguradoras - Balance - Activo (I) - Valores representativos de deuda [115]
Entidades aseguradoras - Balance - Activo (I) - Inversiones por cuenta de tomadores seguros vida
21 266 17 N que asuman riesgo inversión [116]
22 283 17 N Entidades aseguradoras - Balance - Activo (I) - Otros [117]
23 300 17 N Entidades aseguradoras - Balance - Activo (I) - Préstamos y partidas a cobrar [118]
24 317 17 N Entidades aseguradoras - Balance - Activo (I) - Valores representativos de deuda [119]
25 334 17 N Entidades aseguradoras - Balance - Activo (I) - Préstamos [120]
26 351 17 N Entidades aseguradoras - Balance - Activo (I) - Préstamos - Anticipos sobre pólizas [121]
Entidades aseguradoras - Balance - Activo (I) - Préstamos - Préstamos a entidades del grupo y asociadas [122]
27 368 17 N
28 385 17 N Entidades aseguradoras - Balance - Activo (I) - Préstamos - Préstamos a otras partes vinculadas [123]
2299 440022 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass - BBaallaannccee - AAccttiivvoo ((II)) - DDeeppóóssiittooss eenn eennttiiddaaddeess ddee ccrrééddiittoo [[112244]]
30 419 17 N Entidades aseguradoras - Balance - Activo (I) - Depósitos constituídos por reaseguro aceptado [125]
31 436 17 N Entidades aseguradoras - Balance - Activo (I) - Créditos por operaciones de seguro directo [126]
Entidades aseguradoras - Balance - Activo (I) - Créditos por operaciones de seguro directo - Tomadores de seguro
32 453 17 N [127]
Entidades aseguradoras - Balance - Activo (I) - Créditos por operaciones de seguro directo - Mediadores [128]
33 470 17 N
34 487 17 N Entidades aseguradoras - Balance - Activo (I) - Créditos por operaciones de reaseguro [129]
35 504 17 N Entidades aseguradoras - Balance - Activo (I) - Créditos por operaciones de coaseguro [130]
36 521 17 N Entidades aseguradoras - Balance - Activo (I) - Desembolsos exigidos [131]
37 538 17 N Entidades aseguradoras - Balance - Activo (I) - Otros créditos [132]
Entidades aseguradoras - Balance - Activo (I) - Otros créditos - Créditos con las Administraciones Públicas [133]
38 555 17 N
39 572 17 N Entidades aseguradoras - Balance - Activo (I) - Otros créditos - Resto de créditos [134]
4400 558899 1177 NN EEnttiiddaddes aseguraddoras - BBallance - AActtiivo ((II)) - IInversiiones mantteniiddas hhastta ell venciimiientto [[113355]]
41 606 17 N Entidades aseguradoras - Balance - Activo (I) - Derivados de cobertura [136]
Entidades aseguradoras - Balance - Activo (I) - Participación del reaseguro en las provisiones técnicas [137]
42 623 17 N
43 640 17 N Entidades aseguradoras - Balance - Activo (I) - Provisión para primas no consumidas [138]
44 657 17 N Entidades aseguradoras - Balance - Activo (I) - Provisión de seguros de vida [139]
45 674 17 N Entidades aseguradoras - Balance - Activo (I) - Provisión para prestaciones [140]
46 691 17 N Entidades aseguradoras - Balance - Activo (I) - Otras provisiones técnicas [141]
47 708 17 N Entidades aseguradoras - Balance - Activo (I) - Inmovilizado material e inversiónes inmobiliarias [142]
48 725 17 N Entidades aseguradoras - Balance - Activo (I) - Inmovilizado material [143]
49 742 17 N Entidades aseguradoras - Balance - Activo (I) - Inversiones inmobiliarias [144]
50 759 17 N Entidades aseguradoras - Balance - Activo (I) - Inmovilizado intangible [145]
51 776 17 N Entidades aseguradoras - Balance - Activo (I) - Fondo de comercio [146]
EEnnttiiddaaddeess aasseegguurraaddoorraass - BBaallaannccee - AAccttiivvoo ((II)) - DDeerreecchhooss eeccoonnóómmiiccooss ddeerriivvaaddooss ccaarrtteerraass ddee ppóólliizzaass aaddqquuiirriiddaass aa
52 793 17 N mediadores [147]
53 810 17 N Entidades aseguradoras - Balance - Activo (I) - Otro activo intangible [148]
Entidades aseguradoras - Balance - Activo (I) - Participaciones en entidades del grupo y asociadas [149]
54 827 17 N
55 844 17 N Entidades aseguradoras - Balance - Activo (I) - Participaciones en empresas asociadas [150]
56 861 17 N Entidades aseguradoras - Balance - Activo (I) - Participaciones en empresas multigrupo [151]
57 878 17 N Entidades aseguradoras - Balance - Activo (I) - Participaciones en empresas del grupo [152]
58 895 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200320>"
Total: 904
Página 61

# Pag. 62

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "330"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass - BBaallaannccee - AAccttiivvoo ((IIII)) - AAccttiivvooss ffiissccaalleess [[115533]]
7 28 17 N Entidades aseguradoras - Balance - Activo (II) - Activos por impuesto corriente [154]
8 45 17 N Entidades aseguradoras - Balance - Activo (II) - Activos por impuesto diferido [155]
9 62 17 N Entidades aseguradoras - Balance - Activo (II) - Otros activos [156]
Entidades aseguradoras - Balance - Activo (II) - Activos y derechos de reembolso por retribuciones a largo plazo
10 79 17 N al personal [157]
Entidades aseguradoras - Balance - Activo (II) - Comisiones anticipadas y otros costes adquisición [158]
11 96 17 N
12 113 17 N Entidades aseguradoras - Balance - Activo (II) - Periodificaciones [159]
13 130 17 N Entidades aseguradoras - Balance - Activo (II) - Resto de activos [160]
14 147 17 N Entidades aseguradoras - Balance - Activo (II) - Activos mantenidos para la venta [161]
15 164 17 N Entidades aseguradoras - Balance - Activo (II) - TOTAL ACTIVO [162]
16 181 10 An Identificador de fin de reggistro OBLIGATORIO Constante "</T200330>"
Total: 190
Página 62

# Pag. 63

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimiens permanentes y entidades en régimen de atribución de rentas
vers. 1.0
constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "340"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Pasivos financieros mantenidos para
66 1111 1177 NN neggociar [[163]]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Otros pasivos financieros a valor
7 28 17 N razonable con cambios en pérdidas y ganancias. [164]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Débitos y partidas a pagar [165]
8 45 17 N
9 62 17 N Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Pasivos subordinados [166]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Depósitos recibidos por reaseguro cedido
10 79 17 N [167]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Deudas por operaciones de seguro [168]
11 96 17 N
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Deudas por operaciones de seguro -
12 113 17 N Deudas con asegurados [169]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Deudas por operaciones de seguro -
13 130 17 N Deudas con mediadores [170]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Deudas por operaciones de seguro -
1144 114477 1177 NN DDeeuuddaass ccoonnddiicciioonnaaddaass [[117711]]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Deudas por operaciones de reaseguro
15 164 17 N [172]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Deudas por operaciones de coaseguro
16 181 17 N [173]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Obligaciones y otros valores negociables
17 198 17 N [174]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Deudas con entidades de crédito [175]
18 215 17 N
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Deudas por operaciones preparatorias de
19 232 17 N contratos de seguro [176]
20 249 17 N Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Otras deudas [177]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Otras deudas - Deudas con las
21 266 17 N Administraciones Públicas [178]
Entidades asegguradoras - Balance: Pasivo yy patrimonio neto ((I)) - Pasivo - Otras deudas - Otras deudas con
22 283 17 N entidades del grupo y asociadas [179]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Otras deudas - Resto de otras deudas
23 300 17 N [180]
24 317 17 N Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Derivados de cobertura [181]
25 334 17 N Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Provisiones técnicas [182]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Provisión para primas no consumidas
26 351 17 N [183]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Provisión para riesgos en curso [184]
27 368 17 N
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Provision de seguros de vida [185]
28 385 17 N
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Provision de seguros de vida - Provisión
29 402 17 N para primas no consumidas [186]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Provision de seguros de vida - Provisión
3300 441199 1177 NN ppaarraa rriieessggooss eenn ccuurrssoo [[118877]]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Provision de seguros de vida - Provisión
31 436 17 N matemática [188]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Provision de seguros de vida - Provisión
32 453 17 N seguros de vida cuando riesgo de inversión lo asuma el tomador [189]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Provisión para prestaciones [190]
33 470 17 N
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Provisión para participación en beneficios
34 487 17 N y para extornos [191]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Otras provisiones técnicas [192]
35 504 17 N
36 521 17 N Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Provisiones no técnicas [193]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Provisiones para impuestos y otras
37 538 17 N contingencias legales [194]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Provisión para pensiones y obligaciones
3388 555555 1177 NN siimiilliiares [[119955]]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Provisión para pagos por convenios de
39 572 17 N liquidación [196]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Otras provisiones no técnicas [197]
40 589 17 N
41 606 17 N Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Pasivos fiscales [198]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Pasivos por impuesto corriente [199]
42 623 17 N
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Pasivos por impuesto diferido [200]
43 640 17 N
44 657 17 N Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Resto de pasivos [201]
45 674 17 N Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Periodificaciones [202]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Pasivos por asimetrías contables [203]
46 691 17 N
EEnnttiiddaaddeess aasseegguurraaddoorraass -- BBaallaannccee:: PPaassiivvoo yy ppaattrriimmoonniioo nneettoo ((II)) -- PPaassiivvoo -- CCoommiissiioonneess yy oottrrooss ccoosstteess ddee
47 708 17 N adquisición del reaseguro cedido [204]
48 725 17 N Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Otros pasivos [205]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - Pasivos vinculados con activos
49 742 17 N mantenidos para la venta [206]
50 759 17 N Entidades aseguradoras - Balance: Pasivo y patrimonio neto (I) - Pasivo - TOTAL PASIVO [207]
51 776 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200340>"
Total: 785
Página 63

# Pag. 64

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "350"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
6 11 17 N Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Fondos propios [208]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Capital o fondo mutual [209]
77 2288 1177 NN
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Capital o fondo mutual - Capital
8 45 17 N escriturado o fondo mutual [210]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Capital o fondo mutual - (Capital
9 62 17 N no exigido) [211]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Prima de emisión o asunción
10 79 17 N [212]
11 96 17 N Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas [213]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas - Reserva
12 113 17 N de revalorización [382]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas - Legal y estatutarias
13 130 17 N [214]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas - Reserva de
14 147 17 N estabilización [215]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Reservas - Otras reservas [216]
15 164 17 N
EEnttiiddaddes aseguraddoras - BBallance: PPasiivo y pattriimoniio netto ((IIII)) - PPattriimoniio netto - ((AAcciiones propiias)) [[221177]]
16 181 17 N
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Resultados de ejercicios
17 198 17 N anteriores [218]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Resultados de ejercicios
18 215 17 N anteriores - Remanente [219]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Resultados de ejercicios
19 232 17 N anteriores - (Resultados negativos de ejercicios anteriores) [220]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Otras aportaciones de socios y
20 249 17 N mutualistas [221]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Resultado del ejercicio [222]
21 266 17 N
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - (Dividendo a cuenta y reserva de
22 283 17 N estabilización a cuenta) [223]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Otros instrumentos de
2233 330000 1177 NN ppaattrimoonioo neettoo [[224]]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Ajustes por cambios de valor
24 317 17 N [225]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Activos financieros disponibles
25 334 17 N para la venta [226]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Operaciones de cobertura [227]
26 351 17 N
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Diferencias de cambio y
27 368 17 N conversión [228]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Corrección de asimetrías
28 385 17 N contables [229]
29 402 17 N Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Otros ajustes [230]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - Subvenciones, donaciones y
30 419 17 N legados recibidos [231]
Entidades aseguradoras - Balance: Pasivo y patrimonio neto (II) - Patrimonio neto - TOTAL PATRIMONIO NETO
31 436 17 N [232]
EEnnttiiddaaddeess aasseegguurraaddoorraass - BBaallaannccee:: PPaassiivvoo yy ppaattrriimmoonniioo nneettoo ((IIII)) - PPaattrriimmoonniioo nneettoo - TTOOTTAALL PPAASSIIVVOO YY
32 453 17 N PATRIMONIO NETO [233]
33 470 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200350>"
Total: 479
Página 64

# Pag. 65

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "360"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
EEnnttiiddaaddeess aasseegguurraaddoorraass - PPéérrddiiddaass yy ggaannaanncciiaass ((II)) - CCuueennttaa ttééccnniiccaa sseegguurroo nnoo vviiddaa - PPrriimmaass iimmppuuttaaddaass aall eejjeerrcciicciioo
6 11 17 N [234]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas devengadas [235]
7 28 17 N
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas devengadas - Seguro
8 45 17 N directo [236]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas devengadas -
9 62 17 N Reaseguro aceptado [237]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas devengadas -
10 79 17 N Variación de la corrección por deterioro de las primas pendientes de cobro (+ ó -) [238]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Primas reaseguro cedido (-)
11 96 17 N [239]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión primas no
1122 111133 1177 NN ccoonnssuummiiddaass yy ppaarraa rriieessggooss eenn ccuurrssoo ((++ óó -)) [[224400]]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión primas no
13 130 17 N consumidas y para riesgos en curso (+ ó -) - Seguro directo [241]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión primas no
14 147 17 N consumidas y para riesgos en curso (+ ó -) - Reaseguro aceptado [242]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión primas no
15 164 17 N consumidas, reaseguro cedido (+ ó -) [243]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Ingresos inmovilizado
16 181 17 N material y de las inversiones [244]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Ingresos inversiones
17 198 17 N inmobiliarias [245]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Ingresos inversiones
18 215 17 N financieras [246]
Enttiddaaddeess aasseegguuraaddooraass - Péérddiddaass yy ggaanaancciaass ((I)) - CCuueenttaa ttééccniccaa sseegguuroo noo viddaa - Applicc. ccoorreecccciooneess ddee vaaloor
19 232 17 N por deterioro del inmovilizado material y de las inversiones [247]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Aplic. correc. valor por
20 249 17 N deterioro inmovilizado material y de inversiones - Inmovilizado material e inv.inmobiliarias [248]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Aplic. correc. valor por
21 266 17 N deterioro inmovilizado material y de inversiones - Inversiones financieras [249]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Beneficios inmovilizado
22 283 17 N material y de inversiones [250]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Beneficios inmovilizado
23 300 17 N material y de inversiones - Inmovilizado material e inversiones inmobiliarias [251]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Beneficios inmovilizado
24 317 17 N material y de inversiones - Inversiones financieras [252]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Otros ingresos técnicos [253]
25 334 17 N
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Siniestralidad del ejercicio,
26 351 17 N neta de reaseguro [254]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Prestaciones y gastos
27 368 17 N pagados [255]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Prestaciones y gastos
28 385 17 N pagados - Seguro directo [256]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Prestaciones y gastos
29 402 17 N pagados - Reaseguro aceptado [257]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Prestaciones y gastos
30 419 17 N pagados - Reaseguro cedido (-) [258]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión para
31 436 17 N prestaciones (+ ó -) [259]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión para
3322 445533 1177 NN presttaciiones ((+ óó -)) - SSeguro ddiirectto [[226600]]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión para
33 470 17 N prestaciones (+ ó -) - Reaseguro aceptado [261]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación provisión para
34 487 17 N prestaciones (+ ó -) - Reaseguro cedido (-) [262]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos imputables
35 504 17 N prestaciones [263]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación otras provisiones
36 521 17 N técnicas, netas de reaseguro (+ ó -) [264]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Participación en beneficios y
37 538 17 N extornos [265]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Prestaciones y gastos por
38 555 17 N participación en beneficios y extornos [266]
EEnnttiiddaaddeess aasseegguurraaddoorraass - PPéérrddiiddaass yy ggaannaanncciiaass ((II)) - CCuueennttaa ttééccnniiccaa sseegguurroo nnoo vviiddaa - VVaarriiaacciióónn pprroovviissiióónn
39 572 17 N participación en beneficios y extornos (+ ó -) [267]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos explotación netos
40 589 17 N [268]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos adquisición [269]
41 606 17 N
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos administración [270]
42 623 17 N
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Comisiones y participaciones
43 640 17 N en el reaseguro cedido y retrocedido [271]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Otros gastos técnicos (+ ó -)
44 657 17 N [272]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación deterioro por
4455 667744 1177 NN iinsollvenciias ((+ óó -)) [[227733]]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación deterioro del
46 691 17 N inmovilizado (+ ó -) [274]
Página 65

# Pag. 66

Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Variación prestaciones por
47 708 17 N convenios de liquidación de siniestros (+ ó -) [275]
48 725 17 N Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Otros [276]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos inmovilizado material
49 742 17 N e inversiones [277]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos gestión inversiones
50 759 17 N [278]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos gestión inversiones -
51 776 17 N Gastos inmovilizado material e inv.inmobiliarias [279]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Gastos gestión inversiones -
52 793 17 N Gastos inversiones y cuentas financieras [280]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Correciones valor
53 810 17 N inmovilizado material e inversiones [281]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Correciones valor
inmovilizado material e inversiones - Amortización inmovilizado material e inversiones inmobiliarias [282]
54 827 17 N
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Correciones valor
55 844 17 N inmovilizado material e inversiones - Deterioro inmovilizado material e inversiones inmobiliarias [283]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Correciones valor
56 861 17 N inmovilizado material e inversiones - Deterioro inversiones financieras [284]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Pérdidas del inmovilizado
57 878 17 N material e inversiones [285]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Pérdidas del inmovilizado
58 895 17 N material e inversiones - Inmovilizado material e inversiones inmobiliarias [286]
Entidades aseguradoras - Pérdidas y ganancias (I) - Cuenta técnica seguro no vida - Pérdidas del inmovilizado
59 912 17 N material e inversiones -Inversiones financieras [287]
EEnnttiiddaaddeess aasseegguurraaddoorraass - PPéérrddiiddaass yy ggaannaanncciiaass ((II)) - CCuueennttaa ttééccnniiccaa sseegguurroo nnoo vviiddaa - SSuubbttoottaall ((RReessuullttaaddoo ddee llaa
60 929 17 N cuenta técnica del seguro no vida) [288]
61 946 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200360>"
Total: 955
Página 66

# Pag. 67

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "370"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
EEnnttiiddaaddeess aasseegguurraaddoorraass - PPéérrddiiddaass yy ggaannaanncciiaass ((IIII)) - CCuueennttaa ttééccnniiccaa sseegguurroo ddee vviiddaa - PPrriimmaass iimmppuuttaaddaass aall eejjeerrcciicciioo,,
6 11 17 N netas de reaseguro [289]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas devengadas [290]
7 28 17 N
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas devengadas - Seguro
8 45 17 N directo [291]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas devengadas -
9 62 17 N Reaseguro aceptado [292]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas devengadas - Variación
10 79 17 N corrección por deterioro de las primas pendientes de cobro (+ ó -) [293]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Primas reaseguro cedido (-)
11 96 17 N [294]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión para primas
12 113 17 N no consumidas y riesgos en curso (+ ó -) [295]
EEnttiiddaddes aseguraddoras - PPéérddiiddas y gananciias ((IIII)) - CCuentta ttéécniica seguro dde viidda - VVariiaciióón proviisiióón para priimas
13 130 17 N no consumidas y riesgos en curso (+ ó -) -Seguro directo [296]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión para primas
14 147 17 N no consumidas y riesgos en curso (+ ó -) - Reaseguro aceptado [297]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión primas no
15 164 17 N consumidas, reaseguro cedido (+ ó -) [298]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Ingresos inmovilizado material
16 181 17 N e inversiones [299]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Ingresos inversiones
17 198 17 N inmobiliarias [300]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Ingresos inversiones
18 215 17 N financieras [301]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Aplic. correc. de valor por
1199 223322 1177 NN ddeetteerriioorroo iinnmmoovv.. mmaatteerriiaall ee iinnvveerrssiioonneess [[330022]]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Aplic. correc. de valor por
20 249 17 N deterioro inmov. material e inversiones - Inmovilizado material e inv. inmobiliarias [303]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Aplic. correc. de valor por
21 266 17 N deterioro inmov. material e inversiones - Inversiones financieras [304]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Beneficios realización
22 283 17 N inmovilizado material e inversiones [305]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Beneficios realización
23 300 17 N inmovilizado material e inversiones - Inmovilizado material e inv. inmobiliarias [306]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Beneficios realización
24 317 17 N inmovilizado material e inversiones - Inversiones financieras [307]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Inversiones afectas a seguros
25 334 17 N el tomador asume riesgo de inversión [308]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Otros ingresos ténicos [309]
2266 335511 1177 NN
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Siniestralidad del ejercicio, neta
27 368 17 N de reaseguro [310]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Prestaciones y gastos pagados
28 385 17 N [311]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Prestaciones y gastos pagados
29 402 17 N - Seguro directo [312]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Prestaciones y gastos pagados
30 419 17 N - Reaseguro aceptado [313]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Prestaciones y gastos pagados
31 436 17 N - Reaseguro cedido (-) [314]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión
32 453 17 N prestaciones (+ ó -) [315]
EEnnttiiddaaddeess aasseegguurraaddoorraass - PPéérrddiiddaass yy ggaannaanncciiaass ((IIII)) - CCuueennttaa ttééccnniiccaa sseegguurroo ddee vviiddaa - VVaarriiaacciióónn pprroovviissiióónn
33 470 17 N prestaciones (+ ó -) - Seguro directo [316]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión
34 487 17 N prestaciones (+ ó -) - Reaseguro aceptado [317]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión
35 504 17 N prestaciones (+ ó -) - Reaseguro cedido [318]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Gastos imputables
36 521 17 N prestaciones [319]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación otras provisiones
37 538 17 N técnicas [320]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Provisiones seguros de vida
38 555 17 N [321]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Provisiones seguros de vida -
39 572 17 N Seguro directo [322]
EEnttiiddaddes aseguraddoras - PPéérddiiddas y gananciias ((IIII)) - CCuentta ttéécniica seguro dde viidda - PProviisiiones seguros dde viidda -
40 589 17 N Reaseguro aceptado [323]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Provisiones seguros de vida -
41 606 17 N Reaseguro cedido (-) [324]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Provisiones seguros de vida
42 623 17 N riesgo asumen tomadores [325]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Otras provisiones técnicas
43 640 17 N [326]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Participación beneficios y
44 657 17 N extornos [327]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Prestaciones y gastos
45 674 17 N participación beneficios y extornos [328]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Variación provisión
4466 669911 1177 NN ppaarrttiicciippaacciióónn bbeenneeffiicciiooss yy eexxttoorrnnooss ((++ oo -)) [[332299]]
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Gastos explotación netos [330]
47 708 17 N
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Gastos adquisición [331]
48 725 17 N
Página 67

# Pag. 68

Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Gastos administración [332]
49 742 17 N
Entidades aseguradoras - Pérdidas y ganancias (II) - Cuenta técnica seguro de vida - Comisiones y participaciones
50 759 17 N reaseguro cedido y retrocedido [333]
51 776 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200370>"
Total: 785
Página 68

# Pag. 69

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "380"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
EEnnttiiddaaddeess aasseegguurraaddoorraass - PPéérrddiiddaass yy ggaannaanncciiaass ((IIIIII)) - CCuueennttaa ttééccnniiccaa sseegguurroo ddee vviiddaa - OOttrrooss ggaassttooss ttééccnniiccooss ((++ óó -
6 11 17 N ) [334]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Variación deterioro por
7 28 17 N insolvencias (+ ó -) [335]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Variación deterioro del
8 45 17 N inmovilizado (+ ó -) [336]
9 62 17 N Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Otros [337]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Gastos del inmovilizado
10 79 17 N material y de las inversiones [338]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Gastos de gestión del
11 96 17 N inmovilizado material y de las inversiones [339]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Gastos gestión inmovilizado
material e inversiones - Gastos del inmovilizado material y de las inversiones inmobiliarias [340]
1122 111133 1177 NN
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Gastos gestión inmovilizado
13 130 17 N material e inversiones - Gastos de inversiones y cuentas financieras [341]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Correcciones valor
14 147 17 N inmovilizado material e inversiones [342]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Correcciones valor
inmovilizado material e inversiones - Amortización del inmovilizado material y de las inversiones inmobiliarias
15 164 17 N [343]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Correcciones valor
inmovilizado material e inversiones -Deterioro del inmovilizado material y de las inversiones inmobiliarias [344]
16 181 17 N
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Correcciones valor
17 198 17 N inmovilizado material e inversiones - Deterioro de inversiones financieras [345]
EEnnttiiddaaddeess aasseegguurraaddoorraass -- PPéérrddiiddaass yy ggaannaanncciiaass ((IIIIII)) -- CCuueennttaa ttééccnniiccaa sseegguurroo ddee vviiddaa -- PPéérrddiiddaass pprroocceeddeenntteess ddeell
18 215 17 N inmovilizado material y de las inversiones [346]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Pérdidas procedentes del
inmovilizado material y de las inversiones - Del inmovilizado material y de las inversiones inmobiliarias [347]
19 232 17 N
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Pérdidas procedentes del
20 249 17 N inmovilizado material y de las inversiones - De las inversiones financieras [348]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Gastos de inversiones
21 266 17 N afectas a seguros en los que el tomador asume el riesgo de la inversión [349]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta técnica seguro de vida - Subtotal (Resultado de la
22 283 17 N cuenta técnica del seguro de vida) [350]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Ingresos del inmovilizado material y de
23 300 17 N las inversiones [351]
EEnnttiiddaaddeess aasseegguurraaddoorraass - PPéérrddiiddaass yy ggaannaanncciiaass ((IIIIII)) - CCuueennttaa nnoo ttééccnniiccaa - IInnggrreessooss pprroocceeddeenntteess ddee llaass iinnvveerrssiioonneess
24 317 17 N inmobiliarias [352]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Ingresos procedentes de las inversiones
25 334 17 N financieras [353]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Aplicaciones de correcciones de valor
26 351 17 N por deterioro del inmovilizado material y de las inversiones [354]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Aplic. de correc. valor por deterioro
inmovilizado material e inversiones - Del inmovilizado material y de las inversiones inmobiliarias [355]
27 368 17 N
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Aplic. de correc. valor por deterioro
28 385 17 N inmovilizado material e inversiones - De inversiones financieras [356]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Beneficios en realización del
29 402 17 N inmovilizado material y de las inversiones [357]
Entidades asegguradoras - Pérdidas yy gganancias ((III)) - Cuenta no técnica - Beneficios en realización del
inmovilizado material y de las inversiones - Del inmovilizado material y de las inversiones inmobiliarias [358]
30 419 17 N
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Beneficios en realización del
31 436 17 N inmovilizado material y de las inversiones - De inversiones financieras [359]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Gastos del inmovilizado material y de las
32 453 17 N inversiones [360]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Gastos de gestión de las inversiones
33 470 17 N [361]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Gastos de gestión de las inversiones -
34 487 17 N Gastos de inversiones y cuentas financieras [362]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Gastos de gestión de las inversiones -
35 504 17 N Gastos de inversiones materiales [363]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Correcciones de valor del inmovilizado
3366 552211 1177 NN matteriiall y dde llas iinversiiones [[336644]]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Correc. valor inmovilizado material e
37 538 17 N inversiones - Amortización del inmovilizado material y de las inversiones inmobiliarias [365]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Correc. valor inmovilizado material e
38 555 17 N inversiones - Deterioro del inmovilizado material y de las inversiones inmobiliarias [366]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Correc. valor inmovilizado material e
39 572 17 N inversiones - Deterioro de inversiones financieras [367]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Pérdidas procedentes del inmovilizado
40 589 17 N material y de las inversiones [368]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Pérdidas procedentes del inmovilizado
material y de las inversiones - Del inmovilizado material y de las inversiones inmobiliarias [369]
41 606 17 N
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Pérdidas procedentes del inmovilizado
4422 662233 1177 NN mmaatteerriiaall yy ddee llaass iinnvveerrssiioonneess - DDee llaass iinnvveerrssiioonneess ffiinnaanncciieerraass [[337700]]
43 640 17 N Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Otros ingresos [371]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Ingresos por la administración de fondos
44 657 17 N de pensiones [372]
Página 69

# Pag. 70

45 674 17 N Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resto de ingresos [373]
46 691 17 N Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Otros gastos [374]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Gastos por la administración de fondos
47 708 17 N de pensiones [375]
48 725 17 N Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resto de gastos [376]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Subtotal (resultado de la cuenta no
49 742 17 N técnica) [377]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resultado antes de impuestos [378]
50 759 17 N
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Impuesto sobre beneficios [379]
51 776 17 N
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resultado procedente de operaciones
52 793 17 N continuadas [[380]]
Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resultado procedente de operaciones
53 810 17 N interrumpidas neto de impuestos [381]
54 827 17 N Entidades aseguradoras - Pérdidas y ganancias (III) - Cuenta no técnica - Resultado del ejercicio [500]
55 844 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200380>"
Total: 853
Página 70

# Pag. 71

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "390"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
EEnnttiiddaaddeess aasseegguurraaddoorraass - EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo pprrooppiioo ((II)) - IInnggrreessooss yy ggaassttooss rreeccoonnoocciiddooss - RReessuullttaaddoo ddeell
6 11 17 N ejercicio [500]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Otros ingresos y
7 28 17 N gastos reconocidos [383]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Activos financieros
8 45 17 N disponibles para la venta [384]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Ganancias y
9 62 17 N pérdidas por valoración [385]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Importes
10 79 17 N transferidos a la cuenta de pérdidas y ganancias [386]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Otras
11 96 17 N reclasificaciones [387]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Coberturas de los
12 113 17 N flujos de efectivo [388]
EEnttiiddaddes aseguraddoras - EEsttaddo cambbiios pattriimoniio propiio ((II)) - IIngresos y gasttos reconociiddos - GGananciias y
13 130 17 N pérdidas por valoración [389]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Importes
14 147 17 N transferidos a la cuenta de pérdidas y ganancias [390]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Importes
15 164 17 N transferidos al valor inicial de las partidas cubiertas [391]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Otras
16 181 17 N reclasificaciones [392]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Coberturas de
17 198 17 N inversiones netas en negocios en el extranjero [393]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Ganancias y
18 215 17 N pérdidas por valoración [394]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Importes
1199 223322 1177 NN ttrraannssffeerriiddooss aa llaa ccuueennttaa ddee ppéérrddiiddaass yy ggaannaanncciiaass [[339955]]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Otras
20 249 17 N reclasificaciones [396]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Diferencias de
21 266 17 N cambio y conversión [397]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Ganancias y
22 283 17 N pérdidas por valoración [398]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Importes
23 300 17 N transferidos a la cuenta de pérdidas y ganancias [399]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Otras
24 317 17 N reclasificaciones [400]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Corrección de
25 334 17 N asimetrías contables [401]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Ganancias y
2266 335511 1177 NN ppéérrddiiddaass ppoorr vvaalloorraacciióónn [[440022]]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Importes
27 368 17 N transferidos a la cuenta de pérdidas y ganancias [403]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Otras
28 385 17 N reclasificaciones [404]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Activos
29 402 17 N mantenidos para la venta [405]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Ganancias y
30 419 17 N pérdidas por valoración [406]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Importes
31 436 17 N transferidos a la cuenta de pérdidas y ganancias [407]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Otras
32 453 17 N reclasificaciones [408]
EEnnttiiddaaddeess aasseegguurraaddoorraass - EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo pprrooppiioo ((II)) - IInnggrreessooss yy ggaassttooss rreeccoonnoocciiddooss - GGaannaanncciiaass //
33 470 17 N (pérdidas) actuariales por retribuciones a largo plazo del personal [409]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Otros ingresos y
34 487 17 N gastos reconocidos [410]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Impuesto sobre
35 504 17 N beneficios [411]
Entidades aseguradoras - Estado cambios patrimonio propio (I) - Ingresos y gastos reconocidos - Total de ingresos y
36 521 17 N gastos reconocidos [412]
37 538 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200390>"
Total: 547
Página 71

# Pag. 72

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "400"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - Capital o fondo
6 11 17 N mutual escriturado [413]
Entidades asegguradoras - Estado cambios ppatrimonio pproppio ((II)) - Saldo,, final ejjercicio anterior - Cappital o fondo
7 28 17 N mutual (No exigido) [414]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - Prima emisión
8 45 17 N [415]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - Reservas [416]
9 62 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - (Acciones en
10 79 17 N patrimonio propias) [417]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior - Resultados de
11 96 17 N ejercicios anteriores [418]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final ejercicio anterior -Otras aportaciones
12 113 17 N de socios o mutualistas [419]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios
13 130 17 N anteriores - Capital o fondo mutual escriturado [426]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios
14 147 17 N anteriores - Capital o fondo mutual (No exigido) [427]
EEnnttiiddaaddeess aasseegguurraaddoorraass -- EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo pprrooppiioo ((IIII)) -- AAjjuusstteess ppoorr ccaammbbiiooss ddee ccrriitteerriioo ddee eejjeerrcciicciiooss
15 164 17 N anteriores - Prima emisión [428]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios
16 181 17 N anteriores - Reservas [429]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios
17 198 17 N anteriores - (Acciones en patrimonio propias) [430]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios
18 215 17 N anteriores - Resultados de ejercicios anteriores [431]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por cambios de criterio de ejercicios
19 232 17 N anteriores - Otras aportaciones de socios o mutualistas [432]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores -
20 249 17 N Capital o fondo mutual escriturado [439]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores -
21 266 17 N Capital o fondo mutual (No exigido) [440]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores -
22 283 17 N Prima emisión [441]
EEnnttiiddaaddeess aasseegguurraaddoorraass - EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo pprrooppiioo ((IIII)) - AAjjuusstteess ppoorr eerrrroorreess ddee eejjeerrcciicciiooss aanntteerriioorreess -
23 300 17 N Reservas [442]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores -
24 317 17 N (Acciones en patrimonio propias) [443]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores -
25 334 17 N Resultados de ejercicios anteriores [444]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Ajustes por errores de ejercicios anteriores -
26 351 17 N Otras aportaciones de socios o mutualistas [445]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Capital o
27 368 17 N fondo mutual escriturado [452]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Capital o
28 385 17 N fondo mutual (No exigido) [453]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Prima
29 402 17 N emisión [454]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Reservas
30 419 17 N [455]
EEnttiiddaddes aseguraddoras - EEsttaddo cambbiios pattriimoniio propiio ((IIII)) - SSallddo ajjusttaddo, iiniiciio ddell ejjerciiciio - ((AAcciiones en
31 436 17 N patrimonio propias) [456]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Resultados
32 453 17 N de ejercicios anteriores [457]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo ajustado, inicio del ejercicio - Otras
33 470 17 N aportaciones de socios o mutualistas [458]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Capital o
34 487 17 N fondo mutual escriturado [465]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Capital o
35 504 17 N fondo mutual (No exigido) [466]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Prima
36 521 17 N emisión [467]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Reservas
37 538 17 N [468]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - (Acciones
38 555 17 N en patrimonio propias)) [469]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos -
39 572 17 N Resultados de ejercicios anteriores [470]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Total ingresos y gastos reconocidos - Otras
40 589 17 N aportaciones de socios o mutualistas [471]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Capital o
41 606 17 N fondo mutual escriturado [478]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Capital o
42 623 17 N fondo mutual (No exigido) [479]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Prima
43 640 17 N emisión [480]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
44 657 17 N Reservas [481]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
45 674 17 N (Acciones en patrimonio propias) [482]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
4466 669911 1177 NN RReessuullttaaddooss ddee eejjeerrcciicciiooss aanntteerriioorreess [[448833]]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas - Otras
47 708 17 N aportaciones de socios o mutualistas [484]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
48 725 17 N Aumentos del capital o fondo mutual - Capital o fondo mutual escriturado [491]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
49 742 17 N Aumentos del capital o fondo mutual - Capital o fondo mutual (No exigido) [492]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
50 759 17 N Aumentos del capital o fondo mutual - Prima emisión [493]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
51 776 17 N Aumentos del capital o fondo mutual - Reservas [494]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
52 793 17 N Aumentos del capital o fondo mutual - (Acciones en patrimonio propias) [495]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
53 810 17 N Aumentos del capital o fondo mutual - Resultados de ejercicios anteriores [496]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
5544 882277 1177 NN AAuummeennttooss ddeell ccaappiittaall oo ffoonnddoo mmuuttuuaall -- OOttrraass aappoorrttaacciioonneess ddee ssoocciiooss oo mmuuttuuaalliissttaass [[449977]]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
55 844 17 N Reducciones del capital o fondo mutual - Escriturado [504]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
56 861 17 N Reducciones del capital o fondo mutual. (No exigido) [505]
Página 72

# Pag. 73

Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
57 878 17 N Reducciones del capital o fondo mutual. Prima emisión [506]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
58 895 17 N Reducciones del capital o fondo mutual. Reservas [507]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
59 912 17 N Reducciones del capital o fondo mutual. (Acciones en patrimonio propias) [508]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
60 929 17 N Reducciones del capital o fondo mutual. Resultados de ejercicios anteriores [509]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
61 946 17 N Reducciones del capital o fondo mutual. Otras aportaciones de socios o mutualistas [510]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
62 963 17 N Conversión de pasivos financ. en patr. neto. Escriturado [517]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
63 980 17 N Conversión de pasivos financ. en patr. neto. (No exigido) [518]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
6644 999977 1177 NN CCoonnvveerrssiióónn ddee ppaassiivvooss ffiinnaanncc.. eenn ppaattrr.. nneettoo.. PPrriimmaa eemmiissiióónn [[551199]]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
65 1014 17 N Conversión de pasivos financ. en patr. neto. Reservas [520]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
66 1031 17 N Conversión de pasivos financ. en patr. neto. (Acciones en patrimonio propias) [521]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
67 1048 17 N Conversión de pasivos financ. en patr. neto. Resultados de ejercicios anteriores [522]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
Conversión de pasivos financ. en patr. neto. Otras aportaciones de socios o mutualistas [523]
68 1065 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
69 1082 17 N Distribución de dividendos o derramas activas. Escriturado [530]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
70 1099 17 N Distribución de dividendos o derramas activas. (No exigido) [531]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
71 1116 17 N Distribución de dividendos o derramas activas. Prima emisión [532]
EEnnttiiddaaddeess aasseegguurraaddoorraass -- EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo pprrooppiioo ((IIII)) -- OOppeerraacciioonneess ccoonn ssoocciiooss oo mmuuttuuaalliissttaass --
72 1133 17 N Distribución de dividendos o derramas activas. Reservas [533]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
73 1150 17 N Distribución de dividendos o derramas activas. (Acciones en patrimonio propias) [534]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
74 1167 17 N Distribución de dividendos o derramas activas. Resultados de ejercicios anteriores [535]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
Distribución de dividendos o derramas activas. Otras aportaciones de socios o mutualistas [536]
75 1184 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
76 1201 17 N Operaciones con acciones o participaciones propias (netas). Escriturado [543]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
77 1218 17 N Operaciones con acciones o participaciones propias (netas). (No exigido) [544]
Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas -
78 1235 17 N Operaciones con acciones o participaciones propias (netas). Prima emisión [545]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
7799 11225522 1177 NN OOppeerraacciioonneess ccoonn aacccciioonneess oo ppaarrttiicciippaacciioonneess pprrooppiiaass ((nneettaass)). RReesseerrvvaass [[554466]]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
Operaciones con acciones o participaciones propias (netas). (Acciones en patrimonio propias) [547]
80 1269 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
Operaciones con acciones o participaciones propias (netas). Resultados de ejercicios anteriores [548]
81 1286 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Operaciones con socios o mutualistas -
Operaciones con acciones o participaciones propias (netas). Otras aportaciones de socios o mutualistas [549]
82 1303 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas -
Incremento (reducción) de patr. neto resultante de una combinación de negocios. Escriturado [556]
83 1320 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas -
Incremento (reducción) de patr. neto resultante de una combinación de negocios. (No exigido) [557]
84 1337 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas -
Incremento (reducción) de patr. neto resultante de una combinación de negocios. Prima emisión [558]
85 1354 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas -
Incremento (reducción) de patr. neto resultante de una combinación de negocios. Reservas [559]
86 1371 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas -
Incremento (reducción) de patr. neto resultante de una combinación de negocios. (Acciones en patrimonio propias)
87 1388 17 N [560]
Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas -
Incremento (reducción) de patr. neto resultante de una combinación de negocios. Resultados de ejercicios
88 1405 17 N anteriores [561]
Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas -
Incremento (reducción) de patr. neto resultante de una combinación de negocios. Otras aportaciones de socios o
89 1422 17 N mutualistas [562]
EEnnttiiddaaddeess aasseegguurraaddoorraass - EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo pprrooppiioo ((IIII)) -OOppeerraacciioonneess ccoonn ssoocciiooss oo mmuuttuuaalliissttaass - OOttrraass
90 1439 17 N operaciones con socios o mutualistas. Escriturado [569]
Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras
91 1456 17 N operaciones con socios o mutualistas. (No exigido) [570]
Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras
92 1473 17 N operaciones con socios o mutualistas. Prima emisión [571]
Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras
93 1490 17 N operaciones con socios o mutualistas. Reservas [572]
Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras
94 1507 17 N operaciones con socios o mutualistas. (Acciones en patrimonio propias) [573]
Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras
95 1524 17 N operaciones con socios o mutualistas. Resultados de ejercicios anteriores [574]
Entidades aseguradoras - Estado cambios patrimonio propio (II) -Operaciones con socios o mutualistas - Otras
operaciones con socios o mutualistas. Otras aportaciones de socios o mutualistas [575]
96 1541 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto -
9977 11555588 1177 NN EEssccrriittuurraaddoo [[558822]]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - (No
98 1575 17 N exigido) [583]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Prima
99 1592 17 N emisión [584]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Reservas
100 1609 17 N [585]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto -
101 1626 17 N (Acciones en patrimonio propias) [586]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto -
102 1643 17 N Resultados de ejercicios anteriores [587]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras
103 1660 17 N aportaciones de socios o mutualistas [588]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos
104 1677 17 N basados en instrumentos de patrimonio - Escriturado [595]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos
110055 11669944 1177 NN bbaassaaddooss eenn iinnssttrruummeennttooss ddee ppaattrriimmoonniioo - ((NNoo eexxiiggiiddoo)) [[559966]]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos
106 1711 17 N basados en instrumentos de patrimonio - Prima emisión [597]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos
107 1728 17 N basados en instrumentos de patrimonio - Reservas [598]
Página 73

# Pag. 74

Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos
108 1745 17 N basados en instrumentos de patrimonio - (Acciones en patrimonio propias) [599]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos
109 1762 17 N basados en instrumentos de patrimonio - Resultados de ejercicios anteriores [600]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Pagos
110 1779 17 N basados en instrumentos de patrimonio - Otras aportaciones de socios o mutualistas [601]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto -
111 1796 17 N Traspasos entre partidas de patrimonio neto - Escriturado [608]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto -
112 1813 17 N Traspasos entre partidas de patrimonio neto - (No exigido) [609]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto -
113 1830 17 N Traspasos entre partidas de patrimonio neto - Prima emisión [610]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto -
114 1847 17 N Traspasos entre partidas de patrimonio neto - Reservas [611]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto -
111155 11886644 1177 NN TTrraassppaassooss eennttrree ppaarrttiiddaass ddee ppaattrriimmoonniioo nneettoo - ((AAcccciioonneess eenn ppaattrriimmoonniioo pprrooppiiaass)) [[661122]]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto -
116 1881 17 N Traspasos entre partidas de patrimonio neto - Resultados de ejercicios anteriores [613]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto -
117 1898 17 N Traspasos entre partidas de patrimonio neto - Otras aportaciones de socios o mutualistas [614]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras
118 1915 17 N variaciones - Escriturado [621]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras
119 1932 17 N variaciones - (No exigido) [622]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras
120 1949 17 N variaciones - Prima emisión [623]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras
121 1966 17 N variaciones - Reservas [624]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras
122 1983 17 N variaciones - (Acciones en patrimonio propias) [625]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras
112233 22000000 1177 NN vvaarriiaacciioonneess -- RReessuullttaaddooss ddee eejjeerrcciicciiooss aanntteerriioorreess [[662266]]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Otras variaciones del patrimonio neto - Otras
124 2017 17 N variaciones - Otras aportaciones de socios o mutualistas [627]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - Escriturado [634]
125 2034 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - (No exigido) [635]
126 2051 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - Prima emisión [636]
127 2068 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - Reservas [637]
128 2085 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - (Acciones en
129 2102 17 N patrimonio propias) [638]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - Resultados de
130 2119 17 N ejercicios anteriores [639]
Entidades aseguradoras - Estado cambios patrimonio propio (II) - Saldo, final del ejercicio - Otras aportaciones de
113311 22113366 1177 NN ssoocciiooss oo mmuuttuuaalliissttaass [[664400]]
132 2153 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200400>"
Total: 2162
Página 74

# Pag. 75

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "410"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - Resultado del
66 1111 1177 NN eejjeerrcciicciioo [[442200]]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - (Dividendo a cuenta)
7 28 17 N [421]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - Otros instrumentos
8 45 17 N de patrimonio [422]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - Ajustes por cambios
9 62 17 N de valor [423]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - Subvenciones
10 79 17 N donaciones y legados recibidos [424]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio anterior - Total [425]
11 96 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios
12 113 17 N anteriores - Resultado del ejercicio [433]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios
1133 113300 1177 NN aanntteerriioorreess - ((DDiivviiddeennddoo aa ccuueennttaa)) [[443344]]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios
14 147 17 N anteriores - Otros instrumentos de patrimonio [435]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios
15 164 17 N anteriores - Ajustes por cambios de valor [436]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios
16 181 17 N anteriores - Subvenciones donaciones y legados recibidos [437]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por cambios de criterio de ejercicios
17 198 17 N anteriores - Total [438]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores -
18 215 17 N Resultado del ejercicio [446]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores -
19 232 17 N (Dividendo a cuenta) [447]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores - Otros
2200 224499 1177 NN iinnssttrruummeennttooss ddee ppaattrriimmoonniioo [[444488]]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores -
21 266 17 N Ajustes por cambios de valor [449]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores -
22 283 17 N Subvenciones donaciones y legados recibidos [450]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Ajustes por errores de ejercicios anteriores - Total
23 300 17 N [451]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - Resultado del
24 317 17 N ejercicio [459]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - (Dividendo a
25 334 17 N cuenta) [460]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - Otros
26 351 17 N instrumentos de patrimonio [461]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - Ajustes por
2277 336688 1177 NN ccaammbbiiooss ddee vvaalloorr [[446622]]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - Subvenciones
28 385 17 N donaciones y legados recibidos [463]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo ajustado, inicio del ejercicio - Total [464]
29 402 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - Resultado
30 419 17 N del ejercicio [472]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - (Dividendo a
31 436 17 N cuenta) [473]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - Otros
32 453 17 N instrumentos de patrimonio [474]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - Ajustes por
33 470 17 N cambios de valor [475]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos -
3344 448877 1177 NN SSuubbvveenncciioonneess ddoonnaacciioonneess yy lleeggaaddooss rreecciibbiiddooss [[447766]]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Total ingresos y gastos reconocidos - Total [477]
35 504 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Resultado
36 521 17 N del ejercicio [485]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (Dividendo
37 538 17 N a cuenta) [486]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otros
38 555 17 N instrumentos de patrimonio [487]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Ajustes
39 572 17 N por cambios de valor [488]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
40 589 17 N Subvenciones donaciones y legados recibidos [489]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Total [490]
4411 660066 1177 NN
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos
42 623 17 N de capital o fondo mutual - Resultado del ejercicio [498]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos
43 640 17 N de capital o fondo mutual - (Dividendo a cuenta) [499]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos
44 657 17 N de capital o fondo mutual - Otros instrumentos de patrimonio [382]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos
45 674 17 N de capital o fondo mutual - Ajustes por cambios de valor [501]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos
46 691 17 N de capital o fondo mutual - Subvenciones donaciones y legados recibidos [502]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Aumentos
47 708 17 N de capital o fondo mutual - Total [503]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-)
4488 772255 1177 NN RReedduucccciioonneess ddeell ccaappiittaall oo ffoonnddoo mmuuttuuaall -- RReessuullttaaddoo ddeell eejjeerrcciicciioo [[551111]]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-)
49 742 17 N Reducciones del capital o fondo mutual - (Dividendo a cuenta) [512]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-)
50 759 17 N Reducciones del capital o fondo mutual - Otros instrumentos de patrimonio [513]
Página 75

# Pag. 76

Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-)
51 776 17 N Reducciones del capital o fondo mutual - Ajustes por cambios de valor [514]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-)
52 793 17 N Reducciones del capital o fondo mutual - Subvenciones donaciones y legados [515]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-)
53 810 17 N Reducciones del capital o fondo mutual - Total [516]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
54 827 17 N Conversión de pasivos financ. en patr. neto - Resultado del ejercicio [524]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
55 844 17 N Conversión de pasivos financ. en patr. neto - (Dividendo a cuenta) [525]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
56 861 17 N Conversión de pasivos financ. en patr. neto - Otros instrumentos de patrimonio [526]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
57 878 17 N Conversión de pasivos financ. en patr. neto - Ajustes por cambios de valor [527]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
58 895 17 N Conversión de pasivos financ. en patr. neto - Subvenciones donaciones y legados [528]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
59 912 17 N Conversión de pasivos financ. en patr. neto - Total [529]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-)
60 929 17 N Distribución de dividendos o derramas activas - Resultado del ejercicio [537]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-)
61 946 17 N Distribución de dividendos o derramas activas - (Dividendo a cuenta) [538]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-)
62 963 17 N Distribución de dividendos o derramas activas - Otros instrumentos de patrimonio [539]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-)
63 980 17 N Distribución de dividendos o derramas activas - Ajustes por cambios de valor [540]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-)
Distribución de dividendos o derramas activas - Subvenciones donaciones y legados [541]
64 997 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - (-)
65 1014 17 N Distribución de dividendos o derramas activas - Total [542]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
Operaciones con acciones o participaciones propias (netas) - Resultado del ejercicio [550]
66 1031 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
67 1048 17 N Operaciones con acciones o participaciones propias (netas) - (Dividendo a cuenta) [551]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
Operaciones con acciones o participaciones propias (netas) - Otros instrumentos de patrimonio [552]
68 1065 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
Operaciones con acciones o participaciones propias (netas) - Ajustes por cambios de valor [553]
69 1082 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
Operaciones con acciones o participaciones propias (netas) - Subvenciones donaciones y legados [554]
70 1099 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
71 1116 17 N Operaciones con acciones o participaciones propias (netas) - Total [555]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
Incremento (reducción) de patr. neto resultante de una combinación de negocios - Resultado del ejercicio [563]
72 1133 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
Incremento (reducción) de patr. neto resultante de una combinación de negocios - (Dividendo a cuenta) [564]
73 1150 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
Incremento (reducción) de patr. neto resultante de una combinación de negocios - Otros instrumentos de patrimonio
74 1167 17 N [565]
EEnttiiddaddes aseguraddoras - EEsttaddo cambbiios pattriimoniio propiio ((IIIIII)) - OOperaciiones con sociios o muttualliisttas -
Incremento (reducción) de patr. neto resultante de una combinación de negocios - Ajustes por cambios de valor
75 1184 17 N [566]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
Incremento (reducción) de patr. neto resultante de una combinación de negocios - Subvenciones donaciones y
76 1201 17 N legados [567]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas -
Incremento (reducción) de patr. neto resultante de una combinación de negocios - Total [568]
77 1218 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras
78 1235 17 N operaciones con socios o mutualistas - Resultado del ejercicio [576]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras
79 1252 17 N operaciones con socios o mutualistas - (Dividendo a cuenta) [577]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras
8800 11226699 1177 NN ooppeerraacciioonneess ccoonn ssoocciiooss oo mmuttuaalliissttaass - OOttrrooss iinnssttrrummeennttooss ddee ppaattrriimmoonniioo [[557788]]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras
81 1286 17 N operaciones con socios o mutualistas - Ajustes por cambios de valor [579]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras
82 1303 17 N operaciones con socios o mutualistas - Subvenciones donaciones y legados [580]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Operaciones con socios o mutualistas - Otras
83 1320 17 N operaciones con socios o mutualistas - Total [581]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Resultado
84 1337 17 N del ejercicio [589]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - (Dividendo
85 1354 17 N a cuenta) [590]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otros
86 1371 17 N instrumentos de patrimonio [591]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Ajustes por
8877 11338888 1177 NN ccaammbbiiooss ddee vvaalloorr [[559922]]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto -
88 1405 17 N Subvenciones donaciones y legados [593]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Total [594]
89 1422 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos
90 1439 17 N basados en instrumentos de patrimonio - Resultado del ejercicio [602]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos
91 1456 17 N basados en instrumentos de patrimonio - (Dividendo a cuenta) [603]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos
92 1473 17 N basados en instrumentos de patrimonio - Otros instrumentos de patrimonio [604]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos
93 1490 17 N basados en instrumentos de patrimonio - Ajustes por cambios de valor [605]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos
9944 11550077 1177 NN bbaassaaddooss eenn iinnssttrruummeennttooss ddee ppaattrriimmoonniioo - SSuubbvveenncciioonneess ddoonnaacciioonneess yy lleeggaaddooss [[660066]]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Pagos
95 1524 17 N basados en instrumentos de patrimonio - Total [607]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos
96 1541 17 N entre partidas de patrimonio neto - Resultado del ejercicio [615]
Página 76

# Pag. 77

Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos
97 1558 17 N entre partidas de patrimonio neto - (Dividendo a cuenta) [616]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos
98 1575 17 N entre partidas de patrimonio neto - Otros instrumentos de patrimonio [617]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos
99 1592 17 N entre partidas de patrimonio neto - Ajustes por cambios de valor [618]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos
100 1609 17 N entre partidas de patrimonio neto - Subvenciones donaciones y legados [619]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Traspasos
101 1626 17 N entre partidas de patrimonio neto - Total [620]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras
102 1643 17 N variaciones - Resultado del ejercicio [628]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras
103 1660 17 N variaciones - (Dividendo a cuenta) [629]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras
104 1677 17 N variaciones - Otros instrumentos de patrimonio [630]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras
105 1694 17 N variaciones - Ajustes por cambios de valor [631]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras
106 1711 17 N variaciones - Subvenciones donaciones y legados [632]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Otras variaciones del patrimonio neto - Otras
107 1728 17 N variaciones - Total [633]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - Resultado del ejercicio [641]
108 1745 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - (Dividendo a cuenta) [642]
109 1762 17 N
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - Otros instrumentos de
110 1779 17 N patrimonio [643]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - Ajustes por cambios de valor
111 1796 17 N [644]
Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - Subvenciones donaciones y
112 1813 17 N legados [645]
113 1830 17 N Entidades aseguradoras - Estado cambios patrimonio propio (III) - Saldo, final ejercicio - Total [646]
114 1847 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200410>"
Total: 1856
Página 77

# Pag. 78

Agencia Tributaria
Modelo 200 Diseño de registro
vers. 1.0 Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
rentas constituidas en el extranjero con presencia en territorio español) 2013
NºPosic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "420"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
6 11 17 N Inst. inversión colectiva - Balance: Activo - Activo no corriente [101]
7 28 17 N Inst. inversión colectiva - Balance: Activo - Inmovilizado intangible [102]
8 45 17 N Inst. inversión colectiva - Balance: Activo - Inmovilizado material [103]
99 6622 1177 NN IInnsstt.. iinnvveerrssiióónn ccoolleeccttiivvaa - BBaallaannccee:: AAccttiivvoo - IInnmmoovviilliizzaaddoo mmaatteerriiaall - BBiieenneess mmuueebblleess ddee uussoo pprrooppiioo [[110044]]
10 79 17 N Inst. inversión colectiva - Balance: Activo - Inmovilizado material - Mobiliario y enseres [105]
11 96 17 N Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias [106]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y
12 113 17 N derechos [107]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y
13 130 17 N derechos - Inmuebles en fase de construcción [108]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y
14 147 17 N derechos - Inmuebles terminados [109]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y
15 164 17 N derechos - Concesiones administrativas [110]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y
16 181 17 N derechos - Otros derechos reales [111]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y
17 198 17 N derechos - Compromisos de compra de inmuebles [112]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y
18 215 17 N derechos - Compra de opciones de compra de inmuebles [113]
IInnsstt. iinnvveerrssiióónn ccoolleeccttiivvaa - BBaallaannccee:: AAccttiivvoo - CCaarrtteerraa ddee iinnvveerrssiioonneess iinnmmoobbiilliiaarriiaass - CCaarrtteerraa iinntteerriioorr ddee iinnmmuueebblleess yy
19 232 17 N derechos - Acciones en sociedades tenedoras y entidades de arrendamiento [114]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y
20 249 17 N derechos - Opciones sobre la cartera de inversiones inmobiliarias [115]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera interior de inmuebles y
21 266 17 N derechos - Otros [116]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera exterior de inmuebles y
22 283 17 N derechos [117]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera exterior de inmuebles y
23 300 17 N derechos - Sociedades tenedoras de inmuebles [118]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cartera exterior de inmuebles y
24 317 17 N derechos - Otros [119]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Anticipos o entregas a cuenta
25 334 17 N [120]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cuentas transitorias [121]
26 351 17 N
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cuentas transitorias - Inversiones
2277 336688 1177 NN aaddiicciioonnaalleess, ccoommpplleemmeennttaarriiaass yy rreehhaabbiilliittaacciioonneess eenn ccuurrssoo [[112222]]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones inmobiliarias - Cuentas transitorias -
28 385 17 N Indemnizaciones a arrendatarios [123]
29 402 17 N Inst. inversión colectiva - Balance: Activo - Activos por impuesto diferido [124]
30 419 17 N Inst. inversión colectiva - Balance: Activo - Activo corriente [125]
31 436 17 N Inst. inversión colectiva - Balance: Activo - Deudores [126]
32 453 17 N Inst. inversión colectiva - Balance: Activo - Deudores - Deudores por ventas de inmuebles [127]
33 470 17 N Inst. inversión colectiva - Balance: Activo - Deudores - Deudores por alquileres [128]
34 487 17 N Inst. inversión colectiva - Balance: Activo - Deudores - Deudores dudosos o morosos [129]
Inst. inversión colectiva - Balance: Activo - Deudores - Deudores dudosos o morosos avalados o garantizados [130]
35 504 17 N
36 521 17 N Inst. inversión colectiva - Balance: Activo - Deudores - Otros deudores [131]
37 538 17 N Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras [132]
38 555 17 N Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior [133]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Valores
39 572 17 N representativos de deuda [134]
IInnsstt. iinnvveerrssiióónn ccoolleeccttiivvaa -- BBaallaannccee:: AAccttiivvoo -- CCaarrtteerraa ddee iinnvveerrssiioonneess ffiinnaanncciieerraass -- CCaarrtteerraa iinntteerriioorr -- IInnssttrruummeennttooss ddee
40 589 17 N patrimonio [135]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Instituciones de
41 606 17 N inversión colectiva [136]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Depósitos en
42 623 17 N EECC [137]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Derivados [138]
43 640 17 N
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera interior - Otros [139]
44 657 17 N
45 674 17 N Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior [140]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Valores
46 691 17 N representativos de deuda [141]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Instrumentos de
47 708 17 N patrimonio [142]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Instituciones de
48 725 17 N inversión colectiva [143]
IInnsstt. iinnvveerrssiióónn ccoolleeccttiivvaa - BBaallaannccee:: AAccttiivvoo - CCaarrtteerraa ddee iinnvveerrssiioonneess ffiinnaanncciieerraass - CCaarrtteerraa eexxtteerriioorr - DDeeppóóssiittooss eenn
49 742 17 N EECC [144]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Derivados [145]
50 759 17 N
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Cartera exterior - Otros [146]
51 776 17 N
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Intereses de la cartera de inversión
52 793 17 N [147]
Inst. inversión colectiva - Balance: Activo - Cartera de inversiones financieras - Inversiones morosas, dudosas o en
53 810 17 N litigio [148]
54 827 17 N Inst. inversión colectiva - Balance: Activo - Periodificaciones [149]
55 844 17 N Inst. inversión colectiva - Balance: Activo - Tesorería [150]
56 861 17 N Inst. inversión colectiva - Balance: Activo - TOTAL ACTIVO [151]
57 878 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200420>"
Total: 887
Página 78

# Pag. 79

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "430"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
6 11 17 N Inst. inversión colectiva - Patrimonio y pasivo - Patrimonio atribuido a partícipes o accionistas [152]
Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas [153]
77 2288 1177 NN
Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Capital
8 45 17 N [154]
Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas -
9 62 17 N Partícipes [155]
Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas - Prima
10 79 17 N de emisión [156]
Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas -
11 96 17 N Reservas [157]
Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas -
12 113 17 N Reservas revalorización (Ley16/2012, de 27 de diciembre) [243]
Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas -
13 130 17 N (Acciones propias) [158]
Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas -
14 147 17 N Resultados de ejercicios anteriores [159]
IInnsstt.. iinnvveerrssiióónn ccoolleeccttiivvaa -- PPaattrriimmoonniioo yy ppaassiivvoo -- FFoonnddooss rreeeemmbboollssaabblleess aattrriibbuuiiddooss aa ppaarrttíícciippeess oo aacccciioonniissttaass -- OOttrraass
15 164 17 N aportaciones de socios [160]
Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas -
16 181 17 N Resultado del ejercicio [161]
Inst. inversión colectiva - Patrimonio y pasivo - Fondos reembolsables atribuidos a partícipes o accionistas -
17 198 17 N (Dividendo a cuenta) [162]
Inst. inversión colectiva - Patrimonio y pasivo - Ajustes por cambios de valor en inmovilizado material de uso propio
18 215 17 N [163]
Inst. inversión colectiva - Patrimonio y pasivo - Ajustes por cambios valor en invers. inmob. e inmovil. material [164]
19 232 17 N
Inst. inversión colectiva - Patrimonio y pasivo - Ajustes por cambios valor en invers. inmob. e inmovil. material -
20 249 17 N Ajustes por plusvalías de invers. inmob. e inmovilizado material [165]
Inst. inversión colectiva - Patrimonio y pasivo - Ajustes por cambios valor en invers. inmob. e inmovil. material -
21 266 17 N Ajustes por minusvalías de invers. inmob. e inmovil. material [166]
22 283 17 N Inst. inversión colectiva - Patrimonio y pasivo - Otro patrimonio atribuido [167]
233 3300 17 N Inst. inversión colectiva - Patrimonio yy ppasivo - Pasivo no corriente [[168]]
24 317 17 N Inst. inversión colectiva - Patrimonio y pasivo - Provisiones a largo plazo [169]
25 334 17 N Inst. inversión colectiva - Patrimonio y pasivo - Deudas a largo plazo [170]
26 351 17 N Inst. inversión colectiva - Patrimonio y pasivo - Pasivos por impuesto diferido [171]
27 368 17 N Inst. inversión colectiva - Patrimonio y pasivo - Pasivo corriente [172]
28 385 17 N Inst. inversión colectiva - Patrimonio y pasivo - Provisiones a corto plazo [173]
29 402 17 N Inst. inversión colectiva - Patrimonio y pasivo - Deudas a corto plazo [174]
30 419 17 N Inst. inversión colectiva - Patrimonio y pasivo - Acreedores [175]
31 436 17 N Inst. inversión colectiva - Patrimonio y pasivo - Pasivos financieros [176]
32 453 17 N Inst. inversión colectiva - Patrimonio y pasivo - Derivados [177]
33 470 17 N Inst. inversión colectiva - Patrimonio y pasivo - Periodificaciones [178]
34 487 17 N Inst. inversión colectiva - Patrimonio y pasivo - TOTAL PATRIMONIO Y PASIVO [179]
35 504 17 N Inst. inversión colectiva - Cuentas de orden - Cuentas de compromiso [180]
Inst. inversión colectiva - Cuentas de orden - Cuentas de compromiso - Compromisos por operaciones largas de
36 521 17 N derivados [181]
IInnsstt. iinnvveerrssiióónn ccoolleeccttiivvaa - CCuueennttaass ddee oorrddeenn - CCuueennttaass ddee ccoommpprroommiissoo - CCoommpprroommiissooss ppoorr ooppeerraacciioonneess ccoorrttaass ddee
37 538 17 N derivados [182]
Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso - Compromisos por compra de
38 555 17 N inmuebles [183]
Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso - Compromisos de venta de
39 572 17 N inmuebles [184]
Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso - Contratos de arras [185]
40 589 17 N
Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso - Derechos de compra de
41 606 17 N opciones de compra de inmuebles [186]
Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso - Importes pendientes de
42 623 17 N desembolsar por inmuebles en fase de construcción [187]
Inst. inversión colectiva - Cuentas de orden - Cuentas de riesgo y de compromiso - Otras cuentas de riesgo y
43 640 17 N compromiso [188]
44 657 17 N Inst. inversión colectiva - Cuentas de orden - TOTAL CUENTAS DE RIESGO Y COMPROMISO [189]
4455 667744 1177 NN IInnsstt.. iinnvveerrssiióónn ccoolleeccttiivvaa - CCuueennttaass ddee oorrddeenn - OOttrraass ccuueennttaass ddee oorrddeenn [[119900]]
Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Valores cedidos en préstamo por la IIC [191]
46 691 17 N
Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Valores aportados como garantía por la IIC
47 708 17 N [192]
Inst. inversión colectiva - Cuentas de orden -Otras cuentas de orden - Valores recibidos en garantía por la IIC [193]
48 725 17 N
Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Capital nominal no suscrito ni en circulación
49 742 17 N (SICAV) [194]
Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Capital nominal no suscrito (SII) [195]
50 759 17 N
51 776 17 N Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Avales recibidos [196]
52 793 17 N Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Avales emitidos [197]
Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Indemnizaciones previstas pendientes de
53 810 17 N confirmar [198]
IInnsstt.. iinnvveerrssiióónn ccoolleeccttiivvaa - CCuueennttaass ddee oorrddeenn - OOttrraass ccuueennttaass ddee oorrddeenn - PPéérrddiiddaass ffiissccaalleess aa ccoommppeennssaarr [[119999]]
54 827 17 N
55 844 17 N Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Otros [200]
56 861 17 N Inst. inversión colectiva - Cuentas de orden - Otras cuentas de orden - Otras cuentas de orden [201]
57 878 17 N Inst. inversión colectiva - Cuentas de orden - TOTAL OTRAS CUENTAS DE ORDEN [202]
58 895 17 N Inst. inversión colectiva - Cuentas de orden - TOTAL CUENTAS DE ORDEN [203]
59 912 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200430>"
Total: 921
Página 79

# Pag. 80

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas
vers. 1.0
constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "440"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Comisiones de descuento por suscripciones y /o reembolsos [204]
6 11 17 N
77 2288 1177 NN IInnsstt. iinnvveerrssiióónn ccoolleeccttiivvaa - CCuueennttaa ppéérrddiiddaass yy ggaannaanncciiaass - CCoommiissiioonneess rreettrroocceeddiiddaass [[220055]]
8 45 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - Ingresos por alquiler [206]
9 62 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - Gastos de personal [207]
10 79 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - Otros gastos de explotación [208]
11 96 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - Otros gastos de explotación - Comisión de gestión [209]
12 113 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - Otros gastos de explotación - Comisión depositario [210]
13 130 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - Otros gastos de explotación - Otros [212]
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultados por enajenaciones de inmovilizado [213]
14 147 17 N
15 164 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro de inversiones inmobiliarias [214]
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro de inversiones inmobiliarias - Incrementos de deterioro
16 181 17 N [215]
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro de inversiones inmobiliarias - Reversión del deterioro [216]
17 198 17 N
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultados por enajenaciones y otros de invers. inmob. [217]
1188 22115 117 N
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultados por enajenaciones y otros de invers. inmob. - Resultados
19 232 17 N positivos [218]
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultados por enajenaciones y otros de invers. inmob. - Resultados
20 249 17 N negativos [219]
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Compensaciones e indemnizaciones por deterioro o pérdida de
21 266 17 N invers. inmob. [220]
22 283 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - Amortización invers. inmob. e inmovilizado material [221]
23 300 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - Amortización inmovilizado material [222]
24 317 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - Excesos de provisiones [223]
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultados por enajenaciones inmovilizado material [224]
25 334 17 N
26 351 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultado de explotación [225]
27 368 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - Ingresos financieros [226]
28 385 17 N Inst. inversión colectiva - Cuenta ppérdidas yy gganancias - Gastos financieros [[227]]
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Variación del valor razonable en instrumentos financieros [228]
29 402 17 N
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Variación del valor razonable en instrumentos financieros - Por
30 419 17 N operaciones cartera interior [229]
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Variación del valor razonable en instrumentos financieros - Por
31 436 17 N operaciones cartera exterior [230]
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Variación del valor razonable en instrumentos financieros - Por
32 453 17 N operaciones con derivados [231]
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Variación del valor razonable en instrumentos financieros - Otros
33 470 17 N [232]
34 487 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - Diferencias de cambio [233]
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros [234]
35 504 17 N
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros -
36 521 17 N Deterioros [235]
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros -
37 538 17 N Resultados por operaciones cartera interior [236]
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros -
38 555 17 N Resultados por operaciones cartera exterior [237]
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros -
39 572 17 N Resultados por operaciones con derivados [238]
Inst. inversión colectiva - Cuenta pérdidas y ganancias - Deterioro y resultado enajenaciones de instrumentos financieros -
40 589 17 N Otros [239]
41 606 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultado financiero [240]
42 623 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - Resultado antes de impuesto [241]
43 640 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - Impuesto sobre beneficios [242]
44 657 17 N Inst. inversión colectiva - Cuenta pérdidas y ganancias - RESULTADO DEL EJERCICIO [500]
45 674 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200440>"
Total: 683
Página 80

# Pag. 81

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "450"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
6 11 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Patrimonio inicial [244]
7 28 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Saldo neto [245]
8 45 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Suscripciones/puesta circ. Acciones [246]
9 62 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Suscripciones/Aumentos capital [247]
10 79 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Reembolsos/Recompra acciones [248]
11 96 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Reembolsos/Reducciones capital [249]
12 113 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Beneficios brutos distribuidos [250]
13 130 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Rendimientos netos [251]
14 147 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Rendimientos de gestión [252]
15 164 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Alquileres [253]
16 181 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Intereses [254]
17 198 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Dividendos [255]
18 215 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Inversiones inmobiliarias [256]
Inst. inversión colectiva - Estado variación patrimonial (I) - Inversiones inmobiliarias - Variación valor razonable
19 232 17 N invers. inmob. [257]
Inst. inversión colectiva - Estado variación patrimonial (I) - Inversiones inmobiliarias - Resultados enajenaciones
20 249 17 N invers. inmob. [258]
Inst. inversión colectiva - Estado variación patrimonial (I) - Inversiones inmobiliarias - Resultados contratos invers.
21 266 17 N inmob. rescindidos [259]
Inst. inversión colectiva - Estado variación patrimonial (I) - Inversiones inmobiliarias - Otros derivados de las invers.
22 283 17 N inmob. [260]
23 300 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Valores representativos de deuda [261]
24 317 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Instrumentos de patrimonio [262]
25 334 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Depósitos [263]
26 351 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Instituciones inversión colectiva [264]
27 368 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Derivados [265]
28 385 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Otros valores [266]
2299 440022 1177 NN IInnsstt.. iinnvveerrssiióónn ccoolleeccttiivvaa - EEssttaaddoo vvaarriiaacciióónn ppaattrriimmoonniiaall ((II)) - DDiiffeerreenncciiaass ddee ccaammbbiioo [[226677]]
30 419 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Otros rendimientos [268]
31 436 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Gastos repercutidos [269]
32 453 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Gastos gestión corriente [270]
Inst. inversión colectiva - Estado variación patrimonial (I) - Gastos gestión corriente - Comisión gestión sobre
33 470 17 N patrimonio [271]
Inst. inversión colectiva - Estado variación patrimonial (I) - Gastos gestión corriente - Comisión gestión sobre
34 487 17 N resultados [272]
Inst. inversión colectiva - Estado variación patrimonial (I) - Gastos gestión corriente - Comisión de depósito [273]
35 504 17 N
36 521 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Otros gastos gestión corriente [274]
Inst. inversión colectiva - Estado variación patrimonial (I) - Otros gastos gestión corriente - Tasas por registros
37 538 17 N oficiales [275]
Inst. inversión colectiva - Estado variación patrimonial (I) - Otros gastos gestión corriente - Admisión a cotización
3388 555555 1177 NN [[227766]]
Inst. inversión colectiva - Estado variación patrimonial (I) - Otros gastos gestión corriente - Difusión de valores
39 572 17 N liquidativos [277]
Inst. inversión colectiva - Estado variación patrimonial (I) - Otros gastos gestión corriente - Otros gastos gestión
40 589 17 N corriente [278]
41 606 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores [279]
42 623 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Tasaciones [280]
Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Admón.fincas y gastos comunidad
43 640 17 N [281]
Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Reparación y conservación
44 657 17 N inmuebles [282]
45 674 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Auditoría [283]
Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Servicios bancarios y similares [284]
46 691 17 N
Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Publicidad, propaganda y relaciones
47 708 17 N públicas [285]
48 725 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Servicios exteriores - Otros servicios [286]
49 742 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Amortización de mobiliario y enseres [287]
50 759 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Deterioros, excepto por invers. inmob. [288]
51 776 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Deterioros [289]
Inst. inversión colectiva - Estado variación patrimonial (I) - Retenciones no recuperadas por invers. de cartera
52 793 17 N exterior [290]
53 810 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Impuesto sobre beneficios [291]
54 827 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Gasto por compartimento [292]
55 844 17 N Inst. inversión colectiva - Estado variación patrimonial (I) - Otros [293]
56 861 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200450>"
Total: 870
Página 81

# Pag. 82

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "460"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN IInnsstt.. iinnvveerrssiióónn ccoolleeccttiivvaa - EEssttaaddoo vvaarriiaacciióónn ppaattrriimmoonniiaall ((IIII)) - IInnggrreessooss [[229944]]
Inst. inversión colectiva - Estado variación patrimonial (II) - Comisiones de descuento a favor de la Institución [295]
7 28 17 N
8 45 17 N Inst. inversión colectiva - Estado variación patrimonial (II) - Comisiones retrocedidas [296]
Inst. inversión colectiva - Estado variación patrimonial (II) - Comisiones retrocedidas - De intermediarios financieros
9 62 17 N [297]
Inst. inversión colectiva - Estado variación patrimonial (II) - Comisiones retrocedidas - Por inversiones en otras IIC
10 79 17 N [298]
11 96 17 N Inst. inversión colectiva - Estado variación patrimonial (II) - Comisiones retrocedidas - Otras [299]
12 113 17 N Inst. inversión colectiva - Estado variación patrimonial (II) - Ingreso compartimento por IB [300]
13 130 17 N Inst. inversión colectiva - Estado variación patrimonial (II) - Otros [301]
Inst. inversión colectiva - Estado variación patrimonial (II) - Revalorización inmuebles uso propio y resultados por
14 147 17 N enajenación inmobilizado [302]
1155 116644 1177 NN IInnsstt.. iinnvveerrssiióónn ccoolleeccttiivvaa - EEssttaaddoo vvaarriiaacciióónn ppaattrriimmoonniiaall ((IIII)) - PPAATTRRIIMMOONNIIOO FFIINNAALL [[330033]]
16 181 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200460>"
Total: 190
Página 82

# Pag. 83

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "470"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN SSoocciieeddaaddeess ddee ggaarraannttííaa rreeccíípprrooccaa - BBaallaannccee ((II)) - AAccttiivvoo - TTeessoorreerrííaa [[110011]]
Sociedades de garantía recíproca - Balance (I) - Activo - Deudores comerciales y otras cuentas a cobrar [102]
7 28 17 N
8 45 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Socios dudosos [103]
9 62 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Deudores varios [104]
Sociedades de garantía recíproca - Balance (I) - Activo - Otros créditos con las Administraciones Públicas [105]
10 79 17 N
11 96 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Socios por desembolsos exigidos [106]
12 113 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Activos por impuesto corriente [107]
13 130 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Resto de cuentas a cobrar [108]
14 147 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Inversiones financieras [109]
15 164 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Instrumentos de patrimonio [110]
166 1881 17 N Sociedades de ggarantía recípproca - Balance ((I)) - Activo - Valores reppresentativos de deuda [[111]]
17 198 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Depósitos a plazo en entidades de crédito [112]
18 215 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Activos financieros híbridos [113]
19 232 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Derivados de cobertura [114]
20 249 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Resto de derivados [115]
Sociedades de garantía recíproca - Balance (I) - Activo - Inversiones en empresas del grupo y asociadas [116]
21 266 17 N
Sociedades de garantía recíproca - Balance (I) - Activo - Activos no corrientes mantenidos para la venta [117]
22 283 17 N
23 300 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Inmovilizado material [118]
24 317 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Terrenos y construcciones [119]
Sociedades de garantía recíproca - Balance (I) - Activo - Instalaciones técnicas y otro inmovilizado material [120]
25 334 17 N
2266 335511 1177 NN SSoocciieeddaaddeess ddee ggaarraannttííaa rreeccíípprrooccaa -- BBaallaannccee ((II)) -- AAccttiivvoo -- IInnvveerrssiioonneess iinnmmoobbiilliiaarriiaass [[112211]]
27 368 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Inmovilizado intangible [122]
28 385 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Activos por impuesto diferido [123]
29 402 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Resto de activos [124]
30 419 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Periodificaciones [125]
31 436 17 N Sociedades de garantía recíproca - Balance (I) - Activo - Otros activos [126]
32 453 17 N Sociedades de garantía recíproca - Balance (I) - Activo - TOTAL ACTIVO [127]
Sociedades de garantía recíproca - Balance (I) - Pasivo - Acreedores comerciales y otras cuenta a pagar [129]
33 470 17 N
34 487 17 N Sociedades de garantía recíproca - Balance (I) - Pasivo - Acreedores varios [130]
35 504 17 N Sociedades de garantía recíproca - Balance (I) - Pasivo - Pasivos por impuesto corriente [131]
36 521 17 N Sociedades de garantía recíproca - Balance (I) - Pasivo - Deudas [132]
37 538 17 N Sociedades de garantía recíproca - Balance (I) - Pasivo - Obligaciones [133]
38 555 17 N Sociedades de garantía recíproca - Balance (I) - Pasivo - Deudas con entidades de crédito [134]
39 572 17 N Sociedades de garantía recíproca - Balance (I) - Pasivo - Fianzas y depósitos recibidos [135]
40 589 17 N Sociedades de garantía recíproca - Balance (I) - Pasivo - Sociedades de reafianzamiento [136]
41 606 17 N Sociedades de garantía recíproca - Balance (I) - Pasivo - Derivados de cobertura [137]
42 623 17 N Sociedades de garantía recíproca - Balance (I) - Pasivo - Resto de derivados [138]
43 640 17 N Sociedades de garantía recíproca - Balance (I) - Pasivo - Otras deudas [139]
Sociedades de garantía recíproca - Balance (I) - Pasivo - Pasivos vinculados con activos no corrientes mantenidos
44 657 17 N para la venta [140]
45 674 17 N Sociedades de garantía recíproca - Balance (I) - Pasivo - Pasivos por avales y garantías [141]
46 691 17 N Sociedades de garantía recíproca - Balance (I) - Pasivo - Garantías financieras [142]
47 708 17 N Sociedades de garantía recíproca - Balance (I) - Pasivo - Resto de avales y garantías [143]
48 725 17 N Sociedades de garantía recíproca - Balance (I) - Pasivo - Provisiones [144]
4499 774422 1177 NN SSoocciieeddaaddeess ddee ggaarraannttííaa rreeccíípprrooccaa -- BBaallaannccee ((II)) -- PPaassiivvoo -- PPrroovviissiioonneess ppoorr aavvaalleess yy ggaarraannttííaass [[114455]]
50 759 17 N Sociedades de garantía recíproca - Balance (I) - Pasivo - Otras provisiones [146]
51 776 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200470>"
Total: 785
Página 83

# Pag. 84

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "480"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
SSoocciieeddaaddeess ddee ggaarraannttííaa rreeccíípprrooccaa - BBaallaannccee ((IIII)) - PPaassiivvoo ((ccoonntt.)) - FFoonnddoo ddee pprroovviissiioonneess ttééccnniiccaass. CCoobbeerrttuurraa
6 11 17 N conjunto operaciones [147]
7 28 17 N Sociedades de garantía recíproca - Balance (II) - Pasivo (cont.) - Pasivos por impuesto diferido [148]
8 45 17 N Sociedades de garantía recíproca - Balance (II) - Pasivo (cont.) - Resto de pasivos [149]
9 62 17 N Sociedades de garantía recíproca - Balance (II) - Pasivo (cont.) - Capital reembolsable a la vista [150]
10 79 17 N Sociedades de garantía recíproca - Balance (II) - Pasivo (cont.) - TOTAL PASIVO [128]
11 96 17 N Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Fondos propios [151]
12 113 17 N Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital [152]
13 130 17 N Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital - Capital suscrito [153]
Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital - Capital suscrito - Socios protectores
14 147 17 N [154]
Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital - Capital suscrito - Socios partícipes
15 164 17 N [155]
Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital - Menos: capital no exigido [156]
16 181 17 N
Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Capital - Menos: capital reembolsable a la vista
17 198 17 N [157]
18 215 17 N Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Reservas [158]
Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Reservas revalorización (Ley 16/2012, de 27
19 232 17 N diciembre) [194]
Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Resultados de ejercicios anteriores [159]
20 249 17 N
21 266 17 N Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Resultado del ejercicio [160]
22 283 17 N Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Ajustes por cambio de valor [161]
23 300 17 N Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Activos financieros disponibles para la venta
2244 331177 1177 NN Sociedades de ggarantía recípproca - Balance ((II)) - Patrimonio neto - Otros [[163]]
Sociedades de garantía recíproca - Balance (II) - Patrimonio neto - Fondo de provisiones técnicas. Aportaciones
25 334 17 N de terceros [164]
Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - TOTAL PASIVO Y PATRIMONIO NETO [165]
26 351 17 N
27 368 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200480>"
Total: 377
Página 84

# Pag. 85

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "490"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN SSoocciieeddaaddeess ddee ggaarraannttííaa rreeccíípprrooccaa - CCueennttaa ppéérrddiiddaass y ggaannaanncciiaass - IImmppoorrttee nneettoo cciiffrraa ddee nneeggoocciiooss [[116666]]
Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Ingresos por avales y garantías [167]
7 28 17 N
Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Ingresos por prestación de servicios [168]
8 45 17 N
9 62 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Otros ingresos de explotación [169]
10 79 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Gastos de personal [170]
11 96 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Sueldos, salarios y asimilados [171]
12 113 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Cargas sociales [172]
13 130 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Provisiones [173]
14 147 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Otros gastos de explotación [174]
Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Dotaciones a provisiones por avales y garantías
15 164 17 N (neto) [175]
Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Correciones de valor por deterioro de socios
16 181 17 N dudosos (neto) [176]
Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Dotaciones al fondo de provisiones técnicas.
17 198 17 N Cobertura del conjunto de operaciones (neto) [177]
Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Fondo de provisiones técnicas. Aportaciones de
18 215 17 N terceros utilizadas [178]
19 232 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Amortización del inmovilizado [179]
Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Deterioro y resultado por enajenaciones de
20 249 17 N inmovilizado [180]
Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Deterioro y resultado activos no corrientes en
21 266 17 N venta (neto) [181]
22 283 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - RESULTADO DE EXPLOTACION [182]
23 300 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Ingresos financieros [183]
Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - De participaciones en instrumentos de
24 317 17 N patrimonio [184]
Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - De valores negociables y otros instrumentos
25 334 17 N financieros [185]
26 351 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Gastos financieros [186]
Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Variación de valor razonable en instrumentos
27 368 17 N financieros[187]
28 385 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Diferencias de cambio [188]
Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Correcciones de valor por deterioro de
29 402 17 N instrumentos financieros[189]
Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Resultado por enajenación de instrumentos
30 419 17 N financieros[190]
31 436 17 N Sociedades de ggarantía recípproca - Cuenta ppérdidas yy gganancias - RESULTADO FINANCIERO [[191]]
32 453 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Resultado antes de impuestos [192]
33 470 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Impuestos sobre beneficios [193]
34 487 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - RESULTADO DEL EJERCICIO [500]
35 504 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200490>"
Total: 513
Página 85

# Pag. 86

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "500"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Resultado de la cuenta de pérdidas y
6 11 17 N gananciias [[550000]]
Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio
7 28 17 N neto - Por ajustes por cambios de valor [195]
Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio
8 45 17 N neto - Activos fiananc. disponibles venta [196]
Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio
9 62 17 N neto - Otros [197]
Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio
10 79 17 N neto - Fondo provisiones técnicas. Aportaciones terceros [198]
Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio
11 96 17 N neto - Efecto impositivo [199]
Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio
12 113 17 N neto - Total ingresos gastos imputados directamente en el patrimonio neto [200]
Sociedades de ggarantía recípproca - Estado inggresos yy ggastos reconocidos - Transf. cuenta ppérdidas yy gganancias -
13 130 17 N Por ajustes por cambio de valor [201]
Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias -
14 147 17 N Activos financieros disponibles para venta [202]
Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias -
15 164 17 N Otros [203]
Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias -
16 181 17 N Fondo provisiones técnicas. Aportaciones terceros [204]
Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias -
17 198 17 N Efecto impositivo [205]
Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias -
18 215 17 N Total transf.cuenta pérdidas y ganacias [206]
Sociedades de garantía recíproca - Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias -
19 232 17 N TOTAL INGRESOS Y GASTOS RECONOCIDOS [207]
20 249 10 An Identificador de fin de reggistro OBLIGATORIO Constante "</T200500>"
Total: 258
Página 86

# Pag. 87

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "510"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final ejercicio anterior - Capital -
6 11 17 N SSuscriitto [[220088]]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final ejercicio anterior - Capital -
7 28 17 N Menos: no exigido [209]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto -Saldo, final ejercicio anterior - Capital -
8 45 17 N Menos: reembolsable [210]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final ejercicio anterior - Capital -
9 62 17 N Reservas [211]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final ejercicio anterior - Capital -
10 79 17 N Resultados ejercicios anteriores [212]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Capital -
11 96 17 N Suscrito [217]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Capital -
12 113 17 N Menos: no exigido [218]
Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto - Ajjustes ppor cambio de criterio - Cappital -
13 130 17 N Menos: reembolsable [219]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Reservas
14 147 17 N [220]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio -
15 164 17 N Resultados ejercicios anteriores [221]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Capital - Suscrito
16 181 17 N [226]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Capital - Menos: no
17 198 17 N exigido [227]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Capital - Menos:
18 215 17 N reembolsable [228]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Reservas [229]
19 232 17 N
Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto - Ajjustes ppor errores - Resultados
20 249 17 N ejercicios anteriores [230]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio -
21 266 17 N Capital - Suscrito [235]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio -
22 283 17 N Capital - Menos: no exigido [236]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio -
23 300 17 N Capital - Menos: reembolsable [237]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio -
24 317 17 N Reservas [238]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio -
25 334 17 N Resultados ejercicios anteriores [239]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos -
26 351 17 N Capital - Suscrito [244]
Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto - Total inggresos/ggastos reconocidos -
27 368 17 N Capital - Menos: no exigido [245]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos -
28 385 17 N Capital - Menos: reembolsable [246]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos -
29 402 17 N Reservas [247]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos -
30 419 17 N Resultados ejercicios anteriores [248]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Capital -
31 436 17 N Suscrito [253]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Capital -
32 453 17 N Menos: no exigido [254]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Capital -
33 470 17 N Menos: reembolsable [255]
Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto - Opperaciones con socios - Reservas [[256]]
34 487 17 N
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Resultados
35 504 17 N ejercicios anteriores [257]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de
36 521 17 N capital - Capital - Suscrito [262]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de
37 538 17 N capital - Capital - Menos: no exigido [263]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de
38 555 17 N capital - Capital - Menos: reembolsable [264]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto -Operaciones con socios - Aumentos de
39 572 17 N capital - Reservas [265]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de
40 589 17 N capital - Resultados ejercicios anteriores [266]
Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto - Opperaciones con socios - ((-)) Reducciones
41 606 17 N de capital - Capital - Suscrito [271]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones
42 623 17 N de capital - Capital - Menos: no exigido [272]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones
43 640 17 N de capital - Capital - Menos: reembolsable [273]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones
44 657 17 N de capital - Reservas [274]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones
45 674 17 N de capital - Resultados ejercicios anteriores [275]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución
46 691 17 N de dividendos - Capital - Suscrito [280]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución
47 708 17 N de dividendos - Capital - Menos: no exigido [281]
Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto - Opperaciones con socios - ((-)) Distribución
48 725 17 N de dividendos - Capital - Menos: reembolsable [282]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución
49 742 17 N de dividendos - Reservas [283]
Página 87

# Pag. 88

Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución
50 759 17 N de dividendos - Resultados ejercicios anteriores [284]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras
51 776 17 N operaciones con socios - Capital - Suscrito [289]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras
52 793 17 N operaciones con socios - Capital - Menos: no exigido [290]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras
53 810 17 N operaciones con socios - Capital - Menos: reembolsable [291]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras
54 827 17 N operaciones con socios - Reservas [292]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras
55 844 17 N operaciones con socios - Resultados ejercicios anteriores [293]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto -
56 861 17 N Cappital - Suscrito [[298]]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto -
57 878 17 N Capital - Menos: no exigido [299]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto -
58 895 17 N Capital - Menos: reembolsable [300]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto -
59 912 17 N Reservas [301]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto -
60 929 17 N Resultados ejercicios anteriores [302]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - SALDO, FINAL DEL EJERCICIO - Capital
61 946 17 N - Suscrito [307]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - SALDO, FINAL DEL EJERCICIO - Capital
62 963 17 N - Menos: no exigido [308]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - SALDO, FINAL DEL EJERCICIO - Capital
63 980 17 N - Menos: reembolsable [[309]]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - SALDO, FINAL DEL EJERCICIO -
64 997 17 N Reservas [310]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - SALDO, FINAL DEL EJERCICIO -
65 1014 17 N Resultados ejercicios anteriores [311]
66 1031 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200510>"
Total: 1040
Página 88

# Pag. 89

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "520"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio anterior -
6 11 17 N RResullttaddo ejjerciiciio [[221133]]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio anterior - Ajustes
7 28 17 N cambio valor [214]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio anterior - Fondos
8 45 17 N provisiones técnicas. Aportaciones de terceros [215]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio anterior - Total
9 62 17 N [216]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Resultado
10 79 17 N ejercicio [222]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Ajustes
11 96 17 N cambio valor [223]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por cambio de criterio - Fondos
12 113 17 N provisiones técnicas. Aportaciones de terceros [224]
Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto - Ajjustes ppor cambio de criterio - Total
13 130 17 N [225]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Resultado ejercicio
14 147 17 N [231]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Ajustes cambio valor
15 164 17 N [232]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Fondos provisiones
16 181 17 N técnicas. Aportaciones de terceros [233]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Ajustes por errores - Total [234]
17 198 17 N
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio -
18 215 17 N Resultado ejercicio [240]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio -
19 232 17 N Ajustes cambio valor [241]
Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto - Saldo ajjustado, inicio del ejjercicio -
20 249 17 N Fondos provisiones técnicas. Aportaciones de terceros [242]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Total
21 266 17 N [243]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos -
22 283 17 N Resultado ejercicio [249]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos -
23 300 17 N Ajustes cambio valor [250]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Total ingresos/gastos reconocidos -
24 317 17 N Fondos provisiones técnicas. Aportaciones de terceros [251]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto -Total ingresos/gastos reconocidos - Total
25 334 17 N [252]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Resultado
26 351 17 N ejercicio [258]
Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto - Opperaciones con socios - Ajjustes cambio
27 368 17 N valor [259]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Fondos
28 385 17 N provisiones técnicas. Aportaciones de terceros [260]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Total [261]
29 402 17 N
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de
30 419 17 N capital - Resultado ejercicio [267]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de
31 436 17 N capital - Ajustes cambio valor [268]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de
32 453 17 N capital - Fondos provisiones técnicas. Aportaciones de terceros [269]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Aumentos de
33 470 17 N capital - Total [270]
Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto - Opperaciones con socios - ((-)) Reducciones
34 487 17 N de capital - Resultado ejercicio [276]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones
35 504 17 N de capital - Ajustes cambio valor [277]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones
36 521 17 N de capital - Fondos provisiones técnicas. Aportaciones de terceros [278]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Reducciones
37 538 17 N de capital - Total [279]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución
38 555 17 N de dividendos - Resultado ejercicio [285]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución
39 572 17 N de dividendos - Ajustes cambio valor [286]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - (-) Distribución
40 589 17 N de dividendos - Fondos provisiones técnicas. Aportaciones de terceros [287]
Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto - Opperaciones con socios - ((-)) Distribución
41 606 17 N de dividendos - Total [288]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras
42 623 17 N operaciones con socios - Resultado ejercicio [294]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras
43 640 17 N operaciones con socios - Ajustes cambio valor [295]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras
44 657 17 N operaciones con socios - Fondos provisiones técnicas. Aportaciones de terceros [296]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Operaciones con socios - Otras
45 674 17 N operaciones con socios - Total [297]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto -
46 691 17 N Resultado ejercicio [303]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto -
47 708 17 N Ajustes cambio valor [304]
Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto - Otras variaciones ppatrimonio neto -
48 725 17 N Fondos provisiones técnicas. Aportaciones de terceros [305]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Otras variaciones patrimonio neto - Total
49 742 17 N [306]
Página 89

# Pag. 90

Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio - Resultado
50 759 17 N ejercicio [312]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio - Ajustes cambio
51 776 17 N valor [313]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio - Fondos
52 793 17 N provisiones técnicas. Aportaciones de terceros [314]
Sociedades de garantia recíproca - Estado total cambios patrimonio neto - Saldo, final del ejercicio - Total [315]
53 810 17 N
54 827 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200520>"
Total: 836
Página 90

# Pag. 91

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2013
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "DID"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
6 11 1 An Cuenta corriente tributaria "0" o "1"
7 12 4 Num Identificación - Ejercicio
8 16 1 Num Tipo de ejercicio
9 17 2 An Período Impositivo "0A"
10 19 2 Num Período Impositivo inicio - Día
11 21 2 Num Período Impositivo inicio - Mes
12 23 2 Num Período Impositivo inicio - Año
13 25 2 Num Período Impositivo fin - Día
14 27 2 Num Período Impositivo fin - Mes
15 29 2 Num Período Impositivo fin - Año
16 31 9 An Identificación - NIF
17 40 40 An Identificación - Apellidos y nombre o Razón Social
18 80 17 N Liquidación - Base imponible [552]
19 97 17 N Liquidación - Cuota íntegra [562]
20 114 17 N LLiiquiiddaciióón - LLííquiiddo a iingresar o a ddevollver EEsttaddo [[662211]]
21 131 17 Num RESERVADO AEAT
22 148 17 Num RESERVADO AEAT
23 165 17 Num RESERVADO AEAT
24 182 17 Num RESERVADO AEAT
25 199 1 An Devolución - Renuncia o por Transferencia "blanco" "R","D"
26 200 17 Num Devolución - Importe a devolver
27 217 34 An Número de cuenta IBAN
Modalidad de ingreso. Uno de los siguientes valores
"blanco", "I" Adeudo en
cuenta, "H" Efectivo, "U"
28 251 1 An Domiciliación
29 252 1 An RESERVADO AEAT
3300 225533 11 AAnn RREESSEERRVVAADDOO AAEEAATT
31 254 17 Num Ingreso - Importe a ingresar
32 271 34 An Número de cuenta IBAN
33 305 1 An Cuota Cero "0" o "1"
34 306 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200DID>"
Total: 315
Página 91