#!/usr/bin/env python3
"""
Test amb imatges reals de DNI i Permís
"""
import sys
import requests
from pathlib import Path

# URL de l'API
API_URL = "http://localhost:8000"  # Canvia a production si cal
# API_URL = "https://ocr-production-abec.up.railway.app"

def test_dni(image_path: str, nom: str):
    """Test DNI"""
    print(f"\n{'='*80}")
    print(f"🧪 TEST DNI: {nom}")
    print(f"{'='*80}")

    with open(image_path, 'rb') as f:
        response = requests.post(
            f"{API_URL}/ocr/dni",
            files={'file': (Path(image_path).name, f, 'image/jpeg')}
        )

    if response.status_code != 200:
        print(f"❌ ERROR HTTP {response.status_code}")
        print(response.text)
        return

    data = response.json()

    print(f"✅ Válido: {data.get('valido')}")
    print(f"📊 Confianza: {data.get('confianza_global')}")
    print(f"🔧 Motor OCR: {data.get('raw', {}).get('ocr_engine')}")

    datos = data.get('datos', {})
    print(f"\n📄 Dades extretes:")
    print(f"  DNI: {datos.get('numero_documento')}")
    print(f"  Nom: {datos.get('nombre_completo')}")
    print(f"  Naixement: {datos.get('fecha_nacimiento')}")

    print(f"\n📍 Adreça:")
    print(f"  Domicili: {datos.get('domicilio') or 'NULL'}")
    print(f"  CP: {datos.get('codigo_postal') or 'NULL'}")
    print(f"  Municipi: {datos.get('municipio') or 'NULL'}")
    print(f"  Província: {datos.get('provincia') or 'NULL'}")

    if data.get('errores_detectados'):
        print(f"\n⚠️  Errors:")
        for err in data['errores_detectados']:
            print(f"  - [{err['severity']}] {err['message']}")


def test_permis(image_path: str):
    """Test Permís de Circulació"""
    print(f"\n{'='*80}")
    print(f"🧪 TEST PERMÍS DE CIRCULACIÓ")
    print(f"{'='*80}")

    with open(image_path, 'rb') as f:
        response = requests.post(
            f"{API_URL}/ocr/permis",
            files={'file': (Path(image_path).name, f, 'image/jpeg')}
        )

    if response.status_code != 200:
        print(f"❌ ERROR HTTP {response.status_code}")
        print(response.text)
        return

    data = response.json()

    print(f"✅ Válido: {data.get('valido')}")
    print(f"📊 Confianza: {data.get('confianza_global')}")
    print(f"🔧 Motor OCR: {data.get('raw', {}).get('ocr_engine')}")

    datos = data.get('datos', {})
    print(f"\n🚗 Dades extretes:")
    print(f"  Matrícula: {datos.get('matricula')}")
    print(f"  Marca: {datos.get('marca')}")
    print(f"  Model: {datos.get('modelo')}")
    print(f"  Tipus vehicle: {datos.get('tipo_vehiculo') or 'NULL'}")

    print(f"\n⚙️  Motor:")
    print(f"  Cilindrada: {datos.get('cilindrada_cc')} cc")
    print(f"  Potència: {datos.get('potencia_kw')} kW")
    print(f"  Combustible: {datos.get('combustible')}")
    print(f"  Emissions CO2: {datos.get('emissions_co2') or 'NULL'} g/km")

    if data.get('errores_detectados'):
        print(f"\n⚠️  Errors:")
        for err in data['errores_detectados']:
            print(f"  - [{err['severity']}] {err['message']}")


if __name__ == "__main__":
    samples_dir = Path("tests/samples DNI")

    # Test DNIs
    print(f"\n🔍 Testant DNIs locals...")
    test_dni(samples_dir / "dni1_kim.jpg", "Kim Frontal")
    test_dni(samples_dir / "dni2_kim.jpg", "Kim Posterior")

    # Test Permís
    print(f"\n🔍 Testant Permís...")
    test_permis(samples_dir / "permis-circulacio.jpg")

    print(f"\n{'='*80}")
    print("✅ Tests completats")
    print(f"{'='*80}\n")
