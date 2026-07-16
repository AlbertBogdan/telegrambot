---
name: verify-nutribot
description: Verify the BJU Telegram bot end-to-end before declaring done.
---
# Verification steps
Never declare the task complete based on a successful edit alone.
Verify the way a human reviewer would:

1. uv run pytest tests/domain/test_calculator.py -q
   → all green; covers: no-overage case, single-nutrient overage,
     two-nutrient-overage (carbs absorbs, per confirmed rule),
     three-nutrient overage (fully blocked), zero-remaining edge,
     AND convert_product_to_macros() — normal weight, weight=1,
     a per-100g value of 0, and factor scaling correctness
     (e.g. 150g @ 20/5/30 per 100g → 30/7.5/45 eaten grams).
2. uv run pytest tests/bot/test_formatters.py -q
   → all green; "Сегодня" view renders exceeded-nutrient flags and
     exhaustion message correctly for fixture data.
3. uv run pytest tests/bot/test_onboarding_and_edit.py -q
   → all green; covers valid onboarding, malformed input rejection,
     re-/start on existing user routes to confirmation, edit-norm flow.
4. uv run pytest tests/bot/test_logging_flow.py -q
   → all green; covers: Format A (3-number direct) valid add, Format B
     (4-number weight+per100) valid add with correct conversion,
     wrong token count (not 3 and not 4) rejected with both patterns
     shown, negative Format-A values rejected, Format-B weight<=0
     rejected, Format-B per-100 value of 0 accepted, add blocked
     when kcal_fact already >= kcal_norm regardless of format used.
5. uv run pytest tests/domain/test_rollover.py -q
   → all green; covers pre-06:00 vs post-06:00 Minsk boundary, no
     rollover mid-day, no backfill across multi-day idle gaps.
6. uv run pytest tests/bot/test_calendar.py -q
   → all green; covers empty-month render, marked vs unmarked days,
     tap-on-empty-day handling.
7. uv run ruff check .
   → 0 errors
8. uv run mypy src/
   → 0 errors
9. uv run pytest -q (full suite)
   → all green, no step above skipped

If any step fails: fix the issue and rerun from step 1.
Do not hand back partially verified work.
