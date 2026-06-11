# 06-390-ejercicio-2013-45-kb-ejecutable.xsd

<?xml version="1.0" encoding="ISO-8859-1"?>
<!-- edited with XMLSPY v5 rel. 2 U (http://www.xmlspy.com) by sdf (Agencia Tributaria) -->
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" elementFormDefault="qualified" attributeFormDefault="unqualified">
	<!--ABREVIATURAS:
			Rendimiento(s)		->	Rdto(s)
			Retribuciones		->	Retrib
			Contribuyente		-> 	Ctye
			Numero				->	Num
			Importe				->	Imp
	-->
	<!--DECLARACIONES GENERICAS-->
	<xs:complexType name="tipo_Doc">
		<xs:sequence>
			<xs:element name="CodModelo" type="tipo_CodModelo"/>
			<xs:element name="Ejercicio" type="xs:int" fixed="2013"/>
			<xs:element name="VER" type="tipo_IdDoc20" minOccurs="0"/>
			<xs:element name="SO" type="tipo_IdDoc40" minOccurs="0"/>
			<xs:element name="Justif" type="tipo_Justificante" minOccurs="0"/>
			<xs:element name="RefAEAT" type="tipo_IdDoc20Ref" minOccurs="0"/>
			<xs:element name="IdentClienteEEDD" type="tipo_IdDoc20" minOccurs="0"/>
			<xs:element name="FechaHora" minOccurs="0"/>
			<xs:element name="NumExp" minOccurs="0"/>
			<xs:element name="CodElec" minOccurs="0"/>
		</xs:sequence>
	</xs:complexType>
	<xs:simpleType name="tipo_CodModelo">
		<xs:restriction base="xs:string">
			<xs:length value="3"/>
			<xs:pattern value="390"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_IdDoc20">
		<xs:restriction base="xs:string">
			<xs:maxLength value="20"/>
			<xs:pattern value="([0-9]|[A-Z]|Ñ|Ç|\s|\.|&amp;|\-|,|'|/|:|;|_|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_IdDoc20Ref">
		<xs:restriction base="xs:string">
			<xs:maxLength value="20"/>
			<xs:pattern value="([0-9]|[A-Z]|Ñ|Ç|\s|\.|&amp;|\-|,|'|/|:|;|_|\(|\))*"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_IdDoc40">
		<xs:restriction base="xs:string">
			<xs:maxLength value="40"/>
			<xs:pattern value="([0-9]|[A-Z]|Ñ|Ç|\s|\.|&amp;|\-|,|'|/|:|;|_|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Nif">
		<xs:restriction base="xs:string">
			<xs:length value="9"/>
			<xs:pattern value="([A-Z]|[0-9]){9}"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Porcentaje">
		<xs:restriction base="xs:decimal">
			<xs:minInclusive value="0.01"/>
			<xs:maxInclusive value="100.00"/>
			<xs:fractionDigits value="2"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_NumGrupo">
		<xs:restriction base="xs:string">
			<xs:maxLength value="7"/>
			<xs:pattern value="([0-9]|[A-Z]|Ñ|Ç|\s|\.|&amp;|\-|,|'|/|:|;|_|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:complexType name="tipo_GrupoEntidades">
		<xs:sequence>
			<xs:element name="GrupoEntidades">
				<xs:complexType/>
			</xs:element>
			<xs:element name="NumGrupo" type="tipo_NumGrupo"/>
			<xs:choice>
				<xs:element name="Dominante">
					<xs:complexType/>
				</xs:element>
				<xs:element name="Dependiente">
					<xs:complexType/>
				</xs:element>
			</xs:choice>
			<xs:choice>
				<xs:element name="Art.6.5_SI">
					<xs:complexType/>
				</xs:element>
				<xs:element name="Art.6.5_NO">
					<xs:complexType/>
				</xs:element>
			</xs:choice>
			<xs:element name="NIFEntidadDominante" type="tipo_Nif" minOccurs="0"/>
			<xs:choice>
				<xs:element name="UltAutoliquid_SI">
					<xs:complexType/>
				</xs:element>
				<xs:element name="UltAutoliquid_NO">
					<xs:complexType/>
				</xs:element>
			</xs:choice>
		</xs:sequence>
	</xs:complexType>
	<xs:simpleType name="tipo_AgrariasCod">
		<xs:restriction base="xs:string">
			<xs:length value="2"/>
			<xs:pattern value="([0-9]|\s){2}"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_IndiceCorrector">
		<xs:restriction base="xs:decimal">
			<xs:fractionDigits value="2"/>
			<xs:pattern value="(0.0|0.00|1.0|1.00|1.25|1.5|1.50|1.35)"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_InCuota">
		<xs:restriction base="xs:decimal">
			<xs:minInclusive value="0.00000"/>
			<xs:maxInclusive value="0.99999"/>
			<xs:fractionDigits value="5"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_ImpPositivo">
		<xs:restriction base="xs:decimal">
			<xs:minInclusive value="0.01"/>
			<xs:maxInclusive value="999999999999999.99"/>
			<xs:fractionDigits value="2"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_ImpNegativo">
		<xs:restriction base="xs:decimal">
			<xs:minInclusive value="-999999999999999.99"/>
			<xs:maxInclusive value="999999999999999.99"/>
			<xs:fractionDigits value="2"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_vacio">
		<xs:restriction base="xs:string">
			<xs:maxLength value="0"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_ImpNegativoMasEspacio">
		<xs:union memberTypes="tipo_ImpNegativo tipo_vacio"/>
	</xs:simpleType>
	<xs:simpleType name="tipo_Nombre">
		<xs:restriction base="xs:string">
			<xs:maxLength value="15"/>
			<xs:whiteSpace value="collapse"/>
			<xs:pattern value="([A-Z]|Ñ|Ç|\s|\.|\-|_|:|,|'|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_CNAE">
		<xs:restriction base="xs:string">
			<xs:length value="3"/>
			<xs:pattern value="([0-9]){3}"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Justificante">
		<xs:restriction base="xs:string">
			<xs:length value="13"/>
			<xs:pattern value="([0-9]){13}"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Dia">
		<xs:restriction base="xs:integer">
			<xs:minInclusive value="1"/>
			<xs:maxInclusive value="31"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Mes">
		<xs:restriction base="xs:string">
			<xs:maxLength value="10"/>
			<xs:pattern value="([A-Z]|Ñ|Ç|\s|\.|\-|,|')+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Anno">
		<xs:restriction base="xs:integer">
			<xs:minInclusive value="2013"/>
			<xs:maxInclusive value="9999"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:complexType name="tipo_Fecha">
		<xs:sequence>
			<xs:element name="Dia" type="tipo_Dia"/>
			<xs:element name="Mes" type="tipo_Mes"/>
			<xs:element name="Anno" type="tipo_Anno"/>
		</xs:sequence>
	</xs:complexType>
	<xs:simpleType name="tipo_SG">
		<xs:restriction base="xs:string">
			<xs:maxLength value="2"/>
			<xs:pattern value="([A-Z])+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_NombreViaPublica">
		<xs:restriction base="xs:string">
			<xs:maxLength value="17"/>
			<xs:pattern value="([0-9]|[A-Z]|Ñ|Ç|\s|\.|&amp;|\-|,|'|/|:|;|_|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Numero">
		<xs:restriction base="xs:string">
			<xs:maxLength value="5"/>
			<xs:pattern value="([0-9]|[A-Z]|Ñ|Ç|\s|\.|&amp;|\-|,|'|/|:|;|_|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Escalera">
		<xs:restriction base="xs:string">
			<xs:maxLength value="2"/>
			<xs:pattern value="([0-9]|[A-Z]|Ñ|Ç|\s|\.|&amp;|\-|,|'|/|:|;|_|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Piso">
		<xs:restriction base="xs:string">
			<xs:maxLength value="2"/>
			<xs:pattern value="([0-9]|[A-Z]|Ñ|Ç|\s|\.|&amp;|\-|,|'|/|:|;|_|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Puerta">
		<xs:restriction base="xs:string">
			<xs:maxLength value="2"/>
			<xs:pattern value="([0-9]|[A-Z]|Ñ|Ç|\s|\.|&amp;|\-|,|'|/|:|;|_|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Telefono">
		<xs:restriction base="xs:string">
			<xs:maxLength value="9"/>
			<xs:pattern value="([0-9]|\s|\.|&amp;|\-|,|'|/|:|;|_|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_CodigoPostal">
		<xs:restriction base="xs:string">
			<xs:maxLength value="5"/>
			<xs:pattern value="([0-9])+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_RazonSocialConjunta">
		<xs:restriction base="xs:string">
			<xs:maxLength value="37"/>
			<xs:pattern value="([0-9]|[A-Z]|Ñ|Ç|\s|\.|&amp;|\-|,|'|/|:|;|_|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_RazonSocial">
		<xs:restriction base="xs:string">
			<xs:maxLength value="37"/>
			<xs:pattern value="([0-9]|[A-Z]|Ñ|Ç|\s|\.|&amp;|\-|,|'|/|:|;|_|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Municipio">
		<xs:restriction base="xs:string">
			<xs:maxLength value="20"/>
			<xs:pattern value="([A-Z]|Ñ|Ç|\s|\.|\-|_|:|,|'|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_CodigoProvincia">
		<xs:restriction base="xs:string">
			<xs:maxLength value="2"/>
			<xs:pattern value="([0-9])+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Localidad">
		<xs:restriction base="xs:string">
			<xs:maxLength value="26"/>
			<xs:pattern value="([A-Z]|Ñ|Ç|\s|\.|\-|_|:|,|'|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Epigrafe">
		<xs:restriction base="xs:string">
			<xs:maxLength value="5"/>
			<xs:pattern value="([0-9]|[A-Z]|Ñ|Ç|\s|\.|&amp;|\-|,|'|/|:|;|_|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_NumModulo">
		<xs:restriction base="xs:string">
			<xs:maxLength value="1"/>
			<xs:pattern value="([1-7])"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Clave">
		<xs:restriction base="xs:string">
			<xs:maxLength value="1"/>
			<xs:pattern value="([0-6]|\s)"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_ActProrratas">
		<xs:restriction base="xs:string">
			<xs:maxLength value="40"/>
			<xs:pattern value="([0-9]|[A-Z]|Ñ|Ç|\s|\.|&amp;|\-|,|'|/|:|;|_|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Descripcion">
		<xs:restriction base="xs:string">
			<xs:maxLength value="40"/>
			<xs:pattern value="([0-9]|[A-Z]|Ñ|Ç|\s|\.|&amp;|\-|,|'|/|:|;|\(|\)|_|´)+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_Notaria">
		<xs:restriction base="xs:string">
			<xs:maxLength value="12"/>
			<xs:pattern value="([0-9]|[A-Z]|Ñ|Ç|\s|\.|&amp;|\-|,|'|/|:|;|_|\(|\))+"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:simpleType name="tipo_NombreRepresentanteJuridica">
		<xs:restriction base="xs:string">
			<xs:maxLength value="36"/>
			<xs:pattern value="([0-9]|[A-Z]|Ñ|Ç|\s|\.|&amp;|\-|,|'|/|:|;|_|\(|\))*"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:complexType name="tipo_Domicilio">
		<xs:sequence>
			<xs:element name="SG" type="tipo_SG" minOccurs="0"/>
			<xs:element name="ViaPublica" type="tipo_NombreViaPublica" minOccurs="0"/>
			<xs:element name="Num" type="tipo_Numero" minOccurs="0"/>
			<xs:element name="Esc" type="tipo_Escalera" minOccurs="0"/>
			<xs:element name="Piso" type="tipo_Piso" minOccurs="0"/>
			<xs:element name="Puerta" type="tipo_Puerta" minOccurs="0"/>
			<xs:element name="Telefono" type="tipo_Telefono" minOccurs="0"/>
			<xs:element name="CPostal" type="tipo_CodigoPostal" minOccurs="0"/>
			<xs:element name="Municipio" type="tipo_Municipio" minOccurs="0"/>
			<xs:element name="CodProv" type="tipo_CodigoProvincia" minOccurs="0"/>
		</xs:sequence>
	</xs:complexType>
	<xs:complexType name="tipo_PersonaFisica">
		<xs:sequence>
			<xs:element name="Ident" type="tipo_IdentificacionPersonaFisica"/>
		</xs:sequence>
	</xs:complexType>
	<xs:complexType name="tipo_RepresentanteFisica">
		<xs:sequence>
			<xs:element name="Ident" type="tipo_IdentificacionPersonaJuridica" minOccurs="0"/>
			<xs:element name="Domicilio" type="tipo_Domicilio" minOccurs="0"/>
		</xs:sequence>
	</xs:complexType>
	<xs:complexType name="tipo_RepresentanteJuridica">
		<xs:sequence>
			<xs:element name="Nombre" type="tipo_NombreRepresentanteJuridica" minOccurs="0"/>
			<xs:element name="NIF" type="tipo_Nif" minOccurs="0"/>
			<xs:element name="FechaPoder" type="tipo_DiaMesAnno" minOccurs="0"/>
			<xs:element name="Notaria" type="tipo_Notaria" minOccurs="0"/>
		</xs:sequence>
	</xs:complexType>
	<xs:simpleType name="tipo_DiaMesAnno">
		<xs:restriction base="xs:string">
			<xs:maxLength value="10"/>
			<xs:pattern value="([0-9]){2}/([0-9]){2}/([0-9]){4}"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:complexType name="tipo_PersonaJuridica">
		<xs:sequence>
			<xs:element name="IdentPersJuridica" type="tipo_IdentificacionPersonaJuridica"/>
		</xs:sequence>
	</xs:complexType>
	<xs:complexType name="tipo_IdentificacionPersonaFisica">
		<xs:sequence>
			<xs:element name="NIF" type="tipo_Nif"/>
			<xs:element name="Ape1" type="tipo_Nombre"/>
			<xs:element name="Ape2" type="tipo_Nombre" minOccurs="0"/>
			<xs:element name="Nombre" type="tipo_Nombre"/>
		</xs:sequence>
	</xs:complexType>
	<xs:complexType name="tipo_IdentificacionPersonaJuridica">
		<xs:sequence>
			<xs:element name="NIF" type="tipo_Nif"/>
			<xs:element name="RazonSocial" type="tipo_RazonSocial"/>
		</xs:sequence>
	</xs:complexType>
	<xs:complexType name="tipo_BaseImponible_y_Cuota">
		<xs:sequence>
			<xs:element name="BI" type="tipo_ImpNegativo" minOccurs="0"/>
			<xs:element name="Cuota" type="tipo_ImpNegativo" minOccurs="0"/>
		</xs:sequence>
	</xs:complexType>
	<xs:simpleType name="tipo_Prorrata">
		<xs:restriction base="xs:string">
			<xs:maxLength value="1"/>
			<xs:pattern value="(E|G)"/>
		</xs:restriction>
	</xs:simpleType>
	<xs:element name="AEATIVA2013">
		<xs:complexType>
			<xs:sequence>
				<xs:element name="IdDoc" type="tipo_Doc"/>
				<xs:element name="DatIdent">
					<xs:complexType>
						<xs:sequence>
							<xs:choice>
								<xs:element name="PersFisica" type="tipo_PersonaFisica"/>
								<xs:element name="PersJuridica" type="tipo_PersonaJuridica"/>
							</xs:choice>
							<xs:element name="Telefono" type="tipo_Telefono" minOccurs="0"/>
						</xs:sequence>
					</xs:complexType>
				</xs:element>
				<xs:element name="Devengo">
					<xs:complexType>
						<xs:sequence>
							<xs:element name="Ejercicio" type="xs:int" fixed="2013"/>
							<xs:choice>
								<xs:element name="ConcursoUltPer_SI">
									<xs:complexType/>
								</xs:element>
								<xs:element name="ConcursoUltPer_NO">
									<xs:complexType/>
								</xs:element>
							</xs:choice>
							<xs:element name="DecSustitutiva" minOccurs="0">
								<xs:complexType/>
							</xs:element>
							<xs:element name="JustDecAnterior" type="tipo_Justificante" minOccurs="0"/>
							<xs:element name="RegDevMensual" minOccurs="0">
								<xs:complexType/>
							</xs:element>
							<xs:element name="RegGrupoEntidades" type="tipo_GrupoEntidades" minOccurs="0"/>
						</xs:sequence>
					</xs:complexType>
				</xs:element>
				<xs:element name="DatEstadisticos">
					<xs:complexType>
						<xs:sequence>
							<xs:element name="Pral">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="Descripcion" type="tipo_Descripcion" minOccurs="0"/>
										<xs:element name="Clave" type="tipo_Clave"/>
										<xs:element name="Epigrafe" type="tipo_Epigrafe" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="Otras" minOccurs="0" maxOccurs="5">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="Descripcion" type="tipo_Descripcion" minOccurs="0"/>
										<xs:element name="Clave" type="tipo_Clave"/>
										<xs:element name="Epigrafe" type="tipo_Epigrafe" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="OpTercerasPax" minOccurs="0">
								<xs:complexType/>
							</xs:element>
							<xs:element name="Conjunta" minOccurs="0">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="NIF" type="tipo_Nif" minOccurs="0"/>
										<xs:element name="RazonSocial" type="tipo_RazonSocialConjunta" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
						</xs:sequence>
					</xs:complexType>
				</xs:element>
				<xs:choice minOccurs="0">
					<xs:element name="RepresentanteFisica" type="tipo_RepresentanteFisica" minOccurs="0"/>
					<xs:element name="RepresentanteJuridica" type="tipo_RepresentanteJuridica" minOccurs="0" maxOccurs="3"/>
				</xs:choice>
				<xs:element name="RegGeneral" minOccurs="0">
					<xs:complexType>
						<xs:sequence>
							<xs:element name="BaseImponibleyCuota" minOccurs="0">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="RegOrdinario" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="Tipo4" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo8" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo10" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo18" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo21" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="OpIntragrupo" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="Tipo4" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo8" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo10" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo18" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo21" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="RegBienesUsados" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="Tipo4" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo8" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo10" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo18" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo21" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="RegAgViajes" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="Tipo18" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo21" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="AdqIntracomBienes" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="Tipo4" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo8" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo10" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo18" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo21" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="AdqIntracomServicios" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="Tipo4" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo8" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo10" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo18" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo21" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="IVAdevengadoInversionSP" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="TipoX" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="ModBasesyCuotas" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="TipoX" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="ModBasesyCuotasConcursoAcreedores" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="TipoX" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="TotalBasesyCuotasIVA" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="TipoX" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="RecargoEquivalencia" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="Tipo05" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo1" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo14" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo4" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo52" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo175" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="ModRecargoEquivalencia" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="TipoX" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="ModRecargoEquivalenciaConcursoAcreedores" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="TipoX" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="TotalCuotasIVA" type="tipo_ImpNegativo" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="Deducciones" minOccurs="0">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="OpInterioresBienesServiciosCorrientes" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="Tipo4" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo7" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo8" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo10" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo16" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo18" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo21" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Total" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="OpIntragrupoCorrientes" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="Tipo4" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo7" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo8" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo10" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo16" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo18" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo21" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Total" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="OpInterioresBienesInversion" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="Tipo4" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo7" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo8" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo10" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo16" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo18" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo21" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Total" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="OpIntragrupoBienesInversion" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="Tipo4" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo7" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo8" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo10" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo16" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo18" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo21" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Total" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="ImportacionesBienesCorrientes" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="Tipo4" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo7" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo8" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo10" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo16" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo18" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo21" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Total" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="ImportacionesBienesInversion" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="Tipo4" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo7" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo8" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo10" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo16" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo18" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo21" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Total" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="AdqIntracomunitariasBienesCorrientes" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="Tipo4" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo7" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo8" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo10" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo16" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo18" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo21" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Total" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="AdqIntracomunitariasBienesInversion" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="Tipo4" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo7" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo8" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo10" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo16" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo18" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo21" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Total" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="AdqIntracomunitariasServicios" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="Tipo4" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo7" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo8" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo10" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo16" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo18" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Tipo21" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
													<xs:element name="Total" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="ComRegAgricGanadPesca" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="TipoX" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="RectifDeducciones" minOccurs="0">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="TipoX" type="tipo_BaseImponible_y_Cuota"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="RegularizInversiones" type="tipo_ImpNegativo" minOccurs="0"/>
										<xs:element name="RegularizPorcProrrata" type="tipo_ImpNegativo" minOccurs="0"/>
										<xs:element name="SumDeducciones" type="tipo_ImpNegativo" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="ResRegGeneral" type="tipo_ImpNegativoMasEspacio" minOccurs="0"/>
						</xs:sequence>
					</xs:complexType>
				</xs:element>
				<xs:element name="RegSimplificado" minOccurs="0">
					<xs:complexType>
						<xs:sequence>
							<xs:element name="Actividad" minOccurs="0" maxOccurs="6">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="Epigrafe" type="tipo_Epigrafe"/>
										<xs:element name="Modulo" minOccurs="0" maxOccurs="7">
											<xs:complexType>
												<xs:sequence>
													<xs:element name="NumModulo" type="tipo_NumModulo"/>
													<xs:element name="Unidades" type="tipo_ImpPositivo"/>
													<xs:element name="Importe" type="tipo_ImpPositivo"/>
												</xs:sequence>
											</xs:complexType>
										</xs:element>
										<xs:element name="CuotaDevengada" type="tipo_ImpPositivo" minOccurs="0"/>
										<xs:element name="Lorca2013" type="tipo_ImpPositivo" minOccurs="0"/>
										<xs:element name="CuotaSoportada" type="tipo_ImpPositivo" minOccurs="0"/>
										<xs:element name="IndiceCorrector" type="tipo_IndiceCorrector" minOccurs="0"/>
										<xs:element name="Resultado" type="tipo_ImpNegativo" minOccurs="0"/>
										<xs:element name="PorcCuotaMinima" type="tipo_Porcentaje" minOccurs="0"/>
										<xs:element name="DevCuotaSopOtrosPaises" type="tipo_ImpPositivo" minOccurs="0"/>
										<xs:element name="CuotaMinima" type="tipo_ImpPositivo" minOccurs="0"/>
										<xs:element name="CuotaRegSimplificado" type="tipo_ImpPositivo" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="ActAgricGanadForest" minOccurs="0" maxOccurs="5">
								<xs:complexType>
									<xs:sequence minOccurs="0">
										<xs:element name="Codigo" type="tipo_AgrariasCod"/>
										<xs:element name="VolIngresos" type="tipo_ImpPositivo" minOccurs="0"/>
										<xs:element name="IndCuota" type="tipo_InCuota" minOccurs="0"/>
										<xs:element name="CuotaDevengada" type="tipo_ImpPositivo" minOccurs="0"/>
										<xs:element name="CuotasSoportadas" type="tipo_ImpPositivo" minOccurs="0"/>
										<xs:element name="CuotaRegSimplificado" type="tipo_ImpNegativo" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="IvaDevengado" minOccurs="0">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="SumaCuotasNoAgric" type="tipo_ImpPositivo" minOccurs="0"/>
										<xs:element name="SumaCuotasAgric" type="tipo_ImpNegativo" minOccurs="0"/>
										<xs:element name="AdqIntracomunitarias" type="tipo_ImpNegativo" minOccurs="0"/>
										<xs:element name="InversionSujetoPasivo" type="tipo_ImpNegativo" minOccurs="0"/>
										<xs:element name="EntregasActivosFijos" type="tipo_ImpNegativo" minOccurs="0"/>
										<xs:element name="TotalCuota" type="tipo_ImpNegativo"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="IvaDeducible" minOccurs="0">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="IVASoportadoAdqActivosFijos" type="tipo_ImpNegativo" minOccurs="0"/>
										<xs:element name="RegBienesInversion" type="tipo_ImpNegativo" minOccurs="0"/>
										<xs:element name="SumaDeducciones" type="tipo_ImpNegativo"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="ResRegimenSimplificado" type="tipo_ImpNegativo" minOccurs="0"/>
						</xs:sequence>
					</xs:complexType>
				</xs:element>
				<xs:choice>
					<xs:element name="LiqAnual" minOccurs="0">
						<xs:complexType>
							<xs:sequence>
								<xs:element name="SumResultados" type="tipo_ImpNegativo" minOccurs="0"/>
								<xs:element name="CompCuotasEjercicioAnterior" type="tipo_ImpPositivo" minOccurs="0"/>
								<xs:element name="ResLiquidacion" type="tipo_ImpNegativo" minOccurs="0"/>
							</xs:sequence>
						</xs:complexType>
					</xs:element>
					<xs:element name="Administraciones" minOccurs="0">
						<xs:complexType>
							<xs:sequence>
								<xs:element name="Comun" type="tipo_Porcentaje" minOccurs="0"/>
								<xs:element name="ArabaAlava" type="tipo_Porcentaje" minOccurs="0"/>
								<xs:element name="Gipuzkoa" type="tipo_Porcentaje" minOccurs="0"/>
								<xs:element name="Bizkaia" type="tipo_Porcentaje" minOccurs="0"/>
								<xs:element name="Navarra" type="tipo_Porcentaje" minOccurs="0"/>
								<xs:element name="SumResultados" type="tipo_ImpNegativo" minOccurs="0"/>
								<xs:element name="ResTerrComun" type="tipo_ImpNegativo" minOccurs="0"/>
								<xs:element name="ComCuotasEjercicioAnteriorTerrComun" type="tipo_ImpPositivo" minOccurs="0"/>
								<xs:element name="ResLiqAnualTerrComun" type="tipo_ImpNegativo" minOccurs="0"/>
							</xs:sequence>
						</xs:complexType>
					</xs:element>
				</xs:choice>
				<xs:element name="ResLiquidaciones" minOccurs="0">
					<xs:complexType>
						<xs:sequence>
							<xs:element name="PerNoRegGrupos" minOccurs="0">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="TotIngresosIVA" type="tipo_ImpPositivo" minOccurs="0"/>
										<xs:element name="TotDevIVA_SP_RegDevMensual" type="tipo_ImpPositivo" minOccurs="0"/>
										<xs:element name="ExclusionBaja" minOccurs="0">
											<xs:complexType/>
										</xs:element>
										<xs:element name="TotDevAdqElemTrans" type="tipo_ImpPositivo" minOccurs="0"/>
										<xs:element name="ImporteACompensarUltimoPeriodo" type="tipo_ImpPositivo" minOccurs="0"/>
										<xs:element name="ImporteADevolverUltimoPeriodo" type="tipo_ImpPositivo" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="PerSiRegGrupos" minOccurs="0">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="TotResulPositivos322" type="tipo_ImpPositivo" minOccurs="0"/>
										<xs:element name="TotResulNegativos322" type="tipo_ImpPositivo" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
						</xs:sequence>
					</xs:complexType>
				</xs:element>
				<xs:element name="VolOperaciones" minOccurs="0">
					<xs:complexType>
						<xs:sequence>
							<xs:element name="OpRegGeneral" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="EntregasIntracomunitariasExentas" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="ExportacionesExentasConDrchoDeduccion" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="OpExentasSinDrchoDeduccion" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="OpNoSujetas" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="EntregasBienesInstalacionOtrosEM" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="OpRegSimplificado" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="OpRegEspAgricPescGanad" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="OpRegEspRecEquivalencia" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="OpRegEspBienesUsados" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="OpRegEspAgViajes" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="EntregasBienesInmuebles" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="EntregasBienesInversion" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="TotalVolOp" type="tipo_ImpNegativo" minOccurs="0"/>
						</xs:sequence>
					</xs:complexType>
				</xs:element>
				<xs:element name="OpEspecificas" minOccurs="0">
					<xs:complexType>
						<xs:sequence>
							<xs:element name="AdqInterioresExentas" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="AdqIntracomunitariasExentas" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="ImportacionesExentas" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="BasesIVASoportadoNoDeducible" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="OpSujetas" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="EntregasInteriores" type="tipo_ImpPositivo" minOccurs="0"/>
							<xs:element name="ServInversionSP" type="tipo_ImpPositivo" minOccurs="0"/>
						</xs:sequence>
					</xs:complexType>
				</xs:element>
				<xs:element name="Prorratas" minOccurs="0">
					<xs:complexType>
						<xs:sequence>
							<xs:element name="Pro" maxOccurs="30">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="Actividad" type="tipo_ActProrratas" minOccurs="0"/>
										<xs:element name="CNAE" type="tipo_CNAE"/>
										<xs:element name="ImpOper" type="tipo_ImpPositivo" minOccurs="0"/>
										<xs:element name="ImpOperConDrchoDed" type="tipo_ImpPositivo" minOccurs="0"/>
										<xs:element name="Tipo" type="tipo_Prorrata" minOccurs="0"/>
										<xs:element name="Porc" type="tipo_Porcentaje" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
						</xs:sequence>
					</xs:complexType>
				</xs:element>
				<xs:element name="IVADeducibleGrupo1" minOccurs="0">
					<xs:complexType>
						<xs:sequence>
							<xs:element name="OpInteriores" minOccurs="0">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="BienesyServiciosCorrientes" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
										<xs:element name="BienesInversion" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="Importaciones" minOccurs="0">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="BienesCorrientes" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
										<xs:element name="BienesInversion" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="AdqIntracomunitarias" minOccurs="0">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="BienesCorrientes" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
										<xs:element name="BienesInversion" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="CompRegEspAgricGanadPesca" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
							<xs:element name="RectDeducciones" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
							<xs:element name="RegInversiones" type="tipo_ImpNegativo" minOccurs="0"/>
							<xs:element name="SumaDeducciones" type="tipo_ImpNegativo" minOccurs="0"/>
						</xs:sequence>
					</xs:complexType>
				</xs:element>
				<xs:element name="IVADeducibleGrupo2" minOccurs="0">
					<xs:complexType>
						<xs:sequence>
							<xs:element name="OpInteriores" minOccurs="0">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="BienesyServiciosCorrientes" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
										<xs:element name="BienesInversion" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="Importaciones" minOccurs="0">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="BienesCorrientes" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
										<xs:element name="BienesInversion" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="AdqIntracomunitarias" minOccurs="0">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="BienesCorrientes" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
										<xs:element name="BienesInversion" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="CompRegEspAgricGanadPesca" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
							<xs:element name="RectDeducciones" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
							<xs:element name="RegInversiones" type="tipo_ImpNegativo" minOccurs="0"/>
							<xs:element name="SumaDeducciones" type="tipo_ImpNegativo" minOccurs="0"/>
						</xs:sequence>
					</xs:complexType>
				</xs:element>
				<xs:element name="IVADeducibleGrupo3" minOccurs="0">
					<xs:complexType>
						<xs:sequence>
							<xs:element name="OpInteriores" minOccurs="0">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="BienesyServiciosCorrientes" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
										<xs:element name="BienesInversion" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="Importaciones" minOccurs="0">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="BienesCorrientes" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
										<xs:element name="BienesInversion" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="AdqIntracomunitarias" minOccurs="0">
								<xs:complexType>
									<xs:sequence>
										<xs:element name="BienesCorrientes" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
										<xs:element name="BienesInversion" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
									</xs:sequence>
								</xs:complexType>
							</xs:element>
							<xs:element name="CompRegEspAgricGanadPesca" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
							<xs:element name="RectDeducciones" type="tipo_BaseImponible_y_Cuota" minOccurs="0"/>
							<xs:element name="RegInversiones" type="tipo_ImpNegativo" minOccurs="0"/>
							<xs:element name="SumaDeducciones" type="tipo_ImpNegativo" minOccurs="0"/>
						</xs:sequence>
					</xs:complexType>
				</xs:element>
				<xs:element name="Sello" type="tipo_IdDoc20" minOccurs="0"/>
			</xs:sequence>
		</xs:complexType>
	</xs:element>
</xs:schema>