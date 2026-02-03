"""
Parser per extreure dades del DNI
"""
import re
from app.models.dni_response import DNIData
from typing import Optional


class DNIParser:
    """Parser per DNI espanyol"""

    # Lletres de validació DNI
    DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"

    @staticmethod
    def validate_dni(dni: str) -> bool:
        """Valida un DNI espanyol"""
        if not re.match(r'^\d{8}[A-Z]$', dni):
            return False

        number = int(dni[:8])
        letter = dni[8]
        expected_letter = DNIParser.DNI_LETTERS[number % 23]

        return letter == expected_letter

    @staticmethod
    def parse_mrz(text: str) -> Optional[DNIData]:
        """
        Parseja la zona MRZ del DNI (part frontal)

        Format MRZ DNI:
        Línia 1: IDESPBHV122738077612097T<<<<<<
        Línia 2: 7301245M2808288ESP<<<<<<<<<<<6
        Línia 3: COLL<CEREZO<<JOAQUIN<<<<<<<<<<
        """
        lines = text.split('\n')

        # Buscar línies MRZ (comencen amb ID)
        mrz_lines = []
        for line in lines:
            clean_line = line.strip().upper()
            if clean_line.startswith('ID') and len(clean_line) >= 30:
                mrz_lines.append(clean_line)
            elif len(mrz_lines) > 0 and len(clean_line) >= 30:
                mrz_lines.append(clean_line)
            elif len(mrz_lines) >= 3:
                break

        if len(mrz_lines) < 3:
            return None

        try:
            # Línia 1: IDESP + altres + DNI
            line1 = mrz_lines[0].replace(' ', '')
            dni_match = re.search(r'(\d{8}[A-Z])', line1)
            dni = dni_match.group(1) if dni_match else None

            # Línia 2: Data naixement + sexe + data caducitat
            line2 = mrz_lines[1].replace(' ', '')
            data_naixement = f"{line2[4:6]}/{line2[2:4]}/{line2[0:2]}"
            sexe = line2[7]
            data_caducitat = f"{line2[12:14]}/{line2[10:12]}/{line2[8:10]}"
            nacionalitat = line2[15:18].replace('<', '').strip()

            # Línia 3: Cognoms i nom
            # Format MRZ: COGNOMS<<NOM (on < és espai dins cognoms/nom, << separa cognoms de nom)
            line3 = mrz_lines[2].replace(' ', '')
            if '<<' in line3:
                parts = line3.split('<<', 1)
                cognoms = parts[0].replace('<', ' ').strip()
                nom = parts[1].replace('<', ' ').strip() if len(parts) > 1 else None
            else:
                # Fallback si no hi ha <<
                cognoms = line3.replace('<', ' ').strip()
                nom = None

            # Convertir dates
            def convert_date(date_str: str) -> str:
                dd, mm, yy = date_str.split('/')
                yyyy = f"19{yy}" if int(yy) > 30 else f"20{yy}"
                return f"{dd}/{mm}/{yyyy}"

            return DNIData(
                dni=dni,
                nom=nom,
                cognoms=cognoms,
                nom_complet=f"{nom} {cognoms}" if nom and cognoms else None,
                data_naixement=convert_date(data_naixement),
                data_caducitat=convert_date(data_caducitat),
                nacionalitat=nacionalitat or "ESP",
                sexe="Home" if sexe == "M" else "Dona" if sexe == "F" else None,
                ocr_engine="tesseract"
            )

        except Exception as e:
            print(f"Error parseig MRZ: {e}")
            return None

    @staticmethod
    def parse_full_text(text: str) -> DNIData:
        """
        Parseja el text complet del DNI buscant camps específics
        """
        dni_data = DNIData()

        # Buscar DNI
        dni_match = re.search(r'\b(\d{8}[A-Z])\b', text)
        if dni_match:
            dni_data.dni = dni_match.group(1)

        # Keywords que indiquen el final d'un camp
        FIELD_KEYWORDS = [
            'APELLIDOS', 'COGNOMS', 'NOMBRE', 'NOM', 'SEXO', 'SEXE',
            'NACIONALIDAD', 'NACIONALITAT', 'FECHA', 'DATA',
            'DOMICILIO', 'DOMICILI', 'LUGAR', 'LLOC', 'PADRE', 'PARE',
            'MADRE', 'MARE', 'DNI', 'EQUIPO', 'EQUIP', 'IDNUM'
        ]

        def read_field_lines(lines, start_idx):
            """Llegeix línies fins trobar el següent keyword o línia buida"""
            field_lines = []
            for j in range(start_idx, len(lines)):
                line_content = lines[j].strip()

                # Aturar si línia buida
                if not line_content:
                    break

                # Aturar si trobem un keyword (excepte si és la primera línia)
                line_upper = line_content.upper()
                if j > start_idx and any(keyword in line_upper for keyword in FIELD_KEYWORDS):
                    break

                field_lines.append(line_content)

            return ' '.join(field_lines)

        # Buscar nom i cognoms
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if 'APELLIDOS' in line.upper() or 'COGNOMS' in line.upper():
                if i + 1 < len(lines):
                    dni_data.cognoms = read_field_lines(lines, i + 1)
            elif 'NOMBRE' in line.upper() or 'NOM' in line.upper():
                # Evitar confusió amb "NOMBRE DEL PADRE" o "NOM DEL PARE"
                if 'PADRE' not in line.upper() and 'PARE' not in line.upper() and 'MADRE' not in line.upper() and 'MARE' not in line.upper():
                    if i + 1 < len(lines):
                        dni_data.nom = read_field_lines(lines, i + 1)

            # Buscar adreça (DOMICILIO / DOMICILI)
            elif 'DOMICILIO' in line.upper() or 'DOMICILI' in line.upper():
                # L'adreça sol estar a les següents línies
                adreca_lines = []
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].strip()
                    # Aturar si trobem keywords no relacionades amb adreça
                    if next_line and not any(keyword in next_line.upper() for keyword in ['FECHA', 'DATA', 'LUGAR', 'LLOC', 'PADRE', 'PARE', 'MADRE', 'MARE', 'EQUIPO', 'EQUIP', 'HIJO', 'FILL']):
                        adreca_lines.append(next_line)
                    else:
                        break

                if adreca_lines:
                    # Províncies espanyoles conegudes
                    PROVINCIES_ESPANYOLES = [
                        'BARCELONA', 'TARRAGONA', 'LLEIDA', 'GIRONA',  # Catalunya
                        'MADRID', 'VALENCIA', 'ALICANTE', 'CASTELLON', 'CASTELLÓ',
                        'SEVILLA', 'MALAGA', 'CADIZ', 'HUELVA', 'CORDOBA', 'GRANADA', 'JAEN', 'ALMERIA',
                        'ZARAGOZA', 'HUESCA', 'TERUEL',
                        'A CORUÑA', 'PONTEVEDRA', 'OURENSE', 'LUGO',
                        'VIZCAYA', 'GUIPUZCOA', 'ALAVA', 'BIZKAIA', 'GIPUZKOA', 'ARABA',
                        'NAVARRA', 'LA RIOJA', 'CANTABRIA', 'ASTURIAS',
                        'MURCIA', 'BADAJOZ', 'CACERES', 'SALAMANCA', 'ZAMORA', 'VALLADOLID',
                        'LEON', 'PALENCIA', 'BURGOS', 'SORIA', 'SEGOVIA', 'AVILA',
                        'TOLEDO', 'CIUDAD REAL', 'CUENCA', 'GUADALAJARA', 'ALBACETE'
                    ]

                    # Primera línia: carrer i número
                    if len(adreca_lines) > 0:
                        # Netejar abreviatures comunes
                        line0 = adreca_lines[0].replace('CRER.', 'CARRER').replace('C/', 'CARRER').replace('C.', 'CARRER')

                        # Intentar separar carrer i número
                        carrer_match = re.match(r'^(.+?)\s+(\d+.*?)$', line0)
                        if carrer_match:
                            dni_data.carrer = carrer_match.group(1).strip()
                            dni_data.numero = carrer_match.group(2).strip()
                        else:
                            dni_data.carrer = line0

                    # Detectar província a la darrera línia
                    provincia_idx = None
                    for idx in range(len(adreca_lines) - 1, 0, -1):
                        line_upper = adreca_lines[idx].upper().strip()
                        if any(prov in line_upper for prov in PROVINCIES_ESPANYOLES):
                            provincia_idx = idx
                            dni_data.provincia = adreca_lines[idx].strip()
                            break

                    # Si hem trobat província, la línia anterior és la població
                    if provincia_idx and provincia_idx > 1:
                        poblacio_line = adreca_lines[provincia_idx - 1]

                        # Treure codi postal si existeix
                        poblacio_line = re.sub(r'^\d{5}\s+', '', poblacio_line)
                        dni_data.poblacio = poblacio_line.strip()

                    # Si no hem trobat província, usar el mètode antic
                    elif len(adreca_lines) > 1:
                        # Format: "POBLACIÓ (PROVÍNCIA)" o "CP POBLACIÓ (PROVÍNCIA)"
                        poblacio_line = adreca_lines[1]

                        # Buscar província entre parèntesis
                        provincia_match = re.search(r'\(([^)]+)\)', poblacio_line)
                        if provincia_match:
                            dni_data.provincia = provincia_match.group(1).strip()
                            # Treure la província per obtenir població
                            poblacio_line = re.sub(r'\s*\([^)]+\)', '', poblacio_line)

                        # Treure codi postal si existeix
                        poblacio_line = re.sub(r'^\d{5}\s+', '', poblacio_line)
                        dni_data.poblacio = poblacio_line.strip()

                        # Tercera línia: província (si no estava entre parèntesis)
                        if len(adreca_lines) > 2 and not dni_data.provincia:
                            dni_data.provincia = adreca_lines[2].strip()

                    # Adreça completa (només primeres 4 línies màxim)
                    dni_data.adreca_completa = ', '.join(adreca_lines[:4])

            # Buscar data de naixement
            elif ('FECHA' in line.upper() and 'NACIMIENTO' in line.upper()) or ('DATA' in line.upper() and 'NAIXEMENT' in line.upper()):
                if i + 1 < len(lines):
                    data_str = lines[i + 1].strip()
                    # Buscar format DD MM YYYY o DD/MM/YYYY
                    date_match = re.search(r'(\d{2})[\s/](\d{2})[\s/](\d{4})', data_str)
                    if date_match:
                        dni_data.data_naixement = f"{date_match.group(1)}/{date_match.group(2)}/{date_match.group(3)}"

            # Buscar sexe
            elif 'SEXO' in line.upper() or 'SEXE' in line.upper():
                if i + 1 < len(lines):
                    sexe_str = lines[i + 1].strip().upper()
                    if 'M' in sexe_str or 'H' in sexe_str:
                        dni_data.sexe = "Home"
                    elif 'F' in sexe_str or 'D' in sexe_str or 'MUJER' in sexe_str or 'DONA' in sexe_str:
                        dni_data.sexe = "Dona"

            # Buscar nacionalitat
            elif 'NACIONALIDAD' in line.upper() or 'NACIONALITAT' in line.upper():
                if i + 1 < len(lines):
                    nac_str = lines[i + 1].strip()
                    # Buscar codi de 3 lletres (ESP, FRA, etc) o nom complet
                    if len(nac_str) <= 3 and nac_str.isalpha():
                        dni_data.nacionalitat = nac_str.upper()
                    elif 'ESPA' in nac_str.upper():
                        dni_data.nacionalitat = "ESP"

            # Buscar lloc de naixement
            elif ('LUGAR' in line.upper() and 'NACIMIENTO' in line.upper()) or ('LLOC' in line.upper() and 'NAIXEMENT' in line.upper()):
                if i + 1 < len(lines):
                    dni_data.lloc_naixement = lines[i + 1].strip()

            # Buscar pare
            elif 'PADRE' in line.upper() or 'PARE' in line.upper():
                if i + 1 < len(lines):
                    dni_data.pare = lines[i + 1].strip()

            # Buscar mare
            elif 'MADRE' in line.upper() or 'MARE' in line.upper():
                if i + 1 < len(lines):
                    dni_data.mare = lines[i + 1].strip()

        # Nom complet
        if dni_data.nom and dni_data.cognoms:
            dni_data.nom_complet = f"{dni_data.nom} {dni_data.cognoms}"

        return dni_data

    @staticmethod
    def parse(text: str) -> DNIData:
        """
        Parse principal que intenta MRZ primer i després completa amb text complet
        """
        # Intentar MRZ primer
        mrz_data = DNIParser.parse_mrz(text)

        if mrz_data and mrz_data.dni:
            # MRZ trobat - completar amb dades addicionals del text complet
            full_text_data = DNIParser.parse_full_text(text)

            # Copiar dades addicionals que no estan al MRZ
            if full_text_data.carrer:
                mrz_data.carrer = full_text_data.carrer
            if full_text_data.numero:
                mrz_data.numero = full_text_data.numero
            if full_text_data.poblacio:
                mrz_data.poblacio = full_text_data.poblacio
            if full_text_data.provincia:
                mrz_data.provincia = full_text_data.provincia
            if full_text_data.adreca_completa:
                mrz_data.adreca_completa = full_text_data.adreca_completa
            if full_text_data.lloc_naixement:
                mrz_data.lloc_naixement = full_text_data.lloc_naixement
            if full_text_data.pare:
                mrz_data.pare = full_text_data.pare
            if full_text_data.mare:
                mrz_data.mare = full_text_data.mare

            # Preferir cognoms de full_text si són millors (amb espais)
            # La MRZ pot tenir errors de lectura dels caràcters < que separen cognoms
            if full_text_data.cognoms and ' ' in full_text_data.cognoms:
                # Si full_text té cognoms amb espai i MRZ no, preferir full_text
                if not mrz_data.cognoms or ' ' not in mrz_data.cognoms:
                    mrz_data.cognoms = full_text_data.cognoms
                    # Recalcular nom_complet
                    if mrz_data.nom:
                        mrz_data.nom_complet = f"{mrz_data.nom} {mrz_data.cognoms}"

            return mrz_data

        # Si MRZ falla, intentar text complet
        return DNIParser.parse_full_text(text)


# Singleton
dni_parser = DNIParser()
