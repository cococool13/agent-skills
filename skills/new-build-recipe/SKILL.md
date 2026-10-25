---
name: new-build-recipe
description: "Use when starting a new product or app build from scratch, or rebuilding one in a new repo: study a reference, pick design refs, build, add guardrails."
---

# New build recipe

Four phases, in order. Read the project's `AGENTS.md` first if one exists; it wins.

## 1. Study the reference (only when there is one)

Skip this phase when the build has no existing product to learn from.

- Use the `reverse-engineer-anything` skill (REA MCP).
- Legal scope: websites, public docs, and network traffic of software Cohen is licensed to use. Decompile native binaries only where the license allows it.
- Output: a short findings note in the repo (`brief/findings.md`) with features, flows, and data shapes. Not copied code or assets.

## 2. Pick design references

Read `~/.agents/design-refs/DESIGN-PREFS.md`, section "Tools, skills, and when", and follow it. The floor and the chosen mood win over a skill default.

- Pick the mood, then call Stacks `suggest_for_task` once, `get_board_for_project` when a board exists, then `suggest_pack_for_task` and `search_design`.
- Use `refero-design` for real app screens and flows. Use Inspo when that MCP is connected.
- One canvas before code: Paper when it is connected. Otherwise use the tool that section names for this deliverable (Stitch, Figma `use_figma`, `tesseract-design`, or `canvas`).
- Then `hallmark` for a new site or page. `web-designer` for a redesign of an existing site. `app-designer` for iPhone. Hallmark stays off an existing design unless the prompt says `/hallmark redesign`.

## 3. Build

- In Claude Code, run `/pstack:poteto-mode`. In Cursor, run `/poteto-mode`.
- Codex and Grok have no pstack. Follow these four phases directly; for the pre-commit cleanup pass, use the `code-review` skill, then the project's tests and linters.
- Claude Code has no `cursor-team-kit`. When poteto-mode asks for `/deslop` before a commit, run the built-in `/simplify` instead. When it asks for `control-cli` or `control-ui`, use the `run` skill or the built-in browser pane.
- Product rules still apply: Cloudflare hosting, paid web/Mac access through Stripe via the shared `~/Projects/licensing` Worker (test mode until Cohen goes live), project names in Title Case under `~/Projects/`.

## 4. Add guardrails

Copy the shared hook setup from an existing repo, for example `~/Projects/Candor`:

```bash
cp ~/Projects/Candor/lefthook.yml ~/Projects/Candor/biome.json .
lefthook install
```

- `lefthook.yml` covers Swift (swiftformat, swiftlint) and JS/TS (biome) by file glob, plus gitleaks. Remove the jobs for languages the repo does not use.
- Keep `"linter": { "rules": { "preset": "recommended" } }` in `biome.json`.
- Done when `lefthook run pre-commit` passes on the first commit.
