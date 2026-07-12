# Pag. 1

115 DISEÑO DE REGISTRO 13/11/2008
Agencia Tributaria
Modelo 115 Diseño de registro.
vers. 1.0 IRPF - Sociedades - IRNR - Retenciones e ingresos a cuenta
Nº Posic. Lon Tipo Descripción Validación Contenido Uso
1 1 3 Num Modelo. Obligatorio Constante "115"
2 4 2 Num Página. Obligatorio Constante "01" MI
3 6 1 A Indicador de página complementaria. En blanco MI
4 7 1 A Tipo Declaración Obligatorio PI Ver nota PI
5 8 5 Num Código Administración. Obligatorio Incluido en el fichero ADMON.TXT MI
6 13 9 An Identificación (1) -NIF Obligatorio Cualquier NIF válido P.F. o P.J.
7 22 4 An Identificación (1) - Comienzo del primer apellido en personas físicas Obligatorio PI PI
8 26 30 An Identificación (1) - Apellidos o Razón Social. Obligatorio MI
9 56 15 A Identificación (1) - Nombre. Obligatorio P. F. MI
10 71 2 A Identificación (1) - Sigla vía MI
11 73 17 An Identificación (1) - Nombre de la vía pública MI
12 90 4 An Identificación (1) - Número Vía Pública MI
13 94 2 An Identificación (1) - Escalera MI
14 96 2 An Identificación (1) - Piso MI
15 98 2 An Identificación (1) - Puerta MI
16 100 9 An Identificación (1) - Teléfono MI
17 109 20 A Identificación (1) - Municipio MI
18 129 15 A Identificación (1) - Provincia MI
19 144 5 An Identificación (1) - CódigoPostal MI
20 149 4 Num Devengo (2) - Ejercicio. Obligatorio
21 153 2 An Devengo (2) - Período. Obligatorio "01",...,"12" o "1T" …"4T"
22 155 6 N Liquidación (3) - Número de perceptores [1]
23 161 13 N Liquidación (3) - Base de las retenciones e ingresos a cuenta[2]. 11 Enteros y 2 decimales
24 174 13 N Liquidación (3) - Retenciones e ingresos a cuenta [3]. 11 Enteros y 2 decimales
25 187 13 N Liquidación (3) - A deducir [4]. 11 Enteros y 2 decimales
26 200 13 N Liquidación (3) - Resultado a ingresar [5]. 11 Enteros y 2 decimales
27 213 16 An Complementaria (4) - Código electrónico declaración anterior PI
28 229 13 An Complementaria (4) - Nº de justificante de la declaración anterior.
29 242 100 An Persona de Contacto Obligatorio PI PI
30 342 9 An Teléfono Obligatorio PI PI
31 351 350 An Observaciones PI
32 701 1 An Ingreso (5) - Forma de pago - En efectivo "X" o blanco
33 702 1 An Ingreso (5) - Forma de pago - E.C. adeudo en cuenta "X", blanco, D (domiciliación)
34 703 13 N Ingreso (5) - Importe del ingreso [I]. 11 Enteros y 2 decimales
35 716 4 An Ingreso (5) - Código cuenta cliente - Entidad
36 720 4 An Ingreso (5) - Código cuenta cliente - Sucursal
37 724 2 An Ingreso (5) - Código cuenta cliente - DC
38 726 10 An Ingreso (5) - Código cuenta cliente - Número de cuenta
39 736 2 An Firma (6) - Fecha: Día MI
40 738 10 A Firma (6) - Fecha: Mes MI
41 748 4 An Firma (6) - Fecha: Año MI
42 752 2 An Fin de Registro. Constante CRLF (Hexadecimal 0D0A, Decimal 1310) MI
Total: 753
Nota: El uso MI significa que sólo se tiene en cuenta en el módulo de impresión y el uso PI significa que sólo tiene utilidad en las presentaciones por Internet.
PI: El tipo de declaración puede ser: G (cuenta corriente tributaria-ingreso) I (ingreso) N(negativa) U(domiciliación del ingreso en CCC)
MI:Se admitirá cualquier carácter alfanumérico válido
Página 1 de 1