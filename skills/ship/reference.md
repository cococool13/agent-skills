# Ship command contract

Run from the active checkout. No-argument execution and `--plan-only` perform local inspection. `--json` includes actions, blockers and scan status. Plan mode cannot establish remote freshness or a clean secret scan.

`--apply` fetches this repository, stops on blockers, scans, commits and pushes the current branch. It does not integrate branches or deploy. A behind-upstream branch must be integrated and validated before apply. The helper rejects an index containing paths outside its commit set. Git hooks run normally. Existing commit identity is preserved.

`--skip-fetch` is accepted only for plan compatibility. `--fast` is retained for existing callers; every plan now examines only the current branch.

Exit codes: `0` planned Git work completed; `1` blocked or failed; `2` pending work, deployment hint or local-only repository. Exit `0` does not verify deployment. A deploy hint comes from host files and `AGENTS.md`; consult project instructions for the actual target and CI behavior.

## File selection

- `secret`: sensitive-looking paths, including `.env*`, credential files and private-key extensions.
- `noise`: caches, logs, generated noise, owned worktree paths and untracked files over 5 MB.
- `archive`: untracked `_archive/` content.
- `commit`: remaining candidates. Review for task relevance before apply.

The scanner checks history and working-tree content without exposing captured output or generating configuration. Missing scanner or failure blocks apply. Excluded staged paths block the commit instead of being silently included. The helper does not read candidate file contents itself.

## Integration and housekeeping

Textually clean merges do not establish that leftover branches belong in a release. Review and integrate the task branch under project instructions before shipping. Keep unrelated branches, stashes and worktrees intact. The legacy `sync.py` and `worktrees.py` utilities are not called by ship; they are not part of its supported workflow.

After any failed or timed-out push, inspect the remote revision before deciding what to do. Do not replay a state-changing external action automatically.
