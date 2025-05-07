#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
转录查看器 - 负责管理转录文本的显示
"""

import datetime
from typing import Optional
import time

from PySide6.QtCore import Qt
from qfluentwidgets import TextBrowser
from PySide6.QtGui import QTextCursor

from core.models.config import Language
from core.events.event_types import EventTypes, TranscriptionStartedEvent
from core.models.transcription_model import TranscriptionParameters
from core.events import event_bus


class TranscriptViewer:
    """转录查看器，负责管理转录文本的显示"""
    
    def __init__(self, text_browser: TextBrowser):
        """初始化转录查看器
        
        Args:
            text_browser: 文本浏览器控件实例
        """
        self.text_browser = text_browser

        # 仅允许接收键盘焦点以支持滚动，但不允许鼠标选择
        self.text_browser.setFocusPolicy(Qt.TabFocus)
        
        # 订阅转录开始事件
        event_bus.subscribe(EventTypes.TRANSCRIPTION_STARTED, self._handle_transcription_started)
        
        # 订阅转录错误事件，在转录日志中显示错误信息
        event_bus.subscribe(EventTypes.TRANSCRIPTION_ERROR, self._handle_transcription_error)
    
    def _handle_transcription_started(self, event: TranscriptionStartedEvent):
        """处理转录开始事件
        
        Args:
            event: 转录开始事件数据
        """
        # 显示模型信息
        self._display_model_info(event.parameters)
    
    def _handle_transcription_error(self, event):
        """处理转录错误事件
        
        Args:
            event: 转录错误事件数据
        """
        # 显示错误信息
        error_message = f"转录失败: {event.error}"
        if hasattr(event, 'details') and event.details:
            # 如果有详细信息，添加到错误消息中
            if isinstance(event.details, dict) and 'source' in event.details:
                error_message += f" (来源: {event.details['source']})"
        
        # 添加错误消息到转录日志
        self.add_error_message(error_message)
    
    def _display_model_info(self, params: TranscriptionParameters):
        """显示模型信息
        
        Args:
            params: 转录参数
        """
        # 获取当前时间
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 语言显示
        language_str = params.language or "auto"
        language_display = Language.display_name(language_str)
        task_display = "翻译" if params.task == "translate" else "转录"
        
        # 基本信息
        # start_info = f"<span style='color:#888888;'>[{current_time}]</span> <span style='color:#888888;'>开始转录处理</span>"
        # self.text_browser.append(start_info)
        
        # 基本参数
        basic_params = f"<span style='color:#888888;'>[{current_time}]</span> <span style='color:#888888;'>基本参数: 模型={params.model_name}, 语言={language_display}, 任务={task_display}, 输出格式={params.output_format}</span>"
        self.text_browser.append(basic_params)
        
        # 高级参数
        advanced_params = f"<span style='color:#888888;'>[{current_time}]</span> <span style='color:#888888;'>高级参数: 波束大小={params.beam_size}, VAD过滤={params.vad_filter}, 单词时间戳={params.word_timestamps}, 标点符号={params.include_punctuation}</span>"
        self.text_browser.append(advanced_params)
        
        # 技术参数
        tech_params = f"<span style='color:#888888;'>[{current_time}]</span> <span style='color:#888888;'>技术参数: 转录设备={params.device}, 计算精度={params.compute_type}, 温度={params.temperature}, 条件文本={params.condition_on_previous_text}, 无语音阈值={params.no_speech_threshold}</span>"
        self.text_browser.append(tech_params)
        
    def add_transcript_text(self, text: str, start_time: Optional[float] = None, end_time: Optional[float] = None):
        """添加转录文本
        
        Args:
            text: 转录文本
            start_time: 片段开始时间（秒），可选
            end_time: 片段结束时间（秒），可选
            task_id: 任务ID，可选
        """
        # 获取当前时间
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 检查是否是初始消息或音频信息
        is_initial_message = (
            "正在加载音频并准备转录" in text or 
            "已从视频中提取音频" in text or 
            "正在加载模型并处理音频" in text or 
            "音频信息:" in text
        )
        
        # 格式化转录文本
        if start_time is not None and end_time is not None and not is_initial_message:
            # 添加音频内时间戳（仅对实际转录内容）
            timestamp_str = f"<span style='color:#888888;'>[{start_time:.2f}s --> {end_time:.2f}s]</span>"
            display_text = f"<span style='color:#888888;'>[{current_time}]</span> {timestamp_str} {text}"
        else:
            # 如果没有提供时间戳或是初始消息，只显示当前时间
            display_text = f"<span style='color:#888888;'>[{current_time}]</span> <span style='color:#888888;'>{text}</span>"
        
        # 添加到文本浏览器
        self.text_browser.append(display_text)
        
        # 滚动到底部
        self.text_browser.verticalScrollBar().setValue(
            self.text_browser.verticalScrollBar().maximum()
        )
    
    def add_system_message(self, text: str):
        """添加系统消息
        
        Args:
            text: 系统消息文本
        """
        # 获取当前时间
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 格式化为系统消息
        display_text = f"<span style='color:#888888;'>[{current_time}]</span> <span style='color:#888888;'>{text}</span>"
        
        # 添加到文本浏览器
        self.text_browser.append(display_text)
        
        # 滚动到底部
        self.text_browser.verticalScrollBar().setValue(
            self.text_browser.verticalScrollBar().maximum()
        )
    
    def add_error_message(self, text: str):
        """添加错误消息
        
        Args:
            text: 错误消息文本
        """
        # 获取当前时间
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 格式化为错误消息
        display_text = f"<span style='color:#888888;'>[{current_time}]</span> <span style='color:#d83b01;'>{text}</span>"
        
        # 添加到文本浏览器
        self.text_browser.append(display_text)
        
        # 滚动到底部
        self.text_browser.verticalScrollBar().setValue(
            self.text_browser.verticalScrollBar().maximum()
        )
    
    def add_success_message(self, text: str):
        """添加成功消息
        
        Args:
            text: 成功消息文本
        """
        # 获取当前时间
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 格式化为成功消息
        display_text = f"<span style='color:#888888;'>[{current_time}]</span> <span style='color:#107c10;'>{text}</span>"
        
        # 添加到文本浏览器
        self.text_browser.append(display_text)
        
        # 滚动到底部
        self.text_browser.verticalScrollBar().setValue(
            self.text_browser.verticalScrollBar().maximum()
        )
    
    def clear_display(self):
        """清空显示内容"""
        self.text_browser.clear()
        
    def append_viewer_text(self, text: str):
        """更新文本浏览器中最后一行文本
        
        Args:
            text: 要更新的文本内容
        """
        # 获取当前时间
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 格式化为系统消息
        display_text = f"<span style='color:#888888;'>[{current_time}]</span> <span style='color:#0078d4;'>{text}</span>"
        
        # 获取文本浏览器的文档
        document = self.text_browser.document()
        cursor = self.text_browser.textCursor()
        
        # 保存当前滚动位置
        scrollbar = self.text_browser.verticalScrollBar()
        was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 4
        
        # 检查是否有内容
        if document.isEmpty():
            # 如果文档为空，直接添加新内容
            self.text_browser.append(display_text)
            return
        
        # 移动到文档末尾
        cursor.movePosition(QTextCursor.End)
        
        # 更新最后一行
        cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertHtml(display_text)
        
        # 如果之前在底部，则保持滚动到底部
        if was_at_bottom:
            scrollbar.setValue(scrollbar.maximum())

    def __del__(self):
        """析构函数，取消事件订阅"""
        try:
            event_bus.unsubscribe(EventTypes.TRANSCRIPTION_STARTED, self._handle_transcription_started)
            event_bus.unsubscribe(EventTypes.TRANSCRIPTION_ERROR, self._handle_transcription_error)
        except Exception:
            pass  # 忽略取消订阅时可能出现的错误

    def close(self):
        """关闭转录查看器，取消事件订阅"""
        event_bus.unsubscribe(EventTypes.TRANSCRIPTION_STARTED, self._handle_transcription_started)
        event_bus.unsubscribe(EventTypes.TRANSCRIPTION_ERROR, self._handle_transcription_error)