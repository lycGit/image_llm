# from diffusers import StableDiffusionXLPipeline
# import torch
#
# pipe = StableDiffusionXLPipeline.from_pretrained(
#     "segmind/SSD-1B",
#     torch_dtype=torch.float32,  # 改用 float32
#     use_safetensors=True
# )
# pipe = pipe.to("cpu")  # 改用 CPU
#
# # prompt = "An astronaut riding a green horse"
# prompt = "城市夜景，车流穿梭，赛博朋克风格"
# neg_prompt = "ugly, blurry, poor quality"
#
# # 添加更多参数来控制生成过程
# image = pipe(
#     prompt=prompt,
#     negative_prompt=neg_prompt,
#     num_inference_steps=30,
#     height=512,
#     width=512,
# ).images[0]
#
# image.save("output.png")
#
import argparse

# from diffusers import KandinskyPipeline
# import torch
#
# pipe = KandinskyPipeline.from_pretrained(
#     "kandinsky-community/kandinsky-2-2-decoder",
#     torch_dtype=torch.float16,
# ).to("mps")
#
# image = pipe("中国山水画，雾气缭绕，水墨风格").images[0]
# image.save("kandinsky_output.png")

import requests
import json

from diffusers import KandinskyV22Pipeline, KandinskyV22PriorPipeline
import torch

parser = argparse.ArgumentParser(description='图像生成脚本')
parser.add_argument('--discribe', required=True, help='生成图像的提示词')
args = parser.parse_args()
# 修改：使用命令行参数作为prompt
prompt = args.discribe
# 初始化 prior pipeline
prior = KandinskyV22PriorPipeline.from_pretrained(
    "kandinsky-community/kandinsky-2-2-prior",
    torch_dtype=torch.float32
).to("mps")

# 初始化主要 pipeline
pipe = KandinskyV22Pipeline.from_pretrained(
    "kandinsky-community/kandinsky-2-2-decoder",
    torch_dtype=torch.float32
).to("mps")

# prompt = "中国山水画，雾气缭绕，水墨风格"
# negative_prompt = "低质量, 模糊"

# prompt = "一幅震撼的写实油画：18-22岁东亚少女，无瑕如玉的肌肤泛青瓷底调，凤眼含露珠般纯真，玫瑰色嘴唇抿出羞涩微笑，乌黑秀发垂肩点缀珍珠发簪，半透明宋制纱衣透出精致锁骨，仿宫灯柔光晕染，青绿与珍珠白为基调搭配朱砂点缀，笔触精准呈现宣纸肌肤的透光感，背景融合水墨远山与飘落樱花，技法上融合17世纪欧洲肖像画精度与沈周的诗意笔韵 --v 6 --ar 9:16 --style raw"
negative_prompt = "低质量, 模糊"

# # 生成图像嵌入
prior_output = prior(
    prompt, negative_prompt, guidance_scale=1.0
)

# 生成最终图像
image = pipe(
    prompt=prompt,
    negative_prompt=negative_prompt,
    image_embeds=prior_output.image_embeds,
    negative_image_embeds=prior_output.negative_image_embeds,
    # height=512,
    # width=512,
    height=256,
    width=256,
    num_inference_steps=50
).images[0]

image.save("kandinsky_output.png")

import tempfile

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
    # response = requests.post('http://127.0.0.1:8091/api/files/upload', files=files, data=data)
    response = requests.post('http://120.27.130.190:8091/api/files/upload', files=files, data=data)
    response.raise_for_status()
    with open('result.txt', 'w') as f:
      f.write(json.dumps(response.json()))
    # print('文件上传成功，响应结果:', response.json())
    print(response.json())
except requests.RequestException as e:
    # print('文件上传失败:', e)
    print(e)
finally:
    import os
    os.remove(tmp_file_path)