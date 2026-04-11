# Live Visualizer

A custom live modeling environment for LLM-assisted geometry workflows.

## Core idea

This project is for a modeling tool that combines:
- live model viewing
- editable variables and code
- terminal/log feedback
- LLM-assisted model generation and editing
- multiple visual modes from the same scene state

## Position on build123d

`build123d` should be treated as an important geometry backend, but not baked so deeply into the app that the entire product becomes impossible to evolve.

So the architecture should be:
- custom app shell
- custom scene/state/visualization pipeline
- pluggable geometry adapters
- build123d as the first and best-supported adapter

That keeps the project flexible while still embracing the current best geometry engine for this workflow.

## Initial product shape

Three-pane interface:
- editor / prompt / parameter control
- live viewport
- terminal / logs / agent output

## Near-term goals

1. Create a custom app shell
2. Support build123d as the first geometry adapter
3. Enable live regeneration from script or parameter changes
4. Separate display modes:
   - viewport shaded
   - graphic mass
   - technical/vector
5. Define LLM integration layer:
   - OpenClaw-driven
   - provider-agnostic fallback

## Proposed repo layout

- `apps/viewer` - main app shell
- `packages/core` - scene graph, document model, orchestration types
- `packages/renderer` - viewport and render mode logic
- `packages/llm` - LLM session/provider integration
- `packages/session` - terminal/process/runtime session management
- `packages/ui` - reusable interface components
- `examples/build123d` - test scripts and adapter examples

## Principles

- model first, render second
- one source of geometric truth
- multiple display modes from the same scene
- user can steer with language, numbers, and code
- terminal remains a first-class part of the workflow
