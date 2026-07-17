"""Telebot message and callback handlers.

Thin handlers — delegate to domain layer for logic, use storage.Repository
for persistence. No handler touches Supabase directly.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta

from telebot import TeleBot
from telebot.types import CallbackQuery, Message

from nutribot.bot.formatters import (
    format_day_detail,
    format_edit_norm_confirm,
    format_edit_norm_prompt,
    format_input_error,
    format_limit_exhausted,
    format_negative_error,
    format_no_data,
    format_onboarding_confirm,
    format_onboarding_prompt,
    format_today,
    format_weight_error,
)
from nutribot.bot.keyboards import calendar_keyboard, main_menu
from nutribot.bot.states import State, UserStateManager
from nutribot.domain.calculator import (
    compensate,
    convert_product_to_macros,
    is_day_exhausted,
    kcal,
)
from nutribot.domain.models import DailyLog, MacroTotals
from nutribot.domain.rollover import minsk_today, needs_rollover
from nutribot.storage.repository import Repository

logger = logging.getLogger(__name__)


class NutribotHandlers:
    """Wires Telebot handlers to domain logic and storage."""

    def __init__(self, bot: TeleBot, repo: Repository) -> None:
        self.bot = bot
        self.repo = repo
        self.states = UserStateManager()
        self._register()

    def _register(self) -> None:
        bot = self.bot

        @bot.message_handler(commands=["start"])
        def handle_start(message: Message) -> None:
            self._on_start(message)

        @bot.message_handler(commands=["help"])
        def handle_help(message: Message) -> None:
            self._on_help(message)

        @bot.message_handler(
            func=lambda m: True, content_types=["text"]
        )
        def handle_text(message: Message) -> None:
            self._on_text(message)

        @bot.callback_query_handler(func=lambda c: True)
        def handle_callback(call: CallbackQuery) -> None:
            self._on_callback(call)

    # ------------------------------------------------------------------
    # /start
    # ------------------------------------------------------------------

    def _on_start(self, message: Message) -> None:
        if message.from_user is None:
            return
        user_id = message.from_user.id
        if self.states.is_awaiting_input(user_id):
            return

        profile = asyncio.run(self.repo.get_user(user_id))
        if profile is not None and profile.onboarded:
            self.bot.send_message(
                message.chat.id,
                format_edit_norm_prompt(profile),
                parse_mode="Markdown",
            )
            self.states.set(user_id, State.AWAITING_EDIT_NORM)
        else:
            self.bot.send_message(
                message.chat.id,
                format_onboarding_prompt(),
                parse_mode="Markdown",
            )
            self.states.set(user_id, State.AWAITING_ONBOARDING)

    # ------------------------------------------------------------------
    # /help
    # ------------------------------------------------------------------

    def _on_help(self, message: Message) -> None:
        self.bot.send_message(
            message.chat.id,
            (
                "🍎 *Nutribot — трекер БЖУ*\n\n"
                "*Как записывать питание:*\n"
                "• `Б Ж У` — три числа через пробел (граммы, которые съели)\n"
                "  _Пример:_ `20 10 40`\n"
                "• `Вес Б Ж У` — четыре числа (вес продукта + Б/Ж/У на 100г)\n"
                "  _Пример:_ `150 20 5 30`\n\n"
                "*Кнопки главного меню:*\n"
                "📈 *Сегодня* — сколько съедено и сколько осталось\n"
                "📅 *Календарь* — история по дням за весь месяц\n"
                "⚙️ *Изменить норму* — обновить дневные нормы Б/Ж/У\n\n"
                "*Команды:*\n"
                "/start — начать или перенастроить нормы\n"
                "/help — это сообщение\n\n"
                "⚠️ Бот считает калории (Б×4 + Ж×9 + У×4) и "
                "автоматически уменьшает остаток, если вы превысили "
                "норму по одному из нутриентов."
            ),
            parse_mode="Markdown",
        )

    # ------------------------------------------------------------------
    # Text messages (macro logging, onboarding/edit-norm input)
    # ------------------------------------------------------------------

    def _on_text(self, message: Message) -> None:
        if message.from_user is None or message.text is None:
            return
        user_id = message.from_user.id
        state = self.states.get(user_id)
        if state is not None:
            self._handle_norms_input(message, state)
            return

        self._handle_macro_logging(message)

    def _handle_norms_input(self, message: Message, state: State) -> None:
        if message.from_user is None or message.text is None:
            return
        user_id = message.from_user.id
        text = message.text.strip()

        parsed = self._parse_three_numbers(text)
        if parsed is None:
            self.bot.send_message(
                message.chat.id,
                "❌ Введите ровно 3 положительных числа через пробел.\n"
                "Например: `120 60 250`",
                parse_mode="Markdown",
            )
            return

        b, j, u = parsed
        if b < 0 or j < 0 or u < 0:
            self.bot.send_message(message.chat.id, format_negative_error())
            return

        profile = asyncio.run(self.repo.upsert_user(user_id, b, j, u))
        self.states.clear(user_id)

        if state == State.AWAITING_ONBOARDING:
            text_reply = format_onboarding_confirm(profile)
        else:
            text_reply = format_edit_norm_confirm(profile)

        self.bot.send_message(message.chat.id, text_reply, parse_mode="Markdown")
        self.bot.send_message(
            message.chat.id,
            "Главное меню:",
            reply_markup=main_menu(),
        )

    def _handle_macro_logging(self, message: Message) -> None:
        if message.from_user is None or message.text is None:
            return
        user_id = message.from_user.id
        text = message.text.strip()

        # Fetch user profile
        profile = asyncio.run(self.repo.get_user(user_id))
        if profile is None:
            self.bot.send_message(
                message.chat.id,
                "Сначала настройте бота командой /start",
            )
            return

        # Parse input — disambiguate by token count
        tokens = text.split()
        token_count = len(tokens)

        if token_count == 3:
            eaten = self._parse_format_a(tokens)
            if eaten is None:
                self.bot.send_message(message.chat.id, format_input_error())
                return
            if eaten.b < 0 or eaten.j < 0 or eaten.u < 0:
                self.bot.send_message(message.chat.id, format_negative_error())
                return
        elif token_count == 4:
            result = self._parse_format_b(tokens)
            if result is None:
                self.bot.send_message(message.chat.id, format_input_error())
                return
            weight, b100, j100, u100 = result
            if weight <= 0:
                self.bot.send_message(message.chat.id, format_weight_error())
                return
            if b100 < 0 or j100 < 0 or u100 < 0:
                self.bot.send_message(message.chat.id, format_negative_error())
                return
            eaten = convert_product_to_macros(weight, b100, j100, u100)
        else:
            self.bot.send_message(message.chat.id, format_input_error())
            return

        # Rollover check
        now = datetime.now()
        today = minsk_today(now)
        last_log = asyncio.run(self.repo.get_log(user_id, today))
        if last_log is None:
            last_date = self._get_last_log_date(user_id)
            if needs_rollover(now, last_date):
                asyncio.run(self.repo.upsert_log(user_id, today, MacroTotals()))
                last_log = DailyLog(user_id=user_id, date=today, totals=MacroTotals())

        if last_log is None:
            asyncio.run(self.repo.upsert_log(user_id, today, MacroTotals()))
            current = MacroTotals()
        else:
            current = last_log.totals

        # Check if day already exhausted
        if is_day_exhausted(
            profile.norm_b, profile.norm_j, profile.norm_u,
            current.b, current.j, current.u,
        ):
            self.bot.send_message(message.chat.id, format_limit_exhausted())
            return

        # Add eaten to current totals
        new_totals = current + eaten

        # Persist
        log = asyncio.run(self.repo.upsert_log(user_id, today, new_totals))

        # Compensate and render
        comp = compensate(
            profile.norm_b, profile.norm_j, profile.norm_u,
            log.totals.b, log.totals.j, log.totals.u,
        )
        reply = format_today(profile, log, comp)
        self.bot.send_message(message.chat.id, reply, parse_mode="Markdown")

    # ------------------------------------------------------------------
    # Callback queries (today, calendar, edit_norm, calendar nav/day)
    # ------------------------------------------------------------------

    def _on_callback(self, call: CallbackQuery) -> None:
        if call.data is None or call.from_user is None:
            return
        data = call.data
        user_id = call.from_user.id
        chat_id = call.message.chat.id if call.message else user_id

        if data == "today":
            self._cb_today(call, user_id, chat_id)
        elif data == "calendar":
            self._cb_calendar(call, user_id, chat_id)
        elif data == "edit_norm":
            self._cb_edit_norm(call, user_id, chat_id)
        elif data.startswith("cal_nav_"):
            self._cb_calendar_nav(call, user_id, chat_id, data)
        elif data.startswith("cal_day_"):
            self._cb_calendar_day(call, user_id, chat_id, data)
        elif data == "cal_noop":
            self.bot.answer_callback_query(call.id)
        else:
            self.bot.answer_callback_query(call.id)

    def _cb_today(
        self, call: CallbackQuery, user_id: int, chat_id: int
    ) -> None:
        profile = asyncio.run(self.repo.get_user(user_id))
        if profile is None:
            self.bot.answer_callback_query(
                call.id, "Сначала настройте бота командой /start"
            )
            return

        today = minsk_today()
        log = asyncio.run(self.repo.get_log(user_id, today))
        if log is None:
            log = DailyLog(user_id=user_id, date=today, totals=MacroTotals())

        comp = compensate(
            profile.norm_b, profile.norm_j, profile.norm_u,
            log.totals.b, log.totals.j, log.totals.u,
        )
        self.bot.send_message(
            chat_id, format_today(profile, log, comp), parse_mode="Markdown"
        )
        self.bot.answer_callback_query(call.id)

    def _cb_calendar(
        self, call: CallbackQuery, user_id: int, chat_id: int
    ) -> None:
        now = datetime.now()
        today = minsk_today(now)
        year, month = today.year, today.month
        self._send_calendar(chat_id, user_id, year, month)
        self.bot.answer_callback_query(call.id)

    def _cb_edit_norm(
        self, call: CallbackQuery, user_id: int, chat_id: int
    ) -> None:
        profile = asyncio.run(self.repo.get_user(user_id))
        if profile is None:
            self.bot.answer_callback_query(
                call.id, "Сначала настройте бота командой /start"
            )
            return

        self.states.set(user_id, State.AWAITING_EDIT_NORM)
        self.bot.send_message(
            chat_id,
            format_edit_norm_prompt(profile),
            parse_mode="Markdown",
        )
        self.bot.answer_callback_query(call.id)

    def _cb_calendar_nav(
        self, call: CallbackQuery, user_id: int, chat_id: int, data: str
    ) -> None:
        parts = data.split("_")
        year = int(parts[2])
        month = int(parts[3])
        direction = parts[4]

        if direction == "prev":
            month -= 1
            if month < 1:
                month = 12
                year -= 1
        else:
            month += 1
            if month > 12:
                month = 1
                year += 1

        if call.message is not None:
            self._send_calendar(
                chat_id, user_id, year, month, call.message.message_id
            )
        self.bot.answer_callback_query(call.id)

    def _cb_calendar_day(
        self, call: CallbackQuery, user_id: int, chat_id: int, data: str
    ) -> None:
        parts = data.split("_")
        year = int(parts[2])
        month = int(parts[3])
        day = int(parts[4])
        day_date = date(year, month, day)

        log = asyncio.run(self.repo.get_log(user_id, day_date))
        if log is None:
            self.bot.send_message(
                chat_id,
                format_no_data(day_date.isoformat()),
                parse_mode="Markdown",
            )
        else:
            total_kcal = kcal(log.totals)
            self.bot.send_message(
                chat_id,
                format_day_detail(log, total_kcal),
                parse_mode="Markdown",
            )
        self.bot.answer_callback_query(call.id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_three_numbers(text: str) -> tuple[float, float, float] | None:
        """Try to parse a string as exactly 3 positive numbers."""
        tokens = text.split()
        if len(tokens) != 3:
            return None
        try:
            return (float(tokens[0]), float(tokens[1]), float(tokens[2]))
        except ValueError:
            return None

    @staticmethod
    def _parse_format_a(tokens: list[str]) -> MacroTotals | None:
        """Parse Format A: exactly 3 numbers = direct eaten grams Б Ж У."""
        if len(tokens) != 3:
            return None
        try:
            b = float(tokens[0])
            j = float(tokens[1])
            u = float(tokens[2])
            return MacroTotals(b=b, j=j, u=u)
        except ValueError:
            return None

    @staticmethod
    def _parse_format_b(
        tokens: list[str],
    ) -> tuple[float, float, float, float] | None:
        """Parse Format B: exactly 4 numbers = weight + per-100g Б/Ж/У."""
        if len(tokens) != 4:
            return None
        try:
            weight = float(tokens[0])
            b100 = float(tokens[1])
            j100 = float(tokens[2])
            u100 = float(tokens[3])
            return (weight, b100, j100, u100)
        except ValueError:
            return None

    def _get_last_log_date(self, user_id: int) -> date | None:
        """Get the most recent log date for a user before today.

        Scans backwards up to 31 days. Used for rollover detection.
        """
        today = minsk_today()
        for days_back in range(1, 32):
            check_date = today - timedelta(days=days_back)
            log = asyncio.run(self.repo.get_log(user_id, check_date))
            if log is not None:
                return check_date
        return None

    def _send_calendar(
        self,
        chat_id: int,
        user_id: int,
        year: int,
        month: int,
        edit_message_id: int | None = None,
    ) -> None:
        logs = asyncio.run(self.repo.get_logs_for_month(user_id, year, month))
        days_with_data = {log.date.day for log in logs}
        kb = calendar_keyboard(year, month, days_with_data)

        if edit_message_id is not None:
            self.bot.edit_message_reply_markup(
                chat_id, edit_message_id, reply_markup=kb
            )
        else:
            self.bot.send_message(chat_id, "📅 Календарь", reply_markup=kb)
