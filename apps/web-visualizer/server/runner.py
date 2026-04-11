#!/usr/bin/env python3
"""Simple build123d runner with STL and STEP export."""

from __future__ import annotations

import argparse
import pathlib
import sys
import traceback


def coerce_shape(candidate):
    """Try to pull an exportable shape from the user namespace."""
    if candidate is None:
        return None

    if hasattr(candidate, "wrapped"):
        return candidate

    for attr in ("part", "shape", "solid", "obj"):
        value = getattr(candidate, attr, None)
        if value is not None and not callable(value):
            candidate = value
            if hasattr(candidate, "wrapped"):
                return candidate
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description="Run build123d code and export artifacts")
    parser.add_argument("--source", required=True, help="Path to user code file")
    parser.add_argument("--stl-output", required=True, help="Path for the STL output")
    parser.add_argument("--step-output", required=False, help="Path for the STEP output")
    args = parser.parse_args()

    source_path = pathlib.Path(args.source)
    stl_output_path = pathlib.Path(args.stl_output)
    step_output_path = pathlib.Path(args.step_output) if args.step_output else None
    stl_output_path.parent.mkdir(parents=True, exist_ok=True)
    if step_output_path:
        step_output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        code = source_path.read_text()
    except OSError as exc:
        print(f"Failed to read code: {exc}", file=sys.stderr)
        return 1

    user_globals: dict[str, object] = {}
    try:
        exec(compile(code, str(source_path), "exec"), user_globals)
    except Exception as exec_error:  # noqa: BLE001
        print("Execution error:", file=sys.stderr)
        traceback.print_exception(exec_error, file=sys.stderr)
        return 1

    candidate = user_globals.get("result")
    candidate = coerce_shape(candidate)

    if candidate is None:
        print("No `result` geometry found after execution.", file=sys.stderr)
        return 2

    try:
        from build123d import export_stl, export_step
    except Exception as exc:  # noqa: BLE001
        print(f"Unable to import build123d exporters: {exc}", file=sys.stderr)
        return 3

    try:
        export_stl(candidate, str(stl_output_path))
        print(f"STL exported to {stl_output_path}")
        if step_output_path:
            export_step(candidate, str(step_output_path))
            print(f"STEP exported to {step_output_path}")
    except Exception as export_error:  # noqa: BLE001
        print("Export failed:", file=sys.stderr)
        traceback.print_exception(export_error, file=sys.stderr)
        return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
