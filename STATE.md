# Nutribot — Build State

## Last updated: 2026-07-16

## Files Created

```
src/nutribot/
  __init__.py
  config.py
  domain/
    __init__.py
    models.py          # UserProfile, DailyLog, MacroTotals dataclasses
    calculator.py      # compensate(), convert_product_to_macros(), is_day_exhausted(), kcal()
    rollover.py         # needs_rollover(), minsk_today(), minsk_now()
  storage/
    __init__.py
    repository.py      # Repository Protocol, InMemoryRepository, SupabaseRepository
  bot/
    __init__.py
    handlers.py         # NutribotHandlers — /start, macro logging, calendar, edit-norm
    keyboards.py        # main_menu(), calendar_keyboard()
    formatters.py       # format_today(), format_day_detail(), etc.
    states.py           # UserStateManager, State enum
  api/
    __init__.py
    webhook.py          # Flask app + Vercel entrypoint (POST /api/webhook)
tests/
  __init__.py
  domain/
    __init__.py
    test_calculator.py  # 17 tests
    test_rollover.py    # 10 tests
  bot/
    __init__.py
    test_formatters.py          # 12 tests
    test_onboarding_and_edit.py # 12 tests
    test_logging_flow.py        # 20 tests
    test_calendar.py            # 16 tests
SKILL.md
README.md
.env
vercel.json
migrations.sql
pyproject.toml
```

## SKILL.md Verification Status

| Step | Command | Status |
|------|---------|--------|
| 1 | `uv run pytest tests/domain/test_calculator.py -q` | ✅ 17 passed |
| 2 | `uv run pytest tests/bot/test_formatters.py -q` | ✅ 12 passed |
| 3 | `uv run pytest tests/bot/test_onboarding_and_edit.py -q` | ✅ 12 passed |
| 4 | `uv run pytest tests/bot/test_logging_flow.py -q` | ✅ 20 passed |
| 5 | `uv run pytest tests/domain/test_rollover.py -q` | ✅ 10 passed |
| 6 | `uv run pytest tests/bot/test_calendar.py -q` | ✅ 16 passed |
| 7 | `uv run ruff check .` | ✅ 0 errors |
| 8 | `uv run mypy src/` | ✅ 0 errors |
| 9 | `uv run pytest -q` | ✅ 87 passed |

## Pre-flagged Uncertainties — Resolution

1. **Spec example not arithmetically exact**: Confirmed — the UI example numbers don't reconcile with any single proportional-split rule. The spec's documented algorithm is implemented and tested against its own expected outputs.
2. **Re-/start routing**: Confirmed — existing user re-sending /start routes to edit-norm confirmation, never silently overwrites.
3. **Rounding**: Display rounding to 1 decimal (whole if near-integer), internal full-precision storage. Applied in formatters.py only.
4. **Input formats**: Disambiguated purely by token count (3 = direct grams Format A, 4 = product weight+per-100g Format B).

## Known Limitations

- `InMemoryRepository` not thread-safe — tests run single-threaded
- No multi-day backfill on rollover — one new row for today only
- Full month calendar only (no partial-week views)
- No product name capture — numbers only
- SupabaseRepository uses `ignore_missing_imports` for supabase-py type stubs (none available)
