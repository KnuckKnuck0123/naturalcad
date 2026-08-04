#!/usr/bin/env python3
"""Gradio shell for the NaturalCAD 2D Hugging Face prototype."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gradio as gr
import httpx

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from drawing_core import (  # noqa: E402
    REFERENCE_NOTE,
    SCHEMA_VERSION,
    DrawingScene,
    UNIT_MAP,
    build_fallback_scene,
    export_dxf,
    render_svg,
    scene_from_payload,
    scene_quality_report,
    scene_to_dict,
    scene_to_json,
)
from drafting_standards import NOAH_URIU_2D_PROFILE, URIU_PROMPT_LAYER_ROLES  # noqa: E402

ARTIFACTS_DIR = APP_DIR.parent / "artifacts"
RUNS_DIR = ARTIFACTS_DIR / "runs"
LOGS_DIR = ARTIFACTS_DIR / "logs"
RUN_LOG_PATH = LOGS_DIR / "runs.jsonl"
for directory in (ARTIFACTS_DIR, RUNS_DIR, LOGS_DIR):
    directory.mkdir(parents=True, exist_ok=True)

OPENROUTER_API_URL = os.getenv(
    "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"
).strip()
OPENROUTER_MODEL = (
    os.getenv("NATURALCAD_2D_MODEL")
    or os.getenv("OPENROUTER_MODEL")
    or "openai/gpt-4.1-mini"
).strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_REFERER = os.getenv("OPENROUTER_REFERER", "").strip()
OPENROUTER_TITLE = os.getenv("OPENROUTER_TITLE", "NaturalCAD 2D").strip()
OPENROUTER_TIMEOUT = float(os.getenv("NATURALCAD_2D_TIMEOUT", "120"))
MAX_PROMPT_CHARS = 2_000
MAX_REFERENCE_CHARS = 2_000
MAX_REFINEMENT_CHARS = 1_000

EXAMPLE_PROMPTS = [
    "Steel mounting plate 180x90 mm with four 12 mm corner holes and center label",
    "Wall bracket detail 180x90 mm with two 32x10 mm slots, centerline, and dimensions",
    "Detailed concrete footing section with rebar, soil hatch, leader notes, and dimensions",
    "Impossible looping staircase, dense axonometric linework, selective shadow hatches, no labels",
]

APP_THEME = gr.themes.Soft()

PROMPT_LAYER_GUIDE = "\n".join(
    f"  - {role}: {layer}" for role, layer in URIU_PROMPT_LAYER_ROLES.items()
)

MODEL_SYSTEM_PROMPT = f"""You are NaturalCAD 2D, a drafting scene generator.
Return only valid JSON matching this schema:
{{
  "schema_version": "{SCHEMA_VERSION}",
  "standard_profile": "{NOAH_URIU_2D_PROFILE}",
  "title": "short title",
  "units": "mm|cm|m|in|ft",
  "layers": [{{"name": "A-2D::A-DETAIL::A-DETAIL 05"}}, {{"name": "A-2D::A-DETAIL::A-DETAIL 03"}}, {{"name": "A-2D::A-DETAIL::A-HATCH"}}],
  "polylines": [{{"id": "outline", "points": [[0,0],[10,0],[10,5],[0,5]], "layer": "A-2D::A-DETAIL::A-DETAIL 05", "closed": true}}],
  "circles": [{{"id": "hole_1", "center": [0,0], "radius": 3, "layer": "A-2D::A-DETAIL::A-DETAIL 05"}}],
  "arcs": [{{"id": "arc_1", "center": [0,0], "radius": 8, "start_angle": 0, "end_angle": 90, "layer": "A-2D::A-DETAIL::A-DETAIL 03"}}],
  "slots": [{{"id": "slot_1", "center": [0,0], "length": 24, "width": 8, "angle": 0, "layer": "A-2D::A-DETAIL::A-DETAIL 05"}}],
  "hatches": [{{"id": "hatch_1", "boundary": [[0,0],[10,0],[10,5],[0,5]], "holes": [], "layer": "A-2D::A-DETAIL::A-HATCH", "pattern": "ANSI31", "pattern_scale": 1.0, "pattern_angle": 45, "opacity": 0.55}}],
  "texts": [{{"id": "label_1", "text": "note", "insert": [0,0], "height": 3, "layer": "A-ANNOT::A-TEXT"}}],
  "dimensions": [{{"id": "dim_1", "start": [0,0], "end": [10,0], "offset": 10, "angle": 0, "text": "10 mm", "layer": "A-ANNOT::A-DIM"}}],
  "leaders": [{{"id": "leader_1", "points": [[0,0],[10,10]], "text": "note", "text_height": 2.5, "layer": "A-ANNOT::A-NOTES"}}]
}}
Rules:
- Use numeric world coordinates only.
- Give every entity a short, stable id. Preserve existing ids during refinement.
- Use slots for obround holes and arcs for partial circular geometry.
- Always return standard_profile exactly "{NOAH_URIU_2D_PROFILE}".
- Put every entity on one of these exact semantic layer paths. List every used leaf layer in layers; NaturalCAD supplies its CAD color, linetype, hierarchy, display color, and plot lineweight:
{PROMPT_LAYER_GUIDE}
- Do not invent layer colors or widths. Use multiple standard layers so major, minor, hidden, center, hatch, dimension, and annotation work remain independently editable and BYLAYER.
- Keep linework economical and editable, but use enough secondary edges, joints, tread lines, contours, and material boundaries to make the requested subject recognizable.
- Represent hatches, dimensions, leaders, and text as their own objects.
- Valid hatch patterns are SOLID, ANSI31, ANSI32, ANSI33, ANSI34, ANSI35, ANSI36, ANSI37, ANSI38, AR-BRSTD, AR-CONC, AR-SAND, BRICK, CONCRETE1, CONCRETE2, CONCRETE3, EARTH, ESCHER, GLASS, GRASS, GRAVEL, GRID, INSUL, NET, SAND, STEEL, WATER, WOOD1, WOOD2, WOOD3, and WOOD4.
- Use hatch holes for openings inside a hatch boundary. pattern_scale controls spacing; pattern_angle is extra rotation added to the named pattern's native angle. ANSI31 already runs at 45 degrees, so use pattern_angle 0 for standard diagonal section lines. For roughly 100-200 mm details, start around scale 0.2-0.8 for material patterns and 0.5-1.5 for ANSI patterns. opacity controls SVG preview visibility from 0 to 1.
- ESCHER is only a legacy CAD hatch-pattern name; it does not create impossible geometry. Build impossible geometry from deliberate linework.
- Use SOLID for poche or shadow planes and material patterns for sectioned regions. Prefer a few intentional hatch regions over noisy decoration.
- Prefer millimeters unless the user clearly specifies another unit.
- Short conceptual prompts are valid. Commit to a recognizable best-effort composition instead of substituting an unrelated plate or bracket.
- For conceptual drawings, infer a balanced drawing field, omit dimensions unless requested, and use repetition, overlap, occlusion breaks, depth cues, and 3-8 selective hatch/shadow planes.
- Impossible geometry is valid 2D intent. Approximate it ambitiously with projected linework and polygon hatches even when it cannot exist as a physical 3D object.
- For Escher, Penrose, or impossible-stair requests, compose four connected axonometric stair flights. Each flight needs two edge/stringer polylines and 6-10 distinct tread polylines. Add 8-16 connecting, support, parapet, or occlusion lines, conflicting elevation cues, intentional breaks, and 3-6 SOLID shadow polygons. Omit dimensions unless requested.
- For complex concepts, do not stop at a diagrammatic outline: target 40-88 polylines, 120-512 total geometry points, 3-8 hatches, at least 3 used semantic layers, and no more than 112 total entities.
- Count the entities before returning. A complex concept with fewer than 32 polylines or fewer than 2 hatches is incomplete and must be deepened before output.
- For technical drawings, preserve stated dimensions and do not invent fit-critical or code-compliance claims.
- If details are uncertain, preserve the subject's defining structure in geometry and note only assumptions that materially help the drawing.
- Before returning JSON, verify that the subject is recognizable, linework fills the drawing field, hatches clarify depth/material, and no unrelated template geometry is present.
- Do not include markdown fences, prose, comments, or explanations."""

HIGH_CONFIDENCE_CONCEPT_TERMS = {"escher", "impossible", "penrose"}
SOFT_CONCEPT_TERMS = {"axonometric", "concept", "diagram", "perspective", "spatial", "sketch"}
TECHNICAL_TERMS = {
    "clearance", "code", "construction", "dimension", "egress", "fabrication", "floor-to-floor",
    "riser", "section", "tread", "width",
}
DETAIL_TERMS = {
    "architectural", "assembly", "detail", "detailed", "facade", "footing", "hatch", "hatching",
    "insulation", "material", "poche", "rebar", "section", "shadow", "stair",
}


def _generation_profile(prompt: str, image_path: str | None, prior_scene: dict[str, Any] | None) -> dict[str, Any]:
    lowered = prompt.lower()
    if prior_scene:
        mode = "REFINEMENT"
    elif image_path:
        mode = "REFERENCE_RECONSTRUCTION"
    elif any(term in lowered for term in HIGH_CONFIDENCE_CONCEPT_TERMS):
        mode = "CREATIVE_CONCEPT"
    elif any(term in lowered for term in TECHNICAL_TERMS) or any(character.isdigit() for character in lowered):
        mode = "TECHNICAL_DRAFT"
    elif any(term in lowered for term in SOFT_CONCEPT_TERMS):
        mode = "CREATIVE_CONCEPT"
    else:
        mode = "TECHNICAL_DRAFT"
    detail_requested = mode == "CREATIVE_CONCEPT" or any(term in lowered for term in DETAIL_TERMS)
    return {
        "mode": mode,
        "temperature": 0.35 if mode == "CREATIVE_CONCEPT" else 0.15,
        "max_tokens": 8_000 if mode == "CREATIVE_CONCEPT" else (6_500 if detail_requested else 4_000),
    }


def _image_info(image_path: str | None) -> tuple[str | None, tuple[int, int] | None]:
    if not image_path:
        return None, None
    path = Path(image_path)
    try:
        from PIL import Image

        with Image.open(path) as image:
            return path.name, image.size
    except Exception:
        return path.name, None


def _openrouter_headers() -> dict[str, str]:
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not configured")
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    if OPENROUTER_REFERER:
        headers["HTTP-Referer"] = OPENROUTER_REFERER
    if OPENROUTER_TITLE:
        headers["X-Title"] = OPENROUTER_TITLE
    return headers


def _data_url_for_image(image_path: str) -> str:
    mime_type = mimetypes.guess_type(image_path)[0] or "application/octet-stream"
    encoded = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def request_model_scene(
    prompt: str,
    reference_notes: str,
    units: str,
    image_path: str | None,
    prior_scene: dict[str, Any] | None = None,
) -> tuple[DrawingScene | None, dict[str, Any]]:
    if not OPENROUTER_API_KEY:
        return None, {"source": "demo_fallback", "reason": "OPENROUTER_API_KEY not configured"}

    profile = _generation_profile(prompt, image_path, prior_scene)
    user_lines = [
        f"Request: {prompt or 'No text prompt provided.'}",
        f"Reference notes: {reference_notes or 'None'}",
        f"Requested units: {units}",
        f"Intent mode: {profile['mode']}",
        "Prioritize recognizable geometry, semantic layers, and intentional hatches within the scene budgets.",
        f"Accuracy note: {REFERENCE_NOTE}",
    ]
    if prior_scene:
        user_lines.extend([
            "This is a refinement. Return the complete updated scene, preserving entity ids for unchanged geometry.",
            "Previous validated scene:",
            json.dumps(prior_scene, separators=(",", ":")),
        ])
    user_text = "\n".join(user_lines)
    content: Any = [{"type": "text", "text": user_text}]
    if image_path:
        content.append({"type": "image_url", "image_url": {"url": _data_url_for_image(image_path)}})

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": MODEL_SYSTEM_PROMPT},
            {"role": "user", "content": content if image_path else user_text},
        ],
        "temperature": profile["temperature"],
        "max_tokens": profile["max_tokens"],
    }
    started = time.monotonic()
    try:
        with httpx.Client(timeout=OPENROUTER_TIMEOUT) as client:
            response = client.post(OPENROUTER_API_URL, headers=_openrouter_headers(), json=payload)
        response.raise_for_status()
        data = response.json()
        raw_content = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        if not raw_content:
            raise ValueError("Model returned empty content")
        scene = scene_from_payload(json.loads(_strip_markdown_fences(raw_content)), requested_units=units)
        return scene, {
            "source": "model",
            "model": OPENROUTER_MODEL,
            "intent_mode": profile["mode"],
            "max_tokens": profile["max_tokens"],
            "latency_ms": int((time.monotonic() - started) * 1000),
            "usage": data.get("usage", {}),
        }
    except Exception as exc:
        return None, {
            "source": "demo_fallback",
            "model": OPENROUTER_MODEL,
            "intent_mode": profile["mode"],
            "max_tokens": profile["max_tokens"],
            "latency_ms": int((time.monotonic() - started) * 1000),
            "reason": str(exc),
        }


def write_run_log(payload: dict[str, Any]) -> None:
    with RUN_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")


def _entity_counts(scene: DrawingScene) -> dict[str, int]:
    return {
        "polylines": len(scene.polylines),
        "circles": len(scene.circles),
        "arcs": len(scene.arcs),
        "slots": len(scene.slots),
        "hatches": len(scene.hatches),
        "dimensions": len(scene.dimensions),
        "leaders": len(scene.leaders),
        "texts": len(scene.texts),
    }


def _finish_run(
    scene: DrawingScene,
    model_meta: dict[str, Any],
    *,
    prompt: str,
    reference_notes: str,
    image_path: str | None,
    started: float,
    refinement: bool,
) -> tuple[str, str, str, str, str, dict[str, Any]]:
    run_id = uuid.uuid4().hex[:8]
    dxf_path = RUNS_DIR / f"{run_id}.dxf"
    svg_path = RUNS_DIR / f"{run_id}.svg"
    scene_path = RUNS_DIR / f"{run_id}.scene.json"
    export_dxf(scene, dxf_path)
    svg_markup = render_svg(scene)
    svg_path.write_text(svg_markup, encoding="utf-8")
    scene_path.write_text(scene_to_json(scene), encoding="utf-8")
    image_name, image_size = _image_info(image_path)
    quality = scene_quality_report(
        scene,
        intent_mode=str(model_meta.get("intent_mode") or "TECHNICAL_DRAFT"),
    )
    summary = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": scene.schema_version,
        "title": scene.title,
        "units": scene.units,
        "refinement": refinement,
        "prompt_chars": len(prompt),
        "reference_chars": len(reference_notes),
        "sketch_present": bool(image_path),
        "image_name": image_name,
        "image_size": image_size,
        "entity_counts": _entity_counts(scene),
        "quality": quality,
        "source": model_meta.get("source", "demo_fallback"),
        "model": model_meta.get("model"),
        "intent_mode": model_meta.get("intent_mode"),
        "model_max_tokens": model_meta.get("max_tokens"),
        "model_latency_ms": model_meta.get("latency_ms"),
        "total_runtime_ms": int((time.monotonic() - started) * 1000),
        "usage": model_meta.get("usage", {}),
        "fallback_reason": model_meta.get("reason"),
        "artifacts": {"dxf": dxf_path.name, "svg": svg_path.name, "scene_json": scene_path.name},
    }
    write_run_log(summary)

    source = summary["source"]
    if source == "model":
        source_line = "✅ **Model-generated scene** — validated before SVG and DXF export."
    elif source == "preserved_scene":
        source_line = "⚠️ **Refinement was not applied.** The previous validated scene was preserved."
    else:
        source_line = "⚠️ **Local demo fallback.** This geometry was not generated from the uploaded image."
    status_lines = [
        source_line,
        f"Run `{run_id}` · DrawingScene `{scene.schema_version}` · `{scene.units}`",
        f"Downloads: `{dxf_path.name}` + `{scene_path.name}`",
        REFERENCE_NOTE,
    ]
    if summary.get("model"):
        status_lines.append(f"Model: `{summary['model']}`")
    if summary.get("fallback_reason"):
        status_lines.append(f"Reason: `{summary['fallback_reason']}`")
    if quality["status"] != "pass":
        status_lines.append("Depth check: " + "; ".join(quality["issues"]))
    return (
        svg_markup,
        str(dxf_path),
        str(scene_path),
        json.dumps(summary, indent=2),
        "\n\n".join(status_lines),
        scene_to_dict(scene),
    )


def generate_drawing(
    prompt: str,
    sketch_image: str | None,
    reference_notes: str,
    units: str,
) -> tuple[str, str, str, str, str, dict[str, Any]]:
    started = time.monotonic()
    prompt = (prompt or "").strip()[:MAX_PROMPT_CHARS]
    reference_notes = (reference_notes or "").strip()[:MAX_REFERENCE_CHARS]
    scene, model_meta = request_model_scene(prompt, reference_notes, units, sketch_image)
    if scene is None:
        if OPENROUTER_API_KEY:
            raise gr.Error(f"Model generation failed before a valid drawing was produced: {model_meta.get('reason', 'unknown error')}")
        scene = build_fallback_scene(prompt, units)
    return _finish_run(
        scene,
        model_meta,
        prompt=prompt,
        reference_notes=reference_notes,
        image_path=sketch_image,
        started=started,
        refinement=False,
    )


def refine_drawing(
    refinement_prompt: str,
    units: str,
    prior_scene: dict[str, Any] | None,
) -> tuple[str, str, str, str, str, dict[str, Any]]:
    started = time.monotonic()
    refinement_prompt = (refinement_prompt or "").strip()[:MAX_REFINEMENT_CHARS]
    if not prior_scene:
        scene = build_fallback_scene("Create a drawing before refining", units)
        meta = {"source": "demo_fallback", "reason": "No prior scene exists"}
    else:
        previous = scene_from_payload(prior_scene, requested_units=units)
        scene, meta = request_model_scene(refinement_prompt, "", units, None, prior_scene)
        if scene is None:
            scene = previous
            meta = {**meta, "source": "preserved_scene"}
    return _finish_run(
        scene,
        meta,
        prompt=refinement_prompt,
        reference_notes="",
        image_path=None,
        started=started,
        refinement=True,
    )


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="NaturalCAD 2D") as demo:
        scene_state = gr.State(value=None)
        gr.Markdown(
            """
            # NaturalCAD 2D
            Generate a structured 2D drafting scene from text, a sketch, or both—then refine and export it.

            **Prototype scope:** technical details and conceptual 2D drawings with layered linework, dimensions, notes, and material or shadow hatches.

            More reference dimensions = more accurate output.
            """
        )
        with gr.Row():
            with gr.Column(scale=1, min_width=340):
                prompt = gr.Textbox(
                    label="Describe the drawing",
                    placeholder="Describe a detail, section, diagram, object, staircase, linework hierarchy, materials, hatches, and dimensions...",
                    lines=5,
                    max_length=MAX_PROMPT_CHARS,
                )
                sketch_image = gr.Image(type="filepath", label="Sketch image (optional)")
                reference_notes = gr.Textbox(
                    label="Reference dimensions or notes",
                    placeholder="Overall width 180 mm; slots 32 x 10 mm; centers 120 mm apart",
                    lines=4,
                    max_length=MAX_REFERENCE_CHARS,
                )
                units = gr.Dropdown(choices=list(UNIT_MAP.keys()), value="mm", label="Units")
                generate = gr.Button("Generate drawing", variant="primary")
                gr.Examples(examples=EXAMPLE_PROMPTS, inputs=prompt)
                gr.Markdown("---\n### Refine the current drawing")
                refinement_prompt = gr.Textbox(
                    label="Requested change",
                    placeholder="Make both slots 36 mm long and move them 10 mm farther apart",
                    lines=3,
                    max_length=MAX_REFINEMENT_CHARS,
                )
                refine = gr.Button("Apply refinement")
            with gr.Column(scale=1, min_width=420):
                preview = gr.HTML(label="Validated preview")
                with gr.Row():
                    dxf_file = gr.File(label="DXF")
                    scene_file = gr.File(label="DrawingScene JSON")
                status = gr.Markdown()
                scene_summary = gr.Code(label="Run summary", language="json", lines=12)

        outputs = [preview, dxf_file, scene_file, scene_summary, status, scene_state]
        generate.click(
            fn=generate_drawing,
            inputs=[prompt, sketch_image, reference_notes, units],
            outputs=outputs,
        )
        refine.click(
            fn=refine_drawing,
            inputs=[refinement_prompt, units, scene_state],
            outputs=outputs,
        )
    return demo


def launch_app(demo: gr.Blocks) -> None:
    port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
    demo.queue(max_size=24, default_concurrency_limit=2).launch(
        server_name="0.0.0.0",
        server_port=port,
        theme=APP_THEME,
        max_file_size="10mb",
    )


if __name__ == "__main__":
    launch_app(build_ui())
