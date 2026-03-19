# Claim Verification Pattern

## UI Signals
- `Mode: TEXT`
- `Difficulty`
- `Time`
- `Objective`
- `Rules`
- `Clues`
- `Sample Solution`

## Intended Task
- Verify a small set of technical claims using live web sources.
- Use one focused query per claim when possible.
- Avoid broad searches that mix multiple claims.

## Output Shape
- Final answer: boolean tokens only, in claim order.
- Do not add prose on the final line.
- If the challenge asks for citations in reasoning, keep them short and tied to the claim being checked.

## Quality Checks
- Keep claim order exact.
- Use targeted search queries per claim.
- Prefer primary or official sources over summaries.
- If evidence is insufficient, avoid guessing and mark the claim false.
