---
name: prompt-audit
description: "Use when auditing skills, AGENTS.md, or rules for dated/redundant prompt patterns."

---

# Prompt audit

Port of Anthropic `claude-api` **prompt-audit** (Peter Yang / Lance Martin, 2026-09). Do **not** install `anthropics/skills@claude-api` on this machine — that skill defaults to Claude Opus/Fable and would fire on any LLM task.

## Defaults

- **Target model:** whatever the user/agent stack uses day to day (author default: `grok-4.6`) unless the request names another model.
- **Default scope:** `~/.agents/AGENTS.md`, `~/.cursor/rules/`, this skills repo if present, plus live `~/.agents/skills`. Skip `~/.agents/parked-not-for-cursor` unless the user names it.
- **Apply edits** only if the request explicitly says to apply/clean. Otherwise report + proposed diff only.

## Run

Read `references/prompt-audit.md` and execute it in order (Step 0 → Step 6). Do not summarize the guide. Treat `/claude-api prompt-audit` as this skill.

Use the reference as a pattern checklist. Ground each finding in the named target model and current host contract. Do not transfer Claude API errors, configuration semantics, or behavior claims to Grok or GPT without evidence. Preserve explicit completion criteria and authorization for safe work. Flag uncertain model-specific claims without proposing their removal.

Keep load-bearing constraints from the user's `AGENTS.md` (author's include: never permanently delete / prefer Trash, never print secrets, never force-push, Ego Lite for web QA, Cloudflare unless the project says otherwise).
