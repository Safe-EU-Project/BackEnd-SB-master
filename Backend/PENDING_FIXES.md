# Backend Pending Fixes
## Context for new chat session

This file contains all remaining issues to fix in `Backend/src`.
The codebase is a FastAPI + Beanie (MongoDB) + Keycloak auth backend.

---

## DEFERRED (decided to do later)

### D1 — ML model reloaded every grading call
- **File:** `src/assignment/assignment_utils.py` line 15
- **Problem:** `SentenceTransformer("all-MiniLM-L6-v2")` is created inside `evaluate_answer()` on every call. Should be a module-level singleton.
- **Fix:** Move `model = SentenceTransformer(...)` to module level (outside the function).

### D2 — No auth on scenario GET endpoints
- **File:** `src/scenario/routes.py` lines 22-38
- **Problem:** `GET /` and `GET /{scenario_id}` have no `Depends(get_current_user)` — anyone can list/fetch all scenarios.
- **Fix:** Add `user_token=Depends(get_current_user), _=Depends(get_user_role("trainer"))` to both routes.

### D3 — `UnboundLocalError` in `extract_hour_title_description_per_incident`
- **File:** `src/scenario/service.py` ~line 265
- **Problem:** `time` and `title` only assigned inside `if match:` but returned unconditionally. If regex doesn't match → `UnboundLocalError`.
- **Fix:** Flip to `if not match: raise ValueError(...)` then assign unconditionally.

### D4 — `IndexError` in `split_initial_response`
- **File:** `src/scenario/service.py` ~line 220
- **Problem:** `incidents_expected_actions[1]` crashes if LLM output doesn't contain the delimiter `'Expected Actions & Decision Points'`.
- **Fix:** Check `len(parts) < 2` after split and raise a clear `ValueError`.

---

## PENDING (not yet started)

### P1 — Any trainer can grade any assignment (IDOR) — HIGH
- **File:** `src/assignment/service.py` lines 56-71 (`update_assignment_score`)
- **Problem:** Updates grade by `assignment_data.id` only. No check that the assignment's scenario belongs to the calling trainer.
- **Fix:** After finding the assignment, fetch its scenario and verify `scenario.user.id == trainer.id`. Raise 403 if not.

### P2 — Trainee can see other users' grades (IDOR) — HIGH
- **File:** `src/assignment/service.py` lines 227-314 (`analytics_for_specific_assignment`)
- **Problem:** No check that `assignment_id` belongs to the requesting trainee. Anyone can pass another user's assignment ID and get back their grades.
- **Fix:** After loading `current_assignment`, check `current_assignment.trainee.id == user.id`. Raise 403 if not.

### P3 — Completed assignments can be re-submitted — HIGH
- **File:** `src/assignment/service.py` ~line 88 (`solve_assignment`)
- **Problem:** No check that `current_assignment.status == "assigned"` before grading. Trainees can overwrite their grade by submitting again.
- **Fix:** Add check: `if current_assignment.status == "completed": raise HTTPException(400, "Assignment already submitted")`.

### P4 — Exception details leaked in auth routes — HIGH
- **File:** `src/user/routes.py` lines ~50, ~65, ~80, ~100
- **Problem:** `login`, `refresh`, `logout`, `/me` return `detail=f"... {str(e)}"`. Keycloak internals exposed to clients.
- **Fix:** Return generic messages like `"Authentication failed"` or `"Could not refresh token"`. Log the real error with `logger.error`.

### P5 — `average_analytics_per_user` exposes all users' data — MEDIUM
- **File:** `src/assignment/service.py` lines 178-225
- **Problem:** Pipeline aggregates ALL trainees' stats. Every trainee sees every other trainee's email, average grade, and assignment count. Also if current user has no completed assignments, they may not appear in results at all.
- **Fix (option A):** Add `"trainee.$id": user.id` to `$match` to scope to current user only.
- **Fix (option B):** Keep leaderboard but anonymize emails (replace with hashed ID for non-"me" rows).

### P6 — LLM `answer` key missing causes KeyError — MEDIUM
- **File:** `src/scenario/client_llm.py` line ~58
- **Problem:** `result["answer"]` crashes if LLM returns 200 but with different JSON shape.
- **Fix:** Use `result.get("answer")` and raise a clear error if None/missing.

### P7 — No duplicate assignment prevention — MEDIUM
- **File:** `src/assignment/service.py` `create_assignment`
- **Problem:** A trainee can create multiple assignments for the same scenario. No `(scenario, trainee)` uniqueness check.
- **Fix (option A):** Check `await Assignment.find_one(Assignment.scenario.id == ..., Assignment.trainee.id == ..., Assignment.status == "assigned")` before creating.
- **Fix (option B):** Add compound index on `(scenario.$id, trainee.$id)`.

### P8 — `optimal`/`suboptimal` never populated — MEDIUM
- **File:** `src/scenario/service.py` `handle_expected_actions` ~line 279
- **Problem:** `optimal, sub_optimal = None, None` always returned. The LLM parsing for optimal/suboptimal path is not implemented. `Scenario.optimal` and `Scenario.suboptimal` are always `None`.
- **Fix:** Implement parsing using `optimal_key` and `sub_optimal_key` params that are already in the method signature but unused.

### P9 — `updated_at` never updates on PATCH — MEDIUM
- **File:** `src/scenario/service.py` + `src/db/models.py`
- **Problem:** `update_scenario_incidents` uses `await scenario_to_update.set(...)` which is a partial update, not a replace. `@before_event(Replace)` never fires → `updated_at` stays at creation time.
- **Fix:** After `set()`, manually update: `await scenario_to_update.set({Scenario.updated_at: datetime.now(timezone.utc)})`.

### P10 — `status` field accepts any string — LOW
- **File:** `src/assignment/schemas.py` line 19 (`GetAssignmentWithStatus`)
- **Problem:** `status: str` — passing `"xyz"` returns empty results instead of 400.
- **Fix:** Change to `status: Literal["assigned", "completed"]`.

### P11 — DELETE returns 200 instead of 204 — LOW
- **File:** `src/scenario/routes.py` line ~70
- **Problem:** `delete_scenario` returns empty 200. REST convention is 204 No Content.
- **Fix:** Add `status_code=204` to the route decorator: `@scenario_router.delete("/{scenario_id}", status_code=204)`.

### P12 — Duplicate log lines — LOW
- **File:** `src/scenario/logger.py`
- **Problem:** `logger.propagate` not set to `False`. If root logger is also configured, every log message is written twice.
- **Fix:** Add `logger.propagate = False` after creating the logger.

### P13 — `strict_audience` config field never used — LOW
- **File:** `src/user/config.py` + `src/user/service.py`
- **Problem:** `strict_audience: bool = False` is defined in `Settings` but never read in `verify_token`.
- **Fix (option A):** Read it: `"verify_aud": settings.strict_audience` in the jwt.decode options.
- **Fix (option B):** Remove the field entirely if not needed.

### P14 — `except Exception` swallows 500s as 401 — LOW
- **File:** `src/user/dependencies.py` lines 35-38
- **Problem:** `except Exception` after `verify_token` also catches `HTTPException`, turning a 500 into a generic 401. Hides real server errors.
- **Fix:** Change to `except HTTPException: raise` first, then `except Exception` for the fallback.

### P15 — Invalid ObjectId → 500 instead of 400 — LOW
- **Files:** `assignment/service.py` lines 27, 88, 235; `scenario/service.py` lines ~32, ~71 etc.
- **Problem:** `ObjectId("invalid-string")` raises `bson.errors.InvalidId` which becomes an unhandled 500.
- **Fix:** Wrap ObjectId calls in try/except:
  ```python
  try:
      oid = ObjectId(some_id)
  except Exception:
      raise HTTPException(status_code=400, detail="Invalid ID format")
  ```

---

## Files changed so far (for reference)
- `src/assignment/service.py`
- `src/assignment/routes.py`
- `src/assignment/schemas.py`
- `src/assignment/assignment_utils.py` (not yet)
- `src/scenario/service.py`
- `src/scenario/routes.py`
- `src/scenario/schemas.py`
- `src/scenario/client_llm.py`
- `src/user/service.py`
- `src/user/dependencies.py`
- `src/user/config.py`
- `src/db/main.py`
- `src/db/models.py`
- `Backend/.env`
