---
name: recursive-router
description: 'Use when recursive-mode needs to route delegated audit, review, or bounded implementation work through external transports, CLIs, and models while preserving controller verification and fallback behavior.'
---

# recursive-router

Use this skill when `recursive-mode` and `recursive-subagent` have already established a delegated role and you want the route to be driven by a user-editable CLI/model policy instead of ad hoc controller choice.

This skill does **not** relax recursive-mode. Routed external output is still untrusted until the main agent verifies it against actual files, actual diffs, and actual recursive artifacts.

## Controller Boundary

The main orchestrator remains the model the user is currently interacting with in their CLI, IDE, or agent session.

`recursive-router` does **not** become a second orchestrator or a second workflow spec. It only helps the current controller choose and invoke an external CLI/model for a bounded delegated role.

The current controller remains responsible for:

- selecting and sequencing the active recursive phase
- reading the governing recursive docs before delegation
- using `recursive-subagent` and the canonical review-bundle / prompt-bundle contract
- preparing the delegated context bundle or prompt bundle
- making sure routed roles receive the needed docs and exact output contract
- rejecting routed output that is incomplete, context-free, or off-contract
- deciding whether to repair, re-route, fall back, or continue the workflow
- fixing issues introduced by delegated output and rerunning the audit-repair loop until the real gates pass

## Invocation Boundary

`recursive-router` is **opt-in**. Do **not** activate it just because delegated work is possible or because router config files already exist in the repo.

Because router setup and probing may inspect local CLI installs plus provider/model configuration on the user's device, only treat explicit routing language as an invocation signal. Valid examples include phrases containing:

- `route`
- `routing`
- `router`
- `set model`
- `set provider`
- `configure routing`
- `configure model routing`
- `use <provider/model> for <role>`

When that kind of language appears, ask the user **first** whether they want to set up model routing between the different providers for this repo. Do not run `init`, `probe`, `configure`, or any other local-environment discovery step until the user confirms.

If the user declines or only wants an explanation of router behavior, do not inspect the local device and do not modify routing policy.

## Purpose

Use `recursive-router` to:

- probe which supported CLIs are available in the current environment
- inspect the generated discovery inventory of CLI ids and advertised models
- configure verified CLI/model bindings safely before writing policy
- resolve a subagent role to a configured CLI/model pair
- ask the user for unresolved role bindings when policy says `ask`
- preserve explicit fallback behavior when routed CLIs are unavailable

## Trigger Examples

- `Set up routing between Codex, Kimi, and Opencode for this repo`
- `Use the router for delegated review roles`
- `Route code-reviewer through Kimi`
- `Set model bindings for the audit roles`
- `Configure model routing between providers`

## Canonical Paths

- Routing policy: `/.recursive/config/recursive-router.json`
- Discovery inventory: `/.recursive/config/recursive-router-discovered.json`

Canonical scripts are `recursive-router-*`.
Legacy `recursive-router-cli-*` script names still exist only as compatibility wrappers; prefer the canonical names in new controller flows and docs.

## Canonical Roles

- `orchestrator`
- `analyst`
- `planner`
- `implementer`
- `code-reviewer`
- `memory-auditor`
- `tester`

`orchestrator` is explicit in the router policy so the controller role is visible in the same config surface, but it should remain `local-only` with fallback `local-controller` by default. It owns final integration, repair, and acceptance: other routed roles can propose bounded work, but the orchestrator must fix any defects they leave behind and make sure all required gates pass.

Legacy compatibility aliases still resolve to these stage-aligned roles:

- `phase-auditor` -> `analyst`
- `traceability-auditor` -> `planner`
- `bounded-implementer` -> `implementer`
- `test-reviewer` -> `tester`

## Read Order

1. Read `/.recursive/RECURSIVE.md`.
2. Read `/skills/recursive-subagent/SKILL.md`.
3. Read `/.recursive/config/recursive-router.json`.
4. Read `/.recursive/config/recursive-router-discovered.json`.
5. Read `/.recursive/memory/skills/SKILLS.md` plus any relevant delegated-review or capability notes when the phase is capability-sensitive.

`recursive-mode` and `recursive-subagent` still own phase sequencing, audit standards, review-bundle rules, and acceptance criteria. Do not restate or weaken those here.

## Required Behavior

- Routing is an extension of `recursive-subagent`, not a replacement for it.
- The current CLI/IDE/agent session remains the single workflow controller; routed CLIs are assistants, not autonomous phase managers.
- Do **not** scan local CLI/provider/model state unless the user explicitly invoked routing and confirmed setup.
- External CLIs remain optional infrastructure.
- If a routed CLI or model cannot be used, follow configured fallback behavior instead of weakening the phase standard.
- When policy says `ask`, do **not** silently invent CLI/model bindings.
- No routed output may be accepted without main-agent verification against real repo state.
- Do **not** let a routed role choose its own phase, inputs, or acceptance standard.
- Routed roles do not own final acceptance. The orchestrator remains responsible for the audit-repair loop and must keep repairing or rerouting until the phase gates actually pass.
- Before dispatch, give the routed role a real context bundle: canonical review bundle or prompt bundle path, exact artifact paths, relevant upstream docs, required checks, and exact output shape.
- Prefer brief dispatch prompts that point at canonical workflow artifacts such as `00-requirements.md`, `01-as-is.md`, `02-to-be-plan.md`, the active phase artifact, or a generated review bundle, instead of inventing a second router-specific workflow narrative.
- Do **not** delegate using only vague file references such as "read the docs" when the routed model needs concrete context to succeed.
- If a routed model has shown weak instruction-following, inline the specific requirement, artifact, or section excerpts needed for that assignment and reject any output that does not cite or follow them.

## Discovery

Use the router scripts to initialize, probe, validate, and resolve routing:

```bash
python ./scripts/recursive-router-init.py --repo-root .
python ./scripts/recursive-router-probe.py --repo-root . --json
python ./scripts/recursive-router-configure.py --repo-root . --set code-reviewer=codex:gpt-5.4-mini --json
python ./scripts/recursive-router-invoke.py --repo-root . --role code-reviewer --prompt-file "./.recursive/router-prompts/code-reviewer-bundle.md" --json
python ./scripts/recursive-router-validate.py --repo-root .
python ./scripts/recursive-router-resolve.py --repo-root . --role code-reviewer --json
pwsh -NoProfile -File ./scripts/recursive-router-probe.ps1 -RepoRoot . -Json
pwsh -NoProfile -File ./scripts/recursive-router-configure.ps1 -RepoRoot . -Set code-reviewer=codex:gpt-5.4-mini -Json
pwsh -NoProfile -File ./scripts/recursive-router-invoke.ps1 -RepoRoot . -Role code-reviewer -PromptFile "./.recursive/router-prompts/code-reviewer-bundle.md" -Json
```

Built-in discovery targets are:

- `codex`
- `kimi`
- `opencode`

Built-in model discovery sources are:

- `codex`: `codex app-server --listen stdio://` with native `model/list`, falling back to `~/.codex/models_cache.json` when app-server discovery is unavailable
- `kimi`: configured model aliases from `~/.kimi/config.toml` so routed values match what `kimi --model ...` accepts
- `opencode`: configured/authenticated CLI inventory from `opencode models`

For `opencode`, router discovery should use the CLI's configured/authenticated provider and model inventory, so the routed model choices come from the user's real `opencode` setup rather than a hardcoded list.

For `opencode`, provider-qualified model ids such as `github-copilot/...` and `opencode/...` are valid routed targets when they appear in the authenticated inventory.

For `codex`, routed transport should prefer the native app-server protocol rather than `codex exec` when a downstream dispatcher needs to actually send a prompt.

Do **not** rely on a nonexistent top-level `codex model` command for automation. For manual spot checks, `codex exec -m <model>` is useful, but discovery authority should still come from app-server `model/list`.

For `kimi`, do **not** treat `/model` as an automation surface. `/model` is an in-session interactive picker, not a top-level discovery command, and routed config must use invocable alias keys rather than the raw underlying model slug.

Launcher details can differ across operating systems, shells, and devices. Treat the built-in adapter commands as defaults only. If the real local launcher or invocation shape differs, explore the environment first and then record that machine-specific binding in `cli_overrides` for a built-in CLI or `custom_clis` for a fully custom adapter instead of hardcoding a repo-wide path or wrapper assumption.

Custom CLIs may also be defined in the routing policy.

Policy timeout behavior:

- Default probe timeout is `50000` ms.
- Default invoke timeout is `180000` ms.
- Legacy router policies that predate `defaults.invoke_timeout_ms` are still valid; they inherit the current default invoke timeout instead of failing validation.

### Windows launcher notes learned from live routing

- If npm or PATH shims have been removed, bind `codex` or `opencode` through `cli_overrides` to the real executable path instead of assuming `codex.cmd` or `opencode.cmd` still exists.
- For `codex`, point the override at a real `codex.exe` that supports `app-server`; keep the routed transport on the native app-server path.
- For `opencode`, use the dedicated CLI binary such as `opencode-cli.exe`, not the desktop app wrapper such as `OpenCode.exe`.
- For simple one-shot `kimi` shell calls, `kimi --quiet --prompt "..."` works, but the CLI may still append session metadata like `<choice>STOP</choice>` and resume instructions.
- When another agent needs machine-readable `kimi` output, prefer `kimi --print --output-format stream-json --work-dir "<repo>" --prompt "..."` and parse the assistant text from the structured stream.
- If the caller speaks ACP and wants a persistent server instead of one-shot shell delegation, `kimi acp` is the supported Kimi ACP entrypoint.
- For simple one-shot `opencode` shell calls, `opencode-cli.exe run "..."` works; for machine-readable orchestration, prefer `opencode-cli.exe run --format json --dir "<repo>" "..."`.
- If the caller speaks ACP and wants a persistent server instead of one-shot shell delegation, use `opencode-cli.exe acp --cwd "<repo>"` rather than the desktop wrapper.
- Pass an explicit working directory when delegating real tasks: `kimi` uses `--work-dir`, and `opencode` uses `--dir`.
- Use ACP mode only when the upstream caller actually speaks ACP. For normal routed delegation, prefer `kimi --print ...` or `opencode-cli.exe run ...`.
- ACP server entrypoints for `kimi` and `opencode` were verified directly through CLI help on this machine. ACP client/router patterns such as `acpx` are **not** assumed available until they are verified in the current environment.

## Recommended Routing Workflow

1. Run `init` if the repo does not already have router config scaffolding.
2. Run `probe` and inspect `/.recursive/config/recursive-router-discovered.json`.
3. Ask the user for any unresolved role bindings in compact `role=cli:model` form.
4. Apply the requested bindings with `recursive-router-configure.py` or `.ps1` so each route is verified before save.
5. Build or refresh the canonical review bundle or routed prompt bundle for the exact delegated assignment using the contract from `recursive-subagent`.
6. Run `resolve` for the specific role immediately before delegated execution so fallback behavior stays current with the live environment.
7. Dispatch the bounded assignment with `recursive-router-invoke.py` or `.ps1`, then verify the result against the real repo state before any acceptance.

Prefer the configure script over hand-editing policy whenever the controller is making the change, because configure-and-verify prevents bad or stale bindings from being saved silently.

Prefer the invoke script over bespoke shell snippets or one-off helper scripts when the controller actually dispatches routed work. That keeps the route resolution, launcher selection, transport handling, and output capture on the repo-supported path.

## Delegation Payload Shape

The router should pass a concise dispatch prompt that references the real recursive artifacts rather than duplicating them. Typical payload ingredients are:

- delegated role
- active phase and artifact path
- canonical review-bundle path or prompt-bundle path
- exact upstream docs to read, usually including the active run docs such as `00-requirements.md`, `01-as-is.md`, `02-to-be-plan.md`, or the current audited artifact
- exact output contract owned by `recursive-subagent` or the generated review bundle

The router's job is to route that bundle to the selected CLI/model and return the output. The router should not invent substitute workflow rules.

## User Prompting

When a routed role is unresolved, present a compact role-based question that cites:

- discovered CLI ids
- version strings when available
- discovered model lists when available
- unresolved roles
- `/.recursive/config/recursive-router.json`
- `/.recursive/config/recursive-router-discovered.json`

Example prompt:

```text
I found these CLIs in this environment:
- codex (available, version 1.2.3)
- kimi (available, version 1.32.0)

Please choose a CLI and model for these roles in /.recursive/config/recursive-router.json.
For valid CLI ids and model ids, check /.recursive/config/recursive-router-discovered.json.

Unresolved roles:
- analyst
- code-reviewer
```

Valid compact answers:

```text
analyst=codex:gpt-5
code-reviewer=kimi:kimi-code/kimi-for-coding
```

After the user answers, prefer `recursive-router-configure.py` or `.ps1` with one or more `--set role=cli:model` bindings. The configure command must verify each proposed route by sending a live prompt to the selected model before it writes `/.recursive/config/recursive-router.json`. If any verification fails, do not save partial changes. If the user edited the policy file directly, reread it instead of overwriting those manual edits blindly.

Verification guidance learned from live routing:

- `codex` verification should use app-server transport, not a generic CLI-template invocation.
- `kimi` verification should use the configured alias and may still return a non-zero exit after producing the requested token; treat the token as the proof of model reachability, but record the exit code in action records.
- `opencode` verification should use the exact provider-qualified model id returned by `opencode models`.
- Verification only proves that a route is reachable. It does **not** prove that the routed role has enough context for the real assignment. The controller must still assemble the required docs and output contract for the actual dispatch.

## Fallback Behavior

Routing decisions may resolve to:

- `external-cli`
- `local-only`
- `fallback-local`
- `blocked`
- `ask-user`

Fallbacks must be explicit and auditable. Do not silently drop from routed delegation to a local path without recording why.

## Auditability

When routed delegation is used or attempted, phase artifacts and action records should record:

- `Routing Mode`
- `Routed Role`
- `Routed CLI`
- `Routed Model`
- `Routing Config Path`
- `Routing Discovery Path`
- `Routing Resolution Basis`
- `Routing Fallback Reason` when applicable
- `Controller Orchestrator`
- `Delegated Context Bundle`

Use `scripts/recursive-subagent-action.py` or `.ps1` to capture routed action-record details such as:

- `Router Used`
- `CLI Probe Summary`
- `Prompt Bundle Path`
- `Invocation Exit Code`
- `Output Capture Paths`

When routed prompts are sensitive to exact sectioning or citations, prefer a durable prompt bundle that includes:

- the role and bounded assignment
- the artifact path under review
- exact upstream docs or review bundle path
- relevant excerpts inlined when needed for weaker instruction-following models
- the exact required section headings and first-line rules
- explicit rejection conditions

## Warnings

- Do **not** invent CLI/model bindings when config is incomplete and policy says `ask`.
- Do **not** make external CLIs mandatory.
- Do **not** save unchecked bindings when the controller can use `recursive-router-configure.py` or `.ps1`.
- Do **not** treat the router as a replacement for the main controller in the current session.
- Do **not** configure Kimi with the raw `model = "..."` value from `~/.kimi/config.toml`; use the alias key that `kimi --model ...` accepts.
- Do **not** assume Codex will reject every invalid model early enough to serve as discovery. Prefer app-server `model/list` and the discovery inventory as the authority.
- Do **not** accept routed external output without controller verification against actual files, actual diffs, and actual recursive artifacts.
- Do **not** delegate with only bare file-path references when the routed role needs bundled context or exact output-shape instructions to succeed.
