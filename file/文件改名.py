import os

def rename_files_in_directory(directory: str, start: int = 196):
    """
    批量重命名目录下的文件
    :param directory: 目标目录
    :param start: 起始编号
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


if __name__ == "__main__":
    # 修改这里，传入你要处理的目录路径
    target_dir = "/Users/hzx/Downloads/1"
    # 从指定的数字后面开始，比如传的是195，则从196开始命名
    rename_files_in_directory(target_dir, start=195)
