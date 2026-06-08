# -*- coding: utf-8 -*-
"""
槽位系统测试

覆盖：各类型槽位、类型验证、序列化、工厂函数、mapping_type。
"""

import pytest
from app.core.slots import (
    Slot,
    TextSlot,
    BoolSlot,
    FloatSlot,
    ListSlot,
    CategoricalSlot,
    AnySlot,
    SlotMappingType,
    SLOT_TYPE_MAP,
    create_slot,
)
from app.shared.exceptions import InvalidSlotValueError


# =============================================================================
# 槽位创建
# =============================================================================

class TestSlotCreation:
    """测试各类槽位的创建"""

    def test_text_slot(self):
        slot = TextSlot(name="city")
        assert slot.name == "city"
        assert slot.type_name == "text"
        assert slot.value is None

    def test_bool_slot(self):
        slot = BoolSlot(name="is_vip")
        assert slot.type_name == "bool"

    def test_float_slot(self):
        slot = FloatSlot(name="price", min_value=0.0, max_value=1000.0)
        assert slot.type_name == "float"
        assert slot.min_value == 0.0
        assert slot.max_value == 1000.0

    def test_list_slot(self):
        slot = ListSlot(name="items")
        assert slot.type_name == "list"
        assert slot.value == []  # 初始值为空列表

    def test_categorical_slot(self):
        slot = CategoricalSlot(name="size", values=["S", "M", "L"])
        assert slot.type_name == "categorical"
        assert slot.values == ["S", "M", "L"]

    def test_any_slot(self):
        slot = AnySlot(name="data")
        assert slot.type_name == "any"


# =============================================================================
# 槽位值验证
# =============================================================================

class TestSlotValidation:
    """测试槽位值验证"""

    def test_text_slot_accepts_string(self):
        slot = TextSlot(name="city")
        slot.value = "北京"
        assert slot.value == "北京"

    def test_text_slot_rejects_non_string(self):
        slot = TextSlot(name="city")
        with pytest.raises(InvalidSlotValueError):
            slot.value = 123

    def test_bool_slot_accepts_bool(self):
        slot = BoolSlot(name="flag")
        slot.value = True
        assert slot.value is True
        slot.value = False
        assert slot.value is False

    def test_bool_slot_rejects_non_bool(self):
        slot = BoolSlot(name="flag")
        with pytest.raises(InvalidSlotValueError):
            slot.value = "yes"

    def test_float_slot_accepts_number(self):
        slot = FloatSlot(name="price")
        slot.value = 99.9
        assert slot.value == 99.9
        slot.value = 100  # int 也接受
        assert slot.value == 100

    def test_float_slot_rejects_string(self):
        slot = FloatSlot(name="price")
        with pytest.raises(InvalidSlotValueError):
            slot.value = "abc"

    def test_float_slot_respects_min_value(self):
        slot = FloatSlot(name="price", min_value=0.0)
        with pytest.raises(InvalidSlotValueError):
            slot.value = -1.0

    def test_float_slot_respects_max_value(self):
        slot = FloatSlot(name="price", max_value=100.0)
        with pytest.raises(InvalidSlotValueError):
            slot.value = 200.0

    def test_list_slot_accepts_list(self):
        slot = ListSlot(name="items")
        slot.value = ["a", "b"]
        assert slot.value == ["a", "b"]

    def test_list_slot_rejects_non_list(self):
        slot = ListSlot(name="items")
        with pytest.raises(InvalidSlotValueError):
            slot.value = "not a list"

    def test_list_slot_append(self):
        slot = ListSlot(name="items")
        slot.append("item1")
        slot.append("item2")
        assert slot.value == ["item1", "item2"]

    def test_categorical_slot_accepts_valid_value(self):
        slot = CategoricalSlot(name="size", values=["S", "M", "L"])
        slot.value = "M"
        assert slot.value == "M"

    def test_categorical_slot_rejects_invalid_value(self):
        slot = CategoricalSlot(name="size", values=["S", "M", "L"])
        with pytest.raises(InvalidSlotValueError):
            slot.value = "XL"

    def test_categorical_slot_empty_values_accepts_any(self):
        slot = CategoricalSlot(name="open")
        slot.value = "anything"
        assert slot.value == "anything"

    def test_any_slot_accepts_everything(self):
        slot = AnySlot(name="data")
        slot.value = "text"
        assert slot.value == "text"
        slot.value = 42
        assert slot.value == 42
        slot.value = [1, 2]
        assert slot.value == [1, 2]
        slot.value = {"key": "val"}
        assert slot.value == {"key": "val"}

    def test_all_slots_accept_none(self):
        """所有类型槽位都应接受 None"""
        for slot_class in [TextSlot, BoolSlot, FloatSlot, ListSlot, CategoricalSlot, AnySlot]:
            slot = slot_class(name="test")
            slot.value = None
            assert slot.value is None


# =============================================================================
# 槽位辅助方法
# =============================================================================

class TestSlotMethods:
    """测试槽位辅助方法"""

    def test_reset(self):
        slot = TextSlot(name="city", initial_value="默认城市")
        slot.value = "上海"
        slot.reset()
        assert slot.value == "默认城市"

    def test_reset_to_none(self):
        slot = TextSlot(name="city")
        slot.value = "上海"
        slot.reset()
        assert slot.value is None

    def test_is_set_true(self):
        slot = TextSlot(name="city")
        slot.value = "北京"
        assert slot.is_set() is True

    def test_is_set_false(self):
        slot = TextSlot(name="city")
        assert slot.is_set() is False

    def test_is_from_llm(self):
        slot = create_slot("x", "text", mapping_type="from_llm")
        assert slot.is_from_llm() is True
        assert slot.is_controlled() is False

    def test_is_controlled(self):
        slot = create_slot("x", "text", mapping_type="controlled")
        assert slot.is_controlled() is True
        assert slot.is_from_llm() is False

    def test_repr(self):
        slot = TextSlot(name="city")
        slot.value = "北京"
        r = repr(slot)
        assert "TextSlot" in r
        assert "city" in r
        assert "北京" in r


# =============================================================================
# 序列化
# =============================================================================

class TestSlotSerialization:
    """测试槽位序列化和反序列化"""

    def test_to_dict(self):
        slot = TextSlot(name="city", initial_value="默认", description="城市名称")
        slot.value = "上海"
        d = slot.to_dict()
        assert d["name"] == "city"
        assert d["type"] == "text"
        assert d["value"] == "上海"
        assert d["initial_value"] == "默认"
        assert d["description"] == "城市名称"
        assert d["mapping_type"] == "from_llm"

    def test_from_dict_text(self):
        data = {"name": "city", "type": "text", "value": "北京", "initial_value": None}
        slot = Slot.from_dict(data)
        assert isinstance(slot, TextSlot)
        assert slot.value == "北京"

    def test_from_dict_bool(self):
        data = {"name": "flag", "type": "bool", "value": True}
        slot = Slot.from_dict(data)
        assert isinstance(slot, BoolSlot)
        assert slot.value is True

    def test_from_dict_categorical(self):
        data = {"name": "size", "type": "categorical", "values": ["S", "M", "L"], "value": "M"}
        slot = Slot.from_dict(data)
        assert isinstance(slot, CategoricalSlot)
        assert slot.value == "M"

    def test_roundtrip(self):
        """序列化再反序列化应保持一致"""
        original = FloatSlot(name="price", min_value=0, max_value=999, initial_value=10)
        original.value = 88.5
        d = original.to_dict()
        restored = Slot.from_dict(d)
        assert isinstance(restored, FloatSlot)
        assert restored.value == 88.5
        assert restored.name == "price"


# =============================================================================
# 工厂函数
# =============================================================================

class TestCreateSlot:
    """测试 create_slot 工厂函数"""

    def test_create_text_slot(self):
        slot = create_slot("city", "text")
        assert isinstance(slot, TextSlot)

    def test_create_bool_slot(self):
        slot = create_slot("flag", "bool")
        assert isinstance(slot, BoolSlot)

    def test_create_float_slot(self):
        slot = create_slot("price", "float")
        assert isinstance(slot, FloatSlot)

    def test_create_list_slot(self):
        slot = create_slot("items", "list")
        assert isinstance(slot, ListSlot)

    def test_create_categorical_slot(self):
        slot = create_slot("size", "categorical", values=["S", "M"])
        assert isinstance(slot, CategoricalSlot)

    def test_create_any_slot(self):
        slot = create_slot("data", "any")
        assert isinstance(slot, AnySlot)

    def test_create_unknown_type_defaults_to_any(self):
        slot = create_slot("x", "unknown_type")
        assert isinstance(slot, AnySlot)

    def test_create_slot_with_description(self):
        slot = create_slot("city", "text", description="用户所在城市")
        assert slot.description == "用户所在城市"

    def test_create_slot_with_mapping_type_string(self):
        slot = create_slot("x", "text", mapping_type="controlled")
        assert slot.mapping_type == SlotMappingType.CONTROLLED


# =============================================================================
# SlotMappingType
# =============================================================================

class TestSlotMappingType:
    """测试映射类型枚举"""

    def test_from_llm_value(self):
        assert SlotMappingType.FROM_LLM.value == "from_llm"

    def test_controlled_value(self):
        assert SlotMappingType.CONTROLLED.value == "controlled"

    def test_from_string(self):
        assert SlotMappingType("from_llm") == SlotMappingType.FROM_LLM
        assert SlotMappingType("controlled") == SlotMappingType.CONTROLLED


# =============================================================================
# SLOT_TYPE_MAP
# =============================================================================

class TestSlotTypeMap:
    """测试类型映射表"""

    def test_all_types_registered(self):
        expected = {"text", "bool", "float", "list", "categorical", "any"}
        assert set(SLOT_TYPE_MAP.keys()) == expected

    def test_map_values_are_slot_subclasses(self):
        for cls in SLOT_TYPE_MAP.values():
            assert issubclass(cls, Slot)
