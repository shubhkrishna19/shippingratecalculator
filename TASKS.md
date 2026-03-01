# Tasks — ShippingRateCalculator

## Protocol
Before claiming a task: read AGENTS.md + COORDINATION.md (in BluewudOrchestrator/).
Claim a task by moving it to IN PROGRESS with your agent tag [CLAUDE]/[CODEX-XX]/[MINIMAX]/[OPENCLAW].
Always work on a branch: feat/[agent]-T[id]-[slug]. Never commit directly to main.

## PENDING
- [ ] [T-001] Add validation for invalid/non-existent pincodes with clear error response (Priority: HIGH)
- [ ] [T-002] Add weight input validation (reject negative weights, zero, >70kg) (Priority: HIGH)
- [ ] [T-003] Cache pincode lookup results in memory to reduce CSV reads on repeated requests (Priority: MED)
- [ ] [T-004] Add API endpoint documentation (Swagger/OpenAPI) (Priority: LOW)
- [ ] [T-005] Add logging for each rate calculation request (carrier, weight, pincode, result) (Priority: LOW)

## IN PROGRESS
(none)

## DONE
(none yet — project initialized)
