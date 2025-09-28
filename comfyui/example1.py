import websocket
import uuid
import json
import urllib.request
import urllib.parse
from PIL import Image
import io
import os
import random

# 设置服务器地址和客户端
server_address = "127.0.0.1:8188"
client_id = str(uuid.uuid4())


# 定义向服务器发送提示的函数
def queue_prompt(prompt):
    try:
        p = {"prompt": prompt, "client_id": client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(
            "http://{}/prompt".format(server_address), 
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        response = urllib.request.urlopen(req)
        return json.loads(response.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP错误: {e.code} - {e.reason}")
        print(f"错误详情: {e.read().decode()}")
        raise
    except Exception as e:
        print(f"请求出错: {str(e)}")
        raise


# 定义从服务器下载图像数据的函数
def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        return response.read()


# 定义获取历史记录的函数
def get_history(prompt_id):
    with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
        return json.loads(response.read())


# 定义通过WebSocket接收消息并下载图像的函数
def get_images(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break  # 执行完成
        else:
            continue  # 预览是二进制数据

    history = get_history(prompt_id)[prompt_id]
    for o in history['outputs']:
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'])
                    images_output.append(image_data)
            output_images[node_id] = images_output

    return output_images


# 读取workflows文件夹下的generate_image.json文件
def load_workflow_from_json(file_path, custom_prompt=None):
    with open(file_path, 'r', encoding='utf-8') as f:
        workflow_data = json.load(f)
    
    # 创建提示对象
    prompt = {}
    
    # 为每个节点创建基本结构
    for node in workflow_data['nodes']:
        node_id = str(node['id'])
        prompt[node_id] = {
            "inputs": {},
            "class_type": node['type']
        }
    
    # 处理每个节点的widgets_values和输入参数
    for node in workflow_data['nodes']:
        node_id = str(node['id'])
        node_type = node['type']
        
        # 获取所有带widget的输入参数名称
        widget_inputs = [input['name'] for input in node['inputs'] if 'widget' in input]
        
        # 如果有widgets_values，将其映射到对应的输入参数
        if 'widgets_values' in node:
            # 特殊处理KSampler节点
            if node_type == 'KSampler':
                # 根据generate_image.json中的widgets_values结构和已知的KSampler参数顺序进行映射
                # widgets_values顺序: [seed, steps, cfg, sampler_name_index, scheduler_index, denoise]
                if len(node['widgets_values']) >= 6:
                    # 处理seed
                    try:
                        prompt[node_id]["inputs"]["seed"] = int(node['widgets_values'][0])
                    except (ValueError, TypeError):
                        prompt[node_id]["inputs"]["seed"] = random.randint(0, 2**32 - 1)
                    
                    # 处理steps
                    steps_value = node['widgets_values'][1]
                    if isinstance(steps_value, str) and steps_value == 'randomize':
                        prompt[node_id]["inputs"]["steps"] = 20  # 使用默认值
                    else:
                        try:
                            prompt[node_id]["inputs"]["steps"] = int(steps_value)
                        except (ValueError, TypeError):
                            prompt[node_id]["inputs"]["steps"] = 20  # 使用默认值
                    
                    # 处理cfg
                    try:
                        prompt[node_id]["inputs"]["cfg"] = float(node['widgets_values'][2])
                    except (ValueError, TypeError):
                        prompt[node_id]["inputs"]["cfg"] = 8.0  # 使用默认值
                    
                    # 处理sampler_name - 这里使用固定值，因为从错误信息看'8'不是有效值
                    prompt[node_id]["inputs"]["sampler_name"] = "euler_ancestral"
                    
                    # 处理scheduler - 使用服务器支持的值
                    prompt[node_id]["inputs"]["scheduler"] = "normal"
                    
                    # 处理denoise
                    try:
                        prompt[node_id]["inputs"]["denoise"] = float(node['widgets_values'][5])
                    except (ValueError, TypeError):
                        prompt[node_id]["inputs"]["denoise"] = 1.0  # 使用默认值
            elif node_type == 'CLIPTextEncode':
                # 处理文本编码节点，检查是否需要替换提示语
                if len(node['widgets_values']) > 0:
                    # 检查是否是正面提示节点（包含原始提示语的节点）
                    original_prompt = node['widgets_values'][0]
                    if "beautiful scenery nature glass bottle landscape" in original_prompt and custom_prompt:
                        # 使用自定义提示语
                        prompt[node_id]["inputs"]["text"] = custom_prompt
                    else:
                        # 使用原始提示语
                        prompt[node_id]["inputs"]["text"] = original_prompt
            else:
                # 普通节点的处理逻辑
                for i, value in enumerate(node['widgets_values']):
                    if i < len(widget_inputs):
                        input_name = widget_inputs[i]
                        prompt[node_id]["inputs"][input_name] = value
        
        # 为SaveImage节点确保有filename_prefix
        if node_type == 'SaveImage' and 'filename_prefix' not in prompt[node_id]["inputs"]:
            prompt[node_id]["inputs"]["filename_prefix"] = "ComfyUI"
    
    # 处理节点之间的链接
    for link in workflow_data['links']:
        link_id, source_node_id, source_output_idx, target_node_id, target_input_idx, link_type = link
        
        source_node_str = str(source_node_id)
        target_node_str = str(target_node_id)
        
        # 确保源节点和目标节点存在
        if source_node_str not in prompt or target_node_str not in prompt:
            continue
        
        # 找到目标节点中对应索引的输入参数名称
        target_node = next((n for n in workflow_data['nodes'] if str(n['id']) == target_node_str), None)
        if target_node is None or target_input_idx >= len(target_node['inputs']):
            continue
        
        target_input_name = target_node['inputs'][target_input_idx]['name']
        
        # 设置链接值，格式为[源节点ID, 输出索引]
        prompt[target_node_str]["inputs"][target_input_name] = [source_node_str, source_output_idx]
    
    return prompt


def main():
    # 定义默认提示语
    default_prompt = "a beautiful sunset over the mountains"
    
    # 加载workflow文件
    workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', 'generate_image.json')
    
    # 使用默认提示语加载工作流
    prompt = load_workflow_from_json(workflow_path, custom_prompt=default_prompt)
    
    # 创建一个WebSocket连接到服务器
    ws = websocket.WebSocket()
    ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
    
    # 调用get_images()函数来获取图像
    images = get_images(ws, prompt)
    
    # 显示图片
    for node_id in images:
        for image_data in images[node_id]:
            image = Image.open(io.BytesIO(image_data))
            image.show()
            input("")


if __name__ == "__main__":
    main()