#!/usr/bin/env python3
"""
Test manual del parser DNI per verificar detecció d'adreces
"""
from app.parsers.dni_parser import DNIParser

# Test 1: Adreça en múltiples línies (format clàssic)
text1 = """
ESPAÑA
DOCUMENTO NACIONAL DE IDENTIDAD
DNI 77612097T
APELLIDOS/COGNOMS
COLL CEREZO
NOMBRE/NOM
JOAQUIN
DOMICILIO
CARRER VENDRELL 5
08348 CABRILS
BARCELONA
FECHA DE NACIMIENTO
24 01 1973
"""

print("=" * 80)
print("TEST 1: Adreça en múltiples línies (format clàssic)")
print("=" * 80)
data1, _ = DNIParser.parse(text1)
print(f"✅ Domicilio: {data1.domicilio}")
print(f"✅ Codigo Postal: {data1.codigo_postal}")
print(f"✅ Municipio: {data1.municipio}")
print(f"✅ Provincia: {data1.provincia}")
print()

# Test 2: Adreça en una sola línia (format del log que has passat)
text2 = """
EQUIPO/EQUIP 0805516D1
DOMICILIO/DOMICILI C. ARTAIL 9 ESCB01 08908 VILASSAR DE DALT BARCELONA
LUGAR DE NACIMIENTO
VILASSAR DE DALT
"""

print("=" * 80)
print("TEST 2: Adreça en una sola línia (com el teu log)")
print("=" * 80)
data2, _ = DNIParser.parse(text2)
print(f"✅ Domicilio: {data2.domicilio}")
print(f"✅ Codigo Postal: {data2.codigo_postal}")
print(f"✅ Municipio: {data2.municipio}")
print(f"✅ Provincia: {data2.provincia}")
print()

# Test 3: Format real del teu log (sense CP complet)
text3 = """
EQUIPO/EQUIP 0805516D1
DOMICILIO/DOMICILI C. ARTAIL 9 ESCB01 908 VILASSAR DE DALT BARCELONA
LUGAR DE NACIMIENTO LLOC DE NAIXEMENT
VILASSAR DE DALT BARCELONA
HIJO/A DE FILLA DE
JORDI
ASSUMPCIO
"""

print("=" * 80)
print("TEST 3: Format exacte del teu log (908 en lloc de 08908)")
print("=" * 80)
data3, _ = DNIParser.parse(text3)
print(f"✅ Domicilio: {data3.domicilio}")
print(f"✅ Codigo Postal: {data3.codigo_postal}")
print(f"✅ Municipio: {data3.municipio}")
print(f"✅ Provincia: {data3.provincia}")
print()

# Test 4: Sense adreça (només frontal)
text4 = """
ESPAÑA
DOCUMENTO NACIONAL DE IDENTIDAD
DNI 77612097T
APELLIDOS/COGNOMS
COLL CEREZO
NOMBRE/NOM
JOAQUIN
SEXO/SEXE M
NACIONALIDAD/NACIONALITAT ESP
FECHA DE NACIMIENTO/DATA DE NAIXEMENT
24 01 1973
"""

print("=" * 80)
print("TEST 4: DNI Frontal (sense DOMICILIO)")
print("=" * 80)
data4, _ = DNIParser.parse(text4)
print(f"❌ Domicilio: {data4.domicilio or 'NULL'}")
print(f"❌ Codigo Postal: {data4.codigo_postal or 'NULL'}")
print(f"❌ Municipio: {data4.municipio or 'NULL'}")
print(f"❌ Provincia: {data4.provincia or 'NULL'}")
print("(És correcte que sigui NULL perquè és el frontal)")
print()

print("=" * 80)
print("RESUM")
print("=" * 80)
print(f"Test 1 (múltiples línies): {'✅ PASS' if data1.domicilio and data1.provincia else '❌ FAIL'}")
print(f"Test 2 (una línia amb CP): {'✅ PASS' if data2.domicilio and data2.provincia else '❌ FAIL'}")
print(f"Test 3 (una línia sense CP): {'✅ PASS' if data3.domicilio and data3.provincia else '❌ FAIL'}")
print(f"Test 4 (frontal sense adreça): {'✅ PASS' if not data4.domicilio else '❌ FAIL'}")
