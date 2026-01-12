# Meta prompt: Generate PRD.jsonc + PROMPT.md from a narrative plan

You are an AI agent. You will be given only a narrative describing a plan. The PRD.jsonc and PROMPT.md templates are embedded below and must be used as the basis for your outputs.

Your job is to turn the narrative into a complete, concrete PRD.jsonc and PROMPT.md for an implementation agent. Before writing outputs, you must carefully reason through the plan, identify conceptual issues, missing details, assumptions, risks, or contradictions, and ask focused follow-up questions to resolve them. Do not produce final PRD.jsonc/PROMPT.md until the open issues are answered.

## PRD.jsonc template (schema + example shape)
```jsonc
{
  "title": "Some plan",
  "status": "in-progress",
  "goals": [
    "List of things to achieve"
  ],
  "non_goals": [
    "Restrictions, caveats",
    "No refactors or behavior changes beyond mechanical moves and toolchain alignment."
  ],
  "steps": [
    {
      "id": "step-1-preparation",
      "title": "Prepare for the plan",
      "status": "done",
      "tasks": [
        "Some tasks"
      ]
    },
    {
      "id": "step-2-do-the-work",
      "title": "Work man",
      "status": "planned",
      "tasks": [
        "Scan packages/cf-webrtc for internal workspace deps (for example: @hyper-lite/logging, @hyper-lite/ui, @hyper-lite/ts-config) and list everything that must move with the subsystem.",
        "Collect all catalog entries used by cf-webrtc and the supporting packages so the new repo can reuse the same version map."
      ],
      "validation": [
        {
          "id": "Manual browser tests",
          "type": "browser-testing",
          "instructions": [
            "Start a dev server with `just run`",
            "Use claude-in-chrome mcp to control the browser and check if the functionality works"
          ],
          "expected": "Dependencies install without errors."
        }
      ]
    }
  ],
  "global_validation": [
    {
      "id": "Manual browser tests",
      "type": "browser-testing",
      "instructions": [
        "Start a dev server with `just run`",
        "Use claude-in-chrome mcp to control the browser and check if the functionality works"
      ],
      "expected": "Dependencies install without errors."
    },
    {
      "id": "lint",
      "type": "automated",
      "instructions": [
        "just lint"
      ],
      "expected": "No lint errors across packages."
    },
    {
      "id": "build",
      "type": "automated",
      "instructions": [
        "just build"
      ],
      "expected": "Build completes without errors."
    }
  ]
}
```
Schema notes: top-level `status` and per-step `status` must be one of `planned`, `in-progress`, `done`, or `blocked`. Each entry in `steps` is a phase, and each phase uses a `tasks` array (strings) plus optional `validation`.

## PROMPT.md template (structure)
```md
@PRD.jsonc

## Task
- Find the first phase with "status": "planned".
- Implement all tasks for that phase according to "tasks". Follow those tasks precisely.
- Run the phase's listed validation instructions and any lightweight `global_validation` checks that make sense at this point.
- Update the phase status to "done" once complete.
- Append progress notes to `PROGRESS.md` (include what was done, what remains, any blockers, and any additional observations that might be important for follow up work).
- Commit all changes with a concise conventional-commit style message.

If while implementing the steps you find that the prd is complete, output <CLAUDE>DONE</CLAUDE>. NEVER output DONE when there are phases with status "planned" remaining!

If while implementing the steps you run into an issue you cannot resolve or find conceptual problems with the plan, output <CLAUDE>BLOCKED: [explanation]</CLAUDE>.

## Context, scope and intent
- Some narrative about the why
- What to change
- What the outcome should be, high-level

## Workflow expectations
- Follow the phase steps exactly; do not implement future phases early.
- ...

## Tests and validation
- Prefer the phase's listed commands/tests.
- If a test can't be run, explain why and provide manual verification steps.
- Keep tests lightweight and scoped to the current phase.

## Dev environment
- If tools are missing, you may need a Nix dev shell (`nix develop`).
- ...

## Constraints
- Keep changes scoped to the current phase. DO NOT IMPLEMENT other phases.
- Don't remove or alter unrelated code.
- Prefer small, clear changes; avoid introducing new dependencies unless required.

## Progress

@PROGRESS.md
```

## Your workflow
1. Read the narrative and extract the plan's goals, non-goals, constraints, dependencies, and expected outcomes.
2. Identify conceptual issues, missing details, dependencies, risks, or contradictions that would block a precise PRD or an implementation agent.
3. Ask follow-up questions, grouped by theme, and wait for answers. Do not draft final outputs while critical issues remain.
4. Once all issues are resolved, produce:
   - `PRD.jsonc` matching the schema and tailored to the plan.
   - `PROMPT.md` tailored to the plan and aligned with the PRD.

## Output rules
- When asking questions, output only the questions.
- When providing final outputs, write two files:
  - `PRD.jsonc`
  - `PROMPT.md`
- Use concrete, actionable tasks. Avoid vague verbs.
- Ensure the PRD's `steps` are ordered, status values are valid, and validations are realistic.
- Keep steps small and simple. Err on the side of more steps if needed.
- Keep the PROMPT's "Task" section aligned with the PRD (phase-by-phase execution).

## Narrative
