# Validation report — Oryven 0.10.0

## Automated backend

- pytest: 105 passed
- compileall backend/oryven: passed
- smoke: 32 professional agents
- smoke: 41 skills
- smoke: universal operator skills present in professional plan

## Frontend

`npm run build` could not be validated in this environment because dependencies were not installed. An attempted `npm install --no-audit --no-fund` exceeded the execution window. Any partial `node_modules`, `dist` and TypeScript build cache were removed before packaging.

Required local gate:

```powershell
cd web
npm install
npm run build
```

## Windows E2E still required

See `RELEASE_0_10_0_UNIVERSAL_COMPUTER_OPERATOR.md` for the 10 Windows validation cases.
