# -*- coding: utf-8 -*-
"""
常见问题FAQ Action

处理用户的常见问题查询，如退换货政策、配送时间等。
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from app.agent.actions import Action, ActionResult

logger = logging.getLogger(__name__)

# FAQ数据缓存
_faq_data = None


def load_faq_data() -> List[Dict[str, Any]]:
    """加载FAQ数据"""
    global _faq_data
    if _faq_data is not None:
        return _faq_data

    faq_path = Path(__file__).parent.parent / "data" / "faq.yml"
    if not faq_path.exists():
        logger.warning(f"FAQ file not found: {faq_path}")
        _faq_data = []
        return _faq_data

    try:
        with open(faq_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            _faq_data = data.get("faqs", [])
            logger.info(f"Loaded {len(_faq_data)} FAQ entries")
    except Exception as e:
        logger.error(f"Failed to load FAQ data: {e}")
        _faq_data = []

    return _faq_data


def search_faq(query: str) -> Optional[Dict[str, str]]:
    """
    搜索FAQ，返回最匹配的问题和答案

    Args:
        query: 用户查询

    Returns:
        匹配的FAQ条目，如果没有匹配则返回None
    """
    faqs = load_faq_data()
    if not faqs:
        return None

    query_lower = query.lower()

    # 计算每个FAQ的匹配分数
    best_match = None
    best_score = 0

    for faq in faqs:
        score = 0
        keywords = faq.get("keywords", [])

        # 检查关键词匹配
        for keyword in keywords:
            if keyword in query_lower:
                # 关键词越长，分数越高
                score += len(keyword)

        # 如果有匹配，检查是否是最佳匹配
        if score > best_score:
            best_score = score
            best_match = faq

    # 需要至少匹配一个关键词
    if best_score > 0:
        return best_match

    return None


class ActionFAQ(Action):
    """
    常见问题FAQ Action

    根据用户问题自动匹配FAQ答案。
    """

    @property
    def name(self) -> str:
        return "action_faq"

    async def run(
        self,
        tracker: Any,
        domain: Optional[Any] = None,
        **kwargs: Any,
    ) -> ActionResult:
        result = ActionResult()

        # 获取用户消息
        user_message = ""
        if tracker.latest_message:
            user_message = tracker.latest_message.text

        if not user_message:
            result.add_response("请问您想了解什么？")
            return result

        # 搜索FAQ
        faq_match = search_faq(user_message)

        if faq_match:
            answer = faq_match.get("answer", "").strip()
            question = faq_match.get("question", "")
            result.add_response(answer)
            logger.info(f"FAQ matched: {question}")
        else:
            # 没有匹配的FAQ，返回None让其他策略处理
            result.add_response(None)

        return result
