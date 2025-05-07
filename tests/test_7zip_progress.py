import subprocess
import re
import os
import sys
from pathlib import Path

def find_project_root(start_path):
    """向上查找项目根目录（假设包含 'core' 或 'resources' 文件夹）"""
    current_path = Path(start_path).resolve()
    while True:
        if (current_path / 'core').is_dir() or (current_path / 'resources').is_dir():
            return current_path
        parent_path = current_path.parent
        if parent_path == current_path:
            # Reached the root of the filesystem without finding the marker
            raise FileNotFoundError("无法自动定位项目根目录。请确保脚本在项目内运行。")
        current_path = parent_path

def run_7zip_test():
    """运行 7-Zip 解压测试并尝试解析进度"""
    try:
        # --- 1. 定位 7-Zip ---
        try:
            # 尝试基于 __file__ 定位项目根目录
            project_root = find_project_root(__file__)
            print(f"推测的项目根目录: {project_root}")
        except NameError:
             # 如果 __file__ 不可用 (例如在交互式解释器中), 尝试基于当前工作目录
             project_root = find_project_root(os.getcwd())
             print(f"推测的项目根目录 (基于CWD): {project_root}")
        except FileNotFoundError as e:
            print(f"错误: {e}")
            # 作为备选方案，您可以硬编码路径，但这不推荐
            # project_root = Path("C:/path/to/your/project")
            # print(f"警告: 使用硬编码的项目根目录: {project_root}")
            return

        bundled_7z_path = project_root / "resources" / "7-Zip-Zstandard64" / "7z.exe"

        if not bundled_7z_path.is_file():
            print(f"错误: 未找到 7-Zip 可执行文件: {bundled_7z_path}")
            return

        seven_zip_exe = str(bundled_7z_path)
        print(f"找到 7-Zip: {seven_zip_exe}")

        # --- 2. 定义路径 ---
        # 使用原始字符串处理 Windows 路径
        # archive_file = r'C:\Users\Jorkey\AppData\Local\FasterVox\test\temp.zip'
        # target_dir = r'C:\Users\Jorkey\AppData\Local\FasterVox\test\extracted' # 解压到新子目录避免覆盖

        # 改为使用 pathlib 处理路径，更健壮
        base_test_dir = Path('C:/Users/Jorkey/AppData/Local/FasterVox/test')
        archive_file = base_test_dir / 'temp.7z'
        target_dir = base_test_dir / 'extracted_test' # 解压到新子目录

        if not archive_file.is_file():
            print(f"错误: 测试压缩文件未找到: {archive_file}")
            print("请确保 'C:\\\\Users\\\\Jorkey\\\\AppData\\\\Local\\\\FasterVox\\\\test\\\\temp.7z' 文件存在。")
            return

        # --- 3. 准备目标目录 ---
        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"确保解压目标目录存在: {target_dir}")

        # --- 4. 构建并执行命令 ---
        # -bsp1: 尝试输出进度到 stdout
        # -y: 假设对所有提示回答 Yes
        cmd = [
            seven_zip_exe,
            'x',                 # 解压命令
            str(archive_file),   # 压缩文件路径
            f'-o{str(target_dir)}', # 输出目录
            '-bsp1',             # 尝试输出进度到 stdout
            '-y'                 # 全部自动确认
        ]
        print(f"执行命令: {' '.join(cmd)}")

        # 使用 Popen 异步执行并捕获输出
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # 将 stderr 合并到 stdout
            text=True,                # 以文本模式读取输出
            encoding='utf-8',         # 尝试 UTF-8 解码
            errors='ignore',          # 忽略解码错误
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0 # Windows下不显示窗口
        )

        # --- 5. 实时读取和解析输出 ---
        print("--- 开始读取 7-Zip 输出 ---")
        progress_found = False
        # 正则表达式尝试匹配 百分比数字 + %
        # \b 确保匹配整个数字, (\d+) 捕获数字部分
        progress_regex = re.compile(r'(\d+)%')

        while True:
            line = process.stdout.readline()
            if not line:
                break # 输出结束

            line = line.strip()
            if not line:
                continue # 跳过空行

            print(f"  [RAW]: {line}") # 打印原始行

            # 尝试解析进度
            match = progress_regex.search(line)
            if match:
                percentage = int(match.group(1))
                print(f"  >>> 解析到进度: {percentage}%")
                progress_found = True

        print("--- 7-Zip 输出结束 ---")

        # --- 6. 等待进程结束并获取结果 ---
        process.wait()
        print(f"7-Zip 进程已结束，返回码: {process.returncode}")

        if not progress_found:
            print("\n警告: 未能从 7-Zip 输出中解析出任何进度百分比。")
            print("可能的原因:")
            print("  - 您使用的 7-Zip 版本不支持 -bsp1 参数或输出格式不同。")
            print("  - 压缩文件太小，解压过程太快，没有足够的时间输出进度。")
            print("  - 解析进度的正则表达式不匹配实际输出格式。")
            print("请检查上面的 [RAW] 输出以了解具体内容。")

        if process.returncode != 0:
            print(f"错误: 7-Zip 解压失败 (返回码: {process.returncode})。请检查上面的输出了解详情。")
        else:
            print("7-Zip 解压成功完成。")

    except FileNotFoundError as e:
        print(f"错误: 文件未找到 - {e}")
    except Exception as e:
        print(f"执行测试时发生意外错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_7zip_test() 