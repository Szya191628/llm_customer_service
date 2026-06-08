# -*- coding: utf-8 -*-
"""
通道模块

提供与用户交互的通道（Channel）实现。
"""

from app.channels.base_channel import (
    InputChannel,
    OutputChannel,
    UserMessage,
    CollectingOutputChannel,
)
from app.channels.rest_channel import RestChannel
from app.channels.socketio_channel import SocketIOChannel
from app.channels.console_channel import ConsoleChannel
from app.channels.inspect_proxy import InspectProxy

__all__ = [
    "InputChannel",
    "OutputChannel",
    "UserMessage",
    "CollectingOutputChannel",
    "RestChannel",
    "SocketIOChannel",
    "ConsoleChannel",
    "InspectProxy",
]
