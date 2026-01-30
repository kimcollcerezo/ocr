# Integració OCR Agent amb GoGestor Backend

Guia completa per integrar l'OCR Agent amb el backend de GoGestor (PHP/Laravel).

## Índex

- [Variables d'entorn](#variables-dentorn)
- [Configuració a Railway](#configuració-a-railway)
- [Service Layer](#service-layer)
- [Exemples d'ús](#exemples-dús)
- [Gestió d'errors](#gestió-derrors)
- [Testing](#testing)
- [Best practices](#best-practices)

---

## Variables d'entorn

### 1. Afegir al fitxer `.env` de GoGestor

```bash
# OCR Agent Configuration
OCR_AGENT_URL=https://ocr-production-abec.up.railway.app
OCR_AGENT_API_KEY=your-ocr-agent-api-key-here
OCR_AGENT_TIMEOUT=30
OCR_AGENT_ENABLED=true
```

### 2. Afegir a Railway (GoGestor Backend)

A Railway Dashboard del projecte GoGestor:

1. Anar a **Variables**
2. Afegir les següents variables:

| Variable | Valor |
|----------|-------|
| `OCR_AGENT_URL` | `https://ocr-production-abec.up.railway.app` |
| `OCR_AGENT_API_KEY` | `your-ocr-agent-api-key-here` |
| `OCR_AGENT_TIMEOUT` | `30` |
| `OCR_AGENT_ENABLED` | `true` |

3. Guardar i redeploy

---

## Configuració a Railway

### Actualitzar configuració de GoGestor

Al fitxer `config/services.php` (o crear si no existeix):

```php
<?php

return [
    // ... altres serveis ...

    'ocr_agent' => [
        'url' => env('OCR_AGENT_URL'),
        'api_key' => env('OCR_AGENT_API_KEY'),
        'timeout' => env('OCR_AGENT_TIMEOUT', 30),
        'enabled' => env('OCR_AGENT_ENABLED', true),
    ],
];
```

---

## Service Layer

### 1. Crear servei `OcrService.php`

Crear el fitxer: `app/Services/OcrService.php`

```php
<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Http\UploadedFile;

class OcrService
{
    protected string $baseUrl;
    protected string $apiKey;
    protected int $timeout;
    protected bool $enabled;

    public function __construct()
    {
        $this->baseUrl = config('services.ocr_agent.url');
        $this->apiKey = config('services.ocr_agent.api_key');
        $this->timeout = config('services.ocr_agent.timeout', 30);
        $this->enabled = config('services.ocr_agent.enabled', true);
    }

    /**
     * Processar DNI (frontal o posterior)
     *
     * @param UploadedFile|string $file - Fitxer o path del fitxer
     * @param bool $preprocess - Aplicar preprocessament
     * @param string $preprocessMode - Mode: standard, aggressive, document
     * @return array|null
     */
    public function processarDNI($file, bool $preprocess = true, string $preprocessMode = 'standard'): ?array
    {
        if (!$this->enabled) {
            Log::warning('OCR Agent està desactivat');
            return null;
        }

        try {
            $response = Http::timeout($this->timeout)
                ->withHeaders(['X-API-Key' => $this->apiKey])
                ->attach(
                    'file',
                    $this->getFileContents($file),
                    $this->getFileName($file)
                )
                ->post("{$this->baseUrl}/ocr/dni", [
                    'preprocess' => $preprocess,
                    'preprocess_mode' => $preprocessMode
                ]);

            if ($response->successful()) {
                $data = $response->json();

                if ($data['success'] ?? false) {
                    Log::info('DNI processat correctament', [
                        'dni' => $data['data']['dni'] ?? null
                    ]);
                    return $data['data'];
                }
            }

            Log::error('Error processant DNI', [
                'status' => $response->status(),
                'body' => $response->body()
            ]);

            return null;

        } catch (\Exception $e) {
            Log::error('Excepció processant DNI: ' . $e->getMessage());
            return null;
        }
    }

    /**
     * Processar Permís de Circulació
     *
     * @param UploadedFile|string $file
     * @param bool $preprocess
     * @param string $preprocessMode
     * @return array|null
     */
    public function processarPermis($file, bool $preprocess = true, string $preprocessMode = 'standard'): ?array
    {
        if (!$this->enabled) {
            Log::warning('OCR Agent està desactivat');
            return null;
        }

        try {
            $response = Http::timeout($this->timeout)
                ->withHeaders(['X-API-Key' => $this->apiKey])
                ->attach(
                    'file',
                    $this->getFileContents($file),
                    $this->getFileName($file)
                )
                ->post("{$this->baseUrl}/ocr/permis", [
                    'preprocess' => $preprocess,
                    'preprocess_mode' => $preprocessMode
                ]);

            if ($response->successful()) {
                $data = $response->json();

                if ($data['success'] ?? false) {
                    Log::info('Permís processat correctament', [
                        'matricula' => $data['data']['matricula'] ?? null
                    ]);
                    return $data['data'];
                }
            }

            Log::error('Error processant Permís', [
                'status' => $response->status(),
                'body' => $response->body()
            ]);

            return null;

        } catch (\Exception $e) {
            Log::error('Excepció processant Permís: ' . $e->getMessage());
            return null;
        }
    }

    /**
     * Health check de l'OCR Agent
     *
     * @return array|null
     */
    public function healthCheck(): ?array
    {
        try {
            $response = Http::timeout(5)
                ->get("{$this->baseUrl}/health");

            if ($response->successful()) {
                return $response->json();
            }

            return null;

        } catch (\Exception $e) {
            Log::error('OCR Agent health check failed: ' . $e->getMessage());
            return null;
        }
    }

    /**
     * Obtenir contingut del fitxer
     */
    protected function getFileContents($file): string
    {
        if ($file instanceof UploadedFile) {
            return file_get_contents($file->getRealPath());
        }

        return file_get_contents($file);
    }

    /**
     * Obtenir nom del fitxer
     */
    protected function getFileName($file): string
    {
        if ($file instanceof UploadedFile) {
            return $file->getClientOriginalName();
        }

        return basename($file);
    }
}
```

### 2. Registrar servei (opcional)

Al fitxer `app/Providers/AppServiceProvider.php`:

```php
<?php

namespace App\Providers;

use Illuminate\Support\ServiceProvider;
use App\Services\OcrService;

class AppServiceProvider extends ServiceProvider
{
    public function register()
    {
        $this->app->singleton(OcrService::class, function ($app) {
            return new OcrService();
        });
    }
}
```

---

## Exemples d'ús

### 1. Des d'un Controller

```php
<?php

namespace App\Http\Controllers;

use App\Services\OcrService;
use Illuminate\Http\Request;

class DocumentController extends Controller
{
    protected OcrService $ocrService;

    public function __construct(OcrService $ocrService)
    {
        $this->ocrService = $ocrService;
    }

    /**
     * Processar DNI pujat per l'usuari
     */
    public function processarDNI(Request $request)
    {
        $request->validate([
            'dni_frontal' => 'required|image|max:10240', // max 10MB
        ]);

        // Processar DNI frontal
        $dniData = $this->ocrService->processarDNI(
            $request->file('dni_frontal'),
            preprocess: true,
            preprocessMode: 'standard'
        );

        if (!$dniData) {
            return response()->json([
                'error' => 'No s\'ha pogut processar el DNI'
            ], 500);
        }

        // Guardar dades a la base de dades
        // ... lògica per guardar ...

        return response()->json([
            'success' => true,
            'data' => $dniData
        ]);
    }

    /**
     * Processar DNI amb frontal i posterior
     */
    public function processarDNIComplet(Request $request)
    {
        $request->validate([
            'dni_frontal' => 'required|image|max:10240',
            'dni_posterior' => 'nullable|image|max:10240',
        ]);

        // Processar frontal
        $frontalData = $this->ocrService->processarDNI(
            $request->file('dni_frontal')
        );

        if (!$frontalData) {
            return response()->json([
                'error' => 'Error processant la part frontal del DNI'
            ], 500);
        }

        // Processar posterior (si existeix)
        $posteriorData = null;
        if ($request->hasFile('dni_posterior')) {
            $posteriorData = $this->ocrService->processarDNI(
                $request->file('dni_posterior')
            );
        }

        // Combinar dades (el posterior sobrescriu el frontal si hi ha conflictes)
        $dniComplet = array_merge($frontalData, $posteriorData ?? []);

        return response()->json([
            'success' => true,
            'data' => [
                'frontal' => $frontalData,
                'posterior' => $posteriorData,
                'combinat' => $dniComplet
            ]
        ]);
    }

    /**
     * Processar Permís de Circulació
     */
    public function processarPermis(Request $request)
    {
        $request->validate([
            'permis' => 'required|image|max:10240',
        ]);

        $permisData = $this->ocrService->processarPermis(
            $request->file('permis')
        );

        if (!$permisData) {
            return response()->json([
                'error' => 'No s\'ha pogut processar el Permís de Circulació'
            ], 500);
        }

        return response()->json([
            'success' => true,
            'data' => $permisData
        ]);
    }
}
```

### 2. Des d'un Command/Job

```php
<?php

namespace App\Console\Commands;

use Illuminate\Console\Command;
use App\Services\OcrService;

class ProcessarDocuments extends Command
{
    protected $signature = 'ocr:processar {path}';
    protected $description = 'Processar documents amb OCR Agent';

    protected OcrService $ocrService;

    public function __construct(OcrService $ocrService)
    {
        parent::__construct();
        $this->ocrService = $ocrService;
    }

    public function handle()
    {
        $path = $this->argument('path');

        if (!file_exists($path)) {
            $this->error("Fitxer no trobat: {$path}");
            return 1;
        }

        $this->info("Processant document: {$path}");

        $data = $this->ocrService->processarDNI($path);

        if ($data) {
            $this->info("DNI: " . ($data['dni'] ?? 'N/A'));
            $this->info("Nom: " . ($data['nom_complet'] ?? 'N/A'));
            $this->info("Confiança: " . ($data['confidence'] ?? 0) . "%");
            return 0;
        }

        $this->error("Error processant el document");
        return 1;
    }
}
```

### 3. Des d'un Model (Event Listener)

```php
<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use App\Services\OcrService;

class Client extends Model
{
    protected static function booted()
    {
        static::updating(function ($client) {
            // Si s'ha pujat un nou DNI, processar-lo automàticament
            if ($client->isDirty('dni_image_path')) {
                $ocrService = app(OcrService::class);
                $dniData = $ocrService->processarDNI($client->dni_image_path);

                if ($dniData) {
                    $client->dni = $dniData['dni'] ?? null;
                    $client->nom_complet = $dniData['nom_complet'] ?? null;
                    $client->data_naixement = $dniData['data_naixement'] ?? null;
                    $client->adreca = $dniData['adreca_completa'] ?? null;
                }
            }
        });
    }
}
```

---

## Gestió d'errors

### Tipus d'errors i com gestionar-los

```php
public function processarDNIAmbValidacio(Request $request)
{
    try {
        $dniData = $this->ocrService->processarDNI(
            $request->file('dni')
        );

        if (!$dniData) {
            return response()->json([
                'error' => 'No s\'ha pogut processar el DNI',
                'message' => 'El servei OCR no està disponible o no ha pogut extreure les dades'
            ], 500);
        }

        // Validar que les dades essencials existeixen
        if (empty($dniData['dni'])) {
            return response()->json([
                'error' => 'DNI no detectat',
                'message' => 'No s\'ha pogut extreure el número de DNI. Prova amb una imatge de millor qualitat.'
            ], 422);
        }

        // Validar format DNI
        if (!preg_match('/^\d{8}[A-Z]$/', $dniData['dni'])) {
            return response()->json([
                'error' => 'Format DNI invàlid',
                'message' => 'El DNI detectat no té un format vàlid',
                'dni_detectat' => $dniData['dni']
            ], 422);
        }

        // Validar confiança mínima (recomanat: 80%)
        if (($dniData['confidence'] ?? 0) < 80) {
            return response()->json([
                'warning' => 'Baixa confiança',
                'message' => 'Les dades s\'han extret amb baixa confiança. Revisa-les manualment.',
                'confidence' => $dniData['confidence'],
                'data' => $dniData
            ], 200);
        }

        return response()->json([
            'success' => true,
            'data' => $dniData
        ]);

    } catch (\Illuminate\Http\Client\ConnectionException $e) {
        Log::error('OCR Agent no accessible: ' . $e->getMessage());

        return response()->json([
            'error' => 'Servei OCR no disponible',
            'message' => 'No s\'ha pogut connectar amb el servei OCR. Intenta-ho més tard.'
        ], 503);

    } catch (\Exception $e) {
        Log::error('Error inesperat processant DNI: ' . $e->getMessage());

        return response()->json([
            'error' => 'Error inesperat',
            'message' => 'S\'ha produït un error processant el document'
        ], 500);
    }
}
```

---

## Testing

### Test unitari del servei

Crear: `tests/Unit/OcrServiceTest.php`

```php
<?php

namespace Tests\Unit;

use Tests\TestCase;
use App\Services\OcrService;
use Illuminate\Support\Facades\Http;

class OcrServiceTest extends TestCase
{
    public function test_health_check()
    {
        Http::fake([
            '*/health' => Http::response([
                'status' => 'healthy',
                'services' => [
                    'tesseract' => true,
                    'google_vision' => true
                ]
            ], 200)
        ]);

        $ocrService = new OcrService();
        $health = $ocrService->healthCheck();

        $this->assertNotNull($health);
        $this->assertEquals('healthy', $health['status']);
    }

    public function test_processar_dni_success()
    {
        Http::fake([
            '*/ocr/dni' => Http::response([
                'success' => true,
                'data' => [
                    'dni' => '12345678A',
                    'nom_complet' => 'TEST USER',
                    'confidence' => 95.0
                ]
            ], 200)
        ]);

        $ocrService = new OcrService();

        // Crear fitxer temporal de test
        $testFile = __DIR__ . '/../fixtures/dni_test.jpg';

        $result = $ocrService->processarDNI($testFile);

        $this->assertNotNull($result);
        $this->assertEquals('12345678A', $result['dni']);
        $this->assertEquals('TEST USER', $result['nom_complet']);
    }
}
```

---

## Best Practices

### 1. Validació d'imatges abans d'enviar

```php
public function validarImatgeDNI(UploadedFile $file): bool
{
    // Validar mida
    if ($file->getSize() > 10 * 1024 * 1024) { // 10MB
        return false;
    }

    // Validar tipus MIME
    $allowedMimes = ['image/jpeg', 'image/jpg', 'image/png'];
    if (!in_array($file->getMimeType(), $allowedMimes)) {
        return false;
    }

    // Validar dimensions mínimes
    $imageInfo = getimagesize($file->getRealPath());
    if ($imageInfo[0] < 800 || $imageInfo[1] < 600) {
        return false; // massa petita
    }

    return true;
}
```

### 2. Cache de resultats

```php
use Illuminate\Support\Facades\Cache;

public function processarDNIAmbCache($file)
{
    // Generar hash del fitxer
    $fileHash = md5_file($file instanceof UploadedFile ?
        $file->getRealPath() : $file);

    // Comprovar cache (24h)
    $cacheKey = "ocr:dni:{$fileHash}";

    return Cache::remember($cacheKey, now()->addDay(), function () use ($file) {
        return $this->ocrService->processarDNI($file);
    });
}
```

### 3. Processar de manera asíncrona (Job)

```php
<?php

namespace App\Jobs;

use App\Services\OcrService;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;

class ProcessarDNIJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $clientId;
    public string $imagePath;

    public function __construct(int $clientId, string $imagePath)
    {
        $this->clientId = $clientId;
        $this->imagePath = $imagePath;
    }

    public function handle(OcrService $ocrService)
    {
        $dniData = $ocrService->processarDNI($this->imagePath);

        if ($dniData) {
            // Actualitzar client amb dades del DNI
            Client::find($this->clientId)->update([
                'dni' => $dniData['dni'] ?? null,
                'nom_complet' => $dniData['nom_complet'] ?? null,
                'data_naixement' => $dniData['data_naixement'] ?? null,
                'adreca' => $dniData['adreca_completa'] ?? null,
            ]);
        }
    }
}

// Utilitzar-lo:
ProcessarDNIJob::dispatch($clientId, $imagePath);
```

### 4. Retry automàtic en cas d'error

```php
public function processarDNIAmbRetry($file, int $maxRetries = 3)
{
    $attempt = 0;

    while ($attempt < $maxRetries) {
        $result = $this->ocrService->processarDNI($file);

        if ($result) {
            return $result;
        }

        $attempt++;

        if ($attempt < $maxRetries) {
            // Esperar progressivament més temps entre intents
            sleep(pow(2, $attempt)); // 2s, 4s, 8s
        }
    }

    return null;
}
```

---

## Troubleshooting

### Problema: Timeout

```php
// Augmentar timeout per imatges grans
$this->ocrService->timeout = 60; // 60 segons
```

### Problema: API Key invàlida

```bash
# Verificar que l'API key és correcta
php artisan tinker
>>> config('services.ocr_agent.api_key')
```

### Problema: Servei no disponible

```php
// Comprovar health
$health = app(OcrService::class)->healthCheck();
dd($health);
```

---

## Resum configuració ràpida

1. **Afegir variables d'entorn** a Railway (GoGestor):
   - `OCR_AGENT_URL=https://ocr-production-abec.up.railway.app`
   - `OCR_AGENT_API_KEY=your-ocr-agent-api-key-here`

2. **Crear `OcrService.php`** amb el codi proporcionat

3. **Utilitzar al controller**:
   ```php
   $dniData = app(OcrService::class)->processarDNI($request->file('dni'));
   ```

4. **Validar resultats** abans de guardar a BD

---

**Documentació completa**: [API.md](./API.md)
