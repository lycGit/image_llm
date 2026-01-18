import os
import json
from comfyui.image2image import load_workflow_from_json

# 测试脚本：验证image2image.py中的提示语和参考图替换功能

def test_load_workflow():
    # 定义测试参数
    custom_prompt = "a beautiful landscape with mountains and a lake, sunset"
    test_image_filename = "test_image.png"
    
    # 工作流文件路径
    workflow_path = os.path.join(os.path.dirname(__file__), 'comfyui', 'workflows', 'image2image.json')
    
    print(f"正在加载工作流文件: {workflow_path}")
    
    # 1. 加载原始工作流
    with open(workflow_path, 'r', encoding='utf-8') as f:
        original_workflow = json.load(f)
    
    print("\n原始工作流中的提示词:")
    for node_id, node in original_workflow.items():
        if node['class_type'] == 'CLIPTextEncode':
            print(f"节点 {node_id}: {node['inputs'].get('text', '')}")
    
    print("\n原始工作流中的参考图:")
    for node_id, node in original_workflow.items():
        if node['class_type'] == 'LoadImage':
            print(f"节点 {node_id}: {node['inputs'].get('image', '')}")
    
    # 2. 使用自定义参数加载工作流
    print("\n--- 应用自定义参数 ---")
    prompt = load_workflow_from_json(workflow_path, custom_prompt=custom_prompt, image_filename=test_image_filename)
    
    print("\n处理后的工作流中的提示词:")
    for node_id, node in prompt.items():
        if node['class_type'] == 'CLIPTextEncode':
            print(f"节点 {node_id}: {node['inputs'].get('text', '')}")
    
    print("\n处理后的工作流中的参考图:")
    for node_id, node in prompt.items():
        if node['class_type'] == 'LoadImage':
            print(f"节点 {node_id}: {node['inputs'].get('image', '')}")
    
    # 验证替换是否成功
    print("\n--- 验证结果 ---")
    
    # 检查提示词替换
    prompt_replaced = False
    for node_id, node in prompt.items():
        if node['class_type'] == 'CLIPTextEncode':
            text = node['inputs'].get('text', '')
            if text == custom_prompt:
                prompt_replaced = True
                break
    
    # 检查参考图替换
    image_replaced = False
    for node_id, node in prompt.items():
        if node['class_type'] == 'LoadImage':
            image = node['inputs'].get('image', '')
            if image == test_image_filename:
                image_replaced = True
                break
    
    print(f"提示词替换成功: {prompt_replaced}")
    print(f"参考图替换成功: {image_replaced}")
    
    if prompt_replaced and image_replaced:
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 测试失败！")

if __name__ == "__main__":
    test_load_workflow()