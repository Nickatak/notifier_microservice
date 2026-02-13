"""Shared type aliases for the notification package."""

from __future__ import annotations

from typing import Any, Callable, Mapping

Event = Mapping[str, Any]
EventDict = dict[str, Any]
ChannelResult = dict[str, Any]
ProcessingResult = dict[str, Any]

SendEmailFn = Callable[..., None]
SendSMSFn = Callable[..., None]

