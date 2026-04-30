## Kapitel 9: Selbstverbessernde Multi-Agent-RAG-Systeme

Self-Improvement ist 2026 das verlockendste Versprechen am Markt: DSPy kompiliert Prompts automatisch gegen ein Trainset, TextGrad propagiert Gradienten durch natürliche Sprache, und Anthropic Skills lassen sich grundsätzlich versionieren und tauschen. In Demos wirkt das wie ein sich selbst tunender Stack. In Produktion ist es ein Feld, auf dem Reward Hacking, Evaluator-Drift und Benchmark-Overfitting tagtäglich echte Systeme zerschrotten. Dieses Kapitel zeigt nüchtern, wo automatische Verbesserung tatsächlich Wert liefert (Prompts, Few-Shots, retrieval-Heuristiken), und wo man die Hände wegnimmt: Permissions, Output-Validierung, Money-Movement, Sicherheits-Policies. Der rote Faden ist Outer-Loop mit harten Approval Gates, gefrorenen Baselines und Auto-Revert. Ohne diese drei Mechaniken ist jeder Self-Improvement-Loop ein Risiko-Verstärker, kein Qualitätshebel.

### 9.1 Was Self-Improvement realistisch leisten kann (und was nicht)

Die Trennlinie verläuft entlang von Auditierbarkeit und Reversibilität.

**Geht (mit Eval-Harness und Approval):**
- Prompt-Optimierung gegen ein Goldens-Set (DSPy `BootstrapFewShot`, `MIPROv2`, `GEPA`, TextGrad).
- Few-Shot-Auswahl aus einem kuratierten Beispiel-Pool.
- Retrieval-Heuristiken (Chunking-Strategie, Re-Ranking-Gewichte, Query-Expansion).
- Skill-Vorschläge: ein Agent identifiziert wiederkehrende Workflows und schlägt eine neue `SKILL.md` als Pull Request vor. Promoted wird durch einen Menschen.

**Geht nicht (oder nur mit Sync-Approval):**
- Tool-Permissions und `allowed-tools` Listen. Ein Agent darf seinen eigenen Permission-Scope niemals ausweiten, weil genau dieser Pfad das primäre Reward-Hacking-Ziel ist.
- Output-Validation und Schema-Definitionen. Wenn der Agent das Schema selbst lockert, passt plötzlich jeder Müll durch.
- Money-Movement-Pfade (Refunds, Transfers, Auszahlungen). Reward Hacking schlägt hier direkt in Cash durch.
- Sicherheits-Refusals und Content-Policies. Ein Optimizer erkennt jede Refusal als "Score-Verlust" und optimiert sie weg.
- System-Prompts mit Rollen-Definition oder Constraints ("Du darfst niemals X"). Optimierer lernen, solche Constraints zu paraphrasieren bis sie wirkungslos sind.

**Reward-Hacking-Risiko:** Ein Optimizer maximiert das Eval-Score, nicht den Nutzen. Wenn der Judge "Antwort enthält JSON" rewardet, lernt der Agent, JSON in Refusals zu packen. Wenn der Judge "Antwort ist lang" rewardet (Verbosity Bias, sehr häufig), bekommt man dreiseitige Roman-Antworten auf Yes/No-Fragen. Die Goldens müssen das aktiv abwehren, sonst kompiliert man sich gegen die Wand.

### 9.2 Eval-Harness als Fundament

Ohne Goldens kein Self-Improvement. Punkt.

**Goldens-Set (Mindestgröße 100 manuell kuratierte Cases):**
- 60% Happy Path
- 25% Edge Cases (lange Inputs, leere Felder, Mehrsprachigkeit, Formatabweichungen)
- 15% Adversarial (Prompt Injection, Jailbreak, Out-of-Scope, Verbosity-Falle)

Jeder Case hat `id`, `input`, `expected_output` (oder `expected_behavior`), `tags`, `risk_level`, `human_verified_at`. Datensätze unter 100 Goldens produzieren statistisches Rauschen, das ein Optimizer als "Verbesserung" interpretiert.

**Failure Taxonomy** statt Boolean Pass/Fail:

```yaml
failure_taxonomy:
  hallucination:        # Fakten erfunden
  incomplete:           # Antwort schneidet ab
  format_violation:     # JSON/Schema kaputt
  refusal_unwarranted:  # falsche Sicherheits-Refusal
  tool_error:           # falscher Tool-Call oder Parameter
  off_topic:            # antwortet auf etwas anderes
  citation_missing:     # RAG ohne Quelle
```

Nur mit Buckets sieht man, ob ein neuer Lauf "weniger Halluzination, mehr Format-Violations" liefert oder einfach gleich gut bleibt.

**LLM-as-Judge mit Calibration (nicht verhandelbar):**
1. Calibration-Set anlegen: 20-30 Beispiele mit menschlichem Rating.
2. Judge-Prompt schreiben, gegen Calibration-Set laufen lassen.
3. Cohen's Kappa zwischen Judge und Mensch berechnen. Ziel: > 0.7. Bei niedrigerem Wert wird der Prompt überarbeitet, nicht der Datensatz.
4. Order-Swapping bei A/B-Vergleichen (Position-Bias ist real und stark).
5. Chain-of-Thought im Judge-Prompt erzwingen.
6. Calibration-Set quartalsweise re-runnen, da Modell-Updates Judge-Verhalten verschieben.

**DeepEval als Pytest-Gate:**

```python
# tests/test_invoice_skill.py
import pytest
from deepeval import assert_test
from deepeval.metrics import GEval, HallucinationMetric
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from goldens import load_goldens

correctness = GEval(
    name="Correctness",
    threshold=0.8,
    evaluation_steps=[
        "Check whether facts in 'actual output' contradict any facts in 'expected output'.",
        "Heavily penalize omission of detail.",
        "Vague language or contradicting opinions are not okay.",
    ],
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.EXPECTED_OUTPUT,
    ],
)

hallucination = HallucinationMetric(threshold=0.1)

@pytest.mark.parametrize("g", load_goldens("skills/invoice-generator/tests/goldens.yaml"))
def test_golden(g):
    actual = run_skill(g.input)
    case = LLMTestCase(
        input=str(g.input),
        actual_output=actual,
        expected_output=g.expected_output,
        context=g.context,
    )
    assert_test(case, [correctness, hallucination])
```

In CI läuft das als Gate vor jedem Merge. Pass-Rate-Schwelle: Baseline minus 2 Prozentpunkte. Goldens mit `risk_level: high` müssen 100% bestehen, sonst Block.

**Stack-Default 2026 für Engineering-Teams:** DeepEval (CI-Gate, pytest-nativ) + Braintrust ODER Langfuse (Production-Tracing, Annotation-Queue, Self-Host bei Langfuse) + Promptfoo (Red Teaming, 50+ Plugins gegen Prompt Injection und PII) + GrowthBook (Bayesian Canary, Self-Host).[^stack]

### 9.3 Outer-Loop-Pattern mit Approval Gates

Ein Self-Improvement-Loop hat drei Akteure: einen **Proposer** (schlägt Änderung vor), einen **Eval-Harness** (entscheidet automatisch pass/fail/review), einen **Promoter** (Mensch, der staged).

```
[Production Traces]
        |
        v
[Weakness Detector] --(findet Cluster: 30% Format-Violations bei DE-VAT-Cases)
        |
        v
[Proposer Agent] --(generiert Skill v1.2.0 -> v1.3.0 mit angepasstem Prompt + 4 neuen Few-Shots)
        |
        v
[Eval-Harness] --(läuft 100 Goldens + 20 neue gegen v1.3.0)
        |
        +-- Pass-Rate >= Baseline + 1pp UND keine Regression in High-Risk: status=ready_for_review
        +-- Pass-Rate < Baseline - 2pp ODER High-Risk-Regression: status=rejected (auto-close PR)
        +-- Dazwischen: status=needs_human
        |
        v
[Pull Request mit Diff, Eval-Report, Trace-Links]
        |
        v
[Required Reviewer (Mensch)] --> Merge -> Canary-Channel (siehe 9.5)
```

**Warum PR-basiert:** GitHub liefert kostenlos Audit-Trail, Diff-View, Required Reviewers, Branch Protection, Revert-Knopf. Niemand muss eine eigene Approval-UI bauen.

**Approval-Gate via GitHub API:**

```python
# bots/skill_proposer.py
from github import Github
import json, yaml

def propose_skill_update(skill_name: str, new_version: str, eval_report: dict, diff: str):
    if eval_report["high_risk_pass_rate"] < 1.0:
        return {"status": "rejected", "reason": "high_risk_regression"}

    delta = eval_report["pass_rate"] - eval_report["baseline_pass_rate"]
    if delta < -0.02:
        return {"status": "rejected", "reason": f"pass_rate_drop_{delta:.3f}"}

    gh = Github(os.environ["GH_TOKEN"])
    repo = gh.get_repo("deepthink/agents")
    branch = f"skill-update/{skill_name}-{new_version}"

    repo.create_git_ref(ref=f"refs/heads/{branch}", sha=repo.get_branch("main").commit.sha)
    repo.create_file(
        path=f"skills/{skill_name}/skill.yaml",
        message=f"chore({skill_name}): bump to {new_version}",
        content=diff,
        branch=branch,
    )

    pr = repo.create_pull(
        title=f"[auto] {skill_name} {new_version}",
        body=render_eval_report(eval_report),
        head=branch,
        base="main",
    )
    pr.create_review_request(reviewers=["fabian", "ai-ops-lead"])
    pr.add_to_labels("auto-proposal", "skill-update", f"risk:{eval_report['risk_level']}")
    return {"status": "ready_for_review", "pr": pr.html_url}
```

Branch Protection auf `main`: mindestens ein Reviewer mit Domain-Knowledge, alle CI-Checks müssen grün sein, lineare Historie. Damit kann der Bot vorschlagen, aber nicht selbst mergen.

**Risk-Tiering der Approval (Standard 2026):**[^hitl]

| Tier | Beispiele | Approval |
|------|-----------|----------|
| Low | Read, Lookup, Format | Auto-Merge nach grünem Eval, Logging |
| Medium | Skill-PATCH, Few-Shot-Update | Async Spot-Check (Review innerhalb 24h, sonst Auto-Revert) |
| High | Skill-MINOR/MAJOR, System-Prompt-Change, neue Tools | Synchroner Approval, zwei Reviewer |

Ziel-Eskalations-Rate Mensch: 10-15%. Höher heißt Tiering zu konservativ, niedriger heißt das Risiko ist unterschätzt.

### 9.4 Anti-Drift-Mechanik

Die kritischste und am häufigsten falsch implementierte Mechanik: **gegen welche Baseline vergleichst du?**

**Anti-Pattern:** Baseline ist "letzter erfolgreicher Run". Damit verschiebt jeder Run die Latte. Score-Drops von 1pp pro Iteration werden nie erkannt, nach 20 Iterationen ist man 20pp unter der ursprünglichen Qualität, ohne dass je ein Alarm gefeuert hat.

**Pattern:** Baseline ist eine **gefrorene** Version mit Datum, Hash und versionierten Eval-Ergebnissen. Sie wird nur durch expliziten menschlichen Akt aktualisiert ("Promote v1.4.2 zur neuen Baseline"), nicht automatisch.

```yaml
# evals/baseline.yaml
baseline:
  skill: invoice-generator
  version: 2.3.1
  frozen_at: 2026-04-15T10:00:00Z
  eval_run_id: er_a1b2c3
  metrics:
    pass_rate: 0.94
    high_risk_pass_rate: 1.00
    p95_latency_ms: 3200
    cost_per_run_usd: 0.012
    hallucination_rate: 0.03
    refusal_unwarranted_rate: 0.01
  goldens_sha: e5f6...      # Tampering-Detection
```

**Auto-Revert:**

```python
# ops/anti_drift.py
def evaluate_against_baseline(new_run, baseline):
    drops = {
        "pass_rate": baseline.pass_rate - new_run.pass_rate,
        "high_risk_drop": baseline.high_risk_pass_rate - new_run.high_risk_pass_rate,
        "hallucination_increase": new_run.hallucination_rate - baseline.hallucination_rate,
    }
    if drops["pass_rate"] > 0.05:
        return revert(reason=f"pass_rate_drop_{drops['pass_rate']:.3f}")
    if drops["high_risk_drop"] > 0.0:
        return revert(reason="high_risk_regression")
    if drops["hallucination_increase"] > 0.03:
        return revert(reason=f"hallucination_up_{drops['hallucination_increase']:.3f}")
    return ok()

def revert(reason: str):
    flag_provider.set("invoice_skill_version", baseline.version)
    slack.notify("#agent-ops", f"AUTO-REVERT invoice-generator -> {baseline.version}: {reason}")
    pagerduty.trigger("Self-Improvement loop reverted")
    return {"action": "reverted", "reason": reason}
```

**Periodische Re-Calibration:** Goldens-Set und Calibration-Set quartalsweise gegen die aktuell produktive Modell-Version replayen. Wenn der Judge plötzlich anders bewertet (Cohen's Kappa fällt unter 0.7), ist nicht der Agent das Problem, sondern der Judge selbst hat sich verschoben. Beides ist real und beides muss erkannt werden.

**Weekly Replay:** Jeden Montag 02:00 Uhr läuft das volle Goldens-Set gegen die aktuelle Production-Version. Ergebnis wird gegen die gefrorene Baseline verglichen. Bei Drift > 5pp pass-rate: Slack-Alert, kein Auto-Revert (weil das nicht der frische Deploy war), aber Pflicht-Investigation.

### 9.5 Canary-Rollout für Prompt- und Skill-Updates

Approval reicht nicht. Was im Eval funktioniert, kann in Production immer noch versagen (Distribution-Shift, neue Tool-Versionen, User-Verhalten). Deshalb: gestufter Rollout.

**Channel-Konzept:**
- `dev`: jeder Branch, lokale Tests
- `canary`: gemerged in main, 10% Traffic
- `stable`: nach erfolgreichem Canary, 100% Traffic

Channel-Auflösung über Feature-Flag-Provider (GrowthBook empfohlen, weil Bayesian + Self-Host).[^growthbook]

**Stufen-Plan:**

| Stufe | Traffic | Dauer | Guardrails | Auto-Stop bei |
|-------|---------|-------|------------|---------------|
| 1 | 10% | 24h | pass_rate, error_rate, refusal_rate | Bayesian Posterior > 95% für Verschlechterung |
| 2 | 25% | 24h | + p95_latency, cost_per_run | + 95% Posterior auf einer dieser Metriken |
| 3 | 50% | 48h | + thumbs_down_rate, support_tickets | dito |
| 4 | 100% | - | Standard-Monitoring | Manueller Revert via Flag |

**Statistische Signifikanz:** Bei realistischen Effect-Sizes von 5-10% braucht man mindestens 1000 Requests pro Variante für p < 0.05 (Frequentist) bzw. eine Posterior-Probability > 95% (Bayesian, GrowthBook nativ). Stage 1 sollte nicht beendet werden, bevor diese Schwelle erreicht ist, selbst wenn die 24h schon um sind.

**Mini-Architektur:**

```
                +-------------------+
   Request ---> | Skill Runner      |
                |                   |
                |  channel = flag.  |--- 10% --> v1.3.0-rc1 (canary)
                |    get("invoice", |--- 90% --> v1.2.4     (stable)
                |    user_id)       |
                +-------------------+
                       |
                       v
              +------------------+
              | Telemetry (OTel) |
              |  - tags: variant |
              +------------------+
                       |
                       v
              +-------------------+
              | GrowthBook        |
              |  Bayesian Compare |
              |  -> auto_promote  |
              |  -> auto_rollback |
              +-------------------+
```

GrowthBook stoppt den Rollout automatisch, wenn ein Guardrail kippt. Wichtig: Guardrails müssen ex ante definiert sein (vor dem Rollout), nicht ex post. Sonst ist es kein Test, sondern Storytelling.

### 9.6 Wann Self-Improvement abschalten - Verbotszonen

Es gibt Domänen, in denen die richtige Antwort lautet: **kein automatischer Loop, Punkt**. Auto-Optimierung ist hier nicht "vorsichtig riskant", sondern fahrlässig.

**Harte Verbotszonen:**

1. **Money-Movement** (Refunds, Transfers, Auszahlungen, Rechnungs-Stornos). Reward Hacking schlägt direkt in Cash durch. Hier nur statische, geprüfte Skills mit Sync-Approval pro Transaktion.
2. **Medizin, Recht, Finanzberatung**. Halluzinations-Verstärkung in haftungsrelevanten Bereichen ist ein Berufs- und Strafrechts-Risiko.
3. **Auth, Permissions, RBAC**. Ein Optimizer, der seine eigenen Guardrails wegoptimieren kann, hat keine Guardrails.
4. **Destruktive Operationen** (DELETE, DROP, TRUNCATE, `rm`, `git push --force`). Auto-Approve ausschließlich Read-Only.
5. **Datasets unter 100 Goldens**. Statistisches Rauschen wird als "Verbesserung" gelesen. Bei 50 Goldens reicht ein einziger Lucky-Run, um den Optimizer auf einen schlechten Pfad zu zwingen.
6. **Schnell driftende Domänen** (Stock-Prices, Live-News, Compliance-Regeln, geopolitische Lagebilder). Goldens veralten schneller als der Optimization-Loop iteriert. Was gestern korrekt war, ist heute falsch, der Optimizer lernt aber das alte Bild.
7. **Sicherheits-relevante Outputs** (Content-Moderation, PII-Filterung, Refusal-Verhalten). Optimierer behandeln Refusals als Score-Verlust und entfernen sie.

**Faustregel:** Self-Improvement ist nur sicher, wenn alle vier Bedingungen erfüllt sind:
- Reality-Check vorhanden (Test-Suite, Verifier, User-Feedback)
- Updates gated (Approval Gate, kein Auto-Merge bei Risk > Low)
- Auto-Revert verdrahtet (gegen gefrorene Baseline, nicht gegen letzten Run)
- Eval-Set unabhängig vom Optimization-Set (Held-Out, sonst Overfitting garantiert)

Fehlt eine dieser Bedingungen, ist der Loop kein Qualitätshebel sondern ein Risiko-Verstärker. Im Zweifel: keinen Loop bauen, manuell pflegen, mit dem Team weiterleben. Das ist 2026 immer noch der häufigste richtige Default.

### 9.7 Kernergebnisse

- Self-Improvement liefert messbaren Wert auf **Prompts, Few-Shots, Retrieval-Heuristiken**. Auf Permissions, Schemas, Money-Movement und Sicherheits-Policies hat ein Optimizer nichts verloren.
- Ohne **Goldens-Set (mindestens 100 Cases, kuratiert) plus kalibrierten LLM-Judge (Cohen's Kappa > 0.7)** ist jeder Loop blind. Datasets unter 100 Goldens produzieren Rauschen, das als Verbesserung gelesen wird.
- Die Baseline muss **gefroren und versioniert** sein. "Letzter Run" als Baseline ist das häufigste und tödlichste Anti-Pattern, weil Drift unsichtbar bleibt.
- Updates laufen über **Outer-Loop mit Approval Gate**: Bot schlägt PR vor, Eval-Harness entscheidet pass/fail/review, Mensch promotet. PR-basiert auf GitHub mit Required Reviewers reicht, niemand muss eine eigene Approval-UI bauen.
- **Canary-Rollout mit Bayesian-Auto-Stop** (GrowthBook) und mindestens 1000 Requests pro Variante. Guardrails ex ante definieren, nicht ex post.
- Es gibt **harte Verbotszonen** (Money, Medizin/Recht, Auth, destruktive Ops, schnell driftende Domänen, Sicherheits-Outputs). Hier kein Loop, statische Skills, Sync-Approval pro Aktion.

[^stack]: Vergleich der Eval-Frameworks 2026: [DeepEval Alternatives 2026 - Braintrust](https://www.braintrust.dev/articles/deepeval-alternatives-2026), [LLM Evaluation Tools Comparison - Inference.net](https://inference.net/content/llm-evaluation-tools-comparison/), [Promptfoo CI/CD Integration](https://www.promptfoo.dev/docs/integrations/ci-cd/), [Langfuse Docs](https://langfuse.com/docs).
[^hitl]: Risk-Tiering und HITL-Patterns 2026: [Anthropic - Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents), [HITL Patterns 2026 - DEV.to](https://dev.to/taimoor__z/-human-in-the-loop-hitl-for-ai-agents-patterns-and-best-practices-5ep5), [Cloudflare Agents - Human in the Loop](https://developers.cloudflare.com/agents/concepts/human-in-the-loop/).
[^growthbook]: [GrowthBook Safe Rollouts](https://docs.growthbook.io/app/features), [Canary Deployment - Flagsmith](https://www.flagsmith.com/blog/canary-deployment), [De-Risking AI Adoption with Feature Flags - Flagsmith](https://www.flagsmith.com/blog/de-risking-ai-adoption-feature-flags).
