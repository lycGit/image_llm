# 导入必要的库
import websocket
import uuid
import json
import urllib.request
import urllib.parse
from PIL import Image
import io
import os
import random
import base64
import requests

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


# 上传图片到ComfyUI服务器
def upload_image(image_path):
    try:
        # 确保图片文件存在
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        
        # 使用表单数据方式上传图片
        url = f"http://{server_address}/upload/image"
        filename = os.path.basename(image_path)
        
        # 确保文件在上传前完全读取并关闭
        with open(image_path, "rb") as file:
            files = {'image': (filename, file.read())}
        
        response = requests.post(url, files=files)
        
        # 检查响应状态
        response.raise_for_status()
        result = response.json()
        
        # 检查上传是否成功
        if "name" in result:
            print(f"图片上传成功: {result['name']}")
            return result['name']
        else:
            raise Exception(f"图片上传失败: {result}")
    except requests.exceptions.HTTPError as e:
        print(f"上传图片时HTTP错误: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"错误详情: {e.response.text}")
        raise
    except Exception as e:
        print(f"上传图片时出错: {str(e)}")
        raise


# 读取workflows文件夹下的image2image.json文件
def load_workflow_from_json(file_path, custom_prompt=None, image_filename=None):
    with open(file_path, 'r', encoding='utf-8') as f:
        workflow_data = json.load(f)
    
    # 创建提示对象
    prompt = {}
    
    # 过滤掉MarkdownNote节点，因为它们只是注释，不是实际功能节点
    valid_nodes = [node for node in workflow_data['nodes'] if node['type'] != 'MarkdownNote']
    
    # 为每个有效节点创建基本结构
    for node in valid_nodes:
        node_id = str(node['id'])
        prompt[node_id] = {
            "inputs": {},
            "class_type": node['type']
        }
    
    # 处理每个有效节点的widgets_values和输入参数
    for node in valid_nodes:
        node_id = str(node['id'])
        node_type = node['type']
        
        # 获取所有带widget的输入参数名称
        widget_inputs = [input['name'] for input in node['inputs'] if 'widget' in input]
        
        # 如果有widgets_values，将其映射到对应的输入参数
        if 'widgets_values' in node:
            # 特殊处理KSampler节点
            if node_type == 'KSampler':
                # 根据image2image.json中的widgets_values结构和已知的KSampler参数顺序进行映射
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
                    
                    # 处理sampler_name
                    prompt[node_id]["inputs"]["sampler_name"] = "dpmpp_2m"  # 从image2image.json中获取的有效值
                    
                    # 处理scheduler
                    prompt[node_id]["inputs"]["scheduler"] = "normal"  # 从image2image.json中获取的有效值
                    
                    # 处理denoise - 对于image2image，denoise应该小于1
                    try:
                        prompt[node_id]["inputs"]["denoise"] = float(node['widgets_values'][5])
                    except (ValueError, TypeError):
                        prompt[node_id]["inputs"]["denoise"] = 0.87  # 使用默认值
            elif node_type == 'CLIPTextEncode':
                # 处理文本编码节点，检查是否需要替换提示语
                if len(node['widgets_values']) > 0:
                    original_prompt = node['widgets_values'][0]
                    # 检查是否是正面提示节点（包含原始提示语的节点）
                    if "photograph of victorian woman with wings" in original_prompt and custom_prompt:
                        # 使用自定义提示语
                        prompt[node_id]["inputs"]["text"] = custom_prompt
                    else:
                        # 使用原始提示语
                        prompt[node_id]["inputs"]["text"] = original_prompt
            elif node_type == 'LoadImage':
                # 处理图片加载节点
                if image_filename:
                    # 使用上传的图片文件名
                    prompt[node_id]["inputs"]["image"] = image_filename
                else:
                    # 使用默认图片
                    if len(node['widgets_values']) > 0:
                        prompt[node_id]["inputs"]["image"] = node['widgets_values'][0]
            else:
                # 普通节点的处理逻辑
                for i, value in enumerate(node['widgets_values']):
                    if i < len(widget_inputs):
                        input_name = widget_inputs[i]
                        prompt[node_id]["inputs"][input_name] = value
        
        # 为SaveImage节点确保有filename_prefix
        if node_type == 'SaveImage' and 'filename_prefix' not in prompt[node_id]["inputs"]:
            prompt[node_id]["inputs"]["filename_prefix"] = "ComfyUI"
    
    # 处理节点之间的链接，只处理有效节点之间的链接
    for link in workflow_data['links']:
        link_id, source_node_id, source_output_idx, target_node_id, target_input_idx, link_type = link
        
        source_node_str = str(source_node_id)
        target_node_str = str(target_node_id)
        
        # 确保源节点和目标节点都在有效节点列表中
        if source_node_str not in prompt or target_node_str not in prompt:
            continue
        
        # 找到目标节点中对应索引的输入参数名称
        target_node = next((n for n in valid_nodes if str(n['id']) == target_node_str), None)
        if target_node is None or target_input_idx >= len(target_node['inputs']):
            continue
        
        target_input_name = target_node['inputs'][target_input_idx]['name']
        
        # 设置链接值，格式为[源节点ID, 输出索引]
        prompt[target_node_str]["inputs"][target_input_name] = [source_node_str, source_output_idx]
    
    return prompt


# 由外界传入提示词和图片URL生成图片的函数
def generate_image_from_url_and_prompt(prompt_text, image_url, workflow_path=None):
    """
    从给定的图片URL和提示词生成新图片
    
    参数:
        prompt_text (str): 提示词文本
        image_url (str): 图片的URL地址
        workflow_path (str, optional): 工作流文件路径，如果为None则使用默认路径
        
    返回:
        dict: 包含生成结果的字典
    """
    try:
        # 如果没有提供工作流路径，使用默认路径
        if workflow_path is None:
            workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', 'image2image.json')
            
        # 1. 从URL下载图片到临时文件
        print(f"正在从URL下载图片: {image_url}")
        temp_image_path = download_image_from_url(image_url)
        
        try:
            # 2. 上传图片到ComfyUI服务器
            image_filename = upload_image(temp_image_path)
            
            # 3. 使用提示词和上传的图片加载工作流
            prompt = load_workflow_from_json(workflow_path, custom_prompt=prompt_text, image_filename=image_filename)
            
            # 4. 创建WebSocket连接到服务器
            ws = websocket.create_connection(f"ws://{server_address}/ws?clientId={client_id}")
            
            # 5. 获取生成的图像
            images = get_images(ws, prompt)
            
            # 6. 处理生成的图像
            results = []
            for node_id in images:
                for image_data in images[node_id]:
                    image = Image.open(io.BytesIO(image_data))
                    # 7. 上传图像到远程服务器
                    upload_result = uploadImage(image)
                    results.append({
                        'image_data': image_data,
                        'upload_result': upload_result
                    })
            
            return {
                'success': True,
                'results': results,
                'message': '图片生成和上传成功'
            }
        finally:
            # 清理临时文件
            if os.path.exists(temp_image_path):
                os.remove(temp_image_path)
    except Exception as e:
        print(f"图片生成过程中出错: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'message': '图片生成失败'
        }

# 辅助函数：从URL下载图片

def download_image_from_url(image_url):
    """
    从URL下载图片并保存到临时文件
    
    参数:
        image_url (str): 图片的URL地址
        
    返回:
        str: 临时文件的路径
    """
    import tempfile
    import urllib.request
    
    # 创建临时文件
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    temp_file_path = temp_file.name
    temp_file.close()
    
    # 下载图片到临时文件
    try:
        urllib.request.urlretrieve(image_url, temp_file_path)
        return temp_file_path
    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise Exception(f"下载图片失败: {str(e)}")

# 修改现有的uploadImage函数，使其返回上传结果
def uploadImage(image):
    import tempfile
    
    # 保存 image 到临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
        image.save(tmp_file)
        tmp_file_path = tmp_file.name
    
    # 确保文件在上传前完全读取并关闭
    file_data = None
    try:
        # 先读取文件内容到内存
        with open(tmp_file_path, 'rb') as file:
            file_data = file.read()
        
        # 此时文件已经关闭，不再持有文件句柄
        files = {'file': ('temp_image.png', file_data)}
        data = {
            'description': "自动生成的图片",
            'category': '',  # 可根据实际情况修改
            'tags': ''  # 可根据实际情况修改
        }
        
        response = requests.post('http://120.27.130.190:8091/api/files/upload', files=files, data=data)
        response.raise_for_status()
        result = response.json()
        print('文件上传成功，响应结果:', result)
        
        # 保存结果到文件
        with open('result.txt', 'w') as f:
            f.write(json.dumps(result))
            
        return result  # 返回上传结果
    except requests.RequestException as e:
        print(f'文件上传失败: {e}')
        return {'error': str(e)}
    finally:
        # 确保清理临时文件
        import os
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)


def main():
    # 定义默认提示语
    default_prompt = "outdoor portrait photography, beautiful woman in natural setting, golden hour sunlight, dappled light through leaves, garden background with blooming flowers, wind-blown hair, natural makeup, joyful expression, cinematic lighting, high dynamic range, professional color grading"
    
    # 定义默认图片路径（assets/images/woman1.png）
    default_image_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'images', 'girl.png')
    
    # 加载workflow文件
    workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', 'image2image.json')
    
    try:
        # 上传图片
        image_filename = upload_image(default_image_path)
        
        # 使用默认提示语和上传的图片加载工作流
        prompt = load_workflow_from_json(workflow_path, custom_prompt=default_prompt, image_filename=image_filename)
        
        # 创建一个WebSocket连接到服务器
        ws = websocket.create_connection("ws://{}/ws?clientId={}".format(server_address, client_id))
        
        # 调用get_images()函数来获取图像
        images = get_images(ws, prompt)
        
        # 显示图片
        for node_id in images:
            for image_data in images[node_id]:
                image = Image.open(io.BytesIO(image_data))
                image.show()
                uploadImage(image)
                input("")

    except Exception as e:
        print(f"程序执行出错: {str(e)}")


# 使用示例
def example_usage():
    # 提示词
    prompt = "outdoor portrait photography, beautiful woman in natural setting, golden hour sunlight"
    
    # 图片URL
    image_url = "http://120.27.130.190:8091/api/files/download/14d1ea3f-07ea-4302-afff-adc3e6d03c0e_tmpx4_5ndmd.png"
    
    # 调用图片生成函数
    result = generate_image_from_url_and_prompt(prompt, image_url)
    
    if result['success']:
        print("图片生成成功!")
        # 访问结果
        for i, item in enumerate(result['results']):
            print(f"结果 {i+1}: {item['upload_result']}")
    else:
        print(f"图片生成失败: {result['error']}")

if __name__ == "__main__":
    # main()
    example_usage()