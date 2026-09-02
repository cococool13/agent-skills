---
name: prompt-audit
description: "Use when Cohen runs /prompt-audit or /claude-api prompt-audit, or asks to audit skills, AGENTS.md, rules, or tool descriptions for dated prompt patterns. Finds redundancies and rules to remove for grok-4.6. Not for installing the Anthropic Claude API SDK skill."
---

# Prompt audit

Port of Anthropic `claude-api` **prompt-audit** (Peter Yang / Lance Martin, 2026-09). Do **not** install `anthropics/skills@claude-api` on this machine — that skill defaults to Claude Opus/Fable and would fire on any LLM task.

## Defaults (Cohen)

- **Target model:** `grok-4.6` unless the request names another model.
- **Default scope:** `~/.agents/AGENTS.md`, `~/.cursor/rules/`, `~/Projects/agent-skills/skills/`, plus live `~/.agents/skills`. Parked skills in `~/.agents/parked-not-for-cursor` are out of scope unless Cohen names them.
- **Apply edits** only if the request explicitly says to apply/clean. Otherwise report + proposed diff only.

## Run

Read `references/prompt-audit.md` and execute it in order (Step 0 → Step 6). Do not summarize the guide. Treat `/claude-api prompt-audit` as this skill.

Map Claude-specific rows as follows:

- Adaptive thinking / `effort` / structured outputs → Grok already plans and follows instructions; delete "think step by step", planning boosters, and JSON-prefill scaffolds the same way.
- Fable 5.1 refusal / `budget_tokens` 400s → skip unless the file is Anthropic API request code.
- "Current Claude models follow instructions more closely" → same for grok-4.6.

Keep load-bearing Cohen constraints: never permanently delete (Trash), never print secrets, never force-push, Ego Lite for web QA, Cloudflare unless the project CLAUDE.md says otherwise.
