# -*- coding: utf-8 -*-
"""
app API模块

提供基于FastAPI的Web服务接口。
"""

from app.api.server import AtguiguServer, create_app

__all__ = [
    "AtguiguServer",
    "create_app",
]
