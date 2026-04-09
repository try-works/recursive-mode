# recursive-subagent-action (prompt template)

> Paste this into chat if your agent does not support custom slash commands.

## Usage Pattern

```text
Record a subagent action for run <run-id> phase <phase> so the controller can verify it against real files and recursive artifacts.
```

## Script (Recommended)

```powershell
python "<SKILL_DIR>/scripts/recursive-subagent-action.py" --repo-root . --run-id "<run-id>" --subagent-id reviewer-01 --phase "03.5 Code Review" --purpose "Delegated code review" --execution-mode review --artifact-path "/.recursive/run/<run-id>/03-implementation-summary.md" --review-bundle "/.recursive/run/<run-id>/evidence/review-bundles/code-review.md" --action-taken "Reviewed the implementation summary, review bundle, and changed files for requirement and diff alignment." --reviewed-file "src/app.py" --artifact-read "/.recursive/run/<run-id>/02-to-be-plan.md" --artifact-read "/.recursive/run/<run-id>/03-implementation-summary.md" --evidence-used "/.recursive/run/<run-id>/evidence/logs/green/final.log" --finding "No blocking issues remained after verifying the repaired diff." --verification-path "src/app.py" --verification-path "/.recursive/run/<run-id>/evidence/review-bundles/code-review.md" --verification-item "Inspect these paths first during controller acceptance."

pwsh -NoProfile -File "<SKILL_DIR>/scripts/recursive-subagent-action.ps1" -RepoRoot . -RunId "<run-id>" -SubagentId reviewer-01 -Phase "03.5 Code Review" -Purpose "Delegated code review" -ExecutionMode review -ArtifactPath "/.recursive/run/<run-id>/03-implementation-summary.md" -ReviewBundle "/.recursive/run/<run-id>/evidence/review-bundles/code-review.md" -ActionTaken "Reviewed the implementation summary, review bundle, and changed files for requirement and diff alignment." -ReviewedFile "src/app.py" -ArtifactRead "/.recursive/run/<run-id>/02-to-be-plan.md","/.recursive/run/<run-id>/03-implementation-summary.md" -EvidenceUsed "/.recursive/run/<run-id>/evidence/logs/green/final.log" -Finding "No blocking issues remained after verifying the repaired diff." -VerificationPath "src/app.py","/.recursive/run/<run-id>/evidence/review-bundles/code-review.md" -VerificationItem "Inspect these paths first during controller acceptance."
```

## What It Writes

- A durable Markdown action record under `/.recursive/run/<run-id>/subagents/`
- Metadata, inputs provided, claimed file/artifact impact, claimed findings, and verification handoff
- The scaffold is only a starting point; replace placeholder `none` sections with the concrete files, artifacts, evidence, and findings from the delegated work before relying on it
- For review or audit records, point `Current Artifact` at the stable artifact actually reviewed when possible. If you point it at a mutable draft and then edit that draft later, the action-record hash will go stale and should be refreshed.

## Controller Rule

Writing the action record is not acceptance. The controller must still verify:

- claimed changed files against the real diff
- claimed created files against the real worktree
- claimed artifact refs against real recursive artifacts
- bundle/action-record alignment when a review bundle was used
