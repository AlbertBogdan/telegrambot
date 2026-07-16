"""Simple in-memory state machine for onboarding and edit-norm flows.

Tracks which users are awaiting input for onboarding or norm editing.
Not persisted across restarts — ephemeral state only.
"""

from enum import Enum, auto


class State(Enum):
    AWAITING_ONBOARDING = auto()
    AWAITING_EDIT_NORM = auto()


class UserStateManager:
    """In-memory state tracker for multi-step flows."""

    def __init__(self) -> None:
        self._states: dict[int, State] = {}

    def set(self, user_id: int, state: State) -> None:
        self._states[user_id] = state

    def get(self, user_id: int) -> State | None:
        return self._states.get(user_id)

    def clear(self, user_id: int) -> None:
        self._states.pop(user_id, None)

    def is_awaiting_input(self, user_id: int) -> bool:
        return user_id in self._states
