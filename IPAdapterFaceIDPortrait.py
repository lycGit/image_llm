
import cv2
from insightface.app import FaceAnalysis
import torch

app = FaceAnalysis(name="buffalo_l", providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
app.prepare(ctx_id=0, det_size=(257, 257))


# images = ["1.jpg", "2.jpg", "3.jpg", "4.jpg", "5.jpg"]
images = ["test_header_image.jpg"]

# faceid_embeds = []
# for image in images:
#     # image = cv2.imread("person.jpg")
#     faces = app.get(image)
#     faceid_embeds.append(torch.from_numpy(faces[0].normed_embedding).unsqueeze(0).unsqueeze(0))
# image = cv2.imread("ai_face.jpg")
# faces = app.get(image)
# faceid_embeds.append(torch.from_numpy(faces[0].normed_embedding).unsqueeze(0).unsqueeze(0))

image = cv2.imread("assets/images/woman1.png")
faces = app.get(image)
faceid_embeds = faces[0].normed_embedding
faceid_embeds = torch.from_numpy(faceid_embeds).unsqueeze(0)
# faceid_embeds = torch.cat(faceid_embeds, dim=1)

import torch
from diffusers import StableDiffusionPipeline, DDIMScheduler, AutoencoderKL
from PIL import Image

from ip_adapter.ip_adapter_faceid_separate import IPAdapterFaceID

base_model_path = "SG161222/Realistic_Vision_V4.0_noVAE"
vae_model_path = "stabilityai/sd-vae-ft-mse"
ip_ckpt = "models/ip-adapter-faceid-portrait_sd15.bin"
device = "mps"

noise_scheduler = DDIMScheduler(
    num_train_timesteps=100,
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


# load ip-adapter
ip_model = IPAdapterFaceID(pipe, ip_ckpt, device, num_tokens=16, n_cond=5)

# generate image
prompt = "photo of a woman in red dress in a garden"
negative_prompt = "monochrome, lowres, bad anatomy, worst quality, low quality, blurry"

images = ip_model.generate(
    prompt=prompt, negative_prompt=negative_prompt, faceid_embeds=faceid_embeds, num_samples=1, width=256, height=256, num_inference_steps=30, seed=2023
)
image = images[0]
image.save("output.png")



