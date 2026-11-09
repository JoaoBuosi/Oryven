# Oryven 0.19 Paid Pilot — Real User Test Plan

## Cohort
Start with 5–10 invited users on Windows 10/11. Expand to 10–20 only after the first cohort completes the acceptance flows without blocking defects.

## Required flows per participant
1. Install and launch Oryven without developer tooling.
2. Create/verify account, accept pilot terms/privacy and activate pilot license.
3. Complete onboarding and create/select a project.
4. Complete at least one official Functional MVP flow.
5. Review an Authorization card and understand target/impact before approval.
6. Open Mission Intelligence/evidence after the run.
7. Exercise Emergency Stop once in a safe test mission.
8. Export user data.
9. Submit in-app feedback.
10. Restart Windows/application and confirm session/preferences persist.

## Success criteria
- >= 90% install/launch success in the target cohort.
- >= 80% complete one supported MVP flow without developer assistance.
- 0 known critical credential/privacy leaks.
- 0 execution actions bypass authorization policy.
- No unresolved blocker causing data loss.
- Median user-reported task clarity >= 4/5.

## Record only minimal metrics
Allowed: version, flow id, high-level status, duration bucket, error class, UI surface.
Do not collect raw prompts, filenames, file contents, screenshots, passwords, tokens, API keys, or chain-of-thought.

## Exit to 1.0 preparation
Pilot evidence must be reviewed, blocker bugs fixed, legal documents finalized, production update/support infrastructure configured, and billing/provider decisions approved.
