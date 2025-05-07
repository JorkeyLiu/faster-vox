#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
带按钮的InfoBar组件

扩展qfluentwidgets的InfoBar，添加四种预设样式的带按钮通知
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout

from qfluentwidgets import (
    InfoBar, InfoBarIcon, InfoBarPosition, 
    FluentIcon, PushButton, TransparentPushButton
)


class ButtonInfoBar:
    """带按钮的InfoBar辅助类，提供四种预设样式"""
    
    @staticmethod
    def _createBaseInfoBar(
        icon: InfoBarIcon,
        title: str,
        content: str = None,
        duration: int = -1,
        position: InfoBarPosition = InfoBarPosition.TOP,
        parent: QWidget = None
    ):
        """创建基础InfoBar
        
        Parameters
        ----------
        icon: InfoBarIcon
            通知图标
        title: str
            标题
        content: str
            内容
        duration: int
            显示持续时间，-1表示不自动关闭
        position: InfoBarPosition
            显示位置
        parent: QWidget
            父控件
        """
        infoBar = InfoBar(
            icon=icon,
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=False,
            duration=duration,
            position=position,
            parent=parent
        )
        
        # 创建按钮布局
        buttonLayout = QHBoxLayout()
        buttonLayout.setContentsMargins(10, 0, 0, 0)
        buttonLayout.setSpacing(8)
        infoBar.hBoxLayout.addLayout(buttonLayout)
        
        return infoBar, buttonLayout
    
    @classmethod
    def info(
        cls,
        title: str, 
        content: str = None, 
        duration: int = -1, 
        position: InfoBarPosition = InfoBarPosition.TOP,
        parent: QWidget = None, 
        confirm_text: str = "确认", 
        confirm_callback = None,
        cancel_text: str = "忽略", 
        cancel_callback = None
    ):
        """
        创建预设好按钮的信息样式InfoBar
        
        Parameters
        ----------
        title: str
            标题
        content: str
            内容
        duration: int
            显示持续时间，-1表示不自动关闭
        position: InfoBarPosition
            显示位置
        parent: QWidget
            父控件
        confirm_text: str
            确认按钮文本，默认为"确认"
        confirm_callback: callable
            确认按钮回调函数，默认为关闭通知
        cancel_text: str
            取消按钮文本，默认为"忽略"
        cancel_callback: callable
            取消按钮回调函数，默认为关闭通知
        """
        # 创建基础InfoBar
        infoBar, buttonLayout = cls._createBaseInfoBar(
            icon=InfoBarIcon.INFORMATION,
            title=title,
            content=content,
            duration=duration,
            position=position,
            parent=parent
        )
        
        # 添加取消按钮
        cancelButton = TransparentPushButton(cancel_text, infoBar)
        if cancel_callback is None:
            cancel_callback = lambda: infoBar.close()
        cancelButton.clicked.connect(cancel_callback)
        buttonLayout.addWidget(cancelButton)
        
        # 添加确认按钮
        confirmButton = PushButton(confirm_text, infoBar)
        confirmButton.setIcon(FluentIcon.ACCEPT)
        if confirm_callback is None:
            confirm_callback = lambda: infoBar.close()
        confirmButton.clicked.connect(confirm_callback)
        buttonLayout.addWidget(confirmButton)
        
        infoBar.show()
        return infoBar
    
    @classmethod
    def success(
        cls,
        title: str, 
        content: str = None, 
        duration: int = -1, 
        position: InfoBarPosition = InfoBarPosition.TOP,
        parent: QWidget = None, 
        confirm_text: str = "确定"
    ):
        """
        创建预设好按钮的成功样式InfoBar，只有一个确认按钮
        
        Parameters
        ----------
        title: str
            标题
        content: str
            内容
        duration: int
            显示持续时间，-1表示不自动关闭
        position: InfoBarPosition
            显示位置
        parent: QWidget
            父控件
        confirm_text: str
            确认按钮文本，默认为"确定"
        """
        # 创建基础InfoBar
        successBar, buttonLayout = cls._createBaseInfoBar(
            icon=InfoBarIcon.SUCCESS,
            title=title,
            content=content,
            duration=duration,
            position=position,
            parent=parent
        )
        
        # 只添加确认按钮
        confirmButton = PushButton(confirm_text, successBar)
        confirmButton.clicked.connect(lambda: successBar.close())
        buttonLayout.addWidget(confirmButton)
        
        successBar.show()
        return successBar
    
    @classmethod
    def warning(
        cls,
        title: str, 
        content: str = None, 
        duration: int = -1, 
        position: InfoBarPosition = InfoBarPosition.TOP,
        parent: QWidget = None, 
        confirm_text: str = "立即更新", 
        confirm_callback = None,
        cancel_text: str = "稍后提醒"
    ):
        """
        创建预设好按钮的警告样式InfoBar
        
        Parameters
        ----------
        title: str
            标题
        content: str
            内容
        duration: int
            显示持续时间，-1表示不自动关闭
        position: InfoBarPosition
            显示位置
        parent: QWidget
            父控件
        confirm_text: str
            确认按钮文本，默认为"立即更新"
        confirm_callback: callable
            确认按钮回调函数，不指定则只关闭通知
        cancel_text: str
            取消按钮文本，默认为"稍后提醒"
        """
        # 创建基础InfoBar
        warningBar, buttonLayout = cls._createBaseInfoBar(
            icon=InfoBarIcon.WARNING,
            title=title,
            content=content,
            duration=duration,
            position=position,
            parent=parent
        )
        
        # 添加取消按钮
        cancelButton = TransparentPushButton(cancel_text, warningBar)
        cancelButton.clicked.connect(lambda: warningBar.close())
        buttonLayout.addWidget(cancelButton)
        
        # 添加确认按钮
        confirmButton = PushButton(confirm_text, warningBar)
        confirmButton.setIcon(FluentIcon.UPDATE)
        if confirm_callback is None:
            confirm_callback = lambda: warningBar.close()
        confirmButton.clicked.connect(confirm_callback)
        buttonLayout.addWidget(confirmButton)
        
        warningBar.show()
        return warningBar
    
    @classmethod
    def error(
        cls,
        title: str, 
        content: str = None, 
        duration: int = -1, 
        position: InfoBarPosition = InfoBarPosition.TOP,
        parent: QWidget = None, 
        retry_text: str = "重试", 
        retry_callback = None,
        cancel_text: str = "取消"
    ):
        """
        创建预设好按钮的错误样式InfoBar
        
        Parameters
        ----------
        title: str
            标题
        content: str
            内容
        duration: int
            显示持续时间，-1表示不自动关闭
        position: InfoBarPosition
            显示位置
        parent: QWidget
            父控件
        retry_text: str
            重试按钮文本，默认为"重试"
        retry_callback: callable
            重试按钮回调函数，不指定则只关闭通知
        cancel_text: str
            取消按钮文本，默认为"取消"
        """
        # 创建基础InfoBar
        errorBar, buttonLayout = cls._createBaseInfoBar(
            icon=InfoBarIcon.ERROR,
            title=title,
            content=content,
            duration=duration,
            position=position,
            parent=parent
        )
        
        # 添加取消按钮
        cancelButton = TransparentPushButton(cancel_text, errorBar)
        cancelButton.clicked.connect(lambda: errorBar.close())
        buttonLayout.addWidget(cancelButton)
        
        # 添加重试按钮
        retryButton = PushButton(retry_text, errorBar)
        retryButton.setIcon(FluentIcon.SYNC)
        if retry_callback is None:
            retry_callback = lambda: errorBar.close()
        retryButton.clicked.connect(retry_callback)
        buttonLayout.addWidget(retryButton)
        
        errorBar.show()
        return errorBar 