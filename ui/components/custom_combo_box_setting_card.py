#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
自定义下拉框设置卡 - 支持自定义选项转换
"""

from qfluentwidgets import (
    ComboBoxSettingCard, OptionsConfigItem
)


class CustomComboBoxSettingCard(ComboBoxSettingCard):
    """自定义下拉框设置卡，支持自定义选项转换"""
    
    def __init__(self, configItem, icon, title, content=None, texts=None, parent=None):
        """初始化
        
        Args:
            configItem: 配置项
            icon: 图标
            title: 标题
            content: 内容
            texts: 文本列表
            parent: 父组件
        """
        self.texts = texts or []
        self.configItem = configItem
        self.optionToText = {}
        
        # 如果是OptionsConfigItem，使用其option_to_text方法
        if isinstance(configItem, OptionsConfigItem):
            for text in self.texts:
                option = configItem.text_to_option(text)
                self.optionToText[option] = text
        else:
            # 否则使用默认的映射
            for i, text in enumerate(self.texts):
                self.optionToText[i] = text
        
        # 正确调用父类构造函数
        super().__init__(configItem, icon, title, content, parent)
        
        # 清空并重新添加项目
        self.comboBox.clear()
        for text in self.texts:
            self.comboBox.addItem(text)
        
        # 设置当前值
        if isinstance(configItem, OptionsConfigItem):
            current_value = configItem.value
            for i, text in enumerate(self.texts):
                option = configItem.text_to_option(text)
                if option == current_value:
                    self.comboBox.setCurrentIndex(i)
                    break
        else:
            self.comboBox.setCurrentIndex(configItem.value)
    
    def _onCurrentIndexChanged(self, index: int):
        """下拉框索引变更事件
        
        Args:
            index: 新的索引
        """
        if isinstance(self.configItem, OptionsConfigItem):
            option = self.configItem.text_to_option(self.texts[index])
            self.configItem.value = option
        else:
            self.configItem.value = index
        
        self.valueChanged.emit(self.configItem.value) 