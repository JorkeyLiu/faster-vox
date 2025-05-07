#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
双精度微调框设置卡片组件 - 用于小数输入设置
"""

from PySide6.QtCore import Qt, Signal

from qfluentwidgets import (SettingCard, FluentIcon, CompactDoubleSpinBox, ConfigItem)


class DoubleSpinBoxSettingCard(SettingCard):
    """小数输入设置卡片"""
    
    # 值变更信号
    valueChanged = Signal(float)

    def __init__(
        self,
        configItem: ConfigItem,
        icon: FluentIcon,
        title: str,
        content: str = None,
        minimum: float = 0.0,
        maximum: float = 1.0,
        decimals: int = 2,
        step: float = 0.1,
        parent=None,
    ):
        """初始化
        
        Args:
            configItem: 配置项
            icon: 图标
            title: 标题
            content: 内容描述
            minimum: 最小值
            maximum: 最大值
            decimals: 小数位数
            step: 步长
            parent: 父部件
        """
        super().__init__(icon, title, content, parent)
        
        # 保存配置项
        self.configItem = configItem

        # 创建CompactDoubleSpinBox
        self.spinBox = CompactDoubleSpinBox(self)
        self.spinBox.setRange(minimum, maximum)
        self.spinBox.setDecimals(decimals)
        self.spinBox.setMinimumWidth(60)
        self.spinBox.setSingleStep(step)
        self.spinBox.setValue(configItem.value)

        # 添加到布局
        self.hBoxLayout.addWidget(self.spinBox, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(8)

        # 连接信号
        self.spinBox.valueChanged.connect(self.__onValueChanged)
    
    def __onValueChanged(self, value: float):
        """数值改变时的槽函数"""
        self.configItem.value = value
        self.valueChanged.emit(value)

    def setValue(self, value: float):
        """设置数值"""
        if value != self.configItem.value:
            self.configItem.value = value
            self.spinBox.setValue(value)
    
    def value(self) -> float:
        """获取当前数值"""
        return self.configItem.value 