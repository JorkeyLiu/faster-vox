# 错误处理指南

## 错误处理流程

在Faster-Vox项目中，我们使用统一的错误处理流程：

1. 服务捕获异常/错误
2. 使用ErrorHandlingService处理错误
3. 根据错误优先级和可见性，自动通知用户或仅记录日志

## 如何处理错误

### 在服务中处理异常

```python
try:
    # 可能引发异常的代码
    do_something()
except Exception as e:
    if self.error_service:
        # 使用异常处理方法
        self.error_service.handle_exception(
            e,
            ErrorCategory.APPROPRIATE_CATEGORY,
            ErrorPriority.APPROPRIATE_PRIORITY,
            "错误源标识",
            user_visible=True  # 设置为True以显示给用户
        )
```

### 直接创建错误信息

```python
if some_error_condition:
    if self.error_service:
        # 创建错误信息对象
        error_info = ErrorInfo(
            message="错误描述",
            category=ErrorCategory.APPROPRIATE_CATEGORY,
            priority=ErrorPriority.APPROPRIATE_PRIORITY,
            code="ERROR_CODE",
            user_visible=True  # 设置为True以显示给用户
        )
        self.error_service.handle_error(error_info)
```

## 错误分类与优先级

### 错误类别(ErrorCategory)

错误类别用于区分错误的来源和类型：

- `ErrorCategory.GENERAL`: 一般错误
- `ErrorCategory.AUDIO`: 音频处理相关错误
- `ErrorCategory.MODEL`: 模型相关错误
- `ErrorCategory.TRANSCRIPTION`: 转录相关错误
- `ErrorCategory.ENVIRONMENT`: 环境相关错误
- `ErrorCategory.CONFIGURATION`: 配置相关错误

### 错误优先级(ErrorPriority)

错误优先级决定错误的严重程度和处理方式：

- `ErrorPriority.CRITICAL`: 严重错误，应用程序无法继续运行
- `ErrorPriority.HIGH`: 高优先级错误，功能受到严重影响
- `ErrorPriority.MEDIUM`: 中等优先级错误，部分功能可能受影响
- `ErrorPriority.LOW`: 低优先级错误，不影响主要功能
- `ErrorPriority.DEBUG`: 调试级别错误，只用于开发时排查问题

## 用户通知

错误处理服务会自动处理用户通知：

- 设置`user_visible=True`的错误会自动通过NotificationService显示给用户
- 高优先级和严重错误会显示更详细的错误信息
- 低优先级错误只会记录日志，除非明确设置为用户可见

## 错误处理的最佳实践

1. **使用适当的错误类别和优先级**：确保错误分类准确，便于排查和处理
2. **提供有意义的错误信息**：错误消息应该清晰描述问题，便于用户理解
3. **仅在必要时显示给用户**：避免过多的技术错误信息困扰用户
4. **记录详细的错误上下文**：在错误详情中包含有助于调试的信息
5. **避免重复错误处理**：不要同时使用多种错误处理机制处理同一个错误

## 错误处理流程图

```
异常发生
    │
    ▼
捕获异常
    │
    ▼
调用ErrorHandlingService
    │
    ├───► 记录错误历史
    │
    ├───► 记录日志
    │
    ├───► 发送错误信号
    │
    ├───► 调用注册的错误处理器
    │
    └───► 如果用户可见，发送通知
``` 