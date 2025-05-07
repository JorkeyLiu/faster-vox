#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ButtonInfoBar组件测试脚本
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentWindow, setTheme, Theme, InfoBarPosition, FluentIcon

from ui.components.button_infobar import ButtonInfoBar


class ButtonInfoBarDemo(FluentWindow):
    """ButtonInfoBar组件测试窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("带按钮的InfoBar示例")
        self.resize(800, 600)
        
        # 设置深色主题
        setTheme(Theme.DARK)
        
        # 创建各种通知样式的示例
        self.showExamples()
    
    def showExamples(self):
        """展示各种通知样式的示例"""
        # 信息通知示例
        ButtonInfoBar.info(
            title="信息通知", 
            content="这是一个预设好按钮的信息通知",
            position=InfoBarPosition.TOP,
            parent=self,
            confirm_callback=lambda: print("信息通知-确认按钮被点击"),
            cancel_callback=lambda: print("信息通知-忽略按钮被点击")
        )
        
        # 成功通知示例
        ButtonInfoBar.success(
            title="操作成功", 
            content="文件已成功保存到指定位置",
            position=InfoBarPosition.TOP,
            parent=self
        )
        
        # 警告通知示例
        ButtonInfoBar.warning(
            title="更新提示", 
            content="有新版本可用，建议立即更新",
            position=InfoBarPosition.TOP,
            parent=self,
            confirm_callback=lambda: print("警告通知-开始更新")
        )
        
        # 错误通知示例
        ButtonInfoBar.error(
            title="连接错误", 
            content="无法连接到服务器，请检查网络连接",
            position=InfoBarPosition.TOP,
            parent=self,
            retry_callback=lambda: print("错误通知-重试连接")
        )
        
        # 自定义按钮文本示例
        ButtonInfoBar.warning(
            title="自定义按钮示例", 
            content="您可以自定义按钮文本",
            position=InfoBarPosition.TOP,
            parent=self,
            confirm_text="立即处理",
            confirm_callback=lambda: print("立即处理"),
            cancel_text="不再提示"
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ButtonInfoBarDemo()
    window.show()
    sys.exit(app.exec()) 