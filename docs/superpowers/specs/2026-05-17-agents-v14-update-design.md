# Design: agents-Repo v1.4 — Punktuelle Ergänzungen aus 6 Stories

**Datum:** 2026-05-17
**Autor:** Fabian Bäumler / DeepThink AI
**Status:** Freigegeben (Brainstorming abgeschlossen)

## 1. Kontext & Ziel

Das Repo ist der Markdown-Leitfaden *Building AI Agents — The Practical Guide*
(DE + EN), aktuell **v1.3** (6 Teile / 12 Kapitel / 7 Anhänge). Es soll eine
**v1.4**-Edition entstehen, gespeist aus 6 Trello-Karten der Liste "Process Idea"
(Board Consulting). Jede Karte ist eine strukturierte Zusammenfassung eines kurzen
Videos — also **Sekundärquelle**, keine Primärforschung.

Ziel: Das *genuin Neue* aus den 6 Karten **punktuell** in die bestehende Struktur
einarbeiten. Keine neuen Kapitel, kein Umbau, keine Dubletten zu Bestehendem.

## 2. Quellmaterial — die 6 Karten

1. **AI Agent Harness Explained** — Harness = Loop + Primitiv-Tools + Context-Mgmt
   + Error-Handling; warum dasselbe LLM in Claude Code / Cursor / Codex anders wirkt;
   minimales Harness = While-Loop + Read-File-Tool + eine Textdatei.
2. **AI Agent Stack 2026** — 7-Schichten-Stack: Interface, Runtime, Protocol (MCP),
   Tools + Sandboxes, Knowledge + Memory, Models, Evals + Observability.
3. **Multi-Agent RAG Validation Fixes** — Inter-Agent-Misinformation, Downstream-Loss,
   Retrieval an jedem Hop validieren, harte Relevanz-Schwellen, "lieber nichts als Rauschen".
4. **9 AI Agent Prod Layers** — 9-Schichten-Production-Readiness-Modell.
5. **AI Agent Monitoring Setup** — Conversation-Recording, Annotation-Queue mit Filtern,
   Online-Evals auf Prod-Traffic, Closed-Loop ins Eval-Dataset.
6. **Agentic OS Three Steps** — Methodik Domain → Tasks → Skills → Automation.

**Out of scope (vom User ausgeschlossen):** die 3 GDPR/Compliance-Karten, die Karte
"Claude Generall". Diese Karten werden in v1.4 nicht verarbeitet.

## 3. Ansatz

Neue Edition `v1.4/`, **kein roher Vollklon** von `v1.3/`. Nur die zwei
Reader-Hauptdateien werden übernommen und editiert:

```
v1.4/
  Building-AI-Agents-Practical-Guide-EN.md
  KI-Agenten-entwickeln-Praxisleitfaden-DE.md
```

Die v1.3-Zwischenartefakte `sections/` und `snippets/` werden **nicht** mitkopiert
(sie duplizieren bereits Inhalte der Hauptdateien — bekannte v1.3-Strukturdrift).
`v1.3/`, `v1.2/`, `archive/v1.1/` bleiben als eingefrorene Editionen unangetastet.

## 4. Änderungs-Spezifikation pro Story

Für jede neue Sektion gilt: ~0,5–1 Seite, im Stil/Ton der bestehenden Kapitel,
DE + EN parallel, Terminologie konsistent zu v1.3.

### 4.1 Harness → Neuer Abschnitt 3.6 "Das Harness" / "The Harness"

**Ort:** Ende von Kapitel 3 (Die 4 kritischen Architekturlücken). Hängt als 3.6 an
(aktuell endet Kap. 3 bei 3.5) — kein Renumbering.

**Inhalt:**
- Definition: Das Harness ist alles, was ein LLM zu einem arbeitenden Agenten
  verbindet — der Loop, der Satz primitiver Tools, Context-Management, Error-Handling.
  Das LLM ist der Motor, das Harness das Chassis.
- "Warum dasselbe Modell sich anders anfühlt": Claude Code, Cursor und Codex nutzen
  dieselben Basismodelle, fühlen sich aber unterschiedlich an — wegen Harness-
  Designentscheidungen (Tool-Oberfläche, wann Kontext gezeigt wird, Fehlerbehandlung).
- Das minimale Harness: While-Loop + ein Read-File-Tool + eine Textdatei als
  Scratch-Memory = ein erstes funktionierendes Agent-Harness.
- Brückenschlag: Die 4 Architekturlücken aus Kap. 3 sind die Bausteine; das Harness
  ist, wie sie als Loop zusammenlaufen. 3.6 benennt diese Klammer.
- **Cross-Ref statt Doppeln:** Progressive Disclosure wird NICHT neu erklärt —
  Verweis auf 4.6. Context-Management — Verweis auf Kapitel 5.

### 4.2 Stack 2026 → Neuer Abschnitt 1.5 "Der Agent-Stack 2026" / "The 2026 Agent Stack"

**Ort:** Ende von Kapitel 1 (aktuell 1.1–1.4). Hängt als **1.5** an — kein
Renumbering. (Der Harness-Abschnitt 3.6 liegt in Kapitel 3, kollidiert also nicht.)

**Inhalt:**
- 7-Schichten-Orientierungsmodell als Lesekarte für den ganzen Leitfaden:
  Interface, Runtime, Protocol (MCP), Tools & Sandboxes, Knowledge & Memory,
  Models, Evals & Observability.
- Ein kurzer Absatz pro Schicht, jeweils mit Querverweis, wo der Guide die Schicht
  vertieft: Runtime → Kap. 3 + 3.6; Protocol/MCP → Kap. 4; Tools & Sandboxes →
  Kap. 11; Knowledge & Memory → Kap. 5 + Kap. 7–8; Models → Anhang E;
  Evals & Observability → Kap. 9 + Kap. 12.
- "Knowledge ≠ Memory" nur **grob rahmen**; die Begriffspräzision bleibt in Kap. 5
  (Verweis auf 5.2–5.4), um die bestehende Memory-Definition nicht aufzuweichen.
- Rahmung: "Nutze diese 7 Schichten als Landkarte für den Rest des Leitfadens."
- 1 neues Diagramm (vertikaler 7-Schichten-Stack), siehe §6.

### 4.3 Multi-Agent RAG Validation → Erweiterung von 8.5

**Ort:** Innerhalb / direkt im Anschluss an Abschnitt 8.5 "Multi-Agent Query
Processing Pipeline". **Kein** neuer Abschnitt 8.10 (Codex: 8.10 säße zu spät,
nach der Fallstudie 8.9). Integration als Erweiterung von 8.5 — kein Renumbering.

**Inhalt:**
- Fehlermodus: Eine schwache Retrieval-Stufe in einem frühen Agenten propagiert als
  selbstbewusste Ausgabe nach unten ("Inter-Agent-Misinformation", "Downstream-Loss").
- Bessere/größere Modelle lösen das nicht — sie erzeugen "höher aufgelöste
  Halluzinationen".
- Vier Fixes: Retrieval-Qualität an *jedem* Hop validieren (nicht nur am ersten);
  harte Relevanz-Schwellen; "insufficient information" zurückgeben statt aus Rauschen
  zu synthetisieren; jede Agenten-Retrieval-Schnittstelle als eigenen Risikopunkt
  behandeln.
- **Cross-Ref:** 8.6 Re-Ranking (komplementär), Kapitel 9 (Eval-Gates).

### 4.4 9 Prod Layers → Neuer Abschnitt 12.8 "Production-Readiness-Checkliste"

**Ort:** Nach 12.7 (Kostensteuerung). Wird 12.8 — kein Renumbering.

**Inhalt:**
- Explizit eine **Synthese-/Verdichtungs-Checkliste**, KEIN konkurrierendes
  Taxonomie-System. Jede der 9 Schichten ist eine Checklisten-Zeile mit hartem
  Querverweis auf das Kapitel, das sie behandelt:
  1. Modularer Codebase / Config-Hygiene (Debug ≠ Prod)
  2. Datensicherheit (DTOs, keine Roh-Modelle ans Frontend) → Kap. 11
  3. Security (Rate-Limiting, Input-Sanitization, Auth) → 11.x
  4. Service-Layer (Connection-Pooling, Retries mit Exponential Backoff,
     Modell-Tier-Fallback) → 12.7
  5. Multi-Agent-Architektur & persistentes Memory → Kap. 2, Kap. 5
  6. API-Gateway (Auth-Endpunkte, Session-Mgmt, SSE-Streaming)
  7. Observability → 12.1–12.3
  8. Eval-Framework (LLM-Judge) → Kap. 9
  9. Stress-Testing unter realistischer Concurrency
- Rahmung: "Vor dem Go-Live diese 9 Schichten durchgehen; jede verweist auf das
  Kapitel, das sie abdeckt."
- **Spiegelung:** Als Checklisten-Eintrag in Anhang A ergänzen.
- Anekdotische Zahl "98,4 % bei 1500 Concurrent Users" → **weglassen**, ersetzt durch
  "unter realistischer Last testen".

### 4.5 Monitoring → Neuer Abschnitt 12.9 "Production-Monitoring"

**Ort:** Nach 12.8. Wird 12.9 — kein Renumbering.

**Inhalt:**
- Klar abgegrenzt von Kapitel 9: Kap. 9 *baut* das Eval-System, 12.9 ist die
  *Betriebsschleife* des laufenden Prod-Systems.
- Vollständiges Conversation-Recording — "der Bug steckt in der Konversation, nicht
  im Stacktrace".
- Annotation-Queue: nicht alles reviewen; filtern nach Negativ-Feedback, High-Cost-
  Interaktionen, Anomalien. Review mit Rubric (hilfreich? Intent verstanden? richtiger
  Pfad?).
- Automatisierte LLM-Evals auf einem Sample des Prod-Traffics (Themen-Relevanz,
  Tool-Auswahl-Genauigkeit, Format-Treue).
- Closed-Loop: schlechte Konversation → Eval-Dataset → Fix → Test → in Prod
  validieren. **Cross-Ref:** 9.2 (Eval-Harness), 12.3 (Kontinuierliche Verbesserung).
- "Tests fangen nur ~10 %" → relativiert als "den Großteil decken erst echte Nutzer auf".

### 4.6 Agentic OS → Erweiterung von 4.5

**Ort:** Abschnitt 4.5 "Building a Systematic Agent Library" — derzeit nur ein kurzer
Absatz. Wird inhaltlich erweitert, **kein** neuer Abschnitt.

**Inhalt:**
- Methode zur systematischen Skill-Findung: **Domain → Tasks → Skills → Automation**.
  Arbeit in Domänen zerlegen; je Domäne die wiederkehrenden Tasks auflisten; jeden
  Task in einen definierten Skill überführen; jeden Skill auf Automatisierungs-
  potenzial prüfen; pro Domäne wiederholen.
- Rahmung: ersetzt Ad-hoc-Prompting durch absichtsvolle Abdeckung.
- Engineering-Fokus halten; die Personal-Productivity-/Dashboard-Teile der Karte
  entfallen.

## 5. Querschnitt-Änderungen

- **TOC** in beiden Hauptdateien ergänzen: neue Einträge 1.5, 3.6, 12.8, 12.9.
  (8.5- und 4.5-Erweiterungen erzeugen keine neuen TOC-Einträge.)
- **Versions-Header/Footer** in beiden Dateien → v1.4 (Mai 2026).
- **README.md:** "Read the Guide"-Tabelle auf v1.4; neuer Abschnitt "What's new in
  v1.4" (DE + EN); Repo-Layout-Beschreibung aktualisieren; Diagrammzahl korrigieren
  (siehe §7).
- **CITATION.cff:** Version → 1.4 (steht aktuell fälschlich auf 1.2).
- **`_meta/ROADMAP-v1.4.md`:** kurz, dokumentiert die 6-Karten-Quelle und den
  Punktuell-Ansatz.

## 6. Diagramme

### 6.1 Inline-Diagramm — Harness-Anatomie (Mermaid-Pipeline)

Ein neues Diagramm über die **bestehende** Pipeline `tools/render-new-diagrams.mjs`
(deterministisch, Mermaid via `beautiful-mermaid`, zweisprachig, Dark-Theme):

- **Harness-Anatomie** (Abschnitt 3.6) — Flowchart: LLM-Kern + Loop + Primitiv-Tools
  + Context-Mgmt + Error-Handling.

Als neuer Eintrag im `diagrams`-Array von `render-new-diagrams.mjs`, mit denselben
`id`/`captionDe`/`captionEn`/`codeDe`/`codeEn`-Feldern und demselben Theme-Objekt.
Output nach `assets/diagrams/`, Einbindung per Markdown-Image-Tag.

### 6.2 Hero-Diagramm — 7-Schichten-Agent-Stack (diagram-design-Skill)

Das **Signatur-/Hero-Bild der v1.4-Edition**: der 7-Schichten-Agent-Stack, editorial
gestaltet mit dem Skill `cathrynlavery/diagram-design`. Doppelnutzung:
- als Hero-Visual oben in beiden Guide-Hauptdateien (optional zusätzlich README)
- als Abbildung in Abschnitt 1.5

Damit gibt es nur **ein** Stack-Diagramm — keine zusätzliche Mermaid-Variante.

Umsetzung:
- diagram-design-Skill installieren (Repo klonen, `skills/diagram-design/` nach
  `~/.claude/skills/` symlinken).
- **Brand-Tokens des Guides** in den `style-guide.md` des Skills geben — Dark-Slate
  (`#1e293b`), Akzent (`#3b82f6`), Font Inter — damit das Hero zum Guide passt und
  nicht im hellen Editorial-Default landet.
- Output ist eine eigenständige HTML-Datei mit inline-SVG; als Artefakt separat
  ablegen (`assets/hero-v1.4/`). Für die Markdown-Einbindung das SVG aus dem HTML
  extrahieren, nach `assets/diagrams/` legen und per Image-Tag einbinden.
- Der Skill ist LLM-generiert (nicht deterministisch) — für ein einmaliges Hero-Bild
  akzeptabel; die Inline-Diagramme bleiben deterministisch via Mermaid.

## 7. Repo-Hygiene-Fixes (gezielt, im Rahmen der v1.4-Arbeit)

Von Codex gefundene Inkonsistenzen, die in v1.4 mitkorrigiert werden:

- **CITATION.cff** steht auf `version: "1.2"` → auf 1.4 setzen.
- **README** nennt "11 architecture diagrams"; tatsächlich liegen **19** SVG-Dateien
  in `assets/diagrams/` → Zahl korrigieren.
- **README**-Repo-Layout beschreibt `sections/` als "appendices E, F, G", enthält aber
  auch `kapitel_9_rewrite.md` etc. → Beschreibung präzisieren.
- **Kapitel-12-Reihenfolge DE ≠ EN:** Die unnummerierten Intro-Subsections von Kap. 12
  stehen verschieden — EN: Monitoring Strategy → Error Handling → Continuous
  Improvement → Modern Deployment Platforms; DE: Monitoring-Strategie →
  Fehlerbehandlung → Deployment-Plattformen → Kontinuierliche Verbesserung. In v1.4
  auf eine kanonische Reihenfolge angleichen (EN-Reihenfolge als Referenz:
  ... → Continuous Improvement → Deployment Platforms).

**Bekannter, NICHT behobener v1.3-Defekt (out of scope):** Die nummerierten
Abschnitte 12.4–12.7 liegen physisch hinter der `# Appendices`-Überschrift statt im
Kapitel-12-Block. v1.4 erbt das; 12.8/12.9 werden zur Kontiguität direkt hinter 12.7
platziert. Die Relocation von 12.4–12.9 in den Kapitel-12-Block ist ein separates,
größeres Strukturthema und kein Teil dieses Updates.

## 8. Prinzipien & Constraints

- Karten = Framing-Input; **keine** TikTok-Links als Quellen im Guide.
- Anekdotische Zahlen relativieren oder weglassen (v1.3-Rigorositätsregel).
- Nur genuin neues Material; wo Karten Bestehendes bestätigen → Cross-Ref statt Doppeln.
- DE/EN-Parität; Terminologie konsistent zu v1.3.
- Alle neuen Abschnittsnummern hängen an (1.5, 3.6, 12.8, 12.9) — kein Renumbering.
- `v1.3/`, `v1.2/`, `archive/` bleiben unangetastet.

## 9. Abnahmekriterien

- `v1.4/` enthält beide Guide-Dateien, aufbauend auf v1.3-Inhalt + den 6 Ergänzungen.
- Jedes der 6 Story-Materialien ist an der spezifizierten Stelle vorhanden.
- TOC in beiden Sprachen um 1.5 / 3.6 / 12.8 / 12.9 ergänzt.
- 2 neue Diagramme eingebunden (beide Sprachfassungen): Harness-Anatomie (Mermaid,
  Abschnitt 3.6) und 7-Schichten-Stack als Hero via diagram-design (Abschnitt 1.5).
- README, CITATION.cff, `_meta/ROADMAP-v1.4.md` aktualisiert.
- Keine Dublette von Progressive Disclosure (4.6), Memory-Definition (Kap. 5) oder
  Security-Taxonomie (Kap. 11).
- Hygiene-Fixes aus §7 umgesetzt.
- DE- und EN-Fassung inhaltlich deckungsgleich.
