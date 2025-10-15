import sys
import os
import time

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from comfyui.image2video_official_api import generate_video_from_local_image

# 测试函数
def test_video_generation():
    print("开始测试视频生成功能...")
    print(f"当前时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 确保工作流文件存在
    workflow_path = os.path.join(os.path.dirname(__file__), 'comfyui', 'workflows', 'video_wan2_2_14B_i2v.json')
    if not os.path.exists(workflow_path):
        print(f"错误: 工作流文件不存在: {workflow_path}")
        return
    else:
        print(f"找到工作流文件: {workflow_path}")
    
    # 使用当前目录中的测试图片（假设存在）
    # 请用户替换为实际存在的图片路径
    test_image_path = os.path.join(os.path.dirname(__file__), 'assets', 'images', 'girl.png')
    if not os.path.exists(test_image_path):
        # 尝试其他可能的图片路径
        possible_images = []
        for root, dirs, files in os.walk(os.path.dirname(__file__)):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    possible_images.append(os.path.join(root, file))
                    if len(possible_images) >= 3:  # 只显示前3个选项
                        break
        
        print(f"警告: 默认测试图片不存在: {test_image_path}")
        if possible_images:
            print("\n可用的测试图片:")
            for i, img_path in enumerate(possible_images, 1):
                print(f"{i}. {img_path}")
            test_image_path = possible_images[0]  # 使用第一个可用图片
            print(f"\n将使用第一个可用图片: {test_image_path}")
        else:
            print("错误: 找不到任何可用的测试图片")
            return
    
    # 测试参数
    test_prompt = "一只可爱的小猫在花园里玩耍"
    test_negative_prompt = "模糊，低质量，变形"
    
    try:
        # 调用视频生成函数
        print(f"\n使用图片: {test_image_path}")
        print(f"提示词: {test_prompt}")
        print(f"负面提示词: {test_negative_prompt}")
        print(f"开始生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        result = generate_video_from_local_image(
            image_path=test_image_path,
            prompt=test_prompt,
            negative_prompt=test_negative_prompt
        )
        
        # 验证结果
        print("\n===== 结果验证 =====")
        print(f"完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"结果类型: {type(result)}")
        
        if isinstance(result, dict):
            print("\n结果字典键:")
            for key in result.keys():
                print(f"- {key}: {result[key]}")
            
            # 检查关键状态
            success = result.get('success', False)
            print(f"\n关键状态检查:")
            print(f"- 成功标志: {success}")
            print(f"- 提示ID: {result.get('prompt_id', '无')}")
            print(f"- 帧数: {result.get('frames_count', 0)}")
            print(f"- 视频URL: {result.get('video_url', '无')}")
            print(f"- 消息: {result.get('message', '无')}")
            print(f"- 错误: {result.get('error', '无')}")
        else:
            print("错误: 返回值不是字典类型")
        
        print("\n测试完成!")
        
    except Exception as e:
        print(f"\n测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_video_generation()