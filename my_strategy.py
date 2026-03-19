"""Competitor strategy definition for starter-kit agents.

Edit this class to customize behavior without touching runtime code.
"""

from __future__ import annotations

from base_strategy import BaseStrategy


class MyStrategy(BaseStrategy):
    """Default competitor strategy template."""

    # Team identity (shown in Organizer/Dashboard)
    agent_id = "my-agent"
    agent_name = "My Team"

    # Text challenge strategy
    text_system_prompt = (
        "You are a text challenge solver. "
        "Your first line must always be: ANSWER: <final answer>. "
        "Return nothing except the required ANSWER line and optional brief reasoning lines after it. "
        "Follow challenge rules exactly, including strict output formats. "
        "Do not output <think> tags. "
        "If you add reasoning, keep it to at most 2 short lines after the ANSWER line. "
        "Never output 'unknown'."
    )
    text_strategy_notes = "Keep reasoning concise and always include an ANSWER line."
    text_temperature = 0.0
    text_max_tokens = 320

    # Image challenge strategy
    image_strategy_notes = (
        "Prefer one-pass image_edit when an input image is available. "
        "Avoid iterative retries unless the first output is clearly invalid. "
        "For privacy tasks, blur all visible faces strongly while preserving non-face regions. "
        "Keep rationale concise and request standard-resolution output only (no HD/4K)."
    )

    # Leave empty to keep autonomous model selection.
    preferred_model = ""
