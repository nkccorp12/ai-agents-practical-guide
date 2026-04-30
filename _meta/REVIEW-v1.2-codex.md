# Codex-Review v1.2 (DE)

**Reviewer:** Codex (gpt-5.4, reasoning xhigh, sandbox read-only)
**Datum:** 2026-04-30
**Datei:** `v1.2/KI-Agenten-entwickeln-Praxisleitfaden-DE.md`

---

## Gesamteindruck

Zielgruppe: Senior Engineers, Architekt:innen, Tech Leads, Gründer mit LLM-Vorerfahrung. Wird in der Denke getroffen. Als Architektur-Orientierung brauchbar, als echter Praxisleitfaden für produktionsreife Agenten noch nicht. Kernnutzen: Vokabular und Entscheidungsrahmen, nicht Umsetzbarkeit.

## Stärken

- **Kapitel 2** (11 Pattern) — solides mentales Modell für Agentenarchitekturen
- **Kapitel 5** (Memory) — bester Teil, Trennung Kurz/Mittel/Lang plus Budgetierung
- **Kapitel 7+8** (RAG) — praxisnah, echte Produktionsprobleme
- **Kapitel 11** (Security) — "stilles Scheitern" als Framing trifft
- **Anhang-Checklisten** — nützlich als Review-Artefakt

## Schwächen

1. **2026-Update kosmetisch** — Modellnamen ausgetauscht, Patterns kaum weiterentwickelt
2. **Harte Zahlen ohne Beleg** — RLM +34 Punkte, 60% RAG-Fehlerquote, 5x-10x Cache-Effekt (DE 5.5, 8.7, 10)
3. **TOC kaputt** — DE verlinkt auf englische Anchor-IDs (DE Zeile 18)
4. **Code-Beispiel in 8.5 fehlt in DE** — nur EN hat es (EN Zeile 550)
5. **Kapitel 4 zu abstrakt** — kein Dateiformat, kein Versionsmodell, kein Eval-Harness für Skills
6. **Kapitel 9 zu optimistisch** — Selbstverbesserung ohne Evals/Regression-Gates/Rollback brandgefährlich
7. **Production-Themen unterbelichtet** — Identity, Secrets, Mandantentrennung, Audit Logs, Datenklassifizierung, Rate Limits, SLOs, Rollback, Incident Response
8. **Zu RAG-lastig** — Browser-Agenten, Transaction Agents, CRM/ERP-Workflows, Auth-gebundene Tool-Chains, UI-Automation kommen zu kurz
9. **Übersetzungsartefakte (DE):**
   - "deeply-integrierter Tool-Orchestrierung" (DE 1.2)
   - "Detaillierter Prompter" (DE 3.4)
   - "sichtbares Reasoning" (DE 8.5)

## Faktencheck (Stand 2026-04-30)

| Behauptung | Realität | Quelle |
|---|---|---|
| Claude 4.7 + 1M Token | im Kern korrekt | Anthropic Models Overview |
| Claude 4.7 "Extended Thinking" | falsch, heißt **"Adaptive thinking"**, nicht tokenfrei | Claude Opus 4.7 release notes |
| GPT-5 = 1M Kontext | **falsch, 400k Kontext** | platform.openai.com/docs/models/gpt-5 |
| "Gemini 3.0" | falsch — korrekt: **Gemini 3 Pro / Flash / 3.1**, 1M nur bei 3 Pro | ai.google.dev/gemini-api/docs/models |
| Prompt-Caching 1h-TTL pauschal | Anthropic 5min+1h, OpenAI in-memory+24h, Gemini 1h — kein einheitlicher Standard | Provider-Docs |
| MCP als de-facto-Sicherheitslösung | überzeichnet — MCP ist Protokoll, nicht Allowlist/Trust/Policy | MCP Specification |
| "Anthropic Claude Agent SDK" | falsch, heißt **Claude Code SDK** | docs.anthropic.com/en/docs/claude-code/sdk |

## Top-5 für v1.3

1. **Capability-Matrix** statt verstreute Modellnamen, jede Behauptung mit Quelle + Datum + Geltungsbereich
2. **Zwei vollständige Referenzimplementierungen** (Tool-Agent + RAG, Python + TypeScript, mit Code, Tests, Evals, Traces, Deployment)
3. **Production-Kapitel ausbauen:** Auth, Secrets, PII, RBAC, Audit, SLOs, Rollback, Rate Limits, Tenancy, Kostensteuerung
4. **Kapitel 9 realistisch** — Offline-Evals, Approval Gates, Anti-Drift-Mechanik statt Optimismusprosa
5. **DE-Lektorat** — TOC reparieren, fehlendes Code-Beispiel aus EN übernehmen, Produktnamen korrigieren, Terminologie vereinheitlichen
