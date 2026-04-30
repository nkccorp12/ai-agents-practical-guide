# R1 -- Frontier-Modell-Capabilities (Stand 30. April 2026)

> Recherche fuer Buch "AI Agents Practical Guide" v1.3
> Methodik: WebSearch + WebFetch der offiziellen Anbieter-Doku (platform.claude.com, developers.openai.com, ai.google.dev). Drittquellen (BenchLM, OpenRouter, Artificial Analysis) nur zur Plausibilisierung.
> Stand-Datum aller Felder: **2026-04-30**, sofern nicht abweichend annotiert.

---

## 1. Anthropic

### Claude Opus 4.7 (`claude-opus-4-7`)

| Feld | Wert | Stand | Quelle |
|---|---|---|---|
| Kontextfenster | 1.000.000 Tokens (Input, voller Preis ueber gesamten Bereich) | 2026-04-30 | Anthropic Models Overview |
| Max Output | 128.000 Tokens (sync); bis 300k via `output-300k-2026-03-24` Beta-Header (Batch API) | 2026-04-30 | Anthropic Models Overview |
| Modalitaeten | Text-In/Out, Image-In (max **2576px / 3.75MP** -- neu in 4.7, ggue. 1568px in 4.6), PDF-In, kein Audio/Video nativ | 2026-04-30 | What's new in Opus 4.7 |
| Prompt-Caching | TTLs: **5min** (1.25x base) und **1h** (2x base). Cache-Read: **0.1x** (90% Discount). Min. cacheable: **4.096 Tokens**. Max **4 Cache-Breakpoints** pro Request. Default-TTL ist 5min (silent change Maerz 2026). | 2026-04-30 | Anthropic Prompt Caching Docs |
| Reasoning-Modus | **Adaptive Thinking** (offiziell, ersetzt Extended Thinking). Aktivierung: `thinking: {type: "adaptive"}` + `output_config: {effort: "low\|medium\|high\|xhigh"}`. Off by default. Manual `budget_tokens` -> 400 Error. Thinking-Tokens werden voll abgerechnet (auch bei `display: omitted`). | 2026-04-30 | What's new + Adaptive Thinking Docs |
| Tool-Calling | Parallel: ja. Streaming: ja. Schema: JSON Schema. Server-side Tools: web_search, web_fetch, code_execution, computer_use, bash, text_editor, memory. **Task Budgets** (Beta): advisory Token-Cap fuer komplette Agent-Loop. | 2026-04-30 | Tool Use Docs |
| Native Citations | Ja, via `citations` Beta -- automatische Quellenangaben aus Dokumenten. | 2026-04-30 | Anthropic Docs |
| Pricing (USD/1M) | Input **$5** / Output **$25** / 5m-Cache-Write $6.25 / 1h-Cache-Write $10 / Cache-Hit $0.50. Batch: $2.50 / $12.50. Fast Mode (nur 4.6): 6x. | 2026-04-30 | Pricing Page |
| Rate Limits Tier 1 | ITPM ~30k, OTPM 8k, ~50 RPM (Opus-Familie shared) | 2026-04-30 | Anthropic Rate-Limits-Doku |
| SDK | **Claude Agent SDK** (rebranding 2025-09-29 vom "Claude Code SDK"). Pkgs: `@anthropic-ai/claude-agent-sdk` (npm), `claude-agent-sdk` (PyPI). Min Version fuer Opus 4.7: v0.2.111. | 2026-04-30 | Agent SDK Overview |

**Hinweis:** Opus 4.7 nutzt neuen Tokenizer -> bis zu **+35% Tokens** fuer denselben Text -> effektive Kosten steigen trotz gleicher Per-Token-Rate.

### Claude Sonnet 4.6 (`claude-sonnet-4-6`)

| Feld | Wert | Stand | Quelle |
|---|---|---|---|
| Kontextfenster | 1.000.000 Tokens (voller Preis) | 2026-04-30 | Models Overview |
| Max Output | 64.000 Tokens (sync); 300k Batch-Beta | 2026-04-30 | Models Overview |
| Modalitaeten | Text, Image (1568px), PDF | 2026-04-30 | Models Overview |
| Prompt-Caching | wie Opus 4.7 (5min/1h, 1.25x/2x/0.1x), Min. **4.096 Tokens** | 2026-04-30 | Prompt Caching |
| Reasoning-Modus | Sowohl **Extended Thinking** (deprecated, aber funktional) als auch **Adaptive Thinking** (empfohlen) | 2026-04-30 | Models Overview |
| Tool-Calling | wie Opus 4.7 (parallel, streaming, JSON Schema, Server-Tools) | 2026-04-30 | Tool Use |
| Native Citations | Ja | 2026-04-30 | Docs |
| Pricing (USD/1M) | Input **$3** / Output **$15** / 5m-Cache-Write $3.75 / 1h-Cache-Write $6 / Hit $0.30. Batch: $1.50 / $7.50. | 2026-04-30 | Pricing |
| Rate Limits Tier 1 | nicht eindeutig dokumentiert (typisch ~50 RPM, ~40k ITPM Sonnet-Familie -- unklar) | -- | -- |
| SDK | Claude Agent SDK | 2026-04-30 | Agent SDK |

### Claude Haiku 4.5 (`claude-haiku-4-5-20251001`, Alias `claude-haiku-4-5`)

| Feld | Wert | Stand | Quelle |
|---|---|---|---|
| Kontextfenster | **200.000 Tokens** (kein 1M) | 2026-04-30 | Models Overview |
| Max Output | 64.000 Tokens | 2026-04-30 | Models Overview |
| Modalitaeten | Text, Image, PDF; computer-use unterstuetzt | 2026-04-30 | Haiku 4.5 News |
| Prompt-Caching | 5min/1h, Min. **4.096 Tokens**, 1.25x/2x/0.1x | 2026-04-30 | Prompt Caching |
| Reasoning-Modus | **Extended Thinking** (Haiku-Linie hat kein Adaptive Thinking) | 2026-04-30 | Models Overview |
| Tool-Calling | parallel, streaming, Server-Tools (web_search, code, bash, computer_use) | 2026-04-30 | Tool Use |
| Native Citations | Ja | 2026-04-30 | Docs |
| Pricing (USD/1M) | Input **$1** / Output **$5** / 5m-Cache-Write $1.25 / 1h $2 / Hit $0.10. Batch: $0.50 / $2.50. | 2026-04-30 | Pricing |
| Rate Limits Tier 1 | typischer Anthropic-Tier-1 (nicht eindeutig dokumentiert pro Modell) | -- | -- |
| SDK | Claude Agent SDK | 2026-04-30 | Agent SDK |

---

## 2. OpenAI

### GPT-5 (`gpt-5`)

| Feld | Wert | Stand | Quelle |
|---|---|---|---|
| Kontextfenster | **400.000 Tokens** (NICHT 1M) | 2026-04-30 | developers.openai.com/api/docs/models/gpt-5 |
| Max Output | 128.000 Tokens. Achtung: realer Input-Cap ~272k, da Output-Reservierung von 128k im 400k-Bucket | 2026-04-30 | OpenAI Community Doku-Diskussion |
| Modalitaeten | Text-In/Out, Image-In. **Kein Audio, kein Video** (laut offiz. Modelseite) | 2026-04-30 | OpenAI |
| Prompt-Caching | **Automatisch** (kein Code), Trigger ab 1.024 Tokens, danach 128er-Schritte. Cached-Input-Pricing siehe unten. Keine TTL-Konfiguration. Hinweis: in-memory Cache-Retention NICHT verfuegbar fuer gpt-5.5+. | 2026-04-30 | OpenAI Prompt Caching |
| Reasoning-Modus | `reasoning.effort`: **minimal, low, medium, high** (4 Stufen). Kostet Tokens (als Output abgerechnet). | 2026-04-30 | GPT-5 Modelseite |
| Tool-Calling | Function Calling, parallel, streaming, Structured Outputs. Server-Tools (Responses API): web_search, file_search, image_gen, code_interpreter, MCP. **Kein computer-use, kein hosted shell.** | 2026-04-30 | OpenAI |
| Native Citations | Via Responses API (file_search returns document refs) | 2026-04-30 | OpenAI |
| Pricing (USD/1M) | Input **$1.25** / Cached Input **$0.125** (90% Rabatt) / Output **$10.00** | 2026-04-30 | OpenAI Pricing |
| Rate Limits Tier 1 | **500k TPM**, ~1.000 RPM, 1.5M Batch-TPM (nach Sept-2025 Erhoehung) | 2026-04-30 | OpenAI Devs / Simon Willison |
| SDK | OpenAI Python/Node SDK + **OpenAI Agents SDK** (separate Library fuer Agent-Loops) | 2026-04-30 | OpenAI |

### GPT-5 mini (`gpt-5-mini`)

| Feld | Wert | Stand | Quelle |
|---|---|---|---|
| Kontextfenster | 400.000 Tokens | 2026-04-30 | developers.openai.com |
| Max Output | 128.000 Tokens | 2026-04-30 | OpenAI |
| Modalitaeten | Text, Image | 2026-04-30 | OpenAI |
| Prompt-Caching | wie GPT-5 (auto, ab 1.024 Tokens) | 2026-04-30 | OpenAI |
| Reasoning-Modus | `reasoning.effort` minimal/low/medium/high | 2026-04-30 | OpenAI |
| Tool-Calling | wie GPT-5 | 2026-04-30 | OpenAI |
| Native Citations | wie GPT-5 | 2026-04-30 | OpenAI |
| Pricing (USD/1M) | Input ~$0.25 / Output ~$2.00 (exakte Zahlen GPT-5 vs GPT-5.4 unklar in Quellen; siehe Faktencheck unten) | 2026-04-30 | OpenAI Pricing |
| Rate Limits Tier 1 | 500k TPM, 5M Batch (nach Sept-2025 Erhoehung) | 2026-04-30 | OpenAI Devs |
| SDK | OpenAI SDK / Agents SDK | 2026-04-30 | OpenAI |

### GPT-5 nano (`gpt-5-nano`)

| Feld | Wert | Stand | Quelle |
|---|---|---|---|
| Kontextfenster | 400.000 Tokens | 2026-04-30 | developers.openai.com |
| Max Output | 128.000 Tokens | 2026-04-30 | OpenAI |
| Modalitaeten | Text, Image | 2026-04-30 | OpenAI |
| Pricing (USD/1M) | Input ~$0.05 / Output ~$0.40 (sehr guenstig; exakte Werte unklar in Quellen) | 2026-04-30 | OpenAI Pricing |
| Rest | wie GPT-5 mini, deutlich kleineres Modell, fuer Klassifikation/Summarization | 2026-04-30 | OpenAI |

> **Hinweis OpenAI-Familie:** Stand 30.04.2026 sind aktuellere Modelle GPT-5.4 (1.05M Kontext, computer-use nativ) und GPT-5.5 (1M API / 400k Codex) bereits released. Fuer das Buch ist die GPT-5-Basislinie aber relevant, da sie das stabile, dokumentierte Frontier-Modell ist.

---

## 3. Google

### Gemini 3 Pro (`gemini-3-pro-preview`)

| Feld | Wert | Stand | Quelle |
|---|---|---|---|
| Kontextfenster | 1.000.000 Tokens Input | 2026-04-30 | ai.google.dev/gemini-3 |
| Max Output | 64.000 Tokens | 2026-04-30 | Gemini 3 Dev Guide |
| Modalitaeten | Text, Image, **Audio, Video, PDF** -- voll multimodal. `media_resolution` Param fuer Token-Budget pro Input. | 2026-04-30 | Gemini 3 Dev Guide |
| Prompt-Caching | **Context Caching** (explicit). Min. **2.048 Tokens** (Vertex; AI Studio teils 32k). Default TTL **60 Min.** (frei waehlbar). Discount: **75%** auf Cache-Reads. Storage: **$4.50/1M Tokens/h**. | 2026-04-30 | Gemini Caching Docs / Verdent |
| Reasoning-Modus | **Thinking Levels**: `minimal`, `low`, `medium`, `high` (Default = high). Thinking-Tokens werden als Output abgerechnet. | 2026-04-30 | Gemini 3 Dev Guide |
| Tool-Calling | Function Calling, parallel, streaming. Built-in: Google Search, Maps grounding, URL Context, File Search, Code Execution. Kombinierbar mit Function Calling. | 2026-04-30 | Gemini 3 Dev Guide |
| Native Citations | Ja, via Search Grounding (`groundingMetadata` mit Webquellen) | 2026-04-30 | Gemini Docs |
| Pricing (USD/1M) | <=200k: Input **$2** / Output **$12** / Cache-Read $0.20 ; >200k: Input **$4** / Output **$18** / Cache-Read $0.40 | 2026-04-30 | Gemini Pricing |
| Rate Limits Tier 1 | dokumentiert ~50 RPM / 1.000 RPD (Gemini 3 Pro Preview); real teils niedriger (25 RPM / 250 RPD beobachtet) -- **unklar/uneinheitlich** | 2026-04-30 | Google AI Forum |
| SDK | `google-genai` Python/Node SDK; **Vertex AI Agent Builder** + **Google ADK** (Agent Development Kit) | 2026-04-30 | Google |

### Gemini 3 Flash (`gemini-3-flash-preview`)

| Feld | Wert | Stand | Quelle |
|---|---|---|---|
| Kontextfenster | 1.048.576 Tokens (~1M) | 2026-04-30 | Gemini Pricing |
| Max Output | 64.000 Tokens | 2026-04-30 | Gemini 3 Dev Guide |
| Modalitaeten | Text, Image, Audio, Video, PDF | 2026-04-30 | Gemini 3 Dev Guide |
| Prompt-Caching | Implicit Caching (auto) **kostenlos** + Explicit Caching mit Storage. Discount auf Reads: 75%. | 2026-04-30 | Gemini Caching |
| Reasoning-Modus | Thinking Levels minimal/low/medium/high | 2026-04-30 | Gemini |
| Tool-Calling | wie Gemini 3 Pro | 2026-04-30 | Gemini |
| Native Citations | Ja (Search Grounding) | 2026-04-30 | Gemini |
| Pricing (USD/1M) | Input **$0.50** (text/image/video) / **$1.00** (audio) / Output **$3.00** / Cache-Read frei | 2026-04-30 | Gemini Pricing |
| Rate Limits Tier 1 | hoeher als Pro (typischerweise 1.000+ RPM Tier 1) -- nicht exakt dokumentiert | -- | -- |
| SDK | wie Gemini 3 Pro | -- | Google |

### Gemini 3.1 Pro Preview (`gemini-3.1-pro-preview`) -- Bonus

- Kontext: **2M Tokens** Input (Update gegenueber 3 Pro)
- Pricing: identisch zu 3 Pro Tiered ($2/$12 unter 200k, $4/$18 ueber)
- Released April 2026, noch Preview

> **Wichtig (April 2026 Preisaenderung):** Ab 1. April 2026 sind alle Gemini Pro-Modelle **paid-only**. Nur Flash und Flash-Lite haben noch Free-Tier.

---

## 4. Optional -- Open Models

### Mistral Large 3

- **Open Source** (Apache 2.0), 675B total / 41B active params (MoE)
- Kontext: **256K Tokens**
- Released 2025-12-02
- Pricing: self-hosted oder via Mistral La Plateforme (~$2 input / $6 output USD/1M, plausibel aber nicht offiziell verifiziert)
- Tool-Calling: ja, JSON Schema
- Reasoning-Modus: kein dedizierter Mode, klassisches CoT-Prompting

### Llama 4 Maverick

- **Open Source** (Llama Community License)
- Kontext: 1.000.000 Tokens
- Released 2025-04-05
- Pricing: self-hosted (via OpenRouter ~$0.15 input / $0.60 output)
- Modalitaeten: Text, Image (Multimodal-MoE)
- Tool-Calling: ja
- Reasoning: kein dedizierter Mode

---

## 5. Capability-Matrix (Uebersicht)

| Modell | Kontext | Max Out | Audio | Video | PDF | Cache TTLs | Reasoning-Mode | Native Citations | Input $/1M | Output $/1M | SDK |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Claude Opus 4.7 | 1M | 128k | -- | -- | + | 5min/1h | Adaptive Thinking | + | $5 | $25 | Agent SDK |
| Claude Sonnet 4.6 | 1M | 64k | -- | -- | + | 5min/1h | Adaptive + Extended | + | $3 | $15 | Agent SDK |
| Claude Haiku 4.5 | 200k | 64k | -- | -- | + | 5min/1h | Extended Thinking | + | $1 | $5 | Agent SDK |
| GPT-5 | 400k | 128k | -- | -- | (img-only) | auto | reasoning.effort (4) | (Resp API) | $1.25 | $10 | OpenAI/Agents SDK |
| GPT-5 mini | 400k | 128k | -- | -- | (img) | auto | reasoning.effort | -- | ~$0.25 | ~$2.00 | OpenAI |
| GPT-5 nano | 400k | 128k | -- | -- | (img) | auto | reasoning.effort | -- | ~$0.05 | ~$0.40 | OpenAI |
| Gemini 3 Pro | 1M | 64k | + | + | + | 60min default | Thinking Levels (4) | + (Grounding) | $2 (<200k) | $12 (<200k) | google-genai/ADK |
| Gemini 3 Flash | 1M | 64k | + | + | + | implicit free + explicit | Thinking Levels | + | $0.50 | $3.00 | google-genai/ADK |
| Gemini 3.1 Pro | 2M | 64k | + | + | + | wie 3 Pro | Thinking Levels | + | $2 / $4 | $12 / $18 | google-genai/ADK |
| Mistral Large 3 | 256k | -- | -- | -- | -- | -- | -- | -- | OSS | OSS | -- |
| Llama 4 Maverick | 1M | -- | -- | -- | (img) | -- | -- | -- | OSS | OSS | -- |

Legende: `+` = supported, `--` = nicht supported / nicht dokumentiert.

---

## 6. Faktencheck v1.2-Behauptungen

| Behauptung v1.2 | Status | Korrekte Aussage | Quelle |
|---|---|---|---|
| "GPT-5 hat 1M-Token-Kontext" | **FALSCH** | GPT-5 hat **400.000 Tokens** Kontext (Input+Output kombiniert), Max Output 128k. Nur GPT-5.4/5.5 erreichen 1M+. | developers.openai.com/api/docs/models/gpt-5 |
| "Claude 4.7 Opus mit Extended Thinking" | **FALSCH** | Bei Opus 4.7 ist Extended Thinking entfernt (`type: enabled` -> 400 Error). Offizieller Name: **Adaptive Thinking** (`thinking: {type: "adaptive"}` + `effort`). | platform.claude.com/docs/en/build-with-claude/adaptive-thinking + What's-New 4.7 |
| "Gemini 3.0" als Modellname | **FALSCH** | Korrekte Bezeichnung: **Gemini 3 Pro** und **Gemini 3 Flash** (Preview). Daneben **Gemini 3.1 Pro/Flash-Lite**. Es gibt keine "Gemini 3.0" Marke. | ai.google.dev/gemini-api/docs/gemini-3 |
| "Anthropic Claude Agent SDK" | **KORREKT** (Codex-Hinweis "Claude Code SDK" ist FALSCH) | SDK wurde am **2025-09-29** offiziell von "Claude Code SDK" zu **Claude Agent SDK** umbenannt. Pkgs: `@anthropic-ai/claude-agent-sdk`, `claude-agent-sdk`. Claude Code (CLI) ist davon getrennt. | code.claude.com/docs/en/agent-sdk/overview |
| "Prompt-Caching mit 1h TTL" als pauschale Aussage | **TEILWEISE FALSCH** | Provider-spezifisch: **Anthropic** = 5min default + 1h opt-in (2x write). **OpenAI** = automatisch, keine TTL-Konfiguration (Implementierung intern). **Gemini** = explicit caching mit konfigurierbarer TTL (default 60min) plus implicit free auf Flash. Pauschal "1h TTL" stimmt nirgendwo als Default. | Anthropic Caching / OpenAI Caching / Gemini Caching |

---

## 7. Quellen

### Anthropic
- [What's new in Claude Opus 4.7](https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-7)
- [Models Overview](https://platform.claude.com/docs/en/about-claude/models/overview)
- [Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Extended Thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)
- [Adaptive Thinking](https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking)
- [Claude Agent SDK Overview](https://code.claude.com/docs/en/agent-sdk/overview)
- [Claude Agent SDK Migration Guide](https://platform.claude.com/docs/en/agent-sdk/migration-guide)
- [Building Agents with the Claude Agent SDK (Anthropic Eng Blog)](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [Introducing Claude Haiku 4.5](https://www.anthropic.com/news/claude-haiku-4-5)

### OpenAI
- [GPT-5 Model](https://developers.openai.com/api/docs/models/gpt-5)
- [GPT-5 mini Model](https://developers.openai.com/api/docs/models/gpt-5-mini)
- [GPT-5 nano Model](https://developers.openai.com/api/docs/models/gpt-5-nano)
- [API Pricing](https://openai.com/api/pricing/)
- [Prompt Caching Guide](https://developers.openai.com/api/docs/guides/prompt-caching)
- [Prompt Caching Announcement](https://openai.com/index/api-prompt-caching/)
- [GPT-5 Rate Limit Update (OpenAI Devs)](https://x.com/OpenAIDevs/status/1966610846559134140)

### Google
- [Gemini 3 Developer Guide](https://ai.google.dev/gemini-api/docs/gemini-3)
- [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Context Caching](https://ai.google.dev/gemini-api/docs/caching)
- [Rate Limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Vertex AI Pricing (Claude on Vertex)](https://cloud.google.com/vertex-ai/generative-ai/pricing)

### Drittquellen (zur Plausibilisierung)
- [BenchLM Claude Pricing April 2026](https://benchlm.ai/blog/posts/claude-api-pricing)
- [BenchLM OpenAI Pricing April 2026](https://benchlm.ai/blog/posts/openai-api-pricing)
- [Artificial Analysis -- Caching Comparison](https://artificialanalysis.ai/models/caching)
- [Anthropic Cache TTL silently regressed (GitHub Issue 46829)](https://github.com/anthropics/claude-code/issues/46829)
- [The Register: Claude quota drain 2026-04-13](https://www.theregister.com/2026/04/13/claude_code_cache_confusion/)

---

**Erstellt:** 2026-04-30
**Methode:** Offizielle Anbieter-Doku via WebFetch + Cross-Check via WebSearch
**Reviewer-Hinweis:** Werte mit "unklar/nicht dokumentiert" sind explizit markiert -- nicht halluzinieren, sondern beim Anbieter direkt verifizieren.
