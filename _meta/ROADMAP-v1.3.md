# Roadmap v1.3 (April 2026)

Basierend auf Codex-Review von v1.2 (`REVIEW-v1.2-codex.md`).

## Ziel

v1.3 schließt die Lücke zwischen "Architektur-Orientierung" und "praxistauglicher Produktionsleitfaden". Konkret:

1. **Faktentreue** — alle Behauptungen mit Quelle, Datum, Geltungsbereich
2. **Umsetzbarkeit** — vollständige Referenzimplementierungen, nicht nur Patterns
3. **Production-Realismus** — was Senior Engineers wirklich brauchen (Auth, RBAC, SLOs, Audit)
4. **Selbstverbesserung mit Bodenhaftung** — Evals, Approval Gates, Anti-Drift
5. **Sprachliche Konsistenz (DE)** — Lektorat, TOC-Fix, Terminologie-Glossar

## Aufgaben-Lots

### Lot A — Faktenkorrekturen (Quick-Fix)
**Wer:** 1 Quick-Fix-Agent in Welle 1
**Wo:** beide Sprachen, alle Stellen

- [ ] GPT-5: 1M → **400k Token** Kontextfenster
- [ ] "Gemini 3.0" → **Gemini 3 Pro / Flash / 3.1** mit korrekten Token-Limits
- [ ] Claude 4.7 "Extended Thinking" → **"Adaptive Thinking"**, mit Hinweis auf Token-Kosten
- [ ] "Anthropic Claude Agent SDK" → **Claude Code SDK**
- [ ] Prompt-Caching: pauschale 1h-TTL-Aussagen → provider-spezifische Tabelle (Anthropic 5m+1h, OpenAI in-memory+24h, Gemini 1h)
- [ ] MCP-Aussagen entschärfen (Protokoll, nicht Sicherheitslösung)

### Lot B — DE-Lektorat (Quick-Fix)
**Wer:** gleicher Quick-Fix-Agent

- [ ] DE-TOC reparieren (englische Anchor-IDs durch deutsche ersetzen)
- [ ] Code-Beispiel aus EN 8.5 nach DE 8.5 übernehmen
- [ ] Übersetzungsartefakte ausmerzen:
  - DE 1.2 "deeply-integrierter Tool-Orchestrierung"
  - DE 3.4 "Detaillierter Prompter"
  - DE 8.5 "sichtbares Reasoning"
- [ ] Terminologie-Konsistenz: deutsche oder englische Form, nicht Mischmasch (Pattern/Muster, Context Window/Kontextfenster, Skills Layer/Skill-Schicht)

### Lot C — Capability-Matrix (Author)
**Wer:** Author-Agent C (basiert auf Research R1)
**Wo:** Neuer Anhang E (`Anhang E: Modell-Capability-Matrix`)

Tabelle: Modelle (Claude 4.7 Opus, 4.6 Sonnet, GPT-5, GPT-5 mini, Gemini 3 Pro, Gemini 3 Flash) × Features:
- Kontextfenster (Input/Output)
- Multimodal (Text/Image/Audio/Video/PDF)
- Caching (TTL, Mindestgröße)
- Thinking-Modi (Adaptive/Extended)
- Tool-Calling (parallel? streaming?)
- Citations (nativ? Format?)
- Pricing (Input/Output, mit Caching-Discount)
- Rate Limits (Tier 1)
- SDK / Stand

### Lot D — Referenz-Implementierungen (Author)
**Wer:** Author-Agent D (basiert auf Research R4)
**Wo:** Neuer Anhang F (`Anhang F: Referenz-Implementierungen`) + dazugehörige Code-Repos

Zwei vollständige Beispiele:
1. **Tool-Agent** (Customer-Support mit RBAC, Tool-Calling, Approval-Gate für sensible Aktionen)
2. **RAG-Agent** (Hybrid Search + Reranking + Citations)

Für jeden:
- Python (Anthropic SDK + Pydantic)
- TypeScript (Vercel AI SDK 5)
- Tests (Goldens)
- Eval-Harness (Promptfoo oder DeepEval)
- Tracing (Langfuse oder OpenTelemetry)
- Deployment-Snippet (Vercel Workflow oder Modal)

Code als separate Dateien unter `examples/tool-agent/` und `examples/rag-agent/`, im Buch nur Auszüge + Verweise.

### Lot E — Production-Kapitel ausbauen (Author)
**Wer:** Author-Agent E (basiert auf Research R2)
**Wo:** Erweiterung Kapitel 11 + 12

Neue Abschnitte:
- 11.5 **Identity & Auth** (User-Identity-Propagation, OAuth/JWT für Tools)
- 11.6 **Secret-Handling** (Vault, KMS, Rotation, Anti-Pattern: Secrets im Prompt)
- 11.7 **Mandantentrennung** (Tenant-ID-Kontext, Daten-Isolation)
- 11.8 **PII & Datenklassifizierung** (Erkennung, Redaction, Audit-Trail)
- 12.4 **SLOs & Rate Limits** (Latenz-Budgets, Token-Quotas pro Tenant, Backpressure)
- 12.5 **Audit Logs** (was loggen, wie speichern, GDPR/Compliance)
- 12.6 **Rollback & Incident Response** (Canary, Blue/Green, Runbooks)
- 12.7 **Kostensteuerung** (per-Request-Budget, Tenant-Quota, Cache-Hitrate-Monitoring)

### Lot F — Kapitel 9 realistisch (Author)
**Wer:** Author-Agent F (basiert auf Research R3)
**Wo:** Komplett-Rewrite Kapitel 9

Neue Sub-Sections:
- 9.1 Was Self-Improvement realistisch leisten kann (und was nicht)
- 9.2 **Eval-Harness** (Goldens, Failure Taxonomy, Regression Gates)
- 9.3 Outer-Loop-Pattern mit **Approval Gates** und menschlicher Freigabe
- 9.4 **Anti-Drift-Mechanik** (Baseline-Vergleich, Reverting bei Regression)
- 9.5 Canary-Rollout für Prompt/Skill-Updates
- 9.6 Wann Self-Improvement abschalten (Risiko-Heuristik)

### Lot G — Skill-Format-Spec (Author)
**Wer:** Author-Agent G (Erweiterung Kapitel 4, basiert auf Research R3)
**Wo:** Neue Sektion 4.6 + Anhang G

Konkretes Skill-Format mit:
- Dateistruktur (`skill.yaml`, `prompt.md`, `tools.json`, `tests/`)
- Versionierung (SemVer für Skills)
- Test-Spec (Goldens als YAML)
- Laufzeit-Vertrag (Tool-Contract, Input/Output-Schemas)

### Lot H — Belege für harte Zahlen
**Wer:** Quick-Fix-Agent + Author-Agenten

Alle harten Zahlen entweder:
- mit Quelle + Datum versehen
- als "in unseren Messungen / typische Werte" relativiert
- oder ersetzt durch Größenordnungen mit Kontext

Stellen: DE 5.5 (RLM), DE 8.7 (RAG-Fehlerquote), DE 10 (Cache-Effekt), Kap 6 (Prefetch), Kap 9 (RAG-Verbesserung).

## Welle-Plan

### Welle 1 (parallel, ~10 min)
- **Quick-Fix-Agent** → Lot A + B + Teile von H
- **Research R1** (Modell-Capabilities) → Input für Lot C, A
- **Research R2** (Production-Engineering) → Input für Lot E
- **Research R3** (Evals + Skill-Formate) → Input für Lot F, G
- **Research R4** (Referenz-Implementierungen) → Input für Lot D

### Welle 2 (parallel, ~15 min)
- **Author C** → Capability-Matrix (Anhang E)
- **Author D** → Referenz-Implementierungen (Anhang F + examples/)
- **Author E** → Production-Kapitel (11.5-11.8 + 12.4-12.7)
- **Author F** → Kapitel 9 Rewrite
- **Author G** → Skill-Format-Spec (4.6 + Anhang G)

### Welle 3
- Final-Merge zu `v1.3/`-Dateien (DE + EN)
- Versions-Header und -Footer auf v1.3 / "April 2026 (Update)"
- Codex-Re-Review der finalen v1.3
- Commit + Push

## Output-Struktur

```
v1.3/
  KI-Agenten-entwickeln-Praxisleitfaden-DE.md
  Building-AI-Agents-Practical-Guide-EN.md
  de/
    teil1_kapitel1-6.md
    teil2_kapitel7-12.md
    anhang_e_capability_matrix.md
    anhang_f_referenz_implementierungen.md
    anhang_g_skill_spec.md
  en/
    part1_chapters1-6.md
    part2_chapters7-12.md
    appendix_e_capability_matrix.md
    appendix_f_reference_implementations.md
    appendix_g_skill_spec.md
examples/
  tool-agent/        (Python + TypeScript)
  rag-agent/         (Python + TypeScript)
_meta/
  REVIEW-v1.2-codex.md
  ROADMAP-v1.3.md
  research/
    R1-model-capabilities.md
    R2-production-engineering.md
    R3-evals-skill-formats.md
    R4-reference-implementations.md
```
