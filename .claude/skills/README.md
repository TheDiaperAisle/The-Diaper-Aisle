# Design skills (project copies)

Committed so every Claude Code session on this repo (including cloud sessions) has them. Used for the v2 redesign in
`redesign/` (see `redesign/DESIGN-PLAN.md`). Not used by the daily data run.

| Skill | Source (commit) | Licence |
|---|---|---|
| ui-ux-pro-max | github.com/nextlevelbuilder/ui-ux-pro-max-skill (2de1134) | MIT |
| frontend-design, webapp-testing | github.com/anthropics/skills (e4bb5d9) | see each folder's LICENSE.txt |
| impeccable | github.com/pbakaus/impeccable (b49177d) | Apache-2.0 |
| web-design-guidelines, vercel-react-best-practices | github.com/vercel-labs/agent-skills (5a37a63) | MIT (per SKILL.md) |
| baseline-ui, fixing-accessibility, improve-ui | github.com/ibelick/ui-skills (347d318) | MIT |

Notes
- impeccable's launcher (`impeccable/scripts/impeccable`) downloads its engine binary on first use and checks it against
  `impeccable/scripts/engine-checksums.txt`. The binary is not committed.
- ui-ux-pro-max's search script reads only its own `data/` CSV files (no network).
- To update a skill, copy the folder again from its repository and update the commit above.
