"""
Servei de pre-processament d'imatges per millorar OCR
"""
import cv2
import numpy as np
from PIL import Image, ImageEnhance
from typing import Tuple, Optional
import os
import pytesseract


class ImageProcessor:
    """Processador d'imatges amb OpenCV i Pillow"""

    @staticmethod
    def detect_and_fix_rotation(image: np.ndarray) -> np.ndarray:
        """
        Detecta i corregeix la rotació de la imatge
        """
        # Convertir a escala de grisos
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Detectar vores
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)

        # Detectar línies amb Hough Transform
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)

        if lines is not None and len(lines) > 0:
            # Calcular angle mitjà
            angles = []
            for line in lines[:10]:  # Usar les primeres 10 línies
                rho, theta = line[0]
                angle = np.degrees(theta) - 90
                angles.append(angle)

            median_angle = np.median(angles)

            # Si l'angle és significatiu, rotar
            if abs(median_angle) > 0.5:
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                rotated = cv2.warpAffine(image, M, (w, h),
                                         flags=cv2.INTER_CUBIC,
                                         borderMode=cv2.BORDER_REPLICATE)
                return rotated

        return image

    @staticmethod
    def detect_and_fix_orientation(image: np.ndarray) -> np.ndarray:
        """
        Detecta i corregeix orientació de 90/180/270 graus
        Utilitza Tesseract OSD (Orientation and Script Detection)
        """
        try:
            # Convertir a PIL Image per Tesseract
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_image)

            # Detectar orientació amb Tesseract OSD
            try:
                osd = pytesseract.image_to_osd(pil_image)

                # Extreure angle de rotació
                rotation_angle = None
                for line in osd.split('\n'):
                    if 'Rotate:' in line:
                        rotation_angle = int(line.split(':')[1].strip())
                        break

                if rotation_angle is not None and rotation_angle != 0:
                    print(f"🔄 Detectada rotació de {rotation_angle} graus, corregint...")

                    # Rotar la imatge
                    if rotation_angle == 90:
                        rotated = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    elif rotation_angle == 180:
                        rotated = cv2.rotate(image, cv2.ROTATE_180)
                    elif rotation_angle == 270:
                        rotated = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
                    else:
                        rotated = image

                    return rotated

            except Exception as osd_error:
                print(f"⚠️  OSD no ha pogut detectar orientació: {osd_error}")
                # Si OSD falla, provar mètode alternatiu
                return ImageProcessor._detect_orientation_by_text_density(image)

        except Exception as e:
            print(f"⚠️  Error detectant orientació: {e}")

        return image

    @staticmethod
    def _detect_orientation_by_text_density(image: np.ndarray) -> np.ndarray:
        """
        Mètode alternatiu: provar les 4 orientacions i triar la que té més text detectat
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Provar cada orientació
        orientations = [
            (0, image),
            (90, cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)),
            (180, cv2.rotate(image, cv2.ROTATE_180)),
            (270, cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE))
        ]

        best_score = 0
        best_image = image

        for angle, rotated in orientations:
            try:
                # Convertir a PIL
                rgb = cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb)

                # Detectar text amb Tesseract
                text = pytesseract.image_to_string(pil_img)

                # Calcular puntuació (nombre de caràcters alfanumèrics)
                score = sum(c.isalnum() for c in text)

                if score > best_score:
                    best_score = score
                    best_image = rotated
                    if angle != 0:
                        print(f"✅ Millor orientació detectada: {angle}° (score: {score})")

            except Exception as e:
                print(f"⚠️  Error provant orientació {angle}°: {e}")
                continue

        return best_image

    @staticmethod
    def enhance_contrast(image: np.ndarray) -> np.ndarray:
        """
        Millora el contrast de la imatge
        """
        # Convertir a LAB
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        # Aplicar CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)

        # Tornar a combinar
        enhanced_lab = cv2.merge([l, a, b])
        enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

        return enhanced

    @staticmethod
    def denoise(image: np.ndarray) -> np.ndarray:
        """
        Elimina soroll de la imatge
        """
        return cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)

    @staticmethod
    def binarize(image: np.ndarray) -> np.ndarray:
        """
        Converteix a blanc i negre amb threshold adaptatiu
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Threshold adaptatiu
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )

        return binary

    @staticmethod
    def sharpen(image: np.ndarray) -> np.ndarray:
        """
        Millora la nitidesa de la imatge
        """
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]])
        return cv2.filter2D(image, -1, kernel)

    @staticmethod
    def resize_if_needed(image: np.ndarray, max_width: int = 2000) -> np.ndarray:
        """
        Redimensiona la imatge si és massa gran
        """
        height, width = image.shape[:2]

        if width > max_width:
            ratio = max_width / width
            new_width = max_width
            new_height = int(height * ratio)
            resized = cv2.resize(image, (new_width, new_height),
                               interpolation=cv2.INTER_LANCZOS4)
            return resized

        return image

    @staticmethod
    def detect_document_boundaries(image: np.ndarray) -> Optional[np.ndarray]:
        """
        Detecta els límits del document i el retalla
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 75, 200)

        # Trobar contorns
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        # Trobar el contorn més gran
        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)

        # Si el contorn és prou gran (>10% de la imatge)
        image_area = image.shape[0] * image.shape[1]
        if area > image_area * 0.1:
            # Aproximar a un polígon
            peri = cv2.arcLength(largest_contour, True)
            approx = cv2.approxPolyDP(largest_contour, 0.02 * peri, True)

            # Si és un quadrilàter
            if len(approx) == 4:
                return approx

        return None

    @staticmethod
    def perspective_transform(image: np.ndarray, points: np.ndarray) -> np.ndarray:
        """
        Aplica transformació de perspectiva per enderreçar el document
        """
        # Assegurar que points té forma (4, 2)
        if points.shape != (4, 2):
            points = points.reshape(4, 2)

        # Ordenar punts: top-left, top-right, bottom-right, bottom-left
        rect = np.zeros((4, 2), dtype="float32")
        s = points.sum(axis=1)
        rect[0] = points[np.argmin(s)]
        rect[2] = points[np.argmax(s)]

        diff = np.diff(points, axis=1).flatten()
        rect[1] = points[np.argmin(diff)]
        rect[3] = points[np.argmax(diff)]

        # Calcular nova mida
        (tl, tr, br, bl) = rect
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))

        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))

        # Destinació
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]], dtype="float32")

        # Transformació
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

        return warped

    @staticmethod
    def process_for_ocr(image_path: str,
                        output_path: Optional[str] = None,
                        mode: str = "standard") -> str:
        """
        Processa una imatge per millorar OCR

        Args:
            image_path: Path de la imatge d'entrada
            output_path: Path de sortida (opcional)
            mode: "standard", "aggressive", "document"

        Returns:
            Path de la imatge processada
        """
        # Carregar imatge
        image = cv2.imread(image_path)

        if image is None:
            raise ValueError(f"No s'ha pogut carregar la imatge: {image_path}")

        # Path de sortida
        if output_path is None:
            base, ext = os.path.splitext(image_path)
            output_path = f"{base}_processed{ext}"

        # Processar segons mode
        if mode == "document":
            # Intentar detectar i enderreçar document
            boundaries = ImageProcessor.detect_document_boundaries(image)
            if boundaries is not None:
                image = ImageProcessor.perspective_transform(image, boundaries.reshape(4, 2))

        # Processos comuns
        image = ImageProcessor.resize_if_needed(image)

        # Primer corregir orientació de 90/180/270 graus
        image = ImageProcessor.detect_and_fix_orientation(image)

        # Després corregir petites desviacions d'angle
        image = ImageProcessor.detect_and_fix_rotation(image)

        if mode == "aggressive":
            image = ImageProcessor.denoise(image)
            image = ImageProcessor.enhance_contrast(image)
            image = ImageProcessor.sharpen(image)
        elif mode == "standard":
            image = ImageProcessor.enhance_contrast(image)

        # Guardar
        cv2.imwrite(output_path, image)
        print(f"✅ Imatge processada guardada: {output_path}")

        return output_path

    @staticmethod
    def process_for_ocr_pil(image_path: str, output_path: Optional[str] = None) -> str:
        """
        Processament alternatiu amb Pillow (més lleuger)
        """
        if output_path is None:
            base, ext = os.path.splitext(image_path)
            output_path = f"{base}_processed{ext}"

        # Carregar amb Pillow
        image = Image.open(image_path)

        # Convertir a RGB si cal
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Millorar contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)

        # Millorar nitidesa
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)

        # Guardar
        image.save(output_path)
        print(f"✅ Imatge processada (PIL) guardada: {output_path}")

        return output_path


# Singleton
image_processor = ImageProcessor()
