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
import tempfile
import signal
import sys

# 设置服务器地址和客户端
server_address = "127.0.0.1:8188"
client_id = str(uuid.uuid4())

# 标志变量，用于控制程序是否继续运行
should_continue = True

# 信号处理函数，用于优雅地处理中断
def signal_handler(sig, frame):
    global should_continue
    print('\n程序被中断，正在清理资源...')
    should_continue = False

# 注册信号处理函数
signal.signal(signal.SIGINT, signal_handler)

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
    global should_continue
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}
    while should_continue:
        try:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        break  # 执行完成
                    elif data['node'] is not None:
                        print(f"正在执行节点: {data['node']} ({data['progress']*100:.1f}%)")
            else:
                continue  # 预览是二进制数据
        except websocket.WebSocketConnectionClosedException:
            print("WebSocket连接已关闭")
            break
        except Exception as e:
            print(f"接收消息时出错: {str(e)}")
            break

    if not should_continue:
        print("程序被用户中断")
        return {}

    history = get_history(prompt_id)[prompt_id]
    for o in history['outputs']:
        for node_id in history['outputs']:
            node_output = history['outputs'].get(node_id, {})
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

        # 使用files参数以multipart/form-data格式上传
        with open(image_path, "rb") as f:
            files = {'image': (filename, f)}
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

# 加载视频工作流
def load_video_workflow_from_json(file_path, custom_prompt=None, image_filename=None, negative_prompt=None):
    """
    从JSON文件加载视频工作流，并设置自定义提示词和图片
    
    参数:
        file_path (str): 工作流文件路径
        custom_prompt (str, optional): 自定义提示词
        image_filename (str, optional): 图片文件名
        negative_prompt (str, optional): 负面提示词
        
    返回:
        dict: 配置好的工作流提示对象
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        workflow_data = json.load(f)

    # 创建提示对象
    prompt = {}

    # 过滤掉MarkdownNote和Note节点，因为它们只是注释，不是实际功能节点
    valid_nodes = [node for node in workflow_data.get('nodes', []) if node.get('type') not in ['MarkdownNote', 'Note']]

    # 为每个有效节点创建基本结构
    for node in valid_nodes:
        node_id = str(node.get('id', ''))
        if node_id:
            prompt[node_id] = {
                "inputs": {},
                "class_type": node.get('type', '')
            }

    # 处理每个有效节点的widgets_values和输入参数
    for node in valid_nodes:
        node_id = str(node.get('id', ''))
        if node_id not in prompt:
            continue
        
        node_type = node.get('type', '')

        # 获取所有带widget的输入参数名称
        widget_inputs = [input.get('name', '') for input in node.get('inputs', []) if 'widget' in input]

        # 如果有widgets_values，将其映射到对应的输入参数
        if 'widgets_values' in node:
            # 特殊处理KSampler节点
            if node_type == 'KSamplerAdvanced':
                # 根据视频工作流的widgets_values结构处理参数
                # 通常包括采样步数、CFG等参数
                if len(node['widgets_values']) >= 5:
                    try:
                        # 处理seed
                        if len(node['widgets_values']) > 1 and node['widgets_values'][1] == 'randomize':
                            prompt[node_id]["inputs"]["seed"] = random.randint(0, 2**32 - 1)
                        elif len(node['widgets_values']) > 1:
                            try:
                                prompt[node_id]["inputs"]["seed"] = int(node['widgets_values'][1])
                            except (ValueError, TypeError):
                                prompt[node_id]["inputs"]["seed"] = random.randint(0, 2**32 - 1)
                    except Exception as e:
                        print(f"处理KSampler参数时出错: {str(e)}")
                        prompt[node_id]["inputs"]["seed"] = random.randint(0, 2**32 - 1)
            elif node_type == 'CLIPTextEncode':
                # 处理文本编码节点，检查是否需要替换提示语
                if len(node['widgets_values']) > 0:
                    original_prompt = node['widgets_values'][0]
                    # 检查是否是正面提示节点（判断依据是标题或原始内容）
                    if (hasattr(node, 'title') and "Positive" in node['title']) or ("white dragon warrior" in original_prompt and not "色调艳丽" in original_prompt):
                        # 使用自定义提示语
                        if custom_prompt:
                            prompt[node_id]["inputs"]["text"] = custom_prompt
                        else:
                            # 使用原始提示语
                            prompt[node_id]["inputs"]["text"] = original_prompt
                    elif (hasattr(node, 'title') and "Negative" in node['title']) or ("色调艳丽" in original_prompt):
                        # 使用自定义负面提示语
                        if negative_prompt:
                            prompt[node_id]["inputs"]["text"] = negative_prompt
                        else:
                            # 使用原始负面提示语
                            prompt[node_id]["inputs"]["text"] = original_prompt
                    else:
                        # 其他文本节点保持原样
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
            elif node_type == 'WanImageToVideo':
                # 特殊处理WanImageToVideo节点
                if len(node['widgets_values']) >= 4:
                    # 设置视频尺寸等参数
                    try:
                        prompt[node_id]["inputs"]["width"] = node['widgets_values'][0]  # 宽度
                        prompt[node_id]["inputs"]["height"] = node['widgets_values'][1]  # 高度
                        prompt[node_id]["inputs"]["seed"] = node['widgets_values'][2]  # 种子
                        prompt[node_id]["inputs"]["motion_strength"] = node['widgets_values'][3]  # 运动强度
                    except (IndexError, ValueError, TypeError):
                        print("WanImageToVideo节点参数设置失败，使用默认值")
            else:
                # 普通节点的处理逻辑
                for i, value in enumerate(node['widgets_values']):
                    if i < len(widget_inputs):
                        input_name = widget_inputs[i]
                        prompt[node_id]["inputs"][input_name] = value

        # 为SaveImage节点确保有filename_prefix
        if node_type == 'SaveImage' and 'filename_prefix' not in prompt[node_id]["inputs"]:
            prompt[node_id]["inputs"]["filename_prefix"] = "ComfyUI"
            
        # 为CreateVideo节点确保有必要的参数
        elif node_type == 'CreateVideo' or node_type == 'SaveVideo':
            # 添加必要的视频参数
            if 'filename_prefix' not in prompt[node_id]["inputs"]:
                prompt[node_id]["inputs"]["filename_prefix"] = "ComfyUI_video"
            if 'format' not in prompt[node_id]["inputs"]:
                prompt[node_id]["inputs"]["format"] = "mp4"
            if 'codec' not in prompt[node_id]["inputs"]:
                prompt[node_id]["inputs"]["codec"] = "h264"
            # 为CreateVideo节点添加fps参数
            if node_type == 'CreateVideo' and 'fps' not in prompt[node_id]["inputs"]:
                prompt[node_id]["inputs"]["fps"] = 24  # 设置合理的帧率
        
        # 处理节点38的type参数（根据错误信息）
        if node_id == '38' and 'type' not in prompt[node_id]["inputs"]:
            # 使用有效的type值，根据错误信息，有效值包括：stable_diffusion, stable_cascade, sd3等
            prompt[node_id]["inputs"]["type"] = "stable_diffusion"  # 使用stable_diffusion作为默认值

    # 处理节点之间的链接，只处理有效节点之间的链接
    if 'links' in workflow_data:
        for link in workflow_data['links']:
            if len(link) >= 5:
                link_id, source_node_id, source_output_idx, target_node_id, target_input_idx = link[:5]
                link_type = link[5] if len(link) > 5 else None

                source_node_str = str(source_node_id)
                target_node_str = str(target_node_id)

                # 确保源节点和目标节点都在有效节点列表中
                if source_node_str not in prompt or target_node_str not in prompt:
                    continue

                # 找到目标节点中对应索引的输入参数名称
                target_node = next((n for n in valid_nodes if str(n.get('id', '')) == target_node_str), None)
                if target_node is None or target_input_idx >= len(target_node.get('inputs', [])):
                    continue

                target_input_name = target_node.get('inputs', [{}])[target_input_idx].get('name', '')
                if target_input_name:
                    # 设置链接值，格式为[源节点ID, 输出索引]
                    prompt[target_node_str]["inputs"][target_input_name] = [source_node_str, source_output_idx]

    return prompt

# 由外界传入提示词和图片URL生成视频的函数
def generate_video_from_url_and_prompt(prompt_text, image_url, workflow_path=None, negative_prompt=None):
    """
    从给定的图片URL和提示词生成视频
    
    参数:
        prompt_text (str): 提示词文本
        image_url (str): 图片的URL地址
        workflow_path (str, optional): 工作流文件路径，如果为None则使用默认路径
        negative_prompt (str, optional): 负面提示词
        
    返回:
        dict: 包含生成结果的字典
    """
    global should_continue
    temp_image_path = None
    ws = None
    
    try:
        # 如果没有提供工作流路径，使用默认路径
        if workflow_path is None:
            workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', 'video_wan2_2_14B_i2v.json')
            
        # 1. 从URL下载图片到临时文件
        print(f"正在从URL下载图片: {image_url}")
        temp_image_path = download_image_from_url(image_url)
        
        # 2. 上传图片到ComfyUI服务器
        image_filename = upload_image(temp_image_path)
        
        # 3. 使用提示词和上传的图片加载视频工作流
        print(f"正在加载工作流文件: {workflow_path}")
        prompt = load_video_workflow_from_json(
            workflow_path, 
            custom_prompt=prompt_text, 
            image_filename=image_filename,
            negative_prompt=negative_prompt
        )
        
        # 检查是否被中断
        if not should_continue:
            return {
                'success': False,
                'error': '程序被用户中断',
                'message': '视频生成被用户中断'
            }
        
        # 4. 创建WebSocket连接到服务器
        print("正在连接到ComfyUI服务器...")
        ws = websocket.WebSocket()
        ws.connect(f"ws://{server_address}/ws?clientId={client_id}")
        
        # 5. 只调用一次queue_prompt，避免重复生成视频
        print("正在提交视频生成任务...")
        prompt_id = queue_prompt(prompt)['prompt_id']
        print(f"任务ID: {prompt_id}")
        print("视频生成中，请等待...")
        
        # 6. 等待视频生成完成并获取中间帧
        output_images = {}
        while should_continue:
            try:
                out = ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    if message['type'] == 'executing':
                        data = message['data']
                        if data['node'] is not None:
                            # 显示当前执行的节点和进度
                            print(f"\r正在执行节点: {data['node']} ({data['progress']*100:.1f}%)", end="", flush=True)
                        if data['node'] is None and data['prompt_id'] == prompt_id:
                            print()  # 换行
                            break  # 执行完成
                else:
                    continue  # 预览是二进制数据
            except websocket.WebSocketConnectionClosedException:
                print("WebSocket连接已关闭")
                break
            except Exception as e:
                print(f"接收消息时出错: {str(e)}")
                break
        
        if not should_continue:
            print("程序被用户中断")
            return {
                'success': False,
                'error': '程序被用户中断',
                'message': '视频生成被用户中断'
            }
        
        # 7. 从历史记录中获取视频信息
        history = get_history(prompt_id).get(prompt_id, {})
        frames_count = 0
        
        # 计算生成的帧数
        for node_id, node_output in history.get('outputs', {}).items():
            if 'images' in node_output:
                frames_count += len(node_output['images'])
        
        # 查找视频输出信息
        video_info = None
        for node_id, node_output in history.get('outputs', {}).items():
            if 'videos' in node_output:
                video_info = node_output['videos'][0]  # 假设只有一个视频输出
                break
            # 如果没有直接的视频输出，检查是否有保存视频的信息
            elif 'ui' in node_output and 'videos' in node_output['ui']:
                video_info = node_output['ui']['videos'][0]
                break
        
        # 如果找到了视频信息，尝试下载视频
        if video_info:
            try:
                # 构建视频下载URL
                if 'filename' in video_info and 'subfolder' in video_info and 'type' in video_info:
                    video_url = f"http://{server_address}/view?filename={video_info['filename']}&subfolder={video_info['subfolder']}&type={video_info['type']}"
                    print(f"视频生成成功，可从以下地址下载: {video_url}")
                
                return {
                    'success': True,
                    'video_info': video_info,
                    'frames_count': frames_count,
                    'message': '视频生成成功'
                }
            except Exception as e:
                print(f"获取视频信息时出错: {str(e)}")
                # 即使无法获取视频URL，仍返回成功状态，因为视频已在ComfyUI中生成
                return {
                    'success': True,
                    'frames_count': frames_count,
                    'message': '视频生成成功，但获取视频URL失败'
                }
        else:
            # 如果没有找到视频信息，返回帧信息
            return {
                'success': True,
                'frames_count': frames_count,
                'message': '视频生成成功，但未找到视频文件信息'
            }
    except Exception as e:
        print(f"视频生成过程中出错: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'message': '视频生成失败'
        }
    finally:
        # 清理WebSocket连接
        if ws is not None:
            try:
                ws.close()
            except:
                pass
        
        # 清理临时文件
        if temp_image_path and os.path.exists(temp_image_path):
            try:
                os.remove(temp_image_path)
            except:
                pass

# 辅助函数：从URL下载图片
def download_image_from_url(image_url):
    """
    从URL下载图片并保存到临时文件
    
    参数:
        image_url (str): 图片的URL地址
        
    返回:
        str: 临时文件的路径
    """
    # 创建临时文件
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    temp_file_path = temp_file.name
    temp_file.close()
    
    # 下载图片到临时文件
    try:
        print(f"开始下载图片到临时文件: {temp_file_path}")
        urllib.request.urlretrieve(image_url, temp_file_path)
        print(f"图片下载完成，大小: {os.path.getsize(temp_file_path)} 字节")
        return temp_file_path
    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise Exception(f"下载图片失败: {str(e)}")

# 上传文件函数
def uploadImage(image):
    # 保存 image 到临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
        image.save(tmp_file)
        tmp_file_path = tmp_file.name
    
    files = {'file': open(tmp_file_path, 'rb')}
    data = {
        'description': "自动生成的图片",
        'category': '',  # 可根据实际情况修改
        'tags': ''  # 可根据实际情况修改
    }
    try:
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
        os.remove(tmp_file_path)

# 视频生成示例
def main():
    # 定义默认提示语
    default_prompt = "The white dragon warrior stands still, eyes full of determination and strength. The camera slowly moves closer or circles around the warrior, highlighting the powerful presence and heroic spirit of the character."
    
    # 定义默认图片路径
    default_image_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'images', 'girl.png')
    
    # 加载workflow文件
    workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', 'video_wan2_2_14B_i2v.json')
    
    try:
        # 上传图片
        image_filename = upload_image(default_image_path)
        
        # 使用默认提示语和上传的图片加载工作流
        prompt = load_video_workflow_from_json(workflow_path, custom_prompt=default_prompt, image_filename=image_filename)
        
        # 创建一个WebSocket连接到服务器
        ws = websocket.WebSocket()
        ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
        
        # 获取生成的帧
        frames = get_images(ws, prompt)
        
        print(f"视频生成完成，生成了 {sum(len(f) for f in frames.values())} 帧")
        print("视频已保存在ComfyUI的输出目录中")
        
    except Exception as e:
        print(f"程序执行出错: {str(e)}")

# URL图片转视频示例
def example_video_usage():
    # 提示词
    prompt = "A beautiful landscape with mountains and lake, clouds moving slowly across the sky"
    
    # 图片URL
    image_url = "http://120.27.130.190:8091/api/files/download/14d1ea3f-07ea-4302-afff-adc3e6d03c0e_tmpx4_5ndmd.png"
    
    # 可选的负面提示词
    negative_prompt = "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止"
    
    print("开始视频生成示例...")
    print(f"提示词: {prompt}")
    print(f"图片URL: {image_url}")
    
    # 调用视频生成函数
    result = generate_video_from_url_and_prompt(prompt, image_url, negative_prompt=negative_prompt)
    
    if result['success']:
        print("视频生成成功!")
        print(f"生成的帧数: {result['frames_count']}")
        if 'video_info' in result:
            print(f"视频信息: {result['video_info']}")
    else:
        print(f"视频生成失败: {result['error']}")

if __name__ == "__main__":
    # 运行示例
    # main()
    example_video_usage()