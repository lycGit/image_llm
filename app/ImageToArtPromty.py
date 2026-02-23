import os
from dashscope import MultiModalConversation
import dashscope

# 以下为北京地域base_url，若使用弗吉尼亚地域模型，需要将base_url换成 https://dashscope-us.aliyuncs.com/api/v1
# 若使用新加坡地域的模型，需将base_url替换为：https://dashscope-intl.aliyuncs.com/api/v1
dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

# 配置参数
IMAGE_DIR = "/Users/lyc/Desktop/compressimage/5894_selected"
OUTPUT_DIR = "/Users/lyc/Desktop/compressimage/5894_selected/results"
API_KEY = "sk-1f85075ccbba49bb80c72c43c1f53254"
MODEL = 'qwen3.5-plus'

# 支持的图片格式
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}


def process_image(image_path):
    """
    处理单张图片，调用大模型获取提示词
    
    参数:
        image_path: 图片文件的绝对路径
        
    返回:
        str: 大模型返回的提示词文本
    """
    image_uri = f"file://{image_path}"
    messages = [
        {
            'role': 'user',
            'content': [
                {'image': image_uri},
                {'text': '请根据这张图片，反推出生成该图片的提示词。注意当前这张图片和之前的图片是不一样的，请仔细查看图片细节。提示词要求分成两部分，一部分描述背景和风格，另外一部分描述人物衣着，头发，体态姿势等人物本身。注意，描述人物部分的提示词要避免有对人物脸部五官的描述内容，以免后续使用时人物脸部失真。只需要输出中文部分'}
            ]
        }
    ]
    
    try:
        response = MultiModalConversation.call(
            api_key=API_KEY,
            model=MODEL,
            messages=messages
        )
        return response.output.choices[0].message.content[0]["text"]
    except Exception as e:
        print(f"处理图片 {image_path} 时出错: {str(e)}")
        return None


def save_result(image_path, result_text):
    """
    将结果保存到txt文件
    
    参数:
        image_path: 原图片路径
        result_text: 大模型返回的文本
    """
    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 生成输出文件名（与图片同名）
    image_filename = os.path.basename(image_path)
    output_filename = os.path.splitext(image_filename)[0] + '.txt'
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    # 保存结果
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"图片文件: {image_path}\n")
        f.write(f"处理时间: {os.path.getmtime(image_path)}\n")
        f.write("=" * 50 + "\n")
        f.write(result_text)
    
    return output_path


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


def main():
    """
    主函数：批量处理图片
    """
    # 获取所有图片文件
    image_files = get_image_files(IMAGE_DIR)
    
    if not image_files:
        print(f"在目录 {IMAGE_DIR} 中没有找到支持的图片文件")
        return
    
    print(f"找到 {len(image_files)} 张图片，开始处理...")
    
    # 处理每张图片
    success_count = 0
    fail_count = 0
    
    for i, image_path in enumerate(image_files, 1):
        print(f"\n[{i}/{len(image_files)}] 处理图片: {os.path.basename(image_path)}")
        
        # 调用大模型
        result_text = process_image(image_path)
        
        if result_text:
            # 保存结果
            output_path = save_result(image_path, result_text)
            print(f"✓ 处理成功，结果已保存到: {output_path}")
            success_count += 1
        else:
            print(f"✗ 处理失败")
            fail_count += 1
    
    # 输出统计信息
    print("\n" + "=" * 50)
    print(f"处理完成！")
    print(f"成功: {success_count} 张")
    print(f"失败: {fail_count} 张")
    print(f"结果保存在: {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
