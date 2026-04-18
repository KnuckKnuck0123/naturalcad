# Engine-Assembly Milestone (Concept)

## Goal
Support high-detail assemblies (example: engine block + major subsystems) without relying on a single one-shot prompt-to-code pass.

## Why
Single-pass generation is strong for parts and simple assemblies, but detailed mechanical assemblies need decomposition, validation, and staged execution.

## Proposed architecture (multi-stage)

1. **Intent + Scope Pass**
   - Parse user request into complexity level and target detail level (L1/L2/L3).
   - Confirm assumptions if needed (internal channels, bolt patterns, tolerances, etc.).

2. **Assembly Plan JSON**
   - Generate a strict JSON plan:
     - parts list
     - param schema per part
     - mating/constraint relationships
     - units + coordinate conventions
   - Validate against a JSON schema before any CAD execution.

3. **Per-Part CAD Generation**
   - Generate build123d code per part (isolated runs).
   - Validate and export each part independently.
   - Retry/fix only failed parts, not the whole assembly.

4. **Assembly Build Pass**
   - Compose validated parts into final assembly.
   - Run constraint checks and collision checks where possible.

5. **Output Profiles**
   - L1: concept massing
   - L2: manufacturing-relevant external features
   - L3: high-detail subsystem geometry
   - Export: STEP/STL (+ optional linework outputs later)

## Guardrails
- Per-part complexity cap and timeout.
- Max part count per run (configurable).
- Graceful degrade path (drop to L2 if L3 is too heavy).
- User-facing messages should explain what detail was delivered.

## Success criteria
- Higher success rate for detailed prompts.
- Better partial recovery (single part fail does not kill full job).
- More predictable latency and compute cost.
- Clear user control over detail level.

## Suggested implementation order
1. Define JSON schema + validator.
2. Add planner stage (returns plan only).
3. Add per-part execution loop with retries.
4. Add assembly compose stage.
5. Add detail profile controls in UI.
