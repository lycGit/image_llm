#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试视频生成结果判断修复
验证ComfyUI视频生成成功但没有找到标准视频信息时的正确处理
"""

import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comfyui.image2video_official_api import ComfyUIAPI

def find_test_image():
    """查找测试用的图片文件"""
    # 尝试多个可能的图片路径
    possible_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_image.jpg"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "test.jpg"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "example.jpg"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample.jpg")
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"找到测试图片: {path}")
            return path
    
    # 如果没有找到，列出当前目录下的图片文件
    print("未找到默认测试图片，正在搜索当前目录下的图片文件...")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
    
    for file in os.listdir(current_dir):
        if any(file.lower().endswith(ext) for ext in image_extensions):
            path = os.path.join(current_dir, file)
            print(f"找到图片文件: {path}")
            return path
    
    print("错误: 未找到任何测试图片文件")
    return None

def find_workflow_file():
    """查找工作流文件"""
    # 尝试多个可能的工作流路径
    possible_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflows", "image2video_workflow.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "image2video_workflow.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflow.json")
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"找到工作流文件: {path}")
            return path
    
    print("错误: 未找到工作流文件")
    return None

def test_video_generation():
    """测试视频生成功能并验证结果判断逻辑"""
    print("开始测试视频生成结果判断修复...")
    
    # 查找工作流文件
    workflow_file = find_workflow_file()
    if not workflow_file:
        return False
    
    # 查找测试图片
    image_path = find_test_image()
    if not image_path:
        return False
    
    try:
        # 初始化API客户端
        comfy_api = ComfyUIAPI(server_url="http://127.0.0.1:8188")
        
        # 读取工作流文件
        with open(workflow_file, 'r', encoding='utf-8') as f:
            workflow = json.load(f)
        
        print(f"\n使用工作流: {workflow_file}")
        print(f"使用图片: {image_path}")
        
        # 测试参数 - 尽量使用简单设置以加快测试速度
        prompt = "生成一个短视频"
        negative_prompt = "模糊，变形，扭曲"
        frames = 4  # 减少帧数以加快测试
        
        print(f"\n开始生成视频 (帧数: {frames})...")
        print(f"提示词: {prompt}")
        print(f"负面提示词: {negative_prompt}")
        
        # 调用视频生成函数
        result = comfy_api.generate_video_from_local_image(
            image_path=image_path,
            prompt=prompt,
            negative_prompt=negative_prompt,
            frames=frames,
            workflow=workflow,
            save_to_local=False  # 先不保存到本地
        )
        
        print("\n===== 测试结果详情 =====")
        print(f"成功状态: {result.get('success', False)}")
        print(f"消息: {result.get('message', '无消息')}")
        print(f"生成的帧数: {result.get('frames_count', 0)}")
        print(f"是否有输出: {result.get('has_output', False)}")
        
        # 检查是否有视频信息
        if 'video_info' in result:
            print("\n视频信息:")
            video_info = result['video_info']
            if isinstance(video_info, dict):
                for key, value in video_info.items():
                    print(f"  {key}: {value}")
            else:
                print(f"  {video_info}")
        
        # 检查是否有错误信息
        if 'error' in result:
            print(f"\n错误信息: {result['error']}")
        
        print("\n===== 测试总结 =====")
        if result.get('success', False) and result.get('frames_count', 0) > 0:
            print("✓ 测试成功: 即使没有找到标准视频信息，只要有帧数输出就判定为成功")
            return True
        else:
            print("✗ 测试失败: 结果判断逻辑可能仍有问题")
            return False
    
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        return False
    except Exception as e:
        print(f"\n测试过程中出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_video_generation()
    sys.exit(0 if success else 1)