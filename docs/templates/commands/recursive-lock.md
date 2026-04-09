# recursive-lock (prompt template)

> Paste this into chat if your agent does not support custom slash commands.

## Usage Pattern

```text
Lock recursive artifact: [run-id] [artifact]
```

## Script (Recommended)

```powershell
python "<SKILL_DIR>/scripts/recursive-lock.py" --repo-root . --run-id "<run-id>" --artifact "<artifact>.md"
python3 "<SKILL_DIR>/scripts/recursive-lock.py" --repo-root . --run-id "<run-id>" --artifact "<artifact>.md"

powershell -ExecutionPolicy Bypass -File "<SKILL_DIR>/scripts/recursive-lock.ps1" -RepoRoot . -RunId "<run-id>" -Artifact "<artifact>.md"
pwsh -NoProfile -File "<SKILL_DIR>/scripts/recursive-lock.ps1" -RepoRoot . -RunId "<run-id>" -Artifact "<artifact>.md"
```

## What It Does

- Validates the target artifact before locking
- Refuses to lock if required gates or lint-critical structure are invalid
- Refuses to lock strict Phase 3 artifacts that are missing RED or GREEN evidence
- Refuses to lock pragmatic Phase 3 artifacts that are missing an explicit exception rationale plus compensating evidence
- Refuses to lock Phase 5 artifacts whose declared QA mode is missing the required sign-off or execution evidence
- Sets `Status: LOCKED`
- Writes `LockedAt`
- Computes canonical `LockHash`

## Example

```text
Lock recursive artifact: <run-id> 04-test-summary.md
```
