# Pag. 1

ANEXO
DISEÑOS FÍSICOS Y LÓGICOS A LOS QUE DEBEN AJUSTARSE LOS ARCHIVOS QUE SE
GENEREN PARA LA PRESENTACIÓN TELEMÁTICA DEL MODELO 720.
Dirección...
...
Tel.: ...
Fax: …
… @aeat.es

# Pag. 2

B) DISEÑOS LÓGICOS
DESCRIPCIÓN DE LOS REGISTROS
Para cada declarante se incluirán dos tipos diferentes de registro, que se distinguen por la
primera posición, con arreglo a los siguientes criterios:
Tipo 1: Registro del declarante: Datos identificativos y resumen de la declaración. Diseño
de tipo de registro 1 de los recogidos más adelante en estos mismos apartados y Anexo de
la presente Orden.
Tipo 2: Registro de detalle. Diseño de tipo de registro 2 de los recogidos más adelante en
estos mismos apartados y Anexo de la presente Orden.
El orden de presentación será el del tipo de registro, existiendo un único registro del tipo 1 y
tantos registros del tipo 2 como bienes y derechos se reflejen en la declaración, pero teniendo
en cuenta que puede existir más de un registro para cada bien o derecho en función de la
distinta condición que pueda tener un mismo declarante y las distintas fechas de adquisición que
puedan existir.
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
11

# Pag. 3

MODELO 720. REGISTRO DE TIPO 1. REGISTRO DE DECLARANTE
1 7 2 0
1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60 61 62 63 64 65
66 67 68 69 70 71 72 73 74 75 76 77 78 79 80 81 82 83 84 85 86 87 88 89 90 91 92 93 94 95 96 97 98 99 100 101 102 103 104 105 106 107 108 109 110 111 112 113 114 115 116117118119120121122123124125126127128129130
SUMA TOTAL DE VALORACIÓN 1: SALDO O VALOR A 31 DE DICIEMBRE; SALDO O
VALOR EN LA FECHA DE EXTINCIÓN; VALOR DE ADQUISICIÓN
NUMERO TOTAL DE REGISTROS DE
DECLARADOS
131132 133 134 135136137138139140141142143144145146147148149150151152153154155156157158159160161 162 163 164 165 166 167 168 169 170 171 172 173 174 175 176 177 178 179 180 181182183184185186187188189190191192193194195
196197 198 199 200201202203204205206207208209210211212213214215216217218219220221222223224225226 227 228 229 230 231 232 233 234 235 236 237 238 239 240 241 242 243 244 245 246247248249250251252253254255256257258259260
ONGIS
IMPORTE
ENTERA
ORTSIGER
ED
OPIT
LAMICED
IDENTIFICACION DEL DECLARANTE
MODELO EJERCICIO N.I.F. DECLARANTE
CON QUIEN RELACIONARSE
APELLIDOS Y NOMBRE
ETROPOS
ED
OPIT
PERSONA
RAZÓN SOCIAL DEL DECLARANTE
TELEFONO
NUMERO IDENTIFICATIVO DE LA
DECLARACIÓN ANTERIOR
AIRATNEMELPMOC.CED
AVITUTITSUS.CED
NUMERO IDENTIFICATIVO DE LA DECLARACIÓN
SUMA TOTAL DE VALORACIÓN 2: IMPORTE O VALOR DE LA TRANSMISIÓN; SALDO MEDIO ÚLTIMO
TRIMESTRE
ONGIS
IMPORTE
ENTERA
LAMICED
12

# Pag. 4

MODELO 720. REGISTRO DE TIPO 1. REGISTRO DE DECLARANTE
261262 263 264 265266267268269270271272273274275276277278279280281282283284285286287288289290291 292 293 294 295 296 297 298 299 300 301 302 303 304 305 306 307 308 309 310 311312313314315316317318319320321322323324325
326327 328 329 330331332333334335336337338339340341342343344345346347348349350351352353354355356 357 358 359 360 361 362 363 364 365 366 367 368 369 370 371 372 373 374 375 376377378379380381382383384385386387388389390
391392 393 394 395396397398399400401402403404405406407408409410411412413414415416417418419420421 422 423 424 425 426 427 428 429 430 431 432 433 434 435 436 437 438 439 440 441442443444445446447448449450451452453454455
456457 458 459 460461462463464465466467468469470471472473474475476477478479480481482483484485486 487 488 489 490 491 492 493 494 495 496 497 498 499 500
13

# Pag. 5

MODELO 720
A.- TIPO DE REGISTRO 1: REGISTRO DE DECLARANTE.
(POSICIONES, NATURALEZA Y DESCRIPCIÓN DE LOS CAMPOS)
POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS
1 Numérico TIPO DE REGISTRO.
Constante número '1'.
2-4 Numérico MODELO DECLARACIÓN.
Constante ‘720’.
5-8 Numérico EJERCICIO.
Las cuatro cifras del ejercicio fiscal al que corresponde la
declaración.
9-17 Alfanumérico N.I.F. DEL DECLARANTE.
Se consignará el N.I.F. del declarante.
Este campo deberá estar ajustado a la derecha, siendo la
última posición el carácter de control y rellenando con ceros
las posiciones de la izquierda, de acuerdo con las reglas
previstas en el Real Decreto 1065/2007, de 27 de Julio, por
el que se aprueba el Reglamento General de las
actuaciones y los procedimientos de gestión e inspección
tributaria y de desarrollo de las normas comunes de los
procedimientos de aplicación de los tributos, (B.O.E del 5
de septiembre).
18-57 Alfanumérico APELLIDOS Y NOMBRE O RAZÓN SOCIAL DEL
DECLARANTE
Si es una persona física se consignará el primer apellido,
un espacio, el segundo apellido, un espacio y el nombre
completo necesariamente en este orden.
Para personas jurídicas y entidades en régimen de
atribución de rentas, se consignará la razón social
completa, sin anagrama.
En ningún caso podrá figurar en este campo un nombre
comercial.
58 Alfabético TIPO DE SOPORTE.
Se cumplimentará una de las siguientes claves:
'T': Transmisión telemática.
14

# Pag. 6

59-107 Alfanumérico PERSONA CON QUIÉN RELACIONARSE.
Datos de la persona con quién relacionarse. Este campo se
subdivide en dos:
59-67 TELÉFONO: Campo numérico de 9 posiciones.
68-107 APELLIDOS Y NOMBRE: Se consignará el
primer apellido, un espacio, el segundo apellido,
un espacio y el nombre completo,
necesariamente en este orden.
108-120 Numérico NÚMERO IDENTIFICATIVO DE LA DECLARACIÓN.
Se consignará el número identificativo correspondiente a la
declaración. Campo de contenido numérico de 13
posiciones.
El número identificativo que habrá de figurar, será un
número secuencial cuyos tres primeros dígitos se
corresponderán con el código 720.
121-122 Alfabético DECLARACIÓN COMPLEMENTARIA O SUSTITUTIVA.
En el caso excepcional de segunda o posterior
presentación de declaraciones, deberá cumplimentarse
obligatoriamente uno de los siguientes campos:
121 DECLARACIÓN COMPLEMENTARIA: Se
consignará una “C” si la presentación de esta
declaración tiene por objeto incluir registros que,
debiendo haber figurado en otra declaración del
mismo ejercicio presentada anteriormente,
hubieran sido completamente omitidas en la
misma.
La modificación del contenido de datos declarados
en otra declaración del mismo ejercicio presentada
anteriormente, se realizará desde el servicio de
consulta y modificación de declaraciones
informativas en la Oficina Virtual de la Agencia
Tributaria (www.agenciatributaria.es).
122 DECLARACIÓN SUSTITUTIVA: Se consignará
una “S” si la presentación tiene como objeto anular
y sustituir completamente a otra declaración
anterior, del mismo ejercicio. Una declaración
sustitutiva sólo puede anular a una única
declaración anterior.
123-135 Numérico NÚMERO IDENTIFICATIVO DE LA DECLARACIÓN
ANTERIOR.
En el caso de que se haya consignado una “C” en el campo
“Declaración complementaria” o en caso de que se haya
consignado “S” en el campo “Declaración sustitutiva”, se
15

# Pag. 7

consignará el número identificativo correspondiente a la
declaración a la que sustituye o complementa.
Campo de contenido numérico de 13 posiciones.
En cualquier otro caso deberá rellenarse a CEROS.
136-144 Numérico NÚMERO TOTAL DE REGISTROS DECLARADOS.
Se consignará el número total de registros de tipo 2
declarados por el declarante.
145-162 Alfanumérico SUMA TOTAL DE VALORACIÓN 1: SALDO O VALOR A
31 DE DICIEMBRE; SALDO O VALOR EN LA FECHA DE
EXTINCIÓN; VALOR DE ADQUISICIÓN.
Campo Alfanumérico de 18 posiciones.
Este campo se subdivide en dos:
145 SIGNO: campo alfabético que se cumplimentará
cuando el resultado de la suma para obtener la “SUMA
TOTAL DE VALORACIÓN 1: SALDO O VALOR A 31 DE
DICIEMBRE; SALDO O VALOR EN LA FECHA DE
EXTINCIÓN; VALOR DE ADQUISICIÓN” (posiciones 146-
162 de este registro de tipo 1) sea menor de 0 (cero). En
este caso se consignará una “N”; en cualquier otro caso el
contenido de este campo será un espacio.
146-162 IMPORTE: Campo numérico de 17 posiciones.
Se consignará sin coma decimal, la suma total de las
cantidades reflejadas en los campos “VALORACIÓN 1:
SALDO O VALOR A 31 DE DICIEMBRE; SALDO O
VALOR EN LA FECHA DE EXTINCIÓN; VALOR DE
ADQUISICIÓN” (posiciones 433–446 del registro de tipo 2)
correspondientes a los registros declarados. En el supuesto
de que en estos registros declarados se hubiera
consignado “N” en el campo “SIGNO VALORACIÓN 1:
SALDO O VALOR A 31 DE DICIEMBRE; SALDO O
VALOR EN LA FECHA DE EXTINCIÓN; VALOR DE
ADQUISICIÓN” (Posición 432 del registro tipo 2), dichas
cantidades se computarán con signo menos al totalizar los
importes que deben reflejarse en esta suma.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
146-160: Parte entera del importe, si no tiene contenido se
consignará a ceros.
161-162: Parte decimal del importe, si no tiene contenido
se consignará a ceros.
16

# Pag. 8

163-180 Alfanumérico SUMA TOTAL DE VALORACIÓN 2: IMPORTE O VALOR
DE LA TRANSMISIÓN; SALDO MEDIO ÚLTIMO
TRIMESTRE.
Campo Alfanumérico de 18 posiciones.
Este campo se subdivide en dos:
163 SIGNO: campo alfabético que se cumplimentará
cuando el resultado de la suma para obtener la “SUMA
TOTAL DE VALORACIÓN 2: IMPORTE O VALOR DE LA
TRANSMISIÓN; SALDO MEDIO ÚLTIMO TRIMESTRE”
(posiciones 164-180 de este registro de tipo 1) sea menor
de 0 (cero). En este caso se consignará una “N”; en
cualquier otro caso el contenido de este campo será un
espacio.
164-180 IMPORTE: Campo numérico de 17 posiciones.
Se consignará sin coma decimal, la suma total de las
cantidades reflejadas en los campos “VALORACIÓN 2:
IMPORTE O VALOR DE LA TRANSMISIÓN; SALDO
MEDIO ÚLTIMO TRIMESTRE” (posiciones 448 – 461 del
registro de tipo 2) correspondientes a los registros
declarados. En el supuesto de que en estos registros
declarados se hubiera consignado “N” en el campo “SIGNO
VALORACIÓN 2: IMPORTE O VALOR DE LA
TRANSMISIÓN; SALDO MEDIO ÚLTIMO TRIMESTRE”
(Posición 447 del registro tipo 2), dichas cantidades se
computarán con signo menos al totalizar los importes que
deben reflejarse en esta suma.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
164-178: Parte entera del importe, si no tiene contenido se
consignará a ceros.
179-180: Parte decimal del importe, si no tiene contenido
se consignará a ceros.
181-500 ------------ BLANCOS
* Todos los importes serán positivos.
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a
blancos.
* Todos los campos numéricos ajustados a la derecha y rellenos de ceros por la
izquierda.
* Todos los campos alfanuméricos/alfabéticos ajustados a la izquierda y rellenos de
blancos por la derecha, en mayúsculas, sin caracteres especiales y sin vocales
acentuadas, excepto que se especifique lo contrario en la descripción del campo.
17

# Pag. 9

MODELO 720. REGISTRO DE TIPO 2. REGISTRO DEL DECLARADO
2 7 2 0
1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60 61 62 63 64 65
66 67 68 69 70 71 72 73 74 75 76 77 78 79 80 81 82 83 84 85 86 87 88 89 90 91 92 93 94 95 96 97 98 99 100101 102 103 104 105 106 107 108 109 110 111 112 113 114 115 116 117 118 119 120 121 122 123 124 125 126 127 128 129 130
131132133134 135 136 137138139140141142143144145146147148149150151152153154 155 156 157158159160161162163164165166 167 168 169 170 171 172 173 174 175 176 177 178 179 180 181 182 183 184 185 186 187 188 189 190 191 192 193 194 195
196197198199 200 201 202203204205206207208209210211212213214215216217218219 220 221 222223224225226227228229230231 232 233 234 235 236 237 238 239 240 241 242 243 244 245 246 247 248 249 250 251 252 253 254 255 256 257 258 259 260
.FITNEDI
EVALC
TIPO DE TITULARIDAD SOBRE EL BIEN O DERECHO
CÓDIGO BIC
OHCERED
O NEIB
ED OPIT
EVALC
OHCERED
O NEIB
ED EVALCBUS
IDENTIF. DE LA
CÓDIGO DE CUENTA
ENTIDAD
IDENTIFICACIÓN DE LA ENTIDAD (CONT) NÚMERO DE IDENTIFICACIÓN FISCAL EN EL PAÍS DE RESIDENCIA FISCAL
ORTSIGER
ED
OPIT
IDENTIFICACION DEL DECLARANTE
LED
NÓICIDNOC
ED EVALC
ETNARALCED
EJERCICIO N.I.F. DECLARANTE
TIPO DE DERECHO REAL SOBRE INMUEBLE
NOMBRE VIA PUBLICA Y NUMERO
DE CASA
SÍAP
ED
OGIDÓC
IDENTIFICACIÓN DE VALORES
ATNEUC.FITNEDI
EVALC
N.I.F. DEL DECLARADO N.I.F. DEL REPRESENTANTE LEGAL APELLIDOS Y NOMBRE, RAZÓN SOCIAL O DENOMINACIÓN DEL DECLARADO
MODELO
DOMICILIO DE LA ENTIDAD O
UBICACIÓN DEL INMUEBLE
18

# Pag. 10

MODELO 720. REGISTRO DE TIPO 2. REGISTRO DEL DECLARADO
261262263264 265 266 267268269270271272273274275276277278279280281282283284 285 286 287288289290291292293294295296 297 298 299 300 301 302 303 304 305 306 307 308 309 310 311 312 313 314 315 316 317 318 319 320 321 322 323 324 325
326327328329 330 331 332333334335336337338339340341342343344345346347348349 350 351 352353354355356357358359360361 362 363 364 365 366 367 368 369 370 371 372 373 374 375 376 377 378 379 380 381 382 383 384 385 386 387 388 389 390
AÑO MES DÍA
391392393394 395 396 397398399400401402403404405406407408409410411412413414 415 416 417418419420421422423424425426 427 428 429 430 431 432 433 434 435 436 437 438 439 440 441 442 443 444 445 446 447 448 449 450 451 452 453 454 455
456457458459 460 461 462463464465466467468469470471472473474475476477478479 480 481 482483484485486487488489490491 492 493 494 495 496 497 498 499 500
OHCD
O
NEIB
LED
NEGIRO
VALORACIÓN 1: SALDO O VALOR A 31 DE DICIEMBRE; SALDO O
VALOR EN LA FECHA DE EXTINCIÓN; VALOR DE ADQUISICIÓN
ONGIS
VALORACIÓN 2: IMPORTE O VALOR DE
LA TRANSMISIÓN; SALDO MEDIO
ÚLTIMO TRIMESTRE
PORCENTAJE
DE
PARTICIPACIÓN
ONGIS
NOMBRE VÍA PÚBLICA Y NÚMERO DE CASA (CONT.) COMPLEMENTO
DOMICILIO DE LA ENTIDAD O INMUEBLE
POBLACIÓN/CIUDAD PROVINCIA/REGION/ESTADO
DOMICILIO DE LA ENTIDAD O INMUEBLE FECHA DE INCORPORACIÓN FECHA DE EXTINCIÓN
PROVINCIA/REGION/ESTADO CODIGO POSTAL (ZIP CODE) AÑO DÍA DECIMAL ENTERA
SÍAP
OGIDÓC
COMPLEMENTO (CONT.)
MES ENTERA
IMPORTE DE LA
TRANSMISIÓN O DEL
SALDO MEDIO ÚLTIMO
TRIMESTRE
SEROLAV.TNESERPER
EVALC
NÚMERO DE VALORES
ENTERA
LAMICED
ENTERA
(CONT) DECIMAL
ELBMNI
NEIB
ED
OPIT
EVALC
ARETNE LAMICED
DOMICILIO DE LA ENTIDAD O INMUEBLE
19

# Pag. 11

B.- TIPO DE REGISTRO 2: REGISTRO DE DETALLE.
(POSICIONES, NATURALEZA Y DESCRIPCIÓN DE LOS CAMPOS)
POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS
1 Numérico TIPO DE REGISTRO.
Constante '2'.
2-4 Numérico MODELO DECLARACIÓN.
Constante '720'.
5-8 Numérico EJERCICIO.
Consignar lo contenido en estas mismas posiciones del
registro de tipo 1.
9-17 Alfanumérico N.I.F. DEL DECLARANTE.
Consignar lo contenido en estas mismas posiciones del
registro de tipo 1.
18-26 Alfanumérico N.I.F. DEL DECLARADO.
Consignar lo contenido en la posición del N.I.F del
declarante posiciones 9-17 del registro de tipo 1.
27-35 Alfanumérico N.I.F. DEL REPRESENTANTE LEGAL.
Si el declarado es menor de edad o incapacitado y su
representante legal dispone de NIF asignado en España de
acuerdo con las reglas previstas en el Reglamento General
de las actuaciones y los procedimientos de gestión e
inspección tributaria y de desarrollo de las normas
comunes de los procedimientos de aplicación de los
tributos, aprobado por el Real Decreto 1065/2007, de 27 de
julio (B.O.E del 5 de septiembre), se consignará en este
campo el número de identificación fiscal de su
representante legal.
Este campo deberá estar ajustado a la derecha, siendo la
última posición el carácter de control y rellenando con ceros
las posiciones a la izquierda.
36 – 75 Alfanumérico APELLIDOS Y NOMBRE, RAZÓN SOCIAL O
DENOMINACIÓN DEL DECLARADO.
Consignar lo contenido en el campo de “APELLIDOS Y
NOMBRE, RAZÓN SOCIAL O DENOMINACIÓN DEL
DECLARANTE” del registro de tipo 1.
a) Para personas físicas se consignará el primer apellido,
un espacio, el segundo apellido, un espacio y el
20

# Pag. 12

nombre completo, necesariamente en este mismo
orden. Si el declarado es menor de edad o
incapacitado, se consignarán en este campo los
apellidos y nombre del menor de edad o incapacitado.
b). Tratándose de personas jurídicas y entidades, se
consignará la razón social o denominación completa
de la entidad, sin anagramas.
76 Numérico CLAVE DE CONDICIÓN DEL DECLARANTE
Se consignará una de las siguientes claves en función de
la condición con la que figura el declarante en el bien o
derecho declarado:
1 Titular.
2 Representante.
3 Autorizado.
4 Beneficiario.
5 Usufructuario.
6 Tomador.
7 Con poder de disposición.
8 Otras formas de titularidad real conforme a lo
previsto en el artículo 4.2. de la Ley 10/2010, de
28 de abril.
77-101 Alfanumérico TIPO DE TITULARIDAD SOBRE EL BIEN O DERECHO.
En el caso de consignarse la clave “8” en el campo
“CLAVE DE CONDICIÓN DEL DECLARANTE” (posición
76): se informará el tipo de titularidad que ostenta.
102 Alfabético CLAVE TIPO DE BIEN O DERECHO.
Se consignará la clave alfabética que corresponda en
función del tipo de bien o derecho que se posea a lo largo
del ejercicio:
• “C”: Cuentas abiertas en entidades que se dediquen
al tráfico bancario o crediticio y se encuentren
situadas en el extranjero.
• “V”: Valores o derechos situados en el extranjero
representativos de la participación en cualquier tipo
de entidad jurídica, valores situados en el extranjero
representativos de la cesión de capitales propios a
terceros o aportados para su gestión o administración
a cualquier instrumento jurídico, incluyendo
fideicomisos y “trusts” o masas patrimoniales que, no
obstante carecer de personalidad jurídica, puedan
actuar en el tráfico económico.
21

# Pag. 13

• “I”: Acciones y participaciones en el capital social o
fondo patrimonial de Instituciones de Inversión
Colectiva situadas en el extranjero.
• “S”: Seguros de vida o invalidez y rentas temporales o
vitalicias, cuyas entidades aseguradoras se
encuentren situadas en el extranjero.
• “B”: Titularidad y derechos reales sobre inmuebles
ubicados en el extranjero.
No deberá suministrase información relativa a los
seguros de vida que cubran exclusivamente el riesgo
de muerte (sin perjuicio de que puedan cubrir riesgos
complementarios en otros ramos distintos al de vida) y
que no tengan valor de rescate.
103 Numérico SUBCLAVE DE BIEN O DERECHO
Se consignara la subclave numérica que corresponda al
tipo de bien o derecho que se esté declarando, según la
relación de subclaves siguientes:
Subclaves a utilizar en los registros correspondientes
a la clave C (cuentas bancarias o de crédito situadas
en el extranjero):
1 Cuenta corriente.
2 Cuenta de ahorro.
3 Imposiciones a plazo.
4 Cuentas de crédito.
5 Otras cuentas.
Subclaves a utilizar en los registros correspondientes
a la clave V (valores y derechos situados en el
extranjero):
1 Valores o derechos representativos de la participación
en cualquier tipo de entidad jurídica.
2 Valores representativos de la cesión de capitales
propios a terceros.
3 Valores aportados para su gestión o administración a
cualquier instrumento jurídico, incluyendo fideicomisos y
“trusts” o masas patrimoniales que, no obstante carecer
de personalidad jurídica, puedan actuar en el tráfico
económico
Subclaves a utilizar en los registros correspondientes
a la clave S (seguros y rentas temporales o vitalicias):
1 Seguros de vida o invalidez, cuya entidad aseguradora
se encuentra en el extranjero.
2 Rentas temporales o vitalicias generadas como
consecuencia de la entrega de un capital en dinero, de
derechos de contenido económico o de bienes muebles o
22

# Pag. 14

inmuebles, cuya entidad receptora o gestora se encuentre
en el extranjero.
Subclaves a utilizar en los registros correspondientes
a la clave B (titularidad y derechos reales sobre
inmuebles ubicados en el extranjero):
1 Titularidad del bien inmueble.
2 Derechos reales de uso o disfrute sobre bienes
inmuebles.
3 Nuda propiedad sobre bienes inmuebles.
4 Multipropiedad, aprovechamiento por turnos, propiedad
a tiempo parcial o fórmulas similares sobre bienes
inmuebles.
5 Otros derechos reales sobre bienes inmuebles.
Cuando el campo “CLAVE TIPO DE BIEN O DERECHO”
(posición 102) corresponda a la clave I (acciones o
participaciones en el capital social o fondo patrimonial
Instituciones de Inversión Colectiva situadas en el
extranjero) la subclave numérica de la posición 103
deberá informarse sin contenido (a cero).
104-128 Alfanumérico TIPO DE DERECHO REAL SOBRE INMUEBLE.
Cuando el campo “CLAVE TIPO DE BIEN O DERECHO”
toma el valor “B” y la “SUBCLAVE DEL BIEN O
DERECHO” declarada sea “5”, se deberá indicar en el
espacio reservado, el tipo de derecho real que ostenta
sobre el bien inmueble.
129 – 130 Alfabético CÓDIGO DE PAÍS.
En este campo se consignará el código que corresponda
al país o territorio donde:
- se encuentre situada la cuenta de la entidad dedicada al
tráfico bancario o crediticio en los casos donde se declaró
como “CLAVE TIPO DE BIEN O DERECHO” (posición
102) “C”.
- se encuentren depositados o gestionados los bienes y
derechos declarados con la “CLAVE TIPO DE BIEN O
DERECHO” (posición 102) V”.
- se encuentren situadas las instituciones de inversión
colectiva en los casos donde se declaró como “CLAVE
TIPO DE BIEN O DERECHO” (posición 102) “I”.
- se encuentre situada la entidad aseguradora o la
entidad a la que se entregaron los bienes y derechos
constitutivos de las rentas temporales o vitalicias, en los
casos en los que se declaró como “CLAVE TIPO DE
BIEN O DERECHO” (posición 102) “S”.
23

# Pag. 15

- se encuentren situados los bienes inmuebles en los
casos donde se declaró como “CLAVE TIPO DE BIEN O
DERECHO” (posición 102) “B”.
Se identificará el país o territorio de acuerdo con los
códigos alfabéticos de países y territorios que figuran en
la Orden EHA/3496/2011, de 15 de diciembre, en su
anexo II (BOE 26/12/2011).
131 Numérico CLAVE DE IDENTIFICACIÓN.
Cuando el campo “CLAVE TIPO DE BIEN O DERECHO”
(posición102) tome el valor “V” ó “I” se informará este
campo de acuerdo a:
Clave Descripción
1 Identificación por código ISIN (código de 12 posiciones).
2 Valores extranjeros sin código ISIN.
Cuando el campo “CLAVE TIPO DE BIEN O DERECHO”
(posición102) tome otro valor distinto de “V” ó “I” deberá
informarse sin contenido (a cero).
132-143 Alfanumérico IDENTIFICACIÓN DE VALORES.
Cuando en el campo “CLAVE TIPO DE BIEN O
DERECHO” (posición 102) se haya consignado el valor “V”
ó “I”
Se hará constar:
El código ISIN, configurado de acuerdo a la Norma
Técnica 1/1998, de 16 de diciembre, de la Comisión
Nacional del Mercado de Valores y la Circular 2/2010, de
28 Julio de Diciembre, de la Comisión Nacional del
mercado de Valores (supuesto de Campo “CLAVE DE
IDENTIFICACIÓN”, posición 131, configurado con valor
1).
Para valores extranjeros que tengan asignado ISIN se
hará constar éste en todo caso. En los demás casos, se
reflejará la clave “ZXX”, siendo “XX” el código del país
emisor de acuerdo con los códigos alfabéticos de países
y territorios que figuran en la Orden EHA/3496/2011, de
15 de Diciembre en su Anexo II de la Disposición
Adicional primera Anexo II (BOE 26 de Diciembre de
2011) (supuesto de campo “CLAVE DE
IDENTIFICACIÓN”, posición131, configurado con valor 2)
Únicamente se informará este campo si en el campo
“CLAVE TIPO DE BIEN O DERECHO” (posición102) se
ha consignado “V” ó “I”. En cualquier otro caso se
informará sin contenido (espacios en blanco).
24

# Pag. 16

144 Alfabético CLAVE IDENTIFICACIÓN DE CUENTA.
Cuando en el campo “CLAVE TIPO DE BIEN O
DERECHO” (posición 102) se haya consignado “C” y en
función de la identificación de la cuenta se consignará una
de las siguientes claves:
I Identificación de la cuenta con código IBAN
O Otra identificación.
145-155 Alfanumérico CÓDIGO BIC.
Se consignara en este campo el código BIC (Bank
International Code).
156-189 Alfanumérico CÓDIGO DE CUENTA.
Se consignarán los caracteres del código de cuenta.
Cuando el campo “CLAVE IDENTIFICACIÓN DE
CUENTA” (posición144) tome el valor “I” se consignará
este código de cuenta con formato IBAN, si toma el valor
“O” se consignará la codificación de la cuenta asignada por
la entidad bancaria.
190 - 230 Alfanumérico IDENTIFICACIÓN DE LA ENTIDAD.
Se consignará en este campo la Razón Social o
Denominación de las entidades siguientes según el valor
del campo “CLAVE TIPO DE BIEN O DERECHO”
(posición 102):
• Cuando la “CLAVE TIPO DE BIEN O DERECHO”
(posición 102) tome el valor “C”: Razón social o
denominación de la entidad bancaria o crediticia.
• Cuando la “CLAVE TIPO DE BIEN O DERECHO”
(posición 102) tome el valor “V” o “I”: Razón social o
denominación de la entidad participada, cesionaria
del capital, o entidad encargada de la gestión o
administración de los valores, o de la sociedad o
fondo patrimonial de las instituciones de inversión
colectiva.
• Cuando la “CLAVE TIPO DE BIEN O DERECHO”
(posición 102) tome el valor “S”: Razón social o
denominación de la entidad aseguradora.
Este campo quedará en blanco cuando la “CLAVE TIPO
DE BIEN O DERECHO” (posición 102) tome el valor “B”.
25

# Pag. 17

231–250 Alfanumérico NÚMERO DE IDENTIFICACIÓN FISCAL EN EL PAÍS DE
RESIDENCIA FISCAL
Se consignará el número de identificación fiscal de las
entidades declaradas en el campo anterior, asignado en el
país o territorio de residencia fiscal.
Este campo quedará en blanco cuando la “CLAVE TIPO
DE BIEN O DERECHO” (posición 102) tome el valor “B”.
251-414 Alfanumérico DOMICILIO DE LA ENTIDAD O UBICACIÓN DEL
INMUEBLE.
Cuando la “CLAVE TIPO DE BIEN O DERECHO”
(posición102) tome el valor “C”, “V”, “I” o “S”, se
consignará en este campo la dirección de la entidad
identificada en los dos campos anteriores.
Cuando la “CLAVE TIPO DE BIEN O DERECHO”
(posición 102) tome el valor “B”, independiente de la
subclave declarada, se consignará la dirección del
inmueble objeto de la declaración.
Este campo se subdivide en:
251-302 NOMBRE VÍA PUBLICA Y NÚMERO DE
CASA
Se consignará el nombre largo de la vía
pública, si no cupiese completo el nombre, no
se harán constar los artículos, preposiciones ni
conjunciones y se pondrán en abreviatura los
títulos (vgr. cd = Conde). Los demás casos se
abreviarán utilizando las siglas de uso general.
Asimismo se consignará el número o punto
kilométrico.
303-342 COMPLEMENTO.
En su caso, se harán constar en este campo
los datos adicionales que resulten necesarios
para la completa identificación del domicilio.
343-372 POBLACIÓN/CIUDAD.
Se consignará el nombre de la población o
ciudad en la que se encuentra situado el
domicilio
373-402 PROVINCIA/REGIÓN/ESTADO.
Se consignará en este campo el nombre de la
Provincia, Región, Estado, Departamento o
cualquier otra subdivisión política o
administrativa, donde se encuentre situado el
domicilio.
26

# Pag. 18

403-412 CÓDIGO POSTAL (ZIP CODE).
Se consignará el código postal referido al
domicilio
413-414 CÓDIGO PAÍS.
Se cumplimentará el código del país o territorio
correspondiente al domicilio, de acuerdo con
los códigos alfabéticos de países y territorios
que figuran en la Orden EHA/3496/2011, de 15
de Diciembre en su Anexo II de la Disposición
Adicional primera Anexo II (BOE 26 de
Diciembre de 2011).
415-422 Numérico FECHA DE INCORPORACIÓN.
Se hará constar las siguientes fechas según el valor del
campo “CLAVE TIPO DE DE BIEN O DERECHO”
(posición 102) declarada:
‐ Cuando la “CLAVE TIPO DE BIEN O DERECHO”
(posición 102) tome el valor “C” se consignará la
fecha de apertura de la cuenta, de la concesión de la
autorización o del poder de disposición, o de cualquier
otra forma de titularidad real.
‐ Cuando la “CLAVE TIPO DE BIEN O DERECHO”
(posición 102) tome el valor “V” se consignará la
fecha de adquisición de la titularidad o titularidad real
de los valores.
‐ Cuando la “CLAVE TIPO DE BIEN O DERECHO”
(posición 102) tome el valor “I” se consignará la fecha
de adquisición de la titularidad o titularidad real sobre
las acciones o participaciones en la IIC.
‐ Cuando la “CLAVE TIPO DE BIEN O DERECHO”
(posición 102) tome el valor “S” se consignará la
fecha de contratación con la entidad aseguradora o
con la entidad receptora de los bienes y derechos
constitutivos de las rentas vitalicias o temporales.
‐ Cuando la “CLAVE TIPO DE BIEN O DERECHO”
(posición 102) tome el valor “B” se consignará la
fecha de adquisición de la titularidad o titularidad real
sobre el bien inmueble o del derecho real sobre el
mismo.
‐ Cuando existan diferentes fechas de incorporación
respecto del tipo de bien o derecho declarado
deberán consignarse las mismas en diferentes
registros. De este modo cuando la “CLAVE TIPO DE
BIEN O DERECHO” tome el valor “V” o “I” se deberán
declarar tanto registros como fechas de adquisición
diferentes existan.
27

# Pag. 19

Se indicarán los cuatro dígitos del año, los dos del mes
(de 01 a 12) y los dos del día (de 01 a 31) con el formato
AAAAMMDD.
423 Alfabético ORIGEN DEL BIEN O DERECHO.
Se consignará el “Origen del bien o derecho” de acuerdo
con las siguientes claves alfabéticas.
• “A”: Bien o derecho que se declara por primera vez o
que se incorpora en el ejercicio de la declaración.
• “M”: Bien o derecho que ya ha sido declarado en
ejercicios anteriores. Se deberá declarar un bien o
derecho de nuevo dependiendo de la clave “CLAVE
TIPO DE BIEN O DERECHO” (posición 102)
declarada en los siguientes casos:
o Cuando la “CLAVE TIPO DE BIEN O
DERECHO” (posición 102) tome el valor “C”, si el
saldo conjunto de las cuentas a 31 de diciembre
o el saldo medio conjunto del último trimestre de
las cuentas hubiese experimentado un
incremento superior a 20.000 € respecto del que
determino la presentación de la última
declaración.
o Cuando la “CLAVE TIPO DE BIEN O
DERECHO” (posición 102) tome el valor “V”, “I” o
“S”, si el saldo y valor a 31 de diciembre
conjuntamente considerado de todos ellos
hubiese experimentado un incremento superior a
20.000 € respecto del que determino la
presentación de la última declaración.
o Cuando la “CLAVE TIPO DE BIEN O
DERECHO” (posición 102) tome el valor “B”, si el
valor de adquisición y valor a 31 de diciembre
conjuntamente considerados hubiese
experimentado un incremento superior a 20.000
€ respecto del que determino la presentación de
la última declaración.
• “C”: Bien o derecho que se declara porque se
extingue la titularidad, se revoca la autorización o
poder de disposición, o se extingue cualquier otra
forma de titularidad real sobre el mismo.
424 - 431 Numérico FECHA DE EXTINCIÓN.
Este campo solo deberá cumplimentarse cuando el
campo “ORIGEN DE BIEN O DERECHO” (posición 423)
sea “C”. En este caso deberá indicarse una de las fechas
siguientes según sea la “CLAVE TIPO DE BIEN O
DERECHO” (posición 102) declarada:
28

# Pag. 20

‐ Si la “CLAVE TIPO DE BIEN O DERECHO” (posición
102) declarada es “C”: fecha de la revocación de la
autorización, de la representación, del poder de
disposición, de la posición de beneficiario, del cese
como titular o titular real de la cuenta bancaria o de
crédito.
‐ Si la “CLAVE TIPO DE BIEN O DERECHO” (posición
102) es “V”, “I” o “S”: fecha de la transmisión o
extinción de la titularidad o cualquier otra forma de
titularidad real declarada sobre los valores, acciones
o participaciones en IIC, seguros o rentas temporales
y vitalicias.
‐ Si la “CLAVE TIPO DE BIEN O DERECHO” (posición
102) toma el valor “B”: fecha de transmisión o
extinción de, la titularidad, titularidad real o de los
derechos reales sobre los bienes inmuebles.
Se indicarán los cuatro dígitos del año, los dos del mes
(de 01 a 12) y los dos del día (de 01 a 31) con el formato
AAAAMMDD
432-446 Alfanumérico VALORACIÓN 1: SALDO O VALOR A 31 DE
DICIEMBRE; SALDO O VALOR EN LA FECHA DE
EXTINCIÓN; VALORDE ADQUISICIÓN.
Se hará constar el valor de los bienes y derechos
declarados en euros o su contravalor en los casos de
operaciones de divisas. Asimismo cuando existan
múltiples partícipes asociados al bien o derecho
declarado el importe NO se prorrateará.
Este campo se subdivide en:
432 SIGNO: campo alfabético. Si el saldo es negativo se
consignará una “N”, en cualquier otro caso el contenido
de este campo será un espacio.
433-446 IMPORTE: campo numérico de 14 posiciones.
Se hará constar sin coma decimal el saldo.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
433-444 Parte entera del saldo, si no tiene contenido se
consignará a ceros.
445-446 Parte decimal del saldo, si no tiene contenido
se consignará a ceros.
29

# Pag. 21

El importe a consignar en este campo dependerá del
valor consignado en el campo “CLAVE TIPODE BIEN O
DERECHO” (posición102):
‐ Si la “CLAVE TIPO DE BIEN O DERECHO” es “C”:
saldo a 31 de diciembre o saldo en la fecha en la que
se extinga o cese la titularidad, representación,
autorización, poder de disposición o titularidad real
de la cuenta.
‐ Si la “CLAVE TIPO DE BIEN O DERECHO” es “V”:
saldo a 31 de diciembre o en la fecha de extinción de
la titularidad declarada.
‐ Si la “CLAVE TIPO DE BIEN O DERECHO” es “I”:
valor liquidativo a 31 de diciembre o en la fecha de
extinción de la titularidad o titularidad real declarada.
Esta valoración deberá suministrarse conforme a las
reglas establecidas en la Ley 19/1991, de 6 de junio,
del Impuesto sobre el Patrimonio.
‐ Si la “CLAVE TIPO DE BIEN O DERECHO” es “S”, y
la “SUBCLAVE DE BIEN O DERECHO” (posición
103) declarada es “1” se hará constar el valor de
rescate a 31 de diciembre. En los casos en los que la
“SUBCLAVE DE BIEN O DERECHO” (posición 103-
128) sea “2” se informará del valor de capitalización
a 31 de diciembre de la renta temporal o vitalicia.
Esta valoración deberá suministrarse conforme a las
reglas establecidas en la Ley 19/1991, de 6 de junio,
del Impuesto sobre el Patrimonio.
‐ Si la “CLAVE TIPO DE BIEN O DERECHO” es “B”, y
la “SUBCLAVE DE BIEN O DERECHO” (posición
103) es “1” se consignará el valor de adquisición del
bien inmueble incluyendo en su caso los impuestos
satisfechos.
Cuando la “SUBCLAVE DE BIEN O DERECHO” (posición
103) sea “2”, “3” o “4” deberá informarse del valor a 31 de
diciembre según las reglas de valoración establecidas en
la Ley 19/1991, de 6 de junio, del Impuesto sobre el
Patrimonio.
Los importes declarados, salvo los correspondientes a la
“CLAVE TIPO DE BIEN O DERECHO” “B” y “SUBCLAVE
DE BIEN O DERECHO” “1” se refieren al ejercicio de la
declaración.
30

# Pag. 22

447-461 Alfanumérico VALORACIÓN 2: IMPORTE O VALOR DE LA
TRANSMISIÓN; SALDO MEDIO ÚLTIMO TRIMESTRE.
Se hará constar el valor de los bienes y derechos
declarados en euros o su contravalor en los casos de
operaciones de divisas. Asimismo cuando existan
múltiples partícipes asociados al bien o derecho
declarado el importe NO se prorrateará.
Este campo se subdivide en:
447 SIGNO: campo alfabético. Si el saldo es negativo
se consignará una “N”, en cualquier otro caso el contenido
de este campo será un espacio.
448-461 IMPORTE: campo numérico de 14
posiciones.
Se hará constar sin coma decimal el importe.
Los importes deben consignarse en EUROS.
Este campo se subdivide en dos:
448-459 Parte entera del saldo, si no tiene contenido se
consignará a ceros.
460-461 Parte decimal del saldo, si no tiene contenido se
consignará a ceros.
Solamente deberá informarse de este campo:
‐ Si el campo “ORÍGEN DEL BIEN O DERECHO”
(posición423) es “C” y la “CLAVE TIPO DE BIEN O
DERECHO” (posición 102) es “B”. En este caso se
consignará el importe o valor de transmisión de la
titularidad o titularidad real sobre el bien inmueble o
del derecho real sobre el mismo.
‐ Si el campo “ORÍGEN DEL BIEN O DERECHO”
(posición 423) es “A” o “M” y la “CLAVE TIPO DE
BIEN O DERECHO” (posición 102) es “C”. En este
caso se indicará el saldo medio de la cuenta en el
último trimestre del ejercicio de la declaración.
462 Alfabético CLAVE DE REPRESENTACIÓN DE VALORES.
Solo se informará este campo cuando en el campo
“CLAVE TIPO DE BIEN O DERECHO” (posición102) se
haya consignado “V” o “I”.
Se consignará una de las claves siguientes:
31

# Pag. 23

Clave Descripción
A Valores representados mediante anotaciones en
cuenta.
B Valores no representados mediante anotaciones en
cuenta.
463 - 474 Numérico NÚMERO DE VALORES.
Solo se informará este campo cuando en el campo
“CLAVE TIPO DE BIEN O DERECHO” (posición102) se
haya consignado “V” o “I”.
Se consignará el número de acciones, participaciones o
valores respecto de los que se ostente cualquier
condición de declarante.
Se subdivide en dos campos:
463-472 Parte entera de los valores.
473-474 Parte decimal de los valores. (si no tiene contenido se
consignará a ceros).
475 Alfabético CLAVE TIPO DE BIEN INMUEBLE .
Exclusivamente se informará este campo cuando el
campo “CLAVE TIPO DE BIEN O DERECHO” (posición
102) tome el valor “B". En estos casos se deberá indicar
el tipo de bien inmueble sobre el que se ha declarado la
titularidad, titularidad real o derecho real.
U: Urbano.
R: Rústico.
476-480 Numérico PORCENTAJE DE PARTICIPACIÓN.
En el caso de múltiples sujetos con la misma “CLAVE DE
CONDICIÓN DE DECLARANTE” (posición 76) sobre el
bien o derecho declarado, se consignará por cada
declarante el porcentaje de su participación.
Este campo se subdivide en:
476-478 Parte entera del porcentaje; si no tiene contenido,
se consignará a ceros.
479-480 Parte decimal del porcentaje; Figurará la parte
decimal del porcentaje; si no tiene contenido se
consignará a ceros.
32

# Pag. 24

Si la cuenta, valor, seguro, renta, inmueble o derecho real
sobre este último tiene un solo declarante con la misma
“CLAVE DE CONDICIÓN DE DECLARANTE” (posición
76), el valor a declarar en este campo será 100 en la
parte entera, y 00 en la parte decimal
481-500 ---------------- BLANCOS
* Todos los importes serán positivos.
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a blancos.
* Todos los campos numéricos ajustados a la derecha y rellenos de ceros por la izquierda.
* Todos los campos alfanuméricos/alfabéticos ajustados a la izquierda y rellenos de
blancos por la derecha, en mayúsculas, sin caracteres especiales y sin vocales
acentuadas, excepto que se especifique lo contrario en la descripción del campo.
33