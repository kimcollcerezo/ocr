"""
Parser per extreure dades del Permís de Circulació
"""
import re
from app.models.permis_response import PermisData
from typing import List


class PermisParser:
    """Parser per Permís de Circulació espanyol"""

    MARQUES_CONEGUDES = [
        'SEAT', 'VOLKSWAGEN', 'VW', 'RENAULT', 'PEUGEOT', 'CITROEN', 'CITROËN', 'FORD',
        'OPEL', 'FIAT', 'AUDI', 'BMW', 'MERCEDES', 'TOYOTA', 'NISSAN', 'HYUNDAI',
        'KIA', 'MAZDA', 'HONDA', 'SUZUKI', 'DACIA', 'SKODA', 'VOLVO', 'LAND ROVER'
    ]

    @staticmethod
    def parse(text: str) -> PermisData:
        """
        Parse principal del permís de circulació
        """
        permis_data = PermisData()
        lines = text.split('\n')
        lines = [l.strip() for l in lines if l.strip()]

        # 1. MATRÍCULA
        matricula_patterns = [
            r'\b(\d{4}\s?[A-Z]{3})\b',
            r'\b([A-Z]{1,2}\s?\d{4}\s?[A-Z]{2})\b'
        ]
        for pattern in matricula_patterns:
            match = re.search(pattern, text)
            if match:
                permis_data.matricula = match.group(1).replace(' ', '')
                break

        # 2. MARCA
        for marca in PermisParser.MARQUES_CONEGUDES:
            if re.search(rf'\b{marca}\b', text, re.IGNORECASE):
                permis_data.marca = marca
                break

        # 3. MODEL (després de la marca)
        if permis_data.marca:
            marca_index = text.upper().find(permis_data.marca.upper())
            if marca_index >= 0:
                after_marca = text[marca_index + len(permis_data.marca):marca_index + len(permis_data.marca) + 50]
                model_match = re.search(r'\s+([A-Z][A-Z0-9\s\-]{2,20})', after_marca)
                if model_match:
                    permis_data.model = model_match.group(1).strip()

        # 4. CILINDRADA
        cilindrada_patterns = [
            r'(\d{3,4})\s?(?:cc|cm3|cm³|CC|CM3)',
            r'P\.1[:\s]*(\d{3,4})',
            r'cilindrada.*?(\d{3,4})'
        ]
        for pattern in cilindrada_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                permis_data.cilindrada = int(match.group(1))
                break

        # Si no s'ha trobat, buscar per etiqueta P.1 a les línies següents
        if not permis_data.cilindrada:
            for i, line in enumerate(lines):
                if 'P.1' in line:
                    # Buscar a les properes 3 línies
                    for j in range(1, 4):
                        if i + j < len(lines):
                            next_line = lines[i + j]
                            num_match = re.match(r'^(\d{3,4})$', next_line)
                            if num_match:
                                num = int(num_match.group(1))
                                if 50 <= num <= 10000:
                                    permis_data.cilindrada = num
                                    break
                    if permis_data.cilindrada:
                        break

        # 5. DATA MATRICULACIÓ
        data_matches = re.findall(r'(\d{2})[\\/\-\.](\d{2})[\\/\-\.](\d{4})', text)
        for match in data_matches:
            dd, mm, yyyy = int(match[0]), int(match[1]), int(match[2])
            if 1 <= dd <= 31 and 1 <= mm <= 12 and 1980 <= yyyy <= 2026:
                permis_data.data_matriculacio = f"{dd:02d}/{mm:02d}/{yyyy}"
                break

        # 6. VIN (Número bastidor)
        vin_match = re.search(r'\b([A-HJ-NPR-Z0-9]{17})\b', text)
        if vin_match:
            permis_data.numero_bastidor = vin_match.group(1)

        # Cerca per etiquetes
        for i, line in enumerate(lines):
            line_upper = line.upper()

            # D.1 - Marca
            if not permis_data.marca and ('D.1' in line_upper or 'MARCA' in line_upper):
                if i + 1 < len(lines):
                    next_line = lines[i + 1].upper()
                    for marca in PermisParser.MARQUES_CONEGUDES:
                        if marca in next_line:
                            permis_data.marca = marca
                            break

            # D.3 - Model
            if not permis_data.model and ('D.3' in line_upper or ('MODEL' in line_upper and 'DENOM' in line_upper)):
                if i + 1 < len(lines):
                    permis_data.model = lines[i + 1].strip()

            # C.1.1, C.1.2, C.1.3 - Titular
            if 'C.1.1' in line_upper or 'C.1.2' in line_upper or 'C.1.3' in line_upper:
                if i + 1 < len(lines):
                    if not permis_data.titular_nom:
                        permis_data.titular_nom = lines[i + 1].strip()
                    else:
                        permis_data.titular_nom += " " + lines[i + 1].strip()

        return permis_data


# Singleton
permis_parser = PermisParser()
