# Pag. 1

ANEXO
DISEÑOS LÓGICOS A LOS QUE DEBEN AJUSTARSE LOS ARCHIVOS QUE SE GENEREN PARA
LA PRESENTACIÓN TELEMÁTICA DEL MODELO 349.
DISEÑOS LÓGICOS
DESCRIPCIÓN DE LOS REGISTROS
Para cada declarante se incluirán dos tipos diferentes de registro, que se distinguen por la
primera posición, con arreglo a los siguientes criterios:
• Tipo 1: Registro del declarante: Datos identificativos y hoja resumen de la declaración.
Diseño de tipo de registro 1 de los recogidos más adelante en estos mismos apartados y
Anexo de la presente orden.
• Tipo 2: Registro de operador intracomunitario y Registro de rectificaciones. Diseño de tipo
de registro 2 de los recogidos más adelante en estos mismos apartados y Anexo de la
presente orden.
El orden de presentación será el del tipo de registro, existiendo un único registro del tipo 1 y
tantos registros del tipo 2 como operadores intracomunitarios y rectificaciones tenga la
declaración, siendo diferentes los de operadores intracomunitarios y los de rectificaciones.
Todos los campos alfanuméricos y alfabéticos se presentarán alineados a la izquierda y rellenos
de blancos por la derecha, en mayúsculas sin caracteres especiales, y sin vocales acentuadas.
Para los caracteres específicos del idioma se utilizará la codificación ISO-8859-1. De esta forma
la letra “Ñ” tendrá el valor ASCII 209 (Hex. D1) y la “Ç”(cedilla mayúscula) el valor ASCII 199
(Hex. C7).
Todos los campos numéricos se presentarán alineados a la derecha y rellenos a ceros por la
izquierda sin signos y sin empaquetar.
Todos los campos tendrán contenido, a no ser que se especifique lo contrario en la descripción
del campo. Si no lo tuvieran, los campos numéricos se rellenarán a ceros y tanto los
alfanuméricos como los alfabéticos a blancos.
8

# Pag. 2

MODELO 349
A.- TIPO DE REGISTRO 1: REGISTRO DE DECLARANTE.
(POSICIONES, NATURALEZA Y DESCRIPCIÓN DE LOS CAMPOS)
POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS
1 Numérico TIPO DE REGISTRO
Constante número '1'.
2-4 Numérico MODELO DECLARACIÓN
Constante '349'.
5-8 Numérico EJERCICIO
Las cuatro cifras del ejercicio fiscal al que corresponde la declaración.
9-17 Alfanumérico NIF DEL DECLARANTE
Se consignará el NIF del declarante.
Este campo deberá estar ajustado a la derecha, siendo la última
posición el carácter de control y rellenando con ceros las posiciones
de la izquierda, de acuerdo con las reglas previstas en el Reglamento
General de las actuaciones y los procedimientos de gestión e
inspección tributaria y de desarrollo de las normas comunes de los
procedimientos de aplicación de los tributos, aprobado por el Real
Decreto 1065/2007 de 27 de Julio (BOE del 5 de septiembre).
18-57 Alfanumérico APELLIDOS Y NOMBRE O RAZÓN SOCIAL DEL DECLARANTE
Si es una persona física se consignará el primer apellido, un espacio,
el segundo apellido, un espacio y el nombre completo,
necesariamente en este orden.
Para personas jurídicas y entidades en régimen de atribución de
rentas, se consignará la razón social completa, sin anagrama.
En ningún caso podrá figurar en este campo un nombre comercial.
58 BLANCO
59-107 Alfanumérico PERSONA CON QUIÉN RELACIONARSE
Datos de la persona con quién relacionarse. Este campo se subdivide
en dos:
59-67 TELÉFONO: Campo numérico de 9 posiciones.
68-107 APELLIDOS Y NOMBRE: Se consignará el primer
apellido, un espacio, el segundo apellido, un espacio y el
nombre completo, necesariamente en este orden.
9

# Pag. 3

108-120 Numérico NUMERO IDENTIFICATIVO DE LA DECLARACION
Se consignará el número identificativo correspondiente a la
declaración. Campo de contenido numérico de 13 posiciones.
El número identificativo que habrá de figurar, será un número
secuencial cuyos tres primeros dígitos se corresponderán con el
código 349.
121-122 Alfabético DECLARACION COMPLEMENTARIA O SUSTITUTIVA
En el caso excepcional de segunda o posterior presentación de
declaraciones, deberá cumplimentarse obligatoriamente uno de los
siguientes campos:
121 DECLARACIÓN COMPLEMENTARIA: Se consignará una “C” si
la presentación de esta declaración tiene por objeto incluir registros
que, debiendo haber figurado en otra declaración del mismo ejercicio
presentada anteriormente, hubieran sido completamente omitidas en
la misma.
La presentación de una declaración complementaria que tenga por
objeto la modificación del contenido de datos declarados en otra
declaración del mismo ejercicio presentada anteriormente se realizará
desde el servicio de consulta y modificación de declaraciones
informativas en la Oficina Virtual de la Agencia Tributaria
(www.agenciatributaria.es).
122 DECLARACIÓN SUSTITUTIVA: Se consignará una “S” si la
presentación tiene como objeto anular y sustituir completamente a
otra declaración anterior, del mismo ejercicio. Una declaración
sustitutiva sólo puede anular a una única declaración anterior.
123-135 Numérico NUMERO IDENTIFICATIVO DE LA DECLARACIÓN ANTERIOR
En el caso de que se haya consignado una “C” en el campo
“Declaración complementaria” o en el caso de que se haya
consignado “S” en el campo “Declaración sustitutiva”, se consignará
el número identificativo correspondiente a la declaración a la que
sustituye.
Campo de contenido numérico de 13 posiciones.
En cualquier otro caso deberá rellenarse a CEROS.
136-137 Alfanumérico PERÍODO
Se hará constar el periodo al que corresponda la declaración.
Se consignará el que corresponda según la siguiente relación de
claves:
“01” - Enero
“02” - Febrero
“03” - Marzo
“04” - Abril
“05” - Mayo
“06” - Junio
“07” - Julio
10

# Pag. 4

“08” - Agosto
“09” - Septiembre
“10” - Octubre
“11” - Noviembre
“12” - Diciembre
"1T" - Primer trimestre
"2T" - Segundo trimestre
"3T" - Tercer trimestre
"4T" - Cuarto trimestre
138-146 Numérico NÚMERO TOTAL DE OPERADORES INTRACOMUNITARIOS
Deberá consignar el número total de sujetos pasivos a los que se
hayan efectuado entregas intracomunitarias exentas, entregas en
otros Estados miembros subsiguientes a adquisiciones
intracomunitarias exentas en el marco de operaciones triangulares,
adquisiciones intracomunitarias sujetas, prestaciones
intracomunitarias de servicios, adquisiciones intracomunitarias de
servicios, transferencias de bienes, devoluciones de bienes y
sustituciones del empresario o profesional destinatario de los
bienes transferidos en el marco de un acuerdo de ventas de bienes
en consigna, declarados para este declarante que figuren en el
registro de operador intracomunitario (registro de tipo 2).
(Número de registros de operador intracomunitario (registro de tipo
2) con clave de operación, posición 133, igual a “E”, “M”, “H”, “T”,
“A”, “S”, “I”, “R”, “D” o “C”.)
147-161 Numérico IMPORTE DE LAS OPERACIONES INTRACOMUNITARIAS
Numérico de 15 posiciones.
Deberá consignar la suma total de las bases imponibles que
correspondan a entregas intracomunitarias exentas, entregas en
otros Estados miembros, subsiguientes a adquisiciones
intracomunitarias exentas en el marco de operaciones triangulares,
adquisiciones intracomunitarias sujetas, prestaciones
intracomunitarias de servicios, adquisiciones intracomunitarias de
servicios, así como del valor de las transferencias, devoluciones y
sustituciones del empresario o profesional destinatario de los
bienes transferidos efectuadas en el marco de un acuerdo de
ventas de bienes en consigna.
(Suma de Bases Imponibles e importes, posiciones 134-146, de los
registros de operador intracomunitario (registro de tipo 2) y clave de
operación, posición 133, igual a “E”, “M”, “H”, “T”, “A”, “S”, “I”, “R”,
“D” o “C”).
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
147-159 Parte entera del importe de las operaciones
intracomunitarias, si no tiene contenido se consignará a ceros.
160-161 Parte decimal del importe de las operaciones
intracomunitarias, si no tiene contenido se consignará a ceros.
11

# Pag. 5

162-170 Numérico NÚMERO TOTAL DE OPERADORES INTRACOMUNITARIOS
CON RECTIFICACIONES
Deberá consignar el número total de registros de rectificaciones de
entregas intracomunitarias exentas, de entregas en otros Estados
miembros subsiguientes a adquisiciones intracomunitarias exentas
en el marco de operaciones triangulares, de adquisiciones
intracomunitarias sujetas, prestaciones intracomunitarias de
servicios, adquisiciones intracomunitarias de servicios, así como
también las transferencias y, devoluciones de bienes o
sustituciones del empresario o profesional destinatario de los
bienes transferidos efectuadas en el marco de un acuerdo de
ventas de bienes en consigna, declarados para este declarante que
figuren en el registro de rectificaciones (registro de tipo 2).
(Número de registros de rectificaciones (registro de tipo 2) con
clave de operación, posición 133, igual a “E”, “M”, “H”, “T”, “A”, “S”,
“I”, “R”, “D” o “C”.
171-185 Numérico IMPORTE DE LAS RECTIFICACIONES
Deberá consignar la suma total de las bases imponibles rectificadas
que correspondan a las entregas intracomunitarias exentas,
entregas en otros Estados miembros, subsiguientes a adquisiciones
intracomunitarias exentas en el marco de operaciones triangulares,
a adquisiciones intracomunitarias sujetas, a prestaciones
intracomunitarias de servicios, a adquisiciones intracomunitarias de
servicios, así como del valor las transferencias y devoluciones de
bienes, o sustituciones del empresario o profesional destinatario de
los bienes transferidos efectuadas en el marco de un acuerdo de
ventas de bienes en consigna, y efectuadas por la totalidad de
sujetos pasivos mencionados en el apartado anterior.
(Suma de Bases Imponibles Rectificadas, posiciones 153-165, de
los registros de rectificaciones (registro de tipo 2) y clave de
operación, posición 133, igual a “E”, “M”, “H”, “T”, “A”, “S”, “I”, “R”,
“D” o “C”.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
171-183 Parte entera del importe de las bases imponibles
rectificadas, si no tiene contenido se consignará a ceros.
184-185 Parte decimal del importe de las bases imponibles
rectificadas, si no tiene contenido se consignará a ceros.
186 Alfabético INDICADOR CAMBIO PERIODICIDAD EN LA OBLIGACIÓN DE
DECLARAR
En caso de que el importe total de las entregas de bienes y
prestaciones de servicio superen los 50.000 euros en el segundo
mes de cada trimestre (Febrero, Mayo, Agosto, Noviembre) deberá
presentarse una declaración mensual por ese período en la que se
incluirán las operaciones correspondientes a ese mes (segundo
mes del trimestre) y al anterior (primer mes del trimestre)
12

# Pag. 6

Se consignará el valor que corresponda según la siguiente relación:
X: Si se corresponde con una declaración mensual con operaciones
correspondientes a los dos primeros meses del trimestre
Blanco: En cualquier otro caso.
187-390 -------------- BLANCOS
391-399 Alfanumérico NIF DEL REPRESENTANTE LEGAL.
Si el declarante es menor de 14 años se consignará en este campo
el número de identificación fiscal de su representante legal (padre,
madre o tutor). Este campo deberá estar ajustado a la derecha,
siendo la última posición el carácter de control y rellenando con
ceros las posiciones a la izquierda.
En cualquier otro caso el contenido de este campo se rellenará a
espacios.
400 - 500 ------------ BLANCOS
* Todos los importes serán positivos.
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a blancos.
* Todos los campos numéricos ajustados a la derecha y rellenos de ceros por la izquierda.
* Todos los campos alfanuméricos/alfabéticos ajustados a la izquierda y rellenos de blancos por la derecha,
en mayúsculas, sin caracteres especiales y sin vocales acentuadas, excepto que se especifique lo contrario
en la descripción del campo.
13

# Pag. 7

MODELO 349
TIPO DE REGISTRO 2: REGISTRO DE OPERADOR INTRACOMUNITARIO.
(POSICIONES, NATURALEZA Y DESCRIPCIÓN DE LOS CAMPOS)
POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS
1 Numérico TIPO DE REGISTRO
Numérico de una posición
Constante "2" (Dos)
2-4 Numérico MODELO DECLARACIÓN
Numérico de 3 posiciones
Constante "349"
5-8 Numérico EJERCICIO
Numérico de 4 posiciones
Consignar lo contenido en estas mismas posiciones del registro de
tipo 1.
9-17 Alfanumérico NIF DEL DECLARANTE
Alfanumérico de 9 posiciones
Consignar lo contenido en estas mismas posiciones del registro de
tipo 1.
18-75 Alfanumérico BLANCOS
76-92 Alfanumérico NIF OPERADOR COMUNITARIO
Alfanumérico de 17 posiciones
Se compone de los subcampos:
76-77 Código país
Alfabético de 2 posiciones
Se compone de las dos primeras letras identificativas del
Estado miembro de la UE.
78-92 Número
Alfanumérico de 15 posiciones
Campo alfanumérico, que se ajustará a la izquierda y se
rellenará con blancos a la derecha en los casos en que
dicho número tenga menos de 15 posiciones.
14

# Pag. 8

Composición del NIF comunitario de los distintos Estados
miembros:
Debe tenerse en cuenta la composición del NIF aplicable a cada
uno de los Estados miembros de la UE, a efectos de la declaración
recapitulativa de operaciones intracomunitarias, modelo 349.
País Código país Número
Alemania DE 9 caracteres numéricos
Austria AT 9 caracteres alfanuméricos
Bélgica BE 10 caracteres numéricos
Bulgaria BG 9 ó 10 caracteres numéricos
Chipre CY 9 caracteres alfanuméricos
Croacia HR 11 caracteres numéricos
Dinamarca DK 8 caracteres numéricos
Eslovenia SI 8 caracteres numéricos
Estonia EE 9 caracteres numéricos
Finlandia FI 8 caracteres numéricos
Francia FR 11 caracteres alfanuméricos
Grecia EL 9 caracteres numéricos
Reino Unido GB 5, 9 ó 12 caracteres alfanuméricos
Países Bajos NL 12 caracteres alfanuméricos
Hungría HU 8 caracteres numéricos
Italia IT 11 caracteres numéricos
Irlanda IE 8 ó 9 caracteres alfanuméricos
Letonia LV 11 caracteres numéricos
Lituania LT 9 ó 12 caracteres numéricos
Luxemburgo LU 8 caracteres numéricos
Malta MT 8 caracteres numéricos
Polonia PL 10 caracteres numéricos
Portugal PT 9 caracteres numéricos
República Checa CZ 8, 9 ó 10 caracteres numéricos
República Eslovaca SK 10 caracteres numéricos
Rumanía RO de 2 a 10 caracteres numéricos
Suecia SE 12 caracteres numéricos
93-132 Alfanumérico APELLIDOS Y NOMBRE O RAZÓN SOCIAL DEL OPERADOR
INTRACOMUNITARIO
Alfanumérico de 40 posiciones
Se cumplimentará con el mismo criterio que el especificado para el
declarante en el registro de tipo 1.
133 Alfabético CLAVE DE OPERACIÓN
Alfabético de una posición
Se consignará la que corresponda según la siguiente relación:
E: Entregas intracomunitarias exentas, excepto las entregas en
otros Estados miembros subsiguientes a adquisiciones
intracomunitarias exentas en el marco de operaciones triangulares,
que se consignará "T", y las entregas intracomunitarias de bienes
15

# Pag. 9

posteriores a una importación exenta, que se consignarán con las
claves “M” o “H” según corresponda.
M: Entregas intracomunitarias de bienes posteriores a una
importación exenta, de acuerdo con el artículo 27. 12º de la Ley del
Impuesto sobre el Valor Añadido.
H: Entregas intracomunitarias de bienes posteriores a una
importación exenta, de acuerdo con el artículo 27. 12º de la Ley del
Impuesto sobre el Valor Añadido, efectuadas por el representante
fiscal según lo previsto en el artículo 86.Tres de la Ley del
Impuesto.
A: Adquisiciones intracomunitarias sujetas.
T: Entregas en otros Estados miembros subsiguientes a
adquisiciones intracomunitarias exentas en el marco de
operaciones triangulares. Cuando se realice alguna entrega de
bienes de las mencionadas en el artículo 79, apartado cinco del
Reglamento del IVA.
Estas operaciones, cuando sean efectuadas para un destinatario
para el cual se hayan realizado entregas intracomunitarias, se
consignarán en un registro independiente de aquél en que se hayan
consignado estas últimas operaciones.
S: Prestaciones intracomunitarias de servicios realizadas por el
declarante.
I: Adquisiciones intracomunitarias de servicios localizadas en el TAI
prestadas por empresarios o profesionales establecidos en otros
EM cuyo destinatario es el declarante.
R: Transferencias de bienes efectuadas en el marco de acuerdos
de ventas de bienes en consigna.
D: Devoluciones de bienes desde otro Estado miembro al que
previamente fueron enviados desde el TAI en el marco de acuerdos
de ventas de bienes en consigna.
C: Sustituciones del empresario o profesional destinatario de los
bienes expedidos o transportados a otro Estado miembro en el
marco de acuerdos de ventas de bienes en consigna.
134-146 Numérico BASE IMPONIBLE O IMPORTE
Numérico de 13 posiciones
Se hará constar el importe total de la Base Imponible del conjunto
de las entregas intracomunitarias exentas, si se ha consignado
clave de operación E, del conjunto de las entregas
intracomunitarias de bienes posteriores a una importación exenta, si
ha consignado la clave de operación M, del conjunto de las
entregas intracomunitarias de bienes posteriores a una importación
exenta, efectuadas por el representante fiscal en nombre y por
cuenta del importador, si ha consignado la clave de operación H,
del conjunto de las adquisiciones intracomunitarias sujetas, si se ha
consignado clave de operación A, del conjunto de las entregas en
otros Estados miembros subsiguientes a adquisiciones
intracomunitarias exentas en el marco de operaciones triangulares,
si se ha consignado clave de operación T, del conjunto de
prestaciones intracomunitarias de servicios realizadas si se ha
consignado clave de operación S, del conjunto de adquisiciones
intracomunitarias de servicios si se ha consignado clave de
operación I, el valor del conjunto de transferencias de bienes
efectuadas en el marco de acuerdos de ventas de bienes en
16

# Pag. 10

consigna si se ha consignado la clave R, el valor del conjunto de
devoluciones de bienes desde otro Estado miembro al que
previamente fueros enviados desde el TAI en el marco de acuerdos
de ventas de bienes en consigna si se ha consignado clave de
operación D, o el valor del conjunto de sustituciones del sujeto
pasivo destinatario de los bienes expedidos o transportados a otro
Estado miembro en el marco de acuerdos de ventas de bienes en
consigna si se ha consignado clave de operación C para cada
operador intracomunitario. Por lo tanto, si en un mismo periodo se
han realizado varias operaciones con un operador intracomunitario,
éstas deberán acumularse por clave de operación con el fin de
consignar un único registro por cada clave de operación y periodo.
En cuanto a las operaciones triangulares, también deberán
acumularse por operador intracomunitario y periodo, no obstante se
consignarán en un registro independiente de aquellas operaciones
distintas de éstas.
Se consignarán las operaciones mencionadas en los artículos 79 y
80 del Reglamento del IVA.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
134-144 Parte entera del importe de las entregas, si no tiene
contenido se consignará a ceros.
145-146 Parte decimal del importe de las entregas, si no tiene
contenido se consignará a ceros.
147-178 -------------- BLANCOS
179-195 Alfanumérico NIF EMPRESARIO O PROFESIONAL DESTINATARIO FINAL
SUSTITUTO (Sólo se cumplimentará en caso de clave C en tipo
de operación)
Alfanumérico de 17 posiciones
Se compone de los subcampos:
179-180 Código país
Alfabético de 2 posiciones
Se compone de las dos primeras letras identificativas del
Estado miembro de la UE.
Deben referirse al mismo Estado miembro que el
indicado en el operador al que se sustituye.
181-195 Número
Alfanumérico de 15 posiciones
Campo alfanumérico, que se ajustará a la izquierda y se
rellenará con blancos a la derecha en los casos en que
dicho número tenga menos de 15 posiciones.
17

# Pag. 11

Composición del NIF comunitario de los distintos Estados
miembros:
Debe tenerse en cuenta la composición del NIF aplicable a cada
uno de los Estados miembros de la UE, a efectos de la declaración
recapitulativa de operaciones intracomunitarias, modelo 349.
País Código país Número
Alemania DE 9 caracteres numéricos
Austria AT 9 caracteres alfanuméricos
Bélgica BE 10 caracteres numéricos
Bulgaria BG 9 ó 10 caracteres numéricos
Chipre CY 9 caracteres alfanuméricos
Croacia HR 11 caracteres numéricos
Dinamarca DK 8 caracteres numéricos
Eslovenia SI 8 caracteres numéricos
Estonia EE 9 caracteres numéricos
Finlandia FI 8 caracteres numéricos
Francia FR 11 caracteres alfanuméricos
Grecia EL 9 caracteres numéricos
Reino Unido GB 5, 9 ó 12 caracteres alfanuméricos
Países Bajos NL 12 caracteres alfanuméricos
Hungría HU 8 caracteres numéricos
Italia IT 11 caracteres numéricos
Irlanda IE 8 ó 9 caracteres alfanuméricos
Letonia LV 11 caracteres numéricos
Lituania LT 9 ó 12 caracteres numéricos
Luxemburgo LU 8 caracteres numéricos
Malta MT 8 caracteres numéricos
Polonia PL 10 caracteres numéricos
Portugal PT 9 caracteres numéricos
República Checa CZ 8, 9 ó 10 caracteres numéricos
República Eslovaca SK 10 caracteres numéricos
Rumanía RO de 2 a 10 caracteres numéricos
Suecia SE 12 caracteres numéricos
196-235 Alfanumérico APELLIDOS Y NOMBRE O RAZÓN SOCIAL DEL SUJETO
PASIVO SUSTITUTO. (Sólo se cumplimentará en caso de clave
C en tipo de operación)
Alfanumérico de 40 posiciones
Se cumplimentará con el mismo criterio que el especificado para el
declarante en el registro de tipo 1.
236 500 -------------- BLANCOS
* Todos los importes serán positivos.
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a blancos.
* Todos los campos numéricos ajustados a la derecha y rellenos de ceros por la izquierda, sin signos, sin
empaquetar y sin decimales.
* Todos los campos alfanuméricos/alfabéticos ajustados a la izquierda y rellenos de blancos por la derecha,
excepto que se especifique lo contrario en la descripción del campo.
18

# Pag. 12

TIPO DE REGISTRO 2: REGISTRO DE RETIFICACIONES.
(POSICIONES, NATURALEZA Y DESCRIPCIÓN DE LOS CAMPOS)
POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS
1 Numérico TIPO DE REGISTRO
Numérico de una posición
Constante "2" (Dos)
2-4 Numérico MODELO DECLARACIÓN
Numérico de 3 posiciones
Constante "349"
5-8 Numérico EJERCICIO
Numérico de 4 posiciones
Consignar lo contenido en estas mismas posiciones del registro de
tipo 1.
9-17 Alfanumérico NIF DEL DECLARANTE
Alfanumérico de 9 posiciones
Consignar lo contenido en estas mismas posiciones del registro de
tipo 1.
18-75 Alfanumérico BLANCOS
76-92 Alfanumérico NIF OPERADOR COMUNITARIO
Alfanumérico de 17 posiciones
Se compone de los subcampos:
76-77 Código país:
Alfabético de 2 posiciones
Se compone de las dos primeras letras identificativas del
Estado miembro de la UE.
78-92 Número:
Alfanumérico de 15 posiciones
Campo alfanumérico, que se ajustará a la izquierda y se
rellenará con blancos a la derecha en los casos en que
dicho número tenga menos de 15 posiciones.
Composición del NIF comunitario de los distintos Estados
miembros:
Debe tenerse en cuenta la composición del NIF aplicable a cada
uno de los Estados miembros de la UE, a efectos de la declaración
recapitulativa de operaciones intracomunitarias, modelo 349.
19

# Pag. 13

País Código país Número
Alemania DE 9 caracteres numéricos
Austria AT 9 caracteres alfanuméricos
Bélgica BE 10 caracteres numéricos
Bulgaria BG 9 ó 10 caracteres numéricos
Chipre CY 9 caracteres alfanuméricos
Croacia HR 11 caracteres numéricos
Dinamarca DK 8 caracteres numéricos
Eslovenia SI 8 caracteres numéricos
Estonia EE 9 caracteres numéricos
Finlandia FI 8 caracteres numéricos
Francia FR 11 caracteres alfanuméricos
Grecia EL 9 caracteres numéricos
Reino Unido GB 5, 9 ó 12 caracteres alfanuméricos
Países Bajos NL NL 12 caracteres alfanuméricos
Hungría HU 8 caracteres numéricos
Italia IT 11 caracteres numéricos
Irlanda IE 8 ó 9 caracteres alfanuméricos
Letonia LV 11 caracteres numéricos
Lituania LT 9 ó 12 caracteres numéricos
Luxemburgo LU 8 caracteres numéricos
Malta MT 8 caracteres numéricos
Polonia PL 10 caracteres numéricos
Portugal PT 9 caracteres numéricos
República Checa CZ 8, 9 ó 10 caracteres numéricos
República Eslovaca SK 10 caracteres numéricos
Rumanía RO de 2 a 10 caracteres numéricos
Suecia SE 12 caracteres numéricos
93-132 Alfanumérico APELLIDOS Y NOMBRE O RAZÓN SOCIAL DEL OPERADOR
INTRACOMUNITARIO
Alfanumérico de 40 posiciones
Se cumplimentará con el mismo criterio que el especificado para el
declarante en el registro de tipo 1.
133 Alfabético CLAVE DE OPERACIÓN
Alfabético de una posición
Se consignará la que corresponda según la siguiente relación:
E: Rectificaciones de las entregas intracomunitarias exentas,
excepto las que deban consignarse, según corresponda, con las
claves T, M ó H.
M: Rectificaciones de las entregas intracomunitarias de bienes
posteriores a una importación exenta, de acuerdo con el artículo
27.12º de la Ley del Impuesto sobre el Valor Añadido.
H: Rectificaciones de las entregas intracomunitarias de bienes
posteriores a una importación exenta efectuadas por el
representante fiscal, de acuerdo con el artículo 27. 12º de la Ley del
Impuesto sobre el Valor Añadido, efectuadas por el representante
fiscal según lo previsto en el artículo 86.Tres de la Ley del Impuesto
A: Rectificaciones a las adquisiciones intracomunitarias sujetas.
T: Rectificaciones a las entregas en otros Estados miembros
subsiguientes a adquisiciones intracomunitarias exentas en el
marco de operaciones triangulares. Cuando se realice alguna
20

# Pag. 14

entrega de bienes de las mencionadas en el artículo 79, apartado
cinco del Reglamento del IVA.
Estas operaciones, cuando sean efectuadas para un destinatario
para el cual se hayan realizado entregas intracomunitarias, se
consignarán en un registro independiente de aquél en que se hayan
consignado estas últimas operaciones.
S: Rectificaciones a las prestaciones intracomunitarias de servicios
realizadas por el declarante.
I: Rectificaciones a las adquisiciones intracomunitarias de servicios
localizadas en el TAI prestadas por empresarios o profesionales
establecidos en otros EM cuyo destinatario es el declarante.
R: Rectificaciones de transferencias de bienes efectuadas en el
marco de acuerdos de ventas de bienes en consigna.
D: Rectificaciones de devoluciones de bienes desde otro Estado
miembro al que previamente fueron enviados desde el TAI en el
marco de acuerdos de ventas de bienes en consigna.
C: Rectificaciones de sustituciones del empresario o profesional
destinatario de los bienes expedidos o transportados a otro Estado
miembro en el marco de acuerdos de ventas de bienes en
consigna.
134-146 ---------------- BLANCOS
147-178 Alfanumérico RECTIFICACIONES
Estos campos se cumplimentarán cuando se hayan producido
circunstancias que supongan errores o rectificaciones de las bases
consignadas en declaraciones anteriores. La rectificación se incluirá
en el periodo en que se hubiera notificado tal modificación al
destinatario de los bienes. Por tanto, este campo se rellenará
únicamente si la operación que se consigna es una rectificación a
una entrega, adquisición intracomunitaria, operación triangular,
prestación intracomunitaria de servicios, adquisición
intracomunitaria de servicios, transferencias, devoluciones de
bienes o sustituciones del empresario o profesional destinatario de
los bienes transferidos efectuadas en el marco de un acuerdo de
ventas de bienes en consigna.
Se compone de los siguientes subcampos:
147-150 Ejercicio
Numérico de 4 posiciones
Las cuatro cifras del ejercicio fiscal al que corresponde la
declaración que se corrige.
151-152 Periodo
Alfanumérico de 2 posiciones
Periodo al que corresponde la declaración que se corrige,
codificado con las siguientes claves:
“01” - Enero
“02” - Febrero
“03” - Marzo
“04” - Abril
“05” - Mayo
21

# Pag. 15

“06” - Junio
“07” - Julio
“08” - Agosto
“09” - Septiembre
“10” - Octubre
“11” - Noviembre
“12” - Diciembre
"1T" - Primer trimestre
"2T" - Segundo trimestre
"3T" - Tercer trimestre
"4T" - Cuarto trimestre
“0A” - Periodicidad anual
153-165 Numérico BASE IMPONIBLE O IMPORTES RECTIFICADOS
Numérico de 13 posiciones.
Se consignará el nuevo importe total de la Base Imponible de las
entregas intracomunitarias exentas, si se ha consignado clave de
operación E, de las entregas intracomunitarias de bienes
posteriores a una importación exenta, si ha consignado la clave de
operación M, de las entregas intracomunitarias de bienes
posteriores a una importación exenta, efectuadas por el
representante fiscal en nombre y por cuenta del importador, si ha
consignado la clave de operación H, de las adquisiciones
intracomunitarias sujetas, si se ha consignado clave de operación
A, de las entregas en otros Estados miembros subsiguientes a
adquisiciones intracomunitarias exentas en el marco de
operaciones triangulares, si se ha consignado clave de operación T,
de las prestaciones intracomunitarias de servicios realizadas si se
ha consignado clave de operación S, del conjunto de adquisiciones
intracomunitarias de servicios si se ha consignado clave de
operación I, el nuevo valor de las transferencias de bienes, si se ha
consignado la clave de operación R , el nuevo valor de las
devoluciones de bienes, si se ha consignado la clave de operación
D, y el nuevo valor de las sustituciones del sujeto pasivo, si se ha
consignado la clave de operación C que corresponda al operador
intracomunitario y al periodo indicado, una vez modificado el
importe de la Base imponible o el valor de la operación que se
desea rectificar. Por lo tanto, si en un mismo periodo se han
realizado varias operaciones con un operador intracomunitario y en
una o varias de ellas se quiere rectificar la base imponible o el valor
que se declaró, se acumularán en un único registro, por clave de
operación y periodo, el total de bases imponibles o valores de todas
las operaciones una vez rectificadas las bases imponibles o valores
que correspondan.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
153-163 Parte entera del importe de la base imponible
rectificada, si no tiene contenido se consignará a ceros.
164-165 Parte decimal del importe de la base imponible
rectificada, si no tiene contenido se consignará a ceros.
22

# Pag. 16

166-178 Numérico BASE IMPONIBLE DECLARADA ANTERIORMENTE
Numérico de 13 posiciones
Importe de la Base imponible o del valor de la operación que se
consignó en la declaración que se corrige.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
166-176 Parte entera del importe de la base imponible declarada
anteriormente, si no tiene contenido se consignará a
ceros.
177-178 Parte decimal del importe de la base imponible declarada
anteriormente, si no tiene contenido se consignará a
ceros.
179-195 Alfanumérico NIF EMPRESARIO O PROFESIONAL DESTINATARIO FINAL
SUSTITUTO (Sólo se cumplimentará en caso de clave C en tipo
de operación).
Alfanumérico de 17 posiciones
Se compone de los subcampos:
179-180 Código país
Alfabético de 2 posiciones
Se compone de las dos primeras letras identificativas del
Estado miembro de la UE.
Deben referirse al mismo Estado miembro que el
indicado en el operador al que se sustituye.
181-195 Número
Alfanumérico de 15 posiciones
Campo alfanumérico, que se ajustará a la izquierda y se
rellenará con blancos a la derecha en los casos en que
dicho número tenga menos de 15 posiciones.
Composición del NIF comunitario de los distintos Estados
miembros:
Debe tenerse en cuenta la composición del NIF aplicable a cada
uno de los Estados miembros de la UE, a efectos de la declaración
recapitulativa de operaciones intracomunitarias, modelo 349.
País Código país Número
Alemania DE 9 caracteres numéricos
Austria AT 9 caracteres alfanuméricos
Bélgica BE 10 caracteres numéricos
Bulgaria BG 9 ó 10 caracteres numéricos
Chipre CY 9 caracteres alfanuméricos
Croacia HR 11 caracteres numéricos
Dinamarca DK 8 caracteres numéricos
Eslovenia SI 8 caracteres numéricos
Estonia EE 9 caracteres numéricos
23

# Pag. 17

Finlandia FI 8 caracteres numéricos
Francia FR 11 caracteres alfanuméricos
Grecia EL 9 caracteres numéricos
Reino Unido GB 5, 9 ó 12 caracteres alfanuméricos
Países Bajos NL 12 caracteres alfanuméricos
Hungría HU 8 caracteres numéricos
Italia IT 11 caracteres numéricos
Irlanda IE 8 ó 9 caracteres alfanuméricos
Letonia LV 11 caracteres numéricos
Lituania LT 9 ó 12 caracteres numéricos
Luxemburgo LU 8 caracteres numéricos
Malta MT 8 caracteres numéricos
Polonia PL 10 caracteres numéricos
Portugal PT 9 caracteres numéricos
República Checa CZ 8, 9 ó 10 caracteres numéricos
República Eslovaca SK 10 caracteres numéricos
Rumanía RO de 2 a 10 caracteres numéricos
Suecia SE 12 caracteres numéricos
196-235 Alfanumérico APELLIDOS Y NOMBRE O RAZÓN SOCIAL DEL SUJETO
PASIVO SUSTITUTO (Sólo se cumplimentará en caso de clave
C en tipo de operación)
Alfanumérico de 40 posiciones
Se cumplimentará con el mismo criterio que el especificado para el
declarante en el registro de tipo 1.
236-500 ---------------- BLANCOS
* Todos los importes serán positivos.
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a blancos.
* Todos los campos numéricos ajustados a la derecha y rellenos de ceros por la izquierda.
* Todos los campos alfanuméricos/alfabéticos ajustados a la izquierda y rellenos de blancos por la derecha,
excepto que se especifique lo contrario en la descripción del campo.
24