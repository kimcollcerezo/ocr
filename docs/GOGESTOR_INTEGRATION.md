# Integració OCR Agent amb GoGestor Backend

> **Contracte v1** — Resposta unificada amb `valido`, `confianza_global`, `datos`, `errores_detectados`.
> Totes les dates en format ISO 8601 (`YYYY-MM-DD`).
> Última actualització: 2026-02-26

---

## Configuració ràpida

### 1. Variables d'entorn (`.env` GoGestor i Railway)

```bash
OCR_AGENT_URL=https://ocr-production-abec.up.railway.app
OCR_AGENT_TIMEOUT=35
OCR_AGENT_ENABLED=true
```

### 2. `config/services.php`

```php
'ocr_agent' => [
    'url'     => env('OCR_AGENT_URL'),
    'timeout' => env('OCR_AGENT_TIMEOUT', 35),
    'enabled' => env('OCR_AGENT_ENABLED', true),
],
```

---

## OcrService.php (contracte v1)

Crear `app/Services/OcrService.php`:

```php
<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Http\UploadedFile;

class OcrService
{
    protected string $baseUrl;
    protected int $timeout;
    protected bool $enabled;

    public function __construct()
    {
        $this->baseUrl = config('services.ocr_agent.url');
        $this->timeout = (int) config('services.ocr_agent.timeout', 35);
        $this->enabled = (bool) config('services.ocr_agent.enabled', true);
    }

    /**
     * Processar DNI o NIE.
     *
     * Retorna l'array complet del contracte v1:
     *   ['valido' => bool, 'confianza_global' => int, 'datos' => [...], ...]
     * o null si hi ha un error de transport.
     */
    public function processarDNI(
        UploadedFile|string $file,
        bool $preprocess = false,
        string $preprocessMode = 'standard'
    ): ?array {
        if (!$this->enabled) return null;

        try {
            $params = [];
            if ($preprocess) {
                $params['preprocess']      = 'true';
                $params['preprocess_mode'] = $preprocessMode;
            }

            $response = Http::timeout($this->timeout)
                ->attach('file', $this->fileContents($file), $this->fileName($file))
                ->post("{$this->baseUrl}/ocr/dni", $params);

            if (!$response->successful()) {
                Log::error('OCR DNI HTTP error', [
                    'status' => $response->status(),
                    'detail' => $response->json('detail'),
                ]);
                return null;
            }

            $data = $response->json();

            Log::info('OCR DNI processat', [
                'valido'           => $data['valido'] ?? null,
                'confianza_global' => $data['confianza_global'] ?? null,
                'ocr_engine'       => $data['raw']['ocr_engine'] ?? null,
                'errors'           => count($data['errores_detectados'] ?? []),
            ]);

            return $data;

        } catch (\Exception $e) {
            Log::error('OCR DNI excepció: ' . $e->getMessage());
            return null;
        }
    }

    /**
     * Processar NIF/TIF (Targeta Identificació Fiscal).
     *
     * Retorna l'array complet del contracte v1 o null.
     */
    public function processarNIF(
        UploadedFile|string $file,
        bool $preprocess = false,
        string $preprocessMode = 'standard'
    ): ?array {
        if (!$this->enabled) return null;

        try {
            $params = [];
            if ($preprocess) {
                $params['preprocess']      = 'true';
                $params['preprocess_mode'] = $preprocessMode;
            }

            $response = Http::timeout($this->timeout)
                ->attach('file', $this->fileContents($file), $this->fileName($file))
                ->post("{$this->baseUrl}/ocr/nif", $params);

            if (!$response->successful()) {
                Log::error('OCR NIF HTTP error', [
                    'status' => $response->status(),
                    'detail' => $response->json('detail'),
                ]);
                return null;
            }

            $data = $response->json();

            Log::info('OCR NIF processat', [
                'valido'           => $data['valido'] ?? null,
                'confianza_global' => $data['confianza_global'] ?? null,
                'ocr_engine'       => $data['raw']['ocr_engine'] ?? null,
                'errors'           => count($data['errores_detectados'] ?? []),
            ]);

            return $data;

        } catch (\Exception $e) {
            Log::error('OCR NIF excepció: ' . $e->getMessage());
            return null;
        }
    }

    /**
     * Processar Permís de Circulació.
     *
     * Retorna l'array complet del contracte v1 o null.
     */
    public function processarPermis(
        UploadedFile|string $file,
        bool $preprocess = false,
        string $preprocessMode = 'standard'
    ): ?array {
        if (!$this->enabled) return null;

        try {
            $params = [];
            if ($preprocess) {
                $params['preprocess']      = 'true';
                $params['preprocess_mode'] = $preprocessMode;
            }

            $response = Http::timeout($this->timeout)
                ->attach('file', $this->fileContents($file), $this->fileName($file))
                ->post("{$this->baseUrl}/ocr/permis", $params);

            if (!$response->successful()) {
                Log::error('OCR Permís HTTP error', [
                    'status' => $response->status(),
                    'detail' => $response->json('detail'),
                ]);
                return null;
            }

            $data = $response->json();

            Log::info('OCR Permís processat', [
                'valido'           => $data['valido'] ?? null,
                'confianza_global' => $data['confianza_global'] ?? null,
                'ocr_engine'       => $data['raw']['ocr_engine'] ?? null,
                'errors'           => count($data['errores_detectados'] ?? []),
            ]);

            return $data;

        } catch (\Exception $e) {
            Log::error('OCR Permís excepció: ' . $e->getMessage());
            return null;
        }
    }

    public function healthCheck(): ?array
    {
        try {
            $response = Http::timeout(5)->get("{$this->baseUrl}/health");
            return $response->successful() ? $response->json() : null;
        } catch (\Exception $e) {
            return null;
        }
    }

    protected function fileContents(UploadedFile|string $file): string
    {
        return $file instanceof UploadedFile
            ? file_get_contents($file->getRealPath())
            : file_get_contents($file);
    }

    protected function fileName(UploadedFile|string $file): string
    {
        return $file instanceof UploadedFile
            ? $file->getClientOriginalName()
            : basename($file);
    }
}
```

### Registrar singleton (`AppServiceProvider.php`)

```php
$this->app->singleton(OcrService::class);
```

---

## Exemples d'ús

### Processar DNI des d'un controller

```php
use App\Services\OcrService;

class DocumentController extends Controller
{
    public function __construct(protected OcrService $ocr) {}

    public function pujarDNI(Request $request)
    {
        $request->validate([
            'dni' => 'required|image|mimes:jpeg,jpg,png,webp|max:5120',
        ]);

        $resultat = $this->ocr->processarDNI($request->file('dni'));

        if ($resultat === null) {
            return response()->json(['error' => 'Servei OCR no disponible'], 503);
        }

        // Comprovar validesa del document
        if (!$resultat['valido']) {
            $errors = collect($resultat['errores_detectados'])
                ->where('severity', 'critical')
                ->pluck('message')
                ->all();

            return response()->json([
                'error'   => 'Document invàlid',
                'detalls' => $errors,
            ], 422);
        }

        // Avisos no bloquejants (menor d'edat, soroll OCR...)
        $alertes = collect($resultat['alertas'])->pluck('message')->all();

        $datos = $resultat['datos'];

        // Guardar a la base de dades
        $client = Client::updateOrCreate(
            ['numero_documento' => $datos['numero_documento']],
            [
                'nombre'           => $datos['nombre'],
                'apellidos'        => $datos['apellidos'],
                'fecha_nacimiento' => $datos['fecha_nacimiento'], // YYYY-MM-DD
                'fecha_caducidad'  => $datos['fecha_caducidad'],  // YYYY-MM-DD
                'sexo'             => $datos['sexo'],             // M | F | X
                'nacionalidad'     => $datos['nacionalidad'],
                // Adreça (camps separats)
                'calle'            => $datos['calle'],            // "CRER. SALVADOR ESPRIU"
                'numero'           => $datos['numero'],           // "45"
                'piso_puerta'      => $datos['piso_puerta'],      // "P02 0001" | "1º A" | null
                'codigo_postal'    => $datos['codigo_postal'],    // "08328"
                'municipio'        => $datos['municipio'],        // "VILASSAR DE DALT"
                'provincia'        => $datos['provincia'],        // "BARCELONA"
            ]
        );

        return response()->json([
            'success'          => true,
            'confianza_global' => $resultat['confianza_global'],
            'alertes'          => $alertes,
            'client'           => $client,
        ]);
    }

    public function pujarPermis(Request $request)
    {
        $request->validate([
            'permis' => 'required|image|mimes:jpeg,jpg,png,webp|max:5120',
        ]);

        $resultat = $this->ocr->processarPermis($request->file('permis'));

        if ($resultat === null) {
            return response()->json(['error' => 'Servei OCR no disponible'], 503);
        }

        if (!$resultat['valido']) {
            return response()->json([
                'error'   => 'Permís invàlid',
                'detalls' => collect($resultat['errores_detectados'])->pluck('message'),
            ], 422);
        }

        $datos = $resultat['datos'];

        $vehicle = Vehicle::updateOrCreate(
            ['matricula' => $datos['matricula']],
            [
                'numero_bastidor'           => $datos['numero_bastidor'],
                'marca'                     => $datos['marca'],
                'modelo'                    => $datos['modelo'],
                'cilindrada_cc'             => $datos['cilindrada_cc'],
                'potencia_kw'               => $datos['potencia_kw'],
                'potencia_fiscal'           => $datos['potencia_fiscal'],
                'combustible'               => $datos['combustible'],
                'emissions_co2'             => $datos['emissions_co2'],
                'plazas'                    => $datos['plazas'],
                'tipo_vehiculo'             => $datos['tipo_vehiculo'],
                'titular_nombre'            => $datos['titular_nombre'],
                'fecha_matriculacion'       => $datos['fecha_matriculacion'], // YYYY-MM-DD
                'fecha_ultima_transferencia'=> $datos['fecha_ultima_transferencia'], // YYYY-MM-DD
                'proxima_itv'               => $datos['proxima_itv'],         // YYYY-MM-DD
            ]
        );

        return response()->json([
            'success'          => true,
            'confianza_global' => $resultat['confianza_global'],
            'vehicle'          => $vehicle,
        ]);
    }

    public function pujarNIF(Request $request)
    {
        $request->validate([
            'nif' => 'required|image|mimes:jpeg,jpg,png,webp|max:5120',
        ]);

        $resultat = $this->ocr->processarNIF($request->file('nif'));

        if ($resultat === null) {
            return response()->json(['error' => 'Servei OCR no disponible'], 503);
        }

        if (!$resultat['valido']) {
            return response()->json([
                'error'   => 'NIF invàlid',
                'detalls' => collect($resultat['errores_detectados'])->pluck('message'),
            ], 422);
        }

        $datos = $resultat['datos'];

        // Guardar empresa/entitat a la base de dades
        $empresa = Empresa::updateOrCreate(
            ['nif' => $datos['numero_nif']],
            [
                'tipo_nif'             => $datos['tipo_nif'],            // "CIF"
                'razon_social'         => $datos['razon_social'],
                'denominacion'         => $datos['denominacion'],
                'anagrama_comercial'   => $datos['anagrama_comercial'],
                // Domicili Social
                'domicilio_social'     => $datos['domicilio_social'],
                'social_calle'         => $datos['domicilio_social_calle'],
                'social_numero'        => $datos['domicilio_social_numero'],
                'social_piso_puerta'   => $datos['domicilio_social_piso_puerta'],
                'social_cp'            => $datos['domicilio_social_codigo_postal'],
                'social_municipio'     => $datos['domicilio_social_municipio'],
                'social_provincia'     => $datos['domicilio_social_provincia'],
                // Domicili Fiscal (OBLIGATORI)
                'domicilio_fiscal'     => $datos['domicilio_fiscal'],
                'fiscal_calle'         => $datos['domicilio_fiscal_calle'],
                'fiscal_numero'        => $datos['domicilio_fiscal_numero'],
                'fiscal_piso_puerta'   => $datos['domicilio_fiscal_piso_puerta'],
                'fiscal_cp'            => $datos['domicilio_fiscal_codigo_postal'],
                'fiscal_municipio'     => $datos['domicilio_fiscal_municipio'],
                'fiscal_provincia'     => $datos['domicilio_fiscal_provincia'],
                // Dates i AEAT
                'fecha_nif_definitivo' => $datos['fecha_nif_definitivo'], // YYYY-MM-DD
                'administracion_aeat'  => $datos['administracion_aeat'],
                'codigo_electronico'   => $datos['codigo_electronico'],
            ]
        );

        return response()->json([
            'success'          => true,
            'confianza_global' => $resultat['confianza_global'],
            'empresa'          => $empresa,
        ]);
    }
}
```

---

## Gestió d'errors i alertes

### Estructura `ValidationItem` (errores_detectados / alertas)

```json
{
  "code": "DNI_EXPIRED",
  "severity": "critical | error | warning",
  "field": "fecha_caducidad",
  "message": "Document caducat (2020-01-01)",
  "evidence": "2020-01-01",
  "suggested_fix": "Sol·licitar renovació"
}
```

### Regla de negoci

| Situació | `valido` | Acció recomanada |
|----------|----------|------------------|
| `valido: true` + `confianza_global ≥ 90` | ✅ | Acceptar directament |
| `valido: true` + `confianza_global 70–89` | ⚠️ | Acceptar amb avís de revisió |
| `valido: true` + `confianza_global < 70` | ⚠️ | Demanar revisió manual |
| `valido: false` | ❌ | Demanar nou document |

```php
function avaluarOcr(array $resultat): string
{
    if (!$resultat['valido']) {
        return 'INVALIT';
    }
    return match(true) {
        $resultat['confianza_global'] >= 90 => 'ACCEPTAT',
        $resultat['confianza_global'] >= 70 => 'ACCEPTAT_AMB_AVIS',
        default                             => 'REVISAR_MANUALMENT',
    };
}
```

### Codis d'error DNI

| Codi | Gravetat | Significat |
|------|----------|------------|
| `DNI_MISSING_FIELD` | critical / error | Camp mínim absent |
| `DNI_NUMBER_INVALID` | critical | Format DNI/NIE invàlid |
| `DNI_CHECKLETTER_MISMATCH` | critical | Lletra de control incorrecta |
| `DNI_MRZ_MISMATCH` | critical | Discrepància entre text i MRZ |
| `DNI_BIRTHDATE_INVALID` | critical | Data de naixement fora de rang |
| `DNI_EXPIRED` | error | Document caducat |
| `DNI_UNDERAGE` | warning | Titular menor de 18 anys |
| `DNI_NAME_OCR_NOISE` | warning | Caràcters estranys al nom |

### Codis d'error Permís

| Codi | Gravetat | Significat |
|------|----------|------------|
| `VEH_MISSING_FIELD` | critical / error | Camp mínim absent |
| `VEH_PLATE_INVALID` | critical | Format matrícula invàlid |
| `VEH_VIN_INVALID_LENGTH` | critical | VIN sense 17 caràcters |
| `VEH_VIN_INVALID_CHARS` | critical | VIN conté I, O o Q |
| `VEH_OWNER_ID_INVALID` | error | NIF/NIE/CIF titular invàlid |
| `VEH_DATES_INCONSISTENT` | error / warning | Dates incoherents |
| `VEH_VIN_CHECKDIGIT` | warning | Dígit control VIN (normal en UE) |
| `VEH_OCR_SUSPECT` | warning | Soroll OCR en un camp |

---

## Camps de resposta — referència ràpida

### DNI (`datos`)

| Camp | Tipus | Exemple |
|------|-------|---------|
| `numero_documento` | `string\|null` | `"77612097T"` |
| `tipo_numero` | `"DNI"\|"NIE"\|null` | `"DNI"` |
| `nombre` | `string\|null` | `"JOAQUIN"` |
| `apellidos` | `string\|null` | `"COLL CEREZO"` |
| `nombre_completo` | `string\|null` | `"JOAQUIN COLL CEREZO"` |
| `sexo` | `"M"\|"F"\|"X"\|null` | `"M"` |
| `nacionalidad` | `string\|null` | `"ESP"` |
| `fecha_nacimiento` | `string\|null` ISO | `"1973-01-24"` |
| `fecha_caducidad` | `string\|null` ISO | `"2028-08-28"` |
| `domicilio` | `string\|null` | `"CARRER VENDRELL 5"` (deprecated) |
| `calle` | `string\|null` | `"CRER. SALVADOR ESPRIU"` |
| `numero` | `string\|null` | `"45"` |
| `piso_puerta` | `string\|null` | `"P02 0001"`, `"1º A"`, `"2n B"` |
| `municipio` | `string\|null` | `"VILASSAR DE DALT"` |
| `provincia` | `string\|null` | `"BARCELONA"` |
| `codigo_postal` | `string\|null` | `"08328"` |

**Notes sobre l'adreça:**
- **`domicilio`** (deprecated): Adreça completa en un sol camp. Usar `calle`, `numero`, `piso_puerta` en el seu lloc.
- **`calle`**: Nom del carrer sense número (ex: "CRER. SALVADOR ESPRIU", "C. ARTAIL")
- **`numero`**: Número del carrer (ex: "45", "9", "5B")
- **`piso_puerta`**: Pis i porta tal com apareix al DNI. Formats habituals:
  - `"P02 0001"` o `"PO2 0001"` → Pis 02, Porta 0001
  - `"1º A"` o `"1ª B"` → Primer pis, porta A/B
  - `"ESC A 2n 3ª"` → Escala A, 2n pis, porta 3ª
  - `null` si no hi ha pis/porta al DNI
- **Reconstruir adreça completa**: `"{calle} {numero} {piso_puerta}, {codigo_postal} {municipio}, {provincia}"`

### Permís (`datos`)

| Camp | Tipus | Exemple |
|------|-------|---------|
| `matricula` | `string\|null` | `"1177MTM"` |
| `numero_bastidor` | `string\|null` | `"YARKAAC3100018794"` |
| `marca` | `string\|null` | `"TOYOTA"` |
| `modelo` | `string\|null` | `"TOYOTA YARIS"` |
| `categoria` | `string\|null` | `"M1"` |
| `fecha_matriculacion` | `string\|null` ISO | `"2024-08-08"` |
| `titular_nombre` | `string\|null` | `"JOAQUIN COLL CEREZO"` |
| `cilindrada_cc` | `int\|null` | `1490` |
| `potencia_kw` | `float\|null` | `92.0` |
| `potencia_fiscal` | `float\|null` | `125.1` |
| `combustible` | `string\|null` | `"GASOLINA"` |
| `emissions_co2` | `float\|null` | `120.5` |
| `plazas` | `int\|null` | `5` |
| `tipo_vehiculo` | `string\|null` | `"Turisme"` |
| `fecha_ultima_transferencia` | `string\|null` ISO | `"2024-01-15"` |
| `proxima_itv` | `string\|null` ISO | `"2028-08-08"` |

### NIF (`datos`)

| Camp | Tipus | Exemple |
|------|-------|---------|
| `numero_nif` | `string\|null` | `"B76261874"` |
| `tipo_nif` | `string\|null` | `"CIF"` |
| `razon_social` | `string\|null` | `"CASAACTIVA GESTION, S.L."` |
| `denominacion` | `string\|null` | `"CASAACTIVA GESTION, S.L."` |
| `anagrama_comercial` | `string\|null` | `"CASAACTIVA"` |
| **Domicili Social** | | |
| `domicilio_social` | `string\|null` | `"C MOSTEROL, NUM. 7..."` |
| `domicilio_social_calle` | `string\|null` | `"C MOSTEROL"` |
| `domicilio_social_numero` | `string\|null` | `"7"` |
| `domicilio_social_piso_puerta` | `string\|null` | `"1º A"` |
| `domicilio_social_municipio` | `string\|null` | `"TERRASSA"` |
| `domicilio_social_provincia` | `string\|null` | `"BARCELONA"` |
| `domicilio_social_codigo_postal` | `string\|null` | `"08221"` |
| **Domicili Fiscal** | | |
| `domicilio_fiscal` | `string\|null` | `"CALLE ORINOCO, NUM. 5..."` |
| `domicilio_fiscal_calle` | `string\|null` | `"CALLE ORINOCO"` |
| `domicilio_fiscal_numero` | `string\|null` | `"5"` |
| `domicilio_fiscal_piso_puerta` | `string\|null` | `"PLANTA 0, PUERTA 3"` |
| `domicilio_fiscal_municipio` | `string\|null` | `"PALMAS DE GRAN CANARIA"` |
| `domicilio_fiscal_provincia` | `string\|null` | `"LAS"` |
| `domicilio_fiscal_codigo_postal` | `string\|null` | `"35014"` |
| **Dates i AEAT** | | |
| `fecha_nif_definitivo` | `string\|null` ISO | `"2016-07-26"` |
| `fecha_expedicion` | `string\|null` ISO | `"2020-01-15"` |
| `administracion_aeat` | `string\|null` | `"35601 PALMAS G.C"` |
| `codigo_administracion` | `string\|null` | `"35601"` |
| `nombre_administracion` | `string\|null` | `"PALMAS G.C"` |
| `codigo_electronico` | `string\|null` | `"2DCB113CA7F63DC2"` |

**Notes NIF**:
- **`domicilio_fiscal`** és **OBLIGATORI** per `valido: true`
- **`domicilio_social`** és opcional (només algunes targetes)
- Validació CIF amb **algoritme oficial AEAT** (dígit control calculat)
- Tipus entitats per primera lletra: A=SA, B=SL, G=Associació, etc.

### Codis d'error NIF

| Codi | Gravetat | Significat |
|------|----------|------------|
| `NIF_MISSING_FIELD` | critical / error | Camp mínim absent (numero_nif, razon_social, domicilio_fiscal) |
| `NIF_CHECKDIGIT_MISMATCH` | critical | Dígit de control CIF incorrecte (algoritme AEAT) |
| `NIF_INVALID_FORMAT` | critical | Format NIF no reconegut |
| `NIF_DATE_INVALID` | error | Data fora de rang (1980–avui) |
| `NIF_OCR_NOISE` | warning | Caràcters estranys (soroll OCR) |

**Nota**: La validació CIF és més complexa que DNI/NIE. Utilitza l'algoritme oficial AEAT amb suma ponderada dels 7 dígits centrals i validació segons la primera lletra (A/B/E/H només dígit, K/P/Q/S només lletra, altres ambdós).

---

## Testing (Laravel)

```php
// tests/Unit/OcrServiceTest.php
use Illuminate\Support\Facades\Http;

public function test_processar_dni_retorna_contracte_v1(): void
{
    Http::fake([
        '*/ocr/dni' => Http::response([
            'valido'             => true,
            'confianza_global'   => 99,
            'tipo_documento'     => 'dni',
            'datos' => [
                'numero_documento' => '77612097T',
                'nombre'           => 'JOAQUIN',
                'apellidos'        => 'COLL CEREZO',
                'fecha_nacimiento' => '1973-01-24',
                'fecha_caducidad'  => '2028-08-28',
                'sexo'             => 'M',
            ],
            'alertas'            => [],
            'errores_detectados' => [],
            'raw'  => ['ocr_engine' => 'google_vision', 'ocr_confidence' => 95.0],
            'meta' => ['success' => true, 'message' => 'Document processat correctament'],
        ], 200),
    ]);

    $service = app(OcrService::class);
    $result  = $service->processarDNI('/tmp/test_dni.jpg');

    $this->assertNotNull($result);
    $this->assertTrue($result['valido']);
    $this->assertEquals(99, $result['confianza_global']);
    $this->assertEquals('77612097T', $result['datos']['numero_documento']);
    $this->assertEquals('1973-01-24', $result['datos']['fecha_nacimiento']);
}

public function test_processar_dni_error_http_retorna_null(): void
{
    Http::fake(['*/ocr/dni' => Http::response(['detail' => 'Timeout'], 504)]);

    $result = app(OcrService::class)->processarDNI('/tmp/test.jpg');

    $this->assertNull($result);
}
```

---

## Troubleshooting

| Problema | Causa probable | Solució |
|----------|----------------|---------|
| Retorna `null` | Error de connexió o timeout | Verificar `OCR_AGENT_URL` i augmentar `OCR_AGENT_TIMEOUT` |
| `valido: false` + `DNI_EXPIRED` | Document caducat | Informar l'usuari que renovi el document |
| `valido: false` + `VEH_PLATE_INVALID` | Matrícula llegida incorrectament | Provar amb `preprocess=true&preprocess_mode=aggressive` |
| `confianza_global` baix (< 70) | Imatge de baixa qualitat | Demanar foto amb més llum o millor resolució |
| HTTP 413 | Imatge > 5 MB | Redimensionar al client abans d'enviar |
| HTTP 504 | L'OCR ha trigat > 30 s | Reintentar; si persiteix, verificar estat servei |

```bash
# Verificar estat del servei
curl https://ocr-production-abec.up.railway.app/health

# Test ràpid des de terminal
php artisan tinker
>>> app(\App\Services\OcrService::class)->healthCheck()
```

---

**Documentació completa**: [docs/API.md](./API.md)
