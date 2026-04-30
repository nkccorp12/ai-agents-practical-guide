## Appendix E: Model Capability Matrix

Model capabilities change rapidly. This appendix is a snapshot as of 30 April 2026 and is based on the official provider documentation (Anthropic, OpenAI, Google) plus the third-party sources listed at the end. Pricing, rate limits, and reasoning modes are sometimes changed silently (example: Anthropic cache TTL default change in March 2026). Before any production rollout you must verify the current provider documentation, especially for pricing, context window, SDK versions, and rate limits. Values that are not unambiguously documented in the sources are explicitly marked as "unclear" and are not extrapolated.

### Main Capability Matrix

| Model | Provider | Context Window (Input/Output) | Multimodal | Caching (TTL) | Reasoning Mode | Tool Calling | Native Citations | Pricing (USD/1M Input -> Output) | SDK |
|---|---|---|---|---|---|---|---|---|---|
| Claude Opus 4.7 | Anthropic | 1,000,000 / 128,000 (sync), 300k via beta header | Text, Image (up to 2576px / 3.75MP), PDF | 5min default + 1h opt-in | Adaptive Thinking (`type: adaptive` + `effort` low/medium/high/xhigh) | Parallel, Streaming, server tools (web_search, web_fetch, code, computer_use, bash, text_editor, memory) | Yes (Citations Beta) | $5 -> $25 (Batch $2.50 -> $12.50) | Claude Agent SDK |
| Claude Sonnet 4.6 | Anthropic | 1,000,000 / 64,000 (sync), 300k batch beta | Text, Image (1568px), PDF | 5min default + 1h opt-in | Extended Thinking (`budget_tokens`) and Adaptive Thinking | Parallel, Streaming, server tools | Yes | $3 -> $15 (Batch $1.50 -> $7.50) | Claude Agent SDK |
| Claude Haiku 4.5 | Anthropic | 200,000 / 64,000 | Text, Image, PDF, computer_use | 5min default + 1h opt-in | Extended Thinking (`budget_tokens`); no Adaptive | Parallel, Streaming, server tools (web_search, code, bash, computer_use) | Yes | $1 -> $5 (Batch $0.50 -> $2.50) | Claude Agent SDK |
| GPT-5 | OpenAI | 400,000 total / 128,000 output (effective input usable ~272k) | Text, Image; no native audio, no native video | Automatic (no TTL config), triggers from 1,024 tokens | `reasoning.effort`: minimal/low/medium/high (4 levels) | Function calling, parallel, streaming, Structured Outputs, server tools (web_search, file_search, image_gen, code_interpreter, MCP); no computer_use | Yes (Responses API, file_search refs) | $1.25 -> $10.00 (Cached Input $0.125) | OpenAI SDK + OpenAI Agents SDK |
| GPT-5 mini | OpenAI | 400,000 / 128,000 | Text, Image | Automatic (same as GPT-5) | `reasoning.effort` minimal/low/medium/high | Same as GPT-5 | Same as GPT-5 | approx. $0.25 -> $2.00 (exact figures unclear in sources) | OpenAI SDK / Agents SDK |
| Gemini 3 Pro | Google | 1,000,000 / 64,000 | Text, Image, Audio, Video, PDF (`media_resolution` param) | Explicit Caching, default 60min, configurable; storage $4.50/1M tokens/h | Thinking Levels: minimal/low/medium/high (default = high) | Function calling, parallel, streaming, built-in: Google Search, Maps Grounding, URL Context, File Search, Code Execution | Yes (Search Grounding, `groundingMetadata`) | <=200k: $2 -> $12; >200k: $4 -> $18 | google-genai SDK + Vertex AI Agent Builder + Google ADK |
| Gemini 3 Flash | Google | 1,048,576 / 64,000 | Text, Image, Audio, Video, PDF | Implicit caching free + explicit caching with storage | Thinking Levels minimal/low/medium/high | Same as Gemini 3 Pro | Yes (Search Grounding) | $0.50 (text/image/video) or $1.00 (audio) -> $3.00 | google-genai SDK + Google ADK |
| Gemini 3.1 Pro Preview | Google | 2,000,000 / 64,000 | Same as Gemini 3 Pro | Same as Gemini 3 Pro | Thinking Levels | Same as Gemini 3 Pro | Yes | <=200k: $2 -> $12; >200k: $4 -> $18 | google-genai SDK + Google ADK |

Note: GPT-5 nano is documented in R1 (400k context, approx. $0.05 -> $0.40) but is not listed as a primary row because the pricing source is not unambiguous.

### Key Caveats and Pitfalls

- **GPT-5 effective context:** The nominal context window is 400,000 tokens, of which 128,000 are reserved for output. The effectively usable input portion is therefore around 272,000 tokens. GPT-5 does not have a 1M context window.
- **Claude Opus 4.7 reasoning is called Adaptive Thinking, not Extended Thinking:** Activation is via `thinking: {type: "adaptive"}` plus `output_config.effort` with the levels low, medium, high, xhigh. The old form using a manual `budget_tokens` returns a 400 error on Opus 4.7. Thinking tokens are billed in full as output, even when `display: omitted` is set.
- **Sonnet 4.6 and Haiku 4.5 keep Extended Thinking:** Both models still accept the classic `budget_tokens` parameter. Sonnet 4.6 additionally supports Adaptive Thinking. Haiku 4.5 does not have Adaptive Thinking.
- **Prompt caching is provider-specific:** Anthropic offers 5min as default and 1h as opt-in (cache-write at the 1h tier costs 2x the base rate). OpenAI caches automatically with no TTL configuration. Gemini offers explicit context caching with a configurable TTL (default 60min) plus free implicit caching on Flash models.
- **SDK naming for Anthropic:** The official agent SDK has been called **Claude Agent SDK** since 29 September 2025. The packages are `@anthropic-ai/claude-agent-sdk` (npm) and `claude-agent-sdk` (PyPI). "Claude Code" is the official CLI, not the SDK. The older name "Claude Code SDK" is no longer correct.
- **Anthropic tokenizer change for Opus 4.7:** The same input text can produce up to 35 percent more tokens than on Opus 4.6. Effective cost rises even though the per-token rate stays the same.
- **Gemini Pro paid-only since 1 April 2026:** Free tier exists only for Flash and Flash-Lite.

### Sub-table: Cache Hit Discount

| Provider | Cache Hit Discount | Minimum Size | Notes |
|---|---|---|---|
| Anthropic | 90 percent (cache read = 0.1x base) | 4,096 tokens | Cache write 5min: 1.25x base; cache write 1h: 2x base. Max 4 cache breakpoints per request. Default TTL is 5min (silent change March 2026). |
| OpenAI | 90 percent (cached input = 0.1x base) | 1,024 tokens, then in steps of 128 | Fully automatic, no code changes required. No TTL configuration. In-memory cache retention not available for GPT-5.5+. |
| Google | 75 percent on cache reads (Pro), implicit caching on Flash is free | 2,048 tokens (Vertex), AI Studio partly 32,768 tokens | Storage cost: $4.50 per 1M tokens per hour (in addition to cache-read pricing). Default TTL 60min, configurable. |

### Sub-table: Rate Limits Tier 1

| Model | RPM | TPM | Notes |
|---|---|---|---|
| Claude Opus 4.7 | approx. 50 | ITPM approx. 30,000, OTPM 8,000 | Shared across the Opus family. Values from Anthropic rate-limits docs. |
| Claude Sonnet 4.6 | approx. 50 (typical) | approx. 40,000 ITPM (typical) | Not unambiguously documented per model in the sources. |
| Claude Haiku 4.5 | typical Anthropic Tier 1 | typical Anthropic Tier 1 | Per-model values not unambiguously documented. |
| GPT-5 | approx. 1,000 | 500,000 TPM, 1.5M batch TPM | After September 2025 increase. Source: OpenAI Devs on Twitter. |
| GPT-5 mini | not unambiguous | 500,000 TPM, 5M batch | After September 2025 increase. |
| Gemini 3 Pro | approx. 50 documented (in practice sometimes 25 RPM observed) | not unambiguous | 1,000 RPD documented (in practice sometimes 250 RPD). Sources contradict each other (Google AI Forum). |
| Gemini 3 Flash | typically >1,000 RPM | not unambiguous | Values not precisely documented. |

### Source List

**Anthropic**
- What's new in Claude Opus 4.7: https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-7
- Models Overview: https://platform.claude.com/docs/en/about-claude/models/overview
- Pricing: https://platform.claude.com/docs/en/about-claude/pricing
- Prompt Caching: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Extended Thinking: https://platform.claude.com/docs/en/build-with-claude/extended-thinking
- Adaptive Thinking: https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking
- Claude Agent SDK Overview: https://code.claude.com/docs/en/agent-sdk/overview
- Claude Agent SDK Migration Guide: https://platform.claude.com/docs/en/agent-sdk/migration-guide
- Building Agents with the Claude Agent SDK (engineering blog): https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk
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

**Third-party sources (for plausibility checks)**
- BenchLM Claude Pricing April 2026: https://benchlm.ai/blog/posts/claude-api-pricing
- BenchLM OpenAI Pricing April 2026: https://benchlm.ai/blog/posts/openai-api-pricing
- Artificial Analysis Caching Comparison: https://artificialanalysis.ai/models/caching
- Anthropic Cache TTL silently regressed (GitHub Issue 46829): https://github.com/anthropics/claude-code/issues/46829
- The Register on the Claude quota drain 2026-04-13: https://www.theregister.com/2026/04/13/claude_code_cache_confusion/
