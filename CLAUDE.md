# n8n Port: Daily AI Digest

## Amaç
reference/n8n_workflow.json içindeki n8n akışını Python'a port et.
n8n KULLANILMAYACAK — sadece davranış referansı.

## Kurallar
- Her n8n node'u ayrı bir Python modülüne karşılık gelir. Tek dosyaya toplama.
- Her adım Langfuse'da ayrı observation olacak.
- Langfuse Python SDK **v4** kullan. API:
  `from langfuse import get_client, observe, propagate_attributes`
  `with lf.start_as_current_observation(as_type="span"|"generation", name=...)`
  Şüphe halinde WebFetch:
  https://langfuse.com/docs/observability/sdk/python/instrumentation
- LLM = Anthropic Messages API, model claude-sonnet-4-6.
- Ağ çağrısı yapan her fonksiyon retry + timeout içerecek.
- Her adım JSON serileştirilebilir dict döndürecek (n8n item modeli gibi).
- `--dry-run` bayrağı: LLM ve Telegram çağrılmaz, sahte veri kullanılır.

## Yapma
- Kod yazmadan önce plan sun.
- 200 satırdan uzun dosya üretme.
- .env'i git'e ekleme.