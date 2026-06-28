# Pag. 1

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 17 An Constante. <T + modelo + discriminante (*) + Ejercicio devengo + periodo + tipo + > "<T200020100A0000>"
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
16, una 17, una 18, dos 19, una DID debería rellenarse el vector con el siguiente
contenido:001002002003004005006007008009010011012013014015016017018019019DIDFIN (y el resto a blancos hasta
10 337 600 An completar las 600 posiciones)
11 937 9 An Constante "</VECTOR>"
Contenido del fichero. Aquí se debe incluir el contenido de las páginas correspondientes a la declaración según el formato descrito
12 946Variable An para cada página en este mismo documento
13*** 18 An Constante. </T + modelo + discriminante + Ejercicio devengo + periodo + tipo + > "</T200020100A0000>"
14*** 2An Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)
Total Variable
(*) NOTA. Valor discriminante: "0" Normal (resto); "A" Aseguradoras; "E" Entidades de crédito; "I" Inversión colectiva; "G" Garantía recíproca,
(**) A cumplimentar por las entidades desarrolladoras (EEDD):
Versión del programa: Debe consignarse el identificador de la versión del SW desarrollado por la ED
NIF Empresa Desarrollo: Debe consignarse el NIF de la ED del SW
Página 1

# Pag. 2

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "001"
4 9 1 An Fin de identificador de modelo y página. Constante ">". OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria. En blanco
66 1111 55 NNum CCóóddiigo AAddmiiniisttraciióón.{{AAddmon}}
7 16 4 Num Periodo Impositivo -Año inicio.
8 20 2 Num Periodo Impositivo - Mes inicio.
9 22 2 Num Periodo Impositivo - Día Inicio.
10 24 4 Num Periodo Impositivo - Año final.
11 28 2 Num Periodo Impositivo - Mes final.
12 30 2 Num Periodo Impositivo - Día final.
13 32 1 Num Identificación - Tipo de ejercicio. "1", "2" ó "3"
14 33 4 Num Identificación - C.N.A.E. Actividad principal Incluido en el fichero CNAE.TXT.
15 37 9 An Identificación - NIF.
16 46 40 An Identificación - Apellidos y nombre o Razón Social.
17 86 9 An Identificación - Teléfono 1
1188 9955 99 AAnn IIddeennttiiffiiccaacciióónn -- TTeellééffoonnoo 22
19 104 4 Num Ejercicio.
20 108 1 Num Entidad sin animo de lucro acogida régimen fiscal Título II Ley 49/2002 [001]
21 109 1 Num Entidad parcialmente exenta [002]
22 110 1 Num Sociedad de inversión de capital variable o fondo de inversión de carácter financiero [003]
23 111 1 Num Sociedad de inversión inmobiliaria o fondo de inversión inmobiliaria [004]
24 112 1 Num Comunidades titulares de montes vecinales en mano común [005]
25 113 1 Num Entidad de tenencia de valores extranjeros [011]
26 114 1 Num Agrupación de interés económico española o U.T.E. [013]
27 115 1 Num Agrupación europea de interés económico [014]
28 116 1 Num Cooperativa protegida [017]
29 117 1 Num Cooperativa especialmente protegida [018]
30 118 1 Num Resto cooperativas [019]
31 119 1 Num Establecimiento permanente [021]
32 120 1 Num Gran empresa [023]
33 121 1 Num Entidad de crédito [024]
34 122 1 Num Entidad aseguradora [025]
35 123 1 Num Entidades de capital-riesgo [031]
36 124 1 Num Sociedades desarrollo industrial regional [032]
37 125 1 Num Sociedad de garantía recíproca o de reafianzamiento [036]
38 126 1 Num Fondo de Pensiones Real Decreto Legislativo 1/2002 de 29 de noviembre [048]
39 127 1 Num Mutua de seguros o Mutualidad de previsión social [058]
40 128 1 Num Incentivos empresa de reducida dimensión ( cap XII, tít VII L.I.S ) [006]
41 129 1 Num Entidad ZEC [015]
42 130 1 Num Régimen entidades navieras en función del tonelaje [022]
4433 113311 11 NNuumm TTrriibbuuttaacciióónn ccoonnjjuunnttaa EEssttaaddoo//DDiippuutt.CCddaadd.FFoorraalleess [[002288]]
44 132 1 Num Entidades sometidas a normativa foral [047]
45 133 1 Num Regímenes especiales de normativa foral [049]
46 134 1 Num Régimen especial Canarias [029]
47 135 1 Num Régimen especial minería [033]
48 136 1 Num Régimen especial hidrocarburos [034]
49 137 1 Num Entidad dedicada al arrend.viviendas [38]
50 138 1 Num Entidad en rég. atribución de rentas constituida en el extranjero con presencia en territorio español [046]
51 139 1 Num SOCIMI [012]
52 140 1 Num Entidades que aplican el régimen especial Ley 11/2009 (excepto SOCIMI) [057]
53 141 1 Num Otros regímenes especiales [020]
54 142 1 Num Tipo gravamen reducido mant.o creación empleo [056]
5555 114433 11 NNuumm IInncclluussiióónn eenn bbaassee iimmppoonniibbllee rreennttaass ppoossiittiivvaass aarrtt.. 110077 LL..II..SS.. [[000077]]
56 144 1 Num Opción art. 107.6 L.I.S. [008]
57 145 1 Num Sociedad dominante de grupo fiscal [009]
58 146 1 Num Sociedad dependiente de grupo fiscal [010]
59 147 1 Num Opción art.51.2.b) L.I.S. [016]
60 148 1 Num Entidad inactiva [026]
61 149 1 Num Base imponible negativa o cero [027]
62 150 1 Num Transmisión elementos patrimoniales arts. 26.2.d) y 84.1 L.I.S. [030]
63 151 1 Num Opción art.43.1 R.I.S. [035]
64 152 1 Num Opción art. 43.3 R.I.S. [037]
65 153 1 Num Entidad que forma parte de un grupo mercantil (art. 42 del Cód. Comercio) [039]
66 154 1 Num Obligación información art. 15 R.I.S. [043]
67 155 1 Num Obligación información art. 45 R.I.S. [044]
6688 115566 11 NNum IInversiiones anttiiciipaddas - reserva iinversiiones en CCanariias ((artt. 2277.1100 LLey 1199//11999944)) [[004455]]
69 157 1 Num Balance y ECPN 0.No consta 1.Mod.normal 2.Mod.abreviado 3. Mod.PYMES
70 158 1 Num Pérdidas y ganancias 0.No consta 1.Mod.normal 2.Mod.abreviado 3. Mod.PYMES
71 159 7 An Nº de grupo fiscal al que pertenecen las entidades que hayan marcado las claves 009 ó 010 [040]
72 166 9 Num Personal asalariado (cifra media del ejercicio) Personal fijo [041] 7enteros 2 decimales
73 175 9 Num Personal asalariado (cifra media del ejercicio) Personal no fijo [042] 7enteros 2 decimales
74 184 1 Num Declaración complementaria
75 185 13 Num Nº de justificante de la declaración anterior
76 198 21 An D. - Nombre o Razón social - Secretario del Consejo de Administración
77 219 09 An N.I.F. - Secretario del Consejo de Administración
78 228 08 Num Fecha-Contribuyentes por el I.R.N.R. AAAAMMDD
79 236 25 An Declaración representantes legales entidad. Firma - Localidad
8800 226611 22 NNuumm DDeeccllaarraacciióónn rreepprreesseennttaanntteess lleeggaalleess eennttiiddaadd. FFiirrmmaa -- DDííaa
81 263 10 A Declaración representantes legales entidad. Firma - Mes
82 273 4 Num Declaración representantes legales entidad. Firma - Año
83 277 36 An Declaración representantes legales entidad. 1 - Nombre y apellidos
Página 2

# Pag. 3

84 313 9 An Declaración representantes legales entidad. 1 - N.I.F
85 322 8 Num Declaración representantes legales entidad. 1 - Fecha Poder AAAAMMDD
86 330 12 An Declaración representantes legales entidad. 1 - Notaría
87 342 36 An Declaración representantes legales entidad. 2 - Nombre y apellidos
88 378 9 An Declaración representantes legales entidad. 2 - N.I.F
89 387 8 Num Declaración representantes legales entidad. 2 - Fecha Poder AAAAMMDD
90 395 12 An Declaración representantes legales entidad. 2 - Notaría
91 407 36 An Declaración representantes legales entidad. 3 - Nombre y apellidos
92 443 9 An Declaración representantes legales entidad. 3 - N.I.F
93 452 8 Num Declaración representantes legales entidad.3 - Fecha Poder AAAAMMDD
94 460 12 An Declaración representantes legales entidad. 3 - Notaría
95 472 21 An RESERVADO PARA LA A.E.A.T. (Dejar en blanco) Incluye Nº Referencia
9966 449933 2200 AAnn IIddeennttiiffiiccaaddoorr cclliieennttee EEEEDDDD. RREESSEERRVVAADDOO PPAARRAA LLAASS EEEEDDDD.
97 513 50 An Nombre y Apellidos de la persona de contacto para incidencias
98 563 9 Num Teléfono fijo de contacto para incidencias
99 572 9 Num Teléfono móvil de contacto para incidencias
100 581 50 An Dirección de correo electrónico para incidencias
101 631 13 An SELLO ELECTRONICO RESERVADO PARA LA A.E.A.T. (Dejar en blanco)
102 644 10 An Identificador de fin de Registro. OBLIGATORIO </T200001>
Total: 653
NOTA: Los importes son de 15 enteros (o N + 14) y 2 decimales
Página 3

# Pag. 4

Agencia Tributaria
Modelo 200 Diseño de registro
vers. 1.0 I 2 m 01 p 0 uesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas constituidas en el extranjero con presencia en territorio español)
NºPosic. Lon Tipo Descripción Validación Contenido
1 1 2 An C Inicio del identificador de modelo y página. Constante "<T"
2 3 3 Num C Modelo. Constante "200"
3 6 3 An C Página. Constante "002"
4 9 1 An C Fin de identificador de modelo y página. Constante ">"
Indicador de página complementaria. Blanco (No
complementaria) o
"C" (Complementaria)
5 10 1 An C
6 11 9 An C A. Relación de administradores .1 - N.I.F.
7 20 1 A C A. Relación de administradores. 1 - F/J "F" o "J"
8 21 1 Num C A. Relación de administradores. 1 - RPTE. ( "0", "1")
9 22 40 An C AA. RRellaciióón dde addmiiniisttraddores. 11 - AApelllliiddos y nombbre // RRazóón sociiall
10 62 17 An C A. Relación de administradores. 1 - Domicilio fiscal
11 79 2 An C A. Relación de administradores .1 - Código Provincial
12 81 9 An C A. Relación de administradores. 2 - N.I.F.
13 90 1 A C A. Relación de administradores. 2 - F/J "F" o "J"
14 91 1 Num C A. Relación de administradores. 2 - RPTE. ( "0", "1")
15 92 40 An C A. Relación de administradores. 2 - Apellidos y nombre / Razón social
16 132 17 An C A. Relación de administradores. 2 - Domicilio fiscal
17 149 2 An C A. Relación de administradores. 2 - Código Provincial
18 151 9 An C A. Relación de administradores. 3 - N.I.F.
19 160 1 A C A. Relación de administradores. 3 - F/J "F" o "J"
20 161 1 Num C A. Relación de administradores. 3 - RPTE. ( "0", "1")
21 162 40 An C A. Relación de administradores. 3 - Apellidos y nombre / Razón social
22 202 17 An C A. Relación de administradores. 3 - Domicilio fiscal
23 219 2 An C A. Relación de administradores. 3 - Código Provincial
24 221 9 An C A. Relación de administradores. 4 - N.I.F.
25 230 1 A C A. Relación de administradores. 4 - F/J "F" o "J"
2266 223311 11 NNuumm CC AA. RReellaacciióónn ddee aaddmmiinniissttrraaddoorreess. 44 - RRPPTTEE. (( ""00"", ""11""))
27 232 40 An C A. Relación de administradores. 4 - Apellidos y nombre / Razón social
28 272 17 An C A. Relación de administradores. 4 - Domicilio fiscal
29 289 2 An C A. Relación de administradores. 4 - Código Provincial
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
42 431 15 An C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 1 - Datos participada - N.I.F.
4433 444466 3300 AAnn CC BB.. PPaarrttiicciippaacciioonneess ddiirreeccttaass.. - BB..11.. PPaarrttiicc.. ddeeccllaarraannttee eenn oottrraass eennttiiddaaddeess.. EEnnttiiddaadd 11 - DDaattooss ppaarrttiicciippaaddaa - NNoommbbrree oo rraazzóónn ssoocciiaall
44 476 2 An C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 1 - Datos participada - Código provincia / país
45 478 5 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 1 - Datos de la declarante - Porcentaje de participación
46 483 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 1 - Datos de la declarante - Valor nominal total de la participación
47 500 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 1 - Datos de la declarante - Valor en libros (en el activo de la declarante) de la participación
48 517 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 1 - Datos de la declarante - Ingresos por Dividendos recibidos en el ejercicio declarado
49 534 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 1 - Correcciones valorativas - Corrección de valor pérdidas y ganancias ejercicio
50 551 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 1 - Correcciones valorativas - Corrección fiscal (art. 12.3 LIS) del resultado del ejercicio
51 568 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 1 - Correcciones valorativas - Efecto corrección valorativa en la BI del ejercicio
52 585 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 1 - Corrrecciones valorativas - Saldo de correcciones fiscales (art. 12.3 LIS) pendientes a fin de
53 602 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 1 - Datos adicionales participada - Capital
54 619 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 1 - Datos adicionales participada - Reservas
55 636 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 1 - Datos adicionales participada - Otras partidas del patrimonio neto
56 653 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 1 - Datos adicionales participada - Resultado del último ejercicio
57 670 15 An C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 2 - Datos participada - N.I.F.
58 685 30 An C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 2 - Datos participada - Nombre o razón social
59 715 2 An C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 2 - Datos participada - Código provincia / país
60 717 5 Num C B. Particippaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 2 - Datos de la declarante - Porcentajje de pparticippación
61 722 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 2 - Datos de la declarante - Valor nominal total de la participación
62 739 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 2 - Datos de la declarante - Valor en libros (en el activo de la declarante) de la participación
63 756 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 2 - Datos de la declarante - Ingresos por Dividendos recibidos en el ejercicio declarado
64 773 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 2 - Correcciones valorativas - Corrección de valor pérdidas y ganancias ejercicio
65 790 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 2 - Correcciones valorativas - Corrección fiscal (art. 12.3 LIS) del resultado del ejercicio
66 807 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 2 - Correcciones valorativas - Efecto corrección valorativa en la BI del ejercicio
67 824 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 2 - Corrrecciones valorativas - Saldo de correcciones fiscales (art. 12.3 LIS) pendientes a fin de
68 841 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 2 - Datos adicionales participada - Capital
69 858 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 2 - Datos adicionales participada - Reservas
70 875 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 2 - Datos adicionales participada - Otras partidas del patrimonio neto
71 892 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 2 - Datos adicionales participada - Resultado del último ejercicio
72 909 15 An C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 3 - Datos participada - N.I.F.
73 924 30 An C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 3 - Datos participada - Nombre o razón social
74 954 2 An C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 3 - Datos participada - Código provincia / país
75 956 5 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 3 - Datos de la declarante - Porcentaje de participación
76 961 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 3 - Datos de la declarante - Valor nominal total de la participación
77 978 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 3 - Datos de la declarante - Valor en libros (en el activo de la declarante) de la participación
78 995 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 3 - Datos de la declarante - Ingresos por Dividendos recibidos en el ejercicio declarado
79 1012 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 3 - Correcciones valorativas - Corrección de valor pérdidas y ganancias ejercicio
80 1029 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 3 - Correcciones valorativas - Corrección fiscal (art. 12.3 LIS) del resultado del ejercicio
81 1046 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 3 - Correcciones valorativas - Efecto corrección valorativa en la BI del ejercicio
82 1063 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 3 - Corrrecciones valorativas - Saldo de correcciones fiscales (art. 12.3 LIS) pendientes a fin de
83 1080 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 3 - Datos adicionales participada - Capital
84 1097 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 3 - Datos adicionales participada - Reservas
85 1114 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 3 - Datos adicionales participada - Otras partidas del patrimonio neto
86 1131 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 3 - Datos adicionales participada - Resultado del último ejercicio
87 1148 15 An C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 4 - Datos participada - N.I.F.
Página 4

# Pag. 5

88 1163 30 An C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 4 - Datos participada - Nombre o razón social
89 1193 2 An C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 4 - Datos participada - Código provincia / país
90 1195 5 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 4 - Datos de la declarante - Porcentaje de participación
91 1200 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 4 - Datos de la declarante - Valor nominal total de la participación
B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 4 - Datos de la declarante - Valor en libros (en el activo de la declarante) de la participación
92 1217 17 Num C
B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 4 - Datos de la declarante - Ingresos por Dividendos recibidos en el ejercicio declarado
93 1234 17 Num C
94 1251 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 4 - Correcciones valorativas - Corrección de valor pérdidas y ganancias ejercicio
B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 4 - Correcciones valorativas - Corrección fiscal (art. 12.3 LIS) del resultado del ejercicio
95 1268 17 N C
96 1285 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 4 - Correcciones valorativas - Efecto corrección valorativa en la BI del ejercicio
B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 4 - Corrrecciones valorativas - Saldo de correcciones fiscales (art. 12.3 LIS) pendientes a fin de
97 1302 17 N C ejercicio
98 1319 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 4 - Datos adicionales participada - Capital
99 1336 17 Num C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 4 - Datos adicionales participada - Reservas
100 1353 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 4 - Datos adicionales participada - Otras partidas del patrimonio neto
101 1370 17 N C B. Participaciones directas. - B.1. Partic. declarante en otras entidades. Entidad 4 - Datos adicionales participada - Resultado del último ejercicio
102 1387 15 An C B. Participaciones directas. - B.2. Partic.de personas o entidades en la declarante. 1 - N.I.F.
103 1402 1 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 1 - RPTE. ( "0", "1")
104 1403 1 A C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante.1 - F/J "F" o "J"
105 1404 37 An C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 1 - Apellidos y nombre / Razón social
106 1441 2 An C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 1 - Código provincia / país
107 1443 17 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 1 - Nominal
108 1460 5 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 1 - % Particip.
109 1465 15 An C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 2 - N.I.F.
110 1480 1 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 2 - RPTE. ( "0", "1")
111 1481 1 A C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 2 - F/J "F" o "J"
112 1482 37 An C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 2 - Apellidos y nombre / Razón social
113 1519 2 An C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 2 - Código provincia / país
114 1521 17 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 2 - Nominal
115 1538 5 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 2 - % Particip.
116 1543 15 An C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 3 - N.I.F.
117 1558 1 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 3 - RPTE. ( "0", "1")
118 1559 1 A C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 3 - F/J. "F" o "J"
111199 11556600 3377 AAnn CC BB.. PPaarrttiicciippaacciioonneess ddiirreeccttaass.. - BB..22.. PPaarrttiicc.. ddee ppeerrssoonnaass oo eennttiiddaaddeess eenn llaa ddeeccllaarraannttee.. 33 - AAppeelllliiddooss yy nnoommbbrree // RRaazzóónn ssoocciiaall
120 1597 2 An C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 3 - Código provincia / país
121 1599 17 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 3 - Nominal
122 1616 5 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 3 - % Particip.
123 1621 15 An C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 4 - N.I.F.
124 1636 1 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 4 - RPTE. ( "0", "1")
125 1637 1 A C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 4 - F/J. "F" o "J"
126 1638 37 An C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante.4 - Apellidos y nombre / Razón social
127 1675 2 An C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 4 - Código provincia / país
128 1677 17 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 4 - Nominal
129 1694 5 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 4 - % Particip.
130 1699 15 An C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 5 - N.I.F.
131 1714 1 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante.5 - RPTE. ( "0", "1")
132 1715 1 A C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 5 - F/J. "F" o "J"
133 1716 37 An C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 5 - Apellidos y nombre / Razón social.
134 1753 2 An C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 5 - Código provincia / país
135 1755 17 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 5 - Nominal
136 1772 5 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 5 - % Particip.
113377 11777777 1155 AAnn CC BB. PPaarrttiicciippaacciioonneess ddiirreeccttaass. - BB.22. PPaarrttiicc. ddee ppeerrssoonnaass oo eennttiiddaaddeess eenn llaa ddeeccllaarraannttee. 66 - NN.II.FF.
138 1792 1 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 6 - RPTE. ( "0", "1")
139 1793 1 A C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 6 - F/J. "F" o "J"
140 1794 37 An C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante.6 - Apellidos y nombre / Razón social
141 1831 2 An C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 6 - Código provincia / país
142 1833 17 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 6 - Nominal
143 1850 5 Num C B. Participaciones directas. - B.2. Partic. de personas o entidades en la declarante. 6 - % Particip.
B .Participaciones directas.- B.2. Suma de porcentajes de participación de personas o entidades en el capital de la declarante inferiores al 5% o al 1% si se trata de valores que
144 1855 5 Num coticen en un mercado secundario organizado.
145 1860 5 Num B. Participaciones directas.- B.2. Suma de porcentajes de participaciones en situaciones especiales.
146 1865 10 An C Identificador de fin de Registro. OBLIGATORIO </T200002>
Total: 1874
Página 5

# Pag. 6

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "003"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN BBallance - AActtiivo ((II)) - AActtiivo no corriientte [[110011]]
7 28 17 N Balance - Activo (I) - Inmovilizado intangible [102]
8 45 17 N Balance - Activo (I) - Desarrollo [103]
9 62 17 N Balance - Activo (I) - Concesiones [104]
10 79 17 N Balance - Activo (I) - Patentes, licencias, marcas y similares [105]
11 96 17 N Balance - Activo (I) - Fondo de comercio [106]
12 113 17 N Balance - Activo (I) - Aplicaciones informáticas [107]
13 130 17 N Balance - Activo (I) - Investigación [108]
14 147 17 N Balance - Activo (I) - Otro inmovilizado intangible [109]
15 164 17 N Balance - Activo (I) - Resto [110]
16 181 17 N Balance - Activo (I) - Inmovilizado material [111]
17 198 17 N Balance - Activo (I) - Terrenos y construcciones [112]
1188 221155 1177 NN BBaallaannccee -- AAccttiivvoo ((II)) -- IInnssttaallaacciioonneess ttééccnniiccaass yy oottrroo iinnmmoovviilliizzaaddoo mmaatteerriiaall [[111133]]
19 232 17 N Balance - Activo (I) - Inmovilizado en curso y anticipos [114]
20 249 17 N Balance - Activo (I) - Inversiones inmobiliarias [115]
21 266 17 N Balance - Activo (I) - Terrenos [116]
22 283 17 N Balance - Activo (I) - Construcciones [117]
23 300 17 N Balance - Activo (I) - Inversiones en empresas del grupo y asociadas [118]
24 317 17 N Balance - Activo (I) - Instrumentos de patrimonio [119]
25 334 17 N Balance - Activo (I) - Créditos a empresas [120]
26 351 17 N Balance - Activo (I) - Valores representativos de deuda [121]
27 368 17 N Balance - Activo (I) - Derivados [122]
28 385 17 N Balance - Activo (I) - Otros activos financieros [123]
29 402 17 N Balance - Activo (I) - Otras inversiones [124]
30 419 17 N Balance - Activo (I) - Resto [125]
31 436 17 N Balance - Activo (I) - Inversiones financieras a largo plazo [126]
32 453 17 N Balance - Activo (I) - Instrumentos de patrimonio [127]
33 470 17 N Balance - Activo (I) - Créditos a terceros [128]
34 487 17 N Balance - Activo (I) - Valores representativos de deuda [129]
35 504 17 N Balance - Activo (I) - Derivados [130]
36 521 17 N Balance - Activo (I) - Otros activos financieros [131]
37 538 17 N Balance - Activo (I) - Otras inversiones [132]
38 555 17 N Balance - Activo (I) - Resto [133]
39 572 17 N Balance - Activo (I) - Activos por impuesto diferido [134]
40 589 17 N Balance - Activo (I) - Deudores comerciales no corrientes [135]
41 606 17 N Balance - Activo (I) - Activo corriente [136]
42 623 17 N Balance - Activo (I) - Activos no corrientes mantenidos para la venta [137]
4433 664400 1177 NN BBaallaannccee - AAccttiivvoo ((II)) - EExxiisstteenncciiaass [[113388]]
44 657 17 N Balance - Activo (I) - Comerciales [139]
45 674 17 N Balance - Activo (I) - Materias primas y otros aprovisionamientos [140]
46 691 17 N Balance - Activo (I) - Productos en curso [141]
47 708 17 N Balance - Activo (I) - Productos en curso. De ciclo largo de producción [142]
48 725 17 N Balance - Activo (I) - Productos en curso. De ciclo corto de producción [143]
49 742 17 N Balance - Activo (I) - Productos terminados [144]
50 759 17 N Balance - Activo (I) - Productos terminados. De ciclo largo de producción [145]
51 776 17 N Balance - Activo (I) - Productos terminados. De ciclo corto de producción [146]
52 793 17 N Balance - Activo (I) - Subproductos, residuos y materiales recuperados [147]
53 810 17 N Balance - Activo (I) - Anticipos a proveedores [148]
54 827 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200003>"
TToottaall:: 883366
Página 6

# Pag. 7

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. Constante "<T" . OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "004"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria. En blanco En blanco
66 1111 1177 NN BBaallaannccee - AAccttiivvoo ((IIII)) -DDeeuuddoorreess ccoommeerrcciiaalleess yy oottrraass ccuueennttaass aa ccoobbrraarr [[114499]]
7 28 17 N Balance - Activo (II) -Clientes por ventas y prestaciones de servicios [150]
8 45 17 N Balance - Activo (II) - Clientes por ventas y prestaciones de servicios a largo plazo [151]
9 62 17 N Balance - Activo (II) - Clientes por ventas y prestaciones de servicios a corto plazo [152]
10 79 17 N Balance - Activo (II) - Clientes empresas del grupo y asociadas [153]
11 96 17 N Balance - Activo (II) - Deudores varios [154]
12 113 17 N Balance - Activo (II) - Personal [155]
13 130 17 N Balance - Activo (II) - Activos por impuesto corriente [156]
14 147 17 N Balance - Activo (II) - Otros créditos con las Administraciones Públicas [157]
15 164 17 N Balance - Activo (II) - Accionistas (socios) por desembolsos exigidos [158]
16 181 17 N Balance - Activo (II) - Otros deudores [159]
17 198 17 N Balance - Activo (II) - Inversiones en empresas del grupo y asociadas a corto plazo [160]
1188 221155 1177 NN BBaallaannccee -- AAccttiivvoo ((IIII)) -- IInnssttrruummeennttooss ddee ppaattrriimmoonniioo [[116611]]
19 232 17 N Balance - Activo (II) - Créditos a empresas [162]
20 249 17 N Balance - Activo (II) - Valores representativos de deuda [163]
21 266 17 N Balance - Activo (II) - Derivados [164]
22 283 17 N Balance - Activo (II) - Otros activos financieros [165]
23 300 17 N Balance - Activo (II) - Otras inversiones [166]
24 317 17 N Balance - Activo (II) - Resto [167]
25 334 17 N Balance - Activo (II) - Inversiones financieras a corto plazo [168]
26 351 17 N Balance - Activo (II) - Instrumentos de patrimonio [169]
27 368 17 N Balance - Activo (II) - Créditos a empresas [170]
28 385 17 N Balance - Activo (II) - Valores representativos de deuda [171]
29 402 17 N Balance - Activo (II) - Derivados [172]
30 419 17 N Balance - Activo (II) - Otros activos financieros [173]
31 436 17 N Balance - Activo (II) - Otras inversiones [174]
32 453 17 N Balance - Activo (II) - Resto [175]
33 470 17 N Balance - Activo (II) - Periodificaciones a corto plazo [176]
34 487 17 N Balance - Activo (II) - Efectivo y otros activos líquidos equivalentes [177]
35 504 17 N Balance - Activo (II) - Tesorería [178]
36 521 17 N Balance - Activo (II) - Otros activos líquidos equivalentes [179]
37 538 17 N Balance - Activo (II) - Total activo [180]
38 555 10 An Identificador de fin de registro OBLIGATORIO Constante </T200004>
Total: 564
Página 7

# Pag. 8

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "005"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN BBallance - PPattriimoniio netto y pasiivo ((II)) - PPattriimoniio netto [[118855]]
7 28 17 N Balance - Patrimonio neto y pasivo (I) - Fondos propios [186]
8 45 17 N Balance - Patrimonio neto y pasivo (I) - Capital [187]
9 62 17 N Balance - Patrimonio neto y pasivo (I) - Capital escriturado [188]
10 79 17 N Balance - Patrimonio neto y pasivo (I) - Capital no exigido [189]
11 96 17 N Balance - Patrimonio neto y pasivo (I) - Prima de emisión [190]
12 113 17 N Balance - Patrimonio neto y pasivo (I) - Reservas [191]
13 130 17 N Balance - Patrimonio neto y pasivo (I) - Legal y estatutarias [192]
14 147 17 N Balance - Patrimonio neto y pasivo (I) - Otras reservas [193]
15 164 17 N Balance - Patrimonio neto y pasivo (I) - Acciones y participaciones en patrimonio propias [194]
16 181 17 N Balance - Patrimonio neto y pasivo (I) - Resultados de ejercicios anteriores [195]
17 198 17 N Balance - Patrimonio neto y pasivo (I) - Remanente [196]
1188 221155 1177 NN BBaallaannccee -- PPaattrriimmoonniioo nneettoo yy ppaassiivvoo ((II)) -- RReessuullttaaddooss nneeggaattiivvooss ddee eejjeerrcciicciiooss aanntteerriioorreess [[119977]]
19 232 17 N Balance - Patrimonio neto y pasivo (I) - Otras aportaciones de socios [198]
20 249 17 N Balance - Patrimonio neto y pasivo (I) - Resultado del ejercicio [199]
21 266 17 N Balance - Patrimonio neto y pasivo (I) - Dividendo a cuenta [200]
22 283 17 N Balance - Patrimonio neto y pasivo (I) - Otros instrumentos de patrimonio neto [201]
23 300 17 N Balance - Patrimonio neto y pasivo (I) - Ajustes por cambios de valor [202]
24 317 17 N Balance - Patrimonio neto y pasivo (I) - Activos financieros disponibles para la venta [203]
25 334 17 N Balance - Patrimonio neto y pasivo (I) - Operaciones de cobertura [204]
26 351 17 N Balance - Patrimonio neto y pasivo (I) - Activos no corrientes y pasivos vinculados [205]
27 368 17 N Balance - Patrimonio neto y pasivo (I) - Diferencia de conversión [206]
28 385 17 N Balance - Patrimonio neto y pasivo (I) - Otros [207]
29 402 17 N Balance - Patrimonio neto y pasivo (I) - Ajustes en patrimonio neto [208]
30 419 17 N Balance - Patrimonio neto y pasivo (I) - Subvenciones, donaciones y legados recibidos [209]
31 436 17 N Balance - Patrimonio neto y pasivo (I) - Pasivo no corriente [210]
32 453 17 N Balance - Patrimonio neto y pasivo (I) - Provisiones a largo plazo [211]
33 470 17 N Balance - Patrimonio neto y pasivo (I) - Obligaciones por prestaciones a largo plazo al personal [212]
34 487 17 N Balance - Patrimonio neto y pasivo (I) - Actuaciones medioambientales [213]
35 504 17 N Balance - Patrimonio neto y pasivo (I) - Provisiones por reestructuración [214]
36 521 17 N Balance - Patrimonio neto y pasivo (I) - Otras provisiones [215]
37 538 17 N Balance - Patrimonio neto y pasivo (I) - Deudas a largo plazo [216]
38 555 17 N Balance - Patrimonio neto y pasivo (I) - Obligaciones y otros valores negociables [217]
39 572 17 N Balance - Patrimonio neto y pasivo (I) - Deudas con entidades de crédito [218]
40 589 17 N Balance - Patrimonio neto y pasivo (I) - Acreedores por arrendamiento financiero [219]
41 606 17 N Balance - Patrimonio neto y pasivo (I) - Derivados [220]
42 623 17 N Balance - Patrimonio neto y pasivo (I) - Otros pasivos financieros [221]
4433 664400 1177 NN BBaallaannccee - PPaattrriimmoonniioo nneettoo yy ppaassiivvoo ((II)) - OOttrraass ddeeuuddaass aa llaarrggoo ppllaazzoo [[222222]]
44 657 17 N Balance - Patrimonio neto y pasivo (I) - Deudas con empresas del grupo y asociadas a largo plazo [223]
45 674 17 N Balance - Patrimonio neto y pasivo (I) - Pasivos por impuesto diferido [224]
46 691 17 N Balance - Patrimonio neto y pasivo (I) - Periodificaciones a largo plazo [225]
47 708 17 N Balance - Patrimonio neto y pasivo (I) - Acreedores comerciales no corrientes [226]
48 725 17 N Balance - Patrimonio neto y pasivo (I) - Deuda con características especiales a largo plazo [227]
49 742 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200005>"
Total: 751
Página 8

# Pag. 9

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "006"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN BBallance - PPattriimoniio netto y pasiivo ((IIII)) - PPasiivo corriientte [[222288]]
7 28 17 N Balance - Patrimonio neto y pasivo (II) - Pasivos vinculados con activos no corrientes [229]
8 45 17 N Balance - Patrimonio neto y pasivo (II) - Provisiones a corto plazo [230]
9 62 17 N Balance - Patrimonio neto y pasivo (II) - Deudas a corto plazo [231]
10 79 17 N Balance - Patrimonio neto y pasivo (II) - Obligaciones y otros valores negociables [232]
11 96 17 N Balance - Patrimonio neto y pasivo (II) - Deudas con entidades de crédito [233]
12 113 17 N Balance - Patrimonio neto y pasivo (II) - Acreedores por arrendamiento financiero [234]
13 130 17 N Balance - Patrimonio neto y pasivo (II) - Derivados [235]
14 147 17 N Balance - Patrimonio neto y pasivo (II) - Otros pasivos financieros [236]
15 164 17 N Balance - Patrimonio neto y pasivo (II) - Otras deudas a corto plazo [237]
16 181 17 N Balance - Patrimonio neto y pasivo (II) - Deudas con empresas del grupo y asociadas a corto plazo [238]
17 198 17 N Balance - Patrimonio neto y pasivo (II) - Acreedores comerciales y otras cuentas a pagar [239]
1188 221155 1177 NN BBaallaannccee -- PPaattrriimmoonniioo nneettoo yy ppaassiivvoo ((IIII)) -- PPrroovveeeeddoorreess [[224400]]
19 232 17 N Balance - Patrimonio neto y pasivo (II) - Proveedores a largo plazo [241]
20 249 17 N Balance - Patrimonio neto y pasivo (II) - Proveedores a corto plazo [242]
21 266 17 N Balance - Patrimonio neto y pasivo (II) - Proveedores, empresas del grupo y asociadas [243]
22 283 17 N Balance - Patrimonio neto y pasivo (II) - Acreedores varios [244]
23 300 17 N Balance - Patrimonio neto y pasivo (II) - Personal (remuneraciones pendientes de pago) [245]
24 317 17 N Balance - Patrimonio neto y pasivo (II) - Pasivos por impuesto corriente [246]
25 334 17 N Balance - Patrimonio neto y pasivo (II) - Otras deudas con las Administraciones Públicas [247]
26 351 17 N Balance - Patrimonio neto y pasivo (II) - Anticipos de clientes [248]
27 368 17 N Balance - Patrimonio neto y pasivo (II) - Otros acreedores [249]
28 385 17 N Balance - Patrimonio neto y pasivo (II) - Periodificaciones a corto plazo [250]
29 402 17 N Balance - Patrimonio neto y pasivo (II) - Deuda con características especiales a corto plazo [251]
30 419 17 N Balance - Patrimonio neto y pasivo (II) - Total patrimonio neto y pasivo [252]
31 436 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200006>"
Total: 445
Página 9

# Pag. 10

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "007"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN CCuentta dde péérddiiddas y gananciias ((II)) - IImportte netto dde lla ciiffra dde negociios [[225555]]
7 28 17 N Cuenta de pérdidas y ganancias (I) - Ventas [256]
8 45 17 N Cuenta de pérdidas y ganancias (I) - Prestaciones de servicios [257]
9 62 17 N Cuenta de pérdidas y ganancias (I) - Variación de existencias [258]
10 79 17 N Cuenta de pérdidas y ganancias (I) - Trabajos realizados por la empresa para su activo [259]
11 96 17 N Cuenta de pérdidas y ganancias (I) - Aprovisionamientos [260]
12 113 17 N Cuenta de pérdidas y ganancias (I) - Consumo de mercaderías [261]
13 130 17 N Cuenta de pérdidas y ganancias (I) - Consumo de materias primas y otras materias consumibles [262]
14 147 17 N Cuenta de pérdidas y ganancias (I) - Trabajos realizados por otras empresas [263]
15 164 17 N Cuenta de pérdidas y ganancias (I) - Deterioro de mercaderías, materias primas [264]
16 181 17 N Cuenta de pérdidas y ganancias (I) - Otros ingresos de explotación [265]
17 198 17 N Cuenta de pérdidas y ganancias (I) - Ingresos accesorios y otros de gestión corriente [266]
1188 221155 1177 NN CCuueennttaa ddee ppéérrddiiddaass yy ggaannaanncciiaass ((II)) -- IInnggrreessooss ppoorr aarrrreennddaammiieennttooss [[226677]]
19 232 17 N Cuenta de pérdidas y ganancias (I) - Resto [268]
20 249 17 N Cuenta de pérdidas y ganancias (I) - Subvenciones de explotación [269]
21 266 17 N Cuenta de pérdidas y ganancias (I) - Gastos de personal [270]
22 283 17 N Cuenta de pérdidas y ganancias (I) - Sueldos, salarios y asimilados [271]
23 300 17 N Cuenta de pérdidas y ganancias (I) - Indemnizaciones [273]
24 317 17 N Cuenta de pérdidas y ganancias (I) - Seguridad Social a cargo de la empresa [274]
25 334 17 N Cuenta de pérdidas y ganancias (I) - Retribuciones a largo plazo [275]
26 351 17 N Cuenta de pérdidas y ganancias (I) - Retribuciones mediante instrumentos de patrimonio [276]
27 368 17 N Cuenta de pérdidas y ganancias (I) - Otros gastos sociales [277]
28 385 17 N Cuenta de pérdidas y ganancias (I) - Provisiones [278]
29 402 17 N Cuenta de pérdidas y ganancias (I) - Otros gastos de explotación [279]
30 419 17 N Cuenta de pérdidas y ganancias (I) - Servicios exteriores [280]
31 436 17 N Cuenta de pérdidas y ganancias (I) - Tributos [281]
32 453 17 N Cuenta de pérdidas y ganancias (I) - Pérdidas, deterioro y variación de provisiones por operac.comerc. [282]
33 470 17 N Cuenta de pérdidas y ganancias (I) - Otros gastos de gestión corriente [283]
34 487 17 N Cuenta de pérdidas y ganancias (I) - Amortización del inmovilizado [284]
35 504 17 N Cuenta de pérdidas y ganancias (I) - Imputación de subvenciones de inmovilizado no financiero y otras [285]
36 521 17 N Cuenta de pérdidas y ganancias (I) - Excesos de provisiones [286]
37 538 17 N Cuenta de pérdidas y ganancias (I) - Deterioro y resultado por enajenaciones del inmovilizado [287]
38 555 17 N Cuenta de pérdidas y ganancias (I) - Deterioro y pérdidas [288]
39 572 17 N Cuenta de pérdidas y ganancias (I) - Deterioros [289]
40 589 17 N Cuenta de pérdidas y ganancias (I) - Reversión de deterioros [290]
41 606 17 N Cuenta de pérdidas y ganancias (I) - Resultados por enajenaciones y otras [291]
42 623 17 N Cuenta de pérdidas y ganancias (I) - Beneficios [292]
4433 664400 1177 NN CCuueennttaa ddee ppéérrddiiddaass yy ggaannaanncciiaass ((II)) - PPéérrddiiddaass [[229933]]
44 657 17 N Cuenta de pérdidas y ganancias (I) - Diferencia negativa de combinaciones de negocio [294]
45 674 17 N Cuenta de pérdidas y ganancias (I) - Otros resultados [295]
46 691 17 N Cuenta de pérdidas y ganancias (I) - Resultado de explotación [296]
47 708 17 N Cuenta de pérdidas y ganancias (I) - Ingresos financieros [297]
48 725 17 N Cuenta de pérdidas y ganancias (I) - De participaciones en instrumentos de patrimonio [298]
49 742 17 N Cuenta de pérdidas y ganancias (I) - En empresas del grupo y asociadas [299]
50 759 17 N Cuenta de pérdidas y ganancias (I) - En terceros [300]
51 776 17 N Cuenta de pérdidas y ganancias (I) - De valores negociables y otros instrumentos financieros [301]
52 793 17 N Cuenta de pérdidas y ganancias (I) - De empresas del grupo y asociadas [302]
53 810 17 N Cuenta de pérdidas y ganancias (I) - De terceros [303]
54 827 17 N Cuenta de pérdidas y ganancias (I) - Imputación de subvenciones, donaciones y legados [304]
5555 884444 1100 AAnn IIddeennttiiffiiccaaddoorr ddee ffiinn ddee rreeggiissttrroo OOBBLLIIGGAATTOORRIIOO CCoonnssttaannttee "<//TT220000000077>"
Total: 853
Página 10

# Pag. 11

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "008"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN CCuentta dde péérddiiddas y gananciias ((IIII)) - GGasttos ffiinanciieros [[330055]]
7 28 17 N Cuenta de pérdidas y ganancias (II) - Por deudas con empresas del grupo y asociadas [306]
8 45 17 N Cuenta de pérdidas y ganancias (II) - Por deudas con terceros [307]
9 62 17 N Cuenta de pérdidas y ganancias (II) - Por actualización de provisiones [308]
10 79 17 N Cuenta de pérdidas y ganancias (II) - Variación de valor razonable en instrumentos financieros [309]
11 96 17 N Cuenta de pérdidas y ganancias (II) - Cartera de negociación y otros [310]
12 113 17 N Cuenta de pérdidas y ganancias (II) - Imputación por activos financieros disponibles para la venta [311]
13 130 17 N Cuenta de pérdidas y ganancias (II) - Diferencias de cambio [312]
14 147 17 N Cuenta de pérdidas y ganancias (II) - Deterioro y resultado por enajenaciones de instrumentos financieros [313]
15 164 17 N Cuenta de pérdidas y ganancias (II) - Deterioros y pérdidas [314]
16 181 17 N Cuenta de pérdidas y ganancias (II) - Deterioros, empresas del grupo y asociadas a largo plazo [315]
17 198 17 N Cuenta de pérdidas y ganancias (II) - Deterioros, otras empresas [316]
1188 221155 1177 NN CCuueennttaa ddee ppéérrddiiddaass yy ggaannaanncciiaass ((IIII)) -- RReevveerrssiióónn ddee ddeetteerriioorrooss,, eemmpprreessaass ddeell ggrruuppoo yy aassoocciiaaddaass aa llaarrggoo ppllaazzoo [[331177]]
19 232 17 N Cuenta de pérdidas y ganancias (II) - Reversión de deterioros, otras empresas [318]
20 249 17 N Cuenta de pérdidas y ganancias (II) - Resultados por enajenaciones y otras [319]
21 266 17 N Cuenta de pérdidas y ganancias (II) - Beneficios, empresas del grupo y asociadas a largo plazo [320]
22 283 17 N Cuenta de pérdidas y ganancias (II) - Beneficios, otras empresas [321]
23 300 17 N Cuenta de pérdidas y ganancias (II) - Pérdidas, empresas del grupo y asociadas a largo plazo [322]
24 317 17 N Cuenta de pérdidas y ganancias (II) - Pérdidas, otras empresas [323]
25 334 17 N Cuenta de pérdidas y ganancias (II) - Otros ingresos y gastos de carácter financiero [329]
26 351 17 N Cuenta de pérdidas y ganancias (II) - Incorporación al activo de gastos financieros [330]
27 368 17 N Cuenta de pérdidas y ganancias (II) - Ingresos financieros derivados de convenios de acreedores [331]
28 385 17 N Cuenta de pérdidas y ganancias (II) - Resto de ingresos y gastos [332]
29 402 17 N Cuenta de pérdidas y ganancias (II) - Resultado financiero [324]
30 419 17 N Cuenta de pérdidas y ganancias (II) - Resultado antes de impuestos [325]
31 436 17 N Cuenta de pérdidas y ganancias (II) - Impuestos sobre beneficios [326]
32 453 17 N Cuenta de pérdidas y ganancias (II) - Resultado del ejercicio procedente de operaciones continuadas [327]
33 470 17 N Cuenta de pérdidas y ganancias (II) - Resultado del ejercicio procedente de operaciones interrumpidas neto de impuestos [328]
34 487 17 N Cuenta de pérdidas y ganancias (II) - Resultado de la cuenta de pérdidas y ganancias [500]
35 504 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200008>"
Total: 513
Página 11

# Pag. 12

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "009"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN EEsttaddo dde cambbiios pattriimoniio netto - RResullttaddo dde lla cuentta dde péérddiiddas y gananciias [[550000]]
7 28 17 N Estado de cambios patrimonio neto - Ingresos y gastos - Por valoración de instrumentos financieros [336]
8 45 17 N Estado de cambios patrimonio neto - Ingresos y gastos - Activos financieros disponibles para la venta [337]
9 62 17 N Estado de cambios patrimonio neto - Ingresos y gastos - Otros ingresos/gastos [338]
10 79 17 N Estado de cambios patrimonio neto - Ingresos y gastos - Por coberturas de flujos de efectivo [339]
11 96 17 N Estado de cambios patrimonio neto - Ingresos y gastos - Subvenciones, donaciones y legados recibidos [340]
12 113 17 N Estado de cambios patrimonio neto - Ingresos y gastos - Por ganancias y pérdidas actuariales [341]
13 130 17 N Estado de cambios patrimonio neto - Ingresos y gastos - Por activos no corrientes y pasivos vinculados [342]
14 147 17 N Estado de cambios patrimonio neto - Ingresos y gastos - Diferencias de conversión [343]
15 164 17 N Estado de cambios patrimonio neto - Ingresos y gastos - Efecto impositivo [344]
16 181 17 N Estado de cambios patrimonio neto - Ingresos y gastos - Total ingresos y gastos imputados al patrimonio neto [345]
17 198 17 N Estado de cambios patrimonio neto - Transf.pérdidas y ganancias - Por valoración de instrumentos financieros [346]
1188 221155 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo -- TTrraannssff..ppéérrddiiddaass yy ggaannaanncciiaass -- AAccttiivvooss ffiinnaanncciieerrooss ddiissppoonniibblleess ppaarraa llaa vveennttaa [[334477]]
19 232 17 N Estado de cambios patrimonio neto - Transf.pérdidas y ganancias - Otros ingresos/gastos [348]
20 249 17 N Estado de cambios patrimonio neto - Transf.pérdidas y ganancias - Por coberturas de flujos de efectivo [349]
21 266 17 N Estado de cambios patrimonio neto - Transf.pérdidas y ganancias - Subvenciones, donaciones y legados recibidos [350]
22 283 17 N Estado de cambios patrimonio neto - Transf.pérdidas y ganancias - Por activos no corrientes y pasivos vinculados [351]
23 300 17 N Estado de cambios patrimonio neto - Transf.pérdidas y ganancias - Diferencias de conversión [352]
24 317 17 N Estado de cambios patrimonio neto - Transf.pérdidas y ganancias - Efecto impositivo [353]
25 334 17 N Estado de cambios patrimonio neto - Transf.pérdidas y ganancias - Total transferencia a la cuenta de pérdidas y ganancias [354]
26 351 17 N Estado de cambios patrimonio neto - Transf.pérdidas y ganancias - Total de ingresos y gastos reconocidos [355]
27 368 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200009>"
Total: 377
Página 12

# Pag. 13

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "010"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN EEsttaddo dde cambbiios pattriimoniio netto - SSallddo ffiinall ddell ejjerciiciio antteriior - EEscriitturaddo [[338800]]
7 28 17 N Estado de cambios patrimonio neto - Saldo final del ejercicio anterior - No exigido [381]
8 45 17 N Estado de cambios patrimonio neto - Saldo final del ejercicio anterior - Prima de emisión [382]
9 62 17 N Estado de cambios patrimonio neto - Saldo final del ejercicio anterior - Reservas [383]
10 79 17 N Estado de cambios patrimonio neto - Saldo final del ejercicio anterior - Acciones y participaciones propias [384]
11 96 17 N Estado de cambios patrimonio neto - Saldo final del ejercicio anterior - Resultados ejercicios anteriores [385]
12 113 17 N Estado de cambios patrimonio neto - Saldo final del ejercicio anterior - Otras aportaciones socios [386]
13 130 17 N Estado de cambios patrimonio neto - Ajustes por cambio de criterio de ejercicios anteriores - Escriturado [394]
14 147 17 N Estado de cambios patrimonio neto - Ajustes por cambio de criterio de ejercicios anteriores - No exigido [395]
15 164 17 N Estado de cambios patrimonio neto - Ajustes por cambio de criterio de ejercicios anteriores - Prima de emisión [396]
16 181 17 N Estado de cambios patrimonio neto - Ajustes por cambio de criterio de ejercicios anteriores - Reservas [397]
17 198 17 N Estado de cambios patrimonio neto - Ajustes por cambio de criterio de ejercicios anteriores - Acciones y participaciones propias [398]
1188 221155 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo -- AAjjuusstteess ppoorr ccaammbbiioo ddee ccrriitteerriioo ddee eejjeerrcciicciiooss aanntteerriioorreess -- RReessuullttaaddooss eejjeerrcciicciiooss aanntteerriioorreess [[339999]]
19 232 17 N Estado de cambios patrimonio neto - Ajustes por cambio de criterio de ejercicios anteriores - Otras aportaciones socios [400]
20 249 17 N Estado de cambios patrimonio neto - Ajustes por errores de ejercicios anteriores - Escriturado [408]
21 266 17 N Estado de cambios patrimonio neto - Ajustes por errores de ejercicios anteriores - No exigido [409]
22 283 17 N Estado de cambios patrimonio neto - Ajustes por errores de ejercicios anteriores - Prima de emisión [410]
23 300 17 N Estado de cambios patrimonio neto - Ajustes por errores de ejercicios anteriores - Reservas [411]
24 317 17 N Estado de cambios patrimonio neto - Ajustes por errores de ejercicios anteriores - Acciones y participaciones propias [412]
25 334 17 N Estado de cambios patrimonio neto - Ajustes por errores de ejercicios anteriores - Resultados ejercicios anteriores [413]
26 351 17 N Estado de cambios patrimonio neto - Ajustes por errores de ejercicios anteriores - Otras aportaciones socios [414]
27 368 17 N Estado de cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Escriturado [422]
28 385 17 N Estado de cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - No exigido [423]
29 402 17 N Estado de cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Prima de emisión [424]
30 419 17 N Estado de cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Reservas [425]
31 436 17 N Estado de cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Acciones y participaciones propias [426]
32 453 17 N Estado de cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Resultados ejercicios anteriores [427]
33 470 17 N Estado de cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Otras aportaciones socios [428]
34 487 17 N Estado de cambios patrimonio neto - Total ingresos y gastos reconocidos - Escriturado [436]
35 504 17 N Estado de cambios patrimonio neto - Total ingresos y gastos reconocidos - No exigido [437]
36 521 17 N Estado de cambios patrimonio neto - Total ingresos y gastos reconocidos - Prima de emisión [438]
37 538 17 N Estado de cambios patrimonio neto - Total ingresos y gastos reconocidos - Reservas [439]
38 555 17 N Estado de cambios patrimonio neto - Total ingresos y gastos reconocidos - Acciones y participaciones propias [440]
39 572 17 N Estado de cambios patrimonio neto - Total ingresos y gastos reconocidos - Resultados ejercicios anteriores [441]
40 589 17 N Estado de cambios patrimonio neto - Total ingresos y gastos reconocidos - Otras aportaciones socios [442]
41 606 17 N Estado de cambios patrimonio neto - Resultado cuenta pérdidas y ganancias - Escriturado [450]
42 623 17 N Estado de cambios patrimonio neto - Resultado cuenta pérdidas y ganancias - No exigido [451]
4433 664400 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo - RReessuullttaaddoo ccuueennttaa ppéérrddiiddaass yy ggaannaanncciiaass - PPrriimmaa ddee eemmiissiióónn [[445522]]
44 657 17 N Estado de cambios patrimonio neto - Resultado cuenta pérdidas y ganancias - Reservas [453]
45 674 17 N Estado de cambios patrimonio neto - Resultado cuenta pérdidas y ganancias - Acciones y participaciones propias [454]
46 691 17 N Estado de cambios patrimonio neto - Resultado cuenta pérdidas y ganancias - Resultados ejercicios anteriores [455]
47 708 17 N Estado de cambios patrimonio neto - Resultado cuenta pérdidas y ganancias - Otras aportaciones socios [456]
48 725 17 N Estado de cambios patrimonio neto - Ingresos y gastos reconocidos en patrimonio neto - Escriturado [464]
49 742 17 N Estado de cambios patrimonio neto - Ingresos y gastos reconocidos en patrimonio neto - No exigido [465]
50 759 17 N Estado de cambios patrimonio neto - Ingresos y gastos reconocidos en patrimonio neto - Prima de emisión [466]
51 776 17 N Estado de cambios patrimonio neto - Ingresos y gastos reconocidos en patrimonio neto - Reservas [467]
52 793 17 N Estado de cambios patrimonio neto - Ingresos y gastos reconocidos en patrimonio neto - Acciones y participaciones propias [468]
53 810 17 N Estado de cambios patrimonio neto - Ingresos y gastos reconocidos en patrimonio neto - Resultados ejercicios anteriores [469]
54 827 17 N Estado de cambios patrimonio neto - Ingresos y gastos reconocidos en patrimonio neto - Otras aportaciones socios [470]
5555 884444 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo - IInnggrreessooss ffiissccaalleess aa ddiissttrriibbuuiirr eenn vvaarriiooss eejjeerrcciicciiooss - EEssccrriittuurraaddoo [[447788]]
56 861 17 N Estado de cambios patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - No exigido [479]
57 878 17 N Estado de cambios patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Prima de emisión [480]
58 895 17 N Estado de cambios patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Reservas [481]
59 912 17 N Estado de cambios patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Acciones y participaciones propias [482]
60 929 17 N Estado de cambios patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Resultados ejercicios anteriores [483]
61 946 17 N Estado de cambios patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Otras aportaciones socios [484]
62 963 17 N Estado de cambios patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Escriturado [492]
63 980 17 N Estado de cambios patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - No exigido [493]
64 997 17 N Estado de cambios patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Prima de emisión [494]
65 1014 17 N Estado de cambios patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Reservas [495]
66 1031 17 N Estado de cambios patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Acciones y participaciones propias [496]
67 1048 17 N Estado de cambios patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Resultados ejercicios anteriores [497]
6688 11006655 1177 NN EEsttaddo dde cambbiios pattriimoniio netto - OOttros iingresos y gasttos reconociiddos en pattriimoniio netto - OOttras aporttaciiones sociios [[449988]]
69 1082 17 N Estado de cambios patrimonio neto - Operaciones con socios o propietarios - Escriturado [506]
70 1099 17 N Estado de cambios patrimonio neto - Operaciones con socios o propietarios - No exigido [507]
71 1116 17 N Estado de cambios patrimonio neto - Operaciones con socios o propietarios - Prima de emisión [508]
72 1133 17 N Estado de cambios patrimonio neto - Operaciones con socios o propietarios - Reservas [509]
73 1150 17 N Estado de cambios patrimonio neto - Operaciones con socios o propietarios - Acciones y participaciones propias [510]
74 1167 17 N Estado de cambios patrimonio neto - Operaciones con socios o propietarios - Resultados ejercicios anteriores [511]
75 1184 17 N Estado de cambios patrimonio neto - Operaciones con socios o propietarios - Otras aportaciones socios [512]
76 1201 17 N Estado de cambios patrimonio neto - Aumentos de capital - Escriturado [520]
77 1218 17 N Estado de cambios patrimonio neto - Aumentos de capital - No exigido [521]
78 1235 17 N Estado de cambios patrimonio neto - Aumentos de capital - Prima de emisión [522]
79 1252 17 N Estado de cambios patrimonio neto - Aumentos de capital - Reservas [523]
8800 11226699 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo -- AAuummeennttooss ddee ccaappiittaall -- AAcccciioonneess yy ppaarrttiicciippaacciioonneess pprrooppiiaass [[552244]]
81 1286 17 N Estado de cambios patrimonio neto - Aumentos de capital - Resultados ejercicios anteriores [525]
82 1303 17 N Estado de cambios patrimonio neto - Aumentos de capital - Otras aportaciones socios [526]
83 1320 17 N Estado de cambios patrimonio neto - Reducciones de capital - Escriturado [534]
Página 13

# Pag. 14

84 1337 17 N Estado de cambios patrimonio neto - Reducciones de capital - No exigido [535]
85 1354 17 N Estado de cambios patrimonio neto - Reducciones de capital - Prima de emisión [536]
86 1371 17 N Estado de cambios patrimonio neto - Reducciones de capital - Reservas [537]
87 1388 17 N Estado de cambios patrimonio neto - Reducciones de capital - Acciones y participaciones propias [538]
88 1405 17 N Estado de cambios patrimonio neto - Reducciones de capital - Resultados ejercicios anteriores [539]
89 1422 17 N Estado de cambios patrimonio neto - Reducciones de capital - Otras aportaciones socios [540]
90 1439 17 N Estado de cambios patrimonio neto - Conversión de pasivos - Escriturado [548]
91 1456 17 N Estado de cambios patrimonio neto - Conversión de pasivos - No exigido [549]
92 1473 17 N Estado de cambios patrimonio neto - Conversión de pasivos - Prima de emisión [550]
93 1490 17 N Estado de cambios patrimonio neto - Conversión de pasivos - Reservas [551]
94 1507 17 N Estado de cambios patrimonio neto - Conversión de pasivos - Acciones y participaciones propias [552]
95 1524 17 N Estado de cambios patrimonio neto - Conversión de pasivos - Resultados ejercicios anteriores [553]
9966 11554411 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo - CCoonnvveerrssiióónn ddee ppaassiivvooss - OOttrraass aappoorrttaacciioonneess ssoocciiooss [[555544]]
97 1558 17 N Estado de cambios patrimonio neto - Distribución de dividendos - Escriturado [562]
98 1575 17 N Estado de cambios patrimonio neto - Distribución de dividendos - No exigido [563]
99 1592 17 N Estado de cambios patrimonio neto - Distribución de dividendos - Prima de emisión [564]
100 1609 17 N Estado de cambios patrimonio neto - Distribución de dividendos - Reservas [565]
101 1626 17 N Estado de cambios patrimonio neto - Distribución de dividendos - Acciones y participaciones propias [566]
102 1643 17 N Estado de cambios patrimonio neto - Distribución de dividendos - Resultados ejercicios anteriores [567]
103 1660 17 N Estado de cambios patrimonio neto - Distribución de dividendos - Otras aportaciones socios [568]
104 1677 17 N Estado de cambios patrimonio neto - Operaciones con acciones o participaciones propias - Escriturado [576]
105 1694 17 N Estado de cambios patrimonio neto - Operaciones con acciones o participaciones propias - No exigido [577]
106 1711 17 N Estado de cambios patrimonio neto - Operaciones con acciones o participaciones propias - Prima de emisión [578]
107 1728 17 N Estado de cambios patrimonio neto - Operaciones con acciones o participaciones propias - Reservas [579]
110088 11774455 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo - OOppeerraacciioonneess ccoonn aacccciioonneess oo ppaarrttiicciippaacciioonneess pprrooppiiaass - AAcccciioonneess yy ppaarrttiicciippaacciioonneess pprrooppiiaass [[558800]]
109 1762 17 N Estado de cambios patrimonio neto - Operaciones con acciones o participaciones propias - Resultados ejercicios anteriores [581]
110 1779 17 N Estado de cambios patrimonio neto - Operaciones con acciones o participaciones propias - Otras aportaciones socios [582]
111 1796 17 N Estado de cambios patrimonio neto - Incremento (reducción) de patr.neto - Escriturado [590]
112 1813 17 N Estado de cambios patrimonio neto - Incremento (reducción) de patr.neto - No exigido [591]
113 1830 17 N Estado de cambios patrimonio neto - Incremento (reducción) de patr.neto - Prima de emisión [592]
114 1847 17 N Estado de cambios patrimonio neto - Incremento (reducción) de patr.neto - Reservas [593]
115 1864 17 N Estado de cambios patrimonio neto - Incremento (reducción) de patr.neto - Acciones y participaciones propias [594]
116 1881 17 N Estado de cambios patrimonio neto - Incremento (reducción) de patr.neto - Resultados ejercicios anteriores [595]
117 1898 17 N Estado de cambios patrimonio neto - Incremento (reducción) de patr.neto - Otras aportaciones socios [596]
118 1915 17 N Estado de cambios patrimonio neto - Otras operaciones con socios o propietarios - Escriturado [604]
119 1932 17 N Estado de cambios patrimonio neto - Otras operaciones con socios o propietarios - No exigido [605]
120 1949 17 N Estado de cambios patrimonio neto - Otras operaciones con socios o propietarios - Prima de emisión [606]
121 1966 17 N Estado de cambios patrimonio neto - Otras operaciones con socios o propietarios - Reservas [607]
122 1983 17 N Estado de cambios patrimonio neto - Otras operaciones con socios o propietarios - Acciones y participaciones propias [608]
123 2000 17 N Estado de cambios patrimonio neto - Otras operaciones con socios o propietarios - Resultados ejercicios anteriores [609]
124 2017 17 N Estado de cambios patrimonio neto - Otras operaciones con socios o propietarios - Otras aportaciones socios [610]
125 2034 17 N Estado de cambios patrimonio neto - Otras variaciones del patrimonio neto - Escriturado [618]
126 2051 17 N Estado de cambios patrimonio neto - Otras variaciones del patrimonio neto - No exigido [619]
127 2068 17 N Estado de cambios patrimonio neto - Otras variaciones del patrimonio neto - Prima de emisión [620]
128 2085 17 N Estado de cambios patrimonio neto - Otras variaciones del patrimonio neto - Reservas [621]
129 2102 17 N Estado de cambios patrimonio neto - Otras variaciones del patrimonio neto - Acciones y participaciones propias [622]
130 2119 17 N Estado de cambios patrimonio neto - Otras variaciones del patrimonio neto - Resultados ejercicios anteriores [623]
131 2136 17 N Estado de cambios patrimonio neto - Otras variaciones del patrimonio neto - Otras aportaciones socios [624]
132 2153 17 N Estado de cambios patrimonio neto - Saldo, final ejercicio - Escriturado [632]
113333 22117700 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo -- SSaallddoo, ffiinnaall eejjeerrcciicciioo -- NNoo eexxiiggiiddoo [[663333]]
134 2187 17 N Estado de cambios patrimonio neto - Saldo, final ejercicio - Prima de emisión [634]
135 2204 17 N Estado de cambios patrimonio neto - Saldo, final ejercicio - Reservas [635]
136 2221 17 N Estado de cambios patrimonio neto - Saldo, final ejercicio - Acciones y participaciones propias [636]
137 2238 17 N Estado de cambios patrimonio neto - Saldo, final ejercicio - Resultados ejercicios anteriores [637]
138 2255 17 N Estado de cambios patrimonio neto - Saldo, final ejercicio - Otras aportaciones socios [638]
139 2272 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200010>"
Total: 2281
Página 14

# Pag. 15

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "011"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN EEsttaddo dde cambbiios pattriimoniio netto - SSallddo ffiinall ddell ejjerciiciio antteriior - RResullttaddo ddell ejjerciiciio [[338877]]
7 28 17 N Estado de cambios patrimonio neto - Saldo final del ejercicio anterior - Dividendo a cuenta [388]
8 45 17 N Estado de cambios patrimonio neto - Saldo final del ejercicio anterior - Otros instrumentos patrimonio neto [389]
9 62 17 N Estado de cambios patrimonio neto - Saldo final del ejercicio anterior - Ajustes por cambio de valor [390]
10 79 17 N Estado de cambios patrimonio neto - Saldo final del ejercicio anterior - Ajustes en patrimonio neto [391]
11 96 17 N Estado de cambios patrimonio neto - Saldo final del ejercicio anterior - Subvenciones, donaciones y legados recibidos [392]
12 113 17 N Estado de cambios patrimonio neto - Saldo final del ejercicio anterior - Total [393]
13 130 17 N Estado de cambios patrimonio neto - Ajustes por cambio de criterio de ejercicios anteriores - Resultado del ejercicio [401]
14 147 17 N Estado de cambios patrimonio neto - Ajustes por cambio de criterio de ejercicios anteriores - Dividendo a cuenta [402]
15 164 17 N Estado de cambios patrimonio neto - Ajustes por cambio de criterio de ejercicios anteriores - Otros instrumentos patrimonio neto [403]
16 181 17 N Estado de cambios patrimonio neto - Ajustes por cambio de criterio de ejercicios anteriores - Ajustes por cambio de valor [404]
17 198 17 N Estado de cambios patrimonio neto - Ajustes por cambio de criterio de ejercicios anteriores - Ajustes en patrimonio neto [405]
1188 221155 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo -- AAjjuusstteess ppoorr ccaammbbiioo ddee ccrriitteerriioo ddee eejjeerrcciicciiooss aanntteerriioorreess -- SSuubbvveenncciioonneess,, ddoonnaacciioonneess yy lleeggaaddooss rreecciibbiiddooss [[440066]]
19 232 17 N Estado de cambios patrimonio neto - Ajustes por cambio de criterio de ejercicios anteriores - Total [407]
20 249 17 N Estado de cambios patrimonio neto - Ajustes por errores de ejercicios anteriores - Resultado del ejercicio [415]
21 266 17 N Estado de cambios patrimonio neto - Ajustes por errores de ejercicios anteriores - Dividendo a cuenta [416]
22 283 17 N Estado de cambios patrimonio neto - Ajustes por errores de ejercicios anteriores - Otros instrumentos patrimonio neto [417]
23 300 17 N Estado de cambios patrimonio neto - Ajustes por errores de ejercicios anteriores - Ajustes por cambio de valor [418]
24 317 17 N Estado de cambios patrimonio neto - Ajustes por errores de ejercicios anteriores - Ajustes en patrimonio neto [419]
25 334 17 N Estado de cambios patrimonio neto - Ajustes por errores de ejercicios anteriores - Subvenciones, donaciones y legados recibidos [420]
26 351 17 N Estado de cambios patrimonio neto - Ajustes por errores de ejercicios anteriores - Total [421]
27 368 17 N Estado de cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Resultado del ejercicio [429]
28 385 17 N Estado de cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Dividendo a cuenta [430]
29 402 17 N Estado de cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Otros instrumentos patrimonio neto [431]
30 419 17 N Estado de cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Ajustes por cambio de valor [432]
31 436 17 N Estado de cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Ajustes en patrimonio neto [433]
32 453 17 N Estado de cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Subvenciones, donaciones y legados recibidos [434]
33 470 17 N Estado de cambios patrimonio neto - Saldo ajustado, inicio del ejercicio - Total [435]
34 487 17 N Estado de cambios patrimonio neto - Total ingresos y gastos reconocidos - Resultado del ejercicio [443]
35 504 17 N Estado de cambios patrimonio neto - Total ingresos y gastos reconocidos - Dividendo a cuenta [444]
36 521 17 N Estado de cambios patrimonio neto - Total ingresos y gastos reconocidos - Otros instrumentos patrimonio neto [445]
37 538 17 N Estado de cambios patrimonio neto - Total ingresos y gastos reconocidos - Ajustes por cambio de valor [446]
38 555 17 N Estado de cambios patrimonio neto - Total ingresos y gastos reconocidos - Subvenciones, donaciones y legados recibidos [448]
39 572 17 N Estado de cambios patrimonio neto - Total ingresos y gastos reconocidos - Total [449]
40 589 17 N Estado de cambios patrimonio neto - Resultado cuenta pérdidas y ganancias - Resultado del ejercicio [457]
41 606 17 N Estado de cambios patrimonio neto - Resultado cuenta pérdidas y ganancias - Dividendo a cuenta [458]
42 623 17 N Estado de cambios patrimonio neto - Resultado cuenta pérdidas y ganancias - Ajustes en patrimonio neto [461]
4433 664400 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo - RReessuullttaaddoo ccuueennttaa ppéérrddiiddaass yy ggaannaanncciiaass - SSuubbvveenncciioonneess, ddoonnaacciioonneess yy lleeggaaddooss rreecciibbiiddooss [[446622]]
44 657 17 N Estado de cambios patrimonio neto - Resultado cuenta pérdidas y ganancias - Total [463]
45 674 17 N Estado de cambios patrimonio neto - Ingresos y gastos reconocidos en patrimonio neto - Resultado del ejercicio [471]
46 691 17 N Estado de cambios patrimonio neto - Ingresos y gastos reconocidos en patrimonio neto - Dividendo a cuenta [472]
47 708 17 N Estado de cambios patrimonio neto - Ingresos y gastos reconocidos en patrimonio neto - Ajustes en patrimonio neto [475]
48 725 17 N Estado de cambios patrimonio neto - Ingresos y gastos reconocidos en patrimonio neto - Subvenciones, donaciones y legados recibidos [476]
49 742 17 N Estado de cambios patrimonio neto - Ingresos y gastos reconocidos en patrimonio neto - Total [477]
50 759 17 N Estado de cambios patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Resultado del ejercicio [485]
51 776 17 N Estado de cambios patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Dividendo a cuenta [486]
52 793 17 N Estado de cambios patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Ajustes en patrimonio neto [489]
53 810 17 N Estado de cambios patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Subvenciones, donaciones y legados recibidos [490]
54 827 17 N Estado de cambios patrimonio neto - Ingresos fiscales a distribuir en varios ejercicios - Total [491]
5555 884444 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo - OOttrrooss iinnggrreessooss yy ggaassttooss rreeccoonnoocciiddooss eenn ppaattrriimmoonniioo nneettoo - RReessuullttaaddoo ddeell eejjeerrcciicciioo [[449999]]
56 861 17 N Estado de cambios patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Dividendo a cuenta [502]
57 878 17 N Estado de cambios patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Ajustes en patrimonio neto [503]
58 895 17 N Estado de cambios patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Subvenciones, donaciones y legados recibidos [504]
59 912 17 N Estado de cambios patrimonio neto - Otros ingresos y gastos reconocidos en patrimonio neto - Total [505]
60 929 17 N Estado de cambios patrimonio neto - Operaciones con socios o propietarios - Resultado del ejercicio [513]
61 946 17 N Estado de cambios patrimonio neto - Operaciones con socios o propietarios - Dividendo a cuenta [514]
62 963 17 N Estado de cambios patrimonio neto - Operaciones con socios o propietarios - Otros instrumentos patrimonio neto [515]
63 980 17 N Estado de cambios patrimonio neto - Operaciones con socios o propietarios - Ajustes por cambio de valor [516]
64 997 17 N Estado de cambios patrimonio neto - Operaciones con socios o propietarios - Ajustes en patrimonio neto [517]
65 1014 17 N Estado de cambios patrimonio neto - Operaciones con socios o propietarios - Subvenciones, donaciones y legados recibidos [518]
66 1031 17 N Estado de cambios patrimonio neto - Operaciones con socios o propietarios - Total [519]
67 1048 17 N Estado de cambios patrimonio neto - Aumentos de capital - Resultado del ejercicio [527]
6688 11006655 1177 NN EEsttaddo dde cambbiios pattriimoniio netto - AAumenttos dde capiittall - DDiiviiddenddo a cuentta [[552288]]
69 1082 17 N Estado de cambios patrimonio neto - Aumentos de capital - Otros instrumentos patrimonio neto [529]
70 1099 17 N Estado de cambios patrimonio neto - Aumentos de capital - Ajustes por cambio de valor [530]
71 1116 17 N Estado de cambios patrimonio neto - Aumentos de capital - Ajustes en patrimonio neto [531]
72 1133 17 N Estado de cambios patrimonio neto - Aumentos de capital - Subvenciones, donaciones y legados recibidos [532]
73 1150 17 N Estado de cambios patrimonio neto - Aumentos de capital - Total [533]
74 1167 17 N Estado de cambios patrimonio neto - Reducciones de capital - Resultado del ejercicio [541]
75 1184 17 N Estado de cambios patrimonio neto - Reducciones de capital - Dividendo a cuenta [542]
76 1201 17 N Estado de cambios patrimonio neto - Reducciones de capital - Otros instrumentos patrimonio neto [543]
77 1218 17 N Estado de cambios patrimonio neto - Reducciones de capital - Ajustes por cambio de valor [544]
78 1235 17 N Estado de cambios patrimonio neto - Reducciones de capital - Ajustes en patrimonio neto [545]
79 1252 17 N Estado de cambios patrimonio neto - Reducciones de capital - Subvenciones, donaciones y legados recibidos [546]
8800 11226699 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo -- RReedduucccciioonneess ddee ccaappiittaall -- TToottaall [[554477]]
81 1286 17 N Estado de cambios patrimonio neto - Conversión de pasivos - Resultado del ejercicio [555]
82 1303 17 N Estado de cambios patrimonio neto - Conversión de pasivos - Dividendo a cuenta [556]
83 1320 17 N Estado de cambios patrimonio neto - Conversión de pasivos - Otros instrumentos patrimonio neto [557]
Página 15

# Pag. 16

84 1337 17 N Estado de cambios patrimonio neto - Conversión de pasivos - Ajustes por cambio de valor [558]
85 1354 17 N Estado de cambios patrimonio neto - Conversión de pasivos - Subvenciones, donaciones y legados recibidos [560]
86 1371 17 N Estado de cambios patrimonio neto - Conversión de pasivos - Total [561]
87 1388 17 N Estado de cambios patrimonio neto - Distribución de dividendos - Resultado del ejercicio [569]
88 1405 17 N Estado de cambios patrimonio neto - Distribución de dividendos - Dividendo a cuenta [570]
89 1422 17 N Estado de cambios patrimonio neto - Distribución de dividendos - Otros instrumentos patrimonio neto [571]
90 1439 17 N Estado de cambios patrimonio neto - Distribución de dividendos - Ajustes por cambio de valor [572]
91 1456 17 N Estado de cambios patrimonio neto - Distribución de dividendos - Subvenciones, donaciones y legados recibidos [574]
92 1473 17 N Estado de cambios patrimonio neto - Distribución de dividendos - Total [575]
93 1490 17 N Estado de cambios patrimonio neto - Operaciones con acciones o participaciones propias - Resultado del ejercicio [583]
94 1507 17 N Estado de cambios patrimonio neto - Operaciones con acciones o participaciones propias - Dividendo a cuenta [584]
95 1524 17 N Estado de cambios patrimonio neto - Operaciones con acciones o participaciones propias - Otros instrumentos patrimonio neto [585]
9966 11554411 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo - OOppeerraacciioonneess ccoonn aacccciioonneess oo ppaarrttiicciippaacciioonneess pprrooppiiaass - AAjjuusstteess ppoorr ccaammbbiioo ddee vvaalloorr [[558866]]
97 1558 17 N Estado de cambios patrimonio neto - Operaciones con acciones o participaciones propias - Subvenciones, donaciones y legados recibidos [588]
98 1575 17 N Estado de cambios patrimonio neto - Operaciones con acciones o participaciones propias - Total [589]
99 1592 17 N Estado de cambios patrimonio neto - Incremento (reducción) de patr.neto - Resultado del ejercicio [597]
100 1609 17 N Estado de cambios patrimonio neto - Incremento (reducción) de patr.neto - Dividendo a cuenta [598]
101 1626 17 N Estado de cambios patrimonio neto - Incremento (reducción) de patr.neto - Otros instrumentos patrimonio neto [599]
102 1643 17 N Estado de cambios patrimonio neto - Incremento (reducción) de patr.neto - Ajustes por cambio de valor [600]
103 1660 17 N Estado de cambios patrimonio neto - Incremento (reducción) de patr.neto - Subvenciones, donaciones y legados recibidos [602]
104 1677 17 N Estado de cambios patrimonio neto - Incremento (reducción) de patr.neto - Total [603]
105 1694 17 N Estado de cambios patrimonio neto - Otras operaciones con socios o propietarios - Resultado del ejercicio [611]
106 1711 17 N Estado de cambios patrimonio neto - Otras operaciones con socios o propietarios - Dividendo a cuenta [612]
107 1728 17 N Estado de cambios patrimonio neto - Otras operaciones con socios o propietarios - Otros instrumentos patrimonio neto [ [613]
110088 11774455 1177 NN EEssttaaddoo ddee ccaammbbiiooss ppaattrriimmoonniioo nneettoo - OOttrraass ooppeerraacciioonneess ccoonn ssoocciiooss oo pprrooppiieettaarriiooss - AAjjuusstteess ppoorr ccaammbbiioo ddee vvaalloorr [[661144]]
109 1762 17 N Estado de cambios patrimonio neto - Otras operaciones con socios o propietarios - Ajustes en patrimonio neto [615]
110 1779 17 N Estado de cambios patrimonio neto - Otras operaciones con socios o propietarios - Subvenciones, donaciones y legados recibidos [616]
111 1796 17 N Estado de cambios patrimonio neto - Otras operaciones con socios o propietarios - Total [617]
112 1813 17 N Estado de cambios patrimonio neto - Otras variaciones del patrimonio neto - Resultado del ejercicio [625]
113 1830 17 N Estado de cambios patrimonio neto - Otras variaciones del patrimonio neto - Dividendo a cuenta [626]
114 1847 17 N Estado de cambios patrimonio neto - Otras variaciones del patrimonio neto - Otros instrumentos patrimonio neto [ [627]
115 1864 17 N Estado de cambios patrimonio neto - Otras variaciones del patrimonio neto - Ajustes por cambio de valor [628]
116 1881 17 N Estado de cambios patrimonio neto - Otras variaciones del patrimonio neto - Ajustes en patrimonio neto [629]
117 1898 17 N Estado de cambios patrimonio neto - Otras variaciones del patrimonio neto - Subvenciones, donaciones y legados recibidos [630]
118 1915 17 N Estado de cambios patrimonio neto - Otras variaciones del patrimonio neto - Total [631]
119 1932 17 N Estado de cambios patrimonio neto - Saldo, final ejercicio - Resultado del ejercicio [639]
120 1949 17 N Estado de cambios patrimonio neto - Saldo, final ejercicio - Dividendo a cuenta [640]
121 1966 17 N Estado de cambios patrimonio neto - Saldo, final ejercicio - Otros instrumentos patrimonio neto [641]
122 1983 17 N Estado de cambios patrimonio neto - Saldo, final ejercicio - Ajustes por cambio de valor [642]
123 2000 17 N Estado de cambios patrimonio neto - Saldo, final ejercicio - Ajustes en patrimonio neto [643]
124 2017 17 N Estado de cambios patrimonio neto - Saldo, final ejercicio - Subvenciones, donaciones y legados recibidos [644]
125 2034 17 N Estado de cambios patrimonio neto - Saldo, final ejercicio - Total [645]
126 2051 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200011>"
Total: 2060
Página 16

# Pag. 17

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "012"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NN LLiiquiiddaciióón II - CCuentta péérddiiddas y gananciias - RResullttaddo dde lla cuentta dde péérddiiddas y gananciias [[550000]]
7 28 17 N Liquidación I - Cuenta pérdidas y ganancias - Correcciones por Impuesto Sociedades. Aumentos [301]
8 45 17 N Liquidación I - Cuenta pérdidas y ganancias - Correcciones por Impuesto Sociedades. Disminuciones [302]
9 62 17 N Liquidación I - Cuenta pérdidas y ganancias - Resultado cuenta pérdidas y ganancias antes de Impuesto Sociedades [501]
10 79 17 Num Liquidación I - Detalle correcciones - Diferencias entre amortización contable y fiscal. Aumentos [303]
11 96 17 Num Liquidación I - Detalle correcciones - Diferencias entre amortización contable y fiscal. Disminuciones [304]
12 113 17 Num Liquidación I - Detalle correcciones - Amortización inmovilizado. Aumentos [305]
13 130 17 Num Liquidación I - Detalle correcciones - Amortización inmovilizado. Disminuciones [306]
14 147 17 Num Liquidación I - Detalle correcciones - Libertad de amortización de gastos de investigación y desarrollo. Aumentos [307]
15 164 17 Num Liquidación I - Detalle correcciones - Libertad de amortización de gastos de investigación y desarrollo. Disminuciones [308]
16 181 17 Num Liquidación I - Detalle correcciones - Otros supuestos de libertad de amortización. Aumentos [309]
17 198 17 Num Liquidación I - Detalle correcciones - Otros supuestos de libertad de amortización. Disminuciones [310]
1188 221155 1177 NNuumm LLiiqquuiiddaacciióónn II -- DDeettaallllee ccoorrrreecccciioonneess -- EEmmpprreessaass rreedduucciiddaa ddiimmeennssiióónn::lliibbeerrttaadd aammoorrttiizzaacciióónn.. AAuummeennttooss [[331111]]
19 232 17 Num Liquidación I - Detalle correcciones - Empresas reducida dimensión:libertad amortización. Disminuciones [312]
20 249 17 Num Liquidación I - Detalle correcciones - Empresas reducida dimensión:amortización acelerada. Aumentos [313]
21 266 17 Num Liquidación I - Detalle correcciones - Empresas reducida dimensión:amortización acelerada. Disminuciones [314]
22 283 17 Num Liquidación I - Detalle correcciones - Cesión de bienes con opción de compra. Aumentos [315]
23 300 17 Num Liquidación I - Detalle correcciones - Cesión de bienes con opción de compra. Disminuciones [316]
24 317 17 Num Liquidación I - Detalle correcciones - Arrendamiento financiero: régimen especial. Aumentos [317]
25 334 17 Num Liquidación I - Detalle correcciones - Arrendamiento financiero: régimen especial. Disminuciones [318]
26 351 17 Num Liquidación I - Detalle correcciones - Pérdidas por deterioro no justificadas. Aumentos [319]
27 368 17 Num Liquidación I - Detalle correcciones - Pérdidas por deterioro no justificadas. Disminuciones [320]
28 385 17 Num Liquidación I - Detalle correcciones - Pérdidas por deterioro de valor de créditos derivadas de insolvencia deudores. Aumentos [321]
29 402 17 Num Liquidación I - Detalle correcciones - Pérdidas por deterioro de valor de créditos derivadas de insolvencia deudores. Disminuciones [322]
30 419 17 Num Liquidación I - Detalle correcciones - Empresas reducida dimensión: pérdidas por deterioro créditos insolvencias. Aumentos [323]
31 436 17 Num Liquidación I - Detalle correcciones - Empresas reducida dimensión: pérdidas por deterioro creditos insolvencias. Disminuciones [324]
32 453 17 Num Liquidación I - Detalle correcciones - Pérdidas por deterioro de valor de participaciones entidades no cotizadas. Aumentos [325]
33 470 17 Num Liquidación I - Detalle correcciones - Pérdidas por deterioro de valor de participaciones entidades no cotizadas. Disminuciones [326]
34 487 17 Num Liquidación I - Detalle correcciones - Pérdidas por deterioro de valores representativos de deuda. Aumentos [327]
35 504 17 Num Liquidación I - Detalle correcciones - Pérdidas por deterioro de valores representativos de deuda. Disminuciones [328]
36 521 17 Num Liquidación I - Detalle correcciones - Adquisición de participaciones en entidades no residentes. Aumentos [329]
37 538 17 Num Liquidación I - Detalle correcciones - Adquisición de participaciones en entidades no residentes. Disminuciones [330]
38 555 17 Num Liquidación I - Detalle correcciones - Deducción del fondo de comercio. Aumentos [331]
39 572 17 Num Liquidación I - Detalle correcciones - Deducción del fondo de comercio. Disminuciones [332]
40 589 17 Num Liquidación I - Detalle correcciones - Deducción del intangible de vida útil indefinida. Aumentos [333]
41 606 17 Num Liquidación I - Detalle correcciones - Deducción del intangible de vida útil indefinida. Disminuciones [334]
42 623 17 Num Liquidación I - Detalle correcciones - Provisiones y gastos por pensiones. Aumentos [335]
4433 664400 1177 NNuumm LLiiqquuiiddaacciióónn II - DDeettaallllee ccoorrrreecccciioonneess - PPrroovviissiioonneess yy ggaassttooss ppoorr ppeennssiioonneess. DDiissmmiinnuucciioonneess [[333366]]
44 657 17 Num Liquidación I - Detalle correcciones - Otras provisiones no deducibles fiscalmente. Aumentos [337]
45 674 17 Num Liquidación I - Detalle correcciones - Otras provisiones no deducibles fiscalmente. Disminuciones [338]
46 691 17 Num Liquidación I - Detalle correcciones - Gastos por donativos y liberalidades. Aumentos [339]
47 708 17 Num Liquidación I - Detalle correcciones - Operaciones realizadas con paraísos fiscales. Aumentos [341]
48 725 17 Num Liquidación I - Detalle correcciones - Operaciones realizadas con paraísos fiscales. Disminuciones [342]
49 742 17 Num Liquidación I - Detalle correcciones - Otros gastos no deducibles. Aumentos [343]
50 759 17 Num Liquidación I - Detalle correcciones - Revalorizaciones contables. Aumentos [345]
51 776 17 Num Liquidación I - Detalle correcciones - Revalorizaciones contables. Disminuciones [346]
52 793 17 Num Liquidación I - Detalle correcciones - Aplicación del valor normal de mercado. Aumentos [347]
53 810 17 Num Liquidación I - Detalle correcciones - Aplicación del valor normal de mercado. Disminuciones [348]
54 827 17 Num Liquidación I - Detalle correcciones - Ingresos por donaciones y legados otorgados por terceros. Aumentos [349]
5555 884444 1177 NNuumm LLiiqquuiiddaacciióónn II - DDeettaallllee ccoorrrreecccciioonneess - IInnggrreessooss ppoorr ddoonnaacciioonneess yy lleeggaaddooss oottoorrggaaddooss ppoorr tteerrcceerrooss.. DDiissmmiinnuucciioonneess [[335500]]
56 861 17 Num Liquidación I - Detalle correcciones - Correción de rentas por depreciación monetaria. Disminuciones [352]
57 878 17 Num Liquidación I - Detalle correcciones - Gastos por operaciones con acciones propias. Disminuciones [354]
58 895 17 Num Liquidación I - Detalle correcciones - Errores contables. Aumentos [355]
59 912 17 Num Liquidación I - Detalle correcciones - Errores contables. Disminuciones [356]
60 929 17 Num Liquidación I - Detalle correcciones - Operaciones a plazos. Aumentos [357]
61 946 17 Num Liquidación I - Detalle correcciones - Operaciones a plazos. Disminuciones [358]
62 963 17 Num Liquidación I - Detalle correcciones - Reversión del deterioro del valor de elementos patrimoniales. Aumentos [359]
63 980 17 Num Liquidación I - Detalle correcciones - Reversión del deterioro del valor de elementos patrimoniales. Disminuciones [360]
64 997 17 Num Liquidación I - Detalle correcciones - Otras diferencias de imputación temporal de ingresos y gastos. Aumentos [361]
65 1014 17 Num Liquidación I - Detalle correcciones - Otras diferencias de imputación temporal de ingresos y gastos. Disminuciones [362]
66 1031 17 Num Liquidación I - Detalle correcciones - Subcapitalización. Aumentos [363]
67 1048 17 Num Liquidación I - Detalle correcciones - Reinversión de beneficios extraordinarios. Aumentos [365]
6688 11006655 1177 NNum LLiiquiiddaciióón II - DDettalllle correcciiones - GGasttos no ddedduciibblles por iincompattiibbiilliiddadd con lla ddedducciióón por reiinversiióón. AAumenttos [[336677]]
69 1082 17 Num Liquidación I - Detalle correcciones - Exención por doble imposición internacional. Aumentos [369]
70 1099 17 Num Liquidación I - Detalle correcciones - Exención por doble imposición internacional. Disminuciones [370]
71 1116 17 Num Liquidación I - Detalle correcciones - Reducción de ingresos de activos intangibles. Disminuciones [372]
72 1133 17 Num Liquidación I - Detalle correcciones - Obra benéfico-social cajas de ahorro. Aumentos [373]
73 1150 17 Num Liquidación I - Detalle correcciones - Obra benéfico-social cajas de ahorro. Disminuciones [374]
74 1167 17 Num Liquidación I - Detalle correcciones - Agrupaciones interés económico y UTE's. Aumentos [375]
75 1184 17 Num Liquidación I - Detalle correcciones - Agrupaciones interés económico y UTE's. Disminuciones [376]
76 1201 17 Num Liquidación I - Detalle correcciones - Sociedades y fondos de capital-riesgo. Aumentos [377]
77 1218 17 Num Liquidación I - Detalle correcciones - Sociedades y fondos de capital-riesgo. Disminuciones [378]
78 1235 17 Num Liquidación I - Detalle correcciones - Valoración bienes y derechos. Régimen especial operac. reestructuración. Aumentos [379]
79 1252 17 Num Liquidación I - Detalle correcciones - Valoración bienes y derechos. Régimen especial operac. reestructuración. Disminuciones [380]
8800 11226699 1177 NNuumm LLiiqquuiiddaacciióónn II -- DDeettaallllee ccoorrrreecccciioonneess -- MMiinneerrííaa ee hhiiddrrooccaarrbbuurrooss :: ffaaccttoorr aaggoottaammiieennttoo. AAuummeennttooss [[338811]]
81 1286 17 Num Liquidación I - Detalle correcciones - Minería e hidrocarburos : factor agotamiento. Disminuciones [382]
82 1303 17 Num Liquidación I - Detalle correcciones - Hidrocarburos: Amortización inversiones intangibles. Aumentos [383]
83 1320 17 Num Liquidación I - Detalle correcciones - Hidrocarburos: Amortización inversiones intangibles. Disminuciones [384]
Página 17

# Pag. 18

84 1337 17 Num Liquidación I - Detalle correcciones - Régimen fiscal entidades de tenencia valores extranjeros. Aumentos [385]
85 1354 17 Num Liquidación I - Detalle correcciones - Régimen fiscal entidades de tenencia valores extranjeros. Disminuciones [386]
86 1371 17 Num Liquidación I - Detalle correcciones - Transparencia fiscal internacional. Aumentos [387]
87 1388 17 Num Liquidación I - Detalle correcciones - Transparencia fiscal internacional. Disminuciones [388]
88 1405 17 Num Liquidación I - Detalle correcciones - Régimen de entidades parcialmente exentas. Aumentos [389]
89 1422 17 Num Liquidación I - Detalle correcciones - Régimen de entidades parcialmente exentas. Disminuciones [390]
90 1439 17 Num Liquidación I - Detalle correcciones - Aportaciones a favor entidades sin fines lucrativos. Aumentos [250]
91 1456 17 Num Liquidación I - Detalle correcciones - Aportaciones a favor entidades sin fines lucrativos. Disminuciones [251]
92 1473 17 Num Liquidación I - Detalle correcciones - Régimen fiscal entidades sin fines lucrativos. Aumentos [391]
93 1490 17 Num Liquidación I - Detalle correcciones - Régimen fiscal entidades sin fines lucrativos. Disminuciones [392]
94 1507 17 Num Liquidación I - Detalle correcciones - 33ª Copa del América. Aumentos [393]
95 1524 17 Num Liquidación I - Detalle correcciones - 33ª Copa del América. Disminuciones [394]
9966 11554411 1100 AAnn IIddeennttiiffiiccaaddoorr ddee ffiinn ddee rreeggiissttrroo OOBBLLIIGGAATTOORRIIOO CCoonnssttaannttee ""<<//TT220000001122>>""
Total: 1550
Página 18

# Pag. 19

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "013"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 A Indicador de página complementaria. En blanco
66 1111 1177 NNum LLiiquiiddaciióón IIII - DDettalllle correcciiones - MMonttes veciinalles en mano comúún. DDiismiinuciiones [[339966]]
7 28 17 Num Liquidación II - Detalle correcciones - Régimen entidades navieras. Aumentos [397]
8 45 17 Num Liquidación II - Detalle correcciones - Régimen entidades navieras. Disminuciones [398]
9 62 17 Num Liquidación II - Detalle correcciones - Cooperativas: Fondo de reserva obligatorio. Disminuciones [400]
10 79 17 Num Liquidación II - Detalle correcciones - Reservas inversiones en Canarias. Aumentos [403]
11 96 17 Num Liquidación II - Detalle correcciones - Reservas inversiones en Canarias. Disminuciones [404]
12 113 17 Num Liquidación II - Detalle correcciones - Diferimiento plusvalías. Aumentos [405]
13 130 17 Num Liquidación II - Detalle correcciones - Diferimiento plusvalías. Disminuciones [406]
14 147 17 Num Liquidación II - Detalle correcciones - Implantación empresas en el extranjero. Aumentos [407]
15 164 17 Num Liquidación II - Detalle correcciones - Entidades rég.atribución rentas en el extranj. Aumentos [409]
16 181 17 Num Liquidación II - Detalle correcciones - Entidades rég.atribución rentas en el extranj. Disminuciones [410]
17 198 17 Num Liquidación II - Detalle correcciones - Correcciones específicas entidades normativa foral. Aumentos [411]
1188 221155 1177 NNuumm LLiiqquuiiddaacciióónn IIII -- DDeettaallllee ccoorrrreecccciioonneess -- CCoorrrreecccciioonneess eessppeeccííffiiccaass eennttiiddaaddeess nnoorrmmaattiivvaa ffoorraall.. DDiissmmiinnuucciioonneess [[441122]]
19 232 17 Num Liquidación II - Detalle correcciones - Rég. Fiscal S.A. Cotizadas mercado inmobiliario. Disminuciones [503]
20 249 17 Num Liquidación II - Detalle correcciones - Integración de rentas socios SOCIMI. Aumentos [504]
21 266 17 Num Liquidación II - Detalle correcciones - Integración de rentas socios SOCIMI. Disminuciones [505]
22 283 17 Num Liquidación II - Detalle correcciones - Integración bases salida régimen SOCIMI. Aumentos [517]
23 300 17 Num Liquidación II - Detalle correcciones - Otras correcciones al resultado contable. Aumentos [413]
24 317 17 Num Liquidación II - Detalle correcciones - Otras correcciones al resultado contable. Disminuciones [414]
25 334 17 Num Liquidación II - Detalle correcciones - Saldo neto de los ajustes de 1ª aplicación. Aumentos [415]
26 351 17 Num Liquidación II - Detalle correcciones - Saldo neto de los ajustes de 1ª aplicación. Disminuciones [416]
27 368 17 Num Liquidación II - Detalle correcciones - Total correcciones al resultado cta. Pérdidas y gananc. Aumentos [417]
28 385 17 Num Liquidación II - Detalle correcciones - Total correcciones al resultado cta. Pérdidas y gananc. Disminuciones [418]
29 402 17 N Liquidación II - Entidades navieras en función del tonelaje - BI actividades o rentas en régimen general [578]
30 419 17 N Liquidación II - Entidades navieras en función del tonelaje - BI derivada del régimen especial [579]
31 436 17 N Liquidación II - Base imponible - BI antes de la compensación de bases imponibles negativas [550]
32 453 17 Num Liquidación II - Base imponible - Compensación de bases imponibles negativas períodos anteriores [547]
33 470 17 N Liquidación II - Base imponible - Base imponible [552]
34 487 17 N Liquidación II - Base imponible - Sólo cooperativas - Resultados cooperativos [553]
35 504 17 N Liquidación II - Base imponible - Sólo cooperativas - Resultados extracooperativos [554]
36 521 17 N Liquidación II - Base imponible - Sólo agrupaciones interés económico y UTE's - Socios residentes [555]
37 538 17 N Liquidación II - Base imponible - Sólo agrupaciones interés económico y UTE's - Socios no residentes [556]
38 555 17 N Liquidación II - Base imponible - Sólo entidades ZEC - Base imponible a tipo de gravamen especial [559]
39 572 17 N Liquidación II - Base imponible - Sólo SOCIMIS - Parte base impon. del periodo impositivo que tributa al tipo general [520]
40 589 17 N Liquidación II - Base imponible - Sólo SOCIMIS - Parte base impon. del periodo impositivo que tributa al tipo especial [521]
41 606 17 N Liquidación II - Base imponible - Sólo SOCIMIS - Parte base impon. periodos anteriores que tributa este periodo al tipo especial [522]
42 623 17 N Liquidación II - Base imponible - Sólo SOCIMIS - Parte base impon. del periodo impositivo no tributa en este periodo impositivo [523]
4433 664400 44 NNuumm LLiiqquuiiddaacciióónn IIII - TTiippoo ddee ggrraavvaammeenn - TTiippoo ddee ggrraavvaammeenn [[555588]]
44 644 17 N Liquidación II - Sólo sociedades cooperativas - Cuota íntegra previa [560]
45 661 17 Num Liquidación II - Sólo sociedades cooperativas - Compensación de cuotas por pérdidas de cooperativas [561]
46 678 17 N Liquidación II - Cuota íntegra - Cuota íntegra [562]
47 695 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200013>"
Total: 704
Página 19

# Pag. 20

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "014"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria. En blanco En blanco
66 1111 1177 NNuumm BBoonniiffiiccaacciióónn ppoorr rreennttaass oobbtteenniiddaass eenn CCeeuuttaa yy MMeelliillllaa [[556677]]
7 28 17 Num Bonificación actividades exportadoras y de prestación de servicios [568]
8 45 17 Num Bonificación rendimientos por venta de bienes corporales producidos en Canarias [563]
9 62 17 Num Bonificaciones sociedades cooperativas [566]
10 79 17 Num Bonificaciones entidades dedicadas al arrendamiento de viviendas [576]
11 96 17 Num Otras bonificaciones [569]
12 113 17 Num Deducciones por doble imposición - DI interna de periodos anteriores aplicada en el ejercicio [570]
13 130 17 Num Deducciones por doble imposición - DI interna generada y aplicada en el ejercicio actual [571]
14 147 17 Num Deducciones por doble imposición - Deducciones socios SOCIMI [564]
15 164 17 Num Deducciones por doble imposición - DI internacional periodos anteriores aplicada en el ejercicio [572]
16 181 17 Num Deducciones por doble imposición - DI internacional generada y aplicada ejercicio actual [573]
17 198 17 Num Deducciones por doble imposición - Trasparencia fiscal internacional [575]
1188 221155 1177 NNuumm DDeedduucccciioonneess ppoorr ddoobbllee iimmppoossiicciióónn -- DDII iinntteerrnnaa iinntteerrssoocciieettaarriiaa aall 55//1100 %% ((ccooooppeerraattiivvaass)) [[557777]]
19 232 17 Num Bonificaciones empresas navieras en Canarias [581]
20 249 17 N Cuota íntegra ajustada positiva [582]
21 266 17 Num Apoyo fiscal a la inversión y otras deducciones [583]
22 283 17 Num Deducción art.42 L.I.S. Y art. 36 ter Ley 43/95 [585]
23 300 17 Num Deducciones disposición transitoria octava L.I.S. [584]
24 317 17 Num Deducciones con límite del Capítulo IV Título VI L.I.S. [588]
25 334 17 Num Deducción donaciones a entidades sin fines de lucro [565]
26 351 17 Num Deducciones inversión Canarias (Ley 20/1991) [590]
27 368 17 Num Deducciones especifícas de las entidades sometidas a normativa foral [399]
28 385 17 N Cuota líquida positiva [592]
29 402 17 Num Retenciones e ingresos a cuenta/pagos a cuenta participaciones I.I.C. [595]
17 Num Ret. e ingr. a cuenta/pagos a cuenta participaciones I.I.C. Imputadas por agrup. De interés economico y UTES
30 419 [596]
31 436 17 N Cuota del ejercicio a ingresar o a devolver - Estado [599]
32 453 17 N Cuota del ejercicio a ingresar o a devolver - D. Forales/Navarra (Totales) [600]
33 470 17 Num Pagos fraccionados - 1 - Estado [601]
34 487 17 Num Pagos fraccionados - 1 - D. Forales/Navarra (Totales) [602]
35 504 17 Num Pagos fraccionados - 2 - Estado [603]
36 521 17 Num Pagos fraccionados - 2 - D. Forales/Navarra (Totales) [604]
37 538 17 Num Pagos fraccionados - 3 - Estado [605]
38 555 17 Num Pagos fraccionados - 3 - D. Forales/Navarra (Totales) [606]
39 572 17 N Cuota diferencial - Estado [611]
40 589 17 N Cuota diferencial - D. Forales/Navarra (Totales) [612]
41 606 17 Num Incremento por pérdida beneficios fiscales períodos anteriores - Estado [615]
4422 662233 1177 NNuumm IInnccrreemmeennttoo ppoorr ppéérrddiiddaa bbeenneeffiicciiooss ffiissccaalleess ppeerrííooddooss aanntteerriioorreess -- DD. FFoorraalleess//NNaavvaarrrraa ((TToottaalleess)) [[661166]]
43 640 17 Num Incremento por incumplimiento de requisitos SOCIMI - Estado [633]
44 657 17 Num Incremento por incumplimiento de requisitos SOCIMI - D. Forales/Navarra (Totales) [642]
45 674 17 Num Intereses de demora - Estado [617]
46 691 17 Num Intereses de demora - D. Forales/Navarra (Totales) [618]
47 708 17 N Importe ingreso/devolución efectuada de la declaración originaria - Estado [619]
48 725 17 N Importe ingreso/devolución efectuada de la declaración originaria - D. Forales/Navarra (Totales) [620]
49 742 17 N Líquido a ingresar o a devolver - Estado [621]
50 759 17 N Líquido a ingresar o a devolver - D. Forales/Navarra (Totales) [622]
51 776 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200014>"
Total: 785
Página 20

# Pag. 21

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. Constante "<T" . Campo OBLIGATORIO OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "015"
4 9 1 An Fin de identificador de modelo. Constante: ">" .Campo OBLIGATORIO OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria. En blanco
66 1111 1177 NNuumm DDeettaallllee ccoommppeennssaacciióónn bbaasseess iimmpp. nneeggaatt.- aaññoo 11999955 - PPttee. ddee aapplliiccaacciióónn aa pprriinncciippiioo ddeell ppeerriiooddoo [[664400]]
7 28 17 Num Detalle compensación bases imp. negat.- año 1995 - Aplicado en esta liquidación [641]
8 45 17 Num Detalle compensación bases imp. negat.- año 1996 - Pte. de aplicación a principio del periodo [643]
9 62 17 Num Detalle compensación bases imp. negat.- año 1996 - Aplicado en esta liquidación [644]
10 79 17 Num Detalle compensación bases imp. negat.- año 1996 - Pte.aplicación en periodos futuros [645]
11 96 17 Num Detalle compensación bases imp. negat.- año 1997 - Pte. de aplicación a principio del periodo [646]
12 113 17 Num Detalle compensación bases imp. negat.- año 1997 - Aplicado en esta liquidación [647]
13 130 17 Num Detalle compensación bases imp. negat.- año 1997 - Pte.aplicación en periodos futuros [648]
14 147 17 Num Detalle compensación bases imp. negat.- año 1998 - Pte. de aplicación a principio del periodo [649]
15 164 17 Num Detalle compensación bases imp. negat.- año 1998 - Aplicado en esta liquidación [650]
16 181 17 Num Detalle compensación bases imp. negat.- año 1998 - Pte.aplicación en periodos futuros [651]
17 198 17 Num Detalle compensación bases imp. negat.- año 1999 - Pte. de aplicación a principio del periodo [652]
1188 221155 1177 NNuumm DDeettaallllee ccoommppeennssaacciióónn bbaasseess iimmpp.. nneeggaatt..-- aaññoo 11999999 -- AApplliiccaaddoo eenn eessttaa lliiqquuiiddaacciióónn [[665533]]
19 232 17 Num Detalle compensación bases imp. negat.- año 1999 - Pte.aplicación en periodos futuros [654]
20 249 17 Num Detalle compensación bases imp. negat.- año 2000 - Pte. de aplicación a principio del periodo [655]
21 266 17 Num Detalle compensación bases imp. negat.- año 2000 - Aplicado en esta liquidación [656]
22 283 17 Num Detalle compensación bases imp. negat.- año 2000 - Pte.aplicación en periodos futuros [657]
23 300 17 Num Detalle compensación bases imp. negat.- año 2001 - Pte. de aplicación a principio del periodo [658]
24 317 17 Num Detalle compensación bases imp. negat.- año 2001 - Aplicado en esta liquidación [659]
25 334 17 Num Detalle compensación bases imp. negat.- año 2001 - Pte.aplicación en periodos futuros [660]
26 351 17 Num Detalle compensación bases imp. negat.- año 2002 - Pte. de aplicación a principio del periodo [661]
27 368 17 Num Detalle compensación bases imp. negat.- año 2002 - Aplicado en esta liquidación [662]
28 385 17 Num Detalle compensación bases imp. negat.- año 2002 - Pte.aplicación en periodos futuros [663]
29 402 17 Num Detalle compensación bases imp. negat.- año 2003 - Pte. de aplicación a principio del periodo [664]
30 419 17 Num Detalle compensación bases imp. negat.- año 2003 - Aplicado en esta liquidación [665]
31 436 17 Num Detalle compensación bases imp. negat.- año 2003 - Pte.aplicación en periodos futuros [666]
32 453 17 Num Detalle compensación bases imp. negat.- año 2004 - Pte. de aplicación a principio del periodo [667]
33 470 17 Num Detalle compensación bases imp. negat.- año 2004 - Aplicado en esta liquidación [668]
34 487 17 Num Detalle compensación bases imp. negat.- año 2004 - Pte.aplicación en periodos futuros [669]
35 504 17 Num Detalle compensación bases imp. negat.- año 2005 - Pte. de aplicación a principio del periodo [743]
36 521 17 Num Detalle compensación bases imp. negat.- año 2005 - Aplicado en esta liquidación [747]
37 538 17 Num Detalle compensación bases imp. negat.- año 2005 - Pte.aplicación en periodos futuros [748]
38 555 17 Num Detalle compensación bases imp. negat.- año 2006 - Pte. de aplicación a principio del periodo [275]
39 572 17 Num Detalle compensación bases imp. negat.- año 2006 - Aplicado en esta liquidación [276]
40 589 17 Num Detalle compensación bases imp. negat.- año 2006 - Pte.aplicación en periodos futuros [277]
41 606 17 Num Detalle compensación bases imp. negat.- año 2007 - Pte. de aplicación a principio del periodo [608]
42 623 17 Num Detalle compensación bases imp. negat.- año 2007 - Aplicado en esta liquidación [609]
4433 664400 1177 NNuumm DDeettaallllee ccoommppeennssaacciióónn bbaasseess iimmpp. nneeggaatt.- aaññoo 22000077 - PPttee.aapplliiccaacciióónn eenn ppeerriiooddooss ffuuttuurrooss [[661100]]
44 657 17 Num Detalle compensación bases imp. negat.- año 2008 - Pte. de aplicación a principio del periodo [704]
45 674 17 Num Detalle compensación bases imp. negat.- año 2008 - Aplicado en esta liquidación [705]
46 691 17 Num Detalle compensación bases imp. negat.- año 2008 - Pte.aplicación en periodos futuros [706]
47 708 17 Num Detalle compensación bases imp. negat.- año 2009 - Pte. de aplicación a principio del periodo [013]
48 725 17 Num Detalle compensación bases imp. negat.- año 2009 - Aplicado en esta liquidación [014]
49 742 17 Num Detalle compensación bases imp. negat.- año 2009 - Pte.aplicación en periodos futuros [015]
50 759 17 Num Detalle compensación bases imp. negat.- año 2010 - Pte. de aplicación a principio del periodo [725]
51 776 17 Num Detalle compensación bases imp. negat.- año 2010 - Aplicado en esta liquidación [726]
52 793 17 Num Detalle compensación bases imp. negat.- año 2010 - Pte.aplicación en periodos futuros [727]
53 810 17 Num Detalle compensación bases imp. negat.- TOTAL: Pte. de aplicación a principio del periodo [670]
54 827 17 Num Detalle compensación bases imp. negat.- TOTAL: Aplicado en esta liquidación [547]
5555 884444 1177 NNuumm DDeettaallllee ccoommppeennssaacciióónn bbaasseess iimmpp.. nneeggaatt..- TTOOTTAALL:: PPttee.. ddee aapplliiccaacciióónn eenn ppeerriiooddooss ffuuttuurrooss [[667711]]
56 861 17 Num Deducciones doble imposición interna - DI interna 2003 - Deducción pendiente/generada [101]
57 878 4 Num Deducciones doble imposición interna - DI interna 2003 - Tipo de gravamen periodo generación [102]
58 882 17 Num Deducciones doble imposición interna - DI interna 2003 - Deducción pendiente [696]
59 899 17 Num Deducciones doble imposición interna - DI interna 2003 - Deducción aplicada en esta liquidación [697]
60 916 17 Num Deducciones doble imposición interna - DI interna 2004 - Deducción pendiente/generada [104]
61 933 4 Num Deducciones doble imposición interna - DI interna 2004 - Tipo de gravamen periodo generación [105]
62 937 17 Num Deducciones doble imposición interna - DI interna 2004 - Deducción pendiente [846]
63 954 17 Num Deducciones doble imposición interna - DI interna 2004 - Deducción aplicada en esta liquidación [847]
64 971 17 Num Deducciones doble imposición interna - DI interna 2004 - Deducción pendiente ejercicios futuros [848]
65 988 17 Num Deducciones doble imposición interna - DI interna 2005 - Deducción pendiente/generada [106]
66 1005 4 Num Deducciones doble imposición interna - DI interna 2005 - Tipo de gravamen periodo generación [107]
67 1009 17 Num Deducciones doble imposición interna - DI interna 2005 - Deducción pendiente [282]
6688 11002266 1177 NNum DDedducciiones ddobblle iimposiiciióón iintterna - DDII iintterna 22000055 - DDedducciióón aplliicadda en estta lliiquiiddaciióón [[228833]]
69 1043 17 Num Deducciones doble imposición interna - DI interna 2005 - Deducción pendiente ejercicios futuros [284]
70 1060 17 Num Deducciones doble imposición interna - DI interna 2006 - Deducción pendiente/generada [108]
71 1077 4 Num Deducciones doble imposición interna - DI interna 2006 - Tipo de gravamen periodo generación [109]
72 1081 17 Num Deducciones doble imposición interna - DI interna 2006 - Deducción pendiente [702]
73 1098 17 Num Deducciones doble imposición interna - DI interna 2006 - Deducción aplicada en esta liquidación [703]
74 1115 17 Num Deducciones doble imposición interna - DI interna 2006 - Deducción pendiente ejercicios futuros [707]
75 1132 17 Num Deducciones doble imposición interna - DI interna 2007 - Deducción pendiente/generada [110]
76 1149 4 Num Deducciones doble imposición interna - DI interna 2007 - Tipo de gravamen periodo generación [111]
77 1153 17 Num Deducciones doble imposición interna - DI interna 2007 - Deducción pendiente [071]
78 1170 17 Num Deducciones doble imposición interna - DI interna 2007 - Deducción aplicada en esta liquidación [187]
79 1187 17 Num Deducciones doble imposición interna - DI interna 2007 - Deducción pendiente ejercicios futuros [300]
8800 11220044 1177 NNuumm DDeedduucccciioonneess ddoobbllee iimmppoossiicciióónn iinntteerrnnaa -- DDII iinntteerrnnaa 22000088 -- DDeedduucccciióónn ppeennddiieennttee//ggeenneerraaddaa [[111122]]
81 1221 4 Num Deducciones doble imposición interna - DI interna 2008 - Tipo de gravamen periodo generación [113]
82 1225 17 Num Deducciones doble imposición interna - DI interna 2008 - Deducción pendiente [025]
83 1242 17 Num Deducciones doble imposición interna - DI interna 2008 - Deducción aplicada en esta liquidación [026]
Página 21

# Pag. 22

84 1259 17 Num Deducciones doble imposición interna - DI interna 2008 - Deducción pendiente ejercicios futuros [027]
85 1276 17 Num Deducciones doble imposición interna - DI interna 2009 - Deducción pendiente/generada [114]
86 1293 4 Num Deducciones doble imposición interna - DI interna 2009 - Tipo de gravamen periodo generación [115]
87 1297 17 Num Deducciones doble imposición interna - DI interna 2009 - Deducción pendiente [714]
88 1314 17 Num Deducciones doble imposición interna - DI interna 2009 - Deducción aplicada en esta liquidación [715]
89 1331 17 Num Deducciones doble imposición interna - DI interna 2009 - Deducción pendiente ejercicios futuros [716]
90 1348 17 Num Deducciones doble imposición interna - DI interna 2010 - Deducción pendiente/generada [735]
91 1365 4 Num Deducciones doble imposición interna - DI interna 2010 - Tipo de gravamen periodo generación [920]
92 1369 17 Num Deducciones doble imposición interna - DI interna 2010 - Deducción pendiente [736]
93 1386 17 Num Deducciones doble imposición interna - DI interna 2010 - Deducción aplicada en esta liquidación [737]
94 1403 17 Num Deducciones doble imposición interna - DI interna 2010 - Deducción pendiente ejercicios futuros [738]
95 1420 17 Num Deducciones doble imposición interna - Total 2003-2010 - Deducción pendiente/generada [116]
9966 11443377 1177 NNuumm DDeedduucccciioonneess ddoobbllee iimmppoossiicciióónn iinntteerrnnaa - TToottaall 22000033-22001100 - DDeedduucccciióónn ppeennddiieennttee [[111177]]
17 Num Deducciones doble imposición interna - Total 2003-2010 - Deducción aplicada en esta liquidación [570]
97 1454
98 1471 17 Num Deducciones doble imposición interna - Total 2003-2010 - Deducción pendiente ejercicios futuros [118]
99 1488 7 Num Deducciones doble imposición interna - Tipo de gravamen 2010 [103]
17 Num Deducciones doble imposición interna - DI interna 2010 - Intersoc.al 50% - Deducción pendiente/generada [119]
100 1495
101 1512 17 Num Deducciones doble imposición interna - DI interna 2010 - Intersoc.al 50% - Deducción pendiente [120]
17 Num Deducciones doble imposición interna - DI interna 2010 - Intersoc.al 50% - Deducción aplicada en esta liquidación
102 1529 [121]
17 Num Deducciones doble imposición interna - DI interna 2010 - Intersoc.al 50% - Deducción pendiente ejercicios futuros
103 1546 [122]
17 Num Deducciones doble imposición interna - DI interna 2010 - Intersoc.al 100% - Deducción pendiente/generada [123]
110044 11556633
105 1580 17 Num Deducciones doble imposición interna - DI interna 2010 - Intersoc.al 100% - Deducción pendiente [124]
17 Num Deducciones doble imposición interna - DI interna 2010 - Intersoc.al 100% - Deducción aplicada en esta
106 1597 liquidación [125]
17 Num Deducciones doble imposición interna - DI interna 2010 - Intersoc.al 100% - Deducción pendiente ejercicios
107 1614 futuros [126]
17 Num Deducciones doble imposición interna - DI interna 2010 - Plusvalías fuente interna - Deducción
108 1631 pendiente/generada [127]
17 Num Deducciones doble imposición interna - DI interna 2010 - Plusvalías fuente interna - Deducción pendiente [128]
109 1648
17 Num Deducciones doble imposición interna - DI interna 2010 - Plusvalías fuente interna - Deducción aplicada en esta
110 1665 liquidación [129]
17 Num Deducciones doble imposición interna - DI interna 2010 - Plusvalías fuente interna - Deducción pendiente
111111 11668822 eejjeerrcciicciiooss ffuuttuurrooss [[113300]]
112 1699 17 Num Deducciones doble imposición interna - Total 2010 Deducción pendiente/generada [131]
113 1716 17 Num Deducciones doble imposición interna - Total 2010 Deducción pendiente [132]
114 1733 17 Num Deducciones doble imposición interna - Total 2010 Deducción aplicada en esta liquidación [571]
115 1750 17 Num Deducciones doble imposición interna - Total 2010 Deducción pendiente ejercicios futuros [133]
17 Num Deducciones doble imposición internacional - DI internacional 2000 - Deducción pendiente/generada [151]
116 1767
4 Num Deducciones doble imposición internacional - DI internacional 2000 - Tipo de gravamen periodo generación [152]
117 1784
118 1788 17 Num Deducciones doble imposición internacional - DI internacional 2000 - Deducción pendiente [711]
17 Num Deducciones doble imposición internacional - DI internacional 2000 - Deducción aplicada en esta liquidación [712]
119 1805
17 Num Deducciones doble imposición internacional - DI internacional 2001 - Deducción pendiente/generada [153]
112200 11882222
4 Num Deducciones doble imposición internacional - DI internacional 2001 - Tipo de gravamen periodo generación [728]
121 1839
122 1843 17 Num Deducciones doble imposición internacional - DI internacional 2001 - Deducción pendiente [637]
17 Num Deducciones doble imposición internacional - DI internacional 2001 - Deducción aplicada en esta liquidación [638]
123 1860
17 Num Deducciones doble imposición internacional - DI internacional 2001 - Deducción pendiente ejercicios futuros [639]
124 1877
17 Num Deducciones doble imposición internacional - DI internacional 2002 - Deducción pendiente/generada [154]
125 1894
4 Num Deducciones doble imposición internacional - DI internacional 2002 - Tipo de gravamen periodo generación [729]
126 1911
127 1915 17 Num Deducciones doble imposición internacional - DI internacional 2002 - Deducción pendiente [849]
1177 NNumm DDeedducccciioonneess ddoobbllee iimmppoossiicciióónn iinntteerrnnaacciioonnaall - DDII iinntteerrnnaacciioonnaall 22000022 - DDeedducccciióónn aapplliiccaaddaa eenn eessttaa lliiqquiiddaacciióónn [[889944]]
128 1932
17 Num Deducciones doble imposición internacional - DI internacional 2002 - Deducción pendiente ejercicios futuros [197]
129 1949
17 Num Deducciones doble imposición internacional - DI internacional 2003 - Deducción pendiente/generada [155]
130 1966
4 Num Deducciones doble imposición internacional - DI internacional 2003 - Tipo de gravamen periodo generación [730]
131 1983
132 1987 17 Num Deducciones doble imposición internacional - DI internacional 2003 - Deducción pendiente [285]
17 Num Deducciones doble imposición internacional - DI internacional 2003 - Deducción aplicada en esta liquidación [286]
133 2004
17 Num Deducciones doble imposición internacional - DI internacional 2003 - Deducción pendiente ejercicios futuros [287]
134 2021
1177 NNuumm DDeedduucccciioonneess ddoobbllee iimmppoossiicciióónn iinntteerrnnaacciioonnaall - DDII iinntteerrnnaacciioonnaall 22000055 - DDeedduucccciióónn ppeennddiieennttee//ggeenneerraaddaa [[115566]]
135 2038
4 Num Deducciones doble imposición internacional - DI internacional 2005 - Tipo de gravamen periodo generación [731]
136 2055
137 2059 17 Num Deducciones doble imposición internacional - DI internacional 2005 - Deducción pendiente [825]
17 Num Deducciones doble imposición internacional - DI internacional 2005 - Deducción aplicada en esta liquidación [826]
138 2076
17 Num Deducciones doble imposición internacional - DI internacional 2005 - Deducción pendiente ejercicios futuros [827]
139 2093
17 Num Deducciones doble imposición internacional - DI internacional 2005 - Deducción pendiente/generada [157]
140 2110
4 Num Deducciones doble imposición internacional - DI internacional 2005 - Tipo de gravamen periodo generación [732]
141 2127
114422 22113311 1177 NNuumm DDeedduucccciioonneess ddoobbllee iimmppoossiicciióónn iinntteerrnnaacciioonnaall -- DDII iinntteerrnnaacciioonnaall 22000055 -- DDeedduucccciióónn ppeennddiieennttee [[000011]]
17 Num Deducciones doble imposición internacional - DI internacional 2005 - Deducción aplicada en esta liquidación [002]
143 2148
17 Num Deducciones doble imposición internacional - DI internacional 2005 - Deducción pendiente ejercicios futuros [003]
144 2165
Página 22

# Pag. 23

17 Num Deducciones doble imposición internacional - DI internacional 2006 - Deducción pendiente/generada [158]
145 2182
4 Num Deducciones doble imposición internacional - DI internacional 2006 - Tipo de gravamen periodo generación [733]
146 2199
147 2203 17 Num Deducciones doble imposición internacional - DI internacional 2006 - Deducción pendiente [028]
17 Num Deducciones doble imposición internacional - DI internacional 2006 - Deducción aplicada en esta liquidación [029]
148 2220
17 Num Deducciones doble imposición internacional - DI internacional 2006 - Deducción pendiente ejercicios futuros [030]
149 2237
17 Num Deducciones doble imposición internacional - DI internacional 2007 - Deducción pendiente/generada [159]
150 2254
4 Num Deducciones doble imposición internacional - DI internacional 2007 - Tipo de gravamen periodo generación [734]
151 2271
152 2275 17 Num Deducciones doble imposición internacional - DI internacional 2007 - Deducción pendiente [717]
17 Num Deducciones doble imposición internacional - DI internacional 2007 - Deducción aplicada en esta liquidación [718]
153 2292
17 Num Deducciones doble imposición internacional - DI internacional 2007 - Deducción pendiente ejercicios futuros [719]
154 2309
17 Num Deducciones doble imposición internacional - DI internacional 2008 - Deducción pendiente/generada [720]
155 2326
4 Num Deducciones doble imposición internacional - DI internacional 2008 - Tipo de gravamen periodo generación [721]
156 2343
157 2347 17 Num Deducciones doble imposición internacional - DI internacional 2008 - Deducción pendiente [722]
17 Num Deducciones doble imposición internacional - DI internacional 2008 - Deducción aplicada en esta liquidación [723]
158 2364
17 Num Deducciones doble imposición internacional - DI internacional 2008 - Deducción pendiente ejercicios futuros [724]
159 2381
17 Num Deducciones doble imposición internacional - DI internacional 2009 - Deducción pendiente/generada [739]
160 2398
4 Num Deducciones doble imposición internacional - DI internacional 2009 - Tipo de gravamen periodo generación [921]
161 2415
162 2419 17 Num Deducciones doble imposición internacional - DI internacional 2009 - Deducción pendiente [740]
17 Num Deducciones doble imposición internacional - DI internacional 2009 - Deducción aplicada en esta liquidación [741]
163 2436
17 Num Deducciones doble imposición internacional - DI internacional 2009 - Deducción pendiente ejercicios futuros [742]
164 2453
17 Num Deducciones doble imposición internacional - DI internacional 2010 - Deducción pendiente/generada [134]
165 2470
4 Num Deducciones doble imposición internacional - DI internacional 2010 - Tipo de gravamen periodo generación [926]
116666 22448877
167 2491 17 Num Deducciones doble imposición internacional - DI internacional 2010 - Deducción pendiente [135
17 Num Deducciones doble imposición internacional - DI internacional 2010 - Deducción aplicada en esta liquidación [136]
168 2508
17 Num Deducciones doble imposición internacional - DI internacional 2010 - Deducción pendiente ejercicios futuros [137]
169 2525
170 2542 17 Num Deducciones doble imposición internacional - Total 2000-2010 - Deducción pendiente/generada [160]
171 2559 17 Num Deducciones doble imposición internacional - Total 2000-2010 - Deducción pendiente [161]
17 Num Deducciones doble imposición internacional - Total 2000-2010 - Deducción aplicada en esta liquidación [572]
172 2576
17 Num Deducciones doble imposición internacional - Total 2000-2010 - Deducción pendiente ejercicios futuros [162]
173 2593
174 2610 7 Num Deducciones doble imposición internacional - Tipo de gravamen 2010 [103]
17 Num Deducciones doble imposición internacional - DI internacional 2010 - Imp.soportado sujeto pasivo - Deducción
175 2617 pendiente/generada [163]
17 Num Deducciones doble imposición internacional - DI internacional 2010 - Imp.soportado sujeto pasivo - Deducción
176 2634 pendiente [164]
17 Num Deducciones doble imposición internacional - DI internacional 2010 - Imp.soportado sujeto pasivo - Deducción
177 2651 aplicada en esta liquidación [165]
17 Num Deducciones doble imposición internacional - DI internacional 2010 - Imp.soportado sujeto pasivo - Deducción
178 2668 pendiente ejercicios futuros [166]
17 Num Deducciones doble imposición internacional - DI internacional 2010 - Dividendos y participaciones - Deducción
179 2685 pendiente/generada [167]
17 Num Deducciones doble imposición internacional - DI internacional 2010 - Dividendos y participaciones - Deducción
180 2702 pendiente [168]
17 Num Deducciones doble imposición internacional - DI internacional 2010 - Dividendos y participaciones - Deducción
118811 22771199 aapplliiccaaddaa eenn eessttaa lliiqquuiiddaacciióónn [[116699]]
17 Num Deducciones doble imposición internacional - DI internacional 2010 - Dividendos y participaciones - Deducción
182 2736 pendiente ejercicios futuros [170]
183 2753 17 Num Deducciones doble imposición internacional - Total 2010 - Deducción pendiente/generada [171]
184 2770 17 Num Deducciones doble imposición internacional - Total 2010 - Deducción pendiente [172]
185 2787 17 Num Deducciones doble imposición internacional - Total 2010 - Deducción aplicada en esta liquidación [573]
186 2804 17 Num Deducciones doble imposición internacional - Total 2010 - Deducción pendiente ejercicios futuros [174]
187 2821 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200015>"
Total: 2830
Página 23

# Pag. 24

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. Campo OBLIGATORIO OBLIGATORIO Constante "016"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria. En blanco
66 1111 1177 NNuumm DDeedduucccc. AArrtt. 3366 tteerr LLeeyy 4433 // 11999955. 22000011 - DDeedduucccciióónn ppeennddiieennttee//ggeenneerraaddaa [[883355]]
7 28 17 Num Deducc. Art. 36 ter Ley 43 / 1995. 2001 - Aplicado en esta liquidación [836]
8 45 17 Num Deducc. Art. 36 ter Ley 43 / 1995. 2001 - Pendiente aplicación [837]
9 62 17 Num Deducc. Art. 36 ter Ley 43 / 1995. 2002 - Deducción pendiente/generada [838]
10 79 17 Num Deducc. Art. 36 ter Ley 43 / 1995. 2002 - Aplicado en esta liquidación [839]
11 96 17 Num Deducc. Art. 36 ter Ley 43 / 1995. 2002 - Pendiente aplicación [840]
12 113 17 Num Deducc. Art. 36 ter Ley 43 / 1995. 2003 - Deducción pendiente/generada [932]
13 130 17 Num Deducc. Art. 36 ter Ley 43 / 1995. 2003 - Aplicado en esta liquidación [933]
14 147 17 Num Deducc. Art. 36 ter Ley 43 / 1995. 2003 - Pendiente aplicación [934]
15 164 17 Num Deducc. Art. 42 L.I.S. 2004 - Deducción pendiente/generada [297]
16 181 17 Num Deducc. Art. 42 L.I.S. 2004 - Aplicado en esta liquidación [298]
17 198 17 Num Deducc. Art. 42 L.I.S. 2004 - Pendiente aplicación [299]
1188 221155 1177 NNuumm DDeedduucccc.. AArrtt.. 4422 LL..II..SS.. 22000055 -- DDeedduucccciióónn ppeennddiieennttee//ggeenneerraaddaa [[009900]]
19 232 17 Num Deducc. Art. 42 L.I.S. 2005 - Aplicado en esta liquidación [091]
20 249 17 Num Deducc. Art. 42 L.I.S. 2005 - Pendiente aplicación [092]
21 266 17 Num Deducc. Art. 42 L.I.S. 2006 - Deducción pendiente/generada [004]
22 283 17 Num Deducc. Art. 42 L.I.S. 2006 - Aplicado en esta liquidación [005]
23 300 17 Num Deducc. Art. 42 L.I.S. 2006 - Pendiente aplicación [006]
24 317 17 Num Deducc. Art. 42 L.I.S. 2007 - Deducción pendiente/generada [031]
25 334 17 Num Deducc. Art. 42 L.I.S. 2007 - Aplicado en esta liquidación [032]
26 351 17 Num Deducc. Art. 42 L.I.S. 2007 - Pendiente aplicación [033]
27 368 17 Num Deducc. Art. 42 L.I.S. 2008 - Deducción pendiente/generada [022]
28 385 17 Num Deducc. Art. 42 L.I.S. 2008 - Aplicado en esta liquidación [023]
29 402 17 Num Deducc. Art. 42 L.I.S. 2008 - Pendiente aplicación [024]
30 419 17 Num Deducc. Art. 42 L.I.S. 2009 - Deducción pendiente/generada [040]
31 436 17 Num Deducc. Art. 42 L.I.S. 2009 - Aplicado en esta liquidación [041]
32 453 17 Num Deducc. Art. 42 L.I.S. 2009 - Pendiente aplicación [042]
33 470 17 Num Deducc. Art. 42 L.I.S. 2010 - Deducción pendiente/generada [138]
34 487 17 Num Deducc. Art. 42 L.I.S. 2010 - Aplicado en esta liquidación [139]
35 504 17 Num Deducc. Art. 42 L.I.S. 2010 - Pendiente aplicación [140]
36 521 17 Num Deducc. Art. 36 ter Ley 43 / 1995 y 42 LIS. Total Deducc. - Deducción pendiente/generada [841]
37 538 17 Num Deducc. Art. 36 ter Ley 43 / 1995 y 42 LIS. Total Deducc. - Aplicado en esta liquidación [585]
38 555 17 Num Deducc. Art. 36 ter Ley 43 / 1995 y 42 LIS. Total Deducc.. Pendiente aplicación [843]
39 572 17 Num Deducciones DT octava LIS - 2005 Periodificación/diferimiento. Deducción pendiente/generada [749]
40 589 17 Num Deducciones DT octava LIS - 2005 Periodificación/diferimiento. Aplicado en esta liquidación [750]
41 606 17 Num Deducciones DT octava LIS - 2006 Periodificación. Deducción pendiente/generada [752]
42 623 17 Num Deducciones DT octava LIS - 2006 Periodificación. Aplicado en esta liquidación [753]
4433 664400 1177 NNuumm DDeedduucccciioonneess DDTT ooccttaavvaa LLIISS - 22000066 PPeerriiooddiiffiiccaacciióónn. PPeennddiieennttee ddee aapplliiccaacciióónn [[775544]]
44 657 17 Num Deducciones DT octava LIS - 2007 Periodificación. Deducción pendiente/generada [755]
45 674 17 Num Deducciones DT octava LIS - 2007 Periodificación. Aplicado en esta liquidación [756]
46 691 17 Num Deducciones DT octava LIS - 2007 Periodificación. Pendiente de aplicación [757]
47 708 17 Num Deducciones DT octava LIS - 2008 Periodificación. Deducción pendiente/generada [758]
48 725 17 Num Deducciones DT octava LIS - 2008 Periodificación. Aplicado en esta liquidación [759]
49 742 17 Num Deducciones DT octava LIS - 2008 Periodificación. Pendiente de aplicación [760]
50 759 17 Num Deducciones DT octava LIS - 2009 Periodificación. Deducción pendiente/generada [761]
51 776 17 Num Deducciones DT octava LIS - 2009 Periodificación. Aplicado en esta liquidación [762]
52 793 17 Num Deducciones DT octava LIS - 2009 Periodificación. Pendiente de aplicación [763]
53 810 17 Num Deducciones DT octava LIS - 2010 Periodificación. Deducción pendiente/generada [744]
54 827 17 Num Deducciones DT octava LIS - 2010 Periodificación. Aplicado en esta liquidación [745]
5555 884444 1177 NNuumm DDeedduucccciioonneess DDTT ooccttaavvaa LLIISS - 22001100 PPeerriiooddiiffiiccaacciióónn.. PPeennddiieennttee ddee aapplliiccaacciióónn [[774466]]
56 861 17 Num Deducciones DT octava LIS - Total deducciones DT 8ª. Deducción pendiente/generada [764]
57 878 17 Num Deducciones DT octava LIS - Total deducciones DT 8ª. Aplicado en esta liquidación [584]
58 895 17 Num Deducciones DT octava LIS - Total deducciones DT 8ª. Pendiente de aplicación [765]
59 912 17 Num Rég.reserva inversiones Canarias - Canarias 2006. Importe dotaciones [081]
60 929 17 Num Rég.reserva inversiones Canarias - Canarias 2006. Materializaciones 2009 [082]
61 946 1 Num Rég.reserva inversiones Canarias - Canarias 2006. Clave [088]
62 947 17 Num Rég.reserva inversiones Canarias - RIC 2007. Importe dotación [089]
63 964 17 Num Rég.reserva inversiones Canarias - RIC 2007. Inversiones previstas A B D (1) [094]
64 981 17 Num Rég.reserva inversiones Canarias - RIC 2007. Inversiones previstas C y D (2 a 6) [095]
65 998 17 Num Rég.reserva inversiones Canarias - RIC 2007. Pendiente materializar [096]
66 1015 17 Num Rég.reserva inversiones Canarias - RIC 2008. Importe dotación [097]
67 1032 17 Num Rég.reserva inversiones Canarias - RIC 2008. Inversiones previstas A B D (1) [098]
6688 11004499 1177 NNum RRéég.reserva iinversiiones CCanariias - RRIICC 22000088. IInversiiones previisttas CC y DD ((22 a 66)) [[004477]]
69 1066 17 Num Rég.reserva inversiones Canarias - RIC 2008. Pendiente materializar [048]
70 1083 17 Num Rég.reserva inversiones Canarias - RIC 2009. Importe dotación [524]
71 1100 17 Num Rég.reserva inversiones Canarias - RIC 2009. Inversiones previstas A B D (1) [525]
72 1117 17 Num Rég.reserva inversiones Canarias - RIC 2009. Inversiones previstas C y D (2 a 6) [526]
73 1134 17 Num Rég.reserva inversiones Canarias - RIC 2009. Pendiente materializar [527]
74 1151 17 Num Rég.reserva inversiones Canarias - RIC 2010. Importe dotación [922]
75 1168 17 Num Rég.reserva inversiones Canarias - RIC 2010. Inversiones previstas A B D (1) [923]
76 1185 17 Num Rég.reserva inversiones Canarias - RIC 2010. Inversiones previstas C y D (2 a 6) [924]
77 1202 17 Num Rég.reserva inversiones Canarias - RIC 2010. Pendiente materializar [925]
17 Num Rég.reserva inversiones Canarias - Inv.anticipadas futuras dotaciones RIC en 2010. Inversiones previstas A B D
78 1219 (1)[020]
17 Num Rég.reserva inversiones Canarias - Inv.anticipadas futuras dotaciones RIC en 2010. Inversiones previstas C y D
79 1236 (2 a 6) [021]
80 1253 17 Num Deducciones inversión Canarias - Activos fijos 2005. Deducción pendiente/generada [854]
81 1270 17 Num Deducciones inversión Canarias - Activos fijos 2005. Aplicado en esta liquidación [855]
82 1287 17 Num Deducciones inversión Canarias - Activos fijos 2006. Deducción pendiente/generada [857]
Página 24

# Pag. 25

83 1304 17 Num Deducciones inversión Canarias - Activos fijos 2006. Aplicado en esta liquidación [858]
84 1321 17 Num Deducciones inversión Canarias - Activos fijos 2006. Pendiente de aplicación [859]
85 1338 17 Num Deducciones inversión Canarias - Activos fijos 2007. Deducción pendiente/generada [860]
86 1355 17 Num Deducciones inversión Canarias - Activos fijos 2007. Aplicado en esta liquidación [861]
87 1372 17 Num Deducciones inversión Canarias - Activos fijos 2007. Pendiente de aplicación [862]
88 1389 17 Num Deducciones inversión Canarias - Activos fijos 2008. Deducción pendiente/generada [863]
89 1406 17 Num Deducciones inversión Canarias - Activos fijos 2008. Aplicado en esta liquidación [864]
90 1423 17 Num Deducciones inversión Canarias - Activos fijos 2008. Pendiente de aplicación [865]
91 1440 17 Num Deducciones inversión Canarias - Activos fijos 2009. Deducción pendiente/generada [883]
92 1457 17 Num Deducciones inversión Canarias - Activos fijos 2009. Aplicado en esta liquidación [884]
93 1474 17 Num Deducciones inversión Canarias - Activos fijos 2009. Pendiente de aplicación [885]
94 1491 17 Num Deducciones inversión Canarias - 1996 Suma deducciones ID. Deducción pendiente/generada [194]
9955 11550088 1177 NNuumm DDeedduucccciioonneess iinnvveerrssiióónn CCaannaarriiaass - 11999966 SSuummaa ddeedduucccciioonneess IIDD. AApplliiccaaddoo eenn eessttaa lliiqquuiiddaacciióónn [[119955]]
96 1525 17 Num Deducciones inversión Canarias - 1996 Suma deducciones ID. Pendiente de aplicación [196]
97 1542 17 Num Deducciones inversión Canarias - Inversiones Canarias 1997. Deducción pendiente/generada [868]
98 1559 17 Num Deducciones inversión Canarias - Inversiones Canarias 1997. Aplicado en esta liquidación [869]
99 1576 17 Num Deducciones inversión Canarias - Inversiones Canarias 1997. Pendiente de aplicación [834]
100 1593 17 Num Deducciones inversión Canarias - Inversiones Canarias 1998. Deducción pendiente/generada [871]
101 1610 17 Num Deducciones inversión Canarias - Inversiones Canarias 1998. Aplicado en esta liquidación [872]
102 1627 17 Num Deducciones inversión Canarias - Inversiones Canarias 1998. Pendiente de aplicación [873]
103 1644 17 Num Deducciones inversión Canarias - Inversiones Canarias 1999. Deducción pendiente/generada [874]
104 1661 17 Num Deducciones inversión Canarias - Inversiones Canarias 1999. Aplicado en esta liquidación [875]
105 1678 17 Num Deducciones inversión Canarias - Inversiones Canarias 1999. Pendiente de aplicación [876]
106 1695 17 Num Deducciones inversión Canarias - Inversiones Canarias 2000. Deducción pendiente/generada [877]
110077 11771122 1177 NNuumm DDeedduucccciioonneess iinnvveerrssiióónn CCaannaarriiaass - IInnvveerrssiioonneess CCaannaarriiaass 22000000.. AApplliiccaaddoo eenn eessttaa lliiqquuiiddaacciióónn [[887788]]
108 1729 17 Num Deducciones inversión Canarias - Inversiones Canarias 2000. Pendiente de aplicación [879]
109 1746 17 Num Deducciones inversión Canarias - Inversiones Canarias 2001. Deducción pendiente/generada [880]
110 1763 17 Num Deducciones inversión Canarias - Inversiones Canarias 2001. Aplicado en esta liquidación [881]
111 1780 17 Num Deducciones inversión Canarias - Inversiones Canarias 2001. Pendiente de aplicación [882]
112 1797 17 Num Deducciones inversión Canarias - Inversiones Canarias 2002. Deducción pendiente/generada [866]
113 1814 17 Num Deducciones inversión Canarias - Inversiones Canarias 2002. Aplicado en esta liquidación [867]
114 1831 17 Num Deducciones inversión Canarias - Inversiones Canarias 2002. Pendiente de aplicación [870]
115 1848 17 Num Deducciones inversión Canarias - Inversiones Canarias 2003. Deducción pendiente/generada [939]
116 1865 17 Num Deducciones inversión Canarias - Inversiones Canarias 2003. Aplicado en esta liquidación [940]
117 1882 17 Num Deducciones inversión Canarias - Inversiones Canarias 2003. Pendiente de aplicación [941]
118 1899 17 Num Deducciones inversión Canarias - Inversiones Canarias 2004. Deducción pendiente/generada [191]
119 1916 17 Num Deducciones inversión Canarias - Inversiones Canarias 2004. Aplicado en esta liquidación [192]
120 1933 1177 NNum DDedducciiones iinversiióón CCanariias - IInversiiones CCanariias 22000044. PPenddiientte dde aplliicaciióón [[119933]]
121 1950 17 Num Deducciones inversión Canarias - Inversiones Canarias 2005. Deducción pendiente/generada [613]
122 1967 17 Num Deducciones inversión Canarias - Inversiones Canarias 2005. Aplicado en esta liquidación [614]
123 1984 17 Num Deducciones inversión Canarias - Inversiones Canarias 2005. Pendiente de aplicación [701]
124 2001 17 Num Deducciones inversión Canarias - Inversiones Canarias 2006. Deducción pendiente/generada [200]
125 2018 17 Num Deducciones inversión Canarias - Inversiones Canarias 2006. Aplicado en esta liquidación [257]
126 2035 17 Num Deducciones inversión Canarias - Inversiones Canarias 2006. Pendiente de aplicación [011]
127 2052 17 Num Deducciones inversión Canarias - Inversiones Canarias 2007. Deducción pendiente/generada [037]
128 2069 17 Num Deducciones inversión Canarias - Inversiones Canarias 2007. Aplicado en esta liquidación [038]
129 2086 17 Num Deducciones inversión Canarias - Inversiones Canarias 2007. Pendiente de aplicación [039]
130 2103 17 Num Deducciones inversión Canarias - Inversiones Canarias 2008. Deducción pendiente/generada [044]
131 2120 17 Num Deducciones inversión Canarias - Inversiones Canarias 2008. Aplicado en esta liquidación [045]
113322 22113377 1177 NNuumm DDeedduucccciioonneess iinnvveerrssiióónn CCaannaarriiaass -- IInnvveerrssiioonneess CCaannaarriiaass 22000088. PPeennddiieennttee ddee aapplliiccaacciióónn [[004466]]
133 2154 17 Num Deducciones inversión Canarias - Inversiones Canarias 2009. Deducción pendiente/generada [528]
134 2171 17 Num Deducciones inversión Canarias - Inversiones Canarias 2009. Aplicado en esta liquidación [529]
135 2188 17 Num Deducciones inversión Canarias - Inversiones Canarias 2009. Pendiente de aplicación [530]
136 2205 17 Num Deducciones inversión Canarias - Inversiones Canarias 2010. Deducción pendiente/generada [144]
137 2222 17 Num Deducciones inversión Canarias - Inversiones Canarias 2010. Aplicado en esta liquidación [145]
138 2239 17 Num Deducciones inversión Canarias - Inversiones Canarias 2010. Pendiente de aplicación [146]
139 2256 17 Num Deducciones inversión Canarias - Activos fijos 2010. Deducción pendiente/generada [852]
140 2273 17 Num Deducciones inversión Canarias - Activos fijos 2010. Aplicado en esta liquidación [853]
141 2290 17 Num Deducciones inversión Canarias - Activos fijos 2010. Pendiente de aplicación [856]
17 Num Deducciones inversión Canarias - Total deducciones inversiones Canarias. Deducción pendiente/generada [886]
142 2307
17 Num Deducciones inversión Canarias - Total deducciones inversiones Canarias. Aplicado en esta liquidación [590]
143 2324
17 Num Deducciones inversión Canarias - Total deducciones inversiones Canarias. Pendiente de aplicación [887]
144 2341
145 2358 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200016>"
Total: 2367
Página 25

# Pag. 26

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "017"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NNuumm DDeedduucccc.ppaarraa iinncceennttiivvaarr ddeetteerrmmiinnaaddaass aaccttiivviiddaaddeess - 11999966 SSuummaa ddeedduucccciioonneess IIDD. DDeedduucccciióónn ppeennddiieennttee//ggeenneerraaddaa
17 Num [D8e4d2u]cc.para incentivar determinadas actividades - 1996 Suma deducciones ID. Aplicado en esta liquidación [844]
7 28
17 Num Deducc.para incentivar determinadas actividades - 1996 Suma deducciones ID. Pendiente de aplicación [845]
8 45
17 Num Deducc.para incentivar determ.actividades - 1997 Suma deducciones. Deducción pendiente/generada [768]
9 62
10 79 17 Num Deducc.para incentivar determ.actividades - 1997 Suma deducciones. Aplicado en esta liquidación [769]
11 96 17 Num Deducc.para incentivar determ.actividades - 1997 Suma deducciones. Pendiente de aplicación [770]
17 Num Deducc.para incentivar determ.actividades - 1998 Suma deducciones. Deducción pendiente/generada [774]
12 113
13 130 17 Num Deducc.para incentivar determ.actividades - 1998 Suma deducciones. Aplicado en esta liquidación [775]
14 147 17 Num Deducc.para incentivar determ.actividades - 1998 Suma deducciones. Pendiente de aplicación [776]
17 Num Deducc.para incentivar determ.actividades - 1999 Suma deducciones. Deducción pendiente/generada [780]
15 164
16 181 17 Num Deducc.para incentivar determ.actividades - 1999 Suma deducciones. Aplicado en esta liquidación [781]
17 198 17 Num Deducc.para incentivar determ.actividades - 1999 Suma deducciones. Pendiente de aplicación [782]
17 Num Deducc.para incentivar determ.actividades - 2000 Suma deducciones. Deducción pendiente/generada [786]
18 215
19 232 17 Num Deducc.para incentivar determ.actividades - 2000 Suma deducciones. Aplicado en esta liquidación [787]
20 249 17 Num Deducc.para incentivar determ.actividades - 2000 Suma deducciones. Pendiente de aplicación [788]
17 Num Deducc.para incentivar determ.actividades - 2001 Suma deducciones. Deducción pendiente/generada [766]
21 266
22 283 17 Num Deducc.para incentivar determ.actividades - 2001 Suma deducciones. Aplicado en esta liquidación [767]
23 300 17 Num Deducc.para incentivar determ.actividades - 2001 Suma deducciones. Pendiente de aplicación [833]
17 Num Deducc.ppara incentivar determ.actividades - 2002 Suma deducciones. Deducción ppendiente/ggenerada [[198]]
24 317
25 334 17 Num Deducc.para incentivar determ.actividades - 2002 Suma deducciones. Aplicado en esta liquidación [896]
26 351 17 Num Deducc.para incentivar determ.actividades - 2002 Suma deducciones. Pendiente de aplicación [897]
17 Num Deducc.para incentivar determ.actividades - 2003 Suma deducciones. Deducción pendiente/generada [288]
27 368
28 385 17 Num Deducc.para incentivar determ.actividades - 2003 Suma deducciones. Aplicado en esta liquidación [289]
29 402 17 Num Deducc.para incentivar determ.actividades - 2003 Suma deducciones. Pendiente de aplicación [290]
17 Num Deducc.para incentivar determ.actividades - 2004 Suma deducciones. Deducción pendiente/generada [466]
30 419
31 436 17 Num Deducc.para incentivar determ.actividades - 2004 Suma deducciones. Aplicado en esta liquidación [467]
32 453 17 Num Deducc.para incentivar determ.actividades - 2004 Suma deducciones. Pendiente de aplicación [468]
17 Num Deducc.para incentivar determ.actividades - 2005 Suma deducciones. Deducción pendiente/generada [061]
3333 447700
34 487 17 Num Deducc.para incentivar determ.actividades - 2005 Suma deducciones. Aplicado en esta liquidación [498]
35 504 17 Num Deducc.para incentivar determ.actividades - 2005 Suma deducciones. Pendiente de aplicación [586]
17 Num Deducc.para incentivar determ.actividades - 2006 Suma deducciones. Deducción pendiente/generada [472]
36 521
37 538 17 Num Deducc.para incentivar determ.actividades - 2006 Suma deducciones. Aplicado en esta liquidación [473]
38 555 17 Num Deducc.para incentivar determ.actividades - 2006 Suma deducciones. Pendiente de aplicación [478]
17 Num Deducc.para incentivar determ.actividades - 2007 Suma deducciones. Deducción pendiente/generada [180]
39 572
40 589 17 Num Deducc.para incentivar determ.actividades - 2007 Suma deducciones. Aplicado en esta liquidación [181]
41 606 17 Num Deducc.para incentivar determ.actividades - 2007 Suma deducciones. Pendiente de aplicación [182]
17 Num Deducc.para incentivar determ.actividades - 2008 Suma deducciones. Deducción pendiente/generada [531]
42 623
4433 664400 1177 NNuumm DDeedduucccc.ppaarraa iinncceennttiivvaarr ddeetteerrmm.aaccttiivviiddaaddeess -- 22000088 SSuummaa ddeedduucccciioonneess. AApplliiccaaddoo eenn eessttaa lliiqquuiiddaacciióónn [[553322]]
44 657 17 Num Deducc.para incentivar determ.actividades - 2008 Suma deducciones. Pendiente de aplicación [533]
17 Num Deducc.para incentivar determ.actividades - 2009 Suma deducciones. Deducción pendiente/generada [945]
45 674
46 691 17 Num Deducc.para incentivar determ.actividades - 2009 Suma deducciones. Aplicado en esta liquidación [946]
47 708 17 Num Deducc.para incentivar determ.actividades - 2009 Suma deducciones. Pendiente de aplicación [947]
17 Num Deducc.para incentivar determ.actividades - 2010 Inv.protección medio ambiente. Deducción pendiente/generada
48 725 [792]
17 Num Deducc.para incentivar determ.actividades - 2010 Inv.protección medio ambiente. Aplicado en esta liquidación
49 742 [793]
17 Num Deducc.para incentivar determ.actividades - 2010 Inv.protección medio ambiente. Pendiente de aplicación [794]
50 759
17 Num Deducc.para incentivar determ.actividades - 2010 Creación empleo minusválidos. Deducción pendiente/generada
5511 777766 [[779955]]
17 Num Deducc.para incentivar determ.actividades - 2010 Creación empleo minusválidos. Aplicado en esta liquidación
52 793 [796]
17 Num Deducc.para incentivar determ.actividades - 2010 Creación empleo minusválidos. Pendiente de aplicación [797]
53 810
17 Num Deducc.para incentivar determ.actividades - 2010 Gastos investigación y desarrollo. Deducción
54 827 pendiente/generada [798]
17 Num Deducc.para incentivar determ.actividades - 2010 Gastos investigación y desarrollo. Aplicado en esta liquidación
55 844 [799]
17 Num Deducc.para incentivar determ.actividades - 2010 Gastos investigación y desarrollo. Pendiente de aplicación [800]
56 861
17 Num Deducc.para incentivar determ.actividades - 2010 Inv.tecnologías información. Deducción pendiente/generada
57 878 [801]
1177 NNuumm DDeedduucccc.ppaarraa iinncceennttiivvaarr ddeetteerrmm.aaccttiivviiddaaddeess -- 22001100 IInnvv.tteeccnnoollooggííaass iinnffoorrmmaacciióónn. AApplliiccaaddoo eenn eessttaa lliiqquuiiddaacciióónn [[880022]]
58 895
17 Num Deducc.para incentivar determ.actividades - 2010 Inv.tecnologías información. Pendiente de aplicación [803]
59 912
Página 26

# Pag. 27

17 Num Deducc.para incentivar determ.actividades - 2010 Deducc.medidas apoyo transporte. Deducción
60 929 pendiente/generada [804]
17 Num Deducc.para incentivar determ.actividades - 2010 Deducc.medidas apoyo transporte. Aplicado en esta liquidación
61 946 [805]
17 Num Deducc.para incentivar determ.actividades - 2010 Deducc.medidas apoyo transporte. Pendiente de aplicación
62 963 [806]
17 Num Deducc.para incentivar determ.actividades - 2010 Produc.cinematográficas. Deducción pendiente/generada [807]
63 980
17 Num Deducc.para incentivar determ.actividades - 2010 Produc.cinematográficas. Aplicado en esta liquidación [808]
64 997
17 Num Deducc.para incentivar determ.actividades - 2010 Produc.cinematográficas. Pendiente de aplicación [809]
65 1014
17 Num Deducc.para incentivar determ.actividades - 2010 Bienes interés cultural. Deducción pendiente/generada [810]
6666 11003311
17 Num Deducc.para incentivar determ.actividades - 2010 Bienes interés cultural. Aplicado en esta liquidación [811]
67 1048
68 1065 17 Num Deducc.para incentivar determ.actividades - 2010 Bienes interés cultural. Pendiente de aplicación [812]
17 Num Deducc.para incentivar determ.actividades - 2010 Empresas exportadoras. Deducción pendiente/generada [813]
69 1082
17 Num Deducc.para incentivar determ.actividades - 2010 Empresas exportadoras. Aplicado en esta liquidación [814]
70 1099
17 Num Deducc.para incentivar determ.actividades - 2010 Empresas exportadoras. Pendiente de aplicación [815]
71 1116
17 Num Deducc.para incentivar determ.actividades - 2010 Gastos formación profesional. Deducción pendiente/generada
72 1133 [816]
17 Num Deducc.para incentivar determ.actividades - 2010 Gastos formación profesional. Aplicado en esta liquidación [817]
7733 11115500
17 Num Deducc.para incentivar determ.actividades - 2010 Gastos formación profesional. Pendiente de aplicación [818]
74 1167
75 1184 17 Num Deducc.para incentivar determ.actividades - 2010 Edición libros. Deducción pendiente/generada [819]
76 1201 17 Num Deducc.para incentivar determ.actividades - 2010 Edición libros. Aplicado en esta liquidación [820]
77 1218 17 Num Deducc.para incentivar determ.actividades - 2010 Edición libros. Pendiente de aplicación [821]
17 Num Deducc.para incentivar determ.actividades - 2010 Contrib.planes de pensiones. Deducción pendiente/generada
78 1235 [891]
17 Num Deducc.para incentivar determ.actividades - 2010 Contrib.planes de pensiones. Aplicado en esta liquidación [892]
79 1252
17 Num Deducc.para incentivar determ.actividades - 2010 Contrib.planes de pensiones. Pendiente de aplicación [893]
80 1269
17 Num Deducc.para incentivar determ.actividades - 2010 Guarderías para hijos. Deducción pendiente/generada [822]
8811 11228866
17 Num Deducc.para incentivar determ.actividades - 2010 Guarderías para hijos. Aplicado en esta liquidación [823]
82 1303
83 1320 17 Num Deducc.para incentivar determ.actividades - 2010 Guarderías para hijos. Pendiente de aplicación [824]
17 Num Deducc.para incentivar determ.actividades - 2010 Barcelona World Race. Deducción pendiente/generada [993]
84 1337
17 Num Deducc.para incentivar determ.actividades - 2010 Barcelona World Race. Aplicado en esta liquidación [994]
85 1354
86 1371 17 Num Deducc.para incentivar determ.actividades - 2010 Barcelona World Race. Pendiente de aplicación [995]
17 Num Deducc.para incentivar determ.actividades - 2010 33ª Copa del América. Deducción pendiente/generada [177]
87 1388
17 Num Deducc.para incentivar determ.actividades - 2010 33ª Copa del América. Aplicado en esta liquidación [178]
88 1405
8899 11442222 1177 NNum DDedducc.para iincenttiivar ddetterm.acttiiviiddaddes - 22001100 3333ªª CCopa ddell AAméériica. PPenddiientte dde aplliicaciióón [[117799]]
17 Num Deducc.para incentivar determ.actividades - 2010 Guadalquivir Río de Historia. Deducción pendiente/generada
90 1439 [183]
17 Num Deducc.para incentivar determ.actividades - 2010 Guadalquivir Río de Historia. Aplicado en esta liquidación [185]
91 1456
17 Num Deducc.para incentivar determ.actividades - 2010 Guadalquivir Río de Historia. Pendiente de aplicación [186]
92 1473
17 Num Deducc.para incentivar determ.actividades - 2010 Bicentenario Constitución 1812. Deducción pendiente/generada
93 1490 [188]
17 Num Deducc.para incentivar determ.actividades - 2010 Bicentenario Constitución 1812. Aplicado en esta liquidación
94 1507 [189]
17 Num Deducc.para incentivar determ.actividades - 2010 Bicentenario Constitución 1812. Pendiente de aplicación [190]
95 1524
1177 NNuumm DDeedduucccc.ppaarraa iinncceennttiivvaarr ddeetteerrmm.aaccttiivviiddaaddeess - 22001100 PPrrooggrraammaa pprreeppaarraacciióónn ddeeppoorrttiissttaass eessppaaññoolleess. DDeedduucccciióónn
96 1541 pendiente/generada [534]
17 Num Deducc.para incentivar determ.actividades - 2010 Programa preparación deportistas españoles. Aplicado en esta
97 1558 liquidación [535]
17 Num Deducc.para incentivar determ.actividades - 2010 Programa preparación deportistas españoles. Pendiente de
98 1575 aplicación [536]
17 Num Deducc.para incentivar determ.actividades - 2010 Año Santo Xacobeo. Deducción pendiente/generada [537]
99 1592
100 1609 17 Num Deducc.para incentivar determ.actividades - 2010 Año Santo Xacobeo. Aplicado en esta liquidación [538]
101 1626 17 Num Deducc.para incentivar determ.actividades - 2010 Año Santo Xacobeo. Pendiente de aplicación [539]
17 Num Deducc.para incentivar determ.actividades - 2010 IX Centenario Santo Domingo de la Calzada. Deducción
102 1643 pendiente/generada [540]
17 Num Deducc.para incentivar determ.actividades - 2010 IX Centenario Santo Domingo de la Calzada. Aplicado en esta
110033 11666600 lliiqquuiiddaacciióónn [[554411]]
17 Num Deducc.para incentivar determ.actividades - 2010 IX Centenario Santo Domingo de la Calzada. Pendiente de
104 1677 aplicación [542]
17 Num Deducc.para incentivar determ.actividades - 2010 Caravaca jubilar 2010. Deducción pendiente/generada [543]
105 1694
17 Num Deducc.para incentivar determ.actividades - 2010 Caravaca jubilar 2010. Aplicado en esta liquidación [544]
106 1711
107 1728 17 Num Deducc.para incentivar determ.actividades - 2010 Caravaca jubilar 2010. Pendiente de aplicación [545]
17 Num Deducc.para incentivar determ.actividades - 2010 Alzheimer internacional 2011. Deducción pendiente/generada
108 1745 [546]
17 Num Deducc.para incentivar determ.actividades - 2010 Alzheimer internacional 2011. Aplicado en esta liquidación [548]
109 1762
17 Num Deducc.para incentivar determ.actividades - 2010 Alzheimer internacional 2011. Pendiente de aplicación [549]
111100 11777799
17 Num Deducc.para incentivar determ.actividades - 2010 Año Hernandiano. Orihuela 2010. Deducción
111 1796 pendiente/generada [551]
17 Num Deducc.para incentivar determ.actividades - 2010 Año Hernandiano. Orihuela 2010. Aplicado en esta liquidación
112 1813 [580]
Página 27

# Pag. 28

17 Num Deducc.para incentivar determ.actividades - 2010 Año Hernandiano. Orihuela 2010. Pendiente de aplicación [593]
113 1830
17 Num Deducc.para incentivar determ.actividades - 2010 Centenario de la Costa Brava. Deducción pendiente/generada
114 1847 [901]
17 Num Deducc.para incentivar determ.actividades - 2010 Centenario de la Costa Brava. Aplicado en esta liquidación [902]
115 1864
17 Num Deducc.para incentivar determ.actividades - 2010 Centenario de la Costa Brava. Pendiente de aplicación [903]
116 1881
17 Num Deducc.para incentivar determ.actividades - 2010 Symposium 90 Aniversario Salón automóvil Barcelona.
117 1898 Deducción pendiente/generada [917]
17 Num Deducc.para incentivar determ.actividades - 2010 Symposium 90 Aniversario Salón automóvil Barcelona. Aplicado
118 1915 en esta liquidación [918]
17 Num Deducc.para incentivar determ.actividades - 2010 Symposium 90 Aniversario Salón automóvil Barcelona.
111199 11993322 PPenddiientte dde aplliicaciióón [[991199]]
120 1949 17 Num Deducc.para incentivar determ.actividades - 2010 Misteri de ELX . Deducción pendiente/generada [957]
121 1966 17 Num Deducc.para incentivar determ.actividades - 2010 Misteri de ELX . Aplicado en esta liquidación [958]
122 1983 17 Num Deducc.para incentivar determ.actividades - 2010 Misteri de ELX . Pendiente de aplicación [959]
17 Num Deducc.para incentivar determ.actividades - 2010 Año Jubilar Guadalupense 2010 . Deducción
123 2000 pendiente/generada [960]
17 Num Deducc.para incentivar determ.actividades - 2010 Año Jubilar Guadalupense 2010 . Aplicado en esta liquidación
124 2017 [961]
17 Num Deducc.para incentivar determ.actividades - 2010 Año Jubilar Guadalupense 2010 . Pendiente de aplicación [962]
125 2034
17 Num Deducc.para incentivar determ.actividades - 2010 Jornadas Mundiales de la Juventud 2011. Deducción
126 2051 pendiente/generada [963
17 Num Deducc.para incentivar determ.actividades - 2010 Jornadas Mundiales de la Juventud 2011. Aplicado en esta
127 2068 liquidación [964]
17 Num Deducc.para incentivar determ.actividades - 2010 Jornadas Mundiales de la Juventud 2011. Pendiente de
128 2085 aplicación [965]
17 Num Deducc.para incentivar determ.actividades - 2010 Conmemoración Milenio fundación Reino de Granada.
129 2102 Deducción pendiente/generada [966]
17 Num Deducc.para incentivar determ.actividades - 2010 Conmemoración Milenio fundación Reino de Granada. Aplicado
130 2119 en esta liquidación [967]
17 Num Deducc.para incentivar determ.actividades - 2010 Conmemoración Milenio fundación Reino de Granada.
131 2136 Pendiente de aplicación [968]
17 Num Deducc.para incentivar determ.actividades - 2010 Solar Decathlon Europe 2010 y 2012. Deducción
132 2153 pendiente/generada [969
17 Num Deducc.para incentivar determ.actividades - 2010 Solar Decathlon Europe 2010 y 2012. Aplicado en esta
133 2170 liquidación [970]
1177 NNum DDedducc.para iincenttiivar ddetterm.acttiiviiddaddes - 22001100 SSollar DDecatthhllon EEurope 22001100 y 22001122. PPenddiientte dde aplliicaciióón
134 2187 [971]
135 2204 17 Num Deducc.para incentivar determ.actividades - 2010 Alicante 2011. Deducción pendiente/generada [972]
136 2221 17 Num Deducc.para incentivar determ.actividades - 2010 Alicante 2011. Aplicado en esta liquidación [973]
137 2238 17 Num Deducc.para incentivar determ.actividades - 2010 Alicante 2011. Pendiente de aplicación [975]
17 Num Deducc.para incentivar determ.actividades - 2010 Google Lunar X Prize. Deducción pendiente/generada [976]
138 2255
17 Num Deducc.para incentivar determ.actividades - 2010 Google Lunar X Prize. Aplicado en esta liquidación [977]
139 2272
140 2289 17 Num Deducc.para incentivar determ.actividades - 2010 Google Lunar X Prize. Pendiente de aplicación [978]
17 Num Deducc.para incentivar determ.actividades - 2010 Diferimiento 2010 Deducciones. Deducción pendiente/generada
141 2306 [828]
17 Num Deducc.para incentivar determ.actividades - 2010 Diferimiento deducciones. Aplicado en esta liquidación [829]
114422 22332233
17 Num Deducc.para incentivar determ.actividades - 2010 Diferimiento deducciones. Pendiente de aplicación [830]
143 2340
17 Num Deducc.para incentivar determ.actividades - 2010 Total deducciones Cap.IV Tít.VI. Deducción pendiente/generada
144 2357 [831]
17 Num Deducc.para incentivar determ.actividades - 2010 Total deducciones Cap.IV Tít.VI. Aplicado en esta liquidación
145 2374 [588]
17 Num Deducc.para incentivar determ.actividades - 2010 Total deducciones Cap.IV Tít.VI. Pendiente de aplicación [832]
146 2391
147 2408 17 Num Deducc.donativos a entidades sin fines de lucro - 2002 - Deducción pendiente/generada [929]
148 2425 17 Num Deducc.donativos a entidades sin fines de lucro - 2002 - Aplicado en esta declaración [930]
149 2442 17 Num Deducc.donativos a entidades sin fines de lucro - 2002 - Pendiente de aplicación [931]
150 2459 17 Num Deducc.donativos a entidades sin fines de lucro - 2003 - Deducción pendiente/generada [942]
151 2476 17 Num Deducc.donativos a entidades sin fines de lucro - 2003 - Aplicado en esta declaración [943]
152 2493 17 Num Deducc.donativos a entidades sin fines de lucro - 2003 - Pendiente de aplicación [944]
153 2510 17 Num Deducc.donativos a entidades sin fines de lucro - 2004 - Deducción pendiente/generada [294]
154 2527 17 Num Deducc.donativos a entidades sin fines de lucro - 2004 - Aplicado en esta declaración [295]
155 2544 17 Num Deducc.donativos a entidades sin fines de lucro - 2004 - Pendiente de aplicación [296]
156 2561 17 Num Deducc.donativos a entidades sin fines de lucro - 2005 - Deducción pendiente/generada [066]
157 2578 17 Num Deducc.donativos a entidades sin fines de lucro - 2005 - Aplicado en esta declaración [074]
158 2595 17 Num Deducc.donativos a entidades sin fines de lucro - 2005 - Pendiente de aplicación [084]
159 2612 17 Num Deducc.donativos a entidades sin fines de lucro - 2006 - Deducción pendiente/generada [008]
160 2629 17 Num Deducc.donativos a entidades sin fines de lucro - 2006 - Aplicado en esta declaración [009]
161 2646 17 Num Deducc.donativos a entidades sin fines de lucro - 2006 - Pendiente de aplicación [010]
162 2663 17 Num Deducc.donativos a entidades sin fines de lucro - 2007 - Deducción pendiente/generada [034]
116633 22668800 1177 NNuumm DDeedduucccc.ddoonnaattiivvooss aa eennttiiddaaddeess ssiinn ffiinneess ddee lluuccrroo -- 22000077 -- AApplliiccaaddoo eenn eessttaa ddeeccllaarraacciióónn [[003355]]
164 2697 17 Num Deducc.donativos a entidades sin fines de lucro - 2007 - Pendiente de aplicación [036]
165 2714 17 Num Deducc.donativos a entidades sin fines de lucro - 2008 - Deducción pendiente/generada [201]
166 2731 17 Num Deducc.donativos a entidades sin fines de lucro - 2008 - Aplicado en esta declaración [202]
167 2748 17 Num Deducc.donativos a entidades sin fines de lucro - 2008 - Pendiente de aplicación [203]
168 2765 17 Num Deducc.donativos a entidades sin fines de lucro - 2009 - Deducción pendiente/generada [904]
169 2782 17 Num Deducc.donativos a entidades sin fines de lucro - 2009 - Aplicado en esta declaración [905]
170 2799 17 Num Deducc.donativos a entidades sin fines de lucro - 2009 - Pendiente de aplicación [906]
171 2816 17 Num Deducc.donativos a entidades sin fines de lucro - 2010 - Deducción pendiente/generada [990]
172 2833 17 Num Deducc.donativos a entidades sin fines de lucro - 2010 - Aplicado en esta declaración [991]
173 2850 17 Num Deducc.donativos a entidades sin fines de lucro - 2010 - Pendiente de aplicación [992]
174 2867 17 Num Deducc.donativos a entidades sin fines de lucro - Total deducciones donac.sin fines de lucro - Deducción pendiente/generada [598]
175 2884 17 Num Deducc.donativos a entidades sin fines de lucro - Total deducciones donac.sin fines de lucro - Applicado en esta declaración [[565]]
176 2901 17 Num Deducc.donativos a entidades sin fines de lucro - Total deducciones donac.sin fines de lucro - Pendiente de aplicación [895]
177 2918 17 Num Donaciones del período impositivo efectuada a entidades sin fines de lucro [974]
178 2935 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200017>"
Total: 2944
Página 28

# Pag. 29

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "018"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NNuumm AApplliiccaacciióónn ddee rreessuullttaaddooss - BBaassee ddee rreeppaarrttoo. PPéérrddiiddaass yy ggaannaanncciiaass [[665500]]
7 28 17 Num Aplicación de resultados - Base de reparto. Remanente [651]
8 45 17 Num Aplicación de resultados - Base de reparto. Reservas [652]
9 62 17 Num Aplicación de resultados - Base de reparto. Total [653]
10 79 17 Num Aplicación de resultados - Aplicación. A reservas [654]
11 96 17 Num Aplicación de resultados - Aplicación. Intereses aportaciones al capital (Cooperativas) [655]
12 113 17 Num Aplicación de resultados - Aplicación. A dividendos [656]
13 130 17 Num Aplicación de resultados - Aplicación. A dotación O.S. (Cajas de ahorro) [658]
14 147 17 Num Aplicación de resultados - Aplicación. A F.R.O y F.E.P (Cooperativas) [659]
15 164 17 Num Aplicación de resultados - Aplicación. A retornos cooperativos (Cooperativas) [660]
16 181 17 Num Aplicación de resultados - Aplicación. Partícipes (IIC) [662]
17 198 17 Num Aplicación de resultados - Aplicación. A remanente y otros [664]
1188 221155 1177 NNuumm AApplliiccaacciióónn ddee rreessuullttaaddooss -- AApplliiccaacciióónn.. AA ccoommppeessaacciióónn ddee ppéérrddiiddaass ddee eejjeerrcciicciiooss aanntteerriioorreess [[666655]]
19 232 17 Num Aplicación de resultados - Aplicación. Total [666]
20 249 17 Num Correcciones fiscales - Correcciones permanentes. Del ejercicio. Aumentos
21 266 17 Num Correcciones fiscales - Correcciones permanentes. Del ejercicio. Disminuciones
22 283 17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Del ejercicio. Aumentos
23 300 17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Del ejercicio. Disminuciones
24 317 17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Saldo pendiente. Aumentos
25 334 17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Saldo pendiente. Disminuciones
26 351 17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Amortizaciones. Del ejercicio. Aumentos
17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Amortizaciones. Del ejercicio. Disminuciones
27 368
17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Amortizaciones. Saldo pendiente. Aumentos
28 385
1177 NNum CCorrecciiones ffiiscalles - CCorrec.ttemporariias oriigen ejjerciiciio. AAmorttiizaciiones. SSallddo penddiientte. DDiismiinuciiones
29 402
30 419 17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Deterioros valor. Del ejercicio. Aumentos
17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Deterioros valor. Del ejercicio. Disminuciones
31 436
17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Deterioros valor. Saldo pendiente. Aumentos
32 453
17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Deterioros valor. Saldo pendiente. Disminuciones
33 470
34 487 17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Pensiones. Del ejercicio. Aumentos
35 504 17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Pensiones. Del ejercicio. Disminuciones
36 521 17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Pensiones. Saldo pendiente. Aumentos
17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Pensiones. Saldo pendiente. Disminuciones
3377 553388
17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Fondo de comercio. Del ejercicio. Aumentos
38 555
17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Fondo de comercio. Del ejercicio. Disminuciones
39 572
17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Fondo de comercio. Saldo pendiente. Aumentos
40 589
17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Fondo de comercio. Saldo pendiente. Disminuciones
41 606
42 623 17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Resto. Aumentos
43 640 17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Resto. Disminuciones
44 657 17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Resto. Saldo pendiente. Aumentos
45 674 17 Num Correcciones fiscales - Correc.temporarias origen ejercicio. Resto. Saldo pendiente. Disminuciones
46 691 17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Del ejercicio. Aumentos
47 708 17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Del ejercicio. Disminuciones
48 725 17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Saldo pendiente. Aumentos
49 742 17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Saldo pendiente. Disminuciones
17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Amortizaciones. Del ejercicio. Aumentos
50 759
17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Amortizaciones. Del ejercicio. Disminuciones
51 776
17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Amortizaciones. Saldo pendiente. Aumentos
52 793
17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Amortizaciones. Saldo pendiente.
53 810 Disminuciones
17 Num Correcciones fiscales - Correc.tempporarias origgen ejjerc.anteriores. Deterioros valor. Del ejjercicio. Aumentos
54 827
17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Deterioros valor. Del ejercicio. Disminuciones
55 844
17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Deterioros valor. Saldo pendiente. Aumentos
56 861
17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Deterioros valor. Saldo pendiente.
57 878 Disminuciones
58 895 17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Pensiones. Del ejercicio. Aumentos
17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Pensiones. Del ejercicio. Disminuciones
59 912
17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Pensiones. Saldo pendiente. Aumentos
60 929
17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Pensiones. Saldo pendiente. Disminuciones
61 946
17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Fondo de comercio. Del ejercicio. Aumentos
62 963
Página 29

# Pag. 30

17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Fondo de comercio. Del ejercicio.
63 980 Disminuciones
17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Fondo de comercio. Saldo pendiente.
64 997 Aumentos
17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Fondo de comercio. Saldo pendiente.
65 1014 Disminuciones
66 1031 17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Resto. Aumentos
67 1048 17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Resto. Disminuciones
68 1065 17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Resto. Saldo pendiente. Aumentos
17 Num Correcciones fiscales - Correc.temporarias origen ejerc.anteriores. Resto. Saldo pendiente. Disminuciones
69 1082
70 1099 17 Num Correcciones fiscales - Total correcciones resultado contable. Del ejercicio. Aumentos [417]
7711 11111166 17 Num Correcciones fiscales - Total correcciones resultado contable. Del ejjercicio. Disminuciones [[418]]
72 1133 17 Num Correcciones fiscales - Total correcciones resultado contable. Saldo pendiente. Aumentos
73 1150 17 Num Correcciones fiscales - Total correcciones resultado contable. Saldo pendiente. Disminuciones
74 1167 22 An Presentación de documentación previa en la sede electrónica. NRS1
75 1189 22 An Presentación de documentación previa en la sede electrónica. NRS2
76 1211 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200018>"
Total: 1220
Página 30

# Pag. 31

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas
vers. 1.0
constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An C Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num C Modelo. OBLIGATORIO Constante "200"
3 6 3 An C Página. OBLIGATORIO Constante "019"
4 9 1 An C Fin de identificador de modelo. OBLIGATORIO Constante ">"
1 An C Indicador de página complementaria
BBllaannccoo ((NNoo
complementaria) o
5 10 "C" (Complementaria)
6 11 20 An C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 1.Descripción de la operación
20 An C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 1. Persona o entidad
7 31
8 51 1 A C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 1.F/J F - J
9 52 2 A C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 1. Clave país/territorio
10 54 17 N C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 1. Importe
11 71 20 An C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 2.Descripción de la operación
12 91 20 An C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 2. Persona o entidad
13 111 1 A C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 2.F/J F - J
14 112 2 A C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 2. Clave país/territorio
15 114 17 N C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 2. Importe
16 131 20 An C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 3.Descripción de la operación
17 151 20 An C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 3. Persona o entidad
18 171 1 A C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 3.F/J F - J
19 172 2 A C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 3. Clave país/territorio
20 174 17 N C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 3. Importe
21 191 20 An C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 4.Descripción de la operación
22 211 20 An C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 4. Persona o entidad
23 231 1 A C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 4.F/J F - J
24 232 2 A C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 4. Clave país/territorio
25 234 17 N C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 4. Importe
26 251 20 An C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 5.Descripción de la operación
27 271 20 An C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 5. Persona o entidad
28 291 1 A C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 5.F/J F - J
29 292 2 A C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 5. Clave país/territorio
30 294 17 N C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 5. Importe
31 311 20 An C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 6.Descripción de la operación
32 331 20 An C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 6. Persona o entidad
33 351 1 A C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 6.F/J F - J
34 352 2 A C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 6. Clave país/territorio
35 354 17 N C Operaciones y situaciones - Operaciones relacionadas con paraísos fiscales. 6. Importe
36 371 1 A C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 1. Tipo A - B - C
37 372 23 An C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 1. Entidad participada
38 395 2 A C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 1. Clave país/territorio
39 397 17 N C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 1. Valor adquisición
40 414 5 Num C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 1. % participación
4411 441199 1 A C Opperaciones yy situaciones - Tenencia valores con pparaísos fiscales. 2. Tippo A - B - C
42 420 23 An C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 2. Entidad participada
43 443 2 A C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 2. Clave país/territorio
44 445 17 N C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 2. Valor adquisición
45 462 5 Num C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 2. % participación
46 467 1 A C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 3. Tipo A - B - C
47 468 23 An C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 3. Entidad participada
48 491 2 A C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 3. Clave país/territorio
49 493 17 N C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 3. Valor adquisición
50 510 5 Num C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 3. % participación
51 515 1 A C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 4. Tipo A - B - C
52 516 23 An C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 4. Entidad participada
53 539 2 A C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 4. Clave país/territorio
5544 554411 1177 NN CC OOppeerraacciioonneess yy ssiittuuaacciioonneess - TTeenneenncciiaa vvaalloorreess ccoonn ppaarraaííssooss ffiissccaalleess.. 44.. VVaalloorr aaddqquuiissiicciióónn
55 558 5 Num C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 4. % participación
56 563 1 A C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 5. Tipo A - B - C
57 564 23 An C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 5. Entidad participada
58 587 2 A C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 5. Clave país/territorio
59 589 17 N C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 5. Valor adquisición
60 606 5 Num C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 5. % participación
61 611 1 A C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 6. Tipo A - B - C
62 612 23 An C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 6. Entidad participada
63 635 2 A C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 6. Clave país/territorio
64 637 17 N C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 6. Valor adquisición
65 654 5 Num C Operaciones y situaciones - Tenencia valores con paraísos fiscales. 6. % participación
66 659 17 N Comunicación importe neto cifra negocios - Grupos de sociedades. Importe neto cifra negocios [987]
6677 667766 99 AAnn CC CCoommuunniiccaacciióónn iimmppoorrttee nneettoo cciiffrraa nneeggoocciiooss - GGrruuppooss ddee ssoocciieeddaaddeess.. NNIIFF [[11]]
68 685 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF [2]
69 694 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF [3]
70 703 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF [4]
71 712 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF [5]
72 721 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF [6]
73 730 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF [7]
74 739 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF [8]
75 748 9 An C Comunicación importe neto cifra negocios - Grupos de sociedades. NIF [9]
76 757 17 N Comunicación importe neto cifra negocios - No residentes más de un establecimiento. Importe neto [988]
77 774 3 Num Comunicación importe neto cifra negocios - No residentes más de un establecimiento. Nº establecimientos
78 777 9 An C Comunicación importe neto cifra negocios - No residentes más de un establecimiento. NIF [1]
79 786 9 An C Comunicación importe neto cifra negocios - No residentes más de un establecimiento. NIF [2]
8800 779955 99 AAnn CC CCoommuunniiccaacciióónn iimmppoorrttee nneettoo cciiffrraa nneeggoocciiooss -- NNoo rreessiiddeenntteess mmááss ddee uunn eessttaabblleecciimmiieennttoo. NNIIFF [[33]]
81 804 9 An C Comunicación importe neto cifra negocios - No residentes más de un establecimiento. NIF [4]
82 813 9 An C Comunicación importe neto cifra negocios - No residentes más de un establecimiento. NIF [5]
83 822 17 N Comunicación importe neto cifra negocios - Entidades de crédito. Importe neto [989]
84 839 4 Num Rég. Entidades navieras. Nº de buques [N1]
Página 31

# Pag. 32

85 843 17 Num Rég. Entidades navieras. Base imponible resultante de aplicar la escala [630]
86 860 17 Num Rég. Entidades navieras. Importe rentas generadas [631]
87 877 17 Num Rég. Entidades navieras. Compensación bases imponibles negativas [632]
88 894 17 Num Rég. Entidades navieras. Base imponible resultante de la aplicación del régimen [579]
89 911 10 An C Identificador de fin de registro OBLIGATORIO Constante "</T200019>"
Total: 920
Página 32

# Pag. 33

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas
vers. 1.0
constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "020"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
1 An Indicador de página complementaria
Blanco (No
compplementaria)) o
5 10 "C" (Complementaria)
6 11 15 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. NIF
7 26 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. F/J
8 27 40 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Apellidos y nombre
9 67 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Tipo vinculación A a L
10 68 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Código provincia/país
11 70 2 Num C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Tipo operación 1 a 13
12 72 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Ingreso/Pago "I" "P"
13 73 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Método valoración 1a 1b 1c 2a 2b
14 75 17 N C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 1. Importe operación
15 92 15 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. NIF
16 107 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2.F/J
17 108 40 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Apellidos y nombre
1188 114488 11 AA CC OOppeerraacciioonneess ccoonn ppeerrssoonnaass oo eennttiiddaaddeess vviinnccuullaaddaass - PPeerrssoonnaa oo eennttiiddaadd vviinnccuullaaddaa 22. TTiippoo vviinnccuullaacciióónn AA aa LL
19 149 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Código provincia/país
20 151 2 Num C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Tipo operación 1 a 13
21 153 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Ingreso/Pago "I" "P"
22 154 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Método valoración 1a 1b 1c 2a 2b
23 156 17 N C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 2. Importe operación
24 173 15 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. NIF
25 188 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. F/J
26 189 40 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Apellidos y nombre
27 229 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Tipo vinculación A a L
28 230 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Código provincia/país
29 232 2 Num C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Tipo operación 1 a 13
30 234 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Ingreso/Pago "I" "P"
3311 223355 22 AAnn CC OOppeerraacciioonneess ccoonn ppeerrssoonnaass oo eennttiiddaaddeess vviinnccuullaaddaass -- PPeerrssoonnaa oo eennttiiddaadd vviinnccuullaaddaa 33.. MMééttooddoo vvaalloorraacciióónn 11aa 11bb 11cc 22aa 22bb
32 237 17 N C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 3. Importe operación
33 254 15 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. NIF
34 269 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. F/J
35 270 40 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Apellidos y nombre
36 310 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Tipo vinculación A a L
37 311 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Código provincia/país
38 313 2 Num C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Tipo operación 1 a 13
39 315 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Ingreso/Pago "I" "P"
40 316 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Método valoración 1a 1b 1c 2a 2b
41 318 17 Num C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 4. Importe operación
42 335 15 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. NIF
43 350 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. F/J
44 351 40 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. Apellidos y nombre
45 391 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. Tipo vinculación A a L
46 392 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. Código provincia/país
47 394 2 Num C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. Tipo operación 1 a 13
48 396 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. Ingreso/Pago "I" "P"
49 397 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. Método valoración 1a 1b 1c 2a 2b
50 399 17 N C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 5. Importe operación
51 416 15 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 6. NIF
52 431 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 6. F/J
53 432 40 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 6. Apellidos y nombre
54 472 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 6. Tipo vinculación A a L
55 473 2 An C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 6. Código provincia/país
56 475 2 Num C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 6. Tipo operación 1 a 13
57 477 1 A C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 6. Ingreso/Pago "I" "P"
5588 447788 22 AAnn CC OOppeerraacciioonneess ccoonn ppeerrssoonnaass oo eennttiiddaaddeess vviinnccuullaaddaass - PPeerrssoonnaa oo eennttiiddaadd vviinnccuullaaddaa 66. MMééttooddoo vvaalloorraacciióónn 11aa 11bb 11cc 22aa 22bb
59 480 17 N C Operaciones con personas o entidades vinculadas - Persona o entidad vinculada 6. Importe operación
60 497 17 Num Rég. cooperativas - Determ.base imponible. Ingresos computables. Resultados cooperativos [C1]
61 514 17 Num Rég. cooperativas - Determ.base imponible. Ingresos computables. Resultados extracooperativos [E1]
62 531 17 Num Rég. cooperativas - Determ.base imponible. Gastos específicos. Resultados cooperativos [C2]
63 548 17 Num Rég. cooperativas - Determ.base imponible. Gastos específicos. Resultados extracooperativos [E2]
64 565 17 Num Rég. cooperativas - Determ.base imponible. Gastos generales. Resultados cooperativos [C3]
65 582 17 Num Rég. cooperativas - Determ.base imponible. Gastos generales. Resultados extracooperativos [E3]
17 Num Rég. cooperativas - Determ.base imponible. Gastos Fondo de Educación y Promoción. Resultados cooperativos
66 599 [C4]
17 Num Rég. cooperativas - Determ.base imponible. Gastos Fondo de Educación y Promoción. Resultados
67 616 extracooperativos [E4]
17 N Rég. cooperativas - Determ.base imponible. Incrementos y disminuciones patrimoniales. Resultados
6688 663333 extracooperativos [E5]
69 650 17 N Rég. cooperativas - Determ.base imponible. Resultado. Resultados cooperativos [C6]
70 667 17 N Rég. cooperativas - Determ.base imponible. Resultado. Resultados extracooperativos [E6]
71 684 17 Num Rég. cooperativas - Determ.base imponible. Aumentos. Resultados cooperativos [C7]
72 701 17 Num Rég. cooperativas - Determ.base imponible. Aumentos. Resultados extracooperativos [E7]
73 718 17 Num Rég. cooperativas - Determ.base imponible. Disminuciones. Resultados cooperativos [C8]
74 735 17 Num Rég. cooperativas - Determ.base imponible. Disminuciones. Resultados extracooperativos [E8]
75 752 17 Num Rég. cooperativas - Determ.base imponible. 50% Dotación obligatoria. Resultados cooperativos [C9]
76 769 17 Num Rég. cooperativas - Determ.base imponible. 50% Dotación obligatoria. Resultados extracooperativos [E9]
77 786 17 N Rég. cooperativas - Determ.base imponible. Reserva inversiones Canarias. Resultados cooperativos [C10]
78 803 17 N Rég. cooperativas - Determ.base imponible. Factor de agotamiento. Resultados cooperativos [C11]
79 820 17 N Rég. cooperativas - Determ.base imponible. Factor de agotamiento. Resultados extracooperativos [E11]
80 837 17 N Rég. cooperativas - Determ.base imponible. Base imponible Resultados cooperativos [553]
81 854 17 N Rég. cooperativas - Determ.base imponible. Base imponible Resultados extracooperativos [554]
82 871 1177 NNum RRéég. cooperattiivas - DDettalllle compensaciióón cuottas. 11999955 PPenddiientte aplliicaciióón all priinciipiio ddell periioddo [[667733]]
83 888 17 Num Rég. cooperativas - Detalle compensación cuotas. 1995 Aplicado en esta liquidación [674]
17 Num Rég. cooperativas - Detalle compensación cuotas. 1996 Pendiente aplicación al principio del periodo [676]
84 905
Página 33

# Pag. 34

85 922 17 Num Rég. cooperativas - Detalle compensación cuotas. 1996 Aplicado en esta liquidación [677]
17 Num Rég. cooperativas - Detalle compensación cuotas. 1996 Pendiente aplicación en ejercicios futuros [678]
86 939
17 Num Rég. cooperativas - Detalle compensación cuotas. 1997 Pendiente aplicación al principio del periodo [679]
87 956
88 973 17 Num Rég. cooperativas - Detalle compensación cuotas. 1997 Aplicado en esta liquidación [680]
17 Num Rég. cooperativas - Detalle compensación cuotas. 1997 Pendiente aplicación en ejercicios futuros [681]
89 990
17 Num Rég. cooperativas - Detalle compensación cuotas. 1998 Pendiente aplicación al principio del periodo [682]
90 1007
91 1024 17 Num Rég. cooperativas - Detalle compensación cuotas. 1998 Aplicado en esta liquidación [683]
17 Num Rég. cooperativas - Detalle compensación cuotas. 1998 Pendiente aplicación en ejercicios futuros [684]
92 1041
17 Num Rég. cooperativas - Detalle compensación cuotas. 1999 Pendiente aplicación al principio del periodo [685]
9933 11005588
94 1075 17 Num Rég. cooperativas - Detalle compensación cuotas. 1999 Aplicado en esta liquidación [686]
17 Num Rég. cooperativas - Detalle compensación cuotas. 1999 Pendiente aplicación en ejercicios futuros [687]
95 1092
17 Num Rég. cooperativas - Detalle compensación cuotas. 2000 Pendiente aplicación al principio del periodo [688]
96 1109
97 1126 17 Num Rég. cooperativas - Detalle compensación cuotas. 2000 Aplicado en esta liquidación [689]
17 Num Rég. cooperativas - Detalle compensación cuotas. 2000 Pendiente aplicación en ejercicios futuros [690]
98 1143
17 Num Rég. cooperativas - Detalle compensación cuotas. 2001 Pendiente aplicación al principio del periodo [691]
99 1160
100 1177 17 Num Rég. cooperativas - Detalle compensación cuotas. 2001 Aplicado en esta liquidación [692]
17 Num Rég. cooperativas - Detalle compensación cuotas. 2001 Pendiente aplicación en ejercicios futuros [693]
101 1194
1177 NNuumm RRéégg.. ccooooppeerraattiivvaass - DDeettaallllee ccoommppeennssaacciióónn ccuuoottaass.. 22000022 PPeennddiieennttee aapplliiccaacciióónn aall pprriinncciippiioo ddeell ppeerriiooddoo [[662233]]
102 1211
103 1228 17 Num Rég. cooperativas - Detalle compensación cuotas. 2002 Aplicado en esta liquidación [624]
17 Num Rég. cooperativas - Detalle compensación cuotas. 2002 Pendiente aplicación en ejercicios futuros [672]
104 1245
17 Num Rég. cooperativas - Detalle compensación cuotas. 2003 Pendiente aplicación al principio del periodo [279]
105 1262
106 1279 17 Num Rég. cooperativas - Detalle compensación cuotas. 2003 Aplicado en esta liquidación [280]
17 Num Rég. cooperativas - Detalle compensación cuotas. 2003 Pendiente aplicación en ejercicios futuros [281]
107 1296
17 Num Rég. cooperativas - Detalle compensación cuotas. 2004 Pendiente aplicación al principio del periodo [587]
108 1313
109 1330 17 Num Rég. cooperativas - Detalle compensación cuotas. 2004 Aplicado en esta liquidación [515]
17 Num Rég. cooperativas - Detalle compensación cuotas. 2004 Pendiente aplicación en ejercicios futuros [900]
110 1347
17 Num Rég. cooperativas - Detalle compensación cuotas. 2005 Pendiente aplicación al principio del periodo [059]
111 1364
112 1381 17 Num Rég. cooperativas - Detalle compensación cuotas. 2005 Aplicado en esta liquidación [099]
17 Num Rég. cooperativas - Detalle compensación cuotas. 2005 Pendiente aplicación en ejercicios futuros [100]
113 1398
17 Num Rég. cooperativas - Detalle compensación cuotas. 2006 Pendiente aplicación al principio del periodo [017]
114 1415
115 1432 17 Num Rég. cooperativas - Detalle compensación cuotas. 2006 Aplicado en esta liquidación [018]
17 Num Rég. cooperativas - Detalle compensación cuotas. 2006 Pendiente aplicación en ejercicios futuros [019]
116 1449
17 Num Rég. cooperativas - Detalle compensación cuotas. 2007 Pendiente aplicación al principio del periodo [772]
117 1466
118 1483 17 Num Rég. cooperativas - Detalle compensación cuotas. 2007 Aplicado en esta liquidación [773]
17 Num Rég. cooperativas - Detalle compensación cuotas. 2007 Pendiente aplicación en ejercicios futuros [777]
111199 11550000
17 Num Rég. cooperativas - Detalle compensación cuotas. 2008 Pendiente aplicación al principio del periodo [907]
120 1517
121 1534 17 Num Rég. cooperativas - Detalle compensación cuotas. 2008 Aplicado en esta liquidación [908]
17 Num Rég. cooperativas - Detalle compensación cuotas. 2008 Pendiente aplicación en ejercicios futuros [909]
122 1551
17 Num Rég. cooperativas - Detalle compensación cuotas. 2009 Pendiente aplicación al principio del periodo [910]
123 1568
124 1585 17 Num Rég. cooperativas - Detalle compensación cuotas. 2009 Aplicado en esta liquidación [911]
17 Num Rég. cooperativas - Detalle compensación cuotas. 2009 Pendiente aplicación en ejercicios futuros [912]
125 1602
17 Num Rég. cooperativas - Detalle compensación cuotas. 2010 Pendiente aplicación al principio del periodo [935]
126 1619
127 1636 17 Num Rég. cooperativas - Detalle compensación cuotas. 2010 Aplicado en esta liquidación [936]
1177 NNuumm RRéégg.. ccooooppeerraattiivvaass - DDeettaallllee ccoommppeennssaacciióónn ccuuoottaass.. 22001100 PPeennddiieennttee aapplliiccaacciióónn eenn eejjeerrcciicciiooss ffuuttuurrooss [[993377]]
128 1653
17 Num Rég. cooperativas - Detalle compensación cuotas. Total. Pendiente aplicación al principio del periodo [694]
129 1670
130 1687 17 Num Rég. cooperativas - Detalle compensación cuotas. Total. Aplicado en esta liquidación [561]
17 Num Rég. cooperativas - Detalle compensación cuotas. Total. Pendiente aplicación en ejercicios futuros [695]
131 1704
132 1721 10 An C Identificador de fin de registro OBLIGATORIO Constante "</T200020>"
Total: 1730
Página 34

# Pag. 35

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas
vers. 1.0
constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An C Inicio del identificador de modelo y página. Constante "<T"
2 3 3 Num C Modelo. Constante "200"
3 6 3 An C Página. Constante "021"
4 9 1 An C Fin de identificador de modelo. Constante ">"
An C Indicador de página complementaria.
Blanco (No
ccoommpplleemmeennttaarriiaa)) oo
5 10 1 "C" (Complementaria)
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
51 801 10 An C Identificador de fin de registro OBLIGATORIO Constante </T200021>
Total: 810
Página 35

# Pag. 36

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas
vers. 1.0
constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An C Inicio del identificador de modelo y página. Constante "<T"
2 3 3 Num C Modelo. Constante "200"
3 6 3 An C Página. Constante "022"
4 9 1 An C Fin de identificador de modelo. Constante ">"
An C Indicador de página complementaria.
Blanco (No
ccoommpplleemmeennttaarriiaa)) oo
5 10 1 "C" (Complementaria)
6 11 7 Num Agrup.interés económico y UTES - Porcentaje de imputación de bases imponibles [060]
7 18 17 N Agrup.interés económico y UTES - Modelo de información. Resultado contable [500]
8 35 17 N Agrup.interés económico y UTES - Modelo de información. Base imponible [552]
9 52 17 Num C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición interna 1. Base
10 69 40 An C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición interna 1. Tipo
11 109 5 Num C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición interna 1. %
12 114 17 Num C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición interna 2. Base
13 131 40 An C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición interna 2. Tipo
14 171 5 Num C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición interna 2. %
15 176 17 Num C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición interna 3. Base
16 193 40 An C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición interna 3. Tipo
17 233 5 Num C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición interna 3. %
18 238 17 Num C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición interna 4. Base
19 255 40 An C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición interna 4. Tipo
20 295 5 Num C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición interna 4. %
21 300 17 Num C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición internacional 1.
22 317 5 Num C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición internacional 1. %
23 322 17 Num C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición internacional 2.
24 339 5 Num C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición internacional 2. %
25 344 17 Num C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición internacional 3.
26 361 5 Num C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición internacional 3. %
27 366 17 Num C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición internacional 4.
28 383 5 Num C Agrup.interés económico y UTES - Modelo de información. Deduc.evitar doble imposición internacional 4. %
29 388 17 Num Agrup.interés económico y UTES - Modelo de información. Base bonificaciones
30 405 17 Num Agrup.interés económico y UTES - Modelo de información. Base deducciones
3311 442222 1177 NNuumm AAggrruupp.iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS -- MMooddeelloo ddee iinnffoorrmmaacciióónn. RReetteenncciioonneess ee iinnggrreessooss aa ccuueennttaa [[006622]]
32 439 17 Num Agrup.interés económico y UTES - Modelo de información. Dividendos y participaciones. Ejercicios que no
33 456 17 Num Agrup.interés económico y UTES - Modelo de información. Dividendos y participaciones. Ejercicios que haya
34 473 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 1. NIF
35 482 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 1. Rpte.
36 483 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 1. F/J F -J
37 484 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 1. R/X R -X
38 485 34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 1. Apellidos y nombre
39 519 2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 1. Código provincia/país
40 521 17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 1. Base imponible
41 538 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 1. % partic.
42 545 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 2. NIF
43 554 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 2. Rpte.
44 555 1 A C Aggrupp.interés económico yy UTES - Modelo de información. Relación de socios 2. F/J F -J
45 556 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 2. R/X R -X
46 557 34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 2. Apellidos y nombre
47 591 2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 2. Código provincia/país
48 593 17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 2. Base imponible
49 610 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 2. % partic.
50 617 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 3. NIF
51 626 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 3. Rpte.
52 627 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 3. F/J F -J
53 628 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 3. R/X R -X
54 629 34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 3. Apellidos y nombre
55 663 2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 3. Código provincia/país
56 665 17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 3. Base imponible
57 682 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 3. % partic.
5588 668899 99 AAnn CC AAggrruupp.iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS - MMooddeelloo ddee iinnffoorrmmaacciióónn. RReellaacciióónn ddee ssoocciiooss 44. NNIIFF
59 698 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 4. Rpte.
60 699 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 4. F/J F -J
61 700 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 4. R/X R -X
62 701 34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 4. Apellidos y nombre
63 735 2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 4. Código provincia/país
64 737 17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 4. Base imponible
65 754 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 4. % partic.
66 761 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 5. NIF
67 770 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 5. Rpte.
68 771 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 5. F/J F -J
69 772 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 5. R/X R -X
70 773 34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 5. Apellidos y nombre
7711 880077 2 An CC Aggrupp.interés económico yy UUTESS - Modelo de información. Relación de socios 55. CCódiggo pprovincia//ppaís
72 809 17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 5. Base imponible
73 826 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 5. % partic.
74 833 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 6. NIF
75 842 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 6. Rpte.
76 843 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 6. F/J F -J
77 844 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 6. R/X R -X
78 845 34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 6. Apellidos y nombre
79 879 2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 6. Código provincia/país
80 881 17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 6. Base imponible
81 898 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 6. % partic.
82 905 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 7. NIF
83 914 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 7. Rpte.
84 915 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 7. F/J F -J
8855 991166 11 AA CC AAggrruupp.iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS - MMooddeelloo ddee iinnffoorrmmaacciióónn. RReellaacciióónn ddee ssoocciiooss 77. RR//XX RR -XX
Página 36

# Pag. 37

34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 7. Apellidos y nombre
86 917
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 7. Código provincia/país
87 951
88 953 17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 7. Base imponible
89 970 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 7. % partic.
90 977 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 8. NIF
91 986 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 8. Rpte.
92 987 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 8. F/J F -J
93 988 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 8. R/X R -X
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 8. Apellidos y nombre
94 989
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 8. Código provincia/país
95 1023
9966 11002255 1177 NN CC AAgrup.iintteréés econóómiico y UUTTEESS - MModdello dde iinfformaciióón. RRellaciióón dde sociios 88. BBase iimponiibblle
97 1042 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 8. % partic.
98 1049 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 9. NIF
99 1058 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 9. Rpte.
100 1059 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 9. F/J F -J
101 1060 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 9. R/X R -X
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 9. Apellidos y nombre
102 1061
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 9. Código provincia/país
103 1095
104 1097 17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 9. Base imponible
105 1114 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 9. % partic.
106 1121 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 10. NIF
107 1130 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 10. Rpte.
110088 11113311 11 AA CC AAggrruupp.iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS - MMooddeelloo ddee iinnffoorrmmaacciióónn. RReellaacciióónn ddee ssoocciiooss 1100. FF//JJ FF -JJ
109 1132 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 10. R/X R -X
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 10. Apellidos y nombre
110 1133
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 10. Código provincia/país
111 1167
17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 10. Base imponible
112 1169
113 1186 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 10. % partic.
114 1193 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 11. NIF
115 1202 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 11. Rpte.
116 1203 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 11. F/J F -J
117 1204 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 11. R/X R -X
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 11. Apellidos y nombre
111188 11220055
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 11. Código provincia/país
119 1239
17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 11. Base imponible
120 1241
121 1258 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 11. % partic.
122 1265 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 12. NIF
123 1274 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 12. Rpte.
124 1275 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 12. F/J F -J
125 1276 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 12. R/X R -X
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 12. Apellidos y nombre
126 1277
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 12. Código provincia/país
127 1311
17 N C Aggrupp.interés económico yy UTES - Modelo de información. Relación de socios 12. Base impponible
128 1313
129 1330 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 12. % partic.
130 1337 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 13. NIF
131 1346 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 13. Rpte.
132 1347 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 13. F/J F -J
133 1348 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 13. R/X R -X
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 13. Apellidos y nombre
134 1349
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 13. Código provincia/país
135 1383
17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 13. Base imponible
136 1385
137 1402 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 13. % partic.
138 1409 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 14. NIF
139 1418 1 Num CC Agrup.interés económico y UTESS - Modelo de infformación. Relación de socios 14. Rpte.
140 1419 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 14. F/J F -J
141 1420 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 14. R/X R -X
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 14. Apellidos y nombre
142 1421
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 14. Código provincia/país
143 1455
17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 14. Base imponible
144 1457
145 1474 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 14. % partic.
146 1481 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 15. NIF
147 1490 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 15. Rpte.
148 1491 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 15. F/J F -J
149 1492 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 15. R/X R -X
3344 AAnn CC AAggrruupp.iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS - MMooddeelloo ddee iinnffoorrmmaacciióónn. RReellaacciióónn ddee ssoocciiooss 1155. AAppeelllliiddooss yy nnoommbbrree
150 1493
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 15. Código provincia/país
151 1527
17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 15. Base imponible
152 1529
153 1546 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 15. % partic.
154 1553 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 16. NIF
155 1562 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 16. Rpte.
156 1563 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 16. F/J F -J
157 1564 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 16. R/X R -X
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 16. Apellidos y nombre
158 1565
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 16. Código provincia/país
115599 11559999
Página 37

# Pag. 38

17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 16. Base imponible
160 1601
161 1618 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 16. % partic.
162 1625 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 17. NIF
163 1634 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 17. Rpte.
164 1635 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 17. F/J F -J
165 1636 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 17. R/X R -X
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 17. Apellidos y nombre
166 1637
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 17. Código provincia/país
167 1671
17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 17. Base imponible
168 1673
169 1690 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 17. % partic.
117700 11669977 99 AAn CC AAgrup.iintteréés econóómiico y UUTTEESS - MModdello dde iinfformaciióón. RRellaciióón dde sociios 1188. NNIIFF
171 1706 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 18. Rpte.
172 1707 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 18. F/J F -J
173 1708 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 18. R/X R -X
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 18. Apellidos y nombre
174 1709
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 18. Código provincia/país
175 1743
17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 18. Base imponible
176 1745
177 1762 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 18. % partic.
178 1769 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 19. NIF
179 1778 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 19. Rpte.
180 1779 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 19. F/J F -J
118811 11778800 11 AA CC AAggrruupp.iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS - MMooddeelloo ddee iinnffoorrmmaacciióónn. RReellaacciióónn ddee ssoocciiooss 1199. RR//XX RR -XX
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 19. Apellidos y nombre
182 1781
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 19. Código provincia/país
183 1815
17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 19. Base imponible
184 1817
185 1834 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 19. % partic.
186 1841 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 20. NIF
187 1850 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 20. Rpte.
188 1851 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 20. F/J F -J
189 1852 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 20. R/X R -X
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 20. Apellidos y nombre
190 1853
22 AAnn CC AAggrruupp..iinntteerrééss eeccoonnóómmiiccoo yy UUTTEESS - MMooddeelloo ddee iinnffoorrmmaacciióónn.. RReellaacciióónn ddee ssoocciiooss 2200.. CCóóddiiggoo pprroovviinncciiaa//ppaaííss
191 1887
17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 20. Base imponible
192 1889
193 1906 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 20. % partic.
194 1913 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 21. NIF
195 1922 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 21. Rpte.
196 1923 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 21. F/J F -J
197 1924 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 21. R/X R -X
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 21. Apellidos y nombre
198 1925
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 21. Código provincia/país
199 1959
17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 21. Base imponible
200 1961
201 1978 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 21. % partic.
202 1985 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 22. NIF
203 1994 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 22. Rpte.
204 1995 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 22. F/J F -J
205 1996 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 22. R/X R -X
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 22. Apellidos y nombre
206 1997
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 22. Código provincia/país
207 2031
17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 22. Base imponible
208 2033
209 2050 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 22. % partic.
210 2057 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 23. NIF
211 2066 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 23. Rpte.
221122 22006677 11 AA CC AAgrup.iintteréés econóómiico y UUTTEESS - MModdello dde iinfformaciióón. RRellaciióón dde sociios 2233. FF//JJ FF -JJ
213 2068 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 23. R/X R -X
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 23. Apellidos y nombre
214 2069
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 23. Código provincia/país
215 2103
17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 23. Base imponible
216 2105
217 2122 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 23. % partic.
218 2129 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 24. NIF
219 2138 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 24. Rpte.
220 2139 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 24. F/J F -J
221 2140 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 24. R/X R -X
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 24. Apellidos y nombre
222222 22114411
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 24. Código provincia/país
223 2175
17 N C Agrup.interés económico y UTES - Modelo de información. Relación de socios 24. Base imponible
224 2177
225 2194 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 24. % partic.
226 2201 9 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 25. NIF
227 2210 1 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 25. Rpte.
228 2211 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 25. F/J F -J
229 2212 1 A C Agrup.interés económico y UTES - Modelo de información. Relación de socios 25. R/X R -X
34 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 25. Apellidos y nombre
230 2213
2 An C Agrup.interés económico y UTES - Modelo de información. Relación de socios 25. Código provincia/país
231 2247
17 N CC Aggruupp.intteerééss eeccoonóómiccoo yy UUTESS - Mooddeeloo ddee infoormaaccióón. Reelaaccióón ddee ssoocciooss 255. Baassee imppoonibblee
232 2249
233 2266 7 Num C Agrup.interés económico y UTES - Modelo de información. Relación de socios 25. % partic.
234 2273 10 An C Identificador de fin de registro OBLIGATORIO Constante </T200022>
Total: 2282
Página 38

# Pag. 39

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas
vers. 1.0
constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An C Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num C Modelo. OBLIGATORIO Constante "200"
3 6 3 An C Página. OBLIGATORIO Constante "023"
4 9 1 An C Fin de identificador de modelo. OBLIGATORIO Constante ">"
1 An C Indicador de página complementaria
BBllaannccoo ((NNoo
complementaria) o
5 10 "C" (Complementaria)
6 11 40 An C Rég.transparencia fiscal internacional - 1.Nombre o razón social
7 51 40 An C Rég.transparencia fiscal internacional - 1.Domicilio social
8 91 2 An C Rég.transparencia fiscal internacional - 1.Clave país/territorio
9 93 17 Num C Rég.transparencia fiscal internacional - 1. Importe renta [A]
10 110 95 An C Rég.transparencia fiscal internacional - 1. Administradores. Línea 1
11 205 95 An C Rég.transparencia fiscal internacional - 1. Administradores. Línea 2
12 300 95 An C Rég.transparencia fiscal internacional - 1. Administradores. Línea 3
13 395 95 An C Rég.transparencia fiscal internacional - 1. Administradores. Línea 4
14 490 95 An C Rég.transparencia fiscal internacional - 1. Administradores. Línea 5
15 585 40 An C Rég.transparencia fiscal internacional - 2.Nombre o razón social
16 625 40 An C Régg.transpparencia fiscal internacional - 2.Domicilio social
17 665 2 An C Rég.transparencia fiscal internacional - 2.Clave país/territorio
18 667 17 Num C Rég.transparencia fiscal internacional - 2. Importe renta [B]
19 684 95 An C Rég.transparencia fiscal internacional - 2. Administradores. Línea 1
20 779 95 An C Rég.transparencia fiscal internacional - 2. Administradores. Línea 2
21 874 95 An C Rég.transparencia fiscal internacional - 2. Administradores. Línea 3
22 969 95 An C Rég.transparencia fiscal internacional - 2. Administradores. Línea 4
23 1064 95 An C Rég.transparencia fiscal internacional - 2. Administradores. Línea 5
24 1159 40 An C Rég.transparencia fiscal internacional - 3.Nombre o razón social
25 1199 40 An C Rég.transparencia fiscal internacional - 3.Domicilio social
26 1239 2 An C Rég.transparencia fiscal internacional - 3.Clave país/territorio
27 1241 17 Num C Rég.transparencia fiscal internacional - 3. Importe renta [C]
28 1258 95 An C Rég.transparencia fiscal internacional - 3. Administradores. Línea 1
2299 11335533 95 An C Régg.transpparencia fiscal internacional - 3. Administradores. Línea 2
30 1448 95 An C Rég.transparencia fiscal internacional - 3. Administradores. Línea 3
31 1543 95 An C Rég.transparencia fiscal internacional - 3. Administradores. Línea 4
32 1638 95 An C Rég.transparencia fiscal internacional - 3. Administradores. Línea 5
33 1733 40 An C Rég.transparencia fiscal internacional - 4.Nombre o razón social
34 1773 40 An C Rég.transparencia fiscal internacional - 4.Domicilio social
35 1813 2 An C Rég.transparencia fiscal internacional - 4.Clave país/territorio
36 1815 17 Num C Rég.transparencia fiscal internacional - 4. Importe renta [D]
37 1832 95 An C Rég.transparencia fiscal internacional - 4. Administradores. Línea 1
38 1927 95 An C Rég.transparencia fiscal internacional - 4. Administradores. Línea 2
39 2022 95 An C Rég.transparencia fiscal internacional - 4. Administradores. Línea 3
40 2117 95 An C Rég.transparencia fiscal internacional - 4. Administradores. Línea 4
41 2212 95 An C Rég.transparencia fiscal internacional - 4. Administradores. Línea 5
4422 22330077 4400 AAnn CC RRéégg..ttrraannssppaarreenncciiaa ffiissccaall iinntteerrnnaacciioonnaall - 55..NNoommbbrree oo rraazzóónn ssoocciiaall
43 2347 40 An C Rég.transparencia fiscal internacional - 5.Domicilio social
44 2387 2 An C Rég.transparencia fiscal internacional - 5.Clave país/territorio
45 2389 17 Num C Rég.transparencia fiscal internacional - 5. Importe renta [E]
46 2406 95 An C Rég.transparencia fiscal internacional - 5. Administradores. Línea 1
47 2501 95 An C Rég.transparencia fiscal internacional - 5. Administradores. Línea 2
48 2596 95 An C Rég.transparencia fiscal internacional - 5. Administradores. Línea 3
49 2691 95 An C Rég.transparencia fiscal internacional - 5. Administradores. Línea 4
50 2786 95 An C Rég.transparencia fiscal internacional - 5. Administradores. Línea 5
51 2881 40 An C Rég.transparencia fiscal internacional - 6.Nombre o razón social
52 2921 40 An C Rég.transparencia fiscal internacional - 6.Domicilio social
53 2961 2 An C Rég.transparencia fiscal internacional - 6.Clave país/territorio
54 2963 17 Num C Rég.transparencia fiscal internacional - 6. Importe renta [F]
5555 22998800 9955 AAnn CC RRéégg..ttrraannssppaarreenncciiaa ffiissccaall iinntteerrnnaacciioonnaall -- 66.. AAddmmiinniissttrraaddoorreess.. LLíínneeaa 11
56 3075 95 An C Rég.transparencia fiscal internacional - 6. Administradores. Línea 2
57 3170 95 An C Rég.transparencia fiscal internacional - 6. Administradores. Línea 3
58 3265 95 An C Rég.transparencia fiscal internacional - 6. Administradores. Línea 4
59 3360 95 An C Rég.transparencia fiscal internacional - 6. Administradores. Línea 5
60 3455 17 Num Rég.transparencia fiscal internacional - Total importe [387]
61 3472 10 An C Identificador de fin de registro OBLIGATORIO Constante "</T200023>"
Total: 3481
Página 39

# Pag. 40

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "024"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NNuumm TTrriibbuuttaacciióónn ccoonnjjuunnttaa EEssttaaddoo yy AAddmm.FFoorraalleess - CCoonncciieerrttoo eeccoonnóómmiiccoo. VVoolluummeenn ttoottaall ddee ooppeerraacciioonneess [[005500]]
17 Num Tributación conjunta Estado y Adm.Forales - Concierto económico. Volumen operaciones en el extranjero [051]
7 28
8 45 17 Num Tributación conjunta Estado y Adm.Forales - Concierto económico. Volumen operaciones en Álava [052]
17 Num Tributación conjunta Estado y Adm.Forales - Concierto económico. Volumen operaciones en Guipúzcoa [053]
9 62
17 Num Tributación conjunta Estado y Adm.Forales - Concierto económico. Volumen operaciones en Vizcaya [054]
10 79
17 Num Tributación conjunta Estado y Adm.Forales - Concierto económico. Volumen operaciones en Navarra [055]
11 96
Tributación conjunta Estado y Adm.Forales - Concierto económico. Volumen operaciones en Territorio común
12 113 17 Num [056]
13 130 5 Num Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación. Álava [626]
1144 113355 55 NNum TTriibbuttaciióón conjjuntta EEsttaddo y AAddm.FForalles - CCáállcullo porcenttajjes ttriibbuttaciióón. GGuiipúúzcoa [[662277]]
15 140 5 Num Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación. Vizcaya [628]
16 145 5 Num Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación. Navarra [629]
17 150 5 Num Tributación conjunta Estado y Adm.Forales - Cálculo porcentajes tributación. Admón.del Estado [625]
18 155 17 N Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver. Álava [420]
19 172 17 N Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver. Guipúzcoa [421]
20 189 17 N Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver. Vizcaya [426]
21 206 17 N Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver. Navarra [427]
22 223 17 N Tributación conjunta Estado y Adm.Forales - Cuota del ejercicio a ingresar/devolver. Total [600]
23 240 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1. Álava [402]
24 257 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1. Guipúzcoa [442]
25 274 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1. Vizcaya [443]
2266 229911 1177 NNuumm TTrriibbuuttaacciióónn ccoonnjjuunnttaa EEssttaaddoo yy AAddmm..FFoorraalleess -- PPaaggooss ffrraacccciioonnaaddooss 11.. NNaavvaarrrraa [[444444]]
27 308 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 1. Total [602]
28 325 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2. Álava [445]
29 342 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2. Guipúzcoa [446]
30 359 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2. Vizcaya [447]
31 376 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2. Navarra [448]
32 393 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 2. Total [604]
33 410 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3. Álava [449]
34 427 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3. Guipúzcoa [450]
35 444 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3. Vizcaya [451]
36 461 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3. Navarra [465]
37 478 17 Num Tributación conjunta Estado y Adm.Forales - Pagos fraccionados 3. Total [606]
38 495 17 N Tributación conjunta Estado y Adm.Forales - Cuota diferencial. Álava [474]
39 512 17 N Tributación conjunta Estado y Adm.Forales - Cuota diferencial. Guipúzcoa [475]
40 529 17 N Tributación conjunta Estado y Adm.Forales - Cuota diferencial. Vizcaya [476]
41 546 17 N Tributación conjunta Estado y Adm.Forales - Cuota diferencial. Navarra [477]
42 563 17 N Tributación conjunta Estado y Adm.Forales - Cuota diferencial. Total [612]
43 580 17 Num Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales. Álava [482]
17 Num Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales. Guipúzcoa [483]
44 597
45 614 17 Num Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales. Vizcaya [484]
46 631 17 Num Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales. Navarra [485]
47 648 17 Num Tributación conjunta Estado y Adm.Forales - Incremento por pérdida beneficios fiscales. Total [616]
17 Num Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI. Álava [913]
48 665
1177 NNuumm TTrriibbuuttaacciióónn ccoonnjjuunnttaa EEssttaaddoo yy AAddmm..FFoorraalleess -- IInnccrreemmeennttoo ppoorr iinnccuummpplliimmiieennttoo rreeqquuiissiittooss SSOOCCIIMMII.. GGuuiippúúzzccooaa [[991144
49 682
17 Num Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI. Vizcaya [915]
50 699
17 Num Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI. Navarra [916]
51 716
17 Num Tributación conjunta Estado y Adm.Forales - Incremento por incumplimiento requisitos SOCIMI. Total [642]
52 733
53 750 17 Num Tributación conjunta Estado y Adm.Forales - Intereses demora. Álava [486]
54 767 17 Num Tributación conjunta Estado y Adm.Forales - Intereses demora. Guipúzcoa [487]
55 784 17 Num Tributación conjunta Estado y Adm.Forales - Intereses demora. Vizcaya [488]
56 801 17 Num Tributación conjunta Estado y Adm.Forales - Intereses demora. Navarra [489]
57 818 17 Num Tributación conjunta Estado y Adm.Forales - Intereses demora. Total [618]
1177 NN TTrriibbuuttaacciióónn ccoonnjjuunnttaa EEssttaaddoo yy AAddmm.FFoorraalleess -- IImmppoorrttee iinnggrreessoo//ddeevvoolluucciióónn ddeeccllaarraacciióónn oorriiggiinnaarriiaa. ÁÁllaavvaa [[449900]]
58 835
17 N Tributación conjunta Estado y Adm.Forales - Importe ingreso/devolución declaración originaria. Guipúzcoa [491]
59 852
17 N Tributación conjunta Estado y Adm.Forales - Importe ingreso/devolución declaración originaria. Vizcaya [492]
60 869
17 N Tributación conjunta Estado y Adm.Forales - Importe ingreso/devolución declaración originaria. Navarra [493]
61 886
17 N Tributación conjunta Estado y Adm.Forales - Importe ingreso/devolución declaración originaria. Total [620]
62 903
63 920 17 N Tributación conjunta Estado y Adm.Forales - Líquido a ingresar o a devolver. Álava [494]
64 937 17 N Tributación conjunta Estado y Adm.Forales - Líquido a ingresar o a devolver. Guipúzcoa [495]
65 954 17 N Tributación conjunta Estado y Adm.Forales - Líquido a ingresar o a devolver. Vizcaya [496]
6666 997711 1177 NN TTrriibbuuttaacciióónn ccoonnjjuunnttaa EEssttaaddoo yy AAddmm.FFoorraalleess -- LLííqquuiiddoo aa iinnggrreessaarr oo aa ddeevvoollvveerr. NNaavvaarrrraa [[449977]]
67 988 17 N Tributación conjunta Estado y Adm.Forales - Líquido a ingresar o a devolver. Total [622]
68 1005 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200024>"
Total: 1014
Página 40

# Pag. 41

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "025"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - AAccttiivvoo. CCaajjaa yy ddeeppóóssiittooss eenn bbaannccooss cceennttrraalleess [[110011]]
7 28 17 N Contabilidad Banco de España - Activo. Cartera de negociación [102]
8 45 17 N Contabilidad Banco de España - Activo. Depósitos en entidades de crédito [103]
9 62 17 N Contabilidad Banco de España - Activo. Crédito a la clientela [104]
10 79 17 N Contabilidad Banco de España - Activo. Valores representativos de deuda [105]
11 96 17 N Contabilidad Banco de España - Activo. Otros instrumentos de capital [106]
12 113 17 N Contabilidad Banco de España - Activo. Derivados de negociación [107]
13 130 17 N Contabilidad Banco de España - Activo. Otros activos financieros a valor razonable [108]
14 147 17 N Contabilidad Banco de España - Activo. Depósitos en entidades de crédito [109]
15 164 17 N Contabilidad Banco de España - Activo. Crédito a la clientela [110]
16 181 17 N Contabilidad Banco de España - Activo. Valores representativos de deuda [111]
17 198 17 N Contabilidad Banco de España - Activo. Instrumentos de capital [112]
1188 221155 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa -- AAccttiivvoo.. AAccttiivvooss ffiinnaanncciieerrooss ddiissppoonniibblleess ppaarraa llaa vveennttaa [[111133]]
19 232 17 N Contabilidad Banco de España - Activo. Valores representativos de deuda [114]
20 249 17 N Contabilidad Banco de España - Activo. Instrumentos de capital [115]
21 266 17 N Contabilidad Banco de España - Activo. Inversiones crediticias [116]
22 283 17 N Contabilidad Banco de España - Activo. Depósitos en entidades de crédito [117]
23 300 17 N Contabilidad Banco de España - Activo. Crédito a la clientela [118]
24 317 17 N Contabilidad Banco de España - Activo. Valores representativos de deuda [119]
25 334 17 N Contabilidad Banco de España - Activo. Cartera de inversión a vencimiento [120]
26 351 17 N Contabilidad Banco de España - Activo. Ajustes a activos financieros macro-coberturas [121]
27 368 17 N Contabilidad Banco de España - Activo. Derivados de cobertura [122]
28 385 17 N Contabilidad Banco de España - Activo. Activos no corrientes en venta [123]
29 402 17 N Contabilidad Banco de España - Activo. Participaciones [124]
30 419 17 N Contabilidad Banco de España - Activo. Entidades asociadas [125]
31 436 17 N Contabilidad Banco de España - Activo. Entidades multigrupo [126]
32 453 17 N Contabilidad Banco de España - Activo. Entidades del grupo [127]
33 470 17 N Contabilidad Banco de España - Activo. Contratos de seguros vinculados a pensiones [128]
34 487 17 N Contabilidad Banco de España - Activo. Activo material [129]
35 504 17 N Contabilidad Banco de España - Activo. Inmovilizado material [130]
36 521 17 N Contabilidad Banco de España - Activo. De uso propio [131]
37 538 17 N Contabilidad Banco de España - Activo. Cedido en arrendamiento operativo [132]
38 555 17 N Contabilidad Banco de España - Activo. Afecto a la obra social [133]
39 572 17 N Contabilidad Banco de España - Activo. Inversiones inmobiliarias [134]
40 589 17 N Contabilidad Banco de España - Activo. Activo intangible [135]
41 606 17 N Contabilidad Banco de España - Activo. Fondo de comercio [136]
42 623 17 N Contabilidad Banco de España - Activo. Otro activo intangible [137]
4433 664400 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - AAccttiivvoo. AAccttiivvooss ffiissccaalleess [[113388]]
44 657 17 N Contabilidad Banco de España - Activo. Corrientes [139]
45 674 17 N Contabilidad Banco de España - Activo. Diferidos [140]
46 691 17 N Contabilidad Banco de España - Activo. Resto de activos [141]
47 708 17 N Contabilidad Banco de España - Activo. Total activo [142]
17 N Contabilidad Banco de España - Información adicional - Fondos insolvencias por cobertura específica [202]
48 725
17 N Contabilidad Banco de España - Información adicional - Fondos insolvencias por cobertura genérica [203]
49 742
50 759 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200025>"
Total: 768
Página 41

# Pag. 42

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "026"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - PPaassiivvoo. CCaarrtteerraa ddee nneeggoocciiaacciióónn [[114433]]
7 28 17 N Contabilidad Banco de España - Pasivo. Depósitos de bancos centrales [144]
8 45 17 N Contabilidad Banco de España - Pasivo. Depósitos de entidades de crédito [145]
9 62 17 N Contabilidad Banco de España - Pasivo. Depósitos de la clientela [146]
10 79 17 N Contabilidad Banco de España - Pasivo. Débitos representados por valores negociables [147]
11 96 17 N Contabilidad Banco de España - Pasivo. Derivados de negociación [148]
12 113 17 N Contabilidad Banco de España - Pasivo. Posiciones cortas de valores [149]
13 130 17 N Contabilidad Banco de España - Pasivo. Otros pasivos financieros [150]
17 N Contabilidad Banco de España - Pasivo. Otros pasivos financieros a valor razonable con cambios P y G [151]
14 147
15 164 17 N Contabilidad Banco de España - Pasivo. Depósitos a bancos centrales [152]
16 181 17 N Contabilidad Banco de España - Pasivo. Depósitos a entidades de crédito [153]
1177 119988 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - PPaassiivvoo.. DDeeppóóssiittooss aa llaa cclliieenntteellaa [[115544]]
18 215 17 N Contabilidad Banco de España - Pasivo. Débitos representados por valores negociables [155]
19 232 17 N Contabilidad Banco de España - Pasivo. Pasivos subordinados [156]
20 249 17 N Contabilidad Banco de España - Pasivo. Otros pasivos financieros [157]
21 266 17 N Contabilidad Banco de España - Pasivo. Pasivos financieros a coste amortizado [158]
22 283 17 N Contabilidad Banco de España - Pasivo. Depósitos de bancos centrales [159]
23 300 17 N Contabilidad Banco de España - Pasivo. Depósitos de entidades de crédito [160]
24 317 17 N Contabilidad Banco de España - Pasivo. Depósitos de la clientela [161]
25 334 17 N Contabilidad Banco de España - Pasivo. Débitos representados por valores negociables [162]
26 351 17 N Contabilidad Banco de España - Pasivo. Pasivos subordinados [163]
27 368 17 N Contabilidad Banco de España - Pasivo. Otros pasivos financieros [164]
28 385 17 N Contabilidad Banco de España - Pasivo. Ajustes a pasivos financieros por macro-coberturas [165]
29 402 17 N Contabilidad Banco de España - Pasivo. Derivados de cobertura [166]
30 419 117 NN CContabbiilliiddadd BBanco dde EEspaña - PPasiivo. PPasiivos asociiaddos con actiivos no corriientes en venta [[11667]]
31 436 17 N Contabilidad Banco de España - Pasivo. Provisiones [168]
32 453 17 N Contabilidad Banco de España - Pasivo. Fondo para pensiones [169]
33 470 17 N Contabilidad Banco de España - Pasivo. Provisiones para impuestos [170]
34 487 17 N Contabilidad Banco de España - Pasivo. Provisiones para riesgos [171]
35 504 17 N Contabilidad Banco de España - Pasivo. Otras provisiones [172]
36 521 17 N Contabilidad Banco de España - Pasivo. Pasivos fiscales [173]
37 538 17 N Contabilidad Banco de España - Pasivo. Corrientes [174]
38 555 17 N Contabilidad Banco de España - Pasivo. Diferidos [175]
39 572 17 N Contabilidad Banco de España - Pasivo. Fondo de la Obra social [176]
40 589 17 N Contabilidad Banco de España - Pasivo. Resto de pasivos [177]
41 606 17 N Contabilidad Banco de España - Pasivo. Capital reembolsable a la vista [178]
4422 662233 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa -- PPaassiivvoo. TToottaall ppaassiivvoo [[117799]]
43 640 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200026>"
Total: 649
Página 42

# Pag. 43

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "027"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - PPaattrriimmoonniioo nneettoo. FFoonnddooss pprrooppiiooss [[118800]]
7 28 17 N Contabilidad Banco de España - Patrimonio neto. Capital/Fondo dotación [181]
8 45 17 N Contabilidad Banco de España - Patrimonio neto. Escriturado [182]
9 62 17 N Contabilidad Banco de España - Patrimonio neto. Menos:capital no exigido [183]
10 79 17 N Contabilidad Banco de España - Patrimonio neto. Prima de emisión [184]
11 96 17 N Contabilidad Banco de España - Patrimonio neto. Reservas [185]
12 113 17 N Contabilidad Banco de España - Patrimonio neto. Otros instrumentos de capital [186]
13 130 17 N Contabilidad Banco de España - Patrimonio neto. De instrumentos financieros compuestos [187]
14 147 17 N Contabilidad Banco de España - Patrimonio neto. Cuotas participativas y fondos asociados [188]
15 164 17 N Contabilidad Banco de España - Patrimonio neto. Resto de instrumentos de capital [189]
16 181 17 N Contabilidad Banco de España - Patrimonio neto. Menos: valores propios [190]
17 198 17 N Contabilidad Banco de España - Patrimonio neto. Resultado del ejercicio [191]
1188 221155 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa -- PPaattrriimmoonniioo nneettoo.. MMeennooss:: DDiivviiddeennddooss yy rreettrriibbuucciioonneess [[119922]]
19 232 17 N Contabilidad Banco de España - Patrimonio neto. Ajustes por valoración [193]
20 249 17 N Contabilidad Banco de España - Patrimonio neto. Activos financieros disponibles para la venta [194]
21 266 17 N Contabilidad Banco de España - Patrimonio neto. Coberturas de los flujos de efectivo [195]
17 N Contabilidad Banco de España - Patrimonio neto. Coberturas de inversiones netas en negocios en el extranjero
22 283 [196]
23 300 17 N Contabilidad Banco de España - Patrimonio neto. Diferencias de cambio [197]
24 317 17 N Contabilidad Banco de España - Patrimonio neto. Activos no corrientes en venta [198]
25 334 17 N Contabilidad Banco de España - Patrimonio neto. Resto de ajustes por valoración [199]
26 351 17 N Contabilidad Banco de España - Patrimonio neto. Total patrimonio neto [200]
27 368 17 N Contabilidad Banco de España - Patrimonio neto. Total pasivo y patrimonio neto [201]
28 385 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200027>"
Total: 394
Página 43

# Pag. 44

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "028"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa -PPéérrddiiddaass yy ggaannaanncciiaass.IInntteerreesseess yy rreennddiimmiieennttooss aassiimmiillaaddooss [[220044]]
7 28 17 N Contabilidad Banco de España -Pérdidas y ganancias.Intereses y cargas asimiladas [205]
17 N Contabilidad Banco de España -Pérdidas y ganancias.Remuneración de capital reembolsable a la vista(solo coop.
8 45 De crédito) [206]
9 62 17 N Contabilidad Banco de España -Pérdidas y ganancias.Margen de intereses [207]
10 79 17 N Contabilidad Banco de España -Pérdidas y ganancias.Rendimiento de instrumentos de capital [208]
11 96 17 N Contabilidad Banco de España -Pérdidas y ganancias.Comisiones percibidas [209]
12 113 17 N Contabilidad Banco de España -Pérdidas y ganancias.Comisiones pagadas [210]
17 N Contabilidad Banco de España -Pérdidas y ganancias.Resultado de operaciones financieras (neto) [211]
13 130
14 147 17 N Contabilidad Banco de España -Pérdidas y ganancias.Cartera de negociación [212]
17 N Contabilidad Banco de España -Pérdidas y ganancias.Otros instrumentos financieros a valor razonable cambios
15 164 en ppérdidas yy gganancias. [[213]]
17 N Contabilidad Banco de España -Pérdidas y ganancias.Instrumentos financieros no valorados a valor razonable con
16 181 cambios en pérdidas y ganancias. [214]
17 198 17 N Contabilidad Banco de España -Pérdidas y ganancias.Otros [215]
18 215 17 N Contabilidad Banco de España -Pérdidas y ganancias.Diferencias de cambio (neto) [216]
19 232 17 N Contabilidad Banco de España -Pérdidas y ganancias.Otros productos de explotación [217]
20 249 17 N Contabilidad Banco de España -Pérdidas y ganancias.Otras cargas de explotación [218]
21 266 17 N Contabilidad Banco de España -Pérdidas y ganancias.Margen bruto [219]
22 283 17 N Contabilidad Banco de España -Pérdidas y ganancias.Gastos de administración [220]
23 300 17 N Contabilidad Banco de España -Pérdidas y ganancias.Gastos de personal [221]
24 317 17 N Contabilidad Banco de España -Pérdidas y ganancias.Otros gastos generales de admón [222]
25 334 17 N Contabilidad Banco de España -Pérdidas y ganancias.Amortización [223]
26 351 17 N Contabilidad Banco de España -Pérdidas y ganancias.Dotaciones a provisiones (neto) [224]
1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa --PPéérrddiiddaass yy ggaannaanncciiaass.PPéérrddiiddaass ppoorr ddeetteerriioorroo ddee aaccttiivvooss ffiinnaanncciieerrooss ((nneettoo)) [[222255]]
27 368
28 385 17 N Contabilidad Banco de España -Pérdidas y ganancias.inversiones crediticias [226]
17 N Contabilidad Banco de España -Pérdidas y ganancias.Otros instrumentos financieros no valorados a valor
29 402 razonable con cambios en pérdidas y ganancias [227]
30 419 17 N Contabilidad Banco de España -Pérdidas y ganancias.Resultado de la actividad de explotación [228]
17 N Contabilidad Banco de España -Pérdidas y ganancias.Pérdidas por deterioro del resto de activos (neto) [229]
31 436
32 453 17 N Contabilidad Banco de España -Pérdidas y ganancias.Fondo de comercio y otro activo intangible [230]
33 470 17 N Contabilidad Banco de España -Pérdidas y ganancias.Otros activos [231]
17 N Contabilidad Banco de España -Pérdidas y ganancias.Ganancias (pérdidas) en la baja de activos no clasificados
34 487 como no corrientes en venta [232]
17 N Contabilidad Banco de España -Pérdidas y ganancias.Diferencia negativa en combinaciones de negocios [233]
3355 550044
17 N Contabilidad Banco de España -Pérdidas y ganancias.Ganancias (pérdidas) de activos no corrientes en venta no
36 521 clasificados como operaciones interrumpidas [234]
37 538 17 N Contabilidad Banco de España -Pérdidas y ganancias.Resultado antes de impuestos [235]
38 555 17 N Contabilidad Banco de España -Pérdidas y ganancias.Impuesto sobre beneficios [236]
17 N Contabilidad Banco de España -Pérdidas y ganancias.Dotación obligatoria a obras y fondos sociales (sólo cajas
39 572 ahorros y coop. Crédito) [237]
17 N Contabilidad Banco de España -Pérdidas y ganancias.Resultado del ejercicio procedente de operaciones
40 589 continuadas [238]
17 N Contabilidad Banco de España -Pérdidas y ganancias.Resultado de operaciones interrumpidas (neto) [239]
41 606
42 623 17 N Contabilidad Banco de España -Pérdidas y ganancias.Resultado del ejercicio [500]
43 640 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200028>"
TTottall: 664499
Página 44

# Pag. 45

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "029"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa-EEssttaaddoo ddee IInnggrreessooss yy ggaassttooss RReeccoonnoocciiddooss. RReessuullttaaddoo ddeell eejjeerrcciicciioo [[550000]]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos. Otros ingresos y gastos reconocidos
7 28 [256]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos. Activos financieros disponibles para la
8 45 venta [257]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos.Ganancias (pérdidas) por valoración
9 62 [258]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos.Importes transferidos a la cuenta de
10 79 pérdidas y ganancias [259]
11 96 17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos.Otras reclasificaciones [260]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos.Coberturas de los flujos de efectivo
12 113 [261]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos.Ganancias (pérdidas) por valoración
1133 113300 [[226622]]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos.Importes transferidos a la cuenta de
14 147 pérdidas y ganancias [263]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos.Importes transferidos al valor inicial de
15 164 las partidas cubiertas [264]
16 181 17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos. Otras reclasificaciones [265]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos.Coberturas de inversiones netas en
17 198 negocios en el extranjero [266]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos.Ganancias (pérdidas) por valoración
18 215 [267]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos. Importes transferidos a la cuenta de
19 232 pérdidas y ganancias [268]
20 249 17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos. Otras reclasificaciones [269]
2211 226666 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa-EEssttaaddoo ddee IInnggrreessooss yy ggaassttooss RReeccoonnoocciiddooss. DDiiffeerreenncciiaass ddee ccaammbbiioo [[227700]]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos. Ganancias (pérdidas) por valoración
22 283 [271]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos. Importes transferidos a la cuenta de
23 300 pérdidas y ganancias [272]
24 317 17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos. Otras reclasificaciones [273]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos. Activos no corrientes en venta [274]
25 334
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos.Ganancias (pérdidas) por valoración
26 351 [275]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos. Importes transferidos a la cuenta de
27 368 pérdidas y ganancias [276]
28 385 17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos. Otras reclasificaciones [277]
1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa-EEssttaaddoo ddee IInnggrreessooss yy ggaassttooss RReeccoonnoocciiddooss. GGaannaanncciiaass ((ppéérrddiiddaass)) aaccttuuaarriiaalleess eenn
29 402 planes de pensiones [278]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos. Resto de ingresos y gastos reconocidos
30 419 [279]
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos. Impuesto sobre beneficios [280]
31 436
17 N Contabilidad Banco de España-Estado de Ingresos y gastos Reconocidos. Total ingresos y gastos reconocidos
32 453 [281]
33 470 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200029>"
Total: 479
Página 45

# Pag. 46

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "030"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo. SSaallddoo ffiinnaall. CCaappiittaall//ffoonnddoo ddoottaacciióónn [[228822]]
7 28 17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Prima emisión [283]
8 45 17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Reservas [284]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Otros instrumentos capital [285]
9 62
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Menos: valores propios [286]
10 79
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes cambio criterio contable. Capital/fondo
11 96 dotación [292]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes cambio criterio contable. Prima emisión
12 113 [293]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes cambio criterio contable. Reservas [294]
13 130
1177 NN CConttabbiilliiddadd BBanco dde EEspañña - EEsttaddo cambbiios pattriimoniio netto. AAjjusttes cambbiio criitteriio conttabblle. OOttros
14 147 instrumentos capital [295]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes cambio criterio contable. Menos: valores
15 164 propios [296]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes por errores. Capital/fondo dotación
16 181 [302]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes por errores. Prima emisión [303]
17 198
18 215 17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes por errores. Reservas [304]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes por errores. Otros instrumentos capital
19 232 [305]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes por errores. Menos: valores propios
20 249 [306]
1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo. SSaallddoo iinniicciiaall aajjuussttaaddoo. CCaappiittaall//ffoonnddoo ddoottaacciióónn
21 266 [312]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo inicial ajustado. Prima emisión [313]
22 283
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo inicial ajustado. Reservas [314]
23 300
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo inicial ajustado. Otros instrumentos capital
24 317 [315]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo inicial ajustado. Menos: valores propios
25 334 [316]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Total ingresos y gastos reconocidos.
26 351 Capital/fondo dotación [322]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Total ingresos y gastos reconocidos. Prima
2277 336688 eemmiissiióónn [[332233]]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Total ingresos y gastos reconocidos. Reservas
28 385 [324]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Total ingresos y gastos reconocidos. Otros
29 402 instrumentos capital [325]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Total ingresos y gastos reconocidos. Menos:
30 419 valores propios [326]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Otras variaciones del patrimonio neto.
31 436 Capital/fondo dotación [332]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Otras variaciones del patrimonio neto. Prima
32 453 emisión [333]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Otras variaciones del patrimonio neto. Reservas
33 470 [334]
1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa -- EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo.. OOttrraass vvaarriiaacciioonneess ddeell ppaattrriimmoonniioo nneettoo.. OOttrrooss
34 487 instrumentos capital [335]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Otras variaciones del patrimonio neto. Menos:
35 504 valores propios [336]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Aumentos de capital/ fondo de dotación.
36 521 Capital/fondo dotación [342]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Aumentos de capital/ fondo de dotación. Prima
37 538 emisión [343]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Aumentos de capital/ fondo de dotación.
38 555 Reservas [344]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Aumentos de capital/ fondo de dotación. Otros
39 572 instrumentos capital [345]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Aumentos de capital/ fondo de dotación. Menos:
4400 558899 vvaalloorreess pprrooppiiooss [[334466]]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reducciones de capital. Capital/fondo dotación
41 606 [352]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reducciones de capital. Prima emisión [353]
42 623
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reducciones de capital. Reservas [354]
43 640
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reducciones de capital. Otros instrumentos
44 657 capital [355]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reducciones de capital. Menos: valores propios
45 674 [356]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Conversión de pasivos financieros en capital.
46 691 Capital/fondo dotación [362]
17 N Contabilidad Banco de Esppaña - Estado cambios ppatrimonio neto. Conversión de ppasivos financieros en cappital.
47 708 Prima emisión [363]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Conversión de pasivos financieros en capital.
48 725 Reservas [364]
Página 46

# Pag. 47

17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Conversión de pasivos financieros en capital.
49 742 Otros instrumentos capital [365]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Conversión de pasivos financieros en capital.
50 759 Menos: valores propios [366]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos de otros instrumentos de capital.
51 776 Capital/fondo dotación [372]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos de otros instrumentos de capital.
52 793 Prima emisión [373]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos de otros instrumentos de capital.
53 810 Reservas [374]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos de otros instrumentos de capital.
54 827 Otros instrumentos capital [375]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos de otros instrumentos de capital.
55 884444 MMenos: vallores propiios [[337766]]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de pasivos financieros a otros
56 861 instrumentos de capital. Capital/fondo dotación [382]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de pasivos financieros a otros
57 878 instrumentos de capital. Prima emisión [383]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de pasivos financieros a otros
58 895 instrumentos de capital. Reservas [384]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de pasivos financieros a otros
59 912 instrumentos de capital. Otros instrumentos capital [385]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de pasivos financieros a otros
60 929 instrumentos de capital. Menos: valores propios [386]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de otros instrumentos de capital
61 946 a pasivos financieros. Capital/fondo dotación [392]
1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo. RReeccllaassiiffiiccaacciióónn ddee oottrrooss iinnssttrruummeennttooss ddee ccaappiittaall
62 963 a pasivos financieros. Prima emisión [393]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de otros instrumentos de capital
63 980 a pasivos financieros. Reservas [394]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de otros instrumentos de capital
64 997 a pasivos financieros. Otros instrumentos capital [395]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de otros instrumentos de capital
65 1014 a pasivos financieros. Menos: valores propios [396]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Distribución de dividendos / Remuneración a
66 1031 los socios. Capital/fondo dotación [402]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Distribución de dividendos / Remuneración a
67 1048 los socios. Prima emisión [403]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Distribución de dividendos / Remuneración a
6688 11006655 llooss ssoocciiooss. RReesseerrvvaass [[440044]]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Distribución de dividendos / Remuneración a
69 1082 los socios. Otros instrumentos capital [405]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Distribución de dividendos / Remuneración a
70 1099 los socios. Menos: valores propios [406]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Operaciones con instrumentos de capital propio
71 1116 (neto). Capital/fondo dotación [412]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Operaciones con instrumentos de capital propio
72 1133 (neto). Prima emisión [413]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Operaciones con instrumentos de capital propio
73 1150 (neto). Reservas [414]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Operaciones con instrumentos de capital propio
74 1167 (neto). Otros instrumentos capital [415]
1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa -- EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo.. OOppeerraacciioonneess ccoonn iinnssttrruummeennttooss ddee ccaappiittaall pprrooppiioo
75 1184 (neto). Menos: valores propios [416]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Traspasos entre partidas de patrimonio neto.
76 1201 Capital/fondo dotación [422]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Traspasos entre partidas de patrimonio neto.
77 1218 Prima emisión [423]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Traspasos entre partidas de patrimonio neto.
78 1235 Reservas [424]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Traspasos entre partidas de patrimonio neto.
79 1252 Otros instrumentos capital [425]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Traspasos entre partidas de patrimonio neto.
80 1269 Menos: valores propios [426]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos (reducciones) por combinaciones
8811 11228866 ddee nneeggoocciiooss.. CCaappiittaall//ffoonnddoo ddoottaacciióónn [[443322]]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos (reducciones) por combinaciones
82 1303 de negocios. Prima emisión [433]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos (reducciones) por combinaciones
83 1320 de negocios. Reservas [434]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos (reducciones) por combinaciones
84 1337 de negocios. Otros instrumentos capital [435]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos (reducciones) por combinaciones
85 1354 de negocios. Menos: valores propios [436]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Dotación discrecional a obras y fondos sociales.
86 1371 Capital/fondo dotación [442]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Dotación discrecional a obras y fondos sociales.
87 1388 Prima emisión [443]
17 N Contabilidad Banco de Esppaña - Estado cambios ppatrimonio neto. Dotación discrecional a obras yy fondos sociales.
88 1405 Reservas [444]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Dotación discrecional a obras y fondos sociales.
89 1422 Otros instrumentos capital [445]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Dotación discrecional a obras y fondos sociales.
90 1439 Menos: valores propios [446]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Pagos con instrumentos de capital.
91 1456 Capital/fondo dotación [452]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Pagos con instrumentos de capital. Prima
92 1473 emisión [453]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Pagos con instrumentos de capital. Reservas
93 1490 [454]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Pagos con instrumentos de capital. Otros
94 1507 instrumentos capital [455]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Pagos con instrumentos de capital. Menos:
95 1524 valores propios [456]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Resto de incrementos (reducciones) de
96 1541 patrimonio neto. Capital/fondo dotación [462]
Página 47

# Pag. 48

17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Resto de incrementos (reducciones) de
97 1558 patrimonio neto. Prima emisión [463]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Resto de incrementos (reducciones) de
98 1575 patrimonio neto. Reservas [464]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Resto de incrementos (reducciones) de
99 1592 patrimonio neto. Otros instrumentos capital [465]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Resto de incrementos (reducciones) de
100 1609 patrimonio neto. Menos: valores propios [466]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Capital/fondo dotación [472]
101 1626
102 1643 17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Prima emisión [473]
103 1660 17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Reservas [474]
17 N Contabilidad Banco de Esppaña - Estado cambios ppatrimonio neto. Saldo final. Otros instrumentos cappital [[475]]
104 1677
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Menos: valores propios [476]
105 1694
106 1711 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200030>"
Total: 1720
Página 48

# Pag. 49

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "031"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo. SSaallddoo ffiinnaall. RReessuullttaaddoo eejjeerrcciicciioo [[228877]]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Menos:dividendos y retribuciones
7 28 [288]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Total fondos propios [289]
8 45
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Ajustes por valoración [290]
9 62
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Total patrimonio neto [291]
10 79
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes por cambio de criterio contable.
11 96 Resultado ejercicio [297]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes por cambio de criterio contable.
12 113 Menos:dividendos y retribuciones [298]
1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo. AAjjuusstteess ppoorr ccaammbbiioo ddee ccrriitteerriioo ccoonnttaabbllee. TToottaall
13 130 fondos propios [299]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes por cambio de criterio contable. Ajustes
14 147 por valoración [300]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes por cambio de criterio contable. Total
15 164 patrimonio neto [301]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes por errores. Resultado ejercicio [307]
16 181
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes por errores. Menos:dividendos y
17 198 retribuciones [308]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes por errores. Total fondos propios [309]
18 215
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes por errores. Ajustes por valoración [310]
1199 223322
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Ajustes por errores. Total patrimonio neto [311]
20 249
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo inicial ajustado. Resultado ejercicio [317]
21 266
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo inicial ajustado. Menos:dividendos y
22 283 retribuciones [318]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo inicial ajustado. Total fondos propios [319]
23 300
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo inicial ajustado. Ajustes por valoración
24 317 [320]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo inicial ajustado. Total patrimonio neto
25 334 [321]
1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa -- EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo.. TToottaall iinnggrreessooss yy ggaassttooss rreeccoonnoocciiddooss.. RReessuullttaaddoo
26 351 ejercicio [327]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Total ingresos y gastos reconocidos.
27 368 Menos:dividendos y retribuciones [328]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Total ingresos y gastos reconocidos. Total
28 385 fondos propios [329]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Total ingresos y gastos reconocidos. Ajustes por
29 402 valoración [330]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Total ingresos y gastos reconocidos. Total
30 419 patrimonio neto [331]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Otras variaciones del patrimonio neto.
31 436 Resultado ejercicio [337]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Otras variaciones del patrimonio neto.
3322 445533 Meenooss:ddividdeenddooss yy reetribbuucciooneess [[333388]]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Otras variaciones del patrimonio neto. Total
33 470 fondos propios [339]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Otras variaciones del patrimonio neto. Ajustes
34 487 por valoración [340]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Otras variaciones del patrimonio neto. Total
35 504 patrimonio neto [341]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Aumentos de capital/ fondo de dotación.
36 521 Resultado ejercicio [347]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Aumentos de capital/ fondo de dotación.
37 538 Menos:dividendos y retribuciones [348]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Aumentos de capital/ fondo de dotación. Total
38 555 fondos propios [349]
17 N Contabilidad Banco de Esppaña - Estado cambios ppatrimonio neto. Aumentos de cappital/ fondo de dotación. Ajjustes
39 572 por valoración [350]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Aumentos de capital/ fondo de dotación. Total
40 589 patrimonio neto [351]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reducciones de capital. Resultado ejercicio
41 606 [357]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reducciones de capital. Menos:dividendos y
42 623 retribuciones [358]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reducciones de capital. Total fondos propios
43 640 [359]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reducciones de capital. Ajustes por valoración
44 657 [360]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reducciones de capital. Total patrimonio neto
45 674 [361]
1177 NN CConttabbiilliiddadd BBanco dde EEspañña - EEsttaddo cambbiios pattriimoniio netto. CConversiióón dde pasiivos ffiinanciieros en capiittall.
46 691 Resultado ejercicio [367]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Conversión de pasivos financieros en capital.
47 708 Menos:dividendos y retribuciones [368]
Página 49

# Pag. 50

17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Conversión de pasivos financieros en capital.
48 725 Total fondos propios [369]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Conversión de pasivos financieros en capital.
49 742 Ajustes por valoración [370]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Conversión de pasivos financieros en capital.
50 759 Total patrimonio neto [371]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos de otros instrumentos de capital.
51 776 Resultado ejercicio [377]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos de otros instrumentos de capital.
52 793 Menos:dividendos y retribuciones [378]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos de otros instrumentos de capital.
53 810 Total fondos propios [379]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos de otros instrumentos de capital.
544 88227 AAjjusttes por valloraciióón [[338800]]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos de otros instrumentos de capital.
55 844 Total patrimonio neto [381]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de pasivos financieros a otros
56 861 instrumentos de capital. Resultado ejercicio [387]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de pasivos financieros a otros
57 878 instrumentos de capital. Menos:dividendos y retribuciones [388]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de pasivos financieros a otros
58 895 instrumentos de capital. Total fondos propios [389]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de pasivos financieros a otros
59 912 instrumentos de capital. Ajustes por valoración [390]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de pasivos financieros a otros
60 929 instrumentos de capital. Total patrimonio neto [391]
1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa - EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo. RReeccllaassiiffiiccaacciióónn ddee oottrrooss iinnssttrruummeennttooss ddee ccaappiittaall
61 946 a pasivos financieros. Resultado ejercicio [397]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de otros instrumentos de capital
62 963 a pasivos financieros. Menos:dividendos y retribuciones [398]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de otros instrumentos de capital
63 980 a pasivos financieros. Total fondos propios [399]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de otros instrumentos de capital
64 997 a pasivos financieros. Ajustes por valoración [400]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Reclasificación de otros instrumentos de capital
65 1014 a pasivos financieros. Total patrimonio neto [401]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Distribución de dividendos / Remuneración a
66 1031 los socios. Resultado ejercicio [407]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Distribución de dividendos / Remuneración a
6677 11004488 llooss ssoocciiooss. MMeennooss::ddiivviiddeennddooss yy rreettrriibbuucciioonneess [[440088]]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Distribución de dividendos / Remuneración a
68 1065 los socios. Total fondos propios [409]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Distribución de dividendos / Remuneración a
69 1082 los socios. Ajustes por valoración [410]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Distribución de dividendos / Remuneración a
70 1099 los socios. Total patrimonio neto [411]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Operaciones con instrumentos de capital propio
71 1116 (neto). Resultado ejercicio [417]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Operaciones con instrumentos de capital propio
72 1133 (neto). Menos:dividendos y retribuciones [418]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Operaciones con instrumentos de capital propio
73 1150 (neto). Total fondos propios [419]
1177 NN CCoonnttaabbiilliiddaadd BBaannccoo ddee EEssppaaññaa -- EEssttaaddoo ccaammbbiiooss ppaattrriimmoonniioo nneettoo.. OOppeerraacciioonneess ccoonn iinnssttrruummeennttooss ddee ccaappiittaall pprrooppiioo
74 1167 (neto). Ajustes por valoración [420]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Operaciones con instrumentos de capital propio
75 1184 (neto). Total patrimonio neto [421]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Traspasos entre partidas de patrimonio neto.
76 1201 Resultado ejercicio [427]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Traspasos entre partidas de patrimonio neto.
77 1218 Menos:dividendos y retribuciones [428]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Traspasos entre partidas de patrimonio neto.
78 1235 Total fondos propios [429]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Traspasos entre partidas de patrimonio neto.
79 1252 Ajustes por valoración [430]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Traspasos entre partidas de patrimonio neto.
8800 11226699 TToottaall ppaattrriimmoonniioo nneettoo [[443311]]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos (reducciones) por combinaciones
81 1286 de negocios. Resultado ejercicio [437]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos (reducciones) por combinaciones
82 1303 de negocios. Menos:dividendos y retribuciones [438]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos (reducciones) por combinaciones
83 1320 de negocios. Total fondos propios [439]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos (reducciones) por combinaciones
84 1337 de negocios. Ajustes por valoración [440]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Incrementos (reducciones) por combinaciones
85 1354 de negocios. Total patrimonio neto [441]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Dotación discrecional a obras y fondos sociales.
86 1371 Resultado ejercicio [447]
17 N Contabilidad Banco de Esppaña - Estado cambios ppatrimonio neto. Dotación discrecional a obras yy fondos sociales.
87 1388 Menos:dividendos y retribuciones [448]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Dotación discrecional a obras y fondos sociales.
88 1405 Total fondos propios [449]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Dotación discrecional a obras y fondos sociales.
89 1422 Ajustes por valoración [450]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Dotación discrecional a obras y fondos sociales.
90 1439 Total patrimonio neto [451]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Pagos con instrumentos de capital. Resultado
91 1456 ejercicio [457]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Pagos con instrumentos de capital.
92 1473 Menos:dividendos y retribuciones [458]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Pagos con instrumentos de capital. Total fondos
93 1490 propios [459]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Pagos con instrumentos de capital. Ajustes por
94 1507 valoración [460]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Pagos con instrumentos de capital. Total
95 1524 patrimonio neto [461]
Página 50

# Pag. 51

17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Resto de incrementos (reducciones) de
96 1541 patrimonio neto. Resultado ejercicio [467]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Resto de incrementos (reducciones) de
97 1558 patrimonio neto. Menos:dividendos y retribuciones [468]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Resto de incrementos (reducciones) de
98 1575 patrimonio neto. Total fondos propios [469]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Resto de incrementos (reducciones) de
99 1592 patrimonio neto. Ajustes por valoración [470]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Resto de incrementos (reducciones) de
100 1609 patrimonio neto. Total patrimonio neto [471]
101 1626 17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Resultado ejercicio [477]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Menos:dividendos y retribuciones
102 1643 [478]
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Total fondos propios [479]
103 1660
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Ajustes por valoración [480]
104 1677
17 N Contabilidad Banco de España - Estado cambios patrimonio neto. Saldo final. Total patrimonio neto [481]
105 1694
106 1711 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200031>"
Total: 1720
Página 51

# Pag. 52

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "032"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass. BBaallaannccee - AAccttiivvoo.EEffeeccttiivvoo yy oottrrooss aaccttiivvooss llííqquuiiddooss eeqquuiivvaalleenntteess [[110011]]
7 28 17 N Entidades aseguradoras. Balance - Activo.Activos financieros mantenidos para negociar [102]
8 45 17 N Entidades aseguradoras. Balance - Activo.Instrumentos de patrimonio [103]
9 62 17 N Entidades aseguradoras. Balance - Activo.Valores representativos de deuda [104]
10 79 17 N Entidades aseguradoras. Balance - Activo. Derivados [105]
11 96 17 N Entidades aseguradoras. Balance - Activo.Otros [106]
17 N Entidades aseguradoras. Balance - Activo.Otros activos financieros a valor razonable con cambios en perdidas y
12 113 ganancias [107]
13 130 17 N Entidades aseguradoras. Balance - Activo.Instrumentos de patrimonio [108]
14 147 17 N Entidades aseguradoras. Balance - Activo.Valores representativos de la deuda [109]
15 164 17 N Entidades aseguradoras. Balance - Activo.Instrumentos híbridos [110]
17 N Entidades aseguradoras. Balance - Activo. Inversiones por cuenta de tomadores seguros vida que asuman riesgo
166 1881 inversión [[111]]
17 198 17 N Entidades aseguradoras. Balance - Activo. Otros [112]
18 215 17 N Entidades aseguradoras. Balance - Activo.Activos financieros disponibles para la venta [113]
19 232 17 N Entidades aseguradoras. Balance - Activo.Instrumentos de patrimonio [114]
20 249 17 N Entidades aseguradoras. Balance - Activo.Valores representativos de deuda [115]
17 N Entidades aseguradoras. Balance - Activo. Inversiones por cuenta de tomadores seguros vida
21 266 que asuman riesgo inversión [116]
22 283 17 N Entidades aseguradoras. Balance - Activo. Otros [117]
23 300 17 N Entidades aseguradoras. Balance - Activo. Préstamos y partidas a cobrar [118]
24 317 17 N Entidades aseguradoras. Balance - Activo. Valores representativos de la deuda [119]
25 334 17 N Entidades aseguradoras. Balance - Activo. Préstamos [120]
26 351 17 N Entidades aseguradoras. Balance - Activo. Anticipos sobre pólizas [121]
27 368 17 N Entidades aseguradoras. Balance - Activo.Préstamos a entidades del grupo y asociadas [122]
2288 338855 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass. BBaallaannccee - AAccttiivvoo. PPrrééssttaammooss aa oottrraass ppaarrtteess vviinnccuullaaddaass [[112233]]
29 402 17 N Entidades aseguradoras. Balance - Activo. Depósitos en entidades de crédito [124]
30 419 17 N Entidades aseguradoras. Balance - Activo. Depósitos constituidos por reaseguro aceptado [125]
31 436 17 N Entidades aseguradoras. Balance - Activo. Créditos por operaciones de seguro directo [126]
32 453 17 N Entidades aseguradoras. Balance - Activo. Tomadores de seguro [127]
33 470 17 N Entidades aseguradoras. Balance - Activo. Mediadores [128]
34 487 17 N Entidades aseguradoras. Balance - Activo. Créditos por operaciones de reaseguro [129]
35 504 17 N Entidades aseguradoras. Balance - Activo. Créditos por operaciones de coaseguro [130]
36 521 17 N Entidades aseguradoras. Balance - Activo. Desembolsos exigidos [131]
37 538 17 N Entidades aseguradoras. Balance - Activo. Otros créditos [132]
38 555 17 N Entidades aseguradoras. Balance - Activo. Créditos con las Administraciones Públicas [133]
39 572 17 N Entidades aseguradoras. Balance - Activo. Resto de créditos [134]
4400 558899 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass.. BBaallaannccee - AAccttiivvoo.. IInnvveerrssiioonneess mmaanntteenniiddaass hhaassttaa eell vveenncciimmiieennttoo [[113355]]
41 606 17 N Entidades aseguradoras. Balance - Activo. Derivados de cobertura [136]
42 623 17 N Entidades aseguradoras. Balance - Activo. Participación del reaseguro en las provisiones técnicas [137]
43 640 17 N Entidades aseguradoras. Balance - Activo. Provisión para primas no consumidas [138]
44 657 17 N Entidades aseguradoras. Balance - Activo. Provisión de seguros de vida [139]
45 674 17 N Entidades aseguradoras. Balance - Activo. Provisión para prestaciones [140]
46 691 17 N Entidades aseguradoras. Balance - Activo. Otras provisiones técnicas [141]
47 708 17 N Entidades aseguradoras. Balance - Activo. Inmovilizado material e inversiónes inmobiliarias [142]
48 725 17 N Entidades aseguradoras. Balance - Activo. Inmovilizado material [143]
49 742 17 N Entidades aseguradoras. Balance - Activo. Inversiones inmobiliarias [144]
50 759 17 N Entidades aseguradoras. Balance - Activo. Inmovilizado intangible [145]
51 776 17 N Entidades aseguradoras. Balance - Activo. Fondo de comercio [146]
17 N Entidades aseguradoras. Balance - Activo. Derechos económicos derivados carteras de pólizas adquiridas a
5522 779933 meddiiaddores [[114477]]
53 810 17 N Entidades aseguradoras. Balance - Activo. Otro activo intangible [148]
54 827 17 N Entidades aseguradoras. Balance - Activo. Participaciones en entidades del grupo y asociadas [149]
55 844 17 N Entidades aseguradoras. Balance - Activo. Participaciones en empresas asociadas [150]
56 861 17 N Entidades aseguradoras. Balance - Activo. Participaciones en empresas multigrupo [151]
57 878 17 N Entidades aseguradoras. Balance - Activo. Participaciones en empresas del grupo [152]
58 895 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200032>"
Total: 904
Página 52

# Pag. 53

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "033"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass. BBaallaannccee - AAccttiivvoo. AAccttiivvooss ffiissccaalleess [[115533]]
7 28 17 N Entidades aseguradoras. Balance - Activo. Activos por impuesto corriente [154]
8 45 17 N Entidades aseguradoras. Balance - Activo. Activos por impuesto diferido [155]
9 62 17 N Entidades aseguradoras. Balance - Activo. Otros activos [156]
17 N Entidades aseguradoras. Balance - Activo. Activos y derechos de reembolso por retribuciones a largo plazo al
10 79 personal [157]
11 96 17 N Entidades aseguradoras. Balance - Activo. Comisiones anticipadas y otros costes adquisición [158]
12 113 17 N Entidades aseguradoras. Balance - Activo. Periodificaciones [159]
13 130 17 N Entidades aseguradoras. Balance - Activo. Resto de activos [160]
14 147 17 N Entidades aseguradoras. Balance - Activo. Activos mantenidos para la venta [161]
15 164 17 N Entidades aseguradoras. Balance - Activo. TOTAL ACTIVO [162]
16 181 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200033>"
TToottaall:: 119900
Página 53

# Pag. 54

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimiens permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "034"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass. BBaallaannccee - PPaassiivvoo.PPaassiivvooss ffiinnaanncciieerrooss mmaanntteenniiddooss ppaarraa nneeggoocciiaarr [[116633]]
17 N Entidades aseguradoras. Balance - Pasivo. Otros pasivos financieros a valor razonable con cambios en pérdidas y
7 28 ganancias. [164]
8 45 17 N Entidades aseguradoras. Balance - Pasivo. Débitos y partidas a pagar [165]
9 62 17 N Entidades aseguradoras. Balance - Pasivo. Pasivos subordinados [166]
10 79 17 N Entidades Aseguradoras. Balance - Pasivo.Depósitos recibidos por reaseguro cedido [167]
11 96 17 N Entidades aseguradoras. Balance - Pasivo.Deudas por operaciones de seguro [168]
12 113 17 N Entidades Aseguradoras. Balance - Pasivo.Deudas con asegurados [169]
13 130 17 N Entidades aseguradoras. Balance - Pasivo. Deudas con mediadores [170]
14 147 17 N Entidades aseguradoras. Balance - Pasivo.Deudas condicionadas [171]
15 164 17 N Entidades aseguradoras. Balance - Pasivo. Deudas por operaciones de reaseguro [172]
16 181 17 N Entidades aseguradoras. Balance - Pasivo. Deudas por operaciones de coaseguro [173]
1177 119988 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass.. BBaallaannccee - PPaassiivvoo..OObblliiggaacciioonneess yy oottrrooss vvaalloorreess nneeggoocciiaabblleess [[117744]]
18 215 17 N Entidades aseguradoras. Balance - Pasivo. Deudas con entidades de crédito [175]
17 N Entidades Aseguradoras. Balance - Pasivo.Deudas por operaciones preparatorias de contratos de seguro [176]
19 232
20 249 17 N Entidades aseguradoras. Balance - Pasivo. Otras deudas [177]
21 266 17 N Entidades aseguradoras. Balance - Pasivo. Deudas con las Administraciones Públicas [178]
22 283 17 N Entidades aseguradoras. Balance - Pasivo. Otras deudas con entidades del grupo y asociadas [179]
23 300 17 N Entidades aseguradoras. Balance - Pasivo. Resto de otras deudas [180]
24 317 17 N Entidades aseguradoras. Balance - Pasivo. Derivados de cobertura [181]
25 334 17 N Entidades aseguradoras. Balance - Pasivo. Provisiones técnicas [182]
26 351 17 N Entidades aseguradoras. Balance - Pasivo. Provisión para primas no consumidas [183]
27 368 17 N Entidades aseguradoras. Balance - Pasivo. Provisión para riesgos en curso [184]
28 385 17 N Entidades aseguradoras. Balance - Pasivo.Provision de seguros de vida [185]
2299 440022 1177 NN EEnttiiddaddes aseguraddoras. BBallance - PPasiivo. PProviisiióón para priimas no consumiiddas [[118866]]
30 419 17 N Entidades aseguradoras. Balance - Pasivo. Provisión para riesgos en curso [187]
31 436 17 N Entidades aseguradoras. Balance - Pasivo. Provisión matemática [188]
17 N Entidades aseguradoras. Balance - Pasivo. Provisión de seguros de vida cuando el riesgo de la inversión lo asuma
32 453 el tomador [189]
33 470 17 N Entidades aseguradoras. Balance - Pasivo. Provisión para prestaciones [190]
17 N Entidades aseguradoras. Balance - Pasivo. Provisión para participación en beneficios y para extornos [191]
34 487
35 504 17 N Entidades aseguradoras. Balance - Pasivo. Otras provisiones técnicas [192]
36 521 17 N Entidades aseguradoras. Balance - Pasivo. Provisiones no técnicas [193]
17 N Entidades aseguradoras. Balance - Pasivo. Provisiones para impuestos y otras contingencias legales [194]
37 538
38 555 17 N Entidades aseguradoras. Balance - Pasivo. Provisión para pensiones y obligaciones similiares [195]
39 572 17 N Entidades aseguradoras. Balance - Pasivo. Provisión para pagos por convenios de liquidación [196]
40 589 17 N Entidades aseguradoras. Balance - Pasivo. Otras provisiones no técnicas [197]
41 606 17 N Entidades aseguradoras. Balance - Pasivo. Pasivos fiscales [198]
42 623 17 N Entidades aseguradoras. Balance - Pasivo. Pasivos por impuesto corriente [199]
43 640 17 N Entidades aseguradoras. Balance - Pasivo. Pasivos por impuesto diferido [200]
44 657 17 N Entidades aseguradoras. Balance - Pasivo. Resto de pasivos [201]
45 674 17 N Entidades aseguradoras. Balance - Pasivo. Periodificaciones [202]
46 691 17 N Entidades aseguradoras. Balance - Pasivo. Pasivos por asimetrías contables [203]
17 N Entidades aseguradoras. Balance - Pasivo. Comisiones y otros costes de adquisición del reaseguro cedido [204]
47 708
48 725 17 N Entidades aseguradoras. Balance - Pasivo. Otros pasivos [205]
17 N Entidades aseguradoras. Balance - Pasivo. Pasivos vinculados con activos mantenidos para la venta [206]
4499 774422
50 759 17 N Entidades aseguradoras. Balance - Pasivo. TOTAL PASIVO [207]
51 776 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200034>"
Total: 785
Página 54

# Pag. 55

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "035"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass. BBaallaannccee -PPaattrriimmoonniioo NNeettoo. FFoonnddooss pprrooppiiooss [[220088]]
7 28 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Capital o fondo mutual [209]
8 45 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Capital escriturado o fondo mutual [210]
9 62 17 N Entidades aseguradoras. Balance -Patrimonio Neto.(Capital no exigido) [211]
10 79 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Prima de emisión [212]
11 96 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Reservas [213]
12 113 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Legal y estatutarias [214]
13 130 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Reserva de estabilización [215]
14 147 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Otras reservas [216]
15 164 17 N Entidades aseguradoras. Balance -Patrimonio Neto.(Acciones propias) [217]
16 181 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Resultados de ejercicios anteriores [218]
17 198 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Remanente [219]
1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass.. BBaallaannccee --PPaattrriimmoonniioo NNeettoo..((RReessuullttaaddooss nneeggaattiivvooss ddee eejjeerrcciicciiooss aanntteerriioorreess)) [[222200]]
18 215
19 232 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Otras aportaciones de socios y mutualistas [221]
20 249 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Resultado del ejercicio [222]
17 N Entidades aseguradoras. Balance -Patrimonio Neto. (Dividendo a cuenta y reserva de estabilización a cuenta)
21 266 [223]
22 283 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Otros instrumentos de patrimonio neto [224]
23 300 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Ajustes por cambios de valor [225]
24 317 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Activos financieros disponibles para la venta [226]
25 334 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Operaciones de cobertura [227]
26 351 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Diferencias de cambio y conversión [228]
27 368 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Corrección de asimetrías contables [229]
28 385 17 N Entidades aseguradoras. Balance -Patrimonio Neto. Otros ajustes [230]
1177 NN EEnttiiddaddes aseguraddoras. BBallance -PPattriimoniio NNetto. SSubbvenciiones, ddonaciiones y llegaddos reciibbiiddos [[223311]]
29 402
30 419 17 N Entidades aseguradoras. Balance -Patrimonio Neto. TOTAL PATRIMONIO NETO [232]
31 436 17 N Entidades aseguradoras. Balance -Patrimonio Neto. TOTAL PASIVO Y PATRIMONIO NETO [233]
32 453 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200035>"
Total: 462
Página 55

# Pag. 56

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "036"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass. PPéérrddiiddaass yy ggaannaanncciiaass - CCuueennttaa sseegguurroo nnoo vviiddaa. PPrriimmaass iimmppuuttaaddaass aall eejjeerrcciicciioo [[223344]]
7 28 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Primas devengadas [235]
8 45 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Seguro directo [236]
9 62 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Reaseguro aceptado [237]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Variación por deterioro de las primas
10 79 pendientes de cobro (+ ó -) [238]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Primas reaseguro cedido (-) [239]
11 96
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Variación provisión primas no
12 113 consumidas (+ ó -) [240]
13 130 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Seguro directo [241]
14 147 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Reaseguro aceptado [242]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Variación provisión primas no
15 164 consumidas, reaseguro cedido (+ó -) [243]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Ingresos inmovilizado material [244]
16 181
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Ingresos inversiones inmobiliarias [245]
17 198
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Ingresos inversiones financieras [246]
18 215
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Aplic.correcciones de valor por deterioro
19 232 del inmovilizado material y de las inversiones [247]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Inmovilizado material e inv.inmobiliarias
20 249 [248]
21 266 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Inversiones financieras [249]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Beneficios inmovilizado material [250]
2222 228833
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Inmovilizado material e inv.inmobiliarias
23 300 [251]
24 317 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Inversiones financieras [252]
25 334 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Otros ingresos técnicos [253]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Siniestralidad del ejercicio [254]
26 351
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Prestaciones y gastos pagados [255]
27 368
28 385 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Seguro directo [256]
29 402 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Reaseguro aceptado [257]
30 419 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Reaseguro cedido (-) [258]
17 N Entidades asegguradoras. Pérdidas yy gganancias - Cuenta segguro no vida. Variación pprovisión ppara pprestaciones ((+
31 436 ó -) [259]
32 453 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Seguro directo [260]
33 470 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Reaseguro aceptado [261]
34 487 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Reaseguro cedido (-) [262]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Gastos imputables prestaciones [263]
35 504
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Variación otras provisiones técnicas,
36 521 netas de reaseguro (+ ó -) [264]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Participación en beneficios y extornos
37 538 [265]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Prestaciones y gastos participación en
38 555 beneficios y extornos [266]
17 N Entidades asegguradoras. Pérdidas yy gganancias - Cuenta segguro no vida. Variación pprovisión beneficios yy extornos
39 572 (+ ó -) [267]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Gastos explotación netos [268]
40 589
41 606 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Gastos adquisición [269]
42 623 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Gastos administración [270]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Comisiones y participaciones [271]
43 640
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Otros gastos técnicos (+ ó -) [272]
44 657
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Variación deterioro por insolvencias (+ ó -
45 674 ) [273]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Variación deterioro inmovilizado (+ ó -
46 691 ) [274]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Variación prestaciones por convenios (+
47 708 ó -) [275]
48 725 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Otros [276]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Gastos inmovilizado material e
49 742 inversiones [277]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Gastos gestión inversiones [278]
50 759
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Gastos inmovilizado material e
51 776 inv.inmobiliarias [279]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Gastos inversiones y ctas.financieras
52 793 [280]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Correciones valor inmovilizado [281]
53 810
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Amortización inmovilizado material [282]
54 827
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Deterioro inmovilizado material [283]
55 844
Página 56

# Pag. 57

17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Deterioro inversiones financieras [284]
56 861
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Pérdidas del inmovilizado material [285]
57 878
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Inmovilizado material e inv.inmobiliarias
58 895 [286]
59 912 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Inversiones financieras [287]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro no vida. Subtotal. (Resultado de la cuenta técnica
60 929 del seguro no vida) [288]
61 946 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200036>"
Total: 955
Página 57

# Pag. 58

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "037"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
6 11 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Primas imputadas al ejercicio [289]
77 2288 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass. PPéérrddiiddaass yy ggaannaanncciiaass -- CCuueennttaa sseegguurroo ddee vviiddaa. PPrriimmaass ddeevveennggaaddaass [[229900]]
8 45 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Seguro directo [291]
9 62 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Reaseguro aceptado [292]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Variación por deterioro de las primas
10 79 pendientes [293]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Primas reaseguro cedido [294]
11 96
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Variación provisión primas no consumidas
12 113 [295]
13 130 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Seguro directo [296]
14 147 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Reaseguro aceptado [297]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Variación provisión primas no
15 164 consumidas, reaseguro cedido [298]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Ingresos inmovilizado material [299]
1166 118811
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Ingresos inversiones inmobiliarias [300]
17 198
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Ingresos inversiones financieras [301]
18 215
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Aplic.correcciones de valor por deterioro
19 232 [302]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Inmovilizado material e inv.inmobiliarias
20 249 [303]
21 266 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Inversiones financieras [304]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Beneficios inmovilizado material [305]
22 283
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Inmovilizado material e inv.inmobiliarias
23 300 [306]
24 317 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Inversiones financieras [307]
1177 NN EEnttiiddaddes aseguraddoras. PPéérddiiddas y gananciias - CCuentta seguro dde viidda. IInversiiones affecttas a seguros [[330088]]
25 334
26 351 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Otros ingresos ténicos [309]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Siniestralidad del ejercicio [310]
27 368
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Prestaciones y gastos pagados [311]
28 385
29 402 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Seguro directo [312]
30 419 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Reaseguro aceptado [313]
31 436 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Reaseguro cedido [314]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Variación provisión prestaciones [315]
32 453
33 470 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Seguro directo [316]
34 487 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Reaseguro aceptado [317]
3355 550044 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass. PPéérrddiiddaass yy ggaannaanncciiaass - CCuueennttaa sseegguurroo ddee vviiddaa. RReeaasseegguurroo cceeddiiddoo [[331188]]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Gastos imputables prestaciones [319]
36 521
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Variación otras provisiones técnicas [320]
37 538
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Provisiones seguros de vida [321]
38 555
39 572 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Seguro directo [322]
40 589 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Reaseguro aceptado [323]
41 606 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Reaseguro cedido [324]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Provisiones seguros de vida riesgo
42 623 tomadores [325]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Otras provisiones técnicas [326]
43 640
4444 665577 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass.. PPéérrddiiddaass yy ggaannaanncciiaass -- CCuueennttaa sseegguurroo ddee vviiddaa.. PPaarrttiicciippaacciióónn bbeenneeffiicciiooss [[332277]]
45 674 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Prestaciones y gastos [328]
46 691 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Variación provisión [329]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Gastos explotación netos [330]
47 708
48 725 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Gastos adquisición [331]
49 742 17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Gastos administración [332]
17 N Entidades aseguradoras. Pérdidas y ganancias - Cuenta seguro de vida. Comisiones y participaciones [333]
50 759
51 776 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200037>"
Total: 785
Página 58

# Pag. 59

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "038"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass PPéérrddiiddaass yy ggaannaanncciiaass - SSeegguurroo vviiddaa. OOttrrooss ggaassttooss ttééccnniiccooss [[333344]]
7 28 17 N Entidades aseguradoras Pérdidas y ganancias - Seguro vida. Variación deterioro por insolvencias [335]
8 45 17 N Entidades aseguradoras Pérdidas y ganancias - Seguro vida. Variación deterioro del inmovilizado [336]
9 62 17 N Entidades aseguradoras Pérdidas y ganancias - Seguro vida. Otros [337]
17 N Entidades aseguradoras Pérdidas y ganancias - Seguro vida. Gastos del inmovilizado material y de las inversiones
10 79 [338]
17 N Entidades aseguradoras Pérdidas y ganancias - Seguro vida. Gastos de gestión del inmovilizado material y de las
11 96 inversiones [339]
17 N Entidades aseguradoras Pérdidas y ganancias - Seguro vida. Gastos del inmovilizado material y de las inversiones
12 113 inmobiliarias [340]
17 N Entidades aseguradoras Pérdidas y ganancias - Seguro vida. Gastos de inversiones y cuentas financieras [341]
13 130
17 N Entidades aseguradoras Pérdidas y ganancias - Seguro vida. Correcciones del valor del inmovilizado material y de
1144 114477 llas iinversiiones [[334422]]
17 N Entidades aseguradoras Pérdidas y ganancias - Seguro vida. Amortización del inmovilizado material y de las
15 164 inversiones inmobiliarias [343]
17 N Entidades aseguradoras Pérdidas y ganancias - Seguro vida. Deterioro del inmovilizado material y de las
16 181 inversiones inmobiliarias [344]
17 N Entidades aseguradoras Pérdidas y ganancias - Seguro vida. Deterioro de inversiones financieras [345]
17 198
17 N Entidades aseguradoras Pérdidas y ganancias - Seguro vida. Pérdidas procedentes del inmovilizado material y de
18 215 las inversiones [346]
17 N Entidades aseguradoras Pérdidas y ganancias - Seguro vida. Del inmovilizado material y de las inversiones
19 232 inmobiliarias [347]
20 249 17 N Entidades aseguradoras Pérdidas y ganancias - Seguro vida. De las inversiones financieras [348]
17 N Entidades aseguradoras Pérdidas y ganancias - Seguro vida. Gastos de inversiones afectas a seguros en los que
2211 226666 eell ttoommaaddoorr aassuummee eell rriieessggoo ddee llaa iinnvveerrssiióónn [[334499]]
17 N Entidades aseguradoras Pérdidas y ganancias - Seguro vida. Subtotal (Resultado de la cuenta técnica del seguro
22 283 de vida) [350]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Ingresos del inmovilizado material y de las
23 300 inversiones [351]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Ingresos procedentes de las inversiones
24 317 inmobiliarias [352]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Ingresos procedentes de las inversiones
25 334 financieras [353]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Aplicaciones de correcciones del valor por
26 351 deterioro del inmovilizado material y de las inversiones [354]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Del inmovilizado material y de las inversiones
27 368 inmobiliarias [355]
2288 338855 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass PPéérrddiiddaass yy ggaannaanncciiaass - CCuueennttaa nnoo ttééccnniiccaa. DDee iinnvveerrssiioonneess ffiinnaanncciieerraass [[335566]]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Beneficios en realización del inmovilizado
29 402 material y de las inversiones [357]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Del inmovilizado material y de las inversiones
30 419 inmobiliarias [358]
31 436 17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. De inversiones financieras [359]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Gastos del inmovilizado material y de las
32 453 inversiones [360]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Gastos de gestión de las inversiones [361]
33 470
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Gastos de inversiones y cuentas financieras
34 487 [362]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Gastos de inversiones materiales [363]
3355 550044
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Correcciones del valor del inmovilizado
36 521 material y de las inversiones [364]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Amortización del inmovilizado material y de las
37 538 inversiones inmobiliarias [365]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Deterioro del inmovilizado material y de las
38 555 inversiones inmobiliarias [366]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Deterioro de inversiones financieras [367]
39 572
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Pérdidas procedentes del inmovilizado
40 589 material y de las inversiones [368]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Del inmovilizado material y de las inversiones
41 606 inmobiliarias [369]
1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass PPéérrddiiddaass yy ggaannaanncciiaass -- CCuueennttaa nnoo ttééccnniiccaa.. DDee llaass iinnvveerrssiioonneess ffiinnaanncciieerraass [[337700]]
42 623
43 640 17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Otros ingresos [371]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Ingresos por la administración de fondos de
44 657 pensiones [372]
45 674 17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Resto de ingresos [373]
46 691 17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Otros gastos [374]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Gastos por la administración de fondos de
47 708 pensiones [375]
48 725 17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Resto de gastos [376]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Subtotal (resultado de la cuenta no técnica)
49 742 [377]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Resultado antes de impuestos [378]
5500 775599
51 776 17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Impuesto sobre beneficios [379]
17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Resultado procedente de operaciones
52 793 continuadas [380]
Página 59

# Pag. 60

17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Resultado procedente de operaciones
53 810 interrumpidas neto de impuestos [381]
54 827 17 N Entidades aseguradoras Pérdidas y ganancias - Cuenta no técnica. Resultado del ejercicio [500]
55 844 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200038>"
Total: 853
Página 60

# Pag. 61

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "039"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass PPaattrriimmoonniioo pprrooppiioo - IInnggrreessooss yy ggaassttooss rreeccoonnoocciiddooss. RReessuullttaaddoo ddeell eejjeerrcciicciioo [[550000]]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Otros ingresos y gastos reconocidos
7 28 [383]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Activos financieros disponibles para
8 45 la venta [384]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Ganancias y pérdidas por valoración
9 62 [385]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Importes transferidos a la cuenta de
10 79 pérdidas y ganancias [386]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Otras reclasificaciones [387]
11 96
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Coberturas de los flujos de efectivo
12 113 [388]
1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass PPaattrriimmoonniioo pprrooppiioo - IInnggrreessooss yy ggaassttooss rreeccoonnoocciiddooss. GGaannaanncciiaass yy ppéérrddiiddaass ppoorr vvaalloorraacciióónn
13 130 [389]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Importes transferidos a la cuenta de
14 147 pérdidas y ganancias [390]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Importes transferidos al valor inicial
15 164 de las partidas cubiertas [391]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Otras reclasificaciones [392]
16 181
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Coberturas de inversiones netas en
17 198 negocios en el extranjero [393]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Ganancias y pérdidas por valoración
18 215 [394]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Importes transferidos a la cuenta de
1199 223322 ppéérrddiiddaass yy ggaannaanncciiaass [[339955]]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Otras reclasificaciones [396]
20 249
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Diferencias de cambio y conversión
21 266 [397]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Ganancias y pérdidas por valoración
22 283 [398]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Importes transferidos a la cuenta de
23 300 pérdidas y ganancias [399]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Otras reclasificaciones [400]
24 317
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Corrección de asimetrías contables
25 334 [401]
1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass PPaattrriimmoonniioo pprrooppiioo -- IInnggrreessooss yy ggaassttooss rreeccoonnoocciiddooss.. GGaannaanncciiaass yy ppéérrddiiddaass ppoorr vvaalloorraacciióónn
26 351 [402]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Importes transferidos a la cuenta de
27 368 pérdidas y ganancias [403]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Otras reclasificaciones [404]
28 385
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Activos mantenidos para la venta
29 402 [405]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Ganancias y pérdidas por valoración
30 419 [406]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Importes transferidos a la cuenta de
31 436 pérdidas y ganancias [407]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Otras reclasificaciones [408]
3322 445533
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Ganancias / (pérdidas) actuariales
33 470 por retribuciones a largo plazo del personal [409]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Otros ingresos y gastos reconocidos
34 487 [410]
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Impuesto sobre beneficios [411]
35 504
17 N Entidades aseguradoras Patrimonio propio - Ingresos y gastos reconocidos. Total de ingresos y gastos
36 521 reconocidos [412]
37 538 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200039>"
Total: 547
Página 61

# Pag. 62

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "040"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass PPaattrriimmoonniioo pprrooppiioo - SSaallddoo ffiinnaall eejjeerrcciicciioo. EEssccrriittuurraaddoo [[441133]]
7 28 17 N Entidades aseguradoras Patrimonio propio - Saldo final ejercicio. (No exigido) [414]
8 45 17 N Entidades aseguradoras Patrimonio propio - Saldo final ejercicio. Prima emisión [415]
9 62 17 N Entidades aseguradoras Patrimonio propio - Saldo final ejercicio. Reservas [416]
17 N Entidades aseguradoras Patrimonio propio - Saldo final ejercicio . (Acciones en patrimonio propias) [417]
10 79
17 N Entidades aseguradoras Patrimonio propio - Saldo final ejercicio. Resultados de ejercicios anteriores [418]
11 96
17 N Entidades aseguradoras Patrimonio propio - Saldo final ejercicio. Otras aportaciones de socios o mutualistas [419]
12 113
17 N Entidades aseguradoras Patrimonio propio - Ajustes por cambios de criterio de ejercicios anteriores. Escriturado
13 130 [426]
17 N Entidades aseguradoras Patrimonio propio - Ajustes por cambios de criterio de ejercicios anteriores. (No exigido)
1144 114477 [[442277]]
17 N Entidades aseguradoras Patrimonio propio - Ajustes por cambios de criterio de ejercicios anteriores. Prima emisión
15 164 [428]
17 N Entidades aseguradoras Patrimonio propio - Ajustes por cambios de criterio de ejercicios anteriores. Reservas [429]
16 181
17 N Entidades aseguradoras Patrimonio propio - Ajustes por cambios de criterio de ejercicios anteriores. (Acciones en
17 198 patrimonio propias) [430]
17 N Entidades aseguradoras Patrimonio propio - Ajustes por cambios de criterio de ejercicios anteriores. Resultados de
18 215 ejercicios anteriores [431]
17 N Entidades aseguradoras Patrimonio propio - Ajustes por cambios de criterio de ejercicios anteriores. Otras
19 232 aportaciones de socios o mutualistas [432]
17 N Entidades aseguradoras Patrimonio propio - Ajustes por errores de ejercicios anteriores. Escriturado [439]
20 249
1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass PPaattrriimmoonniioo pprrooppiioo - AAjjuusstteess ppoorr eerrrroorreess ddee eejjeerrcciicciiooss aanntteerriioorreess. ((NNoo eexxiiggiiddoo)) [[444400]]
21 266
17 N Entidades aseguradoras Patrimonio propio - Ajustes por errores de ejercicios anteriores. Prima emisión [441]
22 283
17 N Entidades aseguradoras Patrimonio propio - Ajustes por errores de ejercicios anteriores. Reservas [442]
23 300
17 N Entidades aseguradoras Patrimonio propio - Ajustes por errores de ejercicios anteriores. (Acciones en patrimonio
24 317 propias) [443]
17 N Entidades aseguradoras Patrimonio propio - Ajustes por errores de ejercicios anteriores. Resultados de ejercicios
25 334 anteriores [444]
17 N Entidades aseguradoras Patrimonio propio - Ajustes por errores de ejercicios anteriores. Otras aportaciones de
26 351 socios o mutualistas [445]
27 368 17 N Entidades aseguradoras Patrimonio propio - Saldo ajustado, inicio del ejercicio. Escriturado [452]
2288 338855 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass PPaattrriimmoonniioo pprrooppiioo - SSaallddoo aajjuussttaaddoo, iinniicciioo ddeell eejjeerrcciicciioo. ((NNoo eexxiiggiiddoo)) [[445533]]
29 402 17 N Entidades aseguradoras Patrimonio propio - Saldo ajustado, inicio del ejercicio. Prima emisión [454]
30 419 17 N Entidades aseguradoras Patrimonio propio - Saldo ajustado, inicio del ejercicio. Reservas [455]
17 N Entidades aseguradoras Patrimonio propio - Saldo ajustado, inicio del ejercicio. (Acciones en patrimonio propias)
31 436 [456]
17 N Entidades aseguradoras Patrimonio propio - Saldo ajustado, inicio del ejercicio. Resultados de ejercicios anteriores
32 453 [457]
17 N Entidades aseguradoras Patrimonio propio - Saldo ajustado, inicio del ejercicio. Otras aportaciones de socios o
33 470 mutualistas [458]
34 487 17 N Entidades aseguradoras Patrimonio propio - Total ingresos y gastos reconocidos. Escriturado [465]
35 504 17 N Entidades aseguradoras Patrimonio propio - Total ingresos y gastos reconocidos. (No exigido) [466]
36 521 17 N Entidades aseguradoras Patrimonio propio - Total ingresos y gastos reconocidos. Prima emisión [467]
37 538 17 N Entidades aseguradoras Patrimonio propio - Total ingresos y gastos reconocidos. Reservas [468]
1177 NN EEnttiiddaddes aseguraddoras PPattriimoniio propiio - TTottall iingresos y gasttos reconociiddos. ((AAcciiones en pattriimoniio propiias))
38 555 [469]
17 N Entidades aseguradoras Patrimonio propio - Total ingresos y gastos reconocidos. Resultados de ejercicios
39 572 anteriores [470]
17 N Entidades aseguradoras Patrimonio propio - Total ingresos y gastos reconocidos. Otras aportaciones de socios o
40 589 mutualistas [471]
41 606 17 N Entidades aseguradoras Patrimonio propio - Operaciones con socios o mutualistas. Escriturado [478]
42 623 17 N Entidades aseguradoras Patrimonio propio - Operaciones con socios o mutualistas. (No exigido) [479]
17 N Entidades aseguradoras Patrimonio propio - Operaciones con socios o mutualistas. Prima emisión [480]
43 640
44 657 17 N Entidades aseguradoras Patrimonio propio - Operaciones con socios o mutualistas. Reservas [481]
17 N Entidades aseguradoras Patrimonio propio - Operaciones con socios o mutualistas. (Acciones en patrimonio
45 674 propias) [482]
17 N Entidades aseguradoras Patrimonio propio - OOperaciones con socios o mutualistas. Resultados de ejercicios
46 691 anteriores [483]
17 N Entidades aseguradoras Patrimonio propio - Operaciones con socios o mutualistas. Otras aportaciones de socios o
47 708 mutualistas [484]
48 725 17 N Entidades aseguradoras Patrimonio propio - Aumentos del capital o fondo mutual. Escriturado [491]
49 742 17 N Entidades aseguradoras Patrimonio propio - Aumentos del capital o fondo mutual. (No exigido) [492]
50 759 17 N Entidades aseguradoras Patrimonio propio - Aumentos del capital o fondo mutual. Prima emisión [493]
51 776 17 N Entidades aseguradoras Patrimonio propio - Aumentos del capital o fondo mutual. Reservas [494]
17 N Entidades aseguradoras Patrimonio propio - Aumentos del capital o fondo mutual. (Acciones en patrimonio propias)
52 793 [495]
17 N Entidades aseguradoras Patrimonio propio - Aumentos del capital o fondo mutual. Resultados de ejercicios
53 810 anteriores [496]
17 N Entidades aseguradoras Patrimonio propio - Aumentos del capital o fondo mutual. Otras aportaciones de socios o
54 827 mutualistas [497]
55 844 17 N Entidades aseguradoras Patrimonio propio - Reducciones del capital o fondo mutual. Escriturado [504]
17 N Entidades aseguradoras Patrimonio propio - Reducciones del capital o fondo mutual. (No exigido) [505]
56 861
Página 62

# Pag. 63

17 N Entidades aseguradoras Patrimonio propio - Reducciones del capital o fondo mutual. Prima emisión [506]
57 878
58 895 17 N Entidades aseguradoras Patrimonio propio - Reducciones del capital o fondo mutual. Reservas [507]
17 N Entidades aseguradoras Patrimonio propio - Reducciones del capital o fondo mutual. (Acciones en patrimonio
59 912 propias) [508]
17 N Entidades aseguradoras Patrimonio propio - Reducciones del capital o fondo mutual. Resultados de ejercicios
60 929 anteriores [509]
17 N Entidades aseguradoras Patrimonio propio - Reducciones del capital o fondo mutual. Otras aportaciones de socios
61 946 o mutualistas [510]
17 N Entidades aseguradoras Patrimonio propio - Conversión de pasivos financ. en patr. neto. Escriturado [517]
62 963
17 N Entidades aseguradoras Patrimonio propio - Conversión de pasivos financ. en patr. neto. (No exigido) [518]
63 980
17 N Entidades aseguradoras Patrimonio propio - Conversión de pasivos financ. en patr. neto. Prima emisión [519]
64 997
17 N Entidades aseguradoras Patrimonio propio - Conversión de pasivos financ. en patr. neto. Reservas [520]
65 1014
17 N Entidades aseguradoras Patrimonio propio - Conversión de pasivos financ. en patr. neto. (Acciones en patrimonio
66 1031 propias) [521]
17 N Entidades aseguradoras Patrimonio propio - Conversión de pasivos financ. en patr. neto. Resultados de ejercicios
67 1048 anteriores [522]
17 N Entidades aseguradoras Patrimonio propio - Conversión de pasivos financ. en patr. neto. Otras aportaciones de
68 1065 socios o mutualistas [523]
17 N Entidades aseguradoras Patrimonio propio - Distribución de dividendos o derramas activas. Escriturado [530]
69 1082
17 N Entidades aseguradoras Patrimonio propio - Distribución de dividendos o derramas activas. (No exigido) [531]
7700 11009999
17 N Entidades aseguradoras Patrimonio propio - Distribución de dividendos o derramas activas. Prima emisión [532]
71 1116
17 N Entidades aseguradoras Patrimonio propio - Distribución de dividendos o derramas activas. Reservas [533]
72 1133
17 N Entidades aseguradoras Patrimonio propio - Distribución de dividendos o derramas activas. (Acciones en
73 1150 patrimonio propias) [534]
17 N Entidades aseguradoras Patrimonio propio - Distribución de dividendos o derramas activas. Resultados de
74 1167 ejercicios anteriores [535]
17 N Entidades aseguradoras Patrimonio propio - Distribución de dividendos o derramas activas. Otras aportaciones de
75 1184 socios o mutualistas [536]
17 N Entidades aseguradoras Patrimonio propio - Operaciones con acciones o participaciones propias (netas).
76 1201 Escriturado [543]
1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass PPaattrriimmoonniioo pprrooppiioo - OOppeerraacciioonneess ccoonn aacccciioonneess oo ppaarrttiicciippaacciioonneess pprrooppiiaass ((nneettaass)). ((NNoo
77 1218 exigido) [544]
17 N Entidades aseguradoras Patrimonio propio - Operaciones con acciones o participaciones propias (netas). Prima
78 1235 emisión [545]
17 N Entidades aseguradoras Patrimonio propio - Operaciones con acciones o participaciones propias (netas). Reservas
79 1252 [546]
17 N Entidades aseguradoras Patrimonio propio - Operaciones con acciones o participaciones propias (netas). (Acciones
80 1269 en patrimonio propias) [547]
17 N Entidades aseguradoras Patrimonio propio - Operaciones con acciones o participaciones propias (netas).
81 1286 Resultados de ejercicios anteriores [548]
17 N Entidades aseguradoras Patrimonio propio - Operaciones con acciones o participaciones propias (netas). Otras
82 1303 aportaciones de socios o mutualistas [549]
17 N Entidades aseguradoras Patrimonio propio - Incremento (reducción) de patr. neto resultante de una combinación de
8833 11332200 nneeggoocciiooss. EEssccrriittuurraaddoo [[555566]]
17 N Entidades aseguradoras Patrimonio propio - Incremento (reducción) de patr. neto resultante de una combinación de
84 1337 negocios. (No exigido) [557]
17 N Entidades aseguradoras Patrimonio propio - Incremento (reducción) de patr. neto resultante de una combinación de
85 1354 negocios. Prima emisión [558]
17 N Entidades aseguradoras Patrimonio propio - Incremento (reducción) de patr. neto resultante de una combinación de
86 1371 negocios. Reservas [559]
17 N Entidades aseguradoras Patrimonio propio - Incremento (reducción) de patr. neto resultante de una combinación de
87 1388 negocios. (Acciones en patrimonio propias) [560]
17 N Entidades aseguradoras Patrimonio propio - Incremento (reducción) de patr. neto resultante de una combinación de
88 1405 negocios. Resultados de ejercicios anteriores [561]
17 N Entidades aseguradoras Patrimonio propio - Incremento (reducción) de patr. neto resultante de una combinación de
89 1422 negocios. Otras aportaciones de socios o mutualistas [562]
1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass PPaattrriimmoonniioo pprrooppiioo - OOttrraass ooppeerraacciioonneess ccoonn ssoocciiooss oo mmuuttuuaalliissttaass.. EEssccrriittuurraaddoo [[556699]]
90 1439
17 N Entidades aseguradoras Patrimonio propio - Otras operaciones con socios o mutualistas. (No exigido) [570]
91 1456
17 N Entidades aseguradoras Patrimonio propio - Otras operaciones con socios o mutualistas. Prima emisión [571]
92 1473
17 N Entidades aseguradoras Patrimonio propio - Otras operaciones con socios o mutualistas. Reservas [572]
93 1490
17 N Entidades aseguradoras Patrimonio propio - Otras operaciones con socios o mutualistas. (Acciones en patrimonio
94 1507 propias) [573]
17 N Entidades aseguradoras Patrimonio propio - Otras operaciones con socios o mutualistas. Resultados de ejercicios
95 1524 anteriores [574]
17 N Entidades aseguradoras Patrimonio propio - Otras operaciones con socios o mutualistas. Otras aportaciones de
96 1541 socios o mutualistas [[575]]
97 1558 17 N Entidades aseguradoras Patrimonio propio - Otras variaciones del patrimonio neto. Escriturado [582]
98 1575 17 N Entidades aseguradoras Patrimonio propio - Otras variaciones del patrimonio neto. (No exigido) [583]
17 N Entidades aseguradoras Patrimonio propio - Otras variaciones del patrimonio neto. Prima emisión [584]
99 1592
100 1609 17 N Entidades aseguradoras Patrimonio propio - Otras variaciones del patrimonio neto. Reservas [585]
17 N Entidades aseguradoras Patrimonio propio - Otras variaciones del patrimonio neto. (Acciones en patrimonio propias)
101 1626 [586]
17 N Entidades aseguradoras Patrimonio propio - Otras variaciones del patrimonio neto. Resultados de ejercicios
102 1643 anteriores [587]
17 N Entidades aseguradoras Patrimonio propio - Otras variaciones del patrimonio neto. Otras aportaciones de socios o
103 1660 mutualistas [588]
17 N Entidades aseguradoras Patrimonio propio - Pagos basados en instrumentos de patrimonio. Escriturado [595]
1004 16677
17 N Entidades aseguradoras Patrimonio propio - Pagos basados en instrumentos de patrimonio. (No exigido) [596]
105 1694
17 N Entidades aseguradoras Patrimonio propio - Pagos basados en instrumentos de patrimonio. Prima emisión [597]
106 1711
Página 63

# Pag. 64

17 N Entidades aseguradoras Patrimonio propio - Pagos basados en instrumentos de patrimonio. Reservas [598]
107 1728
17 N Entidades aseguradoras Patrimonio propio - Pagos basados en instrumentos de patrimonio. (Acciones en
108 1745 patrimonio propias) [599]
17 N Entidades aseguradoras Patrimonio propio - Pagos basados en instrumentos de patrimonio. Resultados de
109 1762 ejercicios anteriores [600]
17 N Entidades aseguradoras Patrimonio propio - Pagos basados en instrumentos de patrimonio. Otras aportaciones de
110 1779 socios o mutualistas [601]
17 N Entidades aseguradoras Patrimonio propio - Traspasos entre partidas de patrimonio neto. Escriturado [608]
111 1796
17 N Entidades aseguradoras Patrimonio propio - Traspasos entre partidas de patrimonio neto. (No exigido) [609]
112 1813
17 N Entidades aseguradoras Patrimonio propio - Traspasos entre partidas de patrimonio neto. Prima emisión [610]
111133 11883300
17 N Entidades aseguradoras Patrimonio propio - Traspasos entre partidas de patrimonio neto. Reservas [611]
114 1847
17 N Entidades aseguradoras Patrimonio propio - Traspasos entre partidas de patrimonio neto. (Acciones en patrimonio
115 1864 propias) [612]
17 N Entidades aseguradoras Patrimonio propio - Traspasos entre partidas de patrimonio neto. Resultados de ejercicios
116 1881 anteriores [613]
17 N Entidades aseguradoras Patrimonio propio - Traspasos entre partidas de patrimonio neto. Otras aportaciones de
117 1898 socios o mutualistas [614]
118 1915 17 N Entidades aseguradoras Patrimonio propio - Otras variaciones. Escriturado [621]
119 1932 17 N Entidades aseguradoras Patrimonio propio - Otras variaciones. (No exigido) [622]
120 1949 17 N Entidades aseguradoras Patrimonio propio - Otras variaciones. Prima emisión [623]
121 1966 17 N Entidades aseguradoras Patrimonio propio - Otras variaciones. Reservas [624]
122 1983 17 N Entidades aseguradoras Patrimonio propio - Otras variaciones. (Acciones en patrimonio propias) [625]
17 N Entidades aseguradoras Patrimonio propio - Otras variaciones. Resultados de ejercicios anteriores [626]
123 2000
17 N Entidades aseguradoras Patrimonio propio - Otras variaciones. Otras aportaciones de socios o mutualistas [627]
124 2017
125 2034 17 N Entidades aseguradoras Patrimonio propio - Saldo final del ejercicio. Escriturado [634]
126 2051 17 N Entidades aseguradoras Patrimonio propio - Saldo final del ejercicio. (No exigido) [635]
127 2068 17 N Entidades aseguradoras Patrimonio propio - Saldo final del ejercicio. Prima emisión [636]
128 2085 17 N Entidades aseguradoras Patrimonio propio - Saldo final del ejercicio. Reservas [637]
17 N Entidades aseguradoras Patrimonio propio - Saldo final del ejercicio. (Acciones en patrimonio propias) [638]
129 2102
17 N Entidades aseguradoras Patrimonio propio - Saldo final del ejercicio. Resultados de ejercicios anteriores [639]
130 2119
17 N Entidades aseguradoras Patrimonio propio - Saldo final del ejercicio. Otras aportaciones de socios o mutualistas
131 2136 [640]
132 2153 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200040>"
Total: 2162
Página 64

# Pag. 65

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "041"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass. PPaattrriimmoonniioo pprrooppiioo - SSaallddoo ffiinnaall eejjeerrcciicciioo aanntteerriioorr. RReessuullttaaddoo ddeell eejjeerrcciicciioo [[442200]]
7 28 17 N Entidades aseguradoras. Patrimonio propio - Saldo final ejercicio anterior. (Dividendo a cuenta) [421]
17 N Entidades aseguradoras. Patrimonio propio - Saldo final ejercicio anterior. Otros instrumentos de patrimonio [422]
8 45
17 N Entidades aseguradoras. Patrimonio propio - Saldo final ejercicio anterior. Ajustes por cambios de valor [423]
9 62
17 N Entidades aseguradoras. Patrimonio propio - Saldo final ejercicio anterior. Subvenciones donaciones y legados
10 79 [424]
11 96 17 N Entidades aseguradoras. Patrimonio propio - Saldo final ejercicio anterior. Total [425]
17 N Entidades aseguradoras. Patrimonio propio - Ajustes por cambios de criterio de ejercicios anteriores. Resultado del
12 113 ejercicio [433]
17 N Entidades aseguradoras. Patrimonio propio - Ajustes por cambios de criterio de ejercicios anteriores. (Dividendo a
13 130 cuenta) [434]
1177 NN EEnttiiddaddes aseguraddoras. PPattriimoniio propiio - AAjjusttes por cambbiios dde criitteriio dde ejjerciiciios antteriiores. OOttros
14 147 instrumentos de patrimonio [435]
17 N Entidades aseguradoras. Patrimonio propio - Ajustes por cambios de criterio de ejercicios anteriores. Ajustes por
15 164 cambios de valor [436]
17 N Entidades aseguradoras. Patrimonio propio - Ajustes por cambios de criterio de ejercicios anteriores.
16 181 Subvenciones donaciones y legados [437]
17 N Entidades aseguradoras. Patrimonio propio - Ajustes por cambios de criterio de ejercicios anteriores. Total [438]
17 198
17 N Entidades aseguradoras. Patrimonio propio - Ajustes por errores de ejercicios anteriores. Resultado del ejercicio
18 215 [446]
17 N Entidades aseguradoras. Patrimonio propio - Ajustes por errores de ejercicios anteriores. (Dividendo a cuenta)
19 232 [447]
17 N Entidades aseguradoras. Patrimonio propio - Ajustes por errores de ejercicios anteriores. Otros instrumentos de
2200 224499 ppaattrriimmoonniioo [[444488]]
17 N Entidades aseguradoras. Patrimonio propio - Ajustes por errores de ejercicios anteriores. Ajustes por cambios de
21 266 valor [449]
17 N Entidades aseguradoras. Patrimonio propio - Ajustes por errores de ejercicios anteriores. Subvenciones
22 283 donaciones y legados [450]
23 300 17 N Entidades aseguradoras. Patrimonio propio - Ajustes por errores de ejercicios anteriores. Total [451]
17 N Entidades aseguradoras. Patrimonio propio - Saldo ajustado, inicio del ejercicio. Resultado del ejercicio [459]
24 317
17 N Entidades aseguradoras. Patrimonio propio - Saldo ajustado, inicio del ejercicio. (Dividendo a cuenta) [460]
25 334
17 N Entidades aseguradoras. Patrimonio propio - Saldo ajustado, inicio del ejercicio. Otros instrumentos de patrimonio
26 351 [461]
17 N Entidades aseguradoras. Patrimonio propio - Saldo ajustado, inicio del ejercicio. Ajustes por cambios de valor [462]
2277 336688
17 N Entidades aseguradoras. Patrimonio propio - Saldo ajustado, inicio del ejercicio. Subvenciones donaciones y
28 385 legados [463]
29 402 17 N Entidades aseguradoras. Patrimonio propio - Saldo ajustado, inicio del ejercicio. Total [464]
17 N Entidades aseguradoras. Patrimonio propio - Total ingresos y gastos reconocidos. Resultado del ejercicio [472]
30 419
17 N Entidades aseguradoras. Patrimonio propio - Total ingresos y gastos reconocidos. (Dividendo a cuenta) [473]
31 436
17 N Entidades aseguradoras. Patrimonio propio - Total ingresos y gastos reconocidos. Otros instrumentos de
32 453 patrimonio [474]
17 N Entidades aseguradoras. Patrimonio propio - Total ingresos y gastos reconocidos. Ajustes por cambios de valor
33 470 [475]
17 N Entidades aseguradoras. Patrimonio propio - Total ingresos y gastos reconocidos. Subvenciones donaciones y
3344 448877 lleeggaaddooss [[447766]]
35 504 17 N Entidades aseguradoras. Patrimonio propio - Total ingresos y gastos reconocidos. Total [477]
17 N Entidades aseguradoras. Patrimonio propio - Operaciones con socios o mutualistas. Resultado del ejercicio [485]
36 521
17 N Entidades aseguradoras. Patrimonio propio - Operaciones con socios o mutualistas. (Dividendo a cuenta) [486]
37 538
17 N Entidades aseguradoras. Patrimonio propio - Operaciones con socios o mutualistas. Otros instrumentos de
38 555 patrimonio [487]
17 N Entidades aseguradoras. Patrimonio propio - Operaciones con socios o mutualistas. Ajustes por cambios de valor
39 572 [488]
17 N Entidades aseguradoras. Patrimonio propio - Operaciones con socios o mutualistas. Subvenciones donaciones y
40 589 legados [489]
41 606 17 N Entidades aseguradoras. Patrimonio propio - Operaciones con socios o mutualistas. Total [490]
1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass.. PPaattrriimmoonniioo pprrooppiioo -- AAuummeennttooss ddeell ccaappiittaall oo ffoonnddoo mmuuttuuaall.. RReessuullttaaddoo ddeell eejjeerrcciicciioo [[449988]]
42 623
17 N Entidades aseguradoras. Patrimonio propio - Aumentos del capital o fondo mutual. (Dividendo a cuenta) [499]
43 640
17 N Entidades aseguradoras. Patrimonio propio - Aumentos del capital o fondo mutual. Otros instrumentos de
44 657 patrimonio [382]
17 N Entidades aseguradoras. Patrimonio propio - Aumentos del capital o fondo mutual. Ajustes por cambios de valor
45 674 [501]
17 N Entidades aseguradoras. Patrimonio propio - Aumentos del capital o fondo mutual. Subvenciones donaciones y
46 691 legados [502]
47 708 17 N Entidades aseguradoras. Patrimonio propio - Aumentos del capital o fondo mutual. Total [503]
17 N Entidades aseguradoras. Patrimonio propio - (-) Reducciones del capital o fondo mutual. Resultado del ejercicio
48 725 [511]
1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass.. PPaattrriimmoonniioo pprrooppiioo - ((-)) RReedduucccciioonneess ddeell ccaappiittaall oo ffoonnddoo mmuuttuuaall.. ((DDiivviiddeennddoo aa ccuueennttaa))
49 742 [512]
17 N Entidades aseguradoras. Patrimonio propio - (-) Reducciones del capital o fondo mutual. Otros instrumentos de
50 759 patrimonio [513]
Página 65

# Pag. 66

17 N Entidades aseguradoras. Patrimonio propio - (-) Reducciones del capital o fondo mutual. Ajustes por cambios de
51 776 valor [514]
17 N Entidades aseguradoras. Patrimonio propio - (-) Reducciones del capital o fondo mutual. Subvenciones
52 793 donaciones y legados [515]
53 810 17 N Entidades aseguradoras. Patrimonio propio - (-) Reducciones del capital o fondo mutual. Total [516]
17 N Entidades aseguradoras. Patrimonio propio - Conversión de pasivos financ. en patr. neto. Resultado del ejercicio
54 827 [524]
17 N Entidades aseguradoras. Patrimonio propio - Conversión de pasivos financ. en patr. neto. (Dividendo a cuenta)
55 844 [525]
17 N Entidades aseguradoras. Patrimonio propio - Conversión de pasivos financ. en patr. neto. Otros instrumentos de
56 861 patrimonio [526]
17 N Entidades aseguradoras. Patrimonio propio - Conversión de pasivos financ. en patr. neto. Ajustes por cambios de
57 878 valor [527]
17 N Entidades aseguradoras. Patrimonio propio - Conversión de pasivos financ. en patr. neto. Subvenciones
58 895 donaciones y legados [528]
59 912 17 N Entidades aseguradoras. Patrimonio propio - Conversión de pasivos financ. en patr. neto. Total [529]
17 N Entidades aseguradoras. Patrimonio propio - (-) Distribución de dividendos o derramas activas. Resultado del
60 929 ejercicio [537]
17 N Entidades aseguradoras. Patrimonio propio - (-) Distribución de dividendos o derramas activas. (Dividendo a
61 946 cuenta) [538]
17 N Entidades aseguradoras. Patrimonio propio - (-) Distribución de dividendos o derramas activas. Otros instrumentos
62 963 de patrimonio [539]
17 N Entidades aseguradoras. Patrimonio propio - (-) Distribución de dividendos o derramas activas. Ajustes por
63 980 cambios de valor [540]
17 N Entidades aseguradoras. Patrimonio propio - (-) Distribución de dividendos o derramas activas. Subvenciones
64 997 donaciones y legados [541]
1177 NN EEnttiiddaddes aseguraddoras. PPattriimoniio propiio - ((-)) DDiisttriibbuciióón dde ddiiviiddenddos o dderramas acttiivas. TTottall [[554422]]
65 1014
17 N Entidades aseguradoras. Patrimonio propio - Operaciones con acciones o participaciones propias (netas).
66 1031 Resultado del ejercicio [550]
17 N Entidades aseguradoras. Patrimonio propio - Operaciones con acciones o participaciones propias (netas).
67 1048 (Dividendo a cuenta) [551]
17 N Entidades aseguradoras. Patrimonio propio - Operaciones con acciones o participaciones propias (netas). Otros
68 1065 instrumentos de patrimonio [552]
17 N Entidades aseguradoras. Patrimonio propio - Operaciones con acciones o participaciones propias (netas). Ajustes
69 1082 por cambios de valor [553]
17 N Entidades aseguradoras. Patrimonio propio - Operaciones con acciones o participaciones propias (netas).
70 1099 Subvenciones donaciones y legados [554]
17 N Entidades aseguradoras. Patrimonio propio - Operaciones con acciones o participaciones propias (netas). Total
7711 11111166 [[555555]]
17 N Entidades aseguradoras. Patrimonio propio - Incremento (reducción) de patr. neto resultante de una combinación
72 1133 de negocios. Resultado del ejercicio [563]
17 N Entidades aseguradoras. Patrimonio propio - Incremento (reducción) de patr. neto resultante de una combinación
73 1150 de negocios. (Dividendo a cuenta) [564]
17 N Entidades aseguradoras. Patrimonio propio - Incremento (reducción) de patr. neto resultante de una combinación
74 1167 de negocios. Otros instrumentos de patrimonio [565]
17 N Entidades aseguradoras. Patrimonio propio - Incremento (reducción) de patr. neto resultante de una combinación
75 1184 de negocios. Ajustes por cambios de valor [566]
17 N Entidades aseguradoras. Patrimonio propio - Incremento (reducción) de patr. neto resultante de una combinación
76 1201 de negocios. Subvenciones donaciones y legados [567]
17 N Entidades aseguradoras. Patrimonio propio - Incremento (reducción) de patr. neto resultante de una combinación
77 1218 de negocios. Total [568]
1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass. PPaattrriimmoonniioo pprrooppiioo -- OOttrraass ooppeerraacciioonneess ccoonn ssoocciiooss oo mmuuttuuaalliissttaass. RReessuullttaaddoo ddeell eejjeerrcciicciioo
78 1235 [576]
17 N Entidades aseguradoras. Patrimonio propio - Otras operaciones con socios o mutualistas. (Dividendo a cuenta)
79 1252 [577]
17 N Entidades aseguradoras. Patrimonio propio - Otras operaciones con socios o mutualistas. Otros instrumentos de
80 1269 patrimonio [578]
17 N Entidades aseguradoras. Patrimonio propio - Otras operaciones con socios o mutualistas. Ajustes por cambios de
81 1286 valor [579]
17 N Entidades aseguradoras. Patrimonio propio - Otras operaciones con socios o mutualistas. Subvenciones
82 1303 donaciones y legados [580]
83 1320 17 N Entidades aseguradoras. Patrimonio propio - Otras operaciones con socios o mutualistas. Total [581]
17 N Entidades aseguradoras. Patrimonio propio - Otras variaciones del patrimonio neto. Resultado del ejercicio [589]
84 1337
1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass. PPaattrriimmoonniioo pprrooppiioo -- OOttrraass vvaarriiaacciioonneess ddeell ppaattrriimmoonniioo nneettoo. ((DDiivviiddeennddoo aa ccuueennttaa)) [[559900]]
85 1354
17 N Entidades aseguradoras. Patrimonio propio - Otras variaciones del patrimonio neto. Otros instrumentos de
86 1371 patrimonio [591]
17 N Entidades aseguradoras. Patrimonio propio - Otras variaciones del patrimonio neto. Ajustes por cambios de valor
87 1388 [592]
17 N Entidades aseguradoras. Patrimonio propio - Otras variaciones del patrimonio neto. Subvenciones donaciones y
88 1405 legados [593]
89 1422 17 N Entidades aseguradoras. Patrimonio propio - Otras variaciones del patrimonio neto. Total [594]
17 N Entidades aseguradoras. Patrimonio propio - Pagos basados en instrumentos de patrimonio. Resultado del
90 1439 ejercicio [602]
17 N Entidades aseguradoras. Patrimonio propio - Pagos basados en instrumentos de patrimonio. (Dividendo a cuenta)
91 1456 [603]
1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass.. PPaattrriimmoonniioo pprrooppiioo -- PPaaggooss bbaassaaddooss eenn iinnssttrruummeennttooss ddee ppaattrriimmoonniioo.. OOttrrooss iinnssttrruummeennttooss
92 1473 de patrimonio [604]
17 N Entidades aseguradoras. Patrimonio propio - Pagos basados en instrumentos de patrimonio. Ajustes por cambios
93 1490 de valor [605]
17 N Entidades aseguradoras. Patrimonio propio - Pagos basados en instrumentos de patrimonio. Subvenciones
94 1507 donaciones y legados [606]
17 N Entidades aseguradoras. Patrimonio propio - Pagos basados en instrumentos de patrimonio. Total [607]
95 1524
17 N Entidades aseguradoras. Patrimonio propio - Traspasos entre partidas de patrimonio neto. Resultado del ejercicio
96 1541 [615]
17 N Entidades aseguradoras. Patrimonio propio - Traspasos entre partidas de patrimonio neto. (Dividendo a cuenta)
97 1558 [616]
17 N Entidades aseguradoras. Patrimonio propio - Traspasos entre partidas de patrimonio neto. Otros instrumentos de
9988 155755 ppatrimonio [[617]]
17 N Entidades aseguradoras. Patrimonio propio - Traspasos entre partidas de patrimonio neto. Ajustes por cambios de
99 1592 valor [618]
17 N Entidades aseguradoras. Patrimonio propio - Traspasos entre partidas de patrimonio neto. Subvenciones
100 1609 donaciones y legados [619]
Página 66

# Pag. 67

101 1626 17 N Entidades aseguradoras. Patrimonio propio - Traspasos entre partidas de patrimonio neto. Total [620]
102 1643 17 N Entidades aseguradoras. Patrimonio propio - Otras variaciones. Resultado del ejercicio [628]
103 1660 17 N Entidades aseguradoras. Patrimonio propio - Otras variaciones. (Dividendo a cuenta) [629]
104 1677 17 N Entidades aseguradoras. Patrimonio propio - Otras variaciones. Otros instrumentos de patrimonio [630]
105 1694 17 N Entidades aseguradoras. Patrimonio propio - Otras variaciones. Ajustes por cambios de valor [631]
17 N Entidades aseguradoras. Patrimonio propio - Otras variaciones. Subvenciones donaciones y legados [632]
106 1711
107 1728 17 N Entidades aseguradoras. Patrimonio propio - Otras variaciones. Total [633]
108 1745 17 N Entidades aseguradoras. Patrimonio propio - Saldo final ejercicio. Resultado del ejercicio [641]
109 1762 17 N Entidades aseguradoras. Patrimonio propio - Saldo final ejercicio. (Dividendo a cuenta) [642]
17 N Entidades aseguradoras. Patrimonio propio - Saldo final ejercicio. Otros instrumentos de patrimonio [643]
110 1779
111111 11779966 1177 NN EEnnttiiddaaddeess aasseegguurraaddoorraass.. PPaattrriimmoonniioo pprrooppiioo -- SSaallddoo ffiinnaall eejjeerrcciicciioo.. AAjjuusstteess ppoorr ccaammbbiiooss ddee vvaalloorr [[664444]]
17 N Entidades aseguradoras. Patrimonio propio - Saldo final ejercicio. Subvenciones donaciones y legados [645]
112 1813
113 1830 17 N Entidades aseguradoras. Patrimonio propio - Saldo final ejercicio. Total [646]
114 1847 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200041>"
Total: 1856
Página 67

# Pag. 68

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "042"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN IInnsstt. iinnvveerrssiióónn ccoolleeccttiivvaa.BBaallaannccee - AAccttiivvoo. AAccttiivvoo nnoo ccoorrrriieennttee ((FF,II)) [[110011]]
7 28 17 N Inst. inversión colectiva.Balance - Activo. Inmovilizado intangible (F,I) [102]
8 45 17 N Inst. inversión colectiva.Balance - Activo. Inmovilizado material (F,I) [103]
9 62 17 N Inst. inversión colectiva.Balance - Activo. Bienes muebles de uso propio (F,I) [104]
10 79 17 N Inst. inversión colectiva.Balance - Activo. Mobiliario y enseres (F,I) [105]
11 96 17 N Inst. inversión colectiva.Balance - Activo. Cartera de inversiones inmobiliarias (I) [106]
12 113 17 N Inst. inversión colectiva.Balance - Activo. Cartera interior de inmuebles y derechos (I) [107]
13 130 17 N Inst. inversión colectiva.Balance - Activo. Inmuebles en fase de construcción (I) [108]
14 147 17 N Inst. inversión colectiva.Balance - Activo. Inmuebles terminados (I) [109]
15 164 17 N Inst. inversión colectiva.Balance - Activo. Concesiones administrativas (I) [110]
16 181 17 N Inst. inversión colectiva.Balance - Activo. Otros derechos reales (I) [111]
17 198 17 N Inst. inversión colectiva.Balance - Activo. Compromisos de compra de inmuebles (I) [112]
1188 221155 1177 NN IInnsstt.. iinnvveerrssiióónn ccoolleeccttiivvaa..BBaallaannccee -- AAccttiivvoo.. CCoommpprraa ddee ooppcciioonneess ddee ccoommpprraa ddee iinnmmuueebblleess ((II)) [[111133]]
17 N Inst. inversión colectiva.Balance - Activo. Acciones en sociedades tenedoras y entidades de arrendamiento (I)
19 232 [114]
20 249 17 N Inst. inversión colectiva.Balance - Activo. Opciones sobre la cartera de inversiones inmobiliarias (I) [115]
21 266 17 N Inst. inversión colectiva.Balance - Activo. Otros (I) [116]
22 283 17 N Inst. inversión colectiva.Balance - Activo. Cartera exterior de inmuebles y derechos (I) [117]
23 300 17 N Inst. inversión colectiva.Balance - Activo. Sociedades tenedoras de inmuebles (I) [118]
24 317 17 N Inst. inversión colectiva.Balance - Activo. Otros (I) [119]
25 334 17 N Inst. inversión colectiva.Balance - Activo. Anticipos o entregas a cuenta (I) [120]
26 351 17 N Inst. inversión colectiva.Balance - Activo. Cuentas transitorias (I) [121]
17 N Inst. inversión colectiva.Balance - Activo. Inversiones adicionales, complementarias y rehabilitaciones en curso (I)
27 368 [122]
28 385 17 N Inst. inversión colectiva.Balance - Activo. Indemnizaciones a arrendatarios (I) [123]
2299 440022 1177 NN IInstt. iinversiióón collecttiiva.BBallance - AActtiivo. AActtiivos por iimpuestto ddiifferiiddo ((FF,II)) [[112244]]
30 419 17 N Inst. inversión colectiva.Balance - Activo. Activo corriente (F,I) [125]
31 436 17 N Inst. inversión colectiva.Balance - Activo. Deudores (F,I) [126]
32 453 17 N Inst. inversión colectiva.Balance - Activo. Deudores por ventas de inmuebles (I) [127]
33 470 17 N Inst. inversión colectiva.Balance - Activo. Deudores por alquileres (I) [128]
34 487 17 N Inst. inversión colectiva.Balance - Activo. Deudores dudosos o morosos (I) [129]
17 N Inst. inversión colectiva.Balance - Activo. Deudores dudosos o morosos avalados o garantizados (I) [130]
35 504
36 521 17 N Inst. inversión colectiva.Balance - Activo. Otros deudores (I) [131]
37 538 17 N Inst. inversión colectiva.Balance - Activo. Cartera de inversiones financieras (F,I) [132]
38 555 17 N Inst. inversión colectiva.Balance - Activo. Cartera interior (F,I) [133]
39 572 17 N Inst. inversión colectiva.Balance - Activo. Valores representativos de deuda (F) [134]
4400 558899 1177 NN IInnsstt.. iinnvveerrssiióónn ccoolleeccttiivvaa..BBaallaannccee - AAccttiivvoo.. IInnssttrruummeennttooss ddee ppaattrriimmoonniioo ((FF)) [[113355]]
41 606 17 N Inst. inversión colectiva.Balance - Activo. Instituciones de inversión colectiva (F) [136]
42 623 17 N Inst. inversión colectiva.Balance - Activo. Depósitos en EECC (F) [137]
43 640 17 N Inst. inversión colectiva.Balance - Activo. Derivados (F) [138]
44 657 17 N Inst. inversión colectiva.Balance - Activo. Otros (F) [139]
45 674 17 N Inst. inversión colectiva.Balance - Activo. Cartera exterior (F,I) [140]
46 691 17 N Inst. inversión colectiva.Balance - Activo. Valores representativos de deuda (F) [141]
47 708 17 N Inst. inversión colectiva.Balance - Activo. Instrumentos de patrimonio (F) [142]
48 725 17 N Inst. inversión colectiva.Balance - Activo. Instituciones de inversión colectiva (F) [143]
49 742 17 N Inst. inversión colectiva.Balance - Activo. Depósitos en EECC (F) [144]
50 759 17 N Inst. inversión colectiva.Balance - Activo. Derivados (F) [145]
51 776 17 N Inst. inversión colectiva.Balance - Activo. Otros (F) [146]
52 793 17 N Inst. inversión colectiva.Balance - Activo. Intereses de la cartera de inversión (F,I) [147]
53 810 1177 NN IInstt. iinversiióón collecttiiva.BBallance - AActtiivo. IInversiiones morosas, dduddosas o en lliittiigiio ((FF,II)) [[114488]]
54 827 17 N Inst. inversión colectiva.Balance - Activo. Periodificaciones (F,I) [149]
55 844 17 N Inst. inversión colectiva.Balance - Activo. Tesorería (F,I) [150]
56 861 17 N Inst. inversión colectiva.Balance - Activo. Total activo (F,I) [151]
57 878 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200042>"
Total: 887
Página 68

# Pag. 69

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "043"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN IInnssttiittuucciioonneess IInnvveerrssiióónn CCoolleeccttiivvaa - PPaattrriimmoonniioo yy ppaassiivvoo. PPaattrriimmoonniioo aattrriibbuuiiddoo aa ppaarrttíícciippeess oo aacccciioonniissttaass ((FF,II)) [[115522]]
17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Fondos reembonsables atribuidos a partícipes
7 28 o accionistas (F,I) [153]
8 45 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Capital (F,I) [154]
9 62 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Partícipes (F,I) [155]
10 79 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Prima de emisión (F,I) [156]
11 96 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Reservas (F,I) [157]
12 113 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. (Acciones propias) (F,I) [158]
13 130 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Resultado de ejercicios anteriores (F,I) [159]
14 147 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Otras aportaciones de socios (F,I) [160]
15 164 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Resultado del ejercicio (F,I) [161]
16 181 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. (Dividendo a cuenta) (F,I) [162]
1177 NN IInnssttiittuucciioonneess IInnvveerrssiióónn CCoolleeccttiivvaa - PPaattrriimmoonniioo yy ppaassiivvoo.. AAjjuusstteess ppoorr ccaammbbiiooss ddee vvaalloorr eenn iinnmmoovviilliizzaaddoo mmaatteerriiaall ddee
17 198 uso propio (F) [163]
17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Ajustes por cambios de valor en inversiones inmobiliarias e
18 215 inmovilizado material (I) [164]
17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Ajustes por plusvalías de las inversiones inmobiliarias e
19 232 inmovilizado material (I) [165]
17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Ajustes por minusvalías de las inversiones inmobiliarias e
20 249 inmovilizado material (I) [166]
21 266 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Otro patrimonio atribuido (F,I) [167]
22 283 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Pasivo no corriente (F,I) [168]
23 300 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Provisiones a largo plazo (F,I) [169]
24 317 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Deudas a largo plazo (F,I) [170]
25 334 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Pasivos por impuesto diferido (F,I) [171]
2266 335511 1177 NN IInnssttiittuucciioonneess IInnvveerrssiióónn CCoolleeccttiivvaa -- PPaattrriimmoonniioo yy ppaassiivvoo.. PPaassiivvoo ccoorrrriieennttee ((FF,,II)) [[117722]]
27 368 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Provisiones a corto plazo (F,I) [173]
28 385 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Deudas a corto plazo (F,I) [174]
29 402 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Acreedores (F,I) [175]
30 419 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Pasivos financieros (F) [176]
31 436 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Derivados (F) [177]
32 453 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Periodificaciones (F,I) [178]
33 470 17 N Instituciones Inversión Colectiva - Patrimonio y pasivo. Total Patrimonio y pasivo (F,I) [179]
34 487 17 N Instituciones Inversión Colectiva - Cuentas de orden. Cuentas de compromiso (F) [180]
17 N Instituciones Inversión Colectiva - Cuentas de orden. Compromisos por operaciones largas de derivados (F) [181]
35 504
17 N Instituciones Inversión Colectiva - Cuentas de orden. Compromisos por operaciones cortas de derivados (F) [182]
36 521
3377 553388 1177 NN IInsttiittuciiones IInversiióón CCollecttiiva - CCuenttas dde ordden. CCompromiisos por compra dde iinmuebblles ((II)) [[118833]]
38 555 17 N Instituciones Inversión Colectiva - Cuentas de orden. Compromisos de venta de inmuebles (I) [184]
39 572 17 N Instituciones Inversión Colectiva - Cuentas de orden. Contrato de arras (I) [185]
17 N Instituciones Inversión Colectiva - Cuentas de orden. Derechos de compra de opciones de compra de inmuebles
40 589 (I) [186]
17 N Instituciones Inversión Colectiva - Cuentas de orden. Importes pendientes de desembolsar por inmuebles en fase
41 606 de construcción (I) [187]
42 623 17 N Instituciones Inversión Colectiva - Cuentas de orden. Otras cuentas de riesgo y compromiso (I) [188]
43 640 17 N Instituciones Inversión Colectiva - Cuentas de orden. Total cuentas de riesgo y compromiso (I) [189]
44 657 17 N Instituciones Inversión Colectiva - Cuentas de orden. Otras cuentas de orden (F) [190]
45 674 17 N Instituciones Inversión Colectiva - Cuentas de orden. Valores cedidos en préstamo por la IIC (F) [191]
17 N Instituciones Inversión Colectiva - Cuentas de orden. Valores aportados como garantía por la IIC (F) [192]
46 691
47 708 17 N Instituciones Inversión Colectiva - Cuentas de orden. Valores recibidos en garantía por la IIC (F) [193]
17 N Instituciones Inversión Colectiva - Cuentas de orden. Capital nominal no suscrito ni en circulación (SICAV) (F)
48 725 [194]
49 742 17 N Instituciones Inversión Colectiva - Cuentas de orden. Capital nominal no suscrito (SII) (I) [195]
50 759 17 N Instituciones Inversión Colectiva - Cuentas de orden. Avales recibidos (I) [196]
51 776 17 N Instituciones Inversión Colectiva - Cuentas de orden. Avales emitidos (I) [197]
17 N Instituciones Inversión Colectiva - Cuentas de orden. Indemnizaciones previstas pendientes de confirmar (I) [198]
52 793
53 810 17 N Instituciones Inversión Colectiva - Cuentas de orden. Pérdidas fiscales a compensar (F)(I) [199]
54 827 17 N Instituciones Inversión Colectiva - Cuentas de orden. Otros (F) [200]
55 844 17 N Instituciones Inversión Colectiva - Cuentas de orden. Otras cuentas de orden (I) [201]
56 861 17 N Instituciones Inversión Colectiva - Cuentas de orden. Total otras cuentas de orden (I) [202]
5577 887788 1177 NN IInnssttiittuucciioonneess IInnvveerrssiióónn CCoolleeccttiivvaa -- CCuueennttaass ddee oorrddeenn.. TToottaall ccuueennttaass ddee oorrddeenn ((FF)) [[220033]]
58 895 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200043>"
Total: 904
Página 69

# Pag. 70

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de rentas
vers. 1.0
constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "044"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Comisiones de descuento por suscripciones y /o reembolsos
66 1111 [[220044]]
7 28 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Comisiones retrocedidas [205]
8 45 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Ingresos por alquiler [206]
9 62 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Gastos de personal [207]
10 79 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Otros gastos de explotación [208]
11 96 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Comisión de gestión [209]
12 113 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Comisión depositario [210]
13 130 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Otros [212]
14 147 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Deterioro y resultados por enejanaciones [213]
15 164 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Deterioro de inversiones inmobiliarias [214]
16 181 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Incrementos de deterioro [215]
17 198 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Reversión del deterioro [216]
18 215 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Resultados por enajenaciones y otros [217]
1199 223322 1177 NN IInnssttiittuucciioonneess IInnvveerrssiióónn CCoolleeccttiivvaa -- CCuueennttaa ppéérrddiiddaass yy ggaannaanncciiaass. RReessuullttaaddooss ppoossiittiivvooss [[221188]]
20 249 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Resultados negativos [219]
21 266 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Compensaciones e indemnizaciones [220]
22 283 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Amortización inversiones inmobiliarias [221]
23 300 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Amortización inmovilizado material [222]
24 317 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Excesos de provisiones [223]
25 334 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Deterioro y resultados por enajenaciones [224]
26 351 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Resultado de explotación [225]
27 368 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Ingresos financieros [226]
28 385 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Gastos financieros [227]
29 402 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Variación del valor razonable [228]
30 419 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Por operaciones cartera interior [229]
31 436 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Por operaciones cartera exterior [230]
3322 445533 1177 NN IInnssttiittuucciioonneess IInnvveerrssiióónn CCoolleeccttiivvaa - CCuueennttaa ppéérrddiiddaass yy ggaannaanncciiaass.. PPoorr ooppeerraacciioonneess ccoonn ddeerriivvaaddooss [[223311]]
33 470 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Otros [232]
34 487 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Diferencias de cambio [233]
35 504 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Deterioro y resultado enajenaciones [234]
36 521 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Deterioros [235]
17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Resultados por operaciones cartera interior [236]
37 538
17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Resultados por operaciones cartera exterior [237]
38 555
39 572 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Resultados por operaciones con derivados [238]
40 589 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Otros [239]
41 606 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Resultado financiero [240]
42 623 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Resultado antes de impuesto [241]
43 640 17 N Instituciones Inversión Colectiva - Cuenta pérdidas y ganancias. Impuesto sobre beneficios [242]
4444 665577 1177 NN IInsttiittuciiones IInversiióón CCollecttiiva - CCuentta péérddiiddas y gananciias. RResullttaddo ddell ejjerciiciio [[550000]]
45 674 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200044>"
Total: 683
Página 70

# Pag. 71

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "045"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN IInnssttiittuucciioonneess IInnvveerrssiióónn CCoolleeccttiivvaa - EEssttaaddoo vvaarriiaacciióónn ppaattrriimmoonniiaall. PPaattrriimmoonniioo iinniicciiaall [[224444]]
7 28 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Saldo neto [245]
17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Suscripciones/puesta circ.Acciones [246]
8 45
9 62 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Suscripciones/Aumentos capital [247]
10 79 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Reembolsos/Recompra acciones [248]
11 96 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Reembolsos/Reducciones capital [249]
12 113 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Beneficios brutos distribuidos [250]
13 130 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Rendimientos netos [251]
14 147 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Rendimientos de gestión [252]
15 164 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Alquileres [253]
16 181 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Intereses [254]
1177 119988 1177 NN IInnssttiittuucciioonneess IInnvveerrssiióónn CCoolleeccttiivvaa - EEssttaaddoo vvaarriiaacciióónn ppaattrriimmoonniiaall.. DDiivviiddeennddooss [[225555]]
18 215 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Inversiones inmobiliarias [256]
17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Variación valor razonable inversiones inmob. [257]
19 232
17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Resultados enajenaciones inversiones inmob.
20 249 [258]
17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Resultados contratos inversiones
21 266 inmob.rescindidos [259]
17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Otros derivados de la inversiones inmob. [260]
22 283
23 300 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Valores representativos de deuda [261]
24 317 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Instrumentos de patrimonio [262]
25 334 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Depósitos [263]
2266 335511 1177 NN IInnssttiittuucciioonneess IInnvveerrssiióónn CCoolleeccttiivvaa -- EEssttaaddoo vvaarriiaacciióónn ppaattrriimmoonniiaall.. IInnssttiittuucciioonneess iinnvveerrssiióónn ccoolleeccttiivvaa [[226644]]
27 368 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Derivados [265]
28 385 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Otros valores [266]
29 402 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Diferencias de cambio [267]
30 419 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Otros rendimientos [268]
31 436 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Gastos repercutidos [269]
32 453 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Gastos gestión corriente [270]
17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Comisión gestión sobre patrimonio [271]
33 470
17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Comisión gestión sobre resultados [272]
34 487
35 504 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Comisión de depósito [273]
36 521 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Otros gastos gestión corriente [274]
3377 553388 1177 NN IInsttiittuciiones IInversiióón CCollecttiiva - EEsttaddo variiaciióón pattriimoniiall. TTasas por regiisttros offiiciialles [[227755]]
38 555 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Admisión a cotización [276]
39 572 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Difusión de valores liquidativos [277]
40 589 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Otros gastos gestión corriente [278]
41 606 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Servicios exteriores [279]
42 623 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Tasaciones [280]
43 640 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Admón.fincas y gastos comunidad [281]
17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Reparación conservación inmuebles [282]
44 657
45 674 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Auditoría [283]
46 691 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Servicios bancarios y similares [284]
17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Publicidad, propaganda y relaciones públicas [285]
47 70088
48 725 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Otros servicios [286]
49 742 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Amortización mobiliario y enseres [287]
17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Deterioros, excepto inversiones inmob. [288]
50 759
51 776 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Deterioros [289]
52 793 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Retenciones no recuperadas [290]
53 810 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Impuesto sobre beneficios [291]
54 827 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Gasto por compartimento [292]
55 844 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Otros [293]
56 861 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200045>"
Total: 870
Página 71

# Pag. 72

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "046"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN IInnssttiittuucciioonneess IInnvveerrssiióónn CCoolleeccttiivvaa - EEssttaaddoo vvaarriiaacciióónn ppaattrriimmoonniiaall. IInnggrreessooss [[229944]]
7 28 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Comisiones de descuento [295]
8 45 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Comisiones retrocedidas [296]
9 62 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. De intermediarios financieros [297]
10 79 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Por inversiones en otras IIC [298]
11 96 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Otras [299]
12 113 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Ingreso compartimento por IB [300]
13 130 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Otros [301]
17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Revalorización inmuebles uso propio y resultados
14 147 por enajenación inmobilizado [302]
15 164 17 N Instituciones Inversión Colectiva - Estado variación patrimonial. Patrimonio final [303]
16 181 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200046>"
TToottaall:: 119900
Página 72

# Pag. 73

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "047"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN SSoocciieeddaaddeess ddee ggaarraannttííaa rreeccíípprrooccaa. BBaallaannccee ((II)) - AAccttiivvoo - TTeessoorreerrííaa [[110011]]
17 N Sociedades de garantía recíproca. Balance (I) - Activo - Deudores comerciales y otras cuentas a cobrar [102]
7 28
8 45 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Socios dudosos [103]
9 62 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Deudores varios [104]
17 N Sociedades de garantía recíproca. Balance (I) - Activo - Otros créditos con las Administraciones Públicas [105]
10 79
11 96 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Socios por desembolsos exigidos [106]
12 113 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Activos por impuesto corriente [107]
13 130 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Resto de cuentas a cobrar [108]
14 147 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Inversiones financieras [109]
15 164 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Instrumentos de patrimonio [110]
166 1881 17 N Sociedades de ggarantía recípproca. Balance ((I)) - Activo - Valores reppresentativos de deuda [[111]]
17 198 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Depósitos a plazo en entidades de crédito [112]
18 215 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Activos financieros híbridos [113]
19 232 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Derivados de cobertura [114]
20 249 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Resto de derivados [115]
17 N Sociedades de garantía recíproca. Balance (I) - Activo - Inversiones en empresas del grupo y asociadas [116]
21 266
17 N Sociedades de garantía recíproca. Balance (I) - Activo - Activos no corrientes mantenidos para la venta [117]
22 283
23 300 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Inmovilizado material [118]
24 317 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Terrenos y construcciones [119]
17 N Sociedades de garantía recíproca. Balance (I) - Activo - Instalaciones técnicas y otro inmovilizado material [120]
25 334
2266 335511 1177 NN SSoocciieeddaaddeess ddee ggaarraannttííaa rreeccíípprrooccaa.. BBaallaannccee ((II)) -- AAccttiivvoo -- IInnvveerrssiioonneess iinnmmoobbiilliiaarriiaass [[112211]]
27 368 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Inmovilizado intangible [122]
28 385 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Activos por impuesto diferido [123]
29 402 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Resto de activos [124]
30 419 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Periodificaciones [125]
31 436 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Otros activos [126]
32 453 17 N Sociedades de garantía recíproca. Balance (I) - Activo - Total activo [127]
17 N Sociedades de garantía recíproca. Balance (I) - Pasivo - Acreedores comerciales y otras cuenta a pagar [129]
33 470
34 487 17 N Sociedades de garantía recíproca. Balance (I) - Pasivo - Acreedores varios [130]
35 504 17 N Sociedades de garantía recíproca. Balance (I) - Pasivo - Pasivos por impuesto corriente [131]
36 521 17 N Sociedades de garantía recíproca. Balance (I) - Pasivo - Deudas [132]
37 538 17 N Sociedades de garantía recíproca. Balance (I) - Pasivo - obligaciones [133]
38 555 17 N Sociedades de garantía recíproca. Balance (I) - Pasivo - Deudas con entidades de crédito [134]
39 572 17 N Sociedades de garantía recíproca. Balance (I) - Pasivo - Finanzas y depósitos recibidos [135]
40 589 17 N Sociedades de garantía recíproca. Balance (I) - Pasivo - Sociedades de reafianzamiento [136]
41 606 17 N Sociedades de garantía recíproca. Balance (I) - Pasivo - Derivados de cobertura [137]
42 623 17 N Sociedades de garantía recíproca. Balance (I) - Pasivo - Resto de derivados [138]
43 640 17 N Sociedades de garantía recíproca. Balance (I) - Pasivo - Otras deudas [139]
Sociedades de garantía recíproca. Balance (I) - Pasivo - Pasivos vinculados con activos no corrientes mantenidos
44 657 17 N para la venta [140]
45 674 17 N Sociedades de garantía recíproca. Balance (I) - Pasivo - Pasivos por avales y garantías [141]
46 691 17 N Sociedades de garantía recíproca. Balance (I) - Pasivo - Garantías financieras [142]
47 708 17 N Sociedades de garantía recíproca. Balance (I) - Pasivo - Resto de avales y garantías [143]
48 725 17 N Sociedades de garantía recíproca. Balance (I) - Pasivo - Provisiones [144]
4499 774422 1177 NN SSoocciieeddaaddeess ddee ggaarraannttííaa rreeccíípprrooccaa.. BBaallaannccee ((II)) -- PPaassiivvoo -- PPrroovviissiioonneess ppoorr aavvaalleess yy ggaarraannttííaass [[114455]]
50 759 17 N Sociedades de garantía recíproca. Balance (I) - Pasivo - Otras provisiones [146]
51 776 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200047>"
Total: 785
Página 73

# Pag. 74

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "048"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
SSoocciieeddaaddeess ddee ggaarraannttííaa rreeccíípprrooccaa. BBaallaannccee ((IIII)) - PPaassiivvoo ((ccoonntt.)) - FFoonnddoo ddee pprroovviissiioonneess ttééccnniiccaass. CCoobbeerrttuurraa
6 11 17 N conjunto operaciones [147]
7 28 17 N Sociedades de garantía recíproca. Balance (II) - Pasivo (cont.) - Pasivos por impuesto diferido [148]
8 45 17 N Sociedades de garantía recíproca. Balance (II) - Pasivo (cont.) - Resto de pasivos [149]
9 62 17 N Sociedades de garantía recíproca. Balance (II) - Pasivo (cont.) - Capital reembolsable a la vista [150]
10 79 17 N Sociedades de garantía recíproca. Balance (II) - Pasivo (cont.) - Total pasivo [128]
11 96 17 N Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - Fondos propios [151]
12 113 17 N Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - Capital [152]
13 130 17 N Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - Capital suscrito [153]
14 147 17 N Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - Socios protectores [154]
15 164 17 N Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - Socios partícipes [155]
16 181 17 N Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - Menos: capital no exigido [156]
1177 NN SSoocciieeddaaddeess ddee ggaarraannttííaa rreeccíípprrooccaa.. BBaallaannccee ((IIII)) - PPaattrriimmoonniioo nneettoo - MMeennooss:: ccaappiittaall rreeeemmbboollssaabbllee aa llaa vviissttaa [[115577]]
17 198
18 215 17 N Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - Reservas [158]
17 N Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - Resultados de ejercicios anteriores [159]
19 232
20 249 17 N Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - Resultado del ejercicio [160]
21 266 17 N Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - Ajustes por cambio de valor [161]
22 283 17 N Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - Activos financieros disponibles para la venta
23 300 17 N Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - Otros [163]
Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - Fondo de provisiones técnicas. Aportaciones de
24 317 17 N terceros [164]
25 334 17 N Sociedades de garantía recíproca. Balance (II) - Patrimonio neto - Total pasivo y patrimonio neto [165]
26 351 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200048>"
TToottaall:: 336600
Página 74

# Pag. 75

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "049"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
66 1111 1177 NN SSoocciieeddaaddeess ddee ggaarraannttííaa rreeccíípprrooccaa - CCueennttaa ppéérrddiiddaass y ggaannaanncciiaass - IImmppoorrttee nneettoo cciiffrraa ddee nneeggoocciiooss [[116666]]
17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Ingresos por avales y garantías [167]
7 28
17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Ingresos por prestación de servicios [168]
8 45
9 62 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Otros ingresos de explotación [169]
10 79 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Gastos de personal [170]
11 96 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Sueldos, salarios y asimilados [171]
12 113 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Cargas sociales [172]
13 130 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Provisiones [173]
14 147 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Otros gastos de explotación [174]
17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Dotaciones a provisiones por avales y
15 164 garantías [175]
17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Correciones de valor por deterioro de socios
16 181 dudosos [176]
17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Dotaciones al fondo de provisiones técnicas
17 198 [177]
18 215 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Fondo de provisiones técnicas [178]
19 232 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Amortización del inmovilizado [179]
17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Deterioro y resultado por enajenaciones [180]
20 249
17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Deterioro y resultado activos no corrientes en
21 266 venta [181]
22 283 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Resultado de explotación [182]
23 300 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Ingresos financieros [183]
17 N Sociedades de ggarantía recípproca - Cuenta ppérdidas yy gganancias - De pparticippaciones en instrumentos de
24 317 patrimonio [184]
17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - De valores negociables y otros instrumentos
25 334 financieros [185]
26 351 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Gastos financieros [186]
27 368 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Variación de valor razonable [187]
28 385 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Diferencias de cambio [188]
17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Correcciones de valor por deterioro [189]
29 402
30 419 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Resultado por enajenación [190]
31 436 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Resultado financiero [191]
32 453 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Resultado antes de impuestos [192]
33 470 17 N Sociedades de garantía recíproca - Cuenta pérdidas y ganancias - Impuestos sobre beneficios [193]
3344 448877 1177 NN SSoocciieeddaaddeess ddee ggaarraannttííaa rreeccíípprrooccaa -- CCuueennttaa ppéérrddiiddaass yy ggaannaanncciiaass -- RReessuullttaaddoo ddeell eejjeerrcciicciioo [[550000]]
35 504 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200049>"
Total: 513
Página 75

# Pag. 76

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "050"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
Sociedades de garantía recíproca. Estado ingresos y gastos reconocidos - Resultado de la cuenta de pérdidas y
6 11 17 N gananciias [[550000]]
Sociedades de garantía recíproca. Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio -
7 28 17 N Por ajustes por cambios de valor [195]
Sociedades de garantía recíproca. Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio -
8 45 17 N Activos fiananc. disponibles venta [196]
Sociedades de garantía recíproca. Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio -
9 62 17 N Otros [197]
Sociedades de garantía recíproca. Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio -
10 79 17 N Fondo provisiones técnicas. Aportaciones terceros [198]
Sociedades de garantía recíproca. Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio -
11 96 17 N Efecto impositivo [199]
Sociedades de garantía recíproca. Estado ingresos y gastos reconocidos - Ingr. y gastos imput. direct. patrimonio -
12 113 17 N Total ingresos gastos imputados direct. patrimonio neto [200]
Sociedades de ggarantía recípproca. Estado inggresos yy ggastos reconocidos - Transf. cuenta ppérdidas yy gganancias - Por
13 130 17 N ajustes por cambio de valor [201]
Sociedades de garantía recíproca. Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias -
14 147 17 N Activos financieros disponibles para venta [202]
Sociedades de garantía recíproca. Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias -
15 164 17 N Otros [203]
Sociedades de garantía recíproca. Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias -
16 181 17 N Fondo provisiones técnicas. Aportaciones terceros [204]
Sociedades de garantía recíproca. Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias -
17 198 17 N Efecto impositivo [205]
Sociedades de garantía recíproca. Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias -
18 215 17 N Total transf.cuenta pérdidas y ganacias [206]
Sociedades de garantía recíproca. Estado ingresos y gastos reconocidos - Transf. cuenta pérdidas y ganancias -
19 232 17 N Total ingresos y gastos reconocidos [207]
20 249 10 An Identificador de fin de reggistro OBLIGATORIO Constante "</T200050>"
Total: 258
Página 76

# Pag. 77

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "051"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final ejer.ant. Capital. Suscrito [208]
6 11
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final ejer.ant. Capital. Menos:no
7 28 exigido [209]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final ejer.ant. Capital.
8 45 Menos:reembolsable [210]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final ejer.ant. Reservas [211]
9 62
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final ejer.ant. Resultados ejer.ant.
10 79 [212]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Ajustes por cambio. Capital. Suscrito [217]
11 96
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Ajustes por cambio. Capital. Menos:no
12 113 exigido [218]
17 N Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto. Ajjustes ppor cambio. Cappital.
13 130 Menos:reembolsable [219]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Ajustes por cambio. Reservas [220]
14 147
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Ajustes por cambio. Resultados ejer.ant.
15 164 [221]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Ajustes por errores. Capital. Suscrito [226]
16 181
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Ajustes por errores. Capital. Menos:no
17 198 exigido [227]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Ajustes por errores. Capital.
18 215 Menos:reembolsable [228]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Ajustes por errores. Reservas [229]
19 232
17 N Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto. Ajjustes ppor errores. Resultados ejjer.ant.
20 249 [230]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo ajustado. Capital. Suscrito [235]
21 266
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo ajustado. Capital. Menos:no exigido
22 283 [236]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo ajustado. Capital.
23 300 Menos:reembolsable [237]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo ajustado. Reservas [238]
24 317
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo ajustado. Resultados ejer.ant. [239]
25 334
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Total ingresos/gastos. Capital. Suscrito
26 351 [244]
17 N Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto. Total inggresos/ggastos. Cappital. Menos:no
27 368 exigido [245]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Total ingresos/gastos. Capital.
28 385 Menos:reembolsable [246]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Total ingresos/gastos. Reservas [247]
29 402
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Total ingresos/gastos. Resultados ejer.ant.
30 419 [248]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Operaciones con socios. Capital. Suscrito
31 436 [253]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Operaciones con socios. Capital.
32 453 Menos:no exigido [254]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Operaciones con socios. Capital.
33 470 Menos:reembolsable [255]
17 N Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto. Opperaciones con socios. Reservas [[256]]
34 487
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Operaciones con socios. Resultados
35 504 ejer.ant. [257]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Aumentos de capital. Capital. Suscrito
36 521 [262]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Aumentos de capital. Capital. Menos:no
37 538 exigido [263]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Aumentos de capital. Capital.
38 555 Menos:reembolsable [264]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Aumentos de capital. Reservas [265]
39 572
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Aumentos de capital. Resultados ejer.ant.
40 589 [266]
17 N Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto. Reducciones de cappital. Cappital. Suscrito
41 606 [271]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Reducciones de capital. Capital. Menos:no
42 623 exigido [272]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Reducciones de capital. Capital.
43 640 Menos:reembolsable [273]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Reducciones de capital. Reservas [274]
44 657
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Reducciones de capital. Resultados
45 674 ejer.ant. [275]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Distribución de dividendos. Capital.
46 691 Suscrito [280]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Distribución de dividendos. Capital.
47 708 Menos:no exigido [281]
17 N Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto. Distribución de dividendos. Cappital.
48 725 Menos:reembolsable [282]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Distribución de dividendos. Reservas [283]
49 742
Página 77

# Pag. 78

17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Distribución de dividendos. Resultados
50 759 ejer.ant. [284]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras operaciones con socios. Capital.
51 776 Suscrito [289]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras operaciones con socios. Capital.
52 793 Menos:no exigido [290]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras operaciones con socios. Capital.
53 810 Menos:reembolsable [291]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras operaciones con socios. Reservas
54 827 [292]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras operaciones con socios. Resultados
55 844 ejer.ant. [293]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras variaciones patrimonio. Capital.
56 861 Suscrito [[298]]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras variaciones patrimonio. Capital.
57 878 Menos:no exigido [299]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras variaciones patrimonio. Capital.
58 895 Menos:reembolsable [300]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras variaciones patrimonio. Reservas
59 912 [301]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras variaciones patrimonio. Resultados
60 929 ejer.ant. [302]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final. Capital. Suscrito [307]
61 946
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final. Capital. Menos:no exigido
62 963 [308]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final. Capital. Menos:reembolsable
63 980 [[309]]
64 997 17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final. Reservas [310]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final. Resultados ejer.ant. [311]
65 1014
66 1031 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200051>"
Total: 1040
Página 78

# Pag. 79

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "052"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final ejer.ant. Resultado ejercicio
6 11 [[221133]]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final ejer.ant. Ajustes cambio valor
7 28 [214]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final ejer.ant. Fondos/aportaciones
8 45 [215]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final ejer.ant. Total [216]
9 62
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Ajustes por cambio. Resultado ejercicio
10 79 [222]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Ajustes por cambio. Ajustes cambio valor
11 96 [223]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Ajustes por cambio. Fondos/aportaciones
12 113 [224]
17 N Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto. Ajjustes ppor cambio. Total [[225]]
13 130
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Ajustes por errores. Resultado ejercicio
14 147 [231]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Ajustes por errores. Ajustes cambio valor
15 164 [232]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Ajustes por errores. Fondos/aportaciones
16 181 [233]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Ajustes por errores. Total [234]
17 198
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo ajustado. Resultado ejercicio [240]
18 215
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo ajustado. Ajustes cambio valor [241]
19 232
17 N Sociedades de ggarantia recípproca - Estado total cambios ppatrimonio neto. Saldo ajjustado. Fondos/apportaciones [[242]]
20 249
21 266 17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo ajustado. Total [243]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Total ingresos/gastos. Resultado ejercicio
22 283 [249]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Total ingresos/gastos. Ajustes cambio
23 300 valor [250]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Total ingresos/gastos.
24 317 Fondos/aportaciones [251]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Total ingresos/gastos. Total [252]
25 334
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Operaciones con socios. Resultado
26 351 ejercicio [258]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Operaciones con socios. Ajustes cambio
27 368 valor [[259]]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Operaciones con socios.
28 385 Fondos/aportaciones [260]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Operaciones con socios. Total [261]
29 402
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Aumentos de capital. Resultado ejercicio
30 419 [267]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Aumentos de capital. Ajustes cambio valor
31 436 [268]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Aumentos de capital. Fondos/aportaciones
32 453 [269]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Aumentos de capital. Total [270]
33 470
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Reducciones de capital. Resultado
34 487 ejjercicio [[276]]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Reducciones de capital. Ajustes cambio
35 504 valor [277]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Reducciones de capital.
36 521 Fondos/aportaciones [278]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Reducciones de capital. Total [279]
37 538
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Distribución de dividendos. Resultado
38 555 ejercicio [285]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Distribución de dividendos. Ajustes cambio
39 572 valor [286]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Distribución de dividendos.
40 589 Fondos/aportaciones [287]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Distribución de dividendos. Total [288]
4411 660066
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras operaciones con socios. Resultado
42 623 ejercicio [294]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras operaciones con socios. Ajustes
43 640 cambio valor [295]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras operaciones con socios.
44 657 Fondos/aportaciones [296]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras operaciones con socios. Total [297]
45 674
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras variaciones patrimonio. Resultado
46 691 ejercicio [303]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras variaciones patrimonio. Ajustes
47 708 cambio valor [304]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras variaciones patrimonio.
4488 772255 FFoonnddooss//aappoorrttaacciioonneess [[330055]]
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Otras variaciones patrimonio. Total [306]
49 742
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final. Resultado ejercicio [312]
50 759
Página 79

# Pag. 80

17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final. Ajustes cambio valor [313]
51 776
17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final. Fondos/aportaciones [314]
52 793
53 810 17 N Sociedades de garantia recíproca - Estado total cambios patrimonio neto. Saldo final. Total [315]
54 827 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200052>"
Total: 836
Página 80

# Pag. 81

Agencia Tributaria
Modelo 200 Diseño de registro
Impuesto sobre Sociedades e Impuesto sobre la Renta de no Residentes (establecimientos permanentes y entidades en régimen de atribución de
vers. 1.0
rentas constituidas en el extranjero con presencia en territorio español) 2010
Nº Posic. Lon Tipo Descripción Validación Contenido
1 1 2 An Inicio del identificador de modelo y página. OBLIGATORIO Constante "<T"
2 3 3 Num Modelo. OBLIGATORIO Constante "200"
3 6 3 An Página. OBLIGATORIO Constante "DID"
4 9 1 An Fin de identificador de modelo. OBLIGATORIO Constante ">"
5 10 1 An Indicador de página complementaria En blanco
6 11 1 An Cuenta corriente tributaria "0" o "1"
7 12 5 Num Código Administración.
8 17 4 Num Identificación - Ejercicio.
9 21 1 Num Tipo de ejercicio.
10 22 2 An Período Impositivo - "0A"
11 24 2 Num Período Impositivo inicio - Dia.
12 26 2 Num Período Impositivo inicio - Mes.
13 28 2 Num Período Impositivo inicio- El Año.
14 30 2 Num Período Impositivo fin -Día.
15 32 2 Num Período Impositivo fin -Mes.
16 34 2 Num Período Impositivo fin -Año.
17 36 9 An Identificación - NIF.
18 45 40 An Identificación - Apellidos y nombre o Razón Social.
19 85 17 N Liquidación - Base imponible [552] .
20 102 1177 NN LLiiquiiddaciióón - CCuotta íínttegra [[556622]].
21 119 17 N Liquidación - Líquido a ingresar o a devolver Estado [621]
22 136 17 Num RESERVADO AEAT
23 153 17 Num RESERVADO AEAT
24 170 17 Num RESERVADO AEAT
25 187 17 Num RESERVADO AEAT
26 204 1 An Devolución - Renuncia o por Transferencia "blanco" "R","D"
27 205 17 Num Devolución - Importe a devolver.
28 222 4 Num Devolución - Código cuenta cliente CCC - Entidad.
29 226 4 Num Devolución - Código cuenta cliente CCC - Oficina.
30 230 2 Num Devolución - Código cuenta cliente CCC - DC.
31 232 10 Num Devolución - Código cuenta cliente CCC - Número de cuenta.
1 An Modalidad de ingreso. Uno de los siguientes valores
""bbllaannccoo"", ""II"" AAddeeuuddoo eenn
cuenta, "H" Efectivo, "U"
32 242 Domiciliación
33 243 1 An RESERVADO AEAT
34 244 1 An RESERVADO AEAT
35 245 17 Num Ingreso - Importe a ingresar.
36 262 4 Num Ingreso - Código cuenta cliente CCC - Entidad.
37 266 4 Num Ingreso - Código cuenta cliente CCC - Oficina.
38 270 2 Num Ingreso - Código cuenta cliente CCC - DC.
39 272 10 Num Ingreso - Código cuenta cliente CCC - Número de cuenta.
40 282 1 An Cuota Cero. "0" o "1"
41 283 25 An Firma - Localidad.
42 308 2 Num Firma - Día.
4433 331100 1100 AAnn FFiirrmmaa -- MMeess..
44 320 4 Num Firma - Año.
45 324 10 An Identificador de fin de registro OBLIGATORIO Constante "</T200DID>"
Total: 333
Página 81