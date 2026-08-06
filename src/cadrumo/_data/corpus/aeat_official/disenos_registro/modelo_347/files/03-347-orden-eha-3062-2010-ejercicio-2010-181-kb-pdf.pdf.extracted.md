# Pag. 1

ANEXO II
DISEÑOS FÍSICOS Y LÓGICOS PARA LA PRESENTACIÓN
DEL MODELO 347 EN SOPORTE
DIRECTAMENTE LEGIBLE POR ORDENADOR
Versión 1.0

# Pag. 2

ANEXO II
DISEÑOS FÍSICOS Y LÓGICOS A LOS QUE DEBEN AJUSTARSE LOS ARCHIVOS QUE
SE GENEREN PARA LA PRESENTACIÓN TELEMÁTICA Y LOS SOPORTES
DIRECTAMENTE LEGIBLES POR ORDENADOR DEL MODELO 347.
DISEÑOS LÓGICOS
DESCRIPCIÓN DE LOS REGISTROS
Para cada declarante se incluirán dos tipos diferentes de registro, que se distinguen por la
primera posición, con arreglo a los siguientes criterios:
Tipo 1: Registro del declarante: Datos identificativos y resumen de la declaración. Diseño
de tipo de registro 1 de los recogidos más adelante en estos mismos apartados y
Anexo de la presente Orden.
Tipos 2: Registro de declarado y Registro de inmueble. Diseño de tipo de registro 2 de los
recogidos más adelante en estos mismos apartados y Anexo de la presente
Orden.
El orden de presentación será el del tipo de registro, existiendo un único registro del tipo 1 y
tantos registros del tipo 2 como declarados e inmuebles tenga la declaración, siendo diferentes los
de declarados y los de inmuebles.
Todos los campos alfanuméricos y alfabéticos se presentarán alineados a la izquierda y
rellenos de blancos por la derecha, en mayúsculas sin caracteres especiales, y sin vocales
acentuadas.
Para los caracteres específicos del idioma se utilizará la codificación ISO-8859-1. De esta
forma la letra “Ñ” tendrá el valor ASCII 209 (Hex. D1) y la “Ç”(cedilla mayúscula) el valor ASCII
199 (Hex. C7).
Todos los campos numéricos se presentarán alineados a la derecha y rellenos a ceros por la
izquierda sin signos y sin empaquetar.
Todos los campos tendrán contenido, a no ser que se especifique lo contrario en la
descripción del campo. Si no lo tuvieran, los campos numéricos se rellenarán a ceros y tanto los
alfanuméricos como los alfabéticos a blancos.
El primer registro del fichero ( tipo 1) , contendrá un campo de 13 caracteres, en las
posiciones 488 a 500 reservado para el sello electrónico, que será cumplimentado exclusivamente
por los programas oficiales de la A.E.A.T. En cualquier otro caso se rellenará a blancos.
1

# Pag. 3

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
9-17 Alfanumérico N.I.F. DEL DECLARANTE.
Se consignará el N.I.F. del declarante.
Este campo deberá estar ajustado a la derecha, siendo la última
posición el carácter de control y rellenando con ceros las
posiciones de la izquierda, de acuerdo con las reglas previstas en el
Real Decreto 1065/2007 de 27 de Julio, por el que se aprueba el
Reglamento General de las actuaciones y los procedimientos de
gestión e inspección tributaria y de desarrollo de las normas
comunes de los procedimientos de aplicación de los tributos,
(B.O.E del 5 de septiembre).
18-57 Alfanumérico APELLIDOS Y NOMBRE O RAZÓN SOCIAL DEL
DEL DECLARANTE.
Si es una persona física se consignará el primer apellido, un
espacio, el segundo apellido, un espacio y el nombre completo,
necesariamente en este orden.
Para personas jurídicas y entidades en régimen de atribución de
rentas, se consignará la razón social completa, sin anagrama.
En ningún caso podrá figurar en este campo un nombre comercial.
58 Alfabético TIPO DE SOPORTE.
Se cumplimentará una de las siguientes claves:
2

# Pag. 4

'C': Si la información se presenta en CD-R (Compact
Disc Recordable).
'T': Transmisión telemática
La presentación por Internet (con certificado de
usuario), solo podrá realizarse para declaraciones que
no superen los 30.000 registros.
59-107 Alfanumérico PERSONA CON QUIÉN RELACIONARSE
Datos de la persona con quién relacionarse. Este campo se
subdivide en dos:
59-67 TELÉFONO: Campo numérico de 9 posiciones.
68-107 APELLIDOS Y NOMBRE: Se consignará el
primer apellido, un espacio, el segundo apellido, un
espacio y el nombre completo, necesariamente en este
orden.
108- 120 Numérico NUMERO IDENTIFICATIVO DE LA
DECLARACION.
Se consignará el número identificativo correspondiente a la
declaración. Campo de contenido numérico de 13 posiciones.
El número identificativo que habrá de figurar, será un número
secuencial cuyos tres primeros dígitos se corresponderán con el
código 347.
121- 122 Alfabético DECLARACION COMPLEMENTARIA
O SUSTITUTIVA.
En el caso excepcional de segunda o posterior presentación de
declaraciones, deberá cumplimentarse obligatoriamente uno de los
siguientes campos:
121 DECLARACIÓN COMPLEMENTARIA.: Se
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
la Oficina Virtual de la Agencia Tributaria (
www.agenciatributaria.es )
3

# Pag. 5

122 DECLARACIÓN SUSTITUTIVA: Se consignará
una “S” si la presentación tiene como objeto anular y
sustituir completamente a otra declaración anterior, del
mismo ejercicio. Una declaración sustitutiva sólo puede
anular a una única declaración anterior.
123- 135 Numérico NUMERO IDENTIFICATIVO DE LA
DECLARACIÓN ANTERIOR.
En el caso de que se haya consignado una “C” en el campo
“Declaración complementaria” o en el caso de que se haya
consignado “S” en el campo “Declaración sustitutiva”, se
consignará el número identificativo correspondiente a la
declaración a la que sustituye.
Campo de contenido numérico de 13 posiciones.
En cualquier otro caso deberá rellenarse a CEROS.
136-144 Numérico NUMERO TOTAL DE PERSONAS Y ENTIDADES.
Se consignará el número total de personas y entidades declaradas
en el registro de declarado (registro de detalle de tipo 2) por la
entidad declarante. Si un mismo declarado figura en varios
registros, se computará tantas veces como figure relacionado.
(Número de registros de tipo 2)
145-159 Numérico IMPORTE TOTAL DE LAS OPERACIONES.
Campo numérico de 15 posiciones.
Se consignará sin signo y sin coma decimal la suma total de las
cantidades reflejadas en el campo ‘IMPORTE DE LAS
OPERACIONES’ (posiciones 83 a 97) correspondientes a los
registros de declarados.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
145-157 Parte entera del importe total de las operaciones, si no
tiene contenido se consignará a ceros.
158-159 Parte decimal del importe total de las operaciones, si no
tiene contenido se consignará a ceros.
160-168 Numérico NUMERO TOTAL DE INMUEBLES.
Se consignará el número total de inmuebles declarados en el
registro de inmueble (registro de detalle de tipo 2) por la entidad
declarante. Si un mismo inmueble figura en varios registros, se
computará tantas veces como figure relacionado. (Número de
registros de tipo 2)
4

# Pag. 6

169-183 Numérico IMPORTE TOTAL DE LAS OPERACIONES DE
ARRENDAMIENTO DE LOCALES DE NEGOCIO.
Campo numérico de 15 posiciones.
Se consignará sin signo y sin coma decimal la suma total de las
cantidades reflejadas en el campo ‘IMPORTE DE LA
OPERACION’ (posiciones 100 a 114) correspondientes a los
registros de inmuebles.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
169-181 Parte entera del importe total de las operaciones de
arrendamiento de locales de negocio, si no tiene contenido se
consignará a ceros.
182-183 Parte decimal del importe total de las operaciones de
arrendamiento de locales de negocio, si no tiene contenido se
consignará a ceros.
184-390 ------------ BLANCOS
391-399 Alfanumérico N.I.F. DEL REPRESENTANTE LEGAL.
Si el declarante es menor de 14 años se consignará en este campo
el número de identificación fiscal de su representante legal (padre,
madre o tutor). Este campo deberá estar ajustado a la derecha,
siendo la última posición el carácter de control y rellenando con
ceros las posiciones a la izquierda.
En cualquier otro caso el contenido de este campo se rellenará a
espacios.
400-487 ------------ BLANCOS
488-500 Alfanumérico SELLO ELECTRONICO
Campo reservado para el sello electrónico en presentaciones
individuales, que será cumplimentado exclusivamente por los
programas de la A.E.A.T. En cualquier otro caso se rellenará a
blancos.
* Todos los importes serán positivos.
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a blancos.
* Todos los campos numéricos ajustados a la derecha y rellenos de ceros por la izquierda.
* Todos los campos alfanuméricos/alfabéticos ajustados a la izquierda y rellenos de blancos
por la derecha, en mayúsculas, sin caracteres especiales y sin vocales acentuadas, excepto que
se especifique lo contrario en la descripción del campo.
5

# Pag. 7

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
9-17 Alfanumérico N.I.F. DEL DECLARANTE.
Consignar lo contenido en estas mismas posiciones del registro de
tipo 1.
18-26 Alfanumérico N.I.F. DEL DECLARADO.
Si el declarado dispone de NIF asignado en España, se consignará:
Si es una persona física se consignará el N.I.F. del declarado de
acuerdo con las reglas previstas en el Real Decreto 1065/2007, de
27 de julio, por el que se aprueba el Reglamento General de las
actuaciones y los procedimientos de gestión e inspección
tributaria y de desarrollo de las normas comunes de los
procedimientos de aplicación de los tributos, (B.O.E del 5 de
septiembre).
Si el declarado es una persona jurídica o una entidad en régimen de
atribución de rentas (Comunidad de bienes, Sociedad civil,
herencia yacente, etc.), se consignará el número de identificación
fiscal correspondiente a la misma.
Para la identificación de los menores de 14 años en sus
relaciones de naturaleza o con trascendencia tributaria habrán de
figurar tanto los datos de la persona menor de 14 años, incluido
su número de identificación fiscal, como los de su representante
legal.
Este campo deberá estar ajustado a la derecha, siendo la última
posición el carácter de control y rellenando con ceros las
posiciones a la izquierda.
6

# Pag. 8

Sólo se cumplimentará con los NIF asignados en España.
27-35 Alfanumérico N.I.F. DEL REPRESENTANTE LEGAL.
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
espacio, el segundo apellido, un espacio y el nombre
completo, necesariamente en este mismo orden. Si el
declarado es menor de edad, se consignarán en este campo los
apellidos y nombre del menor de edad.
b) Tratándose de personas jurídicas y entidades en régimen de
atribución de rentas, se consignará la razón social o la
denominación completa de la entidad, sin anagramas.
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
ÁLAVA .................... 01 LEÓN .......................... 24
ALBACETE ............. 02 LLEIDA ...................... 25
ALICANTE .............. 03 LUGO .......................... 27
ALMERÍA ................ 04 MADRID ..................... 28
ASTURIAS .............. 33 MÁLAGA ................... 29
ÁVILA ...................... 05 MELILLA ................... 52
BADAJOZ ................ 06 MURCIA ..................... 30
BARCELONA.......... 08 NAVARRA ................. 31
BURGOS .................. 09 OURENSE .................. 32
CÁCERES ................ 10 PALENCIA ................. 34
CÁDIZ ...................... 11 PALMAS, LAS ........... 35
CANTABRIA ........... 39 PONTEVEDRA .......... 36
CASTELLÓN ........... 12 RIOJA, LA .................. 26
CEUTA ..................... 51 SALAMANCA ........... 37
7

# Pag. 9

CIUDAD REAL ....... 13 S.C.TENERIFE ........... 38
CÓRDOBA .............. 14 SEGOVIA ................... 40
CORUÑA, A ............ 15 SEVILLA .................... 41
CUENCA .................. 16 SORIA ......................... 42
GIRONA................... 17 TARRAGONA ............ 43
GRANADA .............. 18 TERUEL ..................... 44
GUADALAJARA .... 19 TOLEDO ..................... 45
GUIPÚZCOA ........... 20 VALENCIA ................ 46
HUELVA .................. 21 VALLADOLID ........... 47
HUESCA .................. 22 VIZCAYA ................... 48
ILLES BALEARS .... 07 ZAMORA.................... 49
JAÉN ........................ 23 ZARAGOZA ............... 50
En el caso de no residentes sin establecimiento permanente se
consignará 99.
79-80 CÓDIGO PAÍS.
Campo alfabético de 2 posiciones.
En el caso de no residentes sin establecimiento permanente se
consignará XX, siendo XX el Código del país de residencia del
declarado, de acuerdo con los códigos alfabéticos de países y
territorios que figuran en la Orden HAC/3626/2003, de 23 de
diciembre, en su Anexo 11 (B.O.E 30 de diciembre de 2003) que
aprueba los modelos de declaración del Impuesto sobre la Renta de
no Resientes.
En cualquier otro caso se rellenará a blancos .
81 ------------ BLANCOS
82 Alfabético CLAVE OPERACIÓN.
Se consignará la que corresponda según el siguiente detalle:
A Adquisiciones de bienes y servicios superiores a 3.005,06
euros.
B Entregas de bienes y prestaciones de servicios superiores
a 3.005,06 euros.
C Cobros por cuenta de terceros superiores a 300,51 euros.
D Adquisiciones de bienes o servicios al margen de
cualquier actividad empresarial o profesional por
Entidades Públicas superiores a 3.005,06 euros.
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
8

# Pag. 10

G Compras agencia viaje: Prestaciones de servicios de
transportes de viajeros y de sus equipajes por vía aérea a
que se refiere la disposición adicional cuarta del
Reglamento por el que se regulan las obligaciones de
facturación.
83-97 Numérico IMPORTE DE LAS OPERACIONES.
Se consignará sin signo y sin coma decimal el importe de las
operaciones, con excepción de las Entidades Aseguradoras que
harán constar de forma separada las operaciones de seguro del
resto, así como los arrendadores y arrendatarios de locales de
negocio que consignarán separadamente las operaciones de
arrendamiento de locales de negocio declarables del resto.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
83-95 Parte entera del importe de las operaciones, si no tiene
contenido se consignará a ceros.
96-97 Parte decimal del importe de las operaciones, si no tiene
contenido se consignará a ceros.
98 Alfabético OPERACIÓN SEGURO.
(Sólo Entidades Aseguradoras).
Las Entidades Aseguradoras pondrán una ‘X’ en este campo para
identificar las operaciones de seguros, debiendo consignarlas
separadamente del resto de operaciones.
99 Alfabético ARRENDAMIENTO LOCAL NEGOCIO.
(Sólo arrendadores y arrendatarios de Locales de Negocio).
Se pondrá en este campo una ‘X’ para operaciones de
arrendamiento de locales de negocio, debiendo consignarlas
separadamente del resto.
Además los arrendadores deberán cumplimentar los campos que
componen el REGISTRO DE INMUEBLE, consignando el
Importe Total de cada arrendamiento correspondiente al año
natural al que se refiere la declaración, con independencia de que
éste ya haya sido incluido en la clave ‘B’ (ventas).
100-114 Numérico IMPORTE PERCIBIDO EN METÁLICO.
Se consignará sin signo y sin coma decimal los importes
superiores a 6000 euros que se hubieran percibido en metálico
(moneda o billetes de curso legal) de cada una de las personas o
entidades relacionadas en la declaración. Las Entidades
Aseguradoras que harán constar de forma separada las operaciones
de seguro del resto, así como los arrendadores y arrendatarios de
9

# Pag. 11

locales de negocio que consignarán separadamente las operaciones
de arrendamiento de locales de negocio declarables del resto,
también deberán consignar las cantidades percibidas en metálico
superiores a 6000 euros si son percibidas de la misma persona o
entidad.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
100-112 Parte entera del importe percibido en metálico, si no tiene
contenido se consignará a ceros.
113-114 Parte decimal del importe percibido en metálico, si no
tiene contenido se consignará a ceros.
115-129 Numérico IMPORTE PERCIBIDO POR TRANSMISIONES DE
INMUEBLES SUJETAS A IVA.
Se consignará, sin signo y sin coma decimal, separadamente de
otras operaciones, las cantidades que se perciban en
contraprestación por transmisiones de inmuebles, efectuadas o que
se deban efectuar, que constituyan entregas sujetas en el Impuesto
sobre el Valor añadido(IVA incluido).
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
115-127 Parte entera del importe percibido por transmisiones de
inmuebles sujetas a IVA, si no tiene contenido se consignará a
ceros.
128-129 Parte decimal del importe percibido por transmisiones de
inmuebles sujetas a IVA, si no tiene contenido se consignará a
ceros.
130-133 Numérico EJERCICIO.
Se consignarán las cuatro cifras del ejercicio en el que se hubieran
declarado las operaciones que dan origen al cobro en metálico por
importe superior a 6.000 euros
134-500 -------- BLANCOS.
* Todos los importes serán positivos.
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a blancos.
* Todos los campos numéricos ajustados a la derecha y rellenos de ceros por la izquierda.
10

# Pag. 12

* Todos los campos alfanuméricos/alfabéticos ajustados a la izquierda y rellenos de blancos
por la derecha, en mayúsculas, sin caracteres especiales y sin vocales acentuadas, excepto que
se especifique lo contrario en la descripción del campo.
11

# Pag. 13

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
9-17 Alfanumérico N.I.F. DEL DECLARANTE.
Consignar lo contenido en estas mismas posiciones del registro de
tipo 1.
18-26 Alfanumérico N.I.F. DEL ARRENDATARIO.
Si el declarado dispone de NIF asignado en España, se consignará:
Si es una persona física se consignará el N.I.F. del declarado de
acuerdo con las reglas previstas en el Real Decreto 1065/2007, de
27 de julio, por el que se aprueba el Reglamento General de las
actuaciones y los procedimientos de gestión e inspección
tributaria y de desarrollo de las normas comunes de los
procedimientos de aplicación de los tributos, (B.O.E del 5 de
septiembre).
Si el declarado es una persona jurídica o una entidad en régimen de
atribución de rentas (Comunidad de bienes, Sociedad civil,
herencia yacente, etc.), se consignará el número de identificación
fiscal correspondiente a la misma.
Para la identificación de los menores de 14 años en sus
relaciones de naturaleza o con trascendencia tributaria habrán de
figurar tanto los datos de la persona menor de 14 años, incluido
su número de identificación fiscal, como los de su representante
legal.
Este campo deberá estar ajustado a la derecha, siendo la última
posición el carácter de control y rellenando con ceros las
posiciones a la izquierda.
12

# Pag. 14

Sólo se cumplimentará con los NIF asignados en España.
27-35 Alfanumérico N.I.F. DEL REPRESENTANTE LEGAL.
Si el arrendatario es menor de 14 años se consignará en este campo
el número de identificación fiscal de su representante legal (padre,
madre o tutor).
En cualquier otro caso el contenido de este campo se rellenará a
espacios.
36-75 Alfanumérico APELLIDOS Y NOMBRE, RAZÓN SOCIAL O
DENOMINACIÓN DEL ARRENDATARIO.
a) Para personas físicas se consignará el primer apellido, un
espacio, el segundo apellido, un espacio y el nombre
completo, necesariamente en este mismo orden. Si el
declarado es menor de 14 años, se consignarán en este campo
los apellidos y nombre del menor de 14 años.
b) Tratándose de personas jurídicas y entidades en régimen de
atribución de rentas, se consignará la razón social o la
denominación completa de la entidad, sin anagramas.
76 Alfabético TIPO DE HOJA.
Constante ‘I’.
77-99 -------- BLANCOS.
100-114 Numérico IMPORTE DE LA OPERACION.
Se consignará el importe total, sin signo y sin coma decimal, del
arrendamiento del local de negocios correspondientes al año
natural al que se refiere la declaración, cualquiera que sea la
cuantía a la que ascienda el mismo.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
100-112 Parte entera del importe de la operación, si no tiene
contenido se consignará a ceros.
113-114 Parte decimal del importe total de la operación, si no tiene
contenido se consignará a ceros.
115 Numérico SITUACIÓN DEL INMUEBLE.
Se consignará de entre las siguientes claves la que corresponda a la
situación del local de negocio arrendado:
1. Inmueble con referencia catastral situado en cualquier punto del
territorio español, excepto País Vasco y Navarra.
2. Inmueble situado en la Comunidad Autónoma del País Vasco o
en la Comunidad Foral de Navarra.
13

# Pag. 15

3. Inmueble en cualquiera de las situaciones anteriores pero sin
referencia catastral.
4. Inmueble situado en el extranjero.
116-140 Alfanumérico REFERENCIA CATASTRAL.
Se consignará la referencia catastral correspondiente al local de
negocio arrendado.
141-333 Alfanumérico DIRECCIÓN DEL INMUEBLE
Se consignará la dirección correspondiente al local de
negocio arrendado.
Este campo se subdivide en :
141 –145 TIPO DE VÍA
Se consignará el código alfabético normalizado de tipo de vía,
normalizado según Instituto Nacional de Estadística (INE).
146 –195 NOMBRE VÍA PUBLICA
Se consignará el nombre largo de la vía pública , si no
cupiese completo el nombre, no se harán constar los
artículos, preposiciones ni conjunciones y se pondrán en
abreviatura los títulos (vgr. cd = Conde). Los demás casos
se abreviarán utilizando las siglas de uso general.
196–198 TIPO DE NUMERACIÓN
Se consignará el tipo de numeración(Valores: NÚM ;
KM. ; S/N ; etc.).
199–203 NUMERO DE CASA
Se consignará el numero de casa o punto kilométrico.
204-206 CALIFICADOR DEL NUMERO
Se consignará el calificador del numero(valores BIS;
DUP; MOD; ANT; etc / metros si Tipo Numer = KM.)
207–209 BLOQUE
Se consignará el bloque (número o letras)
210–212 PORTAL
Se consignará el portal (número o letras)
213–215 ESCALERA
Se consignará la escalera (número o letras)
216–218 PLANTA O PISO
Se consignará la planta o el piso (número o letras)
219–221 PUERTA
Se consignará la puerta (número o letras)
222–261 COMPLEMENTO.
Datos complementarios del domicilio. Valores: Literal
libre.(Ejemplos: “Urbanización ..........”; “Centro
Comercial........, local ..........”; “Mercado de ..........
puesto nº .........”; “Edificio .........”; etc).
14

# Pag. 16

262–291 LOCALIDAD O POBLACIÓN.
Se consignará el nombre de la localidad, de la población,
etc, sí es distinta al Municipio
292–321 MUNICIPIO
Se consignará el nombre de municipio
Se consignará el correspondiente al local de negocio arrendado.
322–326 CODIGO DE MUNICIPIO
Se consignará el CODIGO de municipio normalizado según
Instituto Nacional de Estadística (INE).
327-328 CODIGO PROVINCIA
Se consignará el código de la provincia.
Se consignarán los dos dígitos numéricos que correspondan a la
provincia o, en su caso, ciudad autónoma, del que corresponda al
local de negocios arrendado, según la siguiente relación:
ÁLAVA .................... 01 LEÓN .......................... 24
ALBACETE ............. 02 LLEIDA ...................... 25
ALICANTE .............. 03 LUGO .......................... 27
ALMERÍA ................ 04 MADRID ..................... 28
ASTURIAS .............. 33 MÁLAGA ................... 29
ÁVILA ...................... 05 MELILLA ................... 52
BADAJOZ ................ 06 MURCIA ..................... 30
BARCELONA.......... 08 NAVARRA ................. 31
BURGOS .................. 09 OURENSE .................. 32
CÁCERES ................ 10 PALENCIA ................. 34
CÁDIZ ...................... 11 PALMAS, LAS ........... 35
CANTABRIA ........... 39 PONTEVEDRA .......... 36
CASTELLÓN ........... 12 RIOJA, LA .................. 26
CEÚTA ..................... 51 SALAMANCA ........... 37
CIUDAD REAL ....... 13 S.C.TENERIFE ........... 38
CÓRDOBA .............. 14 SEGOVIA ................... 40
CORUÑA, A ............ 15 SEVILLA .................... 41
CUENCA .................. 16 SORIA ......................... 42
GIRONA................... 17 TARRAGONA ............ 43
GRANADA .............. 18 TERUEL ..................... 44
GUADALAJARA .... 19 TOLEDO ..................... 45
GUIPÚZCOA ........... 20 VALENCIA ................ 46
HUELVA .................. 21 VALLADOLID ........... 47
HUESCA .................. 22 VIZCAYA ................... 48
ILLES BALEARS .... 07 ZAMORA.................... 49
JAÉN ........................ 23 ZARAGOZA ............... 50
329-333 CODIGO POSTAL
Se consignará el código postal correspondiente a la
dirección del local de negocio arrendado.
334-500 -------- BLANCOS.
15

# Pag. 17

* Todos los importes serán positivos.
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a blancos.
* Todos los campos numéricos ajustados a la derecha y rellenos de ceros por la izquierda.
* Todos los campos alfanuméricos/alfabéticos ajustados a la izquierda y rellenos de blancos
por la derecha, en mayúsculas, sin caracteres especiales y sin vocales acentuadas, excepto que
se especifique lo contrario en la descripción del campo.
16

# Pag. 18

MODELO 347 REGISTRO DE TIPO 1 REGISTRO DE DECLARANTE
1 3 4 7
1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60 61 62 63 64 65
CON QUIEN RELACIONARSE
NUMERO IDENTIFICATIVO DE LA
DECLARACIÓN
66 67 68 69 70 71 72 73 74 75 76 77 78 79 80 81 82 83 84 85 86 87 88 89 90 91 92 93 94 95 96 97 98 99 100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130
131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195
196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260
AIRATNEMELPMOC.CED
AVITUTITSUS.CED
NUMERO IDENTIFICATIVO
DE LA DECLARACIÓN
ANTERIOR
APELLIDOS Y NOMBRE
ORTSIGER
ED
OPIT
ETROPOS
ED
OPIT
IDENTIFICACIÓN DEL DECLARANTE PERSONA
APELLIDOS Y NOMBRE, RAZON SOCIAL O DENOMINACIÓN DEL DECLARANTE
MODELO EJERCICIO N.I.F. DEL DECLARANTE TELEFONO
NUMERO TOTAL DE NUMERO TOTAL DE IMPORTE TOTAL DE LAS OPERACIONES DE
IMPORTE TOTAL DE LAS OPERACIONES
PERSONAS Y ENTIDADES INMUEBLES ARRENDAMIENTO DE LOCALES DE NEGOCIO

# Pag. 19

MODELO 347 REGISTRO DE TIPO 1 REGISTRO DE DECLARANTE
261262263264265266267268269270271272273274275276277278279280281282283284285286287288289290291292293294295296297298299300301302303304305306307308309310311312313314315316317318319320321322323324325
326327328329330331332333334335336337338339340341342343344345346347348349350351352353354355356357358359360361362363364365366367368369370371372373374375376377378379380381382383384385386387388389390
NIF. DEL REPRESENTANTE
LEGAL
391392393394395396397398399400401402403404405406407408409410411412413414415416417418419420421422423424425426427428429430431432433434435436437438439440441442443444445446447448449450451452453454455
SELLO ELECTRÓNICO
456457458459460461462463464465466467468469470471472473474475476477478479480481482483484485486487488489490491492493494495496497498499500

# Pag. 20

MODELO 347 REGISTRO DE TIPO 2 REGISTRO DE DECLARADO
2 3 4 7
1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60 61 62 63 64 65
D
66 67 68 69 70 71 72 73 74 75 76 77 78 79 80 81 82 83 84 85 86 87 88 89 90 91 92 93 94 95 96 97 98 99 100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130
SIAP
ORUGES
.REPO
IDENTIFICACIÓN DECLARANTE
N.I.F. DECLARADO N.I.F. REPRESENTANTE LEGAL
O
CI
CI
R
E
J
E
ORTSIGER
ED
OPIT
APELLIDOS Y NOMBRE, RAZÓN SOCIAL O DENOMINACIÓN DEL DECLARADO
MODELO EJERCICIO N.I.F. DECLARANTE
NÓICAREPO
EVALC
IMPORTE DE LAS OPERACIONES
LACOL
.DNERRA
IMPORTE PERCIBIDO EN METALICO
L
A M ENTERA CI
E
D
AICNIVORP L
A M CI
E
D
OICICREJE
IMPORTE RECIBIDO POR TRANSMISIONES DE INMUEBLES SUJETAS A IVA
ENTERA
AJOH
ED
OPIT
CODIGO PROVINCIA PAIS
O
CI
CI
R
E
J
E
131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195
196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260

# Pag. 21

MODELO 347 REGISTRO DE TIPO 2 REGISTRO DE DECLARADO
261262263264265266267268269270271272273274275276277278279280281282283284285286287288289290291292293294295296297298299300301302303304305306307308309310311312313314315316317318319320321322323324325
326327328329330331332333334335336337338339340341342343344345346347348349350351352353354355356357358359360361362363364365366367368369370371372373374375376377378379380381382383384385386387388389390
391392393394395396397398399400401402403404405406407408409410411412413414415416417418419420421422423424425426427428429430431432433434435436437438439440441442443444445446447448449450451452453454455
456457458459460461462463464465466467468469470471472473474475476477478479480481482483484485486487488489490491492493494495496497498499500

# Pag. 22

MODELO 347 REGISTRO DE TIPO 2 REGISTRO DE INMUEBLE
IDENTIFICACIÓN DECLARANTE
N.I.F. ARRENDATARIO N.I.F. REPRESENTANTE LEGAL APELLIDOS Y NOMBRE, RAZÓN SOCIAL O DENOMINACIÓN DEL ARRENDATARIO
MODELO EJERCICIO N.I.F. DECLARANTE
2 3 4 7
1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60 61 62 63 64 65
L REFERENCIA CATASTRAL
A M
ENTERA CI
E D
I
66 67 68 69 70 71 72 73 74 75 76 77 78 79 80 81 82 83 84 85 86 87 88 89 90 91 92 93 94 95 96 97 98 99 100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130
131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195
196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260
ORTSIGER
ED
OPIT
TIPO DE VÍA
DIRECCIÓN DEL IMNUEBLE
A
R
L E PLANTA A O PISO
C
S
E
AJOH
ED
OPIT
E
IMPORTE DE LA OPERACIÓN B L
E
U
M
N
I C.
A
U T SI
DIRECCIÓN DEL INMUEBLE
REFERENCIA CATASTRAL
NOMBRE DE LA VÍA PÚBLICA
COMPLEMENTO OPIT
NÓICAREMUN
NÚMERO DE CALIFIC. BLOQUE PORTAL PUERTA CASA NÚMERO

# Pag. 23

MODELO 347 REGISTRO DE TIPO 2 REGISTRO DE INMUEBLE
DIRECCIÓN DEL INMUEBLE
LOCALIDAD O POBLACIÓN
261262263264265266267268269270271272273274275276277278279280281282283284285286287288289290291292293294295296297298299300301302303304305306307308309310311312313314315316317318319320321322323324325
326327328329330331332333334335336337338339340341342343344345346347348349350351352353354355356357358359360361362363364365366367368369370371372373374375376377378379380381382383384385386387388389390
391392393394395396397398399400401402403404405406407408409410411412413414415416417418419420421422423424425426427428429430431432433434435436437438439440441442443444445446447448449450451452453454455
456457458459460461462463464465466467468469470471472473474475476477478479480481482483484485486487488489490491492493494495496497498499500
OGIDOC
AICNIVORP
MUNICIPIO CÓD. MUNICIPIO
CODIGO POSTAL