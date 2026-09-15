---
name: prompt-audit
description: "Use when auditing skills, AGENTS.md, or rules for dated/redundant prompt patterns."

---

# Prompt audit

Port of Anthropic `claude-api` **prompt-audit** (Peter Yang / Lance Martin, 2026-09). Do **not** install `anthropics/skills@claude-api` on this machine — that skill defaults to Claude Opus/Fable and would fire on any LLM task.

## Defaults (Cohen)

- **Target model:** `grok-4.6` unless the request names another model.
- **Default scope:** `~/.agents/AGENTS.md`, `~/.cursor/rules/`, `~/Projects/Agent Skills/skills/`, plus live `~/.agents/skills`. Parked skills in `~/.agents/parked-not-for-cursor` are out of scope unless Cohen names them.
- **Apply edits** only if the request explicitly says to apply/clean. Otherwise report + proposed diff only.

## Run

Read `references/prompt-audit.md` and execute it in order (Step 0 → Step 6). Do not summarize the guide. Treat `/claude-api prompt-audit` as this skill.

Use the reference as a pattern checklist. Ground each finding in the named target model and current host contract. Do not transfer Claude API errors, configuration semantics, or behavior claims to Grok or GPT without evidence. Preserve explicit completion criteria and authorization for safe work. Flag uncertain model-specific claims without proposing their removal.

Keep load-bearing Cohen constraints: never permanently delete (Trash), never print secrets, never force-push, Ego Lite for web QA, Cloudflare unless the project CLAUDE.md says otherwise.
