# Oryven Professional Agent Runtime — 0.8.0

The original Developer Agent is now the technical execution specialist inside a broader
Professional Agent Runtime. Oryven does not create a separate unrestricted executor for every
profession. It selects a professional profile, then uses shared governed skills.

## Design

- `software.engineering` remains the coding specialist and uses the existing Developer Runtime.
- Other profiles cover data, AI/ML, defensive security, office, research, education, marketing,
  sales, customer success, finance, accounting, legal operations, HR, operations, projects,
  product, design, 3D/Maya, audiovisual, e-commerce, logistics, procurement, engineering,
  architecture/BIM, science, healthcare operations, real estate, hospitality and manufacturing.
- Unknown professions use `general.professional` until a dedicated skill pack is installed.
- Agent selection never grants permissions. Side-effecting tools still require Oryven governance.
- High-stakes domains declare explicit boundaries. For example, healthcare operations does not
  autonomously diagnose/prescribe, finance does not move funds, and legal operations does not
  submit legal filings without review.

## API

- `GET /api/agents` lists packaged professional profiles.
- `POST /api/agents/plan` routes an objective to a profile and returns recommended tool families.
- The route is advisory and produces no side effects.

## Next implementation step

Turn the recommended tool families into real skill packs: filesystem, supervised terminal,
Office/document automation, deep Maya integration, browser actions, professional data tools,
then multimodal screen perception. Every executable skill must remain explicit, auditable and
revocable.
