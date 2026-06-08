# -*- coding: utf-8 -*-
"""
Domain 测试

覆盖：Domain 创建、解析、合并、响应模板。
"""

import pytest
from app.core.domain import Domain, ResponseTemplate
from app.core.slots import create_slot, TextSlot, BoolSlot


# =============================================================================
# ResponseTemplate
# =============================================================================

class TestResponseTemplate:
    """测试响应模板"""

    def test_from_string(self):
        tpl = ResponseTemplate.from_dict("你好")
        assert tpl.text == "你好"

    def test_from_dict(self):
        data = {
            "text": "请选择：",
            "buttons": [{"title": "A"}, {"title": "B"}],
            "image": "http://img.png",
        }
        tpl = ResponseTemplate.from_dict(data)
        assert tpl.text == "请选择："
        assert len(tpl.buttons) == 2
        assert tpl.image == "http://img.png"

    def test_to_dict(self):
        tpl = ResponseTemplate(text="hi", buttons=[{"title": "ok"}])
        d = tpl.to_dict()
        assert d["text"] == "hi"
        assert d["buttons"] == [{"title": "ok"}]

    def test_to_dict_minimal(self):
        tpl = ResponseTemplate()
        d = tpl.to_dict()
        assert d == {}


# =============================================================================
# Domain 创建
# =============================================================================

class TestDomainCreation:
    """测试 Domain 创建"""

    def test_default_domain(self):
        domain = Domain()
        assert domain.version == "1.0"
        # 应包含默认动作
        assert "action_listen" in domain.actions
        assert "action_restart" in domain.actions
        assert "action_session_start" in domain.actions
        assert "action_default_fallback" in domain.actions

    def test_domain_with_slots(self):
        slots = {"city": create_slot("city", "text")}
        domain = Domain(slots=slots)
        assert "city" in domain.slots
        assert isinstance(domain.slots["city"], TextSlot)

    def test_domain_with_responses(self):
        responses = {
            "utter_greet": [ResponseTemplate(text="你好")],
        }
        domain = Domain(responses=responses)
        assert "utter_greet" in domain.responses
        assert domain.responses["utter_greet"][0].text == "你好"


# =============================================================================
# Domain.from_dict
# =============================================================================

class TestDomainFromDict:
    """测试从字典创建 Domain"""

    def test_parse_slots_simple(self):
        data = {"slots": {"city": "text", "is_vip": "bool"}}
        domain = Domain.from_dict(data)
        assert "city" in domain.slots
        assert isinstance(domain.slots["city"], TextSlot)
        assert isinstance(domain.slots["is_vip"], BoolSlot)

    def test_parse_slots_detailed(self):
        data = {
            "slots": {
                "priority": {
                    "type": "categorical",
                    "values": ["low", "high"],
                    "mappings": [{"type": "from_llm"}],
                    "description": "优先级",
                }
            }
        }
        domain = Domain.from_dict(data)
        slot = domain.slots["priority"]
        assert slot.type_name == "categorical"
        assert slot.description == "优先级"

    def test_parse_actions(self):
        data = {"actions": ["action_greet", "action_order"]}
        domain = Domain.from_dict(data)
        assert "action_greet" in domain.actions
        assert "action_order" in domain.actions

    def test_parse_responses(self):
        data = {
            "responses": {
                "utter_greet": [
                    {"text": "你好"},
                    "欢迎光临",
                ]
            }
        }
        domain = Domain.from_dict(data)
        assert len(domain.responses["utter_greet"]) == 2

    def test_parse_flows(self):
        data = {"flows": ["order_flow", "inquiry_flow"]}
        domain = Domain.from_dict(data)
        assert domain.flows == ["order_flow", "inquiry_flow"]

    def test_empty_dict(self):
        domain = Domain.from_dict({})
        assert domain.slots == {}
        assert domain.flows == []


# =============================================================================
# Domain 方法
# =============================================================================

class TestDomainMethods:
    """测试 Domain 方法"""

    def test_get_slot(self, sample_domain):
        slot = sample_domain.get_slot("food_type")
        assert slot is not None
        assert slot.name == "food_type"

    def test_get_slot_nonexistent(self, sample_domain):
        assert sample_domain.get_slot("nonexistent") is None

    def test_get_response(self, sample_domain):
        responses = sample_domain.get_response("utter_greet")
        assert len(responses) == 2
        assert responses[0].text == "你好！有什么可以帮您的吗？"

    def test_get_response_nonexistent(self, sample_domain):
        assert sample_domain.get_response("utter_nonexistent") == []

    def test_has_action(self, sample_domain):
        assert sample_domain.has_action("action_listen") is True
        assert sample_domain.has_action("nonexistent") is False

    def test_has_flow(self, sample_domain):
        assert sample_domain.has_flow("order_flow") is True
        assert sample_domain.has_flow("nonexistent") is False

    def test_add_slot(self):
        domain = Domain()
        domain.add_slot(create_slot("new_slot", "text"))
        assert "new_slot" in domain.slots

    def test_add_action(self):
        domain = Domain()
        domain.add_action("action_custom")
        assert "action_custom" in domain.actions

    def test_add_response(self):
        domain = Domain()
        domain.add_response("utter_new", [ResponseTemplate(text="新响应")])
        assert "utter_new" in domain.responses


# =============================================================================
# Domain 合并
# =============================================================================

class TestDomainMerge:
    """测试 Domain 合并"""

    def test_merge_slots(self):
        d1 = Domain(slots={"a": create_slot("a", "text")})
        d2 = Domain(slots={"b": create_slot("b", "text")})
        merged = d1.merge(d2)
        assert "a" in merged.slots
        assert "b" in merged.slots

    def test_merge_slots_override(self):
        s1 = create_slot("x", "text")
        s1.value = "old"
        s2 = create_slot("x", "text")
        s2.value = "new"
        d1 = Domain(slots={"x": s1})
        d2 = Domain(slots={"x": s2})
        merged = d1.merge(d2)
        assert merged.slots["x"].value == "new"

    def test_merge_actions(self):
        d1 = Domain(actions={"a1"})
        d2 = Domain(actions={"a2"})
        merged = d1.merge(d2)
        assert "a1" in merged.actions
        assert "a2" in merged.actions
        # 默认动作也应保留
        assert "action_listen" in merged.actions

    def test_merge_responses(self):
        d1 = Domain(responses={"r1": [ResponseTemplate(text="a")]})
        d2 = Domain(responses={"r2": [ResponseTemplate(text="b")]})
        merged = d1.merge(d2)
        assert "r1" in merged.responses
        assert "r2" in merged.responses

    def test_merge_flows(self):
        d1 = Domain(flows=["f1", "f2"])
        d2 = Domain(flows=["f2", "f3"])
        merged = d1.merge(d2)
        assert set(merged.flows) == {"f1", "f2", "f3"}


# =============================================================================
# Domain 序列化
# =============================================================================

class TestDomainSerialization:
    """测试 Domain 序列化"""

    def test_to_dict(self, sample_domain):
        d = sample_domain.to_dict()
        assert "slots" in d
        assert "actions" in d
        assert "responses" in d
        assert "flows" in d

    def test_roundtrip(self, sample_domain):
        d = sample_domain.to_dict()
        restored = Domain.from_dict(d)
        assert set(restored.slots.keys()) == set(sample_domain.slots.keys())
        assert restored.flows == sample_domain.flows
