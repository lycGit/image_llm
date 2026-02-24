import os
import shutil
import re

# 配置参数
IMAGE_ID = "5450"
SOURCE_DIR = f"/Users/lyc/Desktop/createImages/{IMAGE_ID}/compress"
OUTPUT_BASE_DIR = f"/Users/lyc/Desktop/createImages/{IMAGE_ID}"

# 支持的图片格式
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}


def get_image_files(directory):
    """
    获取目录中所有支持的图片文件
    
    参数:
        directory: 目录路径
        
    返回:
        list: 图片文件路径列表
    """
    image_files = []
    
    if not os.path.exists(directory):
        print(f"目录不存在: {directory}")
        return image_files
    
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        
        if os.path.isfile(file_path):
            ext = os.path.splitext(filename)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                image_files.append(file_path)
    
    return sorted(image_files)


def parse_filename(filename):
    """
    解析文件名，提取ID和新的文件名
    
    参数:
        filename: 原始文件名，如 "5382_art-1_compressed.jpg"
        
    返回:
        tuple: (id, new_filename) 或 (None, None) 如果解析失败
    """
    # 使用正则表达式匹配文件名格式: {数字}_{名称}_compressed.{扩展名}
    pattern = r'^(\d+)_(.+?)_compressed(\.[^.]+)$'
    match = re.match(pattern, filename)
    
    if match:
        file_id = match.group(1)
        name_part = match.group(2)
        extension = match.group(3)
        new_filename = f"{name_part}{extension}"
        return file_id, new_filename
    
    return None, None


def rename_and_move_image(source_path, output_base_dir):
    """
    重命名并移动图片文件
    
    参数:
        source_path: 源文件路径
        output_base_dir: 输出基础目录
        
    返回:
        tuple: (success, new_path) 或 (False, None) 如果失败
    """
    filename = os.path.basename(source_path)
    
    # 解析文件名
    file_id, new_filename = parse_filename(filename)
    
    if not file_id or not new_filename:
        print(f"✗ 文件名格式不匹配，跳过: {filename}")
        return False, None
    
    # 创建目标文件夹（以ID命名）
    target_dir = os.path.join(output_base_dir, file_id)
    os.makedirs(target_dir, exist_ok=True)
    
    # 目标文件路径
    target_path = os.path.join(target_dir, new_filename)
    
    # 如果目标文件已存在，添加序号
    if os.path.exists(target_path):
        base_name = os.path.splitext(new_filename)[0]
        extension = os.path.splitext(new_filename)[1]
        counter = 1
        while os.path.exists(target_path):
            new_filename = f"{base_name}_{counter}{extension}"
            target_path = os.path.join(target_dir, new_filename)
            counter += 1
    
    try:
        # 移动文件
        shutil.move(source_path, target_path)
        return True, target_path
    except Exception as e:
        print(f"✗ 移动文件失败: {str(e)}")
        return False, None


def main():
    """
    主函数：遍历文件夹，重命名并移动图片
    """
    print("=" * 60)
    print("图片重命名和移动工具")
    print("=" * 60)
    print(f"源目录: {SOURCE_DIR}")
    print(f"输出基础目录: {OUTPUT_BASE_DIR}")
    print("=" * 60)
    
    # 获取所有图片文件
    image_files = get_image_files(SOURCE_DIR)
    
    if not image_files:
        print(f"在目录 {SOURCE_DIR} 中没有找到支持的图片文件")
        return
    
    print(f"找到 {len(image_files)} 张图片，开始处理...\n")
    
    # 处理每张图片
    success_count = 0
    fail_count = 0
    
    for i, image_path in enumerate(image_files, 1):
        filename = os.path.basename(image_path)
        print(f"[{i}/{len(image_files)}] 处理: {filename}")
        
        # 重命名并移动
        success, new_path = rename_and_move_image(image_path, OUTPUT_BASE_DIR)
        
        if success:
            print(f"  ✓ 成功: {os.path.basename(new_path)}")
            success_count += 1
        else:
            print(f"  ✗ 失败")
            fail_count += 1
    
    # 输出统计信息
    print("\n" + "=" * 60)
    print(f"处理完成！")
    print(f"成功: {success_count} 张")
    print(f"失败: {fail_count} 张")
    print("=" * 60)


if __name__ == '__main__':
    main()
