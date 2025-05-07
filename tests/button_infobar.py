#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
带按钮的InfoBar组件

扩展qfluentwidgets的InfoBar，添加按钮功能
"""

from PySide6.QtCore import Qt, Signal, QTimer, QSize, QPoint, Property
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, 
    QPushButton, QGraphicsOpacityEffect, QFrame
)

from qfluentwidgets import (
    InfoBar, InfoBarIcon, InfoBarPosition, 
    isDarkTheme, FluentIconBase, FluentIcon,
    PushButton, TransparentPushButton
)


class ButtonInfoBar(InfoBar):
    """带按钮的InfoBar控件"""
    
    def __init__(
        self,
        icon: InfoBarIcon,
        title: str,
        content: str = None,
        orient: Qt.Orientation = Qt.Horizontal,
        isClosable: bool = False,  # 默认设置为False，不显示关闭按钮
        duration: int = -1,
        position: InfoBarPosition = InfoBarPosition.TOP_RIGHT,
        parent: QWidget = None,
    ):
        """初始化InfoBar

        Parameters
        ----------
        icon: InfoBarIcon
            InfoBar图标样式

        title: str
            标题

        content: str
            内容

        orient: Qt.Orientation
            布局方向

        isClosable: bool
            是否可关闭，默认为False，不显示关闭按钮

        duration: int
            显示的持续时间，单位为毫秒，默认值为-1，表示不会自动关闭，当设置为非负整数时，将在指定的时间后自动关闭

        position: InfoBarPosition
            消息条在容器中的位置

        parent: QWidget
            父控件
        """
        super().__init__(
            icon=icon,
            title=title,
            content=content,
            orient=orient,
            isClosable=isClosable,
            duration=duration,
            position=position,
            parent=parent
        )
        
        self._button = None
        self._buttonLayout = QHBoxLayout()
        self._buttonLayout.setContentsMargins(10, 0, 0, 0)
        self._buttonLayout.setSpacing(8)
        
        # 将按钮布局添加到InfoBar的布局中
        if orient == Qt.Horizontal:
            self.hBoxLayout.addLayout(self._buttonLayout)
        else:
            self.vBoxLayout.addLayout(self._buttonLayout)
    
    def addButton(self, text: str, callback=None, icon: FluentIconBase = None):
        """添加一个按钮到InfoBar

        Parameters
        ----------
        text: str
            按钮文本

        callback: callable
            点击按钮时的回调函数
            
        icon: FluentIconBase
            按钮图标
        """
        button = TransparentPushButton(text, self)
        if icon:
            button.setIcon(icon)
        
        if callback:
            button.clicked.connect(callback)
        
        self._buttonLayout.addWidget(button)
        return button
    
    def addPrimaryButton(self, text: str, callback=None, icon: FluentIconBase = None):
        """添加一个主要按钮到InfoBar (使用蓝色背景)

        Parameters
        ----------
        text: str
            按钮文本

        callback: callable
            点击按钮时的回调函数
            
        icon: FluentIconBase
            按钮图标
        """
        button = PushButton(text, self)
        if icon:
            button.setIcon(icon)
        
        if callback:
            button.clicked.connect(callback)
        
        self._buttonLayout.addWidget(button)
        return button


# 静态方法扩展
def _createButtonInfoBar(cls, icon, title, content, orient, isClosable, duration, position, parent):
    """创建按钮InfoBar的工厂方法"""
    w = ButtonInfoBar(
        icon, title, content, orient, isClosable, duration, position, parent
    )
    w.show()
    return w


def _customButtonInfoBar(icon, title, content, orient=Qt.Horizontal, isClosable=False, 
                         duration=-1, position=InfoBarPosition.TOP_RIGHT, parent=None):
    """创建自定义按钮InfoBar"""
    return _createButtonInfoBar(
        ButtonInfoBar, icon, title, content, orient, isClosable, duration, position, parent
    )


def buttonInfo(title: str, content: str = None, orient=Qt.Horizontal, isClosable=False, 
              duration=-1, position=InfoBarPosition.TOP_RIGHT, parent=None):
    """信息样式的按钮InfoBar"""
    return _customButtonInfoBar(
        InfoBarIcon.INFORMATION, title, content, orient, isClosable, duration, position, parent
    )


def buttonSuccess(title: str, content: str = None, orient=Qt.Horizontal, isClosable=False, 
                 duration=-1, position=InfoBarPosition.TOP_RIGHT, parent=None):
    """成功样式的按钮InfoBar"""
    return _customButtonInfoBar(
        InfoBarIcon.SUCCESS, title, content, orient, isClosable, duration, position, parent
    )


def buttonWarning(title: str, content: str = None, orient=Qt.Horizontal, isClosable=False, 
                 duration=-1, position=InfoBarPosition.TOP_RIGHT, parent=None):
    """警告样式的按钮InfoBar"""
    return _customButtonInfoBar(
        InfoBarIcon.WARNING, title, content, orient, isClosable, duration, position, parent
    )


def buttonError(title: str, content: str = None, orient=Qt.Horizontal, isClosable=False, 
               duration=-1, position=InfoBarPosition.TOP_RIGHT, parent=None):
    """错误样式的按钮InfoBar"""
    return _customButtonInfoBar(
        InfoBarIcon.ERROR, title, content, orient, isClosable, duration, position, parent
    )


# 预设按钮的InfoBar组件函数
def buttonInfoBar(
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
    infoBar = buttonInfo(
        title=title,
        content=content,
        duration=duration,
        position=position,
        parent=parent
    )
    
    # 添加取消按钮
    if cancel_callback is None:
        cancel_callback = lambda: infoBar.close()
    infoBar.addButton(cancel_text, cancel_callback)
    
    # 添加确认按钮
    if confirm_callback is None:
        confirm_callback = lambda: infoBar.close()
    infoBar.addPrimaryButton(confirm_text, confirm_callback, FluentIcon.ACCEPT)
    
    return infoBar


def buttonSuccessBar(
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
    successBar = buttonSuccess(
        title=title,
        content=content,
        duration=duration,
        position=position,
        parent=parent
    )
    
    # 只添加确认按钮
    successBar.addPrimaryButton(confirm_text, lambda: successBar.close())
    
    return successBar


def buttonWarningBar(
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
    warningBar = buttonWarning(
        title=title,
        content=content,
        duration=duration,
        position=position,
        parent=parent
    )
    
    # 添加取消按钮
    warningBar.addButton(cancel_text, lambda: warningBar.close())
    
    # 添加确认按钮
    if confirm_callback is None:
        confirm_callback = lambda: warningBar.close()
    warningBar.addPrimaryButton(confirm_text, confirm_callback, FluentIcon.UPDATE)
    
    return warningBar


def buttonErrorBar(
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
    errorBar = buttonError(
        title=title,
        content=content,
        duration=duration,
        position=position,
        parent=parent
    )
    
    # 添加取消按钮
    errorBar.addButton(cancel_text, lambda: errorBar.close())
    
    # 添加重试按钮
    if retry_callback is None:
        retry_callback = lambda: errorBar.close()
    errorBar.addPrimaryButton(retry_text, retry_callback, FluentIcon.SYNC)
    
    return errorBar


# 直接在main中运行演示程序
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    from qfluentwidgets import FluentWindow, setTheme, Theme, InfoBarPosition
    
    class Demo(FluentWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("按钮InfoBar示例")
            self.resize(800, 600)
            
            # 设置深色主题
            setTheme(Theme.DARK)
            
            # 创建一个带按钮的信息通知
            self.testInfoBar()
            
        def testInfoBar(self):
            """测试带按钮的InfoBar"""
            # 使用预设函数创建信息通知
            buttonInfoBar(
                title="消息通知", 
                content="这是一个预设好按钮的消息通知",
                position=InfoBarPosition.TOP,
                parent=self,
                confirm_callback=lambda: print("确认按钮被点击"),
                cancel_callback=lambda: print("忽略按钮被点击")
            )
            
            # 使用预设函数创建成功通知
            buttonSuccessBar(
                title="操作成功", 
                content="文件已成功保存到指定位置",
                position=InfoBarPosition.TOP,
                parent=self
            )
            
            # 使用预设函数创建警告通知
            buttonWarningBar(
                title="更新提示", 
                content="有新版本可用，建议立即更新",
                position=InfoBarPosition.TOP,
                parent=self,
                confirm_callback=lambda: print("开始更新")
            )
            
            # 使用预设函数创建错误通知
            buttonErrorBar(
                title="连接错误", 
                content="无法连接到服务器，请检查网络连接",
                position=InfoBarPosition.TOP,
                parent=self,
                retry_callback=lambda: print("重试连接")
            )

    # 创建应用
    app = QApplication(sys.argv)
    window = Demo()
    window.show()
    sys.exit(app.exec()) 