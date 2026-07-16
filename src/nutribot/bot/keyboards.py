"""Inline keyboard builders for the Telegram bot."""

import calendar

from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    """Build the main menu keyboard: 📈 Сегодня, 📅 Календарь, ⚙️ Изменить норму."""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📈 Сегодня", callback_data="today"),
        InlineKeyboardButton("📅 Календарь", callback_data="calendar"),
        InlineKeyboardButton("⚙️ Изменить норму", callback_data="edit_norm"),
    )
    return keyboard


def calendar_keyboard(year: int, month: int, days_with_data: set[int]) -> InlineKeyboardMarkup:
    """Build a full-month calendar inline keyboard.

    Args:
        year: Calendar year.
        month: Calendar month (1–12).
        days_with_data: Set of day numbers that have daily_log entries.
    """
    keyboard = InlineKeyboardMarkup(row_width=7)

    # Month/year header row
    month_name = _MONTH_NAMES_RU.get(month, str(month))
    header_text = f"{month_name} {year}"
    keyboard.add(
        InlineKeyboardButton("◀", callback_data=f"cal_nav_{year}_{month}_prev"),
        InlineKeyboardButton(header_text, callback_data="cal_noop"),
        InlineKeyboardButton("▶", callback_data=f"cal_nav_{year}_{month}_next"),
    )

    # Day-of-week header (Mon–Sun)
    dow_buttons = [
        InlineKeyboardButton(abbr, callback_data="cal_noop")
        for abbr in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    ]
    keyboard.add(*dow_buttons)

    # Calendar grid
    cal = calendar.Calendar(firstweekday=0)  # Monday first
    weeks = cal.monthdayscalendar(year, month)

    for week in weeks:
        row: list[InlineKeyboardButton] = []
        for day in week:
            if day == 0:
                # Empty cell
                row.append(InlineKeyboardButton(" ", callback_data="cal_noop"))
            elif day in days_with_data:
                # Marked day — has data
                row.append(
                    InlineKeyboardButton(f"●{day}", callback_data=f"cal_day_{year}_{month}_{day}")
                )
            else:
                # Unmarked day — no data
                row.append(
                    InlineKeyboardButton(str(day), callback_data=f"cal_day_{year}_{month}_{day}")
                )
        keyboard.add(*row)

    return keyboard


_MONTH_NAMES_RU: dict[int, str] = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}
