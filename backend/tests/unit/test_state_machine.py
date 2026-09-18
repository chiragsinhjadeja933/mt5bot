"""Unit tests — bot state machine (Section 15 / 30 [ADD])"""
from __future__ import annotations
import pytest
from app.trading.state_machine import (
    SystemState, BotState, ConnectionState, ExecutionMode,
    OrderClass, is_order_allowed,
)


class TestStateMachineTransitions:
    def test_ready_to_running(self):
        s = SystemState()
        s.transition_bot(BotState.RUNNING, "user_start")
        assert s.bot_state == BotState.RUNNING

    def test_running_to_paused(self):
        s = SystemState()
        s.transition_bot(BotState.RUNNING, "user_start")
        s.transition_bot(BotState.PAUSED, "user_pause")
        assert s.bot_state == BotState.PAUSED

    def test_illegal_transition_raises(self):
        s = SystemState()
        with pytest.raises(ValueError):
            # Cannot go directly from READY to PAUSED
            s.transition_bot(BotState.PAUSED, "illegal")

    def test_emergency_stop_from_running(self):
        s = SystemState()
        s.transition_bot(BotState.RUNNING, "user_start")
        s.transition_bot(BotState.EMERGENCY_STOP, "emergency")
        assert s.bot_state == BotState.EMERGENCY_STOP
        assert s.emergency_stop_persisted is True

    def test_emergency_stop_persisted(self):
        s = SystemState()
        s.transition_bot(BotState.RUNNING, "user_start")
        s.transition_bot(BotState.EMERGENCY_STOP, "emergency")
        # After "restart" (simulated by reading the field)
        assert s.emergency_stop_persisted is True

    def test_reset_from_emergency(self):
        s = SystemState()
        s.transition_bot(BotState.RUNNING, "user_start")
        s.transition_bot(BotState.EMERGENCY_STOP, "emergency")
        s.transition_bot(BotState.READY, "manual_reset_confirmed")
        assert s.bot_state == BotState.READY

    def test_sequence_number_increments(self):
        s = SystemState()
        n0 = s.sequence_number
        s.transition_bot(BotState.RUNNING, "user_start")
        assert s.sequence_number > n0


class TestOrderAllowance:
    def test_entry_allowed_in_running(self):
        assert is_order_allowed(
            OrderClass.ENTRY, ConnectionState.CONNECTED, BotState.RUNNING
        ) is True

    def test_entry_blocked_in_paused(self):
        assert is_order_allowed(
            OrderClass.ENTRY, ConnectionState.CONNECTED, BotState.PAUSED
        ) is False

    def test_entry_blocked_in_emergency(self):
        assert is_order_allowed(
            OrderClass.ENTRY, ConnectionState.CONNECTED, BotState.EMERGENCY_STOP
        ) is False

    def test_reduce_allowed_in_paused(self):
        """PAUSED still allows exits (Section 15 [FIX])."""
        assert is_order_allowed(
            OrderClass.REDUCE, ConnectionState.CONNECTED, BotState.PAUSED
        ) is True

    def test_emergency_close_always_allowed(self):
        for conn in ConnectionState:
            for bot in BotState:
                assert is_order_allowed(
                    OrderClass.EMERGENCY_CLOSE, conn, bot
                ) is True

    def test_entry_blocked_disconnected(self):
        assert is_order_allowed(
            OrderClass.ENTRY, ConnectionState.DISCONNECTED, BotState.RUNNING
        ) is False
