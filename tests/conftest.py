# -*- coding: utf-8 -*-
"""
公共测试 Fixtures

提供各测试模块共享的 fixture。
"""

import pytest
from app.core.slots import create_slot
from app.core.domain import Domain, ResponseTemplate
from app.core.tracker import DialogueStateTracker, UserMessage


@pytest.fixture
def sample_slots():
    """创建示例槽位字典"""
    return {
        "food_type": create_slot("food_type", "text", mapping_type="from_llm"),
        "num_people": create_slot("num_people", "float", mapping_type="from_llm"),
        "is_vip": create_slot("is_vip", "bool", mapping_type="controlled"),
        "order_items": create_slot("order_items", "list", mapping_type="from_llm"),
        "priority": create_slot(
            "priority", "categorical", mapping_type="from_llm",
            values=["low", "medium", "high"],
        ),
    }


@pytest.fixture
def sample_domain(sample_slots):
    """创建示例 Domain"""
    return Domain(
        slots=sample_slots,
        actions={"action_listen", "action_restart", "utter_greet", "utter_goodbye"},
        responses={
            "utter_greet": [
                ResponseTemplate(text="你好！有什么可以帮您的吗？"),
                ResponseTemplate(text="您好，欢迎光临！"),
            ],
            "utter_goodbye": [
                ResponseTemplate(text="再见，祝您生活愉快！"),
            ],
        },
        flows=["order_flow", "inquiry_flow"],
    )


@pytest.fixture
def sample_tracker():
    """创建示例 Tracker"""
    tracker = DialogueStateTracker(sender_id="test_user")
    return tracker


@pytest.fixture
def tracker_with_history(sample_tracker):
    """创建带有对话历史的 Tracker"""
    tracker = sample_tracker

    # 模拟一轮对话
    msg1 = UserMessage(text="你好", sender_id="test_user")
    tracker.update_with_message(msg1)
    tracker.set_slot("food_type", "pizza")
    from app.core.tracker import BotMessage
    tracker.add_bot_message(BotMessage(text="您好！请问您想吃什么？"))
    tracker.finalize_turn()

    # 第二轮
    msg2 = UserMessage(text="我要一个披萨", sender_id="test_user")
    tracker.update_with_message(msg2)
    tracker.set_slot("food_type", "pizza")
    tracker.add_bot_message(BotMessage(text="好的，已为您下单！"))
    tracker.finalize_turn()

    return tracker
