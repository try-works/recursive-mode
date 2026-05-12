# recursive-closeout (prompt template)

> Scaffold Phases 4-8 from existing evidence and control-plane docs instead of starting from a blank markdown file.

## Usage Pattern

```text
Scaffold recursive closeout phase: <run-id> <04|05|06|07|08>
```

## Script (Recommended)

```powershell
python "<SKILL_DIR>/scripts/recursive-closeout.py" --repo-root . --run-id "<run-id>" --phase 04
python "<SKILL_DIR>/scripts/recursive-closeout.py" --repo-root . --run-id "<run-id>" --phase 05 --preview-log ".recursive/run/<run-id>/evidence/logs/preview-server.log"
python "<SKILL_DIR>/scripts/recursive-closeout.py" --repo-root . --run-id "<run-id>" --phase 08 --force

pwsh -NoProfile -File "<SKILL_DIR>/scripts/recursive-closeout.ps1" -RepoRoot . -RunId "<run-id>" -Phase 04
pwsh -NoProfile -File "<SKILL_DIR>/scripts/recursive-closeout.ps1" -RepoRoot . -RunId "<run-id>" -Phase 05 -PreviewLog ".recursive/run/<run-id>/evidence/logs/preview-server.log"
pwsh -NoProfile -File "<SKILL_DIR>/scripts/recursive-closeout.ps1" -RepoRoot . -RunId "<run-id>" -Phase 08 -Force
```

## What It Does

- Scaffolds `04-test-summary.md`, `05-manual-qa.md`, `06-decisions-update.md`, `07-state-update.md`, or `08-memory-impact.md`
- Prefills the required header fields
- Prefills the required phase sections and audited sections
- Prefills late-phase input/output lists using the current run state
- Reuses the Phase 0 executable diff basis inside audited closeout scaffolds
- Optionally parses the actual preview URL from a preview-server log and injects it into Phase 5
- Scaffolds late-phase requirement disposition lines using the current machine-checkable status model
- Includes `/.recursive/memory/skills/SKILLS.md` in Phase 8 closeout scaffolds so skill-memory maintenance is explicit
- For Phase 8, scaffolds `## Run-Local Skill Usage Capture` and `## Skill Memory Promotion Review` so skill lessons are captured before they are promoted into durable memory
- If Phase 8 is already locked, rerunning `recursive-closeout` for phase `08` calls `/.recursive/scripts/recursive-training-phase8-trigger.py --auto`

## Preview URL Capture

- If `--preview-log` or `-PreviewLog` is provided for Phase 5, the helper parses the first served URL from that log.
- If parsing succeeds, the scaffolded `## QA Execution Record` includes both `Preview URL` and `Preview Log`.
- If parsing fails, the helper exits non-zero instead of guessing.

## Intended Workflow

1. Scaffold the closeout phase with `recursive-closeout`.
2. Replace the scaffold guidance with the actual evidence, decisions, state, or memory changes.
3. Run `recursive-lock` only after the phase content is complete and the required gates pass.
4. After locking Phase 8, rerun `recursive-closeout` for phase `08` without `--force` if you want the built-in training trigger hook to fire from this helper.
