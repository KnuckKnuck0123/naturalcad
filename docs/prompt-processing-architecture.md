# NaturalCAD Prompt Processing Architecture

## Objective

Turn a loose user prompt into a **detail-rich, dimension-aware, revision-friendly CAD spec** before code generation.

The goal is not maximal bureaucracy. The goal is to preserve the information that actually matters:
- what the part is
- what it interfaces with
- what dimensions drive fit
- which features must survive refinement
- what is still uncertain

## Current Direction

NaturalCAD should process prompts in layers, not as one giant rewrite:

1. **Raw prompt intake**
   - preserve the exact user wording
   - preserve attached image references separately from text

2. **Deterministic extraction pass**
   - parse direct dimensions such as `width 80`, `80 width`, `80x50x6`, `diameter 12 mm`
   - detect fit-critical language such as tolerance, clearance, press fit, slip fit
   - infer obvious feature families such as holes, tabs, ribs, flanges, tube interfaces
   - infer category and interface hints such as bracket, flange, wall mount, bolt pattern

3. **Structured semantic merge**
   - merge new prompt information into parent spec instead of replacing the whole object memory
   - preserve stable feature identity where possible
   - record explicit `spec_delta` operations for what changed

4. **Reference-image augmentation**
   - use images for visible geometry cues only
   - never treat image evidence as measurement-grade dimensions unless text provides them

5. **Generation-ready spec**
   - pass a richer spec into CAD generation so codegen sees more than a rewritten sentence

6. **Model-router boundary**
   - keep the model layer behind OpenRouter-style API calls or an equivalent provider abstraction
   - do not hard-bind the core prompt-processing architecture to one SDK agent worker if model swapping is strategically important
   - the worker can still act agentic internally, but the product contract should stay model-swappable

## Recommended Spec Shape

The generation spec should carry at least:

- `intent`
- `semantic_part`
  - category
  - function
  - topology
  - symmetry
  - interfaces
- `family_hint`
  - likely reusable generator family
  - novelty vs reuse posture
- `geometry`
  - primitive strategy
  - named features
  - feature counts
  - feature attributes
- `dimensions`
  - named driving dimensions in mm
- `constraints`
  - tolerance
  - clearance
  - fit
  - driving-dimension relationships
- `style`
  - visual/manufacturing bias
- `iteration_memory`
  - turn index
  - last user request
  - active dimensions
  - preserved constraints
  - tracked features
  - unresolved questions
- `uncertainties`
  - missing hole diameters
  - missing interface diameters
  - fit-critical language without explicit tolerance
- `notes`
  - cautionary or downstream handling guidance

## Merge Policy

Prompt processing should follow these rules:

1. **Explicit numeric updates beat prior inferred values**
2. **Parent spec survives unless the new prompt clearly overrides it**
3. **Fit-critical constraints should persist across turns**
4. **Uncertainties should shrink as the user answers them, not get wiped every turn**
5. **Images can add geometry cues but not fake precision**
6. **Iteration memory should survive model swaps**
7. **Provider choice should be replaceable without rewriting object memory semantics**

## Why This Matters

Without this layer, NaturalCAD behaves like:
- prompt continuation
- vague style transfer
- geometry guesswork with weak memory

With this layer, NaturalCAD can move toward:
- part-family understanding
- better multi-turn revision behavior
- more stable dimensional edits
- stronger reconstruction workflows for brackets, flanges, adapters, mounts, and repair parts

## Iteration Memory

NaturalCAD should not rely on prompt continuation alone.

Every turn should leave behind compact object memory that survives into the next turn:
- what part family we think this is
- which dimensions are active and driving
- which constraints must not be dropped
- which named features are now part of the object identity
- which uncertainties still need resolution

This memory belongs in the spec contract itself, not only in raw chat history.

## Model Layer Decision

Current preferred direction:
- use OpenRouter-style API calls for the prompt/spec/generation boundary
- keep model profiles swappable
- avoid welding the core product architecture to a single provider SDK worker

Why:
- easier model comparison
- easier cost/performance routing
- easier later migration
- iteration memory can stay stable while models change underneath it

## External Reference

`earthtojake/text-to-cad` is a useful benchmark/reference point for the category and should inform how sharp the input-to-CAD experience needs to feel.

NaturalCAD should learn from that level of legibility and capability, but keep building its own stronger reconstruction- and iteration-aware spec architecture.

## Beta Posture

For the small Vercel-hosted beta the prompt-processing layer must:

- keep image-guided iteration alive but route image reading through a cheaper
  vision-summary lane instead of paying full spec-model cost for OCR-style work
- keep iteration memory in the spec contract, not in prompt continuation
- accept that early traffic is mostly for **learning**, not for proving polish
- treat all incoming user prompt + attachment text as untrusted and reject obvious
  prompt-injection patterns at the API boundary

Guest abuse controls for the beta are layered:

1. per-project generation cap
2. per-project token cap (real worker telemetry, not request count)
3. cross-project request/window cap keyed to the guest session so opening fresh
   projects does not bypass spam control

Full deployment + env detail lives in [`beta-deployment.md`](./beta-deployment.md).

## Immediate Practical Standard

Within reason, every prompt should try to leave the system with more of the following than it started with:
- more named dimensions
- more interface knowledge
- more feature structure
- more explicit constraints
- fewer hidden assumptions

That is the architecture target for maximum detail with dimensional accuracy, without pretending we already have fabrication-grade certainty.
