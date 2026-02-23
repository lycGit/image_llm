import os

# 配置参数
SOURCE_DIR = "/Users/lyc/Desktop/oldstylecompressimage/results"
OUTPUT_FILE = "/Users/lyc/Desktop/oldstylecompressimage/merged_results.txt"


def get_txt_files(directory):
    """
    获取目录中所有的txt文件
    
    参数:
        directory: 目录路径
        
    返回:
        list: txt文件路径列表，按文件名排序
    """
    txt_files = []
    
    if not os.path.exists(directory):
        print(f"目录不存在: {directory}")
        return txt_files
    
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        
        if os.path.isfile(file_path) and filename.lower().endswith('.txt'):
            txt_files.append(file_path)
    
    return sorted(txt_files)


def read_file_content(file_path):
    """
    读取文件内容
    
    参数:
        file_path: 文件路径
        
    返回:
        str: 文件内容
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"读取文件 {file_path} 时出错: {str(e)}")
        return None


def merge_txt_files(source_dir, output_file):
    """
    遍历文件夹中的所有txt文件，将每个文件内容作为独立段落整合到一个新文件中
    
    参数:
        source_dir: 源文件夹路径
        output_file: 输出文件路径
        
    返回:
        int: 成功合并的文件数量
    """
    # 获取所有txt文件
    txt_files = get_txt_files(source_dir)
    
    if not txt_files:
        print(f"在目录 {source_dir} 中没有找到txt文件")
        return 0
    
    print(f"找到 {len(txt_files)} 个txt文件，开始合并...")
    
    # 创建输出目录（如果需要）
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # 合并文件
    success_count = 0
    
    with open(output_file, 'w', encoding='utf-8') as out_f:
        for i, file_path in enumerate(txt_files, 1):
            print(f"[{i}/{len(txt_files)}] 处理文件: {os.path.basename(file_path)}")
            
            # 读取文件内容
            content = read_file_content(file_path)
            
            if content:
                # 写入内容作为独立段落
                out_f.write(content)
                out_f.write('\n' + '=' * 80 + '\n\n')
                success_count += 1
            else:
                print(f"✗ 读取失败")
    
    return success_count


def main():
    """
    主函数
    """
    print("=" * 60)
    print("TXT文件合并工具")
    print("=" * 60)
    print(f"源目录: {SOURCE_DIR}")
    print(f"输出文件: {OUTPUT_FILE}")
    print("=" * 60)
    
    # 合并文件
    success_count = merge_txt_files(SOURCE_DIR, OUTPUT_FILE)
    
    # 输出统计信息
    print("\n" + "=" * 60)
    if success_count > 0:
        print(f"合并完成！成功合并 {success_count} 个文件")
        print(f"结果已保存到: {OUTPUT_FILE}")
    else:
        print("没有文件被合并")
    print("=" * 60)


if __name__ == '__main__':
    main()
