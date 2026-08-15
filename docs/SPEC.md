# SPEC: AI News Daily Monitor — n8n → Python Port

Kaynak: reference/n8n_workflow.json ("AI News Daily Monitor", id 3Jcxl4sB315JKDVn)
n8n çalıştırılmayacak; bu belge yalnızca davranış referansıdır.

## 1. Node Envanteri

| Node adı | Tip | Parametreler | Girdi | Çıktı |
|---|---|---|---|---|
| Schedule Trigger | n8n-nodes-base.scheduleTrigger | cron: `0 8 * * *` | — (tetikleyici) | boş tetik item'ı |
| Google News AI | n8n-nodes-base.rssFeedRead | url: `https://news.google.com/rss/topics/CAAqIAgKIhpDQkFTRFFvSEwyMHZNRzFyZWhJQ1pXNG9BQVAB?hl=en-US&gl=US&ceid=US:en` | Schedule Trigger sinyali | RSS item listesi (title, link, pubDate, content/contentSnippet, ...) |
| Hacker News AI | n8n-nodes-base.rssFeedRead | url: `https://hnrss.org/newest?q=ai&points=10&count=10` | Schedule Trigger sinyali | RSS item listesi |
| Limit Google to 10 | n8n-nodes-base.limit | maxItems: 10 | Google News AI çıktısı | ilk 10 item (varsayılan keep=firstItems) |
| Create News Object | n8n-nodes-base.code (v2, "run once for all items") | jsCode (aşağıda) | Limit Google to 10 **ve** Hacker News AI çıktıları aynı input index'te birleşir | tek item: `{googleNews: [...], hackerNews: [...]}` |
| AI News Summarizer | @n8n/n8n-nodes-langchain.chainLlm | prompt (madde 4'te birebir) | Create News Object çıktısı (`$json.toJsonString()` ile prompt'a gömülür) | `{text: "<markdown digest>"}` |
| OpenAI Chat Model | @n8n/n8n-nodes-langchain.lmChatOpenAi | model: `gpt-4.1-mini` | — (ai_languageModel bağlantısıyla AI News Summarizer'a servis eder) | — |
| Send to Telegram | n8n-nodes-base.telegram | text: `🤖 AI News Daily Digest\n\n{{ $json.text }}`, appendAttribution: false | AI News Summarizer çıktısı (`.text`) | Telegram API gönderim sonucu |
| Quick Reference | n8n-nodes-base.stickyNote | (dokümantasyon notu) | — | — (yürütülebilir node değil, modül eşlemesi yok) |

**Create News Object jsCode (birebir):**
```js
const googleNews = $input.all().filter(item => item.json.title && item.json.title.includes('AI'));
const hackerNews = $input.all().filter(item => item.json.title && item.json.title.includes('AI'));

return [{
  json: {
    googleNews: googleNews.map(item => item.json),
    hackerNews: hackerNews.map(item => item.json)
  }
}];
```

⚠️ **Tespit edilen davranış:** `googleNews` ve `hackerNews` ikisi de aynı
`$input.all()` (Google+Hacker News birleşik akışı) üzerinden aynı filtreyle
hesaplanıyor — kaynağa göre ayrım yapılmıyor. Bu muhtemelen orijinal
workflow'daki bir hata. Bkz. AÇIK SORU #1.

## 2. Yürütme Sırası (topolojik)

```
Schedule Trigger
 ├─→ Google News AI ─→ Limit Google to 10 ─┐
 └─→ Hacker News AI ───────────────────────┴─→ Create News Object ─→ AI News Summarizer ─→ Send to Telegram
                                     OpenAI Chat Model ─(ai_languageModel)─┘
```

Sıra (bir geçerli linearizasyon):
1. Schedule Trigger (tetik)
2. Google News AI ‖ Hacker News AI (paralel, ikisi de sadece trigger'a bağımlı)
3. Limit Google to 10 (Google News AI'a bağımlı)
4. Create News Object (Limit Google to 10 **ve** Hacker News AI'ın ikisinin de bitmesini bekler)
5. AI News Summarizer (Create News Object'e bağımlı; çalışırken OpenAI Chat Model'i LLM sağlayıcı olarak kullanır — OpenAI Chat Model'in kendisi main-flow'da sıralı bir bağımlılığı yoktur, statik config gibi davranır)
6. Send to Telegram (AI News Summarizer'a bağımlı)

## 3. Node → Python Modül Eşlemesi

CLAUDE.md kuralı: her node ayrı modül, tek dosyaya toplanmayacak, dosya 200
satırı geçmeyecek. Önerilen paket yapısı:

| Node | Python modülü | Not |
|---|---|---|
| Schedule Trigger | `src/main.py` (CLI entrypoint) | Gerçek zamanlama OS cron/launchd'e devredilir; script tek seferlik çalıştırılır. Bkz. AÇIK SORU #2. |
| Google News AI | `src/nodes/fetch_google_news.py` | HTTP RSS çekme, retry+timeout |
| Hacker News AI | `src/nodes/fetch_hacker_news.py` | HTTP RSS çekme, retry+timeout |
| Limit Google to 10 | `src/nodes/limit_google_news.py` | Saf transform, ağ çağrısı yok |
| Create News Object | `src/nodes/create_news_object.py` | Saf transform, ağ çağrısı yok |
| AI News Summarizer | `src/nodes/curator.py`, `src/nodes/summarizer.py`, `src/nodes/editor.py` | Tek n8n node'u 3 Python modülüne bölünüyor — madde 4 |
| OpenAI Chat Model | `src/llm_client.py` | Anthropic Messages API wrapper (claude-sonnet-4-6); OpenAI yerine CLAUDE.md kuralı gereği Anthropic kullanılır — bu bir vekalet değişimi, açık soru değil |
| Send to Telegram | `src/nodes/send_telegram.py` | Telegram Bot API çağrısı, retry+timeout |
| Quick Reference (sticky note) | — | Yürütülebilir değil; içeriği bu SPEC'in üst kısmına/README'ye referans not olarak taşınabilir |

## 4. LLM Node'unun Bölünmesi: curator / summarizer / editor

**Orijinal prompt (birebir, `AI News Summarizer` node'undan):**

```
You are an AI news analyst. Summarize the following AI news from Google News and Hacker News into a concise daily digest. Only include articles that are interesting, important, or notable—skip irrelevant or trivial items.

Instructions:

Begin the digest with a Markdown heading:

# AI News Daily Digest – [date]


(use the most relevant date from the articles).
Do not include any filler text before the heading.

Split the digest into two main sections, each as a Markdown subheading:

## Google News
## Hacker News

Within each section, list the top relevant articles using Markdown bullet points. For each article, include:

- **Title:** [Article Title]  
  **Summary:** [Short professional summary of key points/insights]

Maintain a neutral, professional, concise tone highlighting trends, debates, or important developments.

Important: Ensure the entire digest does not exceed 4,000 characters. If needed, prioritize the most interesting/high-impact articles and omit less important items so the digest stays within the limit.

News to summarize:
{{ $json.toJsonString() }}
```

Bu tek prompt üç sorumluluğu birleştiriyor: (a) alaka/önem filtreleme, (b) her
makale için özet yazma, (c) Markdown biçimlendirme + 4000 karakter bütçesi.
Langfuse'da ayrı gözlemlenebilirlik için üç ayrı LLM çağrısına bölünüyor.

### 4.1 curator (`src/nodes/curator.py`)
Sorumluluk: "Only include articles that are interesting, important, or
notable—skip irrelevant or trivial items." + önem sırasına göre kısa liste
çıkarma (özet yazmadan).

**Girdi sözleşmesi:**
```json
{
  "googleNews": [{"title": "str", "link": "str", "pubDate": "str", "content": "str|null"}],
  "hackerNews": [{"title": "str", "link": "str", "pubDate": "str", "content": "str|null"}]
}
```
(Create News Object çıktısıyla birebir aynı şekil.)

**Çıktı JSON şeması:**
```json
{
  "date": "string (ISO-8601, en alakalı makaleden türetilir)",
  "googleNews": [{"title": "str", "link": "str", "pubDate": "str", "reason": "str"}],
  "hackerNews": [{"title": "str", "link": "str", "pubDate": "str", "reason": "str"}]
}
```
Liste önem sırasına göre; sabit sayı zorunlu değil, curator karar verir.

### 4.2 summarizer (`src/nodes/summarizer.py`)
Sorumluluk: "For each article, include: Title + Summary (short professional
summary of key points/insights)"; "neutral, professional, concise tone
highlighting trends, debates, or important developments."

**Girdi sözleşmesi:** curator çıktısı (madde 4.1 çıktı şeması, `reason` alanı
kullanılmayabilir ama taşınabilir).

**Çıktı JSON şeması:**
```json
{
  "date": "string",
  "googleNews": [{"title": "str", "summary": "str"}],
  "hackerNews": [{"title": "str", "summary": "str"}]
}
```

### 4.3 editor (`src/nodes/editor.py`)
Sorumluluk: Markdown birleştirme — `# AI News Daily Digest – [date]` başlığı,
`## Google News` / `## Hacker News` alt başlıkları, `- **Title:** ...
**Summary:** ...` madde formatı, başlıktan önce dolgu metin yok, toplam ≤4000
karakter (gerekirse düşük öncelikli maddeler atılır).

**Girdi sözleşmesi:** summarizer çıktısı (madde 4.2 çıktı şeması).

**Çıktı JSON şeması:**
```json
{
  "text": "string (nihai Markdown digest, ≤4000 karakter)",
  "char_count": "int",
  "truncated": "bool"
}
```
`text` alanı, orijinal n8n akışındaki `AI News Summarizer` çıktısının
`$json.text` alanıyla aynı isimde tutulur — `send_telegram.py` doğrudan bunu
tüketir (`Send to Telegram` node'undaki `{{ $json.text }}` ile birebir eşleşir).

## 5. Langfuse Trace Ağacı

Her çalıştırma = 1 trace. Node-başına-observation kuralı gereği her adım ayrı
span/generation; öneri (düz yapı, ekstra gruplama span'i yok):

```
trace: ai-news-daily-digest  (root)
├─ span: fetch_google_news        (fetch_google_news.py)
├─ span: fetch_hacker_news        (fetch_hacker_news.py)
├─ span: limit_google_news        (limit_google_news.py)
├─ span: create_news_object       (create_news_object.py)
├─ generation: curator            (curator.py, LLM çağrısı)
├─ generation: summarizer         (summarizer.py, LLM çağrısı)
├─ generation: editor             (editor.py, LLM çağrısı)
└─ span: send_telegram            (send_telegram.py)
```

Trace-level metadata: `run_date`, `dry_run`. `propagate_attributes` ile
`run_date`/`dry_run` tüm alt observation'lara yayılır.

Alternatif (madde AÇIK SORU #3): curator/summarizer/editor, `llm_pipeline`
adlı bir sarmalayıcı span altında toplanabilir — okunabilirliği artırır ama
"her node = ayrı observation" kuralını katı yorumlarsak gereksiz bir ekstra
seviye olur. Varsayılan öneri: düz yapı (yukarıdaki gibi).

## 6. CLAUDE.md kurallarının bu akışa uygulanışı (netleştirme, açık soru değil)

- **Retry+timeout gereken modüller** (ağ çağrısı yapanlar): `fetch_google_news`,
  `fetch_hacker_news`, `curator`, `summarizer`, `editor` (Anthropic API),
  `send_telegram` (Telegram Bot API). `limit_google_news` ve
  `create_news_object` saf transform — retry gerekmez.
- **`--dry-run`:** CLAUDE.md'ye göre yalnızca "LLM ve Telegram çağrılmaz,
  sahte veri kullanılır" — yani RSS fetch node'ları (`fetch_google_news`,
  `fetch_hacker_news`) dry-run'da bile gerçek ağ çağrısı yapar; sadece
  curator/summarizer/editor sahte JSON döner ve `send_telegram` gerçek
  gönderim yapmaz (log'lar).
- **Anthropic vekaleti:** Orijinal `OpenAI Chat Model` (gpt-4.1-mini) node'u,
  CLAUDE.md kuralı gereği Anthropic Messages API + claude-sonnet-4-6 ile
  değiştirilir. Bu bir açık soru değil, doğrudan proje kuralı.

## 7. AÇIK SORULAR

1. **Create News Object bug'ı:** `googleNews` ve `hackerNews` alanları
   orijinal kodda kaynağa göre ayrılmıyor (ikisi de aynı birleşik input'tan
   filtreleniyor). Python portunda bu davranış birebir mi korunsun, yoksa
   kaynağa göre doğru ayrım yapılarak mı düzeltilsin?
2. **Schedule Trigger'ın Python karşılığı:** Bu bir CLI script mi olacak
   (OS cron/launchd `0 8 * * *` ile günde bir çağırır), yoksa Python içinde
   bir scheduler (ör. `schedule`/`apscheduler`) çalıştıran uzun ömürlü bir
   process mi? SPEC, CLI-script varsayımıyla yazıldı.
3. **Langfuse trace ağacında gruplama span'i:** curator/summarizer/editor
   düz mü (root'un doğrudan altında) yoksa `llm_pipeline` sarmalayıcı span'i
   altında mı olsun?
4. **RSS çıktı alan seti:** n8n `rssFeedRead` node'unun tam çıktı alanları
   (guid, isoDate, categories, creator vb.) workflow JSON'ında tanımlı değil,
   kullanılan RSS parser kütüphanesine bağlı. Python tarafında hangi
   kütüphane (`feedparser` vb.) kullanılacağına ve hangi alanların
   taşınacağına netlik gerekiyor.
5. **`Limit Google to 10` node'unun neden yalnızca Google News'e uygulandığı,
   Hacker News'e uygulanmadığı** (HN zaten `count=10` ile URL'de sınırlı) —
   davranış olarak doğru anlaşıldı mı, yoksa iki kaynağın da eşit
   limitlenmesi mi beklenir?
