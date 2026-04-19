---
name: recursive-review-bundle
description: 'Use when recursive-mode work needs a canonical delegated-review or audit handoff. Generates reproducible review bundles for Phase 3.5 code review, test review, or other delegated checks using the repo review-bundle scripts.'
---

# recursive-review-bundle

Use this skill to prepare a canonical review bundle before delegating an audit or review in `recursive-mode`.

This skill does not replace `/.recursive/RECURSIVE.md`. It packages the context bundle that delegated reviewers need so the review is durable, reproducible, and acceptable to the workflow.

## Canonical Scripts

Use the repo scripts:

- `./scripts/recursive-review-bundle.py`
- `./scripts/recursive-review-bundle.ps1`

Prefer the Python script when both toolchains are available. Use the PowerShell wrapper when the delegated path is already PowerShell-oriented.

## Minimum Inputs

Provide all of:

- repo root
- run id
- phase name
- reviewer role
- artifact path being reviewed
- exact upstream artifact paths
- relevant audit questions
- required output shape

Add explicit evidence refs or addenda when they matter. The bundle generator will also auto-discover relevant addenda and skill-memory refs when applicable.

## Typical Commands

```bash
python ./scripts/recursive-review-bundle.py \
  --repo-root . \
  --run-id "<run-id>" \
  --phase "03.5 Code Review" \
  --role code-reviewer \
  --artifact-path "/.recursive/run/<run-id>/03.5-code-review.md" \
  --upstream-artifact "/.recursive/run/<run-id>/00-requirements.md" \
  --upstream-artifact "/.recursive/run/<run-id>/02-to-be-plan.md" \
  --routing-config-path ".recursive/config/recursive-router.json" \
  --routing-discovery-path ".recursive/config/recursive-router-discovered.json" \
  --routed-cli "codex" \
  --routed-model "gpt-5.4" \
  --audit-question "Which R# remain incomplete?" \
  --required-output "Findings ordered by severity"
```

```powershell
pwsh -NoProfile -File ./scripts/recursive-review-bundle.ps1 `
  -RepoRoot . `
  -RunId "<run-id>" `
  -Phase "03.5 Code Review" `
  -Role code-reviewer `
  -ArtifactPath "/.recursive/run/<run-id>/03.5-code-review.md" `
  -UpstreamArtifact "/.recursive/run/<run-id>/00-requirements.md","/.recursive/run/<run-id>/02-to-be-plan.md" `
  -RoutingConfigPath ".recursive/config/recursive-router.json" `
  -RoutingDiscoveryPath ".recursive/config/recursive-router-discovered.json" `
  -RoutedCli "codex" `
  -RoutedModel "gpt-5.4" `
  -AuditQuestion "Which R# remain incomplete?" `
  -RequiredOutput "Findings ordered by severity"
```

## Acceptance Rules

- Record `Review Bundle Path` in the delegated phase artifact.
- Refresh the bundle after material repairs or scope changes.
- Require the reviewer to cite the bundle path, upstream artifacts reread, relevant addenda, changed files or code refs reviewed, and a final verdict.
- Do not treat a bare bundle file as proof of review quality; the written review still has to use the bundle contents.

## Routing Awareness

If the prepared bundle will be handed to a routed reviewer, re-read:

- `/.recursive/config/recursive-router.json`
- `/.recursive/config/recursive-router-discovered.json`

immediately before the delegated call, and include the relevant routing-path citations in the review or action-record metadata.

## References

- `/.recursive/RECURSIVE.md`
- `/docs/templates/commands/recursive-review-bundle.md`
- `/skills/recursive-subagent/SKILL.md`
