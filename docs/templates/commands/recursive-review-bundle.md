# recursive-review-bundle (prompt template)

> Paste this into chat if your agent does not support custom slash commands.

## Usage Pattern

```text
Generate a recursive review bundle for run <run-id> phase 03.5 using the canonical bundle format.
```

## Script (Recommended)

```powershell
python "<SKILL_DIR>/scripts/recursive-review-bundle.py" --repo-root . --run-id "<run-id>" --phase "03.5 Code Review" --role code-reviewer --artifact-path "/.recursive/run/<run-id>/03.5-code-review.md" --upstream-artifact "/.recursive/run/<run-id>/00-requirements.md" --upstream-artifact "/.recursive/run/<run-id>/02-to-be-plan.md" --upstream-artifact "/.recursive/run/<run-id>/03-implementation-summary.md" --routing-config-path ".recursive/config/recursive-router.json" --routing-discovery-path ".recursive/config/recursive-router-discovered.json" --routed-cli "codex" --routed-model "gpt-5.4" --audit-question "Which R# remain incomplete?" --audit-question "Which changed files drift from the plan?" --required-output "Findings ordered by severity"

pwsh -NoProfile -File "<SKILL_DIR>/scripts/recursive-review-bundle.ps1" -RepoRoot . -RunId "<run-id>" -Phase "03.5 Code Review" -Role code-reviewer -ArtifactPath "/.recursive/run/<run-id>/03.5-code-review.md" -UpstreamArtifact "/.recursive/run/<run-id>/00-requirements.md","/.recursive/run/<run-id>/02-to-be-plan.md","/.recursive/run/<run-id>/03-implementation-summary.md" -PriorRef "/.recursive/memory/MEMORY.md" -RoutingConfigPath ".recursive/config/recursive-router.json" -RoutingDiscoveryPath ".recursive/config/recursive-router-discovered.json" -RoutedCli "codex" -RoutedModel "gpt-5.4" -AuditQuestion "Which R# remain incomplete?","Which changed files drift from the plan?" -RequiredOutput "Findings ordered by severity"
```

Example for a Phase 4 test-review bundle:

```powershell
python "<SKILL_DIR>/scripts/recursive-review-bundle.py" --repo-root . --run-id "<run-id>" --phase "04 Test Summary" --role tester --artifact-path "/.recursive/run/<run-id>/04-test-summary.md" --upstream-artifact "/.recursive/run/<run-id>/02-to-be-plan.md" --upstream-artifact "/.recursive/run/<run-id>/03-implementation-summary.md" --evidence-ref "/.recursive/run/<run-id>/evidence/logs/green/tests.log" --audit-question "Are the executed tests sufficient for the changed behavior?" --required-output "Audit recommendation"
```

## What It Writes

- A markdown review bundle under `/.recursive/run/<run-id>/evidence/review-bundles/`
- Artifact content hash for stale-bundle detection
- Diff basis from `00-worktree.md`
- Current changed file list
- Upstream artifact list
- Relevant addenda auto-discovered by default
- Prior recursive evidence refs when supplied
- Code refs, evidence refs, audit questions, and required output hints
- Routed review metadata such as `Routing Config Path`, `Routing Discovery Path`, `Routed CLI`, and `Routed Model`

## Phase 3.5 Expectation

When review is delegated, record the generated bundle path in `03.5-code-review.md`:

```md
## Review Metadata

- Review Bundle Path: `/.recursive/run/<run-id>/evidence/review-bundles/<bundle>.md`
- Routing Config Path: `/.recursive/config/recursive-router.json`
- Routing Discovery Path: `/.recursive/config/recursive-router-discovered.json`
- Routed CLI: `codex`
- Routed Model: `gpt-5.4`
```

If repairs materially change scope, changed files, or evidence, regenerate the bundle before re-audit.

If meaningful subagent work follows from the delegated review, capture that work in a matching action record under `/.recursive/run/<run-id>/subagents/`.

The maintainer smoke harness uses the same bundle contract, so this file is also the reference shape for automated regression runs.
