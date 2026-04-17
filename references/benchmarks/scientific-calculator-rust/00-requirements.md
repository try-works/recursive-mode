## Requirements

### `R1` Dual-display calculator workspace

Description: Build a browser-hosted scientific calculator with a clear calculator layout and visible display surfaces for both the expression in progress and the current result or active input.

Acceptance criteria:
- The UI includes a calculator keypad or equivalent control surface for digits, operators, and scientific actions.
- The UI shows an expression or tape display separate from the main numeric result or entry display.
- The UI supports clear-all, clear-entry, backspace, decimal entry, and sign-toggle behavior.
- The display updates correctly as the user builds, edits, and evaluates expressions.

### `R2` Expression parsing and operator precedence

Description: The calculator must evaluate real expressions instead of relying only on immediate left-to-right button behavior.

Acceptance criteria:
- The calculator supports `+`, `-`, `*`, `/`, and exponentiation with the expected operator precedence.
- The calculator supports nested parentheses.
- Unary negation or sign handling works in realistic entry flows.
- Evaluating an expression updates the display without requiring a backend or external engine.

### `R3` Scientific functions and constants

Description: The benchmark should require more than a four-function calculator.

Acceptance criteria:
- The calculator supports visible scientific functions such as `sin`, `cos`, `tan`, `sqrt`, `log10`, and `ln`.
- The calculator supports useful constants such as `pi` and `e`.
- Scientific functions can participate in larger expressions instead of only stand-alone single-step actions.
- Domain or invalid-operation errors are surfaced visibly rather than silently producing nonsense.

### `R4` Degree-radian mode and result behavior

Description: The calculator should make trigonometric behavior explicit and testable.

Acceptance criteria:
- The UI includes a degree/radian mode toggle.
- Trigonometric results change correctly when the angle mode changes.
- The active angle mode is visible in the UI.
- Result formatting stays readable for normal values and common scientific outputs.

### `R5` Memory register and reusable history

Description: The calculator should support richer state than one transient display value.

Acceptance criteria:
- The UI supports memory actions such as `MC`, `MR`, `M+`, and `M-`.
- The UI shows recent calculation history or a reusable result tape.
- A user can reuse a prior result or history entry without retyping the full expression.
- Memory or history state updates correctly after evaluations.

### `R6` Keyboard input, persistence, and finished-browser UX

Description: The calculator should feel complete enough for browser-based validation instead of only passing tests.

Acceptance criteria:
- A user can drive the calculator with keyboard input for digits, operators, Enter, Backspace, and Escape or comparable clear behavior.
- Calculator state or recent history persists in browser-local storage across reloads.
- Error states, angle mode, and memory state are visible enough for screenshot-based validation.
- The layout remains usable at typical laptop-browser widths.

### `R7` Quality gates

Description: The benchmark result should be judged on working software rather than source changes alone.

Acceptance criteria:
- `cargo test` succeeds.
- `trunk build --release` succeeds.
- `trunk serve --release --address 127.0.0.1 --port <port>` can serve the built app locally.
- The implementation includes meaningful automated tests for expression evaluation, scientific-function correctness, angle-mode behavior, and at least one error case.

## Out of Scope

- `OOS1`: Graph plotting or symbolic algebra.
- `OOS2`: Any server, API, database, Docker, or cloud dependency.
- `OOS3`: User accounts, synchronization, or collaboration.
- `OOS4`: Programmer-mode bitwise math or matrix-calculator features.

## Constraints

- Use Rust for the application logic and browser UI implementation.
- Keep all state local to the browser.
- The project must run from a disposable temp folder.
- Do not require any external service beyond standard Rust tooling and local package installation.
- Keep the app suitable for later browser-agent screenshot validation.

## Assumptions

- Rust, cargo, and rustup are available in the benchmark environment.
- The benchmark harness may install or prepare Trunk and the `wasm32-unknown-unknown` target before the coding agent starts.
- The coding agent may add helper modules, tests, and styles as needed.
