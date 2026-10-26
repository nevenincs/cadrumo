# Pag. 1

123 DISEÑO DE REGISTRO 13/11/2008
Agencia Tributaria
Modelo 123 Diseño de registro.
vers. 1.0 IRPF - Sociedades - IRNR - Retenciones e ingresos a cuenta sobre determinadas rentas
Nº Posic. Lon Tipo Descripción Validación Contenido Uso
1 1 3 Num Modelo. Obligatorio Constante "123"
2 4 2 Num Página. Obligatorio Constante "01" MI
3 6 1 A Indicador de página complementaria. En blanco MI
4 7 1 A Tipo Declaración Obligatorio PI Ver nota PI
5 8 5 Num Código Administración. Incluido en el fichero ADMON.TXT MI
6 13 9 An Identificación (1) -NIF Obligatorio Cualquier NIF válido P.F. o P.J.
7 22 4 An Identificación (1) - Comienzo del primer apellido en personas físicas Obligatorio PI PI
8 26 30 An Identificación (1) - Apellidos o Razón Social. Obligatorio MI
9 56 15 A Identificación (1) - Nombre. Obligatorio P. F. MI
10 71 4 Num Devengo (2) - Ejercicio. Obligatorio
11 75 2 An Devengo (2) - Período. Obligatorio "01",...,"12" o "1T" …"4T"
12 77 6 N Liquidación (3) - Número de perceptores [1]
13 83 13 N Liquidación (3) - Base de las retenciones e ingresos a cuenta[2]. 11 Enteros y 2 decimales
14 96 13 N Liquidación (3) - Retenciones e ingresos a cuenta [3]. 11 Enteros y 2 decimales
15 109 13 N Liquidación (3) - Periodificación. Ingresos ejercicios anteriores[4]. 11 Enteros y 2 decimales
16 122 13 N Liquidación (3) - Periodificación. Regularización [5]. 11 Enteros y 2 decimales
17 135 13 N Liquidación (3) - Total liquidación. Suma retenciones e ingresos a cuenta y regularización [6] 11 Enteros y 2 decimales
18 148 13 N Liquidación (3) - Resultados a ingresar de anteriores declaraciones . [7] 11 Enteros y 2 decimales
19 161 13 N Liquidación (3) - Resultado a ingresar [8] 11 Enteros y 2 decimales
20 174 13 N Ingreso (4) - Importe del ingreso [I] 11 Enteros y 2 decimales
"0" No consta, "1" Efectivo,
"2" Adeudo en cuenta, "3"
21 187 1 Num Ingreso (4) - Forma de pago Domiciliación
22 188 4 An Ingreso (4) - Código cuenta cliente - Entidad
23 192 4 An Ingreso (4) - Código cuenta cliente - Sucursal
24 196 2 An Ingreso (4) - Código cuenta cliente - DC
25 198 10 An Ingreso (4) - Código cuenta cliente - Número de cuenta
26 208 16 An Complementaria (6) - Código electrónico declaración anterior PI
27 224 13 An Declaración complementaria (6) - nº justificante declaración anterior
28 237 100 An Persona de Contacto Obligatorio PI PI
29 337 9 An Teléfono Obligatorio PI PI
30 346 350 An Observaciones PI
31 696 16 A Firma (7) - Localidad MI
32 712 2 An Firma (7) - Fecha: Día MI
33 714 10 A Firma (7) - Fecha: Mes MI
34 724 4 An Firma (7) - Fecha: Año MI
35 728 2 An Fin de Registro. Constante CRLF (Hexadecimal 0D0A, Decimal 1310) MI
Total: 729
Nota: El uso MI significa que sólo se tiene en cuenta en el módulo de impresión y el uso PI significa que sólo tiene utilidad en las presentaciones por Internet.
PI: El tipo de declaración puede ser: G (cuenta corriente tributaria-ingreso) I (ingreso) N (negativa) U (domiciliación del ingreso en CCC)
MI: En caso de declaración negativa consígnese "N". En el caso de declaración NO negativa, se considerará valido cualquier otro carácter alfanuméric
Página 1 de 1