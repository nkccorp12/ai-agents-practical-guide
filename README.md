# Building AI Agents — The Practical Guide

> A practical, production-oriented guide to architecting, building, and operating AI agents.
> Available in **English** and **Deutsch**.

**Version 1.4 (May 2026)** — extended with six new sections covering the 2026 agent stack model, the agent harness concept, inter-agent retrieval validation, a 9-layer production-readiness checklist, production monitoring, and systematic skill discovery.

By **Fabian Bäumler**, [DeepThink AI](https://thnkdeep.ai).

---

## Read the Guide

| Language | File |
| --- | --- |
| English | [Building AI Agents — The Practical Guide (v1.4)](v1.4/Building-AI-Agents-Practical-Guide-EN.md) |
| Deutsch | [KI-Agenten entwickeln — Der Praxisleitfaden (v1.4)](v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md) |

Reference implementations under [`examples/`](examples/) (tool-agent + RAG-agent, Python + TypeScript, ~1,144 LOC).
Older versions: [`v1.3/`](v1.3/) (April 2026), [`v1.2/`](v1.2/) (April 2026 first edition), [`archive/v1.1/`](archive/v1.1/) (February 2026).
Reviewer notes and research outputs: [`_meta/`](_meta/).

## What's inside

Six parts, twelve chapters, seven appendices:

- **Part I** — Fundamentals and the 11 fundamental agentic patterns
- **Part II** — Agent architecture: the four critical gaps, skills layer (incl. Anthropic Skill format), memory architecture
- **Part III** — Performance and speed optimization for production
- **Part IV** — Information retrieval and production-ready RAG systems
- **Part V** — Self-improving multi-agent RAG systems (eval-harness, approval gates, anti-drift, canary rollouts, veto zones)
- **Part VI** — From prototype to production: decision framework, expanded security (identity, secrets, tenancy, PII), expanded deployment (SLOs, audit, rollback, cost control)
- **Appendices A–G** — Checklists, benchmarking templates, troubleshooting, further resources, model capability matrix, reference implementations, skill format spec

## What's new in v1.4

- **Section 1.5** — The 2026 agent stack model: a layered conceptual model of the full agentic runtime, accompanied by a new hero diagram.
- **Section 3.6** — The agent harness concept: the loop, primitive tools, context management, and error handling that turn a model into a working agent; includes an architecture diagram.
- **Section 4.5 extended** — Systematic skill discovery: a domain-to-tasks-to-skills-to-automation mapping method for building a skill inventory from first principles.
- **Section 8.5 extended** — Inter-agent retrieval validation: detecting and mitigating misinformation propagation in multi-agent RAG pipelines.
- **Section 12.8** — 9-layer production-readiness checklist: a pre-launch synthesis check across nine architectural layers (modular codebase, data security, security, service layer, multi-agent, API gateway, observability, eval framework, stress testing).
- **Section 12.9** — Production monitoring: full conversation recording, filtered annotation queues, automated LLM evals on production traffic, and the closed-loop improvement cycle.

## What's new in v1.3

- **Verified model capabilities** in Appendix E: Claude 4.7 Opus (1M context, **Adaptive Thinking**), Claude 4.6 Sonnet, Claude Haiku 4.5, **GPT-5 (400k context, not 1M)**, Gemini 3 Pro / Flash / 3.1, with caching TTLs, pricing, rate limits, and provider-specific caveats — every value sourced.
- **SDK naming corrected** to **Claude Agent SDK** (`@anthropic-ai/claude-agent-sdk`, `claude-agent-sdk`).
- **Full reference implementations** in Appendix F + [`examples/`](examples/): tool-agent (customer-support with approval gate, RBAC, tenant isolation, audit log) and RAG-agent (hybrid BM25 + pgvector, Cohere Rerank v3.5, native citations, 1h prompt cache) — Python and TypeScript, with goldens, Promptfoo configs, Modal deployment.
- **Chapter 9 rewritten** with eval-harness (DeepEval + Promptfoo + GrowthBook), approval gates, frozen-baseline anti-drift, canary rollouts, and explicit veto zones (money movement, auth, medical/legal, destructive ops).
- **Chapter 11 expanded** (11.5–11.11): Output guardrails, security monitoring, integrating security with patterns, **Identity & Auth (OAuth On-Behalf-Of, RFC 8693)**, **Secret handling (Vault/KMS, session-scoped tokens)**, **Multi-tenancy (KV-cache-bleed prevention, vLLM cache_salt, Postgres RLS)**, **PII & data classification (Presidio, GDPR Art. 17)**.
- **Chapter 12 expanded** (12.4–12.7): **SLOs & rate limits** (P50/P95/P99, tenant quotas, provider failover via AI Gateway), **Audit logs** (OpenTelemetry GenAI, WORM storage), **Rollback & incident response** (canary, runbooks), **Cost control** (per-tenant budgets, progressive throttling, Haiku→Sonnet→Opus tiering for 60–90% savings).
- **Section 4.6** added: Anthropic Skill format with `SKILL.md` + `skill.yaml` overlay.
- **Appendix G** added: complete skill format specification with versioning, runtime contract, registry pattern.
- **DE lectorate**: TOC anchors fixed, missing code example from EN ported, translation artefacts cleaned, terminology unified.

## Repository layout

```
.
├── v1.4/                            # current edition (May 2026)
│   ├── Building-AI-Agents-Practical-Guide-EN.md
│   └── KI-Agenten-entwickeln-Praxisleitfaden-DE.md
├── v1.3/                            # previous edition (April 2026)
│   ├── sections/                    # section sources and appendix files
│   └── snippets/                    # chapter extension fragments
├── v1.2/                            # April 2026 first edition
├── examples/                        # reference implementations (~1,144 LOC code + SQL/YAML/JSON)
│   ├── tool-agent/                  # customer-support agent with approval gate
│   └── rag-agent/                   # hybrid-search RAG with citations
├── archive/v1.1/                    # February 2026 edition
├── assets/diagrams/                 # 23 architecture diagrams (SVG)
├── _meta/                           # codex review, roadmap, research outputs
├── CITATION.cff
└── LICENSE                          # CC BY 4.0
```

## License

Content is licensed under [CC BY 4.0](LICENSE). You are free to share and adapt with attribution.

## Citation

```
Bäumler, F. (2026). Building AI Agents — The Practical Guide (v1.4). DeepThink AI.
```

---

# KI-Agenten entwickeln — Der Praxisleitfaden

Praxisorientierter Leitfaden für Architektur, Aufbau und Betrieb produktionsreifer KI-Agenten.

**Version 1.4 (Mai 2026)**, erweitert um sechs neue Abschnitte: 2026 Agent-Stack-Modell, Agent-Harness-Konzept, Inter-Agent-Retrieval-Validierung, 9-Schichten-Produktionsreife-Checkliste, Produktions-Monitoring und systematische Skill-Discovery.

Von **Fabian Bäumler**, [DeepThink AI](https://thnkdeep.ai).

## Was ist drin

Sechs Teile, zwölf Kapitel, sieben Anhänge: Grundlagen + 11 agentische Pattern, Architekturlücken, Skills-Layer (mit Anthropic Skill-Format), Memory, Performance, RAG, selbstverbessernde Multi-Agent-Systeme (mit Eval-Harness, Approval Gates, Verbotszonen), Sicherheit (Identity, Secrets, Mandantentrennung, PII), Deployment (SLOs, Audit, Rollback, Kosten), Anhänge A–G inkl. Capability-Matrix, Referenz-Implementierungen und Skill-Format-Spezifikation.

## Was ist neu in v1.4

- **Abschnitt 1.5** — Das 2026 Agent-Stack-Modell: ein geschichtetes Konzeptmodell der agentischen Laufzeitumgebung mit neuem Hero-Diagramm.
- **Abschnitt 3.6** — Das Agent-Harness-Konzept: der Loop, primitive Tools, Context-Management und Error-Handling, die ein Modell zu einem arbeitenden Agenten machen; mit Architekturdiagramm.
- **Abschnitt 4.5 erweitert** — Systematische Skill-Discovery: Domain-zu-Aufgaben-zu-Skills-zu-Automatisierung-Methode für den Aufbau eines Skill-Inventars.
- **Abschnitt 8.5 erweitert** — Inter-Agent-Retrieval-Validierung: Erkennung und Mitigation von Fehlinformationen in Multi-Agent-RAG-Pipelines.
- **Abschnitt 12.8** — 9-Schichten-Produktionsreife-Checkliste: ein Pre-Launch-Synthese-Check über neun Architektur-Schichten (modularer Codebase, Datensicherheit, Security, Service-Layer, Multi-Agent, API-Gateway, Observability, Eval-Framework, Stress-Testing).
- **Abschnitt 12.9** — Produktions-Monitoring: vollständiges Conversation-Recording, gefilterte Annotation-Queues, automatisierte LLM-Evals auf Prod-Traffic und die Closed-Loop-Verbesserungsschleife.

## Was ist neu in v1.3

- Verifizierte Modell-Capabilities (GPT-5 = **400k**, nicht 1M; Adaptive Thinking statt Extended Thinking bei Opus 4.7; Claude Agent SDK statt Code SDK)
- Vollständige Referenz-Implementierungen (Tool-Agent + RAG-Agent, Python + TypeScript, lauffähig)
- Kapitel 9 komplett neu mit Eval-Harness, Approval Gates und Verbotszonen
- Kapitel 11 erweitert um OAuth On-Behalf-Of, Secret-Handling, Mandantentrennung, PII
- Kapitel 12 erweitert um SLOs, Audit-Logs, Rollback, Kostensteuerung
- DE-Lektorat: TOC-Anchors korrigiert, fehlendes Code-Beispiel ergänzt, Terminologie vereinheitlicht

## Lizenz

Inhalte stehen unter [CC BY 4.0](LICENSE) — frei nutzbar mit Quellenangabe.
