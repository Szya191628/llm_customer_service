# -*- coding: utf-8 -*-
"""
对话状态追踪器测试

覆盖：Tracker 初始化、消息更新、槽位管理、对话历史、Flow 管理、序列化。
"""

import pytest
from app.core.tracker import (
    DialogueStateTracker,
    UserMessage,
    BotMessage,
    DialogueTurn,
)
from app.core.slots import create_slot
from app.shared.constants import ACTION_LISTEN


# =============================================================================
# 初始化
# =============================================================================

class TestTrackerInit:
    """测试 Tracker 初始化"""

    def test_default_init(self):
        tracker = DialogueStateTracker()
        assert tracker.sender_id == "default"
        assert tracker.slots == {}
        assert tracker.dialogue_turns == []
        assert tracker.latest_action_name == ACTION_LISTEN
        assert tracker.paused is False

    def test_custom_sender_id(self):
        tracker = DialogueStateTracker(sender_id="user_123")
        assert tracker.sender_id == "user_123"

    def test_initial_slots(self):
        slots = {"city": create_slot("city", "text")}
        tracker = DialogueStateTracker(slots=slots)
        assert "city" in tracker.slots


# =============================================================================
# 消息更新
# =============================================================================

class TestTrackerMessageUpdate:
    """测试消息更新"""

    def test_update_with_message(self, sample_tracker):
        msg = UserMessage(text="你好", sender_id="test_user")
        sample_tracker.update_with_message(msg)
        assert sample_tracker.latest_message is msg
        assert sample_tracker.latest_action_name == ACTION_LISTEN

    def test_update_with_message_starts_new_turn(self, sample_tracker):
        msg1 = UserMessage(text="第一句", sender_id="test_user")
        sample_tracker.update_with_message(msg1)
        assert sample_tracker._current_turn is not None

        msg2 = UserMessage(text="第二句", sender_id="test_user")
        sample_tracker.update_with_message(msg2)
        # 第一轮应被保存到历史
        assert len(sample_tracker.dialogue_turns) == 1
        assert sample_tracker.dialogue_turns[0].user_message.text == "第一句"

    def test_add_bot_message(self, sample_tracker):
        msg = UserMessage(text="你好", sender_id="test_user")
        sample_tracker.update_with_message(msg)
        sample_tracker.add_bot_message(BotMessage(text="您好！"))
        assert len(sample_tracker._current_turn.bot_messages) == 1
        assert sample_tracker._current_turn.bot_messages[0].text == "您好！"


# =============================================================================
# 槽位管理
# =============================================================================

class TestTrackerSlots:
    """测试槽位管理"""

    def test_set_and_get_slot(self, sample_tracker):
        sample_tracker.set_slot("city", "北京")
        assert sample_tracker.get_slot("city") == "北京"

    def test_set_slot_create_if_missing(self, sample_tracker):
        sample_tracker.set_slot("new_slot", "value")
        assert sample_tracker.get_slot("new_slot") == "value"

    def test_get_nonexistent_slot(self, sample_tracker):
        assert sample_tracker.get_slot("nonexistent") is None

    def test_get_all_slots(self, sample_tracker):
        sample_tracker.set_slot("a", 1)
        sample_tracker.set_slot("b", 2)
        all_slots = sample_tracker.get_all_slots()
        assert all_slots == {"a": 1, "b": 2}

    def test_reset_slots(self, sample_tracker):
        sample_tracker.set_slot("city", "北京")
        sample_tracker.reset_slots()
        # 槽位值应被重置（新创建的槽位 initial_value 为 None）
        assert sample_tracker.get_slot("city") is None


# =============================================================================
# 动作管理
# =============================================================================

class TestTrackerAction:
    """测试动作管理"""

    def test_set_latest_action(self, sample_tracker):
        sample_tracker.set_latest_action("action_greet")
        assert sample_tracker.latest_action_name == "action_greet"

    def test_add_commands(self, sample_tracker):
        msg = UserMessage(text="hi", sender_id="test")
        sample_tracker.update_with_message(msg)
        sample_tracker.add_commands([
            {"command": "set_slot", "name": "city", "value": "北京"},
        ])
        assert len(sample_tracker._current_turn.commands) == 1


# =============================================================================
# Flow 管理
# =============================================================================

class TestTrackerFlow:
    """测试 Flow 管理"""

    def test_start_flow(self, sample_tracker):
        sample_tracker.start_flow("order_flow", step_id="STEP_1")
        assert sample_tracker.active_flow == "order_flow"
        assert len(sample_tracker.flow_history) == 1

    def test_end_flow(self, sample_tracker):
        sample_tracker.start_flow("order_flow")
        ended = sample_tracker.end_flow()
        assert ended == "order_flow"
        assert sample_tracker.active_flow is None

    def test_end_flow_no_active(self, sample_tracker):
        ended = sample_tracker.end_flow()
        assert ended is None

    def test_cancel_flow(self, sample_tracker):
        sample_tracker.start_flow("flow_a")
        sample_tracker.start_flow("flow_b")
        sample_tracker.cancel_flow()
        assert sample_tracker.active_flow is None
        assert sample_tracker.dialogue_stack.is_empty()

    def test_record_pattern(self, sample_tracker):
        sample_tracker.record_pattern("chitchat")
        assert len(sample_tracker.flow_history) == 1
        assert sample_tracker.flow_history[0]["flow_name"] == "pattern_chitchat"


# =============================================================================
# 对话历史
# =============================================================================

class TestTrackerHistory:
    """测试对话历史"""

    def test_get_conversation_history(self, tracker_with_history):
        history = tracker_with_history.get_conversation_history()
        assert len(history) == 2
        assert history[0]["user_message"]["text"] == "你好"
        assert history[1]["user_message"]["text"] == "我要一个披萨"

    def test_get_conversation_history_with_limit(self, tracker_with_history):
        history = tracker_with_history.get_conversation_history(max_turns=1)
        assert len(history) == 1

    def test_get_messages_for_llm(self, tracker_with_history):
        # 添加当前轮次消息
        msg = UserMessage(text="再来一个", sender_id="test_user")
        tracker_with_history.update_with_message(msg)
        messages = tracker_with_history.get_messages_for_llm()
        # 应包含历史 + 当前用户消息
        assert any(m["content"] == "再来一个" for m in messages)
        assert any(m["role"] == "user" for m in messages)
        assert any(m["role"] == "assistant" for m in messages)


# =============================================================================
# 轮次管理
# =============================================================================

class TestTrackerTurn:
    """测试轮次管理"""

    def test_finalize_turn(self, sample_tracker):
        msg = UserMessage(text="hi", sender_id="test")
        sample_tracker.update_with_message(msg)
        sample_tracker.finalize_turn()
        assert sample_tracker._current_turn is None
        assert len(sample_tracker.dialogue_turns) == 1

    def test_restart(self, tracker_with_history):
        tracker_with_history.set_slot("city", "北京")
        tracker_with_history.start_flow("test_flow")
        tracker_with_history.restart()
        assert tracker_with_history.dialogue_turns == []
        # restart 重置槽位值但保留槽位定义
        for slot in tracker_with_history.slots.values():
            assert slot.value is None
        assert tracker_with_history.active_flow is None
        assert tracker_with_history.latest_message is None
        assert tracker_with_history.latest_action_name == ACTION_LISTEN


# =============================================================================
# 序列化
# =============================================================================

class TestTrackerSerialization:
    """测试序列化和反序列化"""

    def test_to_dict(self, sample_tracker):
        sample_tracker.set_slot("city", "北京")
        msg = UserMessage(text="hi", sender_id="test")
        sample_tracker.update_with_message(msg)
        sample_tracker.finalize_turn()
        d = sample_tracker.to_dict()
        assert d["sender_id"] == "test_user"
        assert d["slots"]["city"]["value"] == "北京"
        assert len(d["dialogue_turns"]) == 1

    def test_from_dict(self, sample_tracker):
        sample_tracker.set_slot("city", "北京")
        msg = UserMessage(text="hi", sender_id="test")
        sample_tracker.update_with_message(msg)
        sample_tracker.finalize_turn()
        d = sample_tracker.to_dict()
        restored = DialogueStateTracker.from_dict(d)
        assert restored.sender_id == "test_user"
        assert restored.get_slot("city") == "北京"
        assert len(restored.dialogue_turns) == 1

    def test_roundtrip_with_flow(self, sample_tracker):
        sample_tracker.start_flow("order_flow", step_id="STEP_1")
        d = sample_tracker.to_dict()
        restored = DialogueStateTracker.from_dict(d)
        assert restored.active_flow == "order_flow"

    def test_copy(self, sample_tracker):
        sample_tracker.set_slot("city", "北京")
        copy = sample_tracker.copy()
        assert copy.get_slot("city") == "北京"
        # 修改原版不影响副本
        sample_tracker.set_slot("city", "上海")
        assert copy.get_slot("city") == "北京"


# =============================================================================
# current_state
# =============================================================================

class TestTrackerCurrentState:
    """测试 current_state 方法"""

    def test_current_state_structure(self, sample_tracker):
        state = sample_tracker.current_state()
        assert "sender_id" in state
        assert "slots" in state
        assert "active_flow" in state
        assert "dialogue_stack" in state
        assert "latest_action_name" in state
        assert "paused" in state


# =============================================================================
# UserMessage / BotMessage
# =============================================================================

class TestMessages:
    """测试消息类"""

    def test_user_message_to_dict(self):
        msg = UserMessage(text="hello", sender_id="u1")
        d = msg.to_dict()
        assert d["text"] == "hello"
        assert d["sender_id"] == "u1"

    def test_user_message_from_dict(self):
        d = {"text": "hello", "sender_id": "u1"}
        msg = UserMessage.from_dict(d)
        assert msg.text == "hello"
        assert msg.sender_id == "u1"

    def test_bot_message_to_dict(self):
        msg = BotMessage(text="hi", data={"key": "val"})
        d = msg.to_dict()
        assert d["text"] == "hi"
        assert d["data"] == {"key": "val"}

    def test_bot_message_from_dict(self):
        d = {"text": "hi", "data": {"key": "val"}}
        msg = BotMessage.from_dict(d)
        assert msg.text == "hi"
        assert msg.data == {"key": "val"}
