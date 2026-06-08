# -*- coding: utf-8 -*-
"""
LangGraph 图测试

覆盖：状态创建、图构建、节点函数。
"""

import pytest
from app.agent.graph.state import MessageProcessingState, create_initial_state
from app.agent.graph.builder import (
    build_message_processing_graph,
    get_message_processing_graph,
    reset_graph_instance,
)
from app.core.tracker import DialogueStateTracker, UserMessage
from app.core.domain import Domain
from app.dialogue_understanding.flow import FlowsList


# =============================================================================
# 状态
# =============================================================================

class TestMessageProcessingState:
    """测试消息处理状态"""

    def test_create_initial_state(self):
        tracker = DialogueStateTracker(sender_id="test")
        state = create_initial_state(
            tracker=tracker,
            input_message="你好",
        )
        assert state["tracker"] is tracker
        assert state["input_message"] == "你好"
        assert state["final_responses"] == []
        assert state["is_finished"] is False
        assert state["action_count"] == 0
        assert state["max_actions"] == 10
        assert state["current_commands"] is None
        assert state["current_prediction"] is None
        assert state["current_action_result"] is None
        assert state["node_history"] == []
        assert state["error"] is None

    def test_create_initial_state_with_metadata(self):
        tracker = DialogueStateTracker()
        state = create_initial_state(
            tracker=tracker,
            input_message="test",
            metadata={"channel": "web"},
        )
        assert state["metadata"] == {"channel": "web"}

    def test_create_initial_state_with_components(self):
        tracker = DialogueStateTracker()
        domain = Domain()
        flows = FlowsList()

        state = create_initial_state(
            tracker=tracker,
            input_message="test",
            domain=domain,
            flows=flows,
            max_actions=5,
        )
        assert state["domain"] is domain
        assert state["flows"] is flows
        assert state["max_actions"] == 5


# =============================================================================
# 图构建
# =============================================================================

class TestGraphBuilding:
    """测试图构建"""

    def test_build_graph(self):
        graph = build_message_processing_graph()
        assert graph is not None

    def test_get_singleton_graph(self):
        reset_graph_instance()
        g1 = get_message_processing_graph()
        g2 = get_message_processing_graph()
        assert g1 is g2  # 同一实例

    def test_reset_graph_instance(self):
        reset_graph_instance()
        g1 = get_message_processing_graph()
        reset_graph_instance()
        g2 = get_message_processing_graph()
        assert g1 is not g2  # 重置后应创建新实例


# =============================================================================
# 图结构验证
# =============================================================================

class TestGraphStructure:
    """测试图结构"""

    def test_graph_has_required_nodes(self):
        graph = build_message_processing_graph()
        # LangGraph 编译后的图应支持 ainvoke
        assert hasattr(graph, "ainvoke")

    async def test_graph_invocation(self):
        """测试图能被调用（不带 LLM，走降级路径）"""
        reset_graph_instance()
        graph = get_message_processing_graph()

        tracker = DialogueStateTracker(sender_id="test")
        msg = UserMessage(text="你好", sender_id="test")
        tracker.update_with_message(msg)

        state = create_initial_state(
            tracker=tracker,
            input_message="你好",
            domain=Domain(),
            flows=FlowsList(),
        )

        # 执行图（无 LLM generator，应走降级路径）
        result = await graph.ainvoke(state)

        assert "node_history" in result
        assert len(result["node_history"]) > 0
        # 应经过 understand 和 policy 节点
        assert "understand" in result["node_history"]
        assert "policy" in result["node_history"]
