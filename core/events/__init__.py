#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
事件系统包 - 提供应用程序内部通信的事件机制
"""

from core.events.event_bus import EventBus
from core.events.event_types import (
    BaseEvent,
    TaskEvent,
    TaskStateChangedEvent,
    TaskAddedEvent,
    TaskRemovedEvent,
    TaskTimerUpdatedEvent,
    TranscriptionProgressEvent,
    TranscriptionCompletedEvent,
    TranscriptionErrorEvent,
    TranscriptionStartedEvent,
    TaskStartedEvent, # 添加 TaskStartedEvent
    AudioExtractedEvent,
    ModelDownloadErrorEvent,
    EnvironmentEvent,
    EnvironmentStatusEvent,
    WorkerEvent,
    WorkerRegisteredEvent,
    WorkerUnregisteredEvent,
    WorkerProgressEvent,
    WorkerCompletedEvent,
    WorkerCancelledEvent,
    WorkerFailedEvent,
    ErrorEvent,
    RequestAddTasksEvent,
    RequestRemoveTaskEvent,
    RequestClearTasksEvent,
    RequestStartProcessingEvent,
    RequestCancelProcessingEvent,
    TaskAssignedEvent,
    FilesDroppedEvent,
    ModelEvent,
    EventTypes,
    ConfigChangedEvent, # 添加 ConfigChangedEvent
)

# 创建全局事件总线实例
event_bus = EventBus()

__all__ = [
    'event_bus',
    'EventBus',
    'BaseEvent',
    'TaskEvent',
    'TaskStateChangedEvent',
    'TaskAddedEvent',
    'TaskRemovedEvent',
    'TaskTimerUpdatedEvent',
    'TranscriptionProgressEvent',
    'TranscriptionCompletedEvent',
    'TranscriptionErrorEvent',
    'TranscriptionStartedEvent',
    'TaskStartedEvent', # 添加 TaskStartedEvent
    'AudioExtractedEvent',
    'ModelDownloadErrorEvent',
    'EnvironmentEvent',
    'EnvironmentStatusEvent',
    'WorkerEvent',
    'WorkerRegisteredEvent',
    'WorkerUnregisteredEvent',
    'WorkerProgressEvent',
    'WorkerCompletedEvent',
    'WorkerCancelledEvent',
    'WorkerFailedEvent',
    'ErrorEvent',
    'RequestAddTasksEvent',
    'RequestRemoveTaskEvent',
    'RequestClearTasksEvent',
    'RequestStartProcessingEvent',
    'RequestCancelProcessingEvent',
    'TaskAssignedEvent',
    'FilesDroppedEvent',
    'ModelEvent',
    'EventTypes',
    'ConfigChangedEvent', # 添加 ConfigChangedEvent
]