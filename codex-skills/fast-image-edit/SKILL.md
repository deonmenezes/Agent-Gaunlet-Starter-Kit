---
name: fast-image-edit
description: Solve Agent Gauntlet image-edit challenges with the fastest reliable path. Use when a challenge asks for edits on a provided source image (for example face blur, redaction, masking, or targeted transforms) and speed matters.
---
# Fast Image Edit

## Fast Path

- Prefer `image_edit` immediately when input image is provided.
- Use one high-quality pass before considering retries.
- Keep prompts short, explicit, and action-oriented.
- Avoid extra analysis/model calls unless the challenge explicitly requires a report.
- Keep output at standard resolution unless rules require otherwise.

## Quality Floor

- Follow challenge instructions exactly from `Objective` and `Instructions`.
- Apply edits to all required regions (for example every visible face).
- Preserve non-target regions when rules ask to preserve background/body.
- Use strict submission format if a report/rationale schema is required.

## Face-Blur Pattern

- Instruction style: "Detect every visible human face and apply strong privacy blur to each face region. Preserve non-face regions."
- If report text is required, include face count and approximate boxes concisely.
