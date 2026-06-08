# -*- coding: utf-8 -*-
"""
Action 系统测试

覆盖：内置动作注册/获取、动作执行、ActionResult。
"""

import pytest
from app.agent.actions import (
    Action,
    ActionResult,
    ActionListen,
    ActionRestart,
    ActionSessionStart,
    ActionDefaultFallback,
    ActionChitChatResponse,
    ActionCancelFlow,
    ActionChangeFlow,
    ActionCleanStack,
    ActionSendText,
    ActionHandleHelp,
    ActionClarify,
    ActionHumanHandoff,
    ActionTriggerSearch,
    ActionFlowCompleted,
    ActionUtter,
    register_action,
    get_action,
    get_all_action_names,
    _CUSTOM_ACTIONS,
)
from app.core.tracker import DialogueStateTracker, UserMessage
from app.core.domain import Domain, ResponseTemplate


# =============================================================================
# ActionResult
# =============================================================================

class TestActionResult:
    """测试动作结果"""

    def test_default_values(self):
        result = ActionResult()
        assert result.responses == []
        assert result.events == []
        assert result.success is True

    def test_add_response(self):
        result = ActionResult()
        result.add_response("hello")
        assert len(result.responses) == 1
        assert result.responses[0]["text"] == "hello"

    def test_add_response_with_kwargs(self):
        result = ActionResult()
        result.add_response("hello", buttons=[{"title": "ok"}])
        assert result.responses[0]["buttons"] == [{"title": "ok"}]

    def test_add_event(self):
        result = ActionResult()
        result.add_event("test_event", key="val")
        assert len(result.events) == 1
        assert result.events[0]["event"] == "test_event"
        assert result.events[0]["key"] == "val"


# =============================================================================
# 动作注册和获取
# =============================================================================

class TestActionRegistry:
    """测试动作注册表"""

    def test_get_builtin_action(self):
        action = get_action("action_listen")
        assert isinstance(action, ActionListen)

    def test_get_utter_action(self):
        action = get_action("utter_greet")
        assert isinstance(action, ActionUtter)
        assert action.name == "utter_greet"

    def test_get_nonexistent_action(self):
        assert get_action("nonexistent_action") is None

    def test_register_custom_action(self):
        class MyAction(Action):
            @property
            def name(self):
                return "action_custom_test"

            async def run(self, tracker, domain=None, **kwargs):
                return ActionResult()

        action = MyAction()
        register_action(action)
        retrieved = get_action("action_custom_test")
        assert retrieved is action

    def test_get_all_action_names(self):
        names = get_all_action_names()
        assert "action_listen" in names
        assert "action_restart" in names

    def test_custom_overrides_builtin(self):
        """自定义动作应优先于内置动作"""
        class CustomListen(Action):
            @property
            def name(self):
                return "action_listen"

            async def run(self, tracker, domain=None, **kwargs):
                result = ActionResult()
                result.add_response("custom")
                return result

        action = CustomListen()
        register_action(action)
        retrieved = get_action("action_listen")
        assert isinstance(retrieved, CustomListen)


# =============================================================================
# 内置动作执行
# =============================================================================

@pytest.fixture
def tracker():
    t = DialogueStateTracker(sender_id="test")
    msg = UserMessage(text="你好", sender_id="test")
    t.update_with_message(msg)
    return t


@pytest.fixture
def domain():
    return Domain(
        responses={
            "utter_greet": [ResponseTemplate(text="你好！欢迎光临！")],
        }
    )


class TestBuiltinActions:
    """测试内置动作"""

    @pytest.mark.asyncio
    async def test_action_listen(self, tracker):
        action = ActionListen()
        result = await action.run(tracker)
        assert result.success is True
        assert result.responses == []

    @pytest.mark.asyncio
    async def test_action_restart(self, tracker):
        tracker.set_slot("city", "北京")
        action = ActionRestart()
        result = await action.run(tracker)
        assert result.success is True
        assert any(e["event"] == "conversation_restarted" for e in result.events)
        assert tracker.get_slot("city") is None  # 已重启

    @pytest.mark.asyncio
    async def test_action_session_start(self, tracker):
        action = ActionSessionStart()
        result = await action.run(tracker)
        assert result.success is True
        assert any(e["event"] == "session_started" for e in result.events)

    @pytest.mark.asyncio
    async def test_action_default_fallback(self, tracker):
        action = ActionDefaultFallback()
        result = await action.run(tracker)
        assert result.success is True
        assert any(e["event"] == "cannot_handle_triggered" for e in result.events)

    @pytest.mark.asyncio
    async def test_action_chitchat_response(self, tracker):
        action = ActionChitChatResponse()
        result = await action.run(tracker)
        assert result.success is True
        assert any(e["event"] == "chitchat_triggered" for e in result.events)

    @pytest.mark.asyncio
    async def test_action_cancel_flow_with_active(self, tracker):
        tracker.start_flow("test_flow")
        action = ActionCancelFlow()
        result = await action.run(tracker)
        assert result.success is True
        assert any(e["event"] == "flow_cancelled" for e in result.events)
        assert any("已取消" in r["text"] for r in result.responses)

    @pytest.mark.asyncio
    async def test_action_cancel_flow_without_active(self, tracker):
        action = ActionCancelFlow()
        result = await action.run(tracker)
        assert any("没有进行中的流程" in r["text"] for r in result.responses)

    @pytest.mark.asyncio
    async def test_action_change_flow(self, tracker):
        tracker.start_flow("old_flow")
        action = ActionChangeFlow()
        result = await action.run(tracker, target_flow="new_flow")
        assert result.success is True
        assert tracker.active_flow == "new_flow"

    @pytest.mark.asyncio
    async def test_action_change_flow_no_target(self, tracker):
        action = ActionChangeFlow()
        result = await action.run(tracker)
        assert any("未指定目标流程" in r["text"] for r in result.responses)

    @pytest.mark.asyncio
    async def test_action_clean_stack(self, tracker):
        tracker.start_flow("flow_a")
        tracker.start_flow("flow_b")
        action = ActionCleanStack()
        result = await action.run(tracker)
        assert result.success is True
        assert tracker.dialogue_stack.is_empty()

    @pytest.mark.asyncio
    async def test_action_send_text(self, tracker):
        action = ActionSendText()
        result = await action.run(tracker, text="发送的消息")
        assert any(r["text"] == "发送的消息" for r in result.responses)

    @pytest.mark.asyncio
    async def test_action_send_text_empty(self, tracker):
        action = ActionSendText()
        result = await action.run(tracker)
        assert result.responses == []

    @pytest.mark.asyncio
    async def test_action_handle_help(self, tracker):
        action = ActionHandleHelp()
        result = await action.run(tracker)
        assert len(result.responses) == 1
        assert "帮助" in result.responses[0]["text"]

    @pytest.mark.asyncio
    async def test_action_clarify(self, tracker):
        action = ActionClarify()
        result = await action.run(tracker, question="请问您要什么？", options=["A", "B"])
        assert len(result.responses) == 1
        assert "请问您要什么？" in result.responses[0]["text"]
        assert "A" in result.responses[0]["text"]

    @pytest.mark.asyncio
    async def test_action_clarify_default(self, tracker):
        action = ActionClarify()
        result = await action.run(tracker)
        assert "抱歉" in result.responses[0]["text"]

    @pytest.mark.asyncio
    async def test_action_human_handoff(self, tracker):
        action = ActionHumanHandoff()
        result = await action.run(tracker, reason="用户要求")
        assert any(e["event"] == "human_handoff_triggered" for e in result.events)

    @pytest.mark.asyncio
    async def test_action_trigger_search(self, tracker):
        action = ActionTriggerSearch()
        result = await action.run(tracker)
        assert any(e["event"] == "search_triggered" for e in result.events)

    @pytest.mark.asyncio
    async def test_action_trigger_search_no_message(self):
        tracker = DialogueStateTracker()
        action = ActionTriggerSearch()
        result = await action.run(tracker)
        assert any("请提供" in r["text"] for r in result.responses)

    @pytest.mark.asyncio
    async def test_action_flow_completed(self, tracker):
        action = ActionFlowCompleted()
        result = await action.run(tracker, completed_flow="order_flow")
        assert any(e["event"] == "flow_completed_handled" for e in result.events)

    @pytest.mark.asyncio
    async def test_action_utter(self, tracker, domain):
        action = ActionUtter("utter_greet")
        result = await action.run(tracker, domain=domain)
        assert any("你好" in r["text"] or "欢迎" in r["text"] for r in result.responses)

    @pytest.mark.asyncio
    async def test_action_utter_with_slot_replacement(self, tracker, domain):
        domain.add_response(
            "utter_welcome",
            [ResponseTemplate(text="欢迎{name}！")]
        )
        tracker.set_slot("name", "张三")
        action = ActionUtter("utter_welcome")
        result = await action.run(tracker, domain=domain)
        assert any("张三" in r["text"] for r in result.responses)

    @pytest.mark.asyncio
    async def test_action_utter_no_domain(self, tracker):
        action = ActionUtter("utter_greet")
        result = await action.run(tracker, domain=None)
        assert result.responses == []

    @pytest.mark.asyncio
    async def test_action_utter_nonexistent_response(self, tracker, domain):
        action = ActionUtter("utter_nonexistent")
        result = await action.run(tracker, domain=domain)
        assert result.responses == []


# =============================================================================
# Action 名称
# =============================================================================

class TestActionNames:
    """测试动作名称"""

    def test_listen_name(self):
        assert ActionListen().name == "action_listen"

    def test_restart_name(self):
        assert ActionRestart().name == "action_restart"

    def test_session_start_name(self):
        assert ActionSessionStart().name == "action_session_start"

    def test_default_fallback_name(self):
        assert ActionDefaultFallback().name == "action_default_fallback"

    def test_utter_name(self):
        assert ActionUtter("utter_greet").name == "utter_greet"
