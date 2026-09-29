# Instructions for coding agents working on this project

Read README.md, DEVELOPMENT.md and VERIFICATION.md before changing the implementation.

This repository is a general runtime software-generation agent. Do not include task-specific
application code, fixed answers, business components, seed databases, downloaded application
artifacts or the sibling arcbench-v0 demo in the competition package or agent context.
The agent must actually invoke the configured model and implement supplied requirements at runtime.

Keep the official CLI: main.py REQUIREMENTS_DIR --output-dir OUTPUT_DIR. Preserve nonzero exits
on failure. Official deployment uses frontend/package.json build and backend/package.json start,
listening on HOST=0.0.0.0 PORT=3000. Do not replace it with the local-only deploy.sh shortcut.

Never display .env values, credentials, Authorization headers or private account cookies.
Configuration lives in a local ignored .env. env.example must contain no real key.
Do not read hidden tests or evaluation infrastructure, alter the official evaluator, or weaken
assertions to manufacture success. Public requirement-based tests are allowed.

File tools constrain paths but generated npm code is not sandboxed by Python. Execute real
application generation and build only in the official isolated Linux Runner, not on the user's host.
Do not mount unrelated host directories. Don't auto-submit a paid official evaluation or publish
the repository unless the user authorizes that action.

Use evidence-specific descriptions: offline unit tests, model connectivity, application build,
public Playwright results and official scores are different. Never infer one from another.
Before changing API limits or models, inspect actual usage evidence and document cost tradeoffs.

For behavior changes run relevant unittest tests; for entry/package changes verify ZIP root files.
If you add a runtime module, update package_agent.FILES explicitly and its archive test.
Keep the archive allowlist: never use a recursive ZIP of the whole development folder.
Do not overwrite another team member's uncommitted changes. Use short branches and reviewable commits.
