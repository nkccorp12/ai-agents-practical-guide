## Chapter 9: Self-Improving Multi-Agent RAG Systems

Self-improvement is the most seductive promise on the 2026 market: DSPy compiles prompts automatically against a trainset, TextGrad propagates gradients through natural language, and Anthropic Skills can in principle be versioned and swapped. In demos this looks like a self-tuning stack. In production it is a field where reward hacking, evaluator drift, and benchmark overfitting wreck real systems every day. This chapter shows soberly where automated improvement actually adds value (prompts, few-shots, retrieval heuristics), and where you keep your hands off: permissions, output validation, money movement, security policies. The thread running through it is outer loop with hard approval gates, frozen baselines, and auto-revert. Without those three mechanics, every self-improvement loop is a risk amplifier, not a quality lever.

### 9.1 What Self-Improvement Can Realistically Do (And What It Cannot)

The dividing line runs along auditability and reversibility.

**Works (with eval harness and approval):**
- Prompt optimization against a goldens set (DSPy `BootstrapFewShot`, `MIPROv2`, `GEPA`, TextGrad).
- Few-shot selection from a curated example pool.
- Retrieval heuristics (chunking strategy, re-ranking weights, query expansion).
- Skill proposals: an agent identifies recurring workflows and proposes a new `SKILL.md` as a pull request. A human promotes it.

**Does not work (or only with sync approval):**
- Tool permissions and `allowed-tools` lists. An agent must never expand its own permission scope, because that is the primary reward-hacking target.
- Output validation and schema definitions. If the agent loosens the schema itself, suddenly any garbage passes.
- Money-movement paths (refunds, transfers, payouts). Reward hacking translates directly into cash here.
- Security refusals and content policies. An optimizer reads every refusal as a "score loss" and optimizes it away.
- System prompts with role definitions or constraints ("You must never X"). Optimizers learn to paraphrase such constraints until they are inert.

**Reward-hacking risk:** an optimizer maximizes the eval score, not utility. If the judge rewards "answer contains JSON", the agent learns to embed JSON in refusals. If the judge rewards "answer is long" (verbosity bias, very common), you get three-page essays in response to yes/no questions. The goldens must actively defend against this, otherwise you compile yourself into a wall.

### 9.2 Eval Harness as Foundation

No goldens, no self-improvement. Period.

**Goldens set (minimum 100 manually curated cases):**
- 60% happy path
- 25% edge cases (long inputs, empty fields, multilingual, format deviations)
- 15% adversarial (prompt injection, jailbreak, out-of-scope, verbosity trap)

Each case has `id`, `input`, `expected_output` (or `expected_behavior`), `tags`, `risk_level`, `human_verified_at`. Datasets below 100 goldens produce statistical noise that an optimizer interprets as "improvement".

**Failure taxonomy** instead of boolean pass/fail:

```yaml
failure_taxonomy:
  hallucination:        # facts invented
  incomplete:           # answer truncated
  format_violation:     # JSON/schema broken
  refusal_unwarranted:  # false safety refusal
  tool_error:           # wrong tool call or parameter
  off_topic:            # answers something else
  citation_missing:     # RAG without source
```

Only with buckets can you tell whether a new run delivers "less hallucination, more format violations" or simply stays the same.

**LLM-as-judge with calibration (non-negotiable):**
1. Build a calibration set: 20-30 examples with human ratings.
2. Write the judge prompt, run it against the calibration set.
3. Compute Cohen's Kappa between judge and human. Target: > 0.7. If lower, rewrite the prompt, do not change the data.
4. Order-swapping in A/B comparisons (position bias is real and strong).
5. Force chain-of-thought in the judge prompt.
6. Re-run the calibration set quarterly because model updates shift judge behavior.

**DeepEval as a pytest gate:**

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

In CI this runs as a gate before every merge. Pass-rate threshold: baseline minus 2 percentage points. Goldens with `risk_level: high` must pass at 100%, otherwise block.

**2026 default stack for engineering teams:** DeepEval (CI gate, pytest-native) + Braintrust OR Langfuse (production tracing, annotation queue, self-host with Langfuse) + Promptfoo (red teaming, 50+ plugins for prompt injection and PII) + GrowthBook (Bayesian canary, self-host).[^stack]

### 9.3 Outer-Loop Pattern with Approval Gates

A self-improvement loop has three actors: a **proposer** (suggests a change), an **eval harness** (auto-decides pass/fail/review), a **promoter** (human who stages it).

```
[Production Traces]
        |
        v
[Weakness Detector] --(finds cluster: 30% format violations on DE-VAT cases)
        |
        v
[Proposer Agent] --(generates skill v1.2.0 -> v1.3.0 with adjusted prompt + 4 new few-shots)
        |
        v
[Eval Harness] --(runs 100 goldens + 20 new ones against v1.3.0)
        |
        +-- Pass-rate >= baseline + 1pp AND no high-risk regression: status=ready_for_review
        +-- Pass-rate < baseline - 2pp OR high-risk regression: status=rejected (auto-close PR)
        +-- In between: status=needs_human
        |
        v
[Pull Request with diff, eval report, trace links]
        |
        v
[Required Reviewer (human)] --> Merge -> canary channel (see 9.5)
```

**Why PR-based:** GitHub gives you audit trail, diff view, required reviewers, branch protection, and a revert button for free. Nobody has to build a custom approval UI.

**Approval gate via GitHub API:**

```python
# bots/skill_proposer.py
from github import Github
import os

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

Branch protection on `main`: at least one reviewer with domain knowledge, all CI checks green, linear history. The bot can propose but never merge itself.

**Risk tiering of approval (2026 standard):**[^hitl]

| Tier | Examples | Approval |
|------|----------|----------|
| Low | Read, lookup, format | Auto-merge after green eval, logging |
| Medium | Skill PATCH, few-shot update | Async spot check (review within 24h, otherwise auto-revert) |
| High | Skill MINOR/MAJOR, system-prompt change, new tools | Synchronous approval, two reviewers |

Target human escalation rate: 10-15%. Higher means tiering is too conservative, lower means risk is underestimated.

### 9.4 Anti-Drift Mechanics

The most critical and most frequently misimplemented mechanic: **what baseline are you comparing against?**

**Anti-pattern:** the baseline is "last successful run". This means every run shifts the bar. Score drops of 1pp per iteration are never detected. After 20 iterations you are 20pp below original quality without a single alarm having fired.

**Pattern:** the baseline is a **frozen** version with date, hash, and versioned eval results. It is updated only by an explicit human act ("Promote v1.4.2 to new baseline"), never automatically.

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
  goldens_sha: e5f6...      # tampering detection
```

**Auto-revert:**

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
    pagerduty.trigger("Self-improvement loop reverted")
    return {"action": "reverted", "reason": reason}
```

**Periodic re-calibration:** replay the goldens set and calibration set against the currently productive model version every quarter. If the judge suddenly grades differently (Cohen's Kappa drops below 0.7), the agent is not the problem, the judge itself has shifted. Both are real and both must be detected.

**Weekly replay:** every Monday at 02:00, run the full goldens set against the current production version. Compare against the frozen baseline. If drift > 5pp pass-rate: Slack alert, no auto-revert (because it was not a fresh deploy), but mandatory investigation.

### 9.5 Canary Rollout for Prompt and Skill Updates

Approval is not enough. What works in eval can still fail in production (distribution shift, new tool versions, user behavior). Therefore: staged rollout.

**Channel concept:**
- `dev`: any branch, local tests
- `canary`: merged into main, 10% traffic
- `stable`: after successful canary, 100% traffic

Channel resolution via feature-flag provider (GrowthBook recommended because Bayesian + self-host).[^growthbook]

**Stage plan:**

| Stage | Traffic | Duration | Guardrails | Auto-stop on |
|-------|---------|----------|------------|--------------|
| 1 | 10% | 24h | pass_rate, error_rate, refusal_rate | Bayesian posterior > 95% for regression |
| 2 | 25% | 24h | + p95_latency, cost_per_run | + 95% posterior on any of these |
| 3 | 50% | 48h | + thumbs_down_rate, support_tickets | same |
| 4 | 100% | - | standard monitoring | manual revert via flag |

**Statistical significance:** at realistic effect sizes of 5-10%, you need at least 1000 requests per variant for p < 0.05 (frequentist) or posterior probability > 95% (Bayesian, native in GrowthBook). Stage 1 must not end before this threshold is reached, even if the 24h window is up.

**Mini architecture:**

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
              |  Bayesian compare |
              |  -> auto_promote  |
              |  -> auto_rollback |
              +-------------------+
```

GrowthBook stops the rollout automatically when a guardrail tips. Important: guardrails must be defined ex ante (before the rollout), not ex post. Otherwise it is not a test, it is storytelling.

### 9.6 When to Switch Self-Improvement Off - Forbidden Zones

There are domains where the right answer is: **no automated loop, period**. Auto-optimization here is not "carefully risky", it is negligent.

**Hard forbidden zones:**

1. **Money movement** (refunds, transfers, payouts, invoice voids). Reward hacking translates directly into cash. Only static, vetted skills with sync approval per transaction.
2. **Medicine, law, financial advice**. Hallucination amplification in liability-bearing domains is a professional and criminal-law risk.
3. **Auth, permissions, RBAC**. An optimizer that can optimize its own guardrails away has no guardrails.
4. **Destructive operations** (DELETE, DROP, TRUNCATE, `rm`, `git push --force`). Auto-approve only on read-only.
5. **Datasets below 100 goldens**. Statistical noise is read as "improvement". With 50 goldens a single lucky run is enough to push the optimizer onto a bad path.
6. **Fast-drifting domains** (stock prices, live news, compliance rules, geopolitical situational awareness). Goldens age faster than the optimization loop iterates. Yesterday's truth is wrong today, but the optimizer learned the old picture.
7. **Security-relevant outputs** (content moderation, PII filtering, refusal behavior). Optimizers treat refusals as score losses and remove them.

**Rule of thumb:** self-improvement is safe only if all four conditions hold:
- Reality check available (test suite, verifier, user feedback)
- Updates gated (approval gate, no auto-merge above low risk)
- Auto-revert wired (against frozen baseline, not against last run)
- Eval set independent of optimization set (held-out, otherwise overfitting is guaranteed)

If any of these is missing, the loop is a risk amplifier, not a quality lever. When in doubt: build no loop, maintain manually, live with it as a team. In 2026 that is still the most common right default.

### 9.7 Key Takeaways

- Self-improvement delivers measurable value on **prompts, few-shots, retrieval heuristics**. It has no business touching permissions, schemas, money movement, or security policies.
- Without a **goldens set (at least 100 cases, curated) plus a calibrated LLM judge (Cohen's Kappa > 0.7)** every loop is blind. Datasets below 100 goldens produce noise that gets read as improvement.
- The baseline must be **frozen and versioned**. "Last run" as baseline is the most common and most lethal anti-pattern because drift stays invisible.
- Updates flow through an **outer loop with approval gate**: bot proposes a PR, eval harness decides pass/fail/review, human promotes. PR-based on GitHub with required reviewers is enough, nobody has to build a custom approval UI.
- **Canary rollout with Bayesian auto-stop** (GrowthBook) and at least 1000 requests per variant. Define guardrails ex ante, not ex post.
- There are **hard forbidden zones** (money, medicine/law, auth, destructive ops, fast-drifting domains, security outputs). No loop here. Static skills, sync approval per action.

[^stack]: 2026 eval-framework comparison: [DeepEval Alternatives 2026 - Braintrust](https://www.braintrust.dev/articles/deepeval-alternatives-2026), [LLM Evaluation Tools Comparison - Inference.net](https://inference.net/content/llm-evaluation-tools-comparison/), [Promptfoo CI/CD Integration](https://www.promptfoo.dev/docs/integrations/ci-cd/), [Langfuse Docs](https://langfuse.com/docs).
[^hitl]: Risk tiering and HITL patterns 2026: [Anthropic - Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents), [HITL Patterns 2026 - DEV.to](https://dev.to/taimoor__z/-human-in-the-loop-hitl-for-ai-agents-patterns-and-best-practices-5ep5), [Cloudflare Agents - Human in the Loop](https://developers.cloudflare.com/agents/concepts/human-in-the-loop/).
[^growthbook]: [GrowthBook Safe Rollouts](https://docs.growthbook.io/app/features), [Canary Deployment - Flagsmith](https://www.flagsmith.com/blog/canary-deployment), [De-Risking AI Adoption with Feature Flags - Flagsmith](https://www.flagsmith.com/blog/de-risking-ai-adoption-feature-flags).
