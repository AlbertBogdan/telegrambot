"""Format domain results into Telegram message text.

All display rounding happens here: grams and kcal are rounded to 1 decimal
place unless a whole gram. Internal accumulators are never rounded.
"""

from nutribot.domain.calculator import CompensationResult
from nutribot.domain.models import DailyLog, UserProfile


def _fmt_grams(value: float) -> str:
    """Format grams: whole number if possible, else 1 decimal place."""
    if abs(value - round(value, 0)) < 0.05:
        return f"{value:.0f}г"
    return f"{value:.1f}г"


def _fmt_kcal(value: float) -> str:
    """Format kcal: whole number if possible, else 1 decimal place."""
    if abs(value - round(value, 0)) < 0.05:
        return f"{value:.0f}"
    return f"{value:.1f}"


def format_today(
    profile: UserProfile,
    log: DailyLog,
    comp: CompensationResult,
) -> str:
    """Render the '📈 Сегодня' view."""
    lines: list[str] = []
    lines.append("📈 *Сегодня*")
    lines.append("")

    # Protein
    b_flag = " (ПЕРЕБОР!)" if comp.b_exceeded else ""
    lines.append(
        f"Б: {_fmt_grams(log.totals.b)}/{_fmt_grams(profile.norm_b)}{b_flag}"
    )
    if not comp.b_exceeded:
        lines.append(f"   Осталось: {_fmt_grams(comp.remaining_b)}")

    # Fat
    j_flag = " (ПЕРЕБОР!)" if comp.j_exceeded else ""
    lines.append(
        f"Ж: {_fmt_grams(log.totals.j)}/{_fmt_grams(profile.norm_j)}{j_flag}"
    )
    if not comp.j_exceeded:
        lines.append(f"   Осталось: {_fmt_grams(comp.remaining_j)}")

    # Carbs
    u_flag = " (ПЕРЕБОР!)" if comp.u_exceeded else ""
    lines.append(
        f"У: {_fmt_grams(log.totals.u)}/{_fmt_grams(profile.norm_u)}{u_flag}"
    )
    if not comp.u_exceeded:
        lines.append(f"   Осталось: {_fmt_grams(comp.remaining_u)}")

    lines.append("")
    kcal_str = f"{_fmt_kcal(comp.kcal_fact)}/{_fmt_kcal(comp.kcal_norm)}"
    lines.append(f"🔥 Калории: {kcal_str} ккал")

    if comp.day_exhausted:
        lines.append("")
        lines.append("⚠️ Лимит калорий на сегодня исчерпан!")

    return "\n".join(lines)


def format_day_detail(log: DailyLog, total_kcal: float) -> str:
    """Render a single day's detail (tapped from the calendar)."""
    lines: list[str] = []
    lines.append(f"📋 *{log.date.isoformat()}*")
    lines.append("")
    lines.append(f"Б: {_fmt_grams(log.totals.b)}")
    lines.append(f"Ж: {_fmt_grams(log.totals.j)}")
    lines.append(f"У: {_fmt_grams(log.totals.u)}")
    lines.append(f"🔥 Калории: {_fmt_kcal(total_kcal)} ккал")
    return "\n".join(lines)


def format_no_data(day_date: str) -> str:
    """Render a message for a day with no log data."""
    return f"📋 *{day_date}*\n\nНет данных за этот день."


def format_onboarding_prompt() -> str:
    """Prompt shown to a new user during onboarding."""
    return (
        "🍎 *Добро пожаловать в Nutribot!*\n\n"
        "Я помогу вам следить за белками, жирами и углеводами.\n\n"
        "Для начала введите ваши дневные нормы Б/Ж/У в граммах через пробел.\n"
        "Например: `120 60 250`\n\n"
        "💡 В любой момент отправьте /help чтобы узнать, как пользоваться ботом."
    )


def format_onboarding_confirm(profile: UserProfile) -> str:
    """Show the norms that were just saved, with confirmation."""
    return (
        f"✅ Нормы сохранены!\n\n"
        f"Б: {_fmt_grams(profile.norm_b)}\n"
        f"Ж: {_fmt_grams(profile.norm_j)}\n"
        f"У: {_fmt_grams(profile.norm_u)}\n\n"
        f"Используйте кнопки ниже для начала работы."
    )


def format_edit_norm_prompt(current: UserProfile) -> str:
    """Prompt to edit norms, showing current values."""
    return (
        "⚙️ *Изменить норму*\n\n"
        f"Текущие нормы:\n"
        f"Б: {_fmt_grams(current.norm_b)}\n"
        f"Ж: {_fmt_grams(current.norm_j)}\n"
        f"У: {_fmt_grams(current.norm_u)}\n\n"
        "Введите новые нормы Б/Ж/У через пробел.\n"
        "Например: `120 60 250`"
    )


def format_edit_norm_confirm(profile: UserProfile) -> str:
    """Show confirmation after norms are changed."""
    return (
        "✅ Нормы обновлены!\n\n"
        f"Б: {_fmt_grams(profile.norm_b)}\n"
        f"Ж: {_fmt_grams(profile.norm_j)}\n"
        f"У: {_fmt_grams(profile.norm_u)}"
    )


def format_input_error() -> str:
    """Error shown when macro input doesn't match accepted formats."""
    return (
        "❌ Неверный формат.\n\n"
        "Принимаются два формата:\n"
        "• 3 числа — `Б Ж У` (граммы, которые вы съели)\n"
        "• 4 числа — `вес Б_на_100г Ж_на_100г У_на_100г`\n\n"
        "Пример: `20 10 40` или `150 20 5 30`"
    )


def format_negative_error() -> str:
    """Error for negative values."""
    return "❌ Значения не могут быть отрицательными."


def format_weight_error() -> str:
    """Error for weight <= 0 in Format B."""
    return "❌ Вес должен быть больше нуля."


def format_limit_exhausted() -> str:
    """Message when kcal limit is already exhausted."""
    return "⚠️ Лимит калорий на сегодня исчерпан!"
