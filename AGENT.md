# AGENTS.md

## Purpose

This repository is maintained with AI coding agents.
Work safely, make minimal changes, and verify every modification.

## CodeGraph Usage

Use CodeGraph when it helps you understand the repository structure, locate symbols, inspect dependencies, or estimate the impact of a change.

Prefer CodeGraph for:

1. Finding relevant files, functions, classes, or modules
2. Understanding unfamiliar parts of the codebase
3. Checking callers and callees before modifying shared logic
4. Estimating the impact of changes across the repository
5. Reducing unnecessary full-file reads and token usage

For small, obvious, or localized changes, you may proceed without CodeGraph.

Useful tools:

1. `codegraph_status`
2. `codegraph_files`
3. `codegraph_search`
4. `codegraph_context`
5. `codegraph_callers`
6. `codegraph_callees`
7. `codegraph_impact`

## Before Editing

Before making non-trivial changes:

1. Identify the relevant files and symbols.
2. Understand the affected area.
3. Check dependencies when modifying reused code.
4. Prefer the smallest safe change.
5. Edit only the necessary files.

## Coding Guidelines

Keep changes simple, explicit, and reversible.
Do not rewrite complete modules unless required.
Do not rename public APIs without checking impact.
Do not remove code unless it is clearly unused.
Do not add dependencies unless clearly justified.
Preserve existing project style and naming conventions.

## Testing and Validation

After editing:

1. Run existing tests if available.
2. Run linting or type checks if configured.
3. If no tests exist, describe a manual validation path.
4. Report any command that fails, including the exact error.

## Error Handling

When something fails:

1. State the exact error.
2. Explain the likely cause.
3. Apply the smallest correction.
4. Do not repeat a failed solution without changing the approach.

## Token and Context Discipline

For image processing, follow the per-image subagent workflow in [AGENTS.md](AGENTS.md).

For a library image, start with `python -m backend.agent_worklist --imagen PROJECT ID_OR_EXACT_NAME`.
It returns the saved calibration, scribble pixel counts, mask IDs and pending circles in the latest agent run.
Use the project skill throughout a batch. Review new candidates and their four crossings on native-resolution
crops with surrounding context. Expand to the original field where the crop is ambiguous.
Load full diagnostics only for the relevant image or circle. A resized copy needs its own calibration.

For manually drawn circles in agent mode, read the project's compact worklist first:
`outputs/scribble_research/agent_tasks/circulos-<project_id>.json` for standard project IDs.
LOCO refreshes it after edits, removals, edge marking, diameter runs and Analysis saves.
For offline use or recovery, run `python -m backend.agent_worklist` from the repository root.
Process only the requested entries in `pendientes` using their run ID, geometry ID and native pixel coordinates.
Inspect a crop around the circle on the original photo when marking edges. Use the existing LOCO diameter
method for entries marked `medir`; `registrar` identifies an existing run ready for Analysis.
Entries in `revisar` already have a rejection. Revisit them when the user requests a review.
Use the saved `escalas[image_id]` value and unit per pixel for that image.

Use CodeGraph to reduce unnecessary context usage when repository context is needed.
Read full files only when needed for precise editing or validation.
Prefer targeted symbol-level investigation over broad exploration.

## Final Response Format

End with:

1. Summary of the issue.
2. Files changed.
3. Changes made.
4. Tests or validations run.
5. Risks or follow-up items.
