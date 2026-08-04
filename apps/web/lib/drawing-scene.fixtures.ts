/**
 * Golden DrawingScene 1.0 fixtures, captured from the authoritative Python
 * implementation (apps/gradio-demo/app/drawing_core.py, build_fallback_scene +
 * scene_to_json). These are raw wire payloads (snake_case keys, as emitted by
 * the backend) — the exact shape the TS validator must accept.
 *
 * Re-generate with:
 *   .venv/bin/python -c 'import sys; sys.path.insert(0,"apps/gradio-demo/app");
 *   from drawing_core import build_fallback_scene, scene_to_json;
 *   print(scene_to_json(build_fallback_scene(PROMPT, "mm")))'
 */

export const PLATE_SCENE: unknown = {
  "title": "NaturalCAD 2D Demo",
  "units": "mm",
  "schema_version": "1.0",
  "coordinate_system": "XY_RIGHT_HANDED",
  "layers": [
    {
      "name": "GEOMETRY",
      "color": 7,
      "linetype": "CONTINUOUS"
    },
    {
      "name": "CENTER",
      "color": 4,
      "linetype": "CENTER"
    },
    {
      "name": "HATCH",
      "color": 8,
      "linetype": "CONTINUOUS"
    },
    {
      "name": "DIMENSIONS",
      "color": 2,
      "linetype": "CONTINUOUS"
    },
    {
      "name": "TEXT",
      "color": 3,
      "linetype": "CONTINUOUS"
    },
    {
      "name": "ANNOTATION",
      "color": 6,
      "linetype": "CONTINUOUS"
    }
  ],
  "polylines": [
    {
      "id": "outline",
      "points": [
        [
          -90.0,
          -45.0
        ],
        [
          90.0,
          -45.0
        ],
        [
          90.0,
          45.0
        ],
        [
          -90.0,
          45.0
        ]
      ],
      "layer": "GEOMETRY",
      "closed": true
    },
    {
      "id": "horizontal_centerline",
      "points": [
        [
          -110.0,
          0
        ],
        [
          110.0,
          0
        ]
      ],
      "layer": "CENTER",
      "closed": false
    }
  ],
  "circles": [
    {
      "id": "hole_001",
      "center": [
        -76.5,
        -31.5
      ],
      "radius": 6.0,
      "layer": "GEOMETRY"
    },
    {
      "id": "hole_002",
      "center": [
        76.5,
        -31.5
      ],
      "radius": 6.0,
      "layer": "GEOMETRY"
    },
    {
      "id": "hole_003",
      "center": [
        76.5,
        31.5
      ],
      "radius": 6.0,
      "layer": "GEOMETRY"
    },
    {
      "id": "hole_004",
      "center": [
        -76.5,
        31.5
      ],
      "radius": 6.0,
      "layer": "GEOMETRY"
    }
  ],
  "arcs": [],
  "slots": [],
  "hatches": [
    {
      "id": "body_hatch",
      "boundary": [
        [
          -90.0,
          -45.0
        ],
        [
          90.0,
          -45.0
        ],
        [
          90.0,
          45.0
        ],
        [
          -90.0,
          45.0
        ]
      ],
      "layer": "HATCH",
      "pattern": "SOLID"
    }
  ],
  "texts": [
    {
      "id": "drawing_title",
      "text": "Steel mounting plate 180x90 mm with four 12 mm corner holes and center label",
      "insert": [
        -90.0,
        67.0
      ],
      "height": 4.5,
      "layer": "TEXT"
    }
  ],
  "dimensions": [
    {
      "id": "overall_width",
      "start": [
        -90.0,
        -45.0
      ],
      "end": [
        90.0,
        -45.0
      ],
      "offset": 20.0,
      "layer": "DIMENSIONS",
      "angle": 0.0,
      "text": "180 mm"
    },
    {
      "id": "overall_height",
      "start": [
        90.0,
        -45.0
      ],
      "end": [
        90.0,
        45.0
      ],
      "offset": 22.0,
      "layer": "DIMENSIONS",
      "angle": 90.0,
      "text": "90 mm"
    }
  ],
  "leaders": [
    {
      "id": "accuracy_note",
      "points": [
        [
          76.5,
          31.5
        ],
        [
          108.0,
          63.0
        ]
      ],
      "text": "More reference dimensions = more accurate output.",
      "text_height": 3.1500000000000004,
      "layer": "ANNOTATION"
    }
  ]
};

export const SLOT_SCENE: unknown = {
  "title": "NaturalCAD 2D Demo",
  "units": "mm",
  "schema_version": "1.0",
  "coordinate_system": "XY_RIGHT_HANDED",
  "layers": [
    {
      "name": "GEOMETRY",
      "color": 7,
      "linetype": "CONTINUOUS"
    },
    {
      "name": "CENTER",
      "color": 4,
      "linetype": "CENTER"
    },
    {
      "name": "HATCH",
      "color": 8,
      "linetype": "CONTINUOUS"
    },
    {
      "name": "DIMENSIONS",
      "color": 2,
      "linetype": "CONTINUOUS"
    },
    {
      "name": "TEXT",
      "color": 3,
      "linetype": "CONTINUOUS"
    },
    {
      "name": "ANNOTATION",
      "color": 6,
      "linetype": "CONTINUOUS"
    }
  ],
  "polylines": [
    {
      "id": "outline",
      "points": [
        [
          -90.0,
          -45.0
        ],
        [
          90.0,
          -45.0
        ],
        [
          90.0,
          45.0
        ],
        [
          -90.0,
          45.0
        ]
      ],
      "layer": "GEOMETRY",
      "closed": true
    },
    {
      "id": "horizontal_centerline",
      "points": [
        [
          -110.0,
          0
        ],
        [
          110.0,
          0
        ]
      ],
      "layer": "CENTER",
      "closed": false
    }
  ],
  "circles": [],
  "arcs": [],
  "slots": [
    {
      "id": "slot_001",
      "center": [
        -30.0,
        0.0
      ],
      "length": 28.8,
      "width": 14.0,
      "angle": 0.0,
      "layer": "GEOMETRY"
    },
    {
      "id": "slot_002",
      "center": [
        30.0,
        0.0
      ],
      "length": 28.8,
      "width": 14.0,
      "angle": 0.0,
      "layer": "GEOMETRY"
    }
  ],
  "hatches": [
    {
      "id": "body_hatch",
      "boundary": [
        [
          -90.0,
          -45.0
        ],
        [
          90.0,
          -45.0
        ],
        [
          90.0,
          45.0
        ],
        [
          -90.0,
          45.0
        ]
      ],
      "layer": "HATCH",
      "pattern": "SOLID"
    }
  ],
  "texts": [
    {
      "id": "drawing_title",
      "text": "Wall bracket 180x90 mm with two 32x10 mm slots, centerline, and dimensions",
      "insert": [
        -90.0,
        67.0
      ],
      "height": 4.5,
      "layer": "TEXT"
    }
  ],
  "dimensions": [
    {
      "id": "overall_width",
      "start": [
        -90.0,
        -45.0
      ],
      "end": [
        90.0,
        -45.0
      ],
      "offset": 20.0,
      "layer": "DIMENSIONS",
      "angle": 0.0,
      "text": "180 mm"
    },
    {
      "id": "overall_height",
      "start": [
        90.0,
        -45.0
      ],
      "end": [
        90.0,
        45.0
      ],
      "offset": 22.0,
      "layer": "DIMENSIONS",
      "angle": 90.0,
      "text": "90 mm"
    }
  ],
  "leaders": [
    {
      "id": "accuracy_note",
      "points": [
        [
          76.5,
          31.5
        ],
        [
          108.0,
          63.0
        ]
      ],
      "text": "More reference dimensions = more accurate output.",
      "text_height": 3.1500000000000004,
      "layer": "ANNOTATION"
    }
  ]
};
