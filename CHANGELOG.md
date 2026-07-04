# Changelog — Backend API

## [1.0.0] — 2026-06-23 · First Stable Release

### New Endpoints

- **POST `/v1/scenario/{scenario_id}/policy_draft`** — Generates a formal policy draft for the given scenario by aggregating completed trainee assignments and calling the LLM service. Trainer self-test runs are excluded from the performance data.
- **GET `/v1/scenario/trainer/stats`** — Returns all scenarios created by the authenticated trainer with pre-computed statistics: total runs and unique trainees (trainer's own runs excluded).
- **GET `/v1/assignment/analytics/threat`** — Multi-dimension threat performance analytics aggregated across all assignments for the current user.

### Improvements

- Step evaluation replaced with LLM-based grading via `ClientLLM.grade_step`, providing qualitative feedback alongside a numeric score.
- `ClientLLM.get_policy_draft` proxy added for LLM service communication.
- `ScenarioWithStatsResponse` schema added to carry run and trainee counts to the frontend.
- MongoDB aggregation pipeline used for efficient stats computation (avoids N+1 queries).

### Bug Fixes

- Duplicate user records resolved: returning users are now matched by `auth_provider_id` regardless of legacy field names.
