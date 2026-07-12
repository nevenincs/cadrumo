# Pag. 1

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132687
ANEXO II
DISEÑOS FÍSICOS Y LÓGICOS A LOS QUE DEBEN AJUSTARSE LOS ARCHIVOS QUE
SE GENEREN PARA LA PRESENTACIÓN TELEMÁTICA Y LOS SOPORTES
DIRECTAMENTE LEGIBLES POR ORDENADOR DEL MODELO 347.
DISEÑOS LÓGICOS
DESCRIPCIÓN DE LOS REGISTROS
Para cada declarante se incluirán dos tipos diferentes de registro, que se distinguen por la
primera posición, con arreglo a los siguientes criterios:
Tipo 1: Registro del declarante: Datos identificativos y resumen de la declaración. Diseño de
tipo de registro 1 de los recogidos más adelante en estos mismos apartados y
Anexo de la presente Orden.
Tipos 2: Registro de declarado y Registro de inmueble. Diseño de tipo de registro 2 de los
recogidos más adelante en estos mismos apartados y Anexo de la presente Orden.
El orden de presentación será el del tipo de registro, existiendo un único registro del tipo 1 y
tantos registros del tipo 2 como declarados e inmuebles tenga la declaración, siendo diferentes los de
declarados y los de inmuebles.
Todos los campos alfanuméricos y alfabéticos se presentarán alineados a la izquierda y
rellenos de blancos por la derecha, en mayúsculas sin caracteres especiales, y sin vocales acentuadas.
Para los caracteres específicos del idioma se utilizará la codificación ISO-8859-1. De esta
forma la letra “Ñ” tendrá el valor ASCII 209 (Hex. D1) y la “Ç” (cedilla mayúscula) el valor ASCII
199 (Hex. C7).
Todos los campos numéricos se presentarán alineados a la derecha y rellenos a ceros por la
izquierda sin signos y sin empaquetar.
Todos los campos tendrán contenido, a no ser que se especifique lo contrario en la descripción
del campo. Si no lo tuvieran, los campos numéricos se rellenarán a ceros y tanto los alfanuméricos
como los alfabéticos a blancos.
El primer registro del fichero (tipo 1), contendrá un campo de 13 caracteres, en las posiciones
488 a 500, reservado para el sello electrónico, que será cumplimentado exclusivamente por los
programas oficiales de la A.E.A.T. En cualquier otro caso se rellenará a blancos.
79391-1102-A-EOB
:evc

# Pag. 2

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132688
7
4
3
1
56
46
36
26
16
06
95
85
75
65
55
45
35
25
15
05
94
84
74
64
54
44
34
24
14
04
93
83
73
63
53
43
33
23
13
03
92
82
72
62
52
42
32
22
12
02
91
81
71
61
51
41
31
21
11
01
9
8
7
6
5
4
3
2
1
031921821721621521421321221121021911811711611511411311211111011901801701601501401301201101001
99
89
79
69
59
49
39
29
19
09
98
88
78
68
58
48
38
28
18
08
97
87
77
67
57
47
37
27
17
07
96
86
76
66
ED
LATOT
OREMUN
SEDADITNE
Y
SANOSREP
591491391291191091981881781681581481381281181081971871771671571471371271171071961861761661561461361261161061951851751651551451351251151051941841741641541441341241141041931831731631531431331231131 062952852752652552452352252152052942842742642542442342242142042932832732632532432332232132032922822722622522422322222122022912812712612512412312212112012902802702602502402302202102002991891791691
ONGIS
ANOSREP
ETNARALCED
LED
NÓICACIFITNEDI
ETNARALCED
LED
NÓICANIMONED
O
LAICOS
NOZAR
,ERBMON
Y
SODILLEPA
ONOFELET
ESRANOICALER
NEIUQ
NOC
AL
ED
OVITACIFITNEDI
OREMUN
NÓICARALCED
AVITUTITSUS.CED
AIRATNEMELPMOC.CED
OVITACIFITNEDI
OREMUN
NÓICARALCED
AL
ED
ROIRETNA
ERBMON
Y
SODILLEPA
ETROPOS ED OPIT
ORTSIGER ED OPIT
ETNARALCED
LED
.F.I.N
OICICREJE
OLEDOM
ETROPMI
ARETNE
LAMICED
SENOICAREPO
SAL
ED
LAUNA
LATOT
ETROPMI
ETROPMI
ED
LATOT
OREMÚN
SELBEUMNI
ARETNE
LAMICED
OTNEIMADNERRA
ED
SENOICAREPO
SAL
ED
LATOT
ETROPMI
OICOGEN
ED
SELACOL
ED
79391-1102-A-EOB
:evc

# Pag. 3

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132689
523423323223123023913813713613513413313213113013903803703603503403303203103003992892792692592492392292192092982882782682582482382282182082972872772672572472372272172072962862762662562462362262162 093983883783683583483383283183083973873773673573473373273173073963863763663563463363263163063953853753653553453353253153053943843743643543443343243143043933833733633533433333233133033923823723623
ETNATNESERPER
LED
.FIN
LAGEL
554454354254154054944844744644544444344244144044934834734634534434334234134034924824724624524424324224124024914814714614514414314214114014904804704604504404304204104004993893793693593493393293193
OCINÓRTCELE
OLLES
005994894794694594494394294194094984884784684584484384284184084974874774674574474374274174074964864764664564464364264164064954854754654
79391-1102-A-EOB
:evc

# Pag. 4

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132690
MODELO 347
A.- TIPO DE REGISTRO 1: REGISTRO DE DECLARANTE.
(POSICIONES, NATURALEZA Y DESCRIPCIÓN DE LOS CAMPOS)
POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS
1 Numérico TIPO DE REGISTRO.
Constante número '1'.
2-4 Numérico MODELO DECLARACIÓN.
Constante '347'.
5-8 Numérico EJERCICIO.
Las cuatro cifras del ejercicio fiscal al que corresponde la
declaración.
9-17 Alfanumérico NIF DEL DECLARANTE.
Se consignará el NIF del declarante.
Este campo deberá estar ajustado a la derecha, siendo la última
posición el carácter de control y rellenando con ceros las posiciones
de la izquierda, de acuerdo con las reglas previstas en el
Reglamento General de las actuaciones y los procedimientos de
gestión e inspección tributaria y de desarrollo de las normas
comunes de los procedimientos de aplicación de los tributos,
aprobado por el Real Decreto 1065/2007 de 27 de Julio (BOE del 5
de septiembre).
18-57 Alfanumérico APELLIDOS Y NOMBRE O RAZÓN SOCIAL DEL
DECLARANTE.
Si es una persona física se consignará el primer apellido, un espacio,
el segundo apellido, un espacio y el nombre completo,
necesariamente en este orden.
Para personas jurídicas y entidades sin personalidad jurídica, se
consignará la razón social completa o denominación, sin anagrama.
En ningún caso podrá figurar en este campo un nombre comercial.
58 Alfabético TIPO DE SOPORTE.
Se cumplimentará una de las siguientes claves:
'C': Si la información se presenta en soporte.
'T': Transmisión telemática
79391-1102-A-EOB
:evc

# Pag. 5

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132691
59-107 Alfanumérico PERSONA CON QUIÉN RELACIONARSE.
Datos de la persona con quién relacionarse. Este campo se
subdivide en dos:
59-67 TELÉFONO: Campo numérico de 9 posiciones.
68-107 APELLIDOS Y NOMBRE: Se consignará el
primer apellido, un espacio, el segundo apellido, un
espacio y el nombre completo, necesariamente en este
orden.
108- 120 Numérico NÚMERO IDENTIFICATIVO DE LA DECLARACIÓN.
Se consignará el número identificativo correspondiente a la
declaración. Campo de contenido numérico de 13 posiciones.
El número identificativo que habrá de figurar, será un número
secuencial cuyos tres primeros dígitos se corresponderán con el
código 347.
121- 122 Alfabético DECLARACIÓN COMPLEMENTARIA O
SUSTITUTIVA.
En el caso excepcional de segunda o posterior presentación de
declaraciones, deberá cumplimentarse obligatoriamente uno de los
siguientes campos:
121 DECLARACIÓN COMPLEMENTARIA: Se
consignará una “C” si la presentación de esta declaración
tiene por objeto incluir registros que, debiendo haber
figurado en otra declaración del mismo ejercicio
presentada anteriormente, hubieran sido completamente
omitidas en la misma.
La presentación de una declaración complementaria que
tenga por objeto la modificación del contenido de datos
declarados en otra declaración del mismo ejercicio
presentada anteriormente se realizará desde el servicio de
consulta y modificación de declaraciones informativas en
la Sede Electrónica de la Agencia Tributaria
(https://www.agenciatributaria.gob.es )
122 DECLARACIÓN SUSTITUTIVA: Se consignará
una “S” si la presentación tiene como objeto anular y
sustituir completamente a otra declaración anterior, del
mismo ejercicio. Una declaración sustitutiva sólo puede
anular a una única declaración anterior.
123- 135 Numérico NÚMERO IDENTIFICATIVO DE LA DECLARACIÓN
ANTERIOR.
En el caso de que se haya consignado una “C” en el campo
“Declaración complementaria” o en el caso de que se haya
consignado “S” en el campo “Declaración sustitutiva”, se
consignará el número identificativo correspondiente a la declaración
a la que complementa o sustituye.
79391-1102-A-EOB
:evc

# Pag. 6

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132692
Campo de contenido numérico de 13 posiciones.
En cualquier otro caso deberá rellenarse a CEROS.
136-144 Numérico NÚMERO TOTAL DE PERSONAS Y ENTIDADES.
Se consignará el número total de personas y entidades declaradas en
el registro de declarado (registro de detalle de tipo 2) por la entidad
declarante. Si un mismo declarado figura en varios registros, se
computará tantas veces como figure relacionado. (Número de
registros de tipo 2)
145-160 Alfanumérico IMPORTE TOTAL ANUAL DE LAS OPERACIONES.
Campo alfanumérico de 16 posiciones.
Se consignará la suma total de las cantidades reflejadas en el campo
‘IMPORTE TOTAL ANUAL DE LAS OPERACIONES’
(posiciones 84 a 98) correspondientes a los registros de declarados.
En el supuesto de que en estos registros de declarados se hubiera
consignado “N” en el campo “SIGNO IMPORTE TOTAL ANUAL
DE LAS OPERACIONES” (posición 83 del registro de tipo 2) las
cantidades se computarán con signo menos a efecto de esta suma.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
145 SIGNO: campo alfabético que se cumplimentará cuando
el resultado de la suma a que se acaba de hacer referencia sea menor
que 0 (cero); en este caso se consignará una “N”. En cualquier otro
caso el contenido del campo será un espacio.
146- 160 IMPORTE: Campo numérico de 15 posiciones. Se
consignará el importe resultante de la suma a que se ha hecho
referencia más arriba. Los importes deben consignarse en EUROS.
El importe no irá precedido de signo alguno (+/-), ni incluirá coma
decimal. Este campo se subdivide en dos:
146-158 Parte entera del importe total anual de las
operaciones, si no tiene contenido se consignará a ceros.
159-160 Parte decimal del importe total anual de las
operaciones, si no tiene contenido se consignará a ceros.
161-169 Numérico NÚMERO TOTAL DE INMUEBLES.
Se consignará el número total de inmuebles declarados en el
registro de inmueble (registro de detalle de tipo 2) por la entidad
declarante. Si un mismo inmueble figura en varios registros, se
computará tantas veces como figure relacionado. (Número de
registros de tipo 2)
170-184 Numérico IMPORTE TOTAL DE LAS OPERACIONES DE
ARRENDAMIENTO DE LOCALES DE NEGOCIO.
Campo numérico de 15 posiciones.
79391-1102-A-EOB
:evc

# Pag. 7

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132693
Se consignará sin signo y sin coma decimal la suma total de las
cantidades reflejadas en el campo ‘IMPORTE DE LA
OPERACION’ (posiciones 100 a 114) correspondientes a los
registros de inmuebles.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
170-182 Parte entera del importe total de las operaciones de
arrendamiento de locales de negocio, si no tiene contenido se
consignará a ceros.
183-184 Parte decimal del importe total de las operaciones de
arrendamiento de locales de negocio, si no tiene contenido se
consignará a ceros.
185-390 ------------ BLANCOS.
391-399 Alfanumérico NIF DEL REPRESENTANTE LEGAL.
Si el declarante es menor de 14 años se consignará en este campo el
número de identificación fiscal de su representante legal (padre,
madre o tutor). Este campo deberá estar ajustado a la derecha,
siendo la última posición el carácter de control y rellenando con
ceros las posiciones a la izquierda.
En cualquier otro caso el contenido de este campo se rellenará a
espacios.
400-487 ------------ BLANCOS
488-500 Alfanumérico SELLO ELECTRONICO.
Campo reservado para el sello electrónico en presentaciones
individuales, que será cumplimentado exclusivamente por los
programas de la AEAT En cualquier otro caso se rellenará a
blancos.
* Todos los importes serán positivos.
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a blancos.
* Todos los campos numéricos ajustados a la derecha y rellenos de ceros por la izquierda.
* Todos los campos alfanuméricos/alfabéticos ajustados a la izquierda y rellenos de blancos por
la derecha, en mayúsculas, sin caracteres especiales y sin vocales acentuadas, excepto que se
especifique lo contrario en la descripción del campo.
79391-1102-A-EOB
:evc

# Pag. 8

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132694
7
4
3
2
56
46
36 26 16 06 95 85 75 65 55
45
35
25 15
05
94
84
74
64
54
44
34
24
14
04
93
83
73
63
53
43
33 23
13 03 92 82 72 62 52
42
32
22
12
02
91
81
71
61
51
41
31
21
11
01
9
8
7
6
5
4
3
2
1
LAMICED
D
031921821721621521421321221121021911811711611511411311211111011901801701601501401301201101001
99
89 79
69 59 49 39 29 19 09
98
88
78
68
58
48
38
28
18
08
97
87
77
67
57
47
37
27
17
07
96
86
76
66
AICNIVORP
AJOH ED OPIT
OGIDOC
SIAP
AICNIVORP
ONGIS
ETROPMI ARETNE
ONGIS
ORUGES NÓICAREPO
LAMICED
ARETNE
LACOL .DNERRA
NÓICAREPO EVALC
OCILATEM
NE
ODIBICREP
ETROPMI
ARETNE
LAMICED
SIAP
SENOICAREPO
SAL ED LATOT
LAUNA
ETROPMI
ORTSIGER ED OPIT
ETNARALCED
NÓICACIFITNEDI
ODARALCED LED NÓICANIMONED
O LAICOS
NÓZAR
,ERBMON
Y SODILLEPA
LAGEL
ETNATNESERPER
.F.I.N
ODARALCED
.F.I.N
ETNARALCED
.F.I.N
OICICREJE
OLEDOM
ED
SENOISIMSNART
ROP ODIBICREP LAUNA
ETROPMI
AVI A SATEJUS SELBEUMNI ETROPMI
OICICREJE
SELBEUMN
E I R E T D S S E E M N IR O T IS O IM D S N N U A G R E T S R A O V P I A O S D A IB T I E C J R U E S P ETROPMI
ERTSEMIRT
ODNUGES
SENOICAREPO
SAL
ED
ETROPMI
SELBEUMNI
E E R D T S S E E M NO IR
IS T I R M E S M N I A R R P T A R V O I P A O SA D T IB E I J C U R S EP
ETROPMI
ERTSEMIRT
REMIRP
SENOICAREPO
SAL
ED
ETROPMI
LAMICED
591491391291191091981881781681581481381281181081971871771671571471371271171071961861761661561461361261161061951851751651551451351251151051941841741641541441341241141041931831731631531431331231131
ETROPMI
ETNE AR
062952852752652552452352252152052942842742642542442342242142042932832732632532432332232132032922822722622522422322222122022912812712612512412312212112012902802702602502402302202102002991891791691
OICICREJE
ERTSEMIRT
REMIRP
SENOICAREPO
SAL
ED
ETROPMI
ONGIS
ETROPMI
ARETNE
LAMICED
SELBEUMNI
ED SENOISIMSNART
ROP ODIBICREP
ETROPMI
ERTSEMIRT
REMIRP AVI A SATEJUS
ONGIS
ETROPMI ARETNE
LAMICED
ERTSEMIRT
ODNUGES
SENOICAREPO
SAL
ED
ETROPMI
ONGIS
ETROPMI
ARETNE
ONGIS
LAMICED
SELBEUMNI
ED SENOISIMSNART ROP ODIBICREP ETROPMI ERTSEMIRT ODNUGES AVI A SATEJUS ETROPMI ARETNE
ERTSEMIRT
RECRET
SENOICAREPO
SAL
ED
ETROPMI
ONGIS
ETROPMI
ARETNE
LAMICED
SELBUMNI
ED SENOISIMSNART
ROP ODIBICREP
ETROPMI
ERTSEMIRT
RECRET AVI A SATEJUS
ONGIS
ETROPMI ARETNE
LAMICED
SELBUMNI
E E R D T S S E E N M O IR IS T I M O S TR NA A R UC T R A O VI P A O S D A IB T I E C J R U E S P ETROPMI
ERTSEMIRT
OTRAUC
SENOICAREPO
SAL
ED
ETROPMI
ETROPMI ARETNE
ONGIS
ETROPMI
ARETNE
ONGIS
LAMICED
LAMICED 79391-1102-A-EOB
:evc

# Pag. 9

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132695
ARETNE
523423323223123023913813713613513413313213113013903803703603503403303203103003992892792692592492392292192092982882782682582482382282182082972872772672572472372272172072962862762662562462362262162 093983883783683583483383283183083973873773673573473373273173073963863763663563463363263163063953853753653553453353253153053943843743643543443343243143043933833733633533433333233133033923823723623 554454354254154054944844744644544444344244144044934834734634534434334234134034924824724624524424324224124024914814714614514414314214114014904804704604504404304204104004993893793693593493393293193
005994894794694594494394294194094984884784684584484384284184084974874774674574474374274174074964864764664564464364264164064954854754654
LAMICED
ETROPMI
79391-1102-A-EOB
:evc

# Pag. 10

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132696
MODELO 347
B.- TIPO DE REGISTRO 2: REGISTRO DE DECLARADO.
(POSICIONES, NATURALEZA Y DESCRIPCIÓN DE LOS CAMPOS)
POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS
1 Numérico TIPO DE REGISTRO.
Constante '2'.
2-4 Numérico MODELO DECLARACIÓN.
Constante '347'.
5-8 Numérico EJERCICIO.
Consignar lo contenido en estas mismas posiciones del registro de
tipo 1.
9-17 Alfanumérico NIF DEL DECLARANTE.
Consignar lo contenido en estas mismas posiciones del registro de
tipo 1.
18-26 Alfanumérico NIF DEL DECLARADO.
Si el declarado dispone de NIF asignado en España, se consignará:
Si es una persona física se consignará el NIF del declarado de
acuerdo con las reglas previstas en el Reglamento General de las
actuaciones y los procedimientos de gestión e inspección
tributaria y de desarrollo de las normas comunes de los
procedimientos de aplicación de los tributos, aprobado por el Real
Decreto 1065/2007, de 27 de julio, (BOE del 5 de septiembre).
Si el declarado es una persona jurídica o una entidad sin
personalidad jurídica (Comunidad de bienes, Sociedad civil,
herencia yacente, etc.), se consignará el número de identificación
fiscal correspondiente a la misma.
Para la identificación de los menores de 14 años en sus relaciones
de naturaleza o con trascendencia tributaria habrán de figurar
tanto los datos de la persona menor de 14 años, incluido su
número de identificación fiscal, como los de su representante
legal.
Este campo deberá estar ajustado a la derecha, siendo la última
posición el carácter de control y rellenando con ceros las posiciones
a la izquierda.
Sólo se cumplimentará con los NIF asignados en España.
79391-1102-A-EOB
:evc

# Pag. 11

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132697
27-35 Alfanumérico NIF DEL REPRESENTANTE LEGAL.
Si el declarado es menor de 14 años se consignará en este campo el
número de identificación fiscal de su representante legal (padre,
madre o tutor). Este campo deberá estar ajustado a la derecha,
siendo la última posición el carácter de control y rellenando con
ceros las posiciones a la izquierda.
En cualquier otro caso el contenido de este campo se rellenará a
espacios.
36-75 Alfanumérico APELLIDOS Y NOMBRE, RAZÓN SOCIAL O
DENOMINACIÓN DEL DECLARADO.
a) Para personas físicas se consignará el primer apellido, un
espacio, el segundo apellido, un espacio y el nombre completo,
necesariamente en este mismo orden. Si el declarado es menor
de 14 años, se consignarán en este campo los apellidos y
nombre del menor de edad.
b) Tratándose de personas jurídicas y entidades sin personalidad
jurídica, se consignará la razón social o la denominación
completa de la entidad, sin anagramas.
76 Alfabético TIPO DE HOJA.
Constante ‘D’.
77-80 Numérico CÓDIGO PROVINCIA/PAIS.
77-78 CÓDIGO PROVINCIA:
Campo numérico de dos posiciones.
En el caso de residentes o de no residentes que operen en territorio
español mediante establecimiento permanente, se consignará el
correspondiente al domicilio fiscal del declarado. Se consignarán
los dos dígitos que corresponden a la provincia o ciudad autónoma,
del domicilio del declarado, según la siguiente relación:
ARABA/ÁLAVA…. ..01 LEÓN ......................... 24
ALBACETE. ............. ..02 LLEIDA ..................... 25
ALICANTE/Alacant. ..03 LUGO ........................ 27
ALMERÍA ................ ..04 MADRID ................... 28
ASTURIAS ............... ..33 MÁLAGA .................. 29
ÁVILA ...................... ..05 MELILLA .................. 52
BADAJOZ ................ ..06 MURCIA ................... 30
BARCELONA .......... ..08 NAVARRA ............... 31
BURGOS .................. ..09 OURENSE ................. 32
CÁCERES ................. ..10 PALENCIA ............... 34
CÁDIZ ....................... ..11 PALMAS, LAS ......... 35
CANTABRIA.. ......... ..39 PONTEVEDRA ........ 36
CASTELLÓN/Castell.12 RIOJA, LA ................. 26
CEUTA ..................... ..51 SALAMANCA ......... 37
CIUDAD REAL ....... ..13 S.C.TENERIFE ......... 38
CÓRDOBA ............... ..14 SEGOVIA .................. 40
CORUÑA, A ............. ..15 SEVILLA ................... 41
CUENCA .................. 16 SORIA ......................... 42
GIRONA ................... 17 TARRAGONA ............ 43
GRANADA .............. 18 TERUEL ...................... 44
79391-1102-A-EOB
:evc

# Pag. 12

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132698
GUADALAJARA .... 19 TOLEDO ..................... 45
GIPÚZKOA .............. 20 VALENCIA/Valéncia . 46
HUELVA .................. 21 VALLADOLID ........... 47
HUESCA ................... 22 BIZKAIA ..................... 48
ILLES BALEARS .... 07 ZAMORA .................... 49
JAÉN ......................... 23 ZARAGOZA ............... 50
En el caso de no residentes sin establecimiento permanente se
consignará 99.
79-80 CÓDIGO PAÍS.
Campo alfabético de 2 posiciones.
En el caso de no residentes sin establecimiento
permanente se consignará XX, siendo XX el Código del
país de residencia del declarado, de acuerdo con los
códigos alfabéticos de países y territorios que figuran en
la Orden EHA/3202/2008, de 31 de octubre, en su
Anexo IV (BOE de 10/11/2008).
Adicionalmente se deben considerar los siguientes
códigos de país:
Curaçao CW
San Martín SX
Países Bajos, parte caribeña (Bonaire,
San Eustaquio y Saba) BQ
En cualquier otro caso se rellenará a blancos .
81 ------------ BLANCOS.
82 Alfabético CLAVE OPERACIÓN.
Se consignará la que corresponda según el siguiente detalle:
A Adquisiciones de bienes y servicios superiores a 3.005,06
euros.
B Entregas de bienes y prestaciones de servicios superiores a
3.005,06 euros.
C Cobros por cuenta de terceros superiores a 300,51 euros.
D Adquisiciones de bienes o servicios al margen de cualquier
actividad empresarial o profesional superiores a 3.005,06
euros, realizadas por Entidades Públicas, partidos políticos,
sindicatos o asociaciones empresariales.
E Subvenciones, auxilios y ayudas satisfechos por las
Administraciones Públicas superiores a 3.005,06 euros.
(Clave de uso exclusivo para Administraciones Públicas
que satisfagan dichas subvenciones, auxilios y ayudas,
nunca deben utilizar esta clave los declarados de las
mismas).
F Ventas agencia viaje: Servicios documentados mediante
facturas expedidas por agencias de viajes, al amparo de la
disposición adicional cuarta del Reglamento por el que se
regulan las obligaciones de facturación aprobado por el
artículo primero del Real Decreto 1496/2003.
79391-1102-A-EOB
:evc

# Pag. 13

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132699
G Compras agencia viaje: Prestaciones de servicios de
transportes de viajeros y de sus equipajes por vía aérea a
que se refiere la disposición adicional cuarta del
Reglamento por el que se regulan las obligaciones de
facturación aprobado por el artículo primero del Real
Decreto 1496/2003.
83-98 Alfanumérico IMPORTE ANUAL DE LAS OPERACIONES.
Este campo se subdivide en dos:
83 SIGNO: campo alfabético. Se consignará una “N” cuando
el importe anual de las operaciones sea menor que 0 (cero). En
cualquier otro caso el contenido de este campo será un espacio.
84-98 IMPORTE: campo numérico de 15 posiciones. Se
consignará sin signo y sin coma decimal el importe de las
operaciones correspondientes al año, con excepción de las
Entidades Aseguradoras que harán constar de forma separada las
operaciones de seguro del resto, así como los arrendadores y
arrendatarios de locales de negocio que consignarán separadamente
las operaciones de arrendamiento de locales de negocio declarables
del resto.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
84-96 Parte entera del importe anual de las operaciones, si no
tiene contenido se consignará a ceros.
97-98 Parte decimal del importe anual de las operaciones, si no
tiene contenido se consignará a ceros.
99 Alfabético OPERACIÓN SEGURO.
(Sólo Entidades Aseguradoras).
Las Entidades Aseguradoras pondrán una ‘X’ en este campo para
identificar las operaciones de seguros, debiendo consignarlas
separadamente del resto de operaciones.
100 Alfabético ARRENDAMIENTO LOCAL NEGOCIO.
(Sólo arrendadores y arrendatarios de Locales de Negocio).
Se pondrá en este campo una ‘X’ para operaciones de
arrendamiento de locales de negocio, debiendo consignarlas
separadamente del resto.
Además los arrendadores deberán cumplimentar los campos que
componen el REGISTRO DE INMUEBLE, consignando el Importe
Total de cada arrendamiento correspondiente al año natural al que
se refiere la declaración, con independencia de que éste ya haya
sido incluido en la clave ‘B’ (ventas).
101-115 Numérico IMPORTE PERCIBIDO EN METÁLICO.
Se consignará sin signo y sin coma decimal los importes superiores
a 6.000 euros que se hubieran percibido en metálico (moneda o
billetes de curso legal) de cada una de las personas o entidades
relacionadas en la declaración. Las Entidades Aseguradoras que
79391-1102-A-EOB
:evc

# Pag. 14

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132700
harán constar de forma separada las operaciones de seguro del resto,
así como los arrendadores y arrendatarios de locales de negocio que
consignarán separadamente las operaciones de arrendamiento de
locales de negocio declarables del resto, también deberán consignar
las cantidades percibidas en metálico superiores a 6.000 euros si son
percibidas de la misma persona o entidad.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
101-113 Parte entera del importe percibido en metálico, si no tiene
contenido se consignará a ceros.
114-115 Parte decimal del importe percibido en metálico, si no
tiene contenido se consignará a ceros.
116-131 Alfanumérico IMPORTE ANUAL PERCIBIDO POR TRANSMISIONES
DE INMUEBLES SUJETAS A IVA.
Este campo se subdivide en dos:
116 SIGNO: campo alfabético. Se consignará una “N” cuando
el importe anual de percibido por transmisiones de inmuebles
sujetas a IVA sea menor que 0 (cero). En cualquier otro caso el
contenido de este campo será un espacio.
117-131 IMPORTE: campo numérico de 15 posiciones. Se
consignará sin signo y sin coma decimal, separadamente de otras
operaciones, las cantidades que se perciban en contraprestación por
transmisiones de inmuebles correspondientes al año, efectuadas o
que se deban efectuar, que constituyan entregas sujetas en el
Impuesto sobre el Valor Añadido (IVA incluido).
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
117-129 Parte entera del importe anual percibido por
transmisiones de inmuebles sujetas a IVA, si no tiene
contenido se consignará a ceros.
130-131 Parte decimal del importe anual percibido por
transmisiones de inmuebles sujetas a IVA, si no tiene
contenido se consignará a ceros.
132-135 Numérico EJERCICIO.
Se consignarán las cuatro cifras del ejercicio en el que se hubieran
declarado las operaciones que dan origen al cobro en metálico por
importe superior a 6.000 euros
136-151 Alfanumérico IMPORTE DE LAS OPERACIONES PRIMER
TRIMESTRE.
Este campo se subdivide en dos:
136 SIGNO: campo alfabético. Se consignará una “N” cuando
el importe de las operaciones del primer trimestre sea menor que 0
79391-1102-A-EOB
:evc

# Pag. 15

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132701
(cero). En cualquier otro caso el contenido de este campo será un
espacio.
137-151 IMPORTE: campo numérico de 15 posiciones. Se
consignará sin signo y sin coma decimal, el importe de las
operaciones realizadas en el primer trimestre, con excepción de las
Entidades Aseguradoras que harán constar de forma separada las
operaciones de seguro del resto, así como los arrendadores y
arrendatarios de locales de negocio que consignarán separadamente
las operaciones de arrendamiento de locales de negocio declarables
del resto.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
137-149 Parte entera del importe de las operaciones primer
trimestre, si no tiene contenido se consignará a ceros.
150-151 Parte decimal del importe de las operaciones
primer trimestre, si no tiene contenido se consignará a
ceros.
152-167 Alfanumérico IMPORTE PERCIBIDO POR TRANSMISIONES DE
INMUEBLES SUJETAS A IVA PRIMER TRIMESTRE.
Este campo se subdivide en dos:
152 SIGNO: campo alfabético. Se consignará una “N” cuando
el importe percibido por transmisiones de inmuebles sujetas a IVA
del primer trimestre sea menor que 0 (cero). En cualquier otro caso
el contenido de este campo será un espacio.
153-167 IMPORTE: campo numérico de 15 posiciones. Se
consignará sin signo y sin coma decimal, separadamente de otras
operaciones, las cantidades que se perciban en contraprestación por
transmisiones de inmuebles, efectuadas o que se deban efectuar, que
constituyan entregas sujetas en el Impuesto sobre el Valor añadido
(IVA incluido) durante el primer trimestre.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
153-165 Parte entera del importe percibido por
transmisiones de inmuebles sujetas a IVA primer trimestre,
si no tiene contenido se consignará a ceros.
166-167 Parte decimal del importe percibido por
transmisiones de inmuebles sujetas a IVA primer trimestre,
si no tiene contenido se consignará a ceros.
168-183 Alfanumérico IMPORTE DE LAS OPERACIONES SEGUNDO
TRIMESTRE.
Este campo se subdivide en dos:
168 SIGNO: campo alfabético. Se consignará una “N” cuando
el importe de las operaciones del segundo trimestre sea menor que 0
(cero). En cualquier otro caso el contenido de este campo será un
espacio. 79391-1102-A-EOB
:evc

# Pag. 16

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132702
169-183 IMPORTE: campo numérico de 15 posiciones. Se
consignará sin signo y sin coma decimal el importe de las
operaciones realizadas en el segundo trimestre, con excepción de las
Entidades Aseguradoras que harán constar de forma separada las
operaciones de seguro del resto, así como los arrendadores y
arrendatarios de locales de negocio que consignarán separadamente
las operaciones de arrendamiento de locales de negocio declarables
del resto.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
169-181 Parte entera del importe de las operaciones
segundo trimestre, si no tiene contenido se consignará a
ceros.
182-183 Parte decimal del importe de las operaciones
segundo trimestre, si no tiene contenido se consignará a
ceros.
184-199 Alfanumérico IMPORTE PERCIBIDO POR TRANSMISIONES DE
INMUEBLES SUJETAS A IVA SEGUNDO
TRIMESTRE.
Este campo se subdivide en dos:
184 SIGNO: campo alfabético. Se consignará una “N” cuando
el importe percibido por transmisiones de inmuebles sujetas a IVA
del segundo trimestre sea menor que 0 (cero). En cualquier otro
caso el contenido de este campo será un espacio.
185-199 IMPORTE: campo numérico de 15 posiciones. Se
consignará sin signo y sin coma decimal separadamente de otras
operaciones, las cantidades que se perciban en contraprestación por
transmisiones de inmuebles, efectuadas o que se deban efectuar, que
constituyan entregas sujetas en el Impuesto sobre el Valor
añadido(IVA incluido) durante el segundo trimestre.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
185-197 Parte entera del importe percibido por transmisiones de
inmuebles sujetas a IVA segundo trimestre, si no tiene contenido se
consignará a ceros.
198-199 Parte decimal del importe percibido por transmisiones de
inmuebles sujetas a IVA segundo trimestre, si no tiene contenido se
consignará a ceros.
200-215 Alfanumérico IMPORTE DE LAS OPERACIONES TERCER
TRIMESTRE.
Este campo se subdivide en dos:
200 SIGNO: campo alfabético. Se consignará una “N” cuando
el importe de las operaciones del tercer trimestre sea menor que 0
(cero). En cualquier otro caso el contenido de este campo será un
espacio.
79391-1102-A-EOB
:evc

# Pag. 17

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132703
201-215 IMPORTE: campo numérico de 15 posiciones. Se
consignará sin signo y sin coma decimal el importe de las
operaciones realizadas durante el tercer trimestre, con excepción de
las Entidades Aseguradoras que harán constar de forma separada las
operaciones de seguro del resto, así como los arrendadores y
arrendatarios de locales de negocio que consignarán separadamente
las operaciones de arrendamiento de locales de negocio declarables
del resto.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
201-213 Parte entera del importe de las operaciones tercer
trimestre, si no tiene contenido se consignará a ceros.
214-215Parte decimal del importe de las operaciones tercer
trimestre, si no tiene contenido se consignará a ceros.
216-231 Alfanumérico IMPORTE PERCIBIDO POR TRANSMISIONES DE
INMUEBLES SUJETAS A IVA TERCER TRIMESTRE.
Este campo se subdivide en dos:
216 SIGNO: campo alfabético. Se consignará una “N” cuando
el importe percibido por transmisiones de inmuebles sujetas a IVA
del tercer trimestre sea menor que 0 (cero). En cualquier otro caso el
contenido de este campo será un espacio.
217-231 IMPORTE: campo numérico de 15 posiciones. Se
consignará sin signo y sin coma decimal separadamente de otras
operaciones, las cantidades que se perciban en contraprestación por
transmisiones de inmuebles, efectuadas o que se deban efectuar, que
constituyan entregas sujetas en el Impuesto sobre el Valor
añadido(IVA incluido) durante el tercer trimestre.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
217-229 Parte entera del importe percibido por transmisiones
de inmuebles sujetas a IVA tercer trimestre, si no tiene
contenido se consignará a ceros.
230-231 Parte decimal del importe percibido por transmisiones
de inmuebles sujetas a IVA tercer trimestre, si no tiene
contenido se consignará a ceros.
232-247 Alfanumérico IMPORTE DE LAS OPERACIONES CUARTO
TRIMESTRE.
Este campo se subdivide en dos:
232 SIGNO: campo alfabético. Se consignará una “N” cuando
el importe de las operaciones del cuarto trimestre sea menor que 0
(cero). En cualquier otro caso el contenido de este campo será un
espacio.
233-247 IMPORTE: campo numérico de 15 posiciones. Se
consignará sin signo y sin coma decimal el importe de las
operaciones realizadas durante el cuarto trimestre, con excepción de
las Entidades Aseguradoras que harán constar de forma separada las
79391-1102-A-EOB
:evc

# Pag. 18

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132704
operaciones de seguro del resto, así como los arrendadores y
arrendatarios de locales de negocio que consignarán separadamente
las operaciones de arrendamiento de locales de negocio declarables
del resto.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
233-245 Parte entera del importe de las operaciones cuarto
trimestre, si no tiene contenido se consignará a ceros.
246-247 Parte decimal del importe de las operaciones
cuarto trimestre, si no tiene contenido se consignará a
ceros.
248-263 Alfanumérico IMPORTE PERCIBIDO POR TRANSMISIONES DE
INMUEBLES SUJETAS A IVA CUARTO
TRIMESTRE.
Este campo se subdivide en dos:
248 SIGNO: campo alfabético. Se consignará una “N” cuando
el importe percibido por transmisiones de inmuebles sujetas a IVA
del cuarto trimestre sea menor que 0 (cero). En cualquier otro caso
el contenido de este campo será un espacio.
249-263 IMPORTE: campo numérico de 15 posiciones. Se
consignará sin signo y sin coma decimal, separadamente de otras
operaciones, las cantidades que se perciban en contraprestación por
transmisiones de inmuebles, efectuadas o que se deban efectuar, que
constituyan entregas sujetas en el Impuesto sobre el Valor
añadido(IVA incluido) durante el cuarto trimestre.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
249-261 Parte entera del importe percibido por transmisiones
de inmuebles sujetas a IVA cuarto trimestre, si no tiene
contenido se consignará a ceros.
262-263 Parte decimal del importe percibido por transmisiones
de inmuebles sujetas a IVA cuarto trimestre, si no tiene
contenido se consignará a ceros.
264 -500 -------- BLANCOS.
* Todos los importes serán positivos.
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a blancos.
* Todos los campos numéricos ajustados a la derecha y rellenos de ceros por la izquierda.
* Todos los campos alfanuméricos/alfabéticos ajustados a la izquierda y rellenos de blancos por
la derecha, en mayúsculas, sin caracteres especiales y sin vocales acentuadas, excepto que se
especifique lo contrario en la descripción del campo.
79391-1102-A-EOB
:evc

# Pag. 19

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132705
LAGEL
ETNATNESERPER
.F.I.N
OIRATADNERRA
.F.I.N
OICICREJE
OLEDOM 7
4
3
2
56
46
36
26
16
06
95
85
75
65
55
45
35
25
15
05
94
84
74
64
54
44
34
24
14
04
93
83
73
63
53
43
33
23
13
03
92
82
72
62
52
42
32
22
12
02
91
81
71
61
51
41
31
21
11
01
9
8
7
6
5
4
3
2
1
I
031921821721621521421321221121021911811711611511411311211111011901801701601501401301201101001
99
89
79
69
59
49
39
29
19
09
98
88
78
68
58
48
38
28
18
08
97
87
77
67
57
47
37
27
17
07
96
86
76
66
591491391291191091981881781681581481381281181081971871771671571471371271171071961861761661561461361261161061951851751651551451351251151051941841741641541441341241141041931831731631531431331231131
ATNALP
.CIFILAC
ATREUP
LATROP
EUQOLB
OSIP
O
OREMÚN
062952852752652552452352252152052942842742642542442342242142042932832732632532432332232132032922822722622522422322222122022912812712612512412312212112012902802702602502402302202102002991891791691
AJOH ED OPIT
OIRATADNERRA
LED
NÓICANIMONED
O
LAICOS
NÓZAR
,ERBMON
Y
SODILLEPA
NÓICAREPO
AL
ED
ETROPMI
ARETNE ELBEUMNI
LED
NÓICCERID
LARTSATAC
AICNEREFER
ACILBÚP
AÍV
AL
ED
ERBMON
ED
OREMÚN
OTNEMELPMOC
ASAC
LAMICED
ETNARALCED
NÓICACIFITNEDI
LARTSATAC
AICNEREFER
NÓICAREMUN
OPIT
ORTSIGER ED OPIT
AÍV
ED
OPIT
ARELACSE
ELBEUNMI
LED
NÓICCERID
ELBEUMNI .CAUTIS
ETNARALCED
.F.I.N
79391-1102-A-EOB
:evc

# Pag. 20

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132706
ELBEUMNI
LED
NÓICCERID
OIPICINUM
.DÓC
OIPICINUM
NÓICALBOP
O
DADILACOL
523423323223123023913813713613513413313213113013903803703603503403303203103003992892792692592492392292192092982882782682582482382282182082972872772672572472372272172072962862762662562462362262162 093983883783683583483383283183083973873773673573473373273173073963863763663563463363263163063953853753653553453353253153053943843743643543443343243143043933833733633533433333233133033923823723623 554454354254154054944844744644544444344244144044934834734634534434334234134034924824724624524424324224124024914814714614514414314214114014904804704604504404304204104004993893793693593493393293193
005994894794694594494394294194094984884784684584484384284184084974874774674574474374274174074964864764664564464364264164064954854754654
AICNIVORP
OGIDOC
LATSOP
OGIDOC
79391-1102-A-EOB
:evc

# Pag. 21

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132707
MODELO 347
B.- TIPO DE REGISTRO 2: REGISTRO DE INMUEBLE.
(POSICIONES, NATURALEZA Y DESCRIPCIÓN DE LOS CAMPOS)
POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS
1 Numérico TIPO DE REGISTRO.
Constante '2'.
2-4 Numérico MODELO DECLARACIÓN.
Constante '347'.
5-8 Numérico EJERCICIO.
Consignar lo contenido en estas mismas posiciones del registro de
tipo 1.
9-17 Alfanumérico NIF DEL DECLARANTE.
Consignar lo contenido en estas mismas posiciones del registro de
tipo 1.
18-26 Alfanumérico NIF DEL ARRENDATARIO.
Si el arrendatario dispone de NIF asignado en España, se
consignará:
Si es una persona física se consignará el NIF del declarado de
acuerdo con las reglas previstas en el Reglamento General de las
actuaciones y los procedimientos de gestión e inspección
tributaria y de desarrollo de las normas comunes de los
procedimientos de aplicación de los tributos, aprobado por el Real
Decreto 1065/2007, de 27 de julio, (BOE del 5 de septiembre).
Si el declarado es una persona jurídica o una entidad sin
personalidad jurídica (Comunidad de bienes, Sociedad civil,
herencia yacente, etc.), se consignará el número de identificación
fiscal correspondiente a la misma.
Para la identificación de los menores de 14 años en sus relaciones
de naturaleza o con trascendencia tributaria habrán de figurar
tanto los datos de la persona menor de 14 años, incluido su
número de identificación fiscal, como los de su representante
legal.
Este campo deberá estar ajustado a la derecha, siendo la última
posición el carácter de control y rellenando con ceros las posiciones
a la izquierda.
Sólo se cumplimentará con los NIF asignados en España.
79391-1102-A-EOB
:evc

# Pag. 22

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132708
27-35 Alfanumérico NIF DEL REPRESENTANTE LEGAL.
Si el arrendatario es menor de 14 años se consignará en este campo
el número de identificación fiscal de su representante legal (padre,
madre o tutor).
En cualquier otro caso el contenido de este campo se rellenará a
espacios.
36-75 Alfanumérico APELLIDOS Y NOMBRE, RAZÓN SOCIAL O
DENOMINACIÓN DEL ARRENDATARIO.
a) Para personas físicas se consignará el primer apellido, un
espacio, el segundo apellido, un espacio y el nombre completo,
necesariamente en este mismo orden. Si el arrendatario es
menor de 14 años, se consignarán en este campo los apellidos
y nombre del menor de 14 años.
b) Tratándose de personas jurídicas y entidades sin personalidad
jurídica, se consignará la razón social o la denominación
completa de la entidad, sin anagramas.
76 Alfabético TIPO DE HOJA.
Constante ‘I’.
77-99 -------- BLANCOS.
100-114 Numérico IMPORTE DE LA OPERACION.
Se consignará el importe total, sin signo y sin coma decimal, del
arrendamiento del local de negocios correspondiente al año natural
al que se refiere la declaración, cualquiera que sea la cuantía a la
que ascienda el mismo.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
100-112 Parte entera del importe de la operación, si no tiene
contenido se consignará a ceros.
113-114 Parte decimal del importe de la operación, si no tiene
contenido se consignará a ceros.
115 Numérico SITUACIÓN DEL INMUEBLE.
Se consignará de entre las siguientes claves la que corresponda a la
situación del local de negocio arrendado:
1. Inmueble con referencia catastral situado en cualquier punto del
territorio español, excepto País Vasco y Navarra.
2. Inmueble situado en la Comunidad Autónoma del País Vasco o
en la Comunidad Foral de Navarra.
3. Inmueble en cualquiera de las situaciones anteriores pero sin
referencia catastral.
4. Inmueble situado en el extranjero.
116-140 Alfanumérico REFERENCIA CATASTRAL.
Se consignará la referencia catastral correspondiente al local de
negocio arrendado.
79391-1102-A-EOB
:evc

# Pag. 23

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132709
141-333 Alfanumérico DIRECCIÓN DEL INMUEBLE.
Se consignará la dirección correspondiente al local de negocio
arrendado.
Este campo se subdivide en:
141 –145 TIPO DE VÍA
Se consignará el código alfabético de tipo de vía, normalizado
según Instituto Nacional de Estadística (INE).
146 –195 NOMBRE VÍA PÚBLICA
Se consignará el nombre largo de la vía pública , si no cupiese
completo el nombre, no se harán constar los artículos, preposiciones
ni conjunciones y se pondrán en abreviatura los títulos (vgr. cd =
Conde). Los demás casos se abreviarán utilizando las siglas de uso
general.
196–198 TIPO DE NUMERACIÓN
Se consignará el tipo de numeración (Valores: NÚM ; KM. ; S/N;
etc.).
199–203 NÚMERO DE CASA
Se consignará el número de casa o punto kilométrico.
204-206 CALIFICADOR DEL NÚMERO
Se consignará el calificador del número(valores BIS; DUP;
MOD; ANT; etc / metros si Tipo Numer = KM.)
207–209 BLOQUE
Se consignará el bloque (número o letras).
210–212 PORTAL
Se consignará el portal (número o letras).
213–215 ESCALERA
Se consignará la escalera (número o letras).
216–218 PLANTA O PISO
Se consignará la planta o el piso (número o letras).
219–221 PUERTA
Se consignará la puerta (número o letras).
222–261 COMPLEMENTO
Datos complementarios del domicilio. Valores: Literal
libre.(Ejemplos: “Urbanización ..........”; “Centro Comercial........,
local ..........”; “Mercado de .......... puesto nº .........”; “Edificio
.........”; etc).
262–291 LOCALIDAD O POBLACIÓN
Se consignará el nombre de la localidad, de la población, etc, si es
distinta al Municipio
79391-1102-A-EOB
:evc

# Pag. 24

BOLETÍN OFICIAL DEL ESTADO
Núm. 298 Lunes 12 de diciembre de 2011 Sec. I. Pág. 132710
292–321 MUNICIPIO
Se consignará el nombre de municipio
Se consignará el correspondiente al local de negocio arrendado.
322–326 CÓDIGO DE MUNICIPIO
Se consignará el CODIGO de municipio normalizado según
Instituto Nacional de Estadística (INE).
327-328 CÓDIGO PROVINCIA
Se consignará el código de la provincia.
Se consignarán los dos dígitos numéricos que correspondan a la
provincia o, en su caso, ciudad autónoma, que corresponda al local
de negocios arrendado, según la siguiente relación:
ÁLAVA/ARABA ..... 01 LEÓN ......................... 24
ALBACETE .............. 02 LLEIDA ..................... 25
ALICANTE/Alacant . 03 LUGO ........................ 27
ALMERÍA ................ 04 MADRID ................... 28
ASTURIAS ............... 33 MÁLAGA .................. 29
ÁVILA ...................... 05 MELILLA .................. 52
BADAJOZ ................ 06 MURCIA ................... 30
BARCELONA .......... 08 NAVARRA ............... 31
BURGOS .................. 09 OURENSE ................. 32
CÁCERES ................. 10 PALENCIA ............... 34
CÁDIZ ....................... 11 PALMAS, LAS ......... 35
CANTABRIA ........... 39 PONTEVEDRA ........ 36
CASTELLÓN/Castell 12 RIOJA, LA ................. 26
CEÚTA ..................... 51 SALAMANCA ......... 37
CIUDAD REAL ....... 13 S.C.TENERIFE ......... 38
CÓRDOBA ............... 14 SEGOVIA .................. 40
CORUÑA, A ............. 15 SEVILLA ................... 41
CUENCA .................. 16 SORIA ....................... 42
GIRONA ................... 17 TARRAGONA .......... 43
GRANADA .............. 18 TERUEL .................... 44
GUADALAJARA .... 19 TOLEDO ................... 45
GIPÚZKOA .............. 20 VALENCIA ............... 46
HUELVA .................. 21 VALLADOLID ......... 47
HUESCA ................... 22 BIZKAIA ................... 48
ILLES BALEARS .... 07 ZAMORA .................. 49
JAÉN ......................... 23 ZARAGOZA ............. 50
329-333 CÓDIGO POSTAL
Se consignará el código postal correspondiente a la
dirección del local de negocio arrendado.
334-500 -------- BLANCOS.
* Todos los importes serán positivos.
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a blancos.
* Todos los campos numéricos ajustados a la derecha y rellenos de ceros por la izquierda.
* Todos los campos alfanuméricos/alfabéticos ajustados a la izquierda y rellenos de blancos por
la derecha, en mayúsculas, sin caracteres especiales y sin vocales acentuadas, excepto que se
especifique lo contrario en la descripción del campo.
79391-1102-A-EOB
:evc
http://www.boe.es BOLETÍN OFICIAL DEL ESTADO D. L.: M-1/1958 - ISSN: 0212-033X