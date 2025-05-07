#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Whisper Runner - 在独立环境中运行Whisper模型进行转录
该脚本被主程序通过subprocess调用，通过JSON文件交换数据
"""

import os
import sys
import json
import time
import tempfile
import traceback
from typing import Dict, Any, List, Optional, Tuple

# 尝试导入 faster_whisper，如果失败则尝试添加可能的 site-packages 路径
try:
    import faster_whisper
except ImportError:
    # 尝试添加常见的 site-packages 路径（相对于脚本位置或 python.exe）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    python_exe_dir = os.path.dirname(sys.executable)
    possible_site_packages = [
        os.path.join(python_exe_dir, 'Lib', 'site-packages'),
        # 如果是在 venv/Scripts 目录下运行
        os.path.join(python_exe_dir, '..', 'Lib', 'site-packages'),
    ]
    for sp_path in possible_site_packages:
        if os.path.isdir(sp_path) and sp_path not in sys.path:
            sys.path.insert(0, sp_path)
            print(f"Info: 添加 site-packages 路径: {sp_path}", file=sys.stderr)

    try:
        import faster_whisper
        print("Info: 成功导入 faster_whisper (在添加路径后)", file=sys.stderr)
    except ImportError:
        print("Error: 无法导入 faster_whisper，即使添加了额外路径", file=sys.stderr)
        sys.exit(1)

def process_segments(segments) -> List[Dict[str, Any]]:
    """处理转录片段，将其转换为可序列化的字典格式
    
    Args:
        segments: 转录结果中的片段迭代器
        
    Returns:
        List[Dict[str, Any]]: 处理后的片段列表
    """
    result = []
    for segment in segments:
        # 将片段对象转换为字典
        segment_dict = {
            "id": segment.id,
            "seek": segment.seek,
            "start": segment.start,
            "end": segment.end,
            "text": segment.text,
            "tokens": segment.tokens,
            "temperature": segment.temperature,
            "avg_logprob": segment.avg_logprob,
            "compression_ratio": segment.compression_ratio,
            "no_speech_prob": segment.no_speech_prob,
        }
        
        # 如果有词级时间戳，添加到结果中
        if hasattr(segment, "words") and segment.words:
            segment_dict["words"] = [
                {
                    "word": word.word,
                    "start": word.start,
                    "end": word.end,
                    "probability": word.probability
                }
                for word in segment.words
            ]
        
        result.append(segment_dict)
    
    return result

def process_info(info) -> Dict[str, Any]:
    """处理转录元信息，将其转换为可序列化的字典格式
    
    Args:
        info: 转录结果中的元信息对象
        
    Returns:
        Dict[str, Any]: 处理后的元信息字典
    """
    # 将元信息对象转换为字典
    return {
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "transcription_options": {
            "task": getattr(info, "task", None),
            "language": getattr(info, "language", None),
            "beam_size": getattr(info, "beam_size", None),
            "best_of": getattr(info, "best_of", None),
            "patience": getattr(info, "patience", None),
            "length_penalty": getattr(info, "length_penalty", None),
            "temperature": getattr(info, "temperature", None),
            "compression_ratio_threshold": getattr(info, "compression_ratio_threshold", None),
            "log_prob_threshold": getattr(info, "log_prob_threshold", None),
            "no_speech_threshold": getattr(info, "no_speech_threshold", None),
            "condition_on_previous_text": getattr(info, "condition_on_previous_text", None),
        }
    }

def transcribe(model_path: str, audio_file: str, options: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """使用Faster Whisper进行音频转录
    
    Args:
        model_path: 模型路径
        audio_file: 音频文件路径
        options: 转录选项
        
    Returns:
        Tuple[List[Dict[str, Any]], Dict[str, Any]]: 处理后的片段列表和元信息
    """
    try:
        # 从选项中获取关键参数
        compute_type = options.get("compute_type", "float16")
        device = options.get("device", "cuda")
        cpu_threads = options.get("cpu_threads", 4)
        
        # 如果设备是auto，尝试检测CUDA
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
                print(f"Info: 自动检测设备: {device}", file=sys.stderr)
            except ImportError:
                device = "cpu"
                print("Info: 无法导入torch，使用CPU设备", file=sys.stderr)
        
        # 记录开始时间
        start_time = time.time()
        
        # 创建模型
        print(f"Info: 加载模型 '{model_path}' 使用设备={device}, 计算类型={compute_type}", file=sys.stderr)
        model = faster_whisper.WhisperModel(
            model_path,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
            local_files_only=True
        )
        
        # 记录模型加载时间
        model_load_time = time.time() - start_time
        print(f"Info: 模型加载时间: {model_load_time:.2f}秒", file=sys.stderr)
        
        # 转录参数
        language = options.get("language")
        task = options.get("task", "transcribe")
        beam_size = options.get("beam_size", 5)
        word_timestamps = options.get("word_timestamps", False)
        initial_prompt = options.get("initial_prompt")
        temperature = options.get("temperature", 0.0)
        
        # 执行转录
        print(f"Info: 开始转录 '{audio_file}'", file=sys.stderr)
        transcribe_start = time.time()
        segments, info = model.transcribe(
            audio_file,
            language=language,
            task=task,
            beam_size=beam_size,
            word_timestamps=word_timestamps,
            initial_prompt=initial_prompt,
            temperature=temperature
        )
        
        # 处理结果，转换为可序列化格式
        segments_list = process_segments(segments)
        info_dict = process_info(info)
        
        # 记录总转录时间
        total_time = time.time() - start_time
        transcribe_time = time.time() - transcribe_start
        print(f"Info: 总转录时间: {total_time:.2f}秒, 转录耗时: {transcribe_time:.2f}秒, 音频时长: {info_dict['duration']:.2f}秒", file=sys.stderr)
        
        # 计算实时因子
        rtf = total_time / info_dict["duration"] if info_dict["duration"] > 0 else 0
        print(f"Info: 实时因子 (RTF): {rtf:.2f}", file=sys.stderr)
        
        # 添加性能指标到结果中
        info_dict["performance"] = {
            "model_load_time": model_load_time,
            "transcription_time": transcribe_time,
            "total_time": total_time,
            "rtf": rtf
        }
        
        return segments_list, info_dict
        
    except Exception as e:
        error_msg = f"转录过程中发生错误: {str(e)}"
        print(f"Error: {error_msg}\n{traceback.format_exc()}", file=sys.stderr)
        raise

def main():
    """主函数，处理命令行参数并执行转录"""
    output_path = None  # 初始化输出文件变量
    try:
        # 确保 stdout 和 stderr 使用 UTF-8 编码
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
        
        # 检查命令行参数
        if len(sys.argv) < 2:
            print(f"Error: 缺少参数，需要输入文件路径", file=sys.stderr)
            print(json.dumps({"success": False, "error": "缺少参数，需要输入文件路径"}))
            return 1
        
        # 获取输入文件路径
        input_file = sys.argv[1]
        
        # 检查文件是否存在
        if not os.path.exists(input_file):
            print(f"Error: 输入文件不存在: {input_file}", file=sys.stderr)
            print(json.dumps({"success": False, "error": f"输入文件不存在: {input_file}"}))
            return 1
        
        # 读取输入数据
        print(f"Info: 读取输入文件: {input_file}", file=sys.stderr)
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                input_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: 无法解析输入JSON: {str(e)}", file=sys.stderr)
            print(json.dumps({"success": False, "error": f"无法解析输入JSON: {str(e)}"}))
            return 1
        except Exception as e:
            print(f"Error: 读取输入文件时出错: {str(e)}", file=sys.stderr)
            print(json.dumps({"success": False, "error": f"读取输入文件时出错: {str(e)}"}))
            return 1
        
        # 提取参数
        audio_file = input_data.get("audio_file")
        model_path = input_data.get("model_path")
        options = input_data.get("options", {})
        output_path = input_data.get("output_path")
        
        print(f"Info: 参数 - audio_file: {audio_file}, model_path: {model_path}, output_path: {output_path}", file=sys.stderr)
        
        # 验证必要参数
        if not audio_file or not os.path.exists(audio_file):
            error_msg = f"音频文件不存在: {audio_file}"
            print(f"Error: {error_msg}", file=sys.stderr)
            if output_path:
                try:
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump({"success": False, "error": error_msg}, f, ensure_ascii=False, indent=2)
                except Exception as write_err:
                    print(f"Error: 写入错误信息到输出文件时失败: {str(write_err)}", file=sys.stderr)
            print(json.dumps({"success": False, "error": error_msg}))
            return 2
        
        if not model_path or not os.path.exists(model_path):
            error_msg = f"模型路径不存在: {model_path}"
            print(f"Error: {error_msg}", file=sys.stderr)
            if output_path:
                try:
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump({"success": False, "error": error_msg}, f, ensure_ascii=False, indent=2)
                except Exception as write_err:
                    print(f"Error: 写入错误信息到输出文件时失败: {str(write_err)}", file=sys.stderr)
            print(json.dumps({"success": False, "error": error_msg}))
            return 2
        
        if not output_path:
            error_msg = "未指定输出文件"
            print(f"Error: {error_msg}", file=sys.stderr)
            print(json.dumps({"success": False, "error": error_msg}))
            return 2
        
        # 执行转录
        print(f"Info: 开始转录 '{audio_file}' 使用模型 '{model_path}'", file=sys.stderr)
        try:
            segments, info = transcribe(model_path, audio_file, options)
        except Exception as e:
            error_msg = f"转录过程中出错: {str(e)}"
            print(f"Error: {error_msg}\n{traceback.format_exc()}", file=sys.stderr)
            if output_path:
                try:
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump({"success": False, "error": error_msg}, f, ensure_ascii=False, indent=2)
                except Exception as write_err:
                    print(f"Error: 写入错误信息到输出文件时失败: {str(write_err)}", file=sys.stderr)
            print(json.dumps({"success": False, "error": error_msg}))
            return 3
        
        # 准备结果
        result = {
            "success": True,
            "segments": segments,
            "info": info
        }
        
        # 将结果写入输出文件
        print(f"Info: 写入结果到 {output_path}", file=sys.stderr)
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"Info: 结果写入成功", file=sys.stderr)
        except Exception as e:
            error_msg = f"写入结果文件时出错: {str(e)}"
            print(f"Error: {error_msg}\n{traceback.format_exc()}", file=sys.stderr)
            print(json.dumps({"success": False, "error": error_msg}))
            return 3
        
        # 向标准输出发送成功消息 (这将被主程序捕获)
        print(json.dumps({"success": True}))
        return 0
        
    except Exception as e:
        # 向标准错误输出发送详细错误
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"Error: 未预期的错误: {error_msg}\n{traceback.format_exc()}", file=sys.stderr)
        
        # 尝试写入错误到输出文件
        if output_path:
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump({"success": False, "error": error_msg}, f, ensure_ascii=False, indent=2)
                print(f"Info: 错误信息已写入输出文件", file=sys.stderr)
            except Exception as write_err:
                print(f"Error: 写入错误信息到输出文件时失败: {str(write_err)}", file=sys.stderr)
        
        # 向标准输出发送错误消息 (这将被主程序捕获)
        print(json.dumps({"success": False, "error": error_msg}))
        return 3

if __name__ == "__main__":
    sys.exit(main()) 