---
name: compact-output
description: Keep Codex replies, prompts, and agent outputs extremely concise and token-efficient. Use when the user asks for short answers, minimal-token behavior, terse agent prompts, or tight execution budgets.
---
# Compact Output

## Rules

- Say only the minimum needed to solve the task.
- Prefer one line or one short list.
- Remove filler, restatement, and long preambles.
- In code work, make the smallest safe diff.
- For Agent Gauntlet, keep prompts, retries, and explanations brief.
- If the user does not ask for detail, do not add it.

## Quality Floor

- Never trade correctness for brevity.
- Obey required output format exactly.
- If confidence is low on a fact, verify before answering.
- If still uncertain after checking, state uncertainty briefly instead of guessing.
