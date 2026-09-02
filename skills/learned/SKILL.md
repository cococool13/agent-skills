---
name: learned
description: "Use when cross-project working preferences, recurring environment facts, or personal conventions are needed and the local project context does not cover them."
---

# Learned: Cohen's working memory

Always-on instructions live in `~/.agents/AGENTS.md` (Cursor User Rules should
match). This file is only for environment gotchas and skill routing that do not
belong in every chat. Project `AGENTS.md` / `CLAUDE.md` / `BRAND.md` / `SPEC.md`
still win inside a repo.

## Who / context

UGA student, not a professional dev; builds real client sites and tools with AI
and learns by doing. Runs **The Backpack Project, Inc.** (nonprofit, COO) and is
Honors Student Council Treasurer. Two machines: a **Mac (M4 Pro)** and a
**Windows 11 gaming PC** (the PC-Tweaks toolkit).

## Agents he uses (2026-09)

- **Cursor** — primary daily coding agent (model grok-4.6)
- **Grok** (CLI + bot) — secondary; shares `~/.agents/skills` and global AGENTS
- ChatGPT.app is a chat app only. Claude.app / Claude Code were removed 2026-09-01. Codex is not in the live stack.

## How he works (honor without being asked)

- Decisive and direct. Recommend one option and proceed; don't over-ask.
- Brief "why" then the work. Accuracy over speed.
- **Never permanently delete** — move to Trash / `_archive` / `_needs-review`,
  and ask before bulk moves (20+ files) or destructive actions.
- Naming `YYYY-MM-DD-descriptive-name.ext`; end file operations with a changelog.
- Prefers `.xlsx` with working formulas over `.csv`; Markdown for docs.

## Stack defaults

See `~/.agents/AGENTS.md` — don't pin framework versions here. Host is
**per-project**; read `CLAUDE.md`. Live map: Cloudflare Pages (Spiral Collection,
spiral-brief, Coastal PharmaCare), Cloudflare Workers (Coastal Hardware New
Build, entr-website, JCC forms/evaluator, PropScanner web), Firebase (JCC
SECURE). Coastal Hardware Next checkout is retired. Mobile is native iOS:
**They Hold** (repo `latch`, scheme `Latch`) and Pulse. Flutter is not installed.
- **Xcode 27 beta** at `/Applications/Xcode-beta.app` is required on macOS 27.
  `/Applications/Xcode.app` is 26.6 and is not the active toolchain.
  `DEVELOPER_DIR` is set in `~/.config/zsh/env.zsh`. Cursor drives iOS via
  XcodeBuildMCP + SweetPad; skill `xcodebuildmcp`.

## Recurring environment gotchas (don't rediscover)

- macOS often blocks `rm`/empty-dir removal from the VM; stage to Trash, never
  `sudo rm -rf`. Verify a move/copy landed before reporting done.
- `mas` / `msupdate` fail non-interactively → App Store / MAU GUI.
- macOS screenshot filenames contain a narrow no-break space (U+202F) before AM/PM.
- Secrets must never be sorted by extension → hand to `credential-sweep`.
- `launchctl bootstrap` "error 5" often means disabled in the override DB —
  check `launchctl print-disabled gui/$(id -u)` before deeper debugging.
- **Ego Lite / `ego-browser` is mandatory** for web QA, screenshots, and self-verification. Do not fall back to Cursor browser MCP, Aside, or agent-browser. Invoke `"$HOME/.local/bin/ego-browser"` (wrapper; Cursor GUI PATH is stripped). If `pageInfo()` is `0×0` or `captureScreenshot()` hangs, the Ego Lite window is minimized — CDP `Browser.setWindowBounds` `{windowState:'normal'}` after `openOrReuseTab`. Canonical skill is the writable directory at `~/.agents/skills/ego-browser`; do not edit `ego lite.app`.
- M4 Pro disk audits: Cohen’s home is ~52 GB. The real fill is **`/Users/Shared/Movies` (~233 GB, Infuse 4K remuxes)**. Do not trash it. APFS headroom is the limiter, not leftover apps.
- High Power Mode is already set on adapter (`pmset` `powermode` 2). Battery stays Automatic. `df`/`du` are not aliased. Disk overview is `disks` (duf), interactive usage is `usage` (ncdu). Interactive `top` is `btop`.
- Terminal.app default/startup profile is **Clear Dark** (JetBrainsMono Nerd Font). Cursor's integrated terminal uses the same font. Shell config lives in `~/.zshrc`, `~/.zprofile`, `~/.zshenv`, `~/.config/zsh/env.zsh`, `~/.config/starship.toml`.

## Skill routing

Local files → `organize-mac-files`; secrets → `credential-sweep`; build/extend
sites → `premium-web-build`; browsing/QA → `ego-browser` (mandatory Ego Lite); motion → Emil stack /
`scroll-motion-debug`; hardening → `de-ai-production-pass`; deploy → project
`CLAUDE.md` then `deploy-cloudflare`; slash `/ship` → commit, push, deploy the
current repo only (no other projects, no skill-library update); React/Next polish →
`vercel-react-best-practices` / `web-design-guidelines` / `frontend-design`.

Orca (`computer-use`, `orca-cli`, `orchestration`), Diffusion Studio (`editor`,
`watch`), and Matt Pocock grill stubs are parked — no `orca`/`dapi` binary, and
the grill skills only called a disabled plugin. Restore from
`~/.agents/parked-not-for-cursor` if those tools get installed.

`~/.agents/skills/` is canonical for Cursor and Grok. Parked unused adapters
stay in `~/.agents/parked-not-for-cursor`. Do not copy skills into
`~/.cursor/skills`. After `npx skills update`, run
`python3 ~/.agents/skills/maintain-skill-library/scripts/prune-cursor-scan-paths.py`.

## Keep this current

When a new durable preference or recurring gotcha shows up across sessions, add
it here in a line or two so future sessions inherit it.
