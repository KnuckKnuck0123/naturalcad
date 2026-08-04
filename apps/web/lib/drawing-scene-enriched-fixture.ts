export const ENRICHED_RECT_SCENE: unknown = {
  "title": "Generated 2D profile",
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
      "id": "poly_001",
      "points": [
        [
          50.0,
          -30.0
        ],
        [
          -50.0,
          -30.0
        ],
        [
          -50.0,
          30.0
        ],
        [
          50.0,
          30.0
        ]
      ],
      "layer": "GEOMETRY",
      "closed": true
    },
    {
      "id": "cl_vertical",
      "points": [
        [
          0,
          -40.0
        ],
        [
          0,
          40.0
        ]
      ],
      "layer": "CENTER",
      "closed": false
    },
    {
      "id": "cl_horizontal",
      "points": [
        [
          -60.0,
          0
        ],
        [
          60.0,
          0
        ]
      ],
      "layer": "CENTER",
      "closed": false
    }
  ],
  "circles": [
    {
      "id": "circle_001",
      "center": [
        0.0,
        0.0
      ],
      "radius": 10.0,
      "layer": "GEOMETRY"
    }
  ],
  "arcs": [],
  "slots": [],
  "hatches": [
    {
      "id": "hatch_001",
      "boundary": [
        [
          50.0,
          -30.0
        ],
        [
          -50.0,
          -30.0
        ],
        [
          -50.0,
          30.0
        ],
        [
          50.0,
          30.0
        ]
      ],
      "layer": "HATCH",
      "pattern": "SOLID"
    }
  ],
  "texts": [],
  "dimensions": [
    {
      "id": "dim_width",
      "start": [
        -50.0,
        -30.0
      ],
      "end": [
        50.0,
        -30.0
      ],
      "offset": 15.0,
      "layer": "DIMENSIONS",
      "angle": 0.0,
      "text": "100 mm"
    },
    {
      "id": "dim_height",
      "start": [
        50.0,
        -30.0
      ],
      "end": [
        50.0,
        30.0
      ],
      "offset": 25.0,
      "layer": "DIMENSIONS",
      "angle": 90.0,
      "text": "60 mm"
    }
  ],
  "leaders": [],
  "reference_note": ""
};
