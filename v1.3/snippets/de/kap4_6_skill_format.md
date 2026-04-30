### 4.6 Skills in der Praxis: Anthropic-Format und eigene Erweiterung

Anthropic Skills haben sich 2026 als De-facto-Standard etabliert. Die Open Spec liegt seit Dezember 2025 vor und wird inzwischen von 32 Tools adoptiert, darunter Claude Code, Codex, Cursor, VS Code und Gemini CLI. Wer ein eigenes Skill-Format definiert, sollte nicht neu erfinden, sondern auf SKILL.md aufsetzen und nur dort erweitern, wo Anthropic schweigt: Versionierung, Risk-Tiering, IO-Vertrag, Test-Pfade. Dieser Abschnitt zeigt wie ein konkretes Skill aussieht, von der Datei-Struktur ueber die Activation bis zum Test-Setup.

#### Anthropic-Skill-Anatomie

Ein Skill ist ein Ordner mit einer Pflicht-Datei `SKILL.md` und optionalen Unterordnern fuer Progressive Disclosure:

```
my-skill/
  SKILL.md            # Pflicht: YAML-Frontmatter + Markdown-Body als System-Prompt
  scripts/            # Optional: deterministische Helfer (Python, Bash)
  references/         # Optional: on-demand-Doku, on-demand vom Modell gezogen
  assets/             # Optional: Templates, Bilder, Beispiel-PDFs
```

`SKILL.md` selbst hat einen YAML-Frontmatter und einen Markdown-Body. Der Body wird zur Laufzeit als System-Prompt eingespielt und sollte unter 500 Zeilen bleiben. Alles, was tiefer geht, gehoert in `references/` und wird vom Modell nur bei Bedarf nachgeladen (Progressive Disclosure).

```yaml
---
name: invoice-generator
description: >
  Generate PDF invoices from order data. Use when user asks to create,
  render, send, or export an invoice, receipt, or bill, especially for
  B2B orders with line items, VAT, and customer addresses.
version: 2.3.1
allowed-tools: [bash, file_write, http_get]
activation: auto
---

# Invoice Generator

Generate professional PDF invoices following the company branding spec.

## Workflow
1. Validate order schema (see references/order_schema.md)
2. Fill assets/invoice_template.html
3. Run scripts/render_pdf.py
4. Save to out/invoices/{invoice_number}.pdf

## Output
ALWAYS report invoice_number, total_amount, file_path.
```

#### `description` als Trigger, nicht der Name

Aktiviert wird ein Skill nicht ueber den `name`, sondern ueber `description`. Das LLM matched User-Intent gegen den Beschreibungstext. Pushy formulieren, mit klaren Trigger-Verben und einem "especially for"-Zusatz fuer Edge Cases:

- Schlecht: `description: Invoice tool` (zu generisch, wird nie zuverlaessig getriggert)
- Schlecht: `description: This skill generates invoices` (passiv, kein Trigger)
- Gut: `description: Generate PDF invoices from order data. Use when user asks to create, render, send, or export an invoice, receipt, or bill, especially for B2B orders with VAT.`

Faustregel: drei Trigger-Verben, ein Domain-Anker, ein "especially for"-Zusatz fuer den Edge Case, der den Skill von Nachbarn abgrenzt.

#### Eigenes Skill-Format = Anthropic + YAML-Overlay

Anthropic spezifiziert weder Versionierung noch Test-Vertrag noch Risk-Level. Genau dort setzt das Overlay an. Wir legen neben `SKILL.md` eine `skill.yaml` ab, die Anthropic-kompatibel bleibt und nur ergaenzt:

```yaml
apiVersion: skill.deepthink.ai/v1
kind: Skill
metadata:
  name: invoice-generator
  version: 2.3.1               # SemVer
  risk_level: medium           # low | medium | high
  audit_required: false
spec:
  io_schema_path: ./io_schema.json
  tools_manifest: ./tools.json
  tests_path: ./tests/goldens.yaml
  registry:
    channel: stable            # stable | canary | dev
    sha: a1b2c3d4
  runtime:
    timeout_seconds: 120
    model_preference: [claude-opus-4-7, claude-sonnet-4-7]
  evaluation:
    pass_threshold: 0.90
    baseline_version: 2.3.0
```

Damit bleibt der Skill in jedem Anthropic-kompatiblen Tool ladbar (die kennen `SKILL.md`, ignorieren `skill.yaml`), waehrend der eigene Runner die Overlay-Felder fuer Versionierung, CI-Gates und Canary-Rollouts nutzt.

#### Kernergebnisse

- Anthropic Skills sind 2026 der einzige framework-agnostische Standard. Eigenes Format heisst SKILL.md plus `skill.yaml`-Overlay, nicht Greenfield.
- `description` ist der Trigger, nicht der `name`. Pushy und mit Edge-Case-Zusatz formulieren.
- Body unter 500 Zeilen, Tiefe via `references/` (Progressive Disclosure) statt eines Mega-Prompts.
- Versionierung, Risk-Level, IO-Vertrag und Test-Pfade gehoeren ins Overlay, nicht in den Frontmatter.
- Vollstaendige Spec siehe Anhang G.
