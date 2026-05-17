# agents v1.4 Update — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine v1.4-Edition des Leitfadens *Building AI Agents* erstellen, die das genuin neue Material aus 6 Trello-"Process Idea"-Karten punktuell in die bestehende v1.3-Struktur einarbeitet.

**Architecture:** Neues Verzeichnis `v1.4/` mit den zwei Reader-Hauptdateien (Kopie von v1.3 + Edits). Pro Story genau eine Ergänzung an einer definierten Stelle. Zwei Diagramme: Harness inline via bestehende Mermaid-Pipeline, 7-Schichten-Stack als Editorial-Hero via `diagram-design`-Templates. Plus Querschnitt-Updates (README, CITATION, ROADMAP) und gezielte Hygiene-Fixes.

**Tech Stack:** Markdown, Node.js (`beautiful-mermaid` über `tools/render-new-diagrams.mjs`), SVG, Git.

**Quell-Brief:** Der Content-Brief pro Abschnitt steht in `docs/superpowers/specs/2026-05-17-agents-v14-update-design.md` §4. Dieser Plan wiederholt die Kernpunkte je Task. Bei Konflikt gilt die Spec.

**Commit-Konvention:** Branch ist `v1.4-update`. Commits OHNE `Co-Authored-By`-Trailer und ohne Claude-Attribution (CLAUDE.md). Git-User `nkccorp12` ist global gesetzt.

**Sprach-Parität:** Jede inhaltliche Änderung wird in BEIDEN Dateien gemacht — `Building-AI-Agents-Practical-Guide-EN.md` und `KI-Agenten-entwickeln-Praxisleitfaden-DE.md`. Ton/Terminologie konsistent zu v1.3. Keine Em-Dashes als Satztrenner.

---

## File Structure

**Neu angelegt:**
- `v1.4/Building-AI-Agents-Practical-Guide-EN.md` — EN-Hauptdatei (Kopie v1.3 + Edits)
- `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` — DE-Hauptdatei (Kopie v1.3 + Edits)
- `_meta/ROADMAP-v1.4.md` — kurze Roadmap der v1.4-Arbeit
- `assets/diagrams/abb-3-6-de.svg`, `abb-3-6-en.svg` — Harness-Diagramm (Mermaid-Pipeline)
- `assets/diagrams/abb-1-5-de.svg`, `abb-1-5-en.svg` — 7-Schichten-Stack (aus Hero-HTML extrahiert)
- `assets/hero-v1.4/agent-stack.html` — eigenständiges Editorial-Hero-Artefakt

**Modifiziert:**
- `tools/render-new-diagrams.mjs` — neuer Eintrag im `diagrams`-Array
- `README.md` — Read-the-Guide-Tabelle, "What's new in v1.4", Repo-Layout, Diagrammzahl
- `CITATION.cff` — Version 1.2 → 1.4

**Unangetastet:** `v1.3/`, `v1.2/`, `archive/`, `examples/`.

---

## Task 1: v1.4-Verzeichnis anlegen und Versions-Strings setzen

**Files:**
- Create: `v1.4/Building-AI-Agents-Practical-Guide-EN.md` (Kopie von `v1.3/Building-AI-Agents-Practical-Guide-EN.md`)
- Create: `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` (Kopie von `v1.3/KI-Agenten-entwickeln-Praxisleitfaden-DE.md`)

- [ ] **Step 1: Dateien kopieren**

```bash
mkdir -p v1.4
cp v1.3/Building-AI-Agents-Practical-Guide-EN.md v1.4/Building-AI-Agents-Practical-Guide-EN.md
cp v1.3/KI-Agenten-entwickeln-Praxisleitfaden-DE.md v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md
```

- [ ] **Step 2: Versions-Strings in der EN-Datei aktualisieren**

In `v1.4/Building-AI-Agents-Practical-Guide-EN.md` ersetzen:
- `**Version 1.3**` → `**Version 1.4**`
- `Edition April 2026 (Update 1.3)` → `Edition May 2026 (Update 1.4)`
- `*Version 1.3, sharpened with capability matrix, reference implementations, and expanded production chapter*` → `*Version 1.4, extended with the agent stack model, the harness concept, multi-agent retrieval validation, and a production-readiness checklist*`
- Footer `*Version 1.3 (April 2026)*` → `*Version 1.4 (May 2026)*`

- [ ] **Step 3: Versions-Strings in der DE-Datei aktualisieren**

In `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` ersetzen:
- `**Version 1.3**` → `**Version 1.4**`
- `Ausgabe April 2026 (Update 1.3)` → `Ausgabe Mai 2026 (Update 1.4)`
- `*Version 1.3, verschärft, mit Capability-Matrix, Referenz-Implementierungen und ausgebautem Production-Kapitel*` → `*Version 1.4, erweitert um das Agent-Stack-Modell, das Harness-Konzept, Multi-Agent-Retrieval-Validierung und eine Production-Readiness-Checkliste*`
- Footer `*Version 1.3 (April 2026)*` → `*Version 1.4 (Mai 2026)*`

- [ ] **Step 4: Verifizieren**

Run: `grep -c "Version 1.4" v1.4/*.md && grep -L "Version 1.3" v1.4/*.md`
Expected: jede Datei enthält "Version 1.4" mehrfach; `grep -L` listet beide Dateien (kein "Version 1.3" mehr vorhanden außer evtl. in Code-Beispielen — die bei Schritt 2/3 NICHT angefasst werden, z.B. `skill v1.2.0 -> v1.3.0`).

Run: `grep -n "v1.3.0\|v1.2.0" v1.4/Building-AI-Agents-Practical-Guide-EN.md`
Expected: Code-Beispiel-Treffer (Skill-Versionierung) bleiben unverändert — das ist korrekt, das sind keine Editions-Strings.

- [ ] **Step 5: Commit**

```bash
git add v1.4/
git commit -m "v1.4: scaffold edition from v1.3 with updated version strings"
```

---

## Task 2: Abschnitt 1.5 "Der Agent-Stack 2026" / "The 2026 Agent Stack"

**Files:**
- Modify: `v1.4/Building-AI-Agents-Practical-Guide-EN.md` (neuer Abschnitt am Ende von Chapter 1, direkt vor `## Chapter 2:`)
- Modify: `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` (analog, vor `## Kapitel 2:`)

**Content-Brief (Spec §4.2):** Ein 7-Schichten-Orientierungsmodell als Lesekarte. Schichten von oben nach unten:
1. **Interface** — Mensch-Agent-Berührungspunkte (Terminal, Web).
2. **Runtime** — Agenten-Ausführung: Planung, Loop, State (Querverweis Kap. 3 + 3.6).
3. **Protocol** — standardisierte Tool-Anbindung, MCP statt Custom-Integrationen (Querverweis Kap. 4).
4. **Tools & Sandboxes** — Code/Browser/API-Ausführung mit Sandboxing, Rate-Limits, Permissions (Querverweis Kap. 11).
5. **Knowledge & Memory** — zwei getrennte Probleme: Knowledge = externe Informationsbeschaffung, Memory = persistenter Zustand (Querverweis Kap. 5, Kap. 7–8). Nur grob rahmen; Detail bleibt in Kap. 5.
6. **Models** — Multi-Modell-Orchestrierung: Routing, Fallbacks, Gateways (Querverweis Anhang E).
7. **Evals & Observability** — Messung und Verbesserung über Zeit (Querverweis Kap. 9, Kap. 12).
Ein kurzer Absatz pro Schicht mit dem jeweiligen Querverweis. Abschluss-Satz: das Modell als Landkarte für den Rest des Leitfadens. ~0,75 Seite. Diagramm-Einbindung folgt in Task 11 (Platzhalter-Hinweis hier NICHT setzen — Task 11 fügt das Bild ein).

- [ ] **Step 1: EN-Abschnitt schreiben**

In `v1.4/Building-AI-Agents-Practical-Guide-EN.md` direkt vor der Zeile `## Chapter 2: The 11 Fundamental Agentic Patterns` einfügen: eine Heading `### 1.5 The 2026 Agent Stack`, gefolgt vom Fließtext gemäß Content-Brief (englisch). Sieben Schichten, je ein Absatz mit Cross-Ref. Stil wie die bestehenden 1.x-Abschnitte.

- [ ] **Step 2: DE-Abschnitt schreiben**

In `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` direkt vor `## Kapitel 2: Die 11 fundamentalen agentischen Muster` (Heading-Text ggf. an die Ist-Datei anpassen) einfügen: `### 1.5 Der Agent-Stack 2026` + Fließtext (deutsch), inhaltsgleich zur EN-Fassung.

- [ ] **Step 3: TOC-Einträge ergänzen**

In beiden Dateien im `## Table of Contents` / `## Inhaltsverzeichnis` unter dem Kapitel-1-Block einen Eintrag für 1.5 ergänzen. Anchor im GitHub-Stil aus dem Heading ableiten (lowercase, Leerzeichen→Bindestrich, Punkt entfernt): EN `#15-the-2026-agent-stack`, DE `#15-der-agent-stack-2026`. Format an die vorhandenen TOC-Zeilen anpassen.

- [ ] **Step 4: Verifizieren**

Run: `grep -n "### 1.5" v1.4/*.md`
Expected: je ein Treffer pro Datei.

Run: `grep -n "15-the-2026-agent-stack\|15-der-agent-stack-2026" v1.4/*.md`
Expected: je ein TOC-Treffer pro Datei.

- [ ] **Step 5: Commit**

```bash
git add v1.4/
git commit -m "v1.4: add section 1.5 — the 2026 agent stack"
```

---

## Task 3: Abschnitt 3.6 "Das Agent-Harness" / "The Agent Harness"

**Files:**
- Modify: `v1.4/Building-AI-Agents-Practical-Guide-EN.md` (am Ende von Chapter 3, direkt vor `## Chapter 4:`)
- Modify: `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` (analog, vor `## Kapitel 4:`)

**Content-Brief (Spec §4.1):**
- Definition: Das Harness ist alles, was ein LLM zu einem arbeitenden Agenten verbindet — der Loop, der Satz primitiver Tools, Context-Management, Error-Handling. Bild: LLM = Motor, Harness = Chassis.
- "Warum dasselbe Modell sich anders anfühlt": Claude Code, Cursor, Codex nutzen dieselben Basismodelle, fühlen sich aber unterschiedlich an — wegen Harness-Designentscheidungen (Tool-Oberfläche, wann Kontext gezeigt wird, Fehlerbehandlung).
- Minimales Harness: While-Loop + ein Read-File-Tool + eine Textdatei als Scratch-Memory = ein erstes funktionierendes Agent-Harness.
- Brückenschlag: Die 4 Architekturlücken aus Kapitel 3 sind die Bausteine; das Harness ist, wie sie als Loop zusammenlaufen. 3.6 benennt diese Klammer.
- Cross-Ref statt Doppeln: Progressive Disclosure NICHT neu erklären — Verweis auf 4.6. Context-Management — Verweis auf Kapitel 5.
- ~0,75 Seite. Diagramm-Einbindung folgt in Task 10.

- [ ] **Step 1: EN-Abschnitt schreiben**

In `v1.4/Building-AI-Agents-Practical-Guide-EN.md` direkt vor `## Chapter 4: Skills Layer Architecture` einfügen: `### 3.6 The Agent Harness` + Fließtext (englisch) gemäß Content-Brief. Stil wie 3.1–3.5.

- [ ] **Step 2: DE-Abschnitt schreiben**

In `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` direkt vor `## Kapitel 4:` (Skills-Layer; Heading-Text an Ist-Datei anpassen) einfügen: `### 3.6 Das Agent-Harness` + Fließtext (deutsch), inhaltsgleich.

- [ ] **Step 3: TOC-Einträge ergänzen**

In beiden Dateien TOC-Eintrag für 3.6 unter dem Kapitel-3-Block. Anchor: EN `#36-the-agent-harness`, DE `#36-das-agent-harness`.

- [ ] **Step 4: Verifizieren**

Run: `grep -n "### 3.6" v1.4/*.md`
Expected: je ein Treffer pro Datei.

Run: `grep -n "36-the-agent-harness\|36-das-agent-harness" v1.4/*.md`
Expected: je ein TOC-Treffer pro Datei.

Run: `grep -ci "progressive disclosure" v1.4/Building-AI-Agents-Practical-Guide-EN.md`
Expected: Treffer in 4.6 plus höchstens EIN Verweis-Treffer in 3.6 (3.6 darf das Konzept nur referenzieren, nicht erklären).

- [ ] **Step 5: Commit**

```bash
git add v1.4/
git commit -m "v1.4: add section 3.6 — the agent harness"
```

---

## Task 4: Abschnitt 4.5 erweitern — systematische Skill-Findung

**Files:**
- Modify: `v1.4/Building-AI-Agents-Practical-Guide-EN.md` (Abschnitt `### 4.5 Building a Systematic Agent Library`)
- Modify: `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` (Abschnitt `### 4.5 ...`)

**Content-Brief (Spec §4.6):** 4.5 ist derzeit nur ein kurzer Absatz. Erweitern um die Methode **Domain → Tasks → Skills → Automation**: Arbeit in Domänen zerlegen; je Domäne die wiederkehrenden Tasks auflisten; jeden Task in einen definierten Skill überführen; jeden Skill auf Automatisierungspotenzial prüfen; pro Domäne wiederholen. Rahmung: ersetzt Ad-hoc-Prompting durch absichtsvolle Abdeckung. Engineering-Fokus halten — Personal-Productivity-/Dashboard-Aspekte der Quellkarte weglassen. KEIN neuer Abschnitt, keine neue Nummer, kein TOC-Eintrag.

- [ ] **Step 1: EN-Erweiterung schreiben**

Den bestehenden Inhalt von `### 4.5 Building a Systematic Agent Library` um 1–2 Absätze ergänzen, die die Domain→Tasks→Skills→Automation-Methode beschreiben. Bestehenden Text erhalten, nur anhängen/verweben.

- [ ] **Step 2: DE-Erweiterung schreiben**

Analog im DE-Abschnitt 4.5, inhaltsgleich.

- [ ] **Step 3: Verifizieren**

Run: `grep -in "Domain\|Domäne" v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md | grep -i "Task\|Skill"`
Expected: mindestens ein Treffer, der die Methode benennt.

Run: `grep -c "### 4.5" v1.4/*.md && grep -c "### 4.6" v1.4/*.md`
Expected: je 1 — die Abschnitte 4.5 und 4.6 existieren unverändert als eigene Headings (keine versehentliche Verschmelzung/Umnummerierung).

- [ ] **Step 4: Commit**

```bash
git add v1.4/
git commit -m "v1.4: extend section 4.5 with domain-to-automation skill discovery"
```

---

## Task 5: Abschnitt 8.5 erweitern — Inter-Agent-Misinformation

**Files:**
- Modify: `v1.4/Building-AI-Agents-Practical-Guide-EN.md` (Abschnitt `### 8.5 Multi-Agent Query Processing Pipeline`)
- Modify: `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` (Abschnitt `### 8.5 ...`)

**Content-Brief (Spec §4.3):** Erweiterung von 8.5 (KEIN neuer Abschnitt 8.10, kein TOC-Eintrag). Inhalt:
- Fehlermodus: Eine schwache Retrieval-Stufe in einem frühen Agenten propagiert als selbstbewusste Ausgabe nach unten ("Inter-Agent-Misinformation", "Downstream-Loss").
- Bessere/größere Modelle lösen das nicht — sie erzeugen "höher aufgelöste Halluzinationen".
- Vier Fixes: (1) Retrieval-Qualität an jedem Hop validieren, nicht nur am ersten; (2) harte Relevanz-Schwellen; (3) "insufficient information" zurückgeben statt aus Rauschen zu synthetisieren; (4) jede Agenten-Retrieval-Schnittstelle als eigenen Risikopunkt behandeln.
- Cross-Ref: 8.6 Re-Ranking (komplementär), Kapitel 9 (Eval-Gates).
- ~0,5 Seite, als Fortführung von 8.5.

- [ ] **Step 1: EN-Erweiterung schreiben**

Den bestehenden 8.5-Inhalt um einen klar abgesetzten Block (eigener Zwischen-Absatz mit fettem Lead-In wie `**Inter-agent misinformation.**`) zur Retrieval-Validierung ergänzen. Innerhalb von 8.5, vor `### 8.6`.

- [ ] **Step 2: DE-Erweiterung schreiben**

Analog im DE-Abschnitt 8.5, inhaltsgleich.

- [ ] **Step 3: Verifizieren**

Run: `grep -in "misinformation\|downstream" v1.4/Building-AI-Agents-Practical-Guide-EN.md`
Expected: Treffer im 8.5-Bereich.

Run: `grep -c "### 8.10" v1.4/*.md`
Expected: 0 — es entsteht KEIN Abschnitt 8.10.

- [ ] **Step 4: Commit**

```bash
git add v1.4/
git commit -m "v1.4: extend section 8.5 with inter-agent retrieval validation"
```

---

## Task 6: Abschnitt 12.8 "Production-Readiness-Checkliste"

**Files:**
- Modify: `v1.4/Building-AI-Agents-Practical-Guide-EN.md` (neuer Abschnitt nach dem Inhalt von `### 12.7 Cost Control`, direkt vor `## Appendix A: Architecture Checklists`)
- Modify: `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` (analog, vor `## Anhang A: Architektur-Checklisten`)

**Content-Brief (Spec §4.4):** Eine **Synthese-/Verdichtungs-Checkliste**, explizit KEIN konkurrierendes Taxonomie-System. Einleitungssatz, der das klarstellt. Neun Schichten als Checklisten-Zeilen, jede mit hartem Querverweis:
1. Modularer Codebase / Config-Hygiene (Debug ≠ Prod)
2. Datensicherheit — DTOs, keine Roh-Modelle ans Frontend (→ Kap. 11)
3. Security — Rate-Limiting, Input-Sanitization, Auth (→ 11.x)
4. Service-Layer — Connection-Pooling, Retries mit Exponential Backoff, Modell-Tier-Fallback (→ 12.7)
5. Multi-Agent-Architektur & persistentes Memory (→ Kap. 2, Kap. 5)
6. API-Gateway — Auth-Endpunkte, Session-Mgmt, SSE-Streaming
7. Observability (→ 12.1–12.3)
8. Eval-Framework — LLM-Judge (→ Kap. 9)
9. Stress-Testing unter realistischer Concurrency
Rahmung: "Vor dem Go-Live diese 9 Schichten durchgehen." Die anekdotische Zahl "98,4 % bei 1500 Usern" NICHT übernehmen — ersetzen durch "unter realistischer Last testen". ~0,75 Seite.

- [ ] **Step 1: EN-Abschnitt schreiben**

In `v1.4/Building-AI-Agents-Practical-Guide-EN.md` direkt vor `## Appendix A: Architecture Checklists` einfügen: `### 12.8 Production Readiness: The Layer Checklist` + Einleitung + nummerierte 9-Punkte-Checkliste mit Cross-Refs (englisch).

- [ ] **Step 2: DE-Abschnitt schreiben**

In `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` direkt vor `## Anhang A: Architektur-Checklisten` einfügen: `### 12.8 Production-Readiness: Die Schichten-Checkliste` + Einleitung + 9-Punkte-Checkliste, inhaltsgleich.

- [ ] **Step 3: TOC-Einträge ergänzen**

In beiden Dateien TOC-Eintrag für 12.8 unter dem Kapitel-12-Block. Anchor: EN `#128-production-readiness-the-layer-checklist`, DE `#128-production-readiness-die-schichten-checkliste`.

- [ ] **Step 4: Verifizieren**

Run: `grep -n "### 12.8" v1.4/*.md`
Expected: je ein Treffer pro Datei.

Run: `grep -c "98.4\|98,4" v1.4/*.md`
Expected: 0 — die anekdotische Zahl wurde nicht übernommen.

- [ ] **Step 5: Commit**

```bash
git add v1.4/
git commit -m "v1.4: add section 12.8 — production-readiness layer checklist"
```

---

## Task 7: Abschnitt 12.9 "Production-Monitoring"

**Files:**
- Modify: `v1.4/Building-AI-Agents-Practical-Guide-EN.md` (neuer Abschnitt direkt nach 12.8, vor `## Appendix A:`)
- Modify: `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` (analog)

**Content-Brief (Spec §4.5):**
- Klare Abgrenzung zu Kapitel 9: Kap. 9 baut das Eval-System, 12.9 ist die Betriebsschleife des laufenden Prod-Systems. Diesen Unterschied im ersten Absatz benennen.
- Vollständiges Conversation-Recording — "der Bug steckt in der Konversation, nicht im Stacktrace".
- Annotation-Queue: nicht alles reviewen; filtern nach Negativ-Feedback, High-Cost-Interaktionen, Anomalien. Review mit Rubric (hilfreich? Intent verstanden? richtiger Pfad?).
- Automatisierte LLM-Evals auf einem Sample des Prod-Traffics (Themen-Relevanz, Tool-Auswahl-Genauigkeit, Format-Treue).
- Closed-Loop: schlechte Konversation → Eval-Dataset → Fix → Test → in Prod validieren. Cross-Ref 9.2 (Eval-Harness), 12.3 (Kontinuierliche Verbesserung).
- "Tests fangen nur ~10 %" relativiert als "den Großteil decken erst echte Nutzer auf" — keine harte Prozentzahl behaupten.
- ~0,75 Seite.

- [ ] **Step 1: EN-Abschnitt schreiben**

Direkt nach dem 12.8-Block, vor `## Appendix A:`, einfügen: `### 12.9 Production Monitoring` + Fließtext (englisch) gemäß Content-Brief.

- [ ] **Step 2: DE-Abschnitt schreiben**

Analog in der DE-Datei: `### 12.9 Production-Monitoring` + Fließtext (deutsch), inhaltsgleich.

- [ ] **Step 3: TOC-Einträge ergänzen**

In beiden Dateien TOC-Eintrag für 12.9. Anchor: EN `#129-production-monitoring`, DE `#129-production-monitoring`.

- [ ] **Step 4: Verifizieren**

Run: `grep -n "### 12.9" v1.4/*.md`
Expected: je ein Treffer pro Datei.

Run: `grep -n "129-production-monitoring" v1.4/*.md`
Expected: je ein TOC-Treffer pro Datei.

- [ ] **Step 5: Commit**

```bash
git add v1.4/
git commit -m "v1.4: add section 12.9 — production monitoring"
```

---

## Task 8: Anhang A — 9-Schichten-Readiness-Checkliste spiegeln

**Files:**
- Modify: `v1.4/Building-AI-Agents-Practical-Guide-EN.md` (`## Appendix A: Architecture Checklists`)
- Modify: `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` (`## Anhang A: Architektur-Checklisten`)

**Content-Brief (Spec §4.4):** In Anhang A eine kompakte Checklisten-Variante der 9 Production-Readiness-Schichten aus 12.8 ergänzen — als abhakbare Liste (`- [ ] ...`), ohne die Fließtext-Erklärungen, mit kurzem Verweis auf 12.8 für die Details.

- [ ] **Step 1: EN-Checkliste ergänzen**

In `## Appendix A: Architecture Checklists` einen neuen Unterblock "Production-Readiness Layers" mit 9 Checkbox-Zeilen ergänzen (eine pro Schicht aus Task 6), plus Verweis "see 12.8".

- [ ] **Step 2: DE-Checkliste ergänzen**

Analog in `## Anhang A: Architektur-Checklisten`, inhaltsgleich, Verweis "siehe 12.8".

- [ ] **Step 3: Verifizieren**

Run: `grep -n "Production-Readiness\|Production Readiness" v1.4/*.md`
Expected: Treffer sowohl in Kapitel 12 (12.8) als auch in Anhang A.

- [ ] **Step 4: Commit**

```bash
git add v1.4/
git commit -m "v1.4: mirror production-readiness checklist into Appendix A"
```

---

## Task 9: Hygiene — Kapitel-12-Reihenfolge DE/EN angleichen

**Files:**
- Modify: `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` (Kapitel-12-Intro-Subsections)

**Content-Brief (Spec §7):** Die unnummerierten Intro-Subsections von Kapitel 12 stehen in DE und EN in unterschiedlicher Reihenfolge. EN-Reihenfolge ist die Referenz: Monitoring Strategy → Error Handling → Continuous Improvement → Modern Deployment Platforms. DE hat aktuell: Monitoring-Strategie → Fehlerbehandlung → **Deployment-Plattformen → Kontinuierliche Verbesserung** (vertauscht). In der DE-Datei die Blöcke `### Deployment-Plattformen` und `### Kontinuierliche Verbesserung` so umordnen, dass `### Kontinuierliche Verbesserung` VOR `### Deployment-Plattformen` steht. Nur diese zwei Blöcke verschieben, Inhalt unverändert lassen.

- [ ] **Step 1: Reihenfolge in der DE-Datei korrigieren**

In `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md`, Kapitel-12-Intro: den kompletten Block `### Kontinuierliche Verbesserung` (Heading + Absatz) vor den Block `### Deployment-Plattformen` ziehen. Die `> Kernergebnisse Kapitel 12`-Box bleibt an ihrer Position danach.

- [ ] **Step 2: Verifizieren**

Run: `grep -n "^### \(Monitoring-Strategie\|Fehlerbehandlung\|Deployment-Plattformen\|Kontinuierliche Verbesserung\)" v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md`
Expected: Reihenfolge der Zeilen ist Monitoring-Strategie, Fehlerbehandlung, Kontinuierliche Verbesserung, Deployment-Plattformen.

- [ ] **Step 3: Commit**

```bash
git add v1.4/
git commit -m "v1.4: align chapter 12 intro subsection order between DE and EN"
```

---

## Task 10: Harness-Diagramm (Mermaid-Pipeline) erzeugen und einbinden

**Files:**
- Modify: `tools/render-new-diagrams.mjs` (neuer Eintrag im `diagrams`-Array)
- Create: `assets/diagrams/abb-3-6-de.svg`, `assets/diagrams/abb-3-6-en.svg` (vom Script erzeugt)
- Modify: `v1.4/Building-AI-Agents-Practical-Guide-EN.md` (Bild in 3.6)
- Modify: `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` (Bild in 3.6)

- [ ] **Step 1: Diagramm-Eintrag in render-new-diagrams.mjs ergänzen**

Im `diagrams`-Array von `tools/render-new-diagrams.mjs` als letztes Element ergänzen:

```javascript
  ,{
    id: '3-6',
    captionDe: 'Das Agent-Harness: Loop, Tools, Context-Management und Error-Handling um den Modell-Kern',
    captionEn: 'The agent harness: loop, tools, context management, and error handling around the model core',
    codeDe: `flowchart TD
  M["LLM-Kern<br/>(das Modell)"] --> L["Agent-Loop"]
  L --> T["Primitive Tools<br/>Read / Write / Exec"]
  T --> CM["Context-Management<br/>Was sieht das Modell, wann?"]
  CM --> EH["Error-Handling<br/>Retry / Fallback"]
  EH --> L
  L --> O["Aktion / Ergebnis"]`,
    codeEn: `flowchart TD
  M["LLM core<br/>(the model)"] --> L["Agent loop"]
  L --> T["Primitive tools<br/>Read / Write / Exec"]
  T --> CM["Context management<br/>What the model sees, when"]
  CM --> EH["Error handling<br/>Retry / fallback"]
  EH --> L
  L --> O["Action / result"]`
  }
```

Außerdem den Kommentar `// Vier Diagramme in zwei Sprachen (DE + EN)` auf `// Fünf Diagramme in zwei Sprachen (DE + EN)` aktualisieren.

- [ ] **Step 2: Render-Script ausführen**

Run (vom Repo-Root): `node tools/render-new-diagrams.mjs`
Expected: Ausgabe enthält `OK assets/diagrams/abb-3-6-de.svg` und `OK assets/diagrams/abb-3-6-en.svg` (sowie die vier bestehenden Diagramme). Kein `FAIL`.

Falls `beautiful-mermaid` nicht installiert ist: `npm install` im Repo-Root ausführen, dann erneut rendern.

- [ ] **Step 3: SVG-Dateien prüfen**

Run: `ls -la assets/diagrams/abb-3-6-*.svg && head -c 80 assets/diagrams/abb-3-6-en.svg`
Expected: beide Dateien existieren, nicht leer, beginnen mit `<svg` o.ä.

- [ ] **Step 4: Bild in beide 3.6-Abschnitte einbinden**

In `v1.4/Building-AI-Agents-Practical-Guide-EN.md`, Abschnitt 3.6, an passender Stelle einfügen:
```markdown
![The agent harness: loop, tools, context management, and error handling around the model core](../assets/diagrams/abb-3-6-en.svg)
```
In `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md`, Abschnitt 3.6:
```markdown
![Das Agent-Harness: Loop, Tools, Context-Management und Error-Handling um den Modell-Kern](../assets/diagrams/abb-3-6-de.svg)
```
Den Bildbezug am bestehenden Muster der v1.3-Diagramm-Einbindungen ausrichten (Pfad-Präfix `../assets/diagrams/` prüfen, ggf. an v1.3-Konvention angleichen).

- [ ] **Step 5: Verifizieren**

Run: `grep -n "abb-3-6" v1.4/*.md`
Expected: je ein Treffer pro Datei (DE referenziert `-de`, EN referenziert `-en`).

- [ ] **Step 6: Commit**

```bash
git add tools/render-new-diagrams.mjs assets/diagrams/abb-3-6-de.svg assets/diagrams/abb-3-6-en.svg v1.4/
git commit -m "v1.4: add harness diagram via mermaid pipeline, embed in section 3.6"
```

---

## Task 11: Hero-Diagramm (7-Schichten-Stack) mit diagram-design erzeugen

**Files:**
- Create: `assets/hero-v1.4/agent-stack.html` (eigenständiges Editorial-Artefakt)
- Create: `assets/diagrams/abb-1-5-de.svg`, `assets/diagrams/abb-1-5-en.svg` (aus dem HTML extrahiertes SVG)
- Modify: `v1.4/Building-AI-Agents-Practical-Guide-EN.md` (Hero oben + Bild in 1.5)
- Modify: `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` (analog)

**Hinweis:** `diagram-design` ist ein Kontext-/Template-Pack, kein deterministischer Renderer (Subagent-Recherche, Spec §6.2). Der Executor klont das Repo nur, um dessen Referenz-Templates zu lesen, und baut das SVG entlang dieser Vorlagen — der `Skill`-Tool-Mechanismus wird nicht gebraucht.

- [ ] **Step 1: diagram-design-Repo klonen (nur als Template-Referenz)**

```bash
git clone https://github.com/cathrynlavery/diagram-design.git ~/Documents/repos/diagram-design
```
Dann lesen: `~/Documents/repos/diagram-design/skills/diagram-design/SKILL.md`, `references/style-guide.md` und `references/type-layers.md` (Pfade ggf. an die Ist-Struktur des Repos anpassen).

- [ ] **Step 2: Brand-Tokens festlegen**

Für das Hero gelten die Guide-Brand-Tokens (NICHT der helle Editorial-Default von diagram-design): Hintergrund Dark-Slate `#1e293b`, Vordergrund `#cbd5e1`, Akzent `#3b82f6`, Muted `#64748b`, Font `Inter`. Diese Werte beim Aufbau des SVG verwenden, damit das Hero zum Guide passt.

- [ ] **Step 3: Hero-HTML mit 7-Schichten-Stack bauen**

Eine eigenständige HTML-Datei `assets/hero-v1.4/agent-stack.html` mit inline-SVG erstellen, entlang der `type-layers.md`-Vorlage von diagram-design (vertikaler Schichten-Stack). Sieben Schichten von oben nach unten, mit den Brand-Tokens aus Step 2:
1. Interface
2. Runtime
3. Protocol (MCP)
4. Tools & Sandboxes
5. Knowledge & Memory
6. Models
7. Evals & Observability
Titel/Untertitel: "The 2026 Agent Stack" / "Der Agent-Stack 2026". Sieben Schichten überschreiten das 6-Schichten-Limit der diagram-design-Layer-Vorlage bewusst — Layout entsprechend anpassen (kompaktere Schichthöhe), kein Abschneiden.

- [ ] **Step 4: SVG für die Markdown-Einbindung extrahieren**

Aus dem inline-SVG der HTML-Datei zwei eingebundene SVG-Dateien ableiten: `assets/diagrams/abb-1-5-en.svg` (Beschriftungen englisch) und `assets/diagrams/abb-1-5-de.svg` (deutsche Schicht-Beschreibungen/Untertitel; die Schicht-Namen Interface/Runtime/Protocol/Models etc. bleiben als etablierte Fachbegriffe stehen). Beide als valide eigenständige `.svg`-Dateien speichern.

- [ ] **Step 5: Hero oben in beide Guide-Dateien einbinden**

In `v1.4/Building-AI-Agents-Practical-Guide-EN.md` direkt nach dem Versions-/Titelblock und VOR `## Table of Contents` das Hero einbinden:
```markdown
![The 2026 Agent Stack](../assets/diagrams/abb-1-5-en.svg)
```
In `v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md` analog vor `## Inhaltsverzeichnis`:
```markdown
![Der Agent-Stack 2026](../assets/diagrams/abb-1-5-de.svg)
```

- [ ] **Step 6: Dasselbe Bild in Abschnitt 1.5 einbinden**

In Abschnitt 1.5 (Task 2) beider Dateien dasselbe SVG als Abbildung einbinden (EN: `abb-1-5-en.svg`, DE: `abb-1-5-de.svg`), mit einer Bildunterschrift im Stil der übrigen Abbildungen.

- [ ] **Step 7: Verifizieren**

Run: `ls -la assets/hero-v1.4/agent-stack.html assets/diagrams/abb-1-5-*.svg`
Expected: alle drei Dateien existieren, nicht leer.

Run: `grep -c "abb-1-5" v1.4/Building-AI-Agents-Practical-Guide-EN.md`
Expected: 2 (Hero oben + Abbildung in 1.5).

Run: `head -c 80 assets/diagrams/abb-1-5-de.svg`
Expected: beginnt mit `<svg` o.ä., valides SVG.

- [ ] **Step 8: Commit**

```bash
git add assets/hero-v1.4/ assets/diagrams/abb-1-5-de.svg assets/diagrams/abb-1-5-en.svg v1.4/
git commit -m "v1.4: add 7-layer agent stack hero diagram (diagram-design), embed as hero and in 1.5"
```

---

## Task 12: README, CITATION.cff und ROADMAP-v1.4

**Files:**
- Modify: `README.md`
- Modify: `CITATION.cff`
- Create: `_meta/ROADMAP-v1.4.md`

- [ ] **Step 1: README "Read the Guide"-Tabelle aktualisieren**

In `README.md` die Tabelle so ändern, dass v1.4 die aktuelle Edition ist:
- EN-Zeile → `[Building AI Agents — The Practical Guide (v1.4)](v1.4/Building-AI-Agents-Practical-Guide-EN.md)`
- DE-Zeile → `[KI-Agenten entwickeln — Der Praxisleitfaden (v1.4)](v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md)`
- Den Hinweis auf ältere Versionen um v1.3 ergänzen: `Older versions: v1.3/ (April 2026), v1.2/ ..., archive/v1.1/ ...`

- [ ] **Step 2: README Versions-Überschrift und "What's new" aktualisieren**

- Die Zeile `**Version 1.3 (April 2026)** — ...` ersetzen durch eine v1.4-Beschreibung.
- Einen neuen Abschnitt `## What's new in v1.4` ergänzen (vor oder anstelle von "What's new in v1.3"; "What's new in v1.3" als kurzen Verweis behalten oder nach unten verschieben). Inhalt: Abschnitt 1.5 (Agent-Stack-Modell + Hero-Diagramm), 3.6 (Harness-Konzept), 8.5-Erweiterung (Inter-Agent-Retrieval-Validierung), 12.8 (Production-Readiness-Checkliste), 12.9 (Production-Monitoring), 4.5-Erweiterung (systematische Skill-Findung).
- Den deutschen README-Teil ("Was ist neu in v1.3") analog um "Was ist neu in v1.4" ergänzen.

- [ ] **Step 3: README Repo-Layout und Diagrammzahl korrigieren**

- Im Repo-Layout-Block `v1.4/` als aktuelle Edition ergänzen, `v1.3/` als vorherige.
- Die Beschreibung von `sections/` korrigieren — sie enthält nicht nur "appendices E, F, G", sondern auch Kapitel-Rewrite-Fragmente; präziser formulieren (z.B. "section sources and appendix files").
- Die Diagrammzahl korrigieren. Run zur Ermittlung: `ls assets/diagrams/*.svg | wc -l`. Den Ist-Wert in der README-Zeile statt "11 architecture diagrams" einsetzen.

- [ ] **Step 4: CITATION.cff aktualisieren**

In `CITATION.cff`:
- `version: "1.2"` → `version: "1.4"`
- `date-released: "2026-04-30"` → `date-released: "2026-05-17"`

- [ ] **Step 5: _meta/ROADMAP-v1.4.md anlegen**

`_meta/ROADMAP-v1.4.md` erstellen — kurz (~30 Zeilen): Ziel der v1.4 (punktuelle Ergänzung aus 6 "Process Idea"-Trello-Karten), die 6 Story→Abschnitt-Zuordnungen als Tabelle, der Punktuell-Ansatz, Verweis auf die Spec `docs/superpowers/specs/2026-05-17-agents-v14-update-design.md`.

- [ ] **Step 6: Verifizieren**

Run: `grep -n "v1.4\|1.4" CITATION.cff && grep -c "v1.4" README.md && ls _meta/ROADMAP-v1.4.md`
Expected: CITATION zeigt version 1.4; README enthält mehrere v1.4-Treffer; ROADMAP-Datei existiert.

Run: `ls assets/diagrams/*.svg | wc -l` und prüfen, dass dieselbe Zahl in README.md steht.

- [ ] **Step 7: Commit**

```bash
git add README.md CITATION.cff _meta/ROADMAP-v1.4.md
git commit -m "v1.4: update README, CITATION, and add v1.4 roadmap"
```

---

## Task 13: Abschluss-Verifikation

**Files:** keine Änderung — reine Prüfung. Falls Fehler gefunden werden, im jeweiligen Task-Bereich beheben und nachcommitten.

- [ ] **Step 1: Alle neuen Abschnitte vorhanden**

Run: `for f in v1.4/*.md; do echo "== $f =="; grep -cE "### (1\.5|3\.6|12\.8|12\.9)" "$f"; done`
Expected: je Datei der Wert 4.

- [ ] **Step 2: TOC-Anker vollständig**

Run: `grep -n "15-the-2026-agent-stack\|36-the-agent-harness\|128-production-readiness\|129-production-monitoring" v1.4/Building-AI-Agents-Practical-Guide-EN.md`
Expected: vier TOC-Treffer.
Run analog für die DE-Datei mit den DE-Ankern.

- [ ] **Step 3: DE/EN-Strukturparität**

Run: `diff <(grep -oE "^#{2,3} " v1.4/Building-AI-Agents-Practical-Guide-EN.md | sort | uniq -c) <(grep -oE "^#{2,3} " v1.4/KI-Agenten-entwickeln-Praxisleitfaden-DE.md | sort | uniq -c)`
Expected: identische Anzahl von `##`- und `###`-Headings in beiden Dateien.

- [ ] **Step 4: Keine v1.3-Editionsreste**

Run: `grep -n "Version 1.3\|April 2026 (Update" v1.4/*.md`
Expected: keine Treffer (Code-Beispiele mit `v1.3.0` sind erlaubt und kein Treffer dieses Musters).

- [ ] **Step 5: Diagramme eingebunden und vorhanden**

Run: `grep -c "abb-3-6\|abb-1-5" v1.4/Building-AI-Agents-Practical-Guide-EN.md && ls assets/diagrams/abb-3-6-*.svg assets/diagrams/abb-1-5-*.svg`
Expected: mindestens 3 Einbindungs-Treffer (Harness 1x + Stack 2x); alle vier SVG-Dateien existieren.

- [ ] **Step 6: Verbotene Inhalte nicht vorhanden**

Run: `grep -n "tiktok\|vm.tiktok" v1.4/*.md`
Expected: keine Treffer (Karten-Quelllinks dürfen nicht im Guide stehen).

- [ ] **Step 7: Spec-Abnahmekriterien durchgehen**

Die Liste in `docs/superpowers/specs/2026-05-17-agents-v14-update-design.md` §9 Punkt für Punkt gegen das Ergebnis prüfen. Bei Lücke: beheben und nachcommitten.

- [ ] **Step 8: Abschluss-Commit (falls Fixes nötig waren)**

```bash
git add -A
git commit -m "v1.4: final verification fixes"
```

(Wenn Step 1–7 ohne Fund durchlaufen, entfällt dieser Commit.)

---

## Nach Abschluss

Branch `v1.4-update` ist fertig. Optionen: Merge nach `main`, oder PR erstellen — über die Sub-Skill `superpowers:finishing-a-development-branch` entscheiden.
