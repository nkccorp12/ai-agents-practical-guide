### 4.6 Skills in Practice: Anthropic Format and Extensions

Anthropic Skills emerged as the de-facto standard in 2026. The open spec has been public since December 2025 and is now adopted by 32 tools, including Claude Code, Codex, Cursor, VS Code, and Gemini CLI. If you define your own skill format, do not reinvent the wheel. Build on top of SKILL.md and only extend where Anthropic stays silent: versioning, risk tiering, IO contract, test paths. This section shows what a concrete skill looks like, from file structure through activation to test setup.

#### Anatomy of an Anthropic Skill

A skill is a folder with one mandatory `SKILL.md` and optional subfolders for progressive disclosure:

```
my-skill/
  SKILL.md            # Required: YAML frontmatter + Markdown body as system prompt
  scripts/            # Optional: deterministic helpers (Python, Bash)
  references/         # Optional: on-demand docs, pulled by the model when needed
  assets/             # Optional: templates, images, sample PDFs
```

`SKILL.md` itself has a YAML frontmatter and a Markdown body. The body is injected as system prompt at runtime and should stay below 500 lines. Anything deeper belongs in `references/` and is loaded by the model on demand (progressive disclosure).

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

#### `description` Is the Trigger, Not the Name

A skill activates not via `name` but via `description`. The LLM matches user intent against the description text. Phrase it pushy, with explicit trigger verbs and an "especially for" tail for edge cases:

- Bad: `description: Invoice tool` (too generic, never reliably triggered)
- Bad: `description: This skill generates invoices` (passive, no trigger)
- Good: `description: Generate PDF invoices from order data. Use when user asks to create, render, send, or export an invoice, receipt, or bill, especially for B2B orders with VAT.`

Rule of thumb: three trigger verbs, one domain anchor, one "especially for" tail to disambiguate from neighboring skills.

#### Custom Format = Anthropic + YAML Overlay

Anthropic does not specify versioning, test contract, or risk level. That is exactly where the overlay lives. Next to `SKILL.md` we ship a `skill.yaml` that stays Anthropic-compatible and only adds:

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

The skill remains loadable by every Anthropic-compatible tool (they parse `SKILL.md`, ignore `skill.yaml`), while your own runner uses the overlay fields for versioning, CI gates, and canary rollouts.

#### Key Takeaways

- Anthropic Skills are the only framework-agnostic standard in 2026. Custom format means SKILL.md plus a `skill.yaml` overlay, not greenfield.
- `description` is the trigger, not `name`. Phrase pushy with an edge-case tail.
- Body below 500 lines, depth via `references/` (progressive disclosure) instead of a mega prompt.
- Versioning, risk level, IO contract, and test paths belong in the overlay, not in the frontmatter.
- Full spec in Appendix G.
