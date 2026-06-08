# -*- coding: utf-8 -*-
"""
电商客服Demo Actions模块

导出所有自定义Action供app框架使用。
"""

from .action_order import (
    ActionAskOrderId,
    ActionGetOrderDetail,
    ActionAskReceiveId,
    ActionAskReceiveProvince,
    ActionAskReceiveCity,
    ActionAskReceiveDistrict,
    ActionAskSetReceiveInfo,
    ActionCancelOrder,
    ActionUrgeShipping,
    ActionConfirmReceipt,
)
from .action_logistics import (
    ActionGetLogisticsCompanys,
    ActionGetLogisticsInfo,
)
from .action_postsale import (
    ActionAskOrderIdAfterDelivered,
    ActionCheckPostsaleEligible,
    ActionAskPostsaleReason,
    ActionApplyPostsale,
)
from .action_faq import ActionFAQ

# 导出所有Action类
__all__ = [
    # 订单相关
    "ActionAskOrderId",
    "ActionGetOrderDetail",
    "ActionAskReceiveId",
    "ActionAskReceiveProvince",
    "ActionAskReceiveCity",
    "ActionAskReceiveDistrict",
    "ActionAskSetReceiveInfo",
    "ActionCancelOrder",
    "ActionUrgeShipping",
    "ActionConfirmReceipt",
    # 物流相关
    "ActionGetLogisticsCompanys",
    "ActionGetLogisticsInfo",
    # 售后相关
    "ActionAskOrderIdAfterDelivered",
    "ActionCheckPostsaleEligible",
    "ActionAskPostsaleReason",
    "ActionApplyPostsale",
    # FAQ相关
    "ActionFAQ",
]
