# Milestone 01 - Stable Live Modeling Loop

## Goal

Turn the prototype into a dependable first product loop.

## Scope

- edit build123d code in-app
- run geometry through the local build123d runtime
- stream logs/errors live
- preview geometry in a live viewport via STL
- export both STL and STEP from the same run

## Why this first

This locks the core modeling runtime before deeper LLM integration.
If the live loop is weak, the AI layer becomes brittle and frustrating.

## Definition of done

- code changes run reliably from the UI
- viewport updates consistently after successful runs
- STL download works
- STEP download works
- errors are readable in the log pane
- repo is clean enough to keep building on

## Next after this

- parameter controls and editable variables
- document model and adapter contract
- LLM edit/apply flow
- vector and graphic-mass display modes
