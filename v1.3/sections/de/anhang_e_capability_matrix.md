## Anhang E: Modell-Capability-Matrix

Modell-Capabilities ändern sich rasant. Dieser Anhang ist ein Snapshot mit Stand 30.04.2026 und basiert auf den offiziellen Anbieter-Dokumentationen (Anthropic, OpenAI, Google) sowie auf Drittquellen, die im Verzeichnis am Ende dieses Anhangs gelistet sind. Pricing, Rate Limits und Reasoning-Modi werden teils still verändert (Beispiel: Anthropic-Cache-TTL-Default-Wechsel im März 2026). Vor produktivem Einsatz ist es zwingend, die aktuelle Anbieter-Doku gegenzuprüfen, insbesondere für Pricing, Kontextfenster, SDK-Versionen und Rate Limits. Werte, die in den Quellen nicht eindeutig dokumentiert sind, sind explizit als "unklar" markiert und nicht extrapoliert.

### Haupt-Capability-Matrix

| Modell | Anbieter | Kontextfenster (Input/Output) | Multimodal | Caching (TTL) | Reasoning-Modus | Tool-Calling | Native Citations | Pricing (USD/1M Input -> Output) | SDK |
|---|---|---|---|---|---|---|---|---|---|
| Claude Opus 4.7 | Anthropic | 1.000.000 / 128.000 (sync), 300k via Beta-Header | Text, Image (bis 2576px / 3.75MP), PDF | 5min default + 1h opt-in | Adaptive Thinking (`type: adaptive` + `effort` low/medium/high/xhigh) | Parallel, Streaming, Server-Tools (web_search, web_fetch, code, computer_use, bash, text_editor, memory) | Ja (Citations Beta) | $5 -> $25 (Batch $2.50 -> $12.50) | Claude Agent SDK |
| Claude Sonnet 4.6 | Anthropic | 1.000.000 / 64.000 (sync), 300k Batch-Beta | Text, Image (1568px), PDF | 5min default + 1h opt-in | Extended Thinking (`budget_tokens`) und Adaptive Thinking | Parallel, Streaming, Server-Tools | Ja | $3 -> $15 (Batch $1.50 -> $7.50) | Claude Agent SDK |
| Claude Haiku 4.5 | Anthropic | 200.000 / 64.000 | Text, Image, PDF, computer_use | 5min default + 1h opt-in | Extended Thinking (`budget_tokens`); kein Adaptive | Parallel, Streaming, Server-Tools (web_search, code, bash, computer_use) | Ja | $1 -> $5 (Batch $0.50 -> $2.50) | Claude Agent SDK |
| GPT-5 | OpenAI | 400.000 total / 128.000 Output (effektiv ~272k Input nutzbar) | Text, Image; kein Audio, kein Video nativ | Automatisch (keine TTL-Config), Trigger ab 1.024 Tokens | `reasoning.effort`: minimal/low/medium/high (4 Stufen) | Function Calling, parallel, Streaming, Structured Outputs, Server-Tools (web_search, file_search, image_gen, code_interpreter, MCP); kein computer_use | Ja (Responses API, file_search refs) | $1.25 -> $10.00 (Cached Input $0.125) | OpenAI SDK + OpenAI Agents SDK |
| GPT-5 mini | OpenAI | 400.000 / 128.000 | Text, Image | Automatisch (wie GPT-5) | `reasoning.effort` minimal/low/medium/high | wie GPT-5 | wie GPT-5 | ca. $0.25 -> $2.00 (exakte Werte in Quellen unscharf) | OpenAI SDK / Agents SDK |
| Gemini 3 Pro | Google | 1.000.000 / 64.000 | Text, Image, Audio, Video, PDF (`media_resolution`-Param) | Explicit Caching, Default 60min, frei wählbar; Storage $4.50/1M Tokens/h | Thinking Levels: minimal/low/medium/high (Default = high) | Function Calling, parallel, Streaming, Built-in: Google Search, Maps Grounding, URL Context, File Search, Code Execution | Ja (Search Grounding, `groundingMetadata`) | <=200k: $2 -> $12; >200k: $4 -> $18 | google-genai SDK + Vertex AI Agent Builder + Google ADK |
| Gemini 3 Flash | Google | 1.048.576 / 64.000 | Text, Image, Audio, Video, PDF | Implicit Caching kostenlos + Explicit Caching mit Storage | Thinking Levels minimal/low/medium/high | wie Gemini 3 Pro | Ja (Search Grounding) | $0.50 (Text/Image/Video) bzw. $1.00 (Audio) -> $3.00 | google-genai SDK + Google ADK |
| Gemini 3.1 Pro Preview | Google | 2.000.000 / 64.000 | wie Gemini 3 Pro | wie Gemini 3 Pro | Thinking Levels | wie Gemini 3 Pro | Ja | <=200k: $2 -> $12; >200k: $4 -> $18 | google-genai SDK + Google ADK |

Hinweis: GPT-5 nano ist in R1 dokumentiert (400k Kontext, ca. $0.05 -> $0.40), wird hier aber nicht als Hauptzeile geführt, weil die Pricing-Quelle nicht eindeutig ist.

### Wichtige Caveats und Stolperfallen

- **GPT-5 Kontext realistisch nutzbar:** Das nominelle Kontextfenster ist 400.000 Tokens, davon werden 128.000 Tokens für die Output-Reservierung gehalten. Effektiv nutzbar als Input sind etwa 272.000 Tokens. GPT-5 hat damit kein 1M-Kontextfenster.
- **Claude Opus 4.7 Reasoning heisst Adaptive Thinking, nicht Extended Thinking:** Aktivierung erfolgt über `thinking: {type: "adaptive"}` plus `output_config.effort` mit den Stufen low, medium, high, xhigh. Die alte Form mit manuellem `budget_tokens` wirft bei Opus 4.7 einen 400-Error. Thinking-Tokens werden voll als Output abgerechnet, auch wenn `display: omitted` gesetzt ist.
- **Sonnet 4.6 und Haiku 4.5 behalten Extended Thinking:** Beide Modelle akzeptieren weiterhin den klassischen `budget_tokens`-Parameter. Sonnet 4.6 unterstützt zusätzlich Adaptive Thinking. Haiku 4.5 hat kein Adaptive Thinking.
- **Prompt-Caching ist anbieter-spezifisch:** Anthropic bietet 5min als Default und 1h als opt-in (Cache-Write kostet beim 1h-Modus 2x Base-Rate). OpenAI cached automatisch ohne TTL-Konfiguration. Gemini bietet explizites Context Caching mit frei wählbarer TTL (Default 60min) plus implicit Caching kostenlos auf Flash-Modellen.
- **SDK-Naming bei Anthropic:** Das offizielle Agent-SDK heisst seit dem 29.09.2025 **Claude Agent SDK**. Die Pakete heissen `@anthropic-ai/claude-agent-sdk` (npm) und `claude-agent-sdk` (PyPI). "Claude Code" ist die offizielle CLI, nicht das SDK. Der ältere Name "Claude Code SDK" ist nicht mehr korrekt.
- **Anthropic-Tokenizer-Wechsel bei Opus 4.7:** Derselbe Text kann bis zu 35 Prozent mehr Tokens erzeugen als bei Opus 4.6. Effektive Kosten steigen, obwohl die Per-Token-Rate gleich bleibt.
- **Gemini Pro paid-only seit 01.04.2026:** Free-Tier nur noch bei Flash und Flash-Lite.

### Sub-Tabelle: Cache-Hit-Discount

| Anbieter | Cache-Hit-Discount | Mindestgrösse | Notes |
|---|---|---|---|
| Anthropic | 90 Prozent (Cache-Read = 0.1x Base) | 4.096 Tokens | Cache-Write 5min: 1.25x Base; Cache-Write 1h: 2x Base. Maximal 4 Cache-Breakpoints pro Request. Default-TTL ist 5min (silent change März 2026). |
| OpenAI | 90 Prozent (Cached Input = 0.1x Base) | 1.024 Tokens, danach 128er-Schritte | Vollautomatisch, keine Code-Änderung nötig. Keine TTL-Konfiguration. In-memory Cache-Retention nicht für GPT-5.5+ verfügbar. |
| Google | 75 Prozent auf Cache-Reads (Pro), Implicit Caching auf Flash kostenlos | 2.048 Tokens (Vertex), AI Studio teils 32.768 Tokens | Storage-Kosten: $4.50 pro 1M Tokens pro Stunde (zusätzlich zu Cache-Read-Pricing). Default TTL 60min, frei wählbar. |

### Sub-Tabelle: Rate Limits Tier 1

| Modell | RPM | TPM | Notizen |
|---|---|---|---|
| Claude Opus 4.7 | ca. 50 | ITPM ca. 30.000, OTPM 8.000 | Opus-Familie shared. Werte aus Anthropic Rate-Limits-Doku. |
| Claude Sonnet 4.6 | ca. 50 (typisch) | ca. 40.000 ITPM (typisch) | In Quellen nicht eindeutig pro Modell dokumentiert. |
| Claude Haiku 4.5 | typischer Anthropic-Tier-1 | typischer Anthropic-Tier-1 | Pro-Modell-Werte nicht eindeutig dokumentiert. |
| GPT-5 | ca. 1.000 | 500.000 TPM, 1.5M Batch-TPM | Stand nach Erhöhung September 2025. Quelle: OpenAI Devs Twitter. |
| GPT-5 mini | nicht eindeutig | 500.000 TPM, 5M Batch | Stand nach Erhöhung September 2025. |
| Gemini 3 Pro | ca. 50 dokumentiert (real teils 25 RPM beobachtet) | nicht eindeutig | 1.000 RPD dokumentiert (real teils 250 RPD). Quellen widersprüchlich (Google AI Forum). |
| Gemini 3 Flash | typisch >1.000 RPM | nicht eindeutig | Werte nicht exakt dokumentiert. |

### Quellenverzeichnis

**Anthropic**
- What's new in Claude Opus 4.7: https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-7
- Models Overview: https://platform.claude.com/docs/en/about-claude/models/overview
- Pricing: https://platform.claude.com/docs/en/about-claude/pricing
- Prompt Caching: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Extended Thinking: https://platform.claude.com/docs/en/build-with-claude/extended-thinking
- Adaptive Thinking: https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking
- Claude Agent SDK Overview: https://code.claude.com/docs/en/agent-sdk/overview
- Claude Agent SDK Migration Guide: https://platform.claude.com/docs/en/agent-sdk/migration-guide
- Building Agents with the Claude Agent SDK (Eng-Blog): https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk
- Introducing Claude Haiku 4.5: https://www.anthropic.com/news/claude-haiku-4-5

**OpenAI**
- GPT-5 Model: https://developers.openai.com/api/docs/models/gpt-5
- GPT-5 mini Model: https://developers.openai.com/api/docs/models/gpt-5-mini
- GPT-5 nano Model: https://developers.openai.com/api/docs/models/gpt-5-nano
- API Pricing: https://openai.com/api/pricing/
- Prompt Caching Guide: https://developers.openai.com/api/docs/guides/prompt-caching
- Prompt Caching Announcement: https://openai.com/index/api-prompt-caching/
- GPT-5 Rate Limit Update (OpenAI Devs Twitter): https://x.com/OpenAIDevs/status/1966610846559134140

**Google**
- Gemini 3 Developer Guide: https://ai.google.dev/gemini-api/docs/gemini-3
- Gemini API Pricing: https://ai.google.dev/gemini-api/docs/pricing
- Context Caching: https://ai.google.dev/gemini-api/docs/caching
- Rate Limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Vertex AI Pricing (Claude on Vertex): https://cloud.google.com/vertex-ai/generative-ai/pricing

**Drittquellen (zur Plausibilisierung)**
- BenchLM Claude Pricing April 2026: https://benchlm.ai/blog/posts/claude-api-pricing
- BenchLM OpenAI Pricing April 2026: https://benchlm.ai/blog/posts/openai-api-pricing
- Artificial Analysis Caching Comparison: https://artificialanalysis.ai/models/caching
- Anthropic Cache TTL silently regressed (GitHub Issue 46829): https://github.com/anthropics/claude-code/issues/46829
- The Register zum Claude-Quota-Drain 2026-04-13: https://www.theregister.com/2026/04/13/claude_code_cache_confusion/
