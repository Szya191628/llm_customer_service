# -*- coding: utf-8 -*-
"""
对话栈测试

覆盖：DialogueStack 基本操作、Flow 帧管理、栈帧类型、序列化。
"""

import pytest
from app.dialogue_understanding.stack.dialogue_stack import DialogueStack
from app.dialogue_understanding.stack.stack_frame import (
    StackFrame,
    FlowStackFrame,
    SearchStackFrame,
    ChitChatStackFrame,
    CannotHandleStackFrame,
    CompletedStackFrame,
    HumanHandoffStackFrame,
    FrameState,
    FlowFrameType,
    generate_frame_id,
    create_frame_from_dict,
)


# =============================================================================
# 基本栈操作
# =============================================================================

class TestDialogueStackBasic:
    """测试基本栈操作"""

    def test_empty_stack(self):
        stack = DialogueStack()
        assert stack.is_empty()
        assert stack.size() == 0
        assert len(stack) == 0
        assert stack.top() is None
        assert stack.pop() is None

    def test_push_and_pop(self):
        stack = DialogueStack()
        frame = FlowStackFrame(flow_id="test_flow")
        stack.push(frame)
        assert not stack.is_empty()
        assert stack.size() == 1
        popped = stack.pop()
        assert popped is frame
        assert stack.is_empty()

    def test_top_returns_without_removing(self):
        stack = DialogueStack()
        frame = FlowStackFrame(flow_id="test_flow")
        stack.push(frame)
        top = stack.top()
        assert top is frame
        assert stack.size() == 1  # 没有被移除

    def test_lifo_order(self):
        stack = DialogueStack()
        f1 = FlowStackFrame(flow_id="flow_1")
        f2 = FlowStackFrame(flow_id="flow_2")
        stack.push(f1)
        stack.push(f2)
        assert stack.pop() is f2
        assert stack.pop() is f1

    def test_clear(self):
        stack = DialogueStack()
        stack.push(FlowStackFrame(flow_id="a"))
        stack.push(FlowStackFrame(flow_id="b"))
        stack.clear()
        assert stack.is_empty()

    def test_len(self):
        stack = DialogueStack()
        assert len(stack) == 0
        stack.push(FlowStackFrame(flow_id="a"))
        assert len(stack) == 1

    def test_iter_top_to_bottom(self):
        stack = DialogueStack()
        f1 = FlowStackFrame(flow_id="a")
        f2 = FlowStackFrame(flow_id="b")
        stack.push(f1)
        stack.push(f2)
        frames = list(stack)
        assert frames[0] is f2  # 栈顶先出
        assert frames[1] is f1

    def test_bottom_up(self):
        stack = DialogueStack()
        f1 = FlowStackFrame(flow_id="a")
        f2 = FlowStackFrame(flow_id="b")
        stack.push(f1)
        stack.push(f2)
        frames = list(stack.bottom_up())
        assert frames[0] is f1  # 栈底先出
        assert frames[1] is f2


# =============================================================================
# Flow 帧操作
# =============================================================================

class TestDialogueStackFlow:
    """测试 Flow 帧操作"""

    def test_push_flow(self):
        stack = DialogueStack()
        frame = stack.push_flow("order_flow", step_id="STEP_1")
        assert isinstance(frame, FlowStackFrame)
        assert frame.flow_id == "order_flow"
        assert frame.step_id == "STEP_1"
        assert stack.top() is frame

    def test_top_flow_frame(self):
        stack = DialogueStack()
        stack.push(SearchStackFrame())  # 非 Flow 帧
        flow_frame = stack.push_flow("order_flow")
        assert stack.top_flow_frame() is flow_frame

    def test_top_flow_frame_none(self):
        stack = DialogueStack()
        stack.push(SearchStackFrame())
        assert stack.top_flow_frame() is None

    def test_active_flow_frame(self):
        stack = DialogueStack()
        frame = stack.push_flow("order_flow")
        assert stack.active_flow_frame() is frame

    def test_active_flow_frame_interrupted(self):
        stack = DialogueStack()
        frame = stack.push_flow("order_flow")
        frame.interrupt()
        assert stack.active_flow_frame() is None  # 已中断，不算 active

    def test_find_flow_frame(self):
        stack = DialogueStack()
        stack.push_flow("flow_a")
        stack.push_flow("flow_b")
        found = stack.find_flow_frame("flow_a")
        assert found is not None
        assert found.flow_id == "flow_a"

    def test_find_flow_frame_not_found(self):
        stack = DialogueStack()
        stack.push_flow("flow_a")
        assert stack.find_flow_frame("flow_b") is None

    def test_has_flow(self):
        stack = DialogueStack()
        stack.push_flow("order_flow")
        assert stack.has_flow("order_flow") is True
        assert stack.has_flow("other_flow") is False

    def test_get_all_flow_ids(self):
        stack = DialogueStack()
        stack.push_flow("flow_a")
        stack.push(SearchStackFrame())
        stack.push_flow("flow_b")
        ids = stack.get_all_flow_ids()
        assert ids == ["flow_b", "flow_a"]  # 栈顶到栈底

    def test_pop_to_flow(self):
        stack = DialogueStack()
        stack.push_flow("flow_a")
        stack.push(SearchStackFrame())
        stack.push_flow("flow_b")
        popped = stack.pop_to_flow("flow_a")
        assert len(popped) == 2  # flow_b + search
        assert stack.top_flow_frame().flow_id == "flow_a"

    def test_interrupt_top_flow(self):
        stack = DialogueStack()
        frame = stack.push_flow("order_flow")
        interrupted = stack.interrupt_top_flow()
        assert interrupted is frame
        assert frame.state == FrameState.INTERRUPTED

    def test_interrupt_top_flow_none(self):
        stack = DialogueStack()
        assert stack.interrupt_top_flow() is None


# =============================================================================
# 帧查找
# =============================================================================

class TestDialogueStackFind:
    """测试帧查找操作"""

    def test_find_frame(self):
        stack = DialogueStack()
        frame = stack.push_flow("order_flow")
        found = stack.find_frame(frame.frame_id)
        assert found is frame

    def test_find_frame_not_found(self):
        stack = DialogueStack()
        assert stack.find_frame("nonexistent") is None

    def test_find_frames_of_type(self):
        stack = DialogueStack()
        stack.push_flow("flow_a")
        stack.push(SearchStackFrame())
        stack.push_flow("flow_b")
        flow_frames = stack.find_frames_of_type(FlowStackFrame)
        assert len(flow_frames) == 2

    def test_remove_frame(self):
        stack = DialogueStack()
        frame = stack.push_flow("order_flow")
        removed = stack.remove_frame(frame.frame_id)
        assert removed is frame
        assert stack.is_empty()

    def test_remove_frame_not_found(self):
        stack = DialogueStack()
        assert stack.remove_frame("nonexistent") is None


# =============================================================================
# 序列化
# =============================================================================

class TestDialogueStackSerialization:
    """测试序列化"""

    def test_as_dict(self):
        stack = DialogueStack()
        stack.push_flow("order_flow", step_id="STEP_1")
        d = stack.as_dict()
        assert "frames" in d
        assert len(d["frames"]) == 1
        assert d["frames"][0]["type"] == "flow"
        assert d["frames"][0]["flow_id"] == "order_flow"

    def test_from_dict(self):
        data = {
            "frames": [
                {"type": "flow", "flow_id": "order_flow", "step_id": "STEP_1"},
                {"type": "search"},
            ]
        }
        stack = DialogueStack.from_dict(data)
        assert stack.size() == 2
        assert isinstance(stack.frames[0], FlowStackFrame)
        assert isinstance(stack.frames[1], SearchStackFrame)

    def test_roundtrip(self):
        stack = DialogueStack()
        stack.push_flow("order_flow")
        stack.push(SearchStackFrame())
        restored = DialogueStack.from_dict(stack.as_dict())
        assert restored.size() == 2
        assert restored.frames[0].flow_id == "order_flow"

    def test_copy(self):
        stack = DialogueStack()
        stack.push_flow("order_flow")
        copy = stack.copy()
        assert copy.size() == 1
        # 修改原版不影响副本
        stack.push_flow("other")
        assert copy.size() == 1


# =============================================================================
# StackFrame 类型
# =============================================================================

class TestStackFrameTypes:
    """测试各种栈帧类型"""

    def test_flow_stack_frame(self):
        frame = FlowStackFrame(flow_id="order_flow", step_id="STEP_1")
        assert frame.frame_type() == "flow"
        assert frame.is_active() is True
        assert frame.flow_id == "order_flow"

    def test_flow_stack_frame_advance(self):
        frame = FlowStackFrame(flow_id="order_flow", step_id="STEP_1")
        frame.advance_to_step("STEP_2")
        assert frame.step_id == "STEP_2"

    def test_flow_stack_frame_states(self):
        frame = FlowStackFrame(flow_id="test")
        assert frame.is_active()
        frame.complete()
        assert frame.is_completed()
        assert not frame.is_active()

    def test_flow_stack_frame_interrupt_type(self):
        frame = FlowStackFrame(flow_id="test", flow_frame_type=FlowFrameType.INTERRUPT)
        assert frame.is_interrupt()

    def test_search_stack_frame(self):
        frame = SearchStackFrame()
        assert frame.frame_type() == "search"
        assert frame.is_active()

    def test_chitchat_stack_frame(self):
        frame = ChitChatStackFrame()
        assert frame.frame_type() == "chitchat"

    def test_cannot_handle_stack_frame(self):
        frame = CannotHandleStackFrame(reason="不支持的请求")
        assert frame.frame_type() == "cannot_handle"
        assert frame.reason == "不支持的请求"

    def test_completed_stack_frame(self):
        frame = CompletedStackFrame(previous_flow_name="order_flow")
        assert frame.frame_type() == "completed"
        assert frame.previous_flow_name == "order_flow"

    def test_human_handoff_stack_frame(self):
        frame = HumanHandoffStackFrame(reason="用户要求人工")
        assert frame.frame_type() == "human_handoff"
        assert frame.reason == "用户要求人工"


# =============================================================================
# FrameState 枚举
# =============================================================================

class TestFrameState:
    """测试帧状态枚举"""

    def test_values(self):
        assert FrameState.ACTIVE.value == "active"
        assert FrameState.COMPLETED.value == "completed"
        assert FrameState.INTERRUPTED.value == "interrupted"
        assert FrameState.CANCELLED.value == "cancelled"


# =============================================================================
# 工厂函数
# =============================================================================

class TestCreateFrameFromDict:
    """测试 create_frame_from_dict 工厂函数"""

    def test_create_flow_frame(self):
        data = {"type": "flow", "flow_id": "order", "step_id": "S1"}
        frame = create_frame_from_dict(data)
        assert isinstance(frame, FlowStackFrame)
        assert frame.flow_id == "order"

    def test_create_search_frame(self):
        data = {"type": "search"}
        frame = create_frame_from_dict(data)
        assert isinstance(frame, SearchStackFrame)

    def test_create_chitchat_frame(self):
        data = {"type": "chitchat"}
        frame = create_frame_from_dict(data)
        assert isinstance(frame, ChitChatStackFrame)

    def test_create_cannot_handle_frame(self):
        data = {"type": "cannot_handle", "reason": "test"}
        frame = create_frame_from_dict(data)
        assert isinstance(frame, CannotHandleStackFrame)

    def test_create_completed_frame(self):
        data = {"type": "completed", "previous_flow_name": "order"}
        frame = create_frame_from_dict(data)
        assert isinstance(frame, CompletedStackFrame)

    def test_create_human_handoff_frame(self):
        data = {"type": "human_handoff", "reason": "test"}
        frame = create_frame_from_dict(data)
        assert isinstance(frame, HumanHandoffStackFrame)

    def test_missing_type_raises(self):
        with pytest.raises(ValueError, match="Missing 'type'"):
            create_frame_from_dict({"flow_id": "x"})

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown frame type"):
            create_frame_from_dict({"type": "nonexistent"})


# =============================================================================
# generate_frame_id
# =============================================================================

class TestGenerateFrameId:
    """测试帧 ID 生成"""

    def test_returns_string(self):
        fid = generate_frame_id()
        assert isinstance(fid, str)

    def test_length(self):
        fid = generate_frame_id()
        assert len(fid) == 8

    def test_unique(self):
        ids = {generate_frame_id() for _ in range(100)}
        assert len(ids) == 100  # 100 个应全部不同


# =============================================================================
# repr
# =============================================================================

class TestDialogueStackRepr:
    """测试字符串表示"""

    def test_empty_repr(self):
        stack = DialogueStack()
        assert "empty" in repr(stack)

    def test_with_flows_repr(self):
        stack = DialogueStack()
        stack.push_flow("order_flow", step_id="STEP_1")
        r = repr(stack)
        assert "order_flow" in r
        assert "STEP_1" in r
