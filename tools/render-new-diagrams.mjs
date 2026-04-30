import { renderMermaidSVG } from 'beautiful-mermaid'
import { writeFileSync, mkdirSync } from 'fs'

mkdirSync('assets/diagrams', { recursive: true })

const theme = {
  bg: '#1e293b',
  fg: '#cbd5e1',
  accent: '#3b82f6',
  muted: '#64748b'
}

// Vier Diagramme in zwei Sprachen (DE + EN)
const diagrams = [
  {
    id: '5-1',
    captionDe: 'Drei-Schichten-Gedaechtnisarchitektur mit Extraktions-, Konsolidierungs- und Abruf-Pipeline',
    captionEn: 'Three-layer memory architecture with extraction, consolidation, and retrieval pipeline',
    codeDe: `flowchart LR
  I["Interaktion / Tool-Output / Nutzerinput"] --> E["Extraktion"]
  E --> C["Konsolidierung"]
  C --> T{"Typisierung"}
  T --> S["Kurzzeit<br/>Kontextfenster"]
  T --> M["Mittelfristig<br/>DB / Dateien"]
  T --> L["Langzeit<br/>Persistenz"]
  Q["Aktuelle Aufgabe"] --> R["Abruf & Ranking"]
  M --> R
  L --> R
  R --> B["Kontextbudget"]
  B --> S
  S --> A["Agenten-Antwort"]`,
    codeEn: `flowchart LR
  I["Interaction / Tool output / User input"] --> E["Extraction"]
  E --> C["Consolidation"]
  C --> T{"Typing"}
  T --> S["Short-term<br/>Context window"]
  T --> M["Mid-term<br/>DB / Files"]
  T --> L["Long-term<br/>Persistent store"]
  Q["Current task"] --> R["Retrieval & Ranking"]
  M --> R
  L --> R
  R --> B["Context budget"]
  B --> S
  S --> A["Agent response"]`
  },
  {
    id: '6-9',
    captionDe: 'Recursive Language Model: programmatische Zerlegung des Datensatzes statt Direkt-Prompt',
    captionEn: 'Recursive Language Model: programmatic decomposition of the dataset instead of direct prompting',
    codeDe: `flowchart TD
  Q["Frage"] --> P["LLM mit RLM-Prompt"]
  D["Gesamtdatensatz<br/>in Code-Umgebung"] --> X["LLM schreibt Code:<br/>samplen, filtern, chunken"]
  P --> X
  X --> K{"Chunk klein genug?"}
  K -- nein --> X
  K -- ja --> R["Rekursive LLM-Aufrufe<br/>je Chunk"]
  R --> G["Programmatische<br/>Aggregation"]
  G --> A["Finale Antwort"]`,
    codeEn: `flowchart TD
  Q["Question"] --> P["LLM with RLM prompt"]
  D["Full dataset<br/>in code environment"] --> X["LLM writes code:<br/>sample, filter, chunk"]
  P --> X
  X --> K{"Chunk small enough?"}
  K -- no --> X
  K -- yes --> R["Recursive LLM calls<br/>per chunk"]
  R --> G["Programmatic<br/>aggregation"]
  G --> A["Final answer"]`
  },
  {
    id: '8-1',
    captionDe: 'Produktionsreife RAG-Pipeline: Ingest, Retrieval und Antwort mit Quellenangaben',
    captionEn: 'Production-ready RAG pipeline: ingest, retrieval, and answer with citations',
    codeDe: `flowchart LR
  D["Dokumente / PDFs"] --> P["Struktur- oder<br/>bildbasierte<br/>PDF-Verarbeitung"]
  P --> M["LLM-Metadaten-<br/>Anreicherung"]
  M --> I["BM25 + Vector Index"]
  Q["Nutzerfrage"] --> O["Query-Optimierer"]
  O --> C["Sammlungs-<br/>Klassifikator"]
  C --> F["Strukturierte Filter"]
  F --> H["Hybrid Retrieval"]
  I --> H
  H --> RR["Re-Ranking"]
  RR --> Z["Antwort mit<br/>Quellenangaben"]`,
    codeEn: `flowchart LR
  D["Documents / PDFs"] --> P["Structural or<br/>vision-based<br/>PDF parsing"]
  P --> M["LLM metadata<br/>enrichment"]
  M --> I["BM25 + Vector Index"]
  Q["User query"] --> O["Query optimizer"]
  O --> C["Collection<br/>classifier"]
  C --> F["Structured filters"]
  F --> H["Hybrid retrieval"]
  I --> H
  H --> RR["Re-ranking"]
  RR --> Z["Answer with<br/>citations"]`
  },
  {
    id: '11-1',
    captionDe: 'Drei-Schichten-Sicherheitsdurchlauf einer Anfrage durch Eingabe-, Plan-/Tool- und Ausgabe-Guardrails',
    captionEn: 'Three-layer security flow: a request through input, plan/tool, and output guardrails',
    codeDe: `flowchart LR
  U["Nutzeranfrage"] --> IG["Eingabe-Guardrails<br/>Injection, PII, Risk Flags"]
  IG -->|ok| P["Plan erzeugen"]
  IG -->|block| X["Abweisen / Eskalieren"]
  P --> TG["Plan- & Tool-Guardrails<br/>Allowlist, Business Rules"]
  TG -->|high risk| H["Human Approval"]
  H -->|freigegeben| E["Agent & Tools"]
  TG -->|ok| E
  TG -->|verboten| X
  E --> OG["Ausgabe-Guardrails<br/>Grounding, Redaction"]
  OG --> R["Antwort an Nutzer"]
  OG -->|eskalieren| X`,
    codeEn: `flowchart LR
  U["User request"] --> IG["Input guardrails<br/>Injection, PII, Risk Flags"]
  IG -->|ok| P["Build plan"]
  IG -->|block| X["Refuse / escalate"]
  P --> TG["Plan & Tool guardrails<br/>Allowlist, Business Rules"]
  TG -->|high risk| H["Human approval"]
  H -->|approved| E["Agent & Tools"]
  TG -->|ok| E
  TG -->|forbidden| X
  E --> OG["Output guardrails<br/>Grounding, Redaction"]
  OG --> R["Answer to user"]
  OG -->|escalate| X`
  }
]

for (const d of diagrams) {
  for (const lang of ['de', 'en']) {
    const code = lang === 'de' ? d.codeDe : d.codeEn
    const filename = `assets/diagrams/abb-${d.id}-${lang}.svg`
    try {
      const svg = renderMermaidSVG(code, theme)
      writeFileSync(filename, svg)
      console.log(`OK ${filename}`)
    } catch (err) {
      console.error(`FAIL ${filename}: ${err.message}`)
    }
  }
}
