import torch
from diffusers import StableDiffusionPipeline, StableDiffusionImg2ImgPipeline, StableDiffusionInpaintPipelineLegacy, DDIMScheduler, AutoencoderKL
from PIL import Image

from ip_adapter import IPAdapterPlus

base_model_path = "runwayml/stable-diffusion-v1-5"
vae_model_path = "stabilityai/sd-vae-ft-mse"
image_encoder_path = "models/image_encoder/"
ip_ckpt = "models/ip-adapter-plus-face_sd15.bin"
device = "mps"


def image_grid(imgs, rows, cols):
    assert len(imgs) == rows * cols

    w, h = imgs[0].size
    grid = Image.new('RGB', size=(cols * w, rows * h))
    grid_w, grid_h = grid.size

    for i, img in enumerate(imgs):
        grid.paste(img, box=(i % cols * w, i // cols * h))
    return grid


noise_scheduler = DDIMScheduler(
    num_train_timesteps=1000,
    beta_start=0.00085,
    beta_end=0.012,
    beta_schedule="scaled_linear",
    clip_sample=False,
    set_alpha_to_one=False,
    steps_offset=1,
)
vae = AutoencoderKL.from_pretrained(vae_model_path).to(dtype=torch.float16)

pipe = StableDiffusionPipeline.from_pretrained(
    base_model_path,
    torch_dtype=torch.float16,
    scheduler=noise_scheduler,
    vae=vae,
    feature_extractor=None,
    safety_checker=None
)

image = Image.open("assets/images/ai_face.png")
image.resize((256, 256))

ip_model = IPAdapterPlus(pipe, image_encoder_path, ip_ckpt, device, num_tokens=16)

images = ip_model.generate(pil_image=image, num_samples=1, num_inference_steps=100, seed=420,
        prompt="The image features a young woman with long, flowing hair styled in soft waves. She has a gentle expression, highlighted by large, expressive eyes and a subtle smile. She's dressed in a sleek, cream-colored blazer over a light top, giving her a polished and sophisticated appearance. Her pose, with one hand gently touching her chin, conveys a sense of thoughtfulness and poise. The background is a soft, neutral tone, enhancing the overall elegance of the portrait.")

image = images[0]
image.save("output4.png")