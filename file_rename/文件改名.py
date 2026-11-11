"""批量重命名目录下的文件为连续编号。

既可以作为模块调用 ``main()``（使用 argparse 默认参数），
也可以通过命令行执行:

    python 文件改名.py ./images_20261111-1626 --start 195
"""

from __future__ import annotations

import argparse
import os

# ===== 默认配置（命令行参数默认值也取自这里）=====
DEFAULT_DIRECTORY = "./images"
DEFAULT_START = 1


def rename_files_in_directory(directory: str, start: int = DEFAULT_START) -> None:
    """批量重命名目录下的文件。

    :param directory: 目标目录
    :param start: 起始编号（第一个文件将被命名为该编号）
    """
    if not os.path.isdir(directory):
        print(f"❌ 目录不存在: {directory}")
        return

    files = sorted(os.listdir(directory))  # 排序，避免顺序混乱
    counter = start

    for filename in files:
        file_path = os.path.join(directory, filename)

        # 跳过子目录
        if not os.path.isfile(file_path):
            continue

        # 保留扩展名
        _, ext = os.path.splitext(filename)
        new_name = f"{counter}{ext}"
        new_path = os.path.join(directory, new_name)

        # 如果目标文件已存在，避免覆盖
        if os.path.exists(new_path):
            print(f"⚠️ 跳过 {filename} -> {new_name} (目标已存在)")
            continue

        os.rename(file_path, new_path)
        print(f"✅ {filename} -> {new_name}")
        counter += 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="批量重命名目录下的文件为连续编号")
    parser.add_argument(
        "directory",
        nargs="?",
        default=DEFAULT_DIRECTORY,
        help=f"目标目录，默认 {DEFAULT_DIRECTORY}",
    )
    parser.add_argument(
        "-s", "--start",
        type=int,
        default=DEFAULT_START,
        help=f"起始编号，默认 {DEFAULT_START}",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """入口函数。``main()`` 使用默认参数，``main([...])`` 等价于命令行传参。"""
    args = build_parser().parse_args(argv)
    rename_files_in_directory(args.directory, args.start)


if __name__ == "__main__":
    main()
