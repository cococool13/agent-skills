# Agent skills

Personal skills I use with coding agents (Cursor / Grok).

## Install

```bash
npx skills add cococool13/agent-skills --all -g -y
```

That command downloads every skill folder under `skills/` into your agent skills directory so Cursor can load them by name.

## What is a skill?

A **skill** is a markdown recipe (`SKILL.md`) that tells an AI agent *when* to run a workflow and *how* to do it step by step. You do not run skills like apps. You open Cursor (or another coding agent), ask for work in plain English, and the agent pulls in the matching skill.

Examples:
- `refero-design` — research real UI before inventing screens
- `unslop` / `de-ai-production-pass` — strip AI-looking writing and UI tells
- `ship` — commit / push / deploy checklist
- `grill-me` — stress-test a plan with hard questions

## Files in this repo

| Path | What it is |
| --- | --- |
| `skills/*/SKILL.md` | The actual recipes |
| [CATALOG.md](./CATALOG.md) | Full list of skills I use, including upstream links |
| [AGENTS.md](./AGENTS.md) | Global rules my agents always follow |

## Upstream skills I also use

I install extra skills from other authors (Emil Kowalski, Matt Pocock, Vercel, Refero, etc.). Those stay in their own GitHub repos — see [CATALOG.md](./CATALOG.md). Do not expect every name on my Mac to live in *this* repo.

## Update

```bash
npx skills update -g -y
```
