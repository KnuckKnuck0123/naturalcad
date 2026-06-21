# NaturalCAD Remaining Work

## Current Position

NaturalCAD is no longer just a rough frontend mock. The main website lane exists in `apps/web`, guest session bootstrap works, generation works, iteration works in a basic way, and soft reset exists.

The product is now past the question of "does the loop exist?" and into the more important question:

- can the loop become smart, reliable, and affordable enough to be useful?

That work breaks down into a few real categories.

## 1. Better Modeling and Iteration

This is the highest-value product work.

Current issue:
- the app can iterate, but the iteration memory is still relatively shallow
- the system behaves more like prompt continuation than durable part understanding
- detail quality is still inconsistent for more exact components

Needed:
- stronger multi-turn reconstruction logic
- better retention of part identity across corrections
- more detailed component generation
- better feature-level edits instead of only whole-prompt rewrites

Examples:
- "make a carburetor for my old John Deere"
- "actually it's a Buck 500"
- "make the holes 2 mm for the tubes"

The system should preserve structured understanding of:
- part family
- mounting conditions
- dimensions
- named features
- revision history

## 2. Prompt to Spec / JSON Layer

This is probably the main technical bridge between toy text-to-CAD and a real reconstruction tool.

Goal:
- translate user prompts into a structured spec/JSON representation that is high-detail but token-efficient

Why it matters:
- preserves intent across turns
- makes refinement cheaper than replaying large freeform prompt histories
- makes edits more explicit and safer
- supports future scan/photo/dimension ingestion

This layer should eventually track:
- part name / type
- candidate product or equipment family
- inferred constraints
- dimensions and tolerances
- holes / bosses / flanges / brackets / offsets / tube interfaces
- open questions and uncertainties
- edit operations across iterations

## 3. Memory and Refinement

Iteration should not just remember previous text. It should remember the evolving object.

Needed:
- durable per-project memory of spec state
- explicit refinement operations
- better handling of corrections, reversals, and "actually..." prompts
- visibility into what changed from version to version

In practice this means:
- structured part memory
- diffable revisions
- refinement-aware prompts to the generation layer

## 4. Guest Cost Control

The guest flow is useful, but it can become expensive quickly if left open-ended.

Questions to solve:
- how many runs per guest session?
- how many retries before cooldown?
- what gets persisted for guests versus only for signed-in users?
- what rate limits belong in frontend versus backend?

Likely controls:
- session quotas
- cooldown windows
- backend rate limiting
- artifact retention limits
- cheaper default model/profile for guest usage
- upgrade gates for heavier or repeated work

This needs to be solved before broad public exposure.

## 5. Vercel Deployment

The website lane is intended for Vercel, but deployment still needs to be treated as a concrete work item rather than an assumption.

Needed:
- confirm environment variable shape for `apps/web`
- verify build and runtime behavior on Vercel
- point frontend to the correct hosted backend URL
- confirm guest bootstrap, generate, recovery, and export flows in hosted conditions
- document deployment steps cleanly

This is mostly execution and validation work, not product discovery.

## 6. Frontend Product Surface

The frontend is in decent shape, but it is not done.

Still left:
- account states
- payment or usage-upgrade states
- guest-to-account transition
- clearer export/download flows
- subscription/limits messaging if monetization becomes visible

This should stay behind modeling/spec work in priority unless launch pressure forces it forward.

## Suggested Order

1. Better modeling and iteration
2. Prompt-to-spec / JSON layer
3. Memory and refinement behavior
4. Guest cost controls
5. Vercel deployment hardening
6. Accounts / payment / polished frontend states

## Product Note

NaturalCAD should still start as a broad text-to-CAD tool because that keeps it legible and easy to try.

But the sharper wedge is reconstruction:
- replacement parts
- missing mounts
- fit-critical edits
- practical repair scenarios for wrench turners, farmers, and mechanics

That is where the product should become unusually strong.
