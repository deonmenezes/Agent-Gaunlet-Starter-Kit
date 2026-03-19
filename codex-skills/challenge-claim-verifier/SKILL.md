---
name: challenge-claim-verifier
description: Solve Agent Gauntlet text challenges that verify a small number of factual claims from live web sources. Use when the challenge screen shows Challenge Overview, Objective, Rules, Clues, or Sample Solution and asks for booleans in claim order.
---
# Challenge Claim Verifier

## Recognize the Pattern

- The objective asks to verify 2-3 claims with live web sources.
- The rules call for targeted searches, not one broad query.
- The final answer is usually one line with boolean tokens in claim order.
- The UI often shows `Challenge Overview`, `Objective`, `Rules`, `Clues`, and `Sample Solution`.

## Workflow

- Verify one claim at a time with a focused search.
- Prefer authoritative or primary sources.
- Keep notes short.
- Keep citations in reasoning if the challenge asks for them.
- Final answer must be only the boolean tokens in order.
- When the screen matches the photographed layout, treat it as this pattern even if wording shifts slightly.

## Quality Floor

- Do not guess across claims. Mark a claim false if evidence is weak or missing.
- Prefer official docs, vendor sources, or primary technical references.
- Keep claim order strict from the challenge text.
- Match output schema exactly to avoid quality score loss from formatting errors.

## Reference

See [patterns.md](references/patterns.md) for the exact layout checklist and output shape.
