import os
from dashscope import MultiModalConversation
import dashscope

# 以下为北京地域base_url，若使用弗吉尼亚地域模型，需要将base_url换成 https://dashscope-us.aliyuncs.com/api/v1
# 若使用新加坡地域的模型，需将base_url替换为：https://dashscope-intl.aliyuncs.com/api/v1
dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

# 将xxx/eagle.png替换为你本地图像的绝对路径
local_path = "/Users/lyc/Desktop/oldstylecompressimage/02_compressed.jpg"
image_path = f"file://{local_path}"
messages = [
                {'role':'user',
                'content': [{'image': image_path},
                            {'text': '请根据这张图片，反推出生成该图片的提示词。注意当前这张图片和之前的图片是不一样的，请仔细查看图片细节。提示词要求分成两部分，一部分描述背景和风格，另外一部分描述人物衣着，头发，体态姿势等人物本身。注意，描述人物部分的提示词要避免有对人物脸部五官的描述内容，以免后续使用时人物脸部失真。只需要输出中文部分'}]}]
response = MultiModalConversation.call(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx"
    # 各地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    api_key="sk-1f85075ccbba49bb80c72c43c1f53254",
    model='qwen3.5-plus',  # 此处以qwen3.5-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/models
    messages=messages)
print(response.output.choices[0].message.content[0]["text"])

