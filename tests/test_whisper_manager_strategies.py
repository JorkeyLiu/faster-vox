import sys
import os

# 动态添加项目根目录到sys.path，确保可以导入core模块
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import os
import sys
import tempfile
import time
import shutil
import subprocess
from core.whisper_manager import PrecompiledTranscriptionStrategy, TranscriptionContext
from core.models.transcription_model import TranscriptionParameters
from core.models.config import WHISPER_EXE_PATH

def create_fake_precompiled_app(script_path):
    """
    创建一个模拟的预编译应用脚本，模拟输出进度信息
    """
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(
            '#!/usr/bin/env python\n'
            'import sys\n'
            'import time\n'
            'import json\n'
            '\n'
            '# 解析--output-json参数\n'
            'output_path = None\n'
            'for idx, arg in enumerate(sys.argv):\n'
            '    if arg == "--output-json" and idx + 1 < len(sys.argv):\n'
            '        output_path = sys.argv[idx + 1]\n'
            '        break\n'
            '\n'
            'for i in range(5):\n'
            '    print(f"PROGRESS: {i * 20}%: 模拟进度")\n'
            '    time.sleep(0.2)\n'
            '\n'
            '# 写入模拟JSON结果\n'
            'if output_path:\n'
            '    with open(output_path, "w", encoding="utf-8") as f:\n'
            '        json.dump({"segments": [], "rtf": 0.1}, f)\n'
            '\n'
            'exit(0)\n'
        )

def test_precompiled_strategy_runs_and_captures_output(monkeypatch):
    """
    测试预编译策略是否能正常启动子进程并捕获输出
    """
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="test_fake_app_")
    fake_app_path = os.path.join(temp_dir, "fake_precompiled_app.py")

    try:
        # 创建模拟预编译应用
        create_fake_precompiled_app(fake_app_path)

        # 使用python解释器运行模拟脚本
        fake_exe = sys.executable
        cmd_prefix = [fake_exe, fake_app_path]

        # 替换WHISPER_EXE_PATH为模拟命令
        monkeypatch.setattr('core.models.config.WHISPER_EXE_PATH', fake_exe)

        # 构造参数
        params = TranscriptionParameters()
        params.language = "zh"
        params.task = "transcribe"
        params.beam_size = 5
        params.word_timestamps = True
        params.no_speech_threshold = 0.6

        # 构造上下文
        context = TranscriptionContext(
            audio_file="dummy.wav",
            model_path="dummy_model",
            output_path="dummy.json",
            parameters=params,
            progress_callback=lambda p, t: print(f"[TEST] progress: {p:.2f}, text: {t}"),
            audio_duration=10.0
        )
        context.prepare()
        # 强制替换命令为python fake_app
        def fake_get_temp_json_path():
            return os.path.join(temp_dir, "output.json")
        context.get_temp_json_path = fake_get_temp_json_path

        # 替换subprocess.Popen以插入模拟命令
        original_popen = subprocess.Popen
        def fake_popen(cmd, **kwargs):
            # 替换命令为python fake_app
            new_cmd = [*cmd_prefix, *cmd[1:]]  # 保持python fake_app + 原始参数
            return original_popen(new_cmd, **kwargs)
        monkeypatch.setattr(subprocess, "Popen", fake_popen)

        # 执行策略
        strategy = PrecompiledTranscriptionStrategy()
        success, error, result = strategy._execute_internal(context)

        assert success, f"预编译策略执行失败: {error}"
        print("[TEST] 预编译策略执行成功，结果：", result)

    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    # 定义一个简单的monkeypatch替代，直接调用setattr
    class SimpleMonkeyPatch:
        def setattr(self, target_or_obj, name=None, value=None):
            # 支持pytest monkeypatch.setattr(obj, "attr", value) 或 monkeypatch.setattr("module.attr", value)
            if name is None:
                # 形式: monkeypatch.setattr("module.attr", value)
                target, value = target_or_obj, value
                parts = target.split('.')
                module = __import__('.'.join(parts[:-1]), fromlist=[parts[-1]])
                setattr(module, parts[-1], value)
            else:
                # 形式: monkeypatch.setattr(obj, "attr", value)
                # 如果target_or_obj是字符串，说明用户写成了monkeypatch.setattr("module.attr", value)，但传了两个参数
                if isinstance(target_or_obj, str):
                    parts = target_or_obj.split('.')
                    module = __import__('.'.join(parts[:-1]), fromlist=[parts[-1]])
                    setattr(module, parts[-1], name)
                else:
                    setattr(target_or_obj, name, value)
    monkeypatch = SimpleMonkeyPatch()
    test_precompiled_strategy_runs_and_captures_output(monkeypatch)