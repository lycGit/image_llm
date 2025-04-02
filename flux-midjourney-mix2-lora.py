from diffusers import StableDiffusionXLPipeline
import torch

pipe = StableDiffusionXLPipeline.from_pretrained(
    "segmind/SSD-1B", 
    torch_dtype=torch.float32,  # 改用 float32
    use_safetensors=True
)
pipe = pipe.to("cpu")  # 改用 CPU

prompt = "An astronaut riding a green horse"
neg_prompt = "ugly, blurry, poor quality"

# 添加更多参数来控制生成过程
image = pipe(
    prompt=prompt, 
    negative_prompt=neg_prompt,
    num_inference_steps=30,
    height=512,
    width=512,
).images[0]

image.save("output.png")