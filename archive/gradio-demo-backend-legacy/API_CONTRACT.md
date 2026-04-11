# API Contract Sketch

## POST `/v1/generate-spec`

Request:

```json
{
  "prompt": "make a heavy steel bracket with 4 bolt holes",
  "mode": "part",
  "output_type": "3d_solid",
  "session_id": "optional-client-session"
}
```

Response:

```json
{
  "ok": true,
  "cached": false,
  "prompt_hash": "8a41b50d23f1b3de",
  "spec": {
    "output_type": "3d_solid",
    "geometry_family": "bracket_plate",
    "units": "mm",
    "parameters": {
      "width": 80,
      "height": 50,
      "thickness": 6,
      "hole_count": 4,
      "hole_diameter": 10
    },
    "style": {
      "family": "industrial",
      "heaviness": 0.8
    }
  },
  "notes": [
    "This is a scaffolded template/spec response.",
    "Next step: route this through an actual HF model endpoint."
  ],
  "model": "stub/template-router"
}
```

## GET `/v1/health`
Simple health check for the Space.

## Intended evolution
- add actual HF endpoint call inside `generate_spec`
- keep prompt normalization, caching, and rate limiting in this backend
- convert returned JSON spec into build123d code inside the Gradio app
