# NaturalCAD Compositional Spec v1.1

## Why this exists

NaturalCAD is currently targeting **concept-grade** generation, not fabrication-grade precision.
That means the next spec should stay loose enough to support novel and unexpected objects, instead of forcing every prompt into a tiny menu of safe default families.

This spec is meant to capture:
- intent
- semantic part meaning
- topology/composition
- geometry features and operations
- dimensions
- constraints
- style cues

It is intentionally less rigid than a true later-phase spec-to-model contract.

## Design goals

1. Preserve novelty and surprise
2. Avoid collapsing every prompt into the same default family
3. Capture enough structure to support execution and logging
4. Leave room for later hardening into stricter parametric generators

## Shape

```json
{
  "spec_version": "1.1",
  "intent": "Offset wall support with ribbed spine and staggered mounting tabs",
  "mode": "part",
  "output_type": "3d_solid",
  "units": "mm",
  "semantic_part": {
    "category": "support",
    "function": "wall-mounted load transfer",
    "topology": ["main spine", "2 mounting tabs", "reinforcing ribs"],
    "symmetry": "asymmetric"
  },
  "family_hint": {
    "name": "support_bracket",
    "generation_mode": "extend",
    "parent_family": null,
    "confidence": 0.64,
    "novelty_score": 0.72
  },
  "geometry": {
    "primitive_strategy": ["extrude", "boolean_subtract", "fillet"],
    "features": [
      {
        "name": "spine",
        "feature_type": "tapered_plate",
        "attributes": {"taper_ratio": 0.7}
      },
      {
        "name": "tabs",
        "feature_type": "offset_mounts",
        "count": 2,
        "attributes": {"tab_offset": 18}
      },
      {
        "name": "ribs",
        "feature_type": "triangular_gusset",
        "count": 3,
        "attributes": {"rib_depth": 10}
      }
    ]
  },
  "dimensions": {
    "overall_height": 120,
    "overall_width": 60,
    "overall_depth": 45
  },
  "constraints": [
    {
      "kind": "min",
      "target": "wall_thickness",
      "value": 6
    }
  ],
  "style": {
    "keywords": ["industrial", "structural", "heavy-duty"],
    "symmetry": "asymmetric",
    "manufacturing_bias": "machined"
  },
  "dedupe": {
    "canonical_signature": null,
    "similar_to_job_id": null,
    "is_likely_duplicate": false
  },
  "notes": [
    "Treat as a concept-grade structural support rather than a fabrication-verified design."
  ]
}
```

## Interpretation notes

### `intent`
A concise restatement of what the prompt is trying to produce.

### `semantic_part`
Describes what the object is and how it is composed, without prematurely locking it into a rigid generator family.

### `family_hint`
Optional. This should be treated as a backend hint, not as the main creative frame.
- `reuse`: known generator likely fits
- `extend`: known generator likely fits with variation
- `new`: likely needs a new generator path or a looser execution strategy

### `geometry`
Captures operations and features. This is closer to executable structure than pure natural language, while still leaving room for novelty.

### `dimensions`
Stores named scale-driving values. These should stay loose in concept-grade mode, then become more constrained in later phases.

### `constraints`
Carries guardrails and relationships, but should not yet be treated as full fabrication-grade tolerance logic.

### `dedupe`
Supports later duplicate detection and lineage without dominating the first-pass generation stage.

## Current recommendation

Use this spec as the next target for:
- backend model output
- prompt logging
- evaluation
- future prompt-to-build123d translation

Current repo status:
- `POST /v1/generate-spec` now emits this general semantic shape through a stub translator
- the Gradio app temporarily adapts the semantic spec back into the older generator families for execution
- this keeps the contract moving forward without breaking the current build123d demo path

Do not over-tighten it yet. NaturalCAD still needs room for new and unexpected objects.
