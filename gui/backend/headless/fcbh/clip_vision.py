from transformers import CLIPVisionModelWithProjection, CLIPVisionConfig, modeling_utils
from .utils import load_torch_file, transformers_convert, common_upscale
import os
import torch
import contextlib

import fcbh.ops
import fcbh.model_patcher
import fcbh.model_management
import fcbh.utils

def clip_preprocess(image, size=224):
    mean = torch.tensor([ 0.48145466,0.4578275,0.40821073], device=image.device, dtype=image.dtype)
    std = torch.tensor([0.26862954,0.26130258,0.27577711], device=image.device, dtype=image.dtype)
    scale = (size / min(image.shape[1], image.shape[2]))
    image = torch.nn.functional.interpolate(image.movedim(-1, 1), size=(round(scale * image.shape[1]), round(scale * image.shape[2])), mode="bicubic", antialias=True)
    h = (image.shape[2] - size)//2
    w = (image.shape[3] - size)//2
    image = image[:,:,h:h+size,w:w+size]
    image = torch.clip((255. * image), 0, 255).round() / 255.0
    return (image - mean.view([3,1,1])) / std.view([3,1,1])

class ClipVisionModel():
    def __init__(self, json_config):
        config = CLIPVisionConfig.from_json_file(json_config)
        self.load_device = fcbh.model_management.text_encoder_device()
        offload_device = fcbh.model_management.text_encoder_offload_device()
        self.dtype = torch.float32
        if fcbh.model_management.should_use_fp16(self.load_device, prioritize_performance=False):
            self.dtype = torch.float16

        with fcbh.ops.use_fcbh_ops(offload_device, self.dtype):
            with modeling_utils.no_init_weights():
                self.model = CLIPVisionModelWithProjection(config)
        self.model.to(self.dtype)

        self.patcher = fcbh.model_patcher.ModelPatcher(self.model, load_device=self.load_device, offload_device=offload_device)
    def load_sd(self, sd):
        return self.model.load_state_dict(sd, strict=False)

    def encode_image(self, image):
        fcbh.model_management.load_model_gpu(self.patcher)
        pixel_values = clip_preprocess(image.to(self.load_device))

        if self.dtype != torch.float32:
            precision_scope = torch.autocast
        else:
            precision_scope = lambda a, b: contextlib.nullcontext(a)

        with precision_scope(fcbh.model_management.get_autocast_device(self.load_device), torch.float32):
            outputs = self.model(pixel_values=pixel_values, output_hidden_states=True)

        for k in outputs:
            t = outputs[k]
            if t is not None:
                if k == 'hidden_states':
                    outputs["penultimate_hidden_states"] = t[-2].cpu()
                    outputs["hidden_states"] = None
                else:
                    outputs[k] = t.cpu()

        return outputs

def convert_to_transformers(sd, prefix):
    sd_k = sd.keys()
    if "{}transformer.resblocks.0.attn.in_proj_weight".format(prefix) in sd_k:
        keys_to_replace = {
            "{}class_embedding".format(prefix): "vision_model.embeddings.class_embedding",
            "{}conv1.weight".format(prefix): "vision_model.embeddings.patch_embedding.weight",
            "{}positional_embedding".format(prefix): "vision_model.embeddings.position_embedding.weight",
            "{}ln_post.bias".format(prefix): "vision_model.post_layernorm.bias",
            "{}ln_post.weight".format(prefix): "vision_model.post_layernorm.weight",
            "{}ln_pre.bias".format(prefix): "vision_model.pre_layrnorm.bias",
            "{}ln_pre.weight".format(prefix): "vision_model.pre_layrnorm.weight",
        }

        for x in keys_to_replace:
            if x in sd_k:
                sd[keys_to_replace[x]] = sd.pop(x)

        if "{}proj".format(prefix) in sd_k:
            sd['visual_projection.weight'] = sd.pop("{}proj".format(prefix)).transpose(0, 1)

        sd = transformers_convert(sd, prefix, "vision_model.", 48)
    return sd

def load_clipvision_from_sd(sd, prefix="", convert_keys=False):
    if convert_keys:
        sd = convert_to_transformers(sd, prefix)
    if "vision_model.encoder.layers.47.layer_norm1.weight" in sd:
        json_config = os.path.join(os.path.dirname(os.path.realpath(__file__)), "clip_vision_config_g.json")
    elif "vision_model.encoder.layers.30.layer_norm1.weight" in sd:
        json_config = os.path.join(os.path.dirname(os.path.realpath(__file__)), "clip_vision_config_h.json")
    elif "vision_model.encoder.layers.22.layer_norm1.weight" in sd:
        json_config = os.path.join(os.path.dirname(os.path.realpath(__file__)), "clip_vision_config_vitl.json")
    else:
        return None

    clip = ClipVisionModel(json_config)
    m, u = clip.load_sd(sd)
    if len(m) > 0:
        print("missing clip vision:", m)
    u = set(u)
    keys = list(sd.keys())
    for k in keys:
        if k not in u:
            t = sd.pop(k)
            del t
    return clip

def load(ckpt_path):
    sd = load_torch_file(ckpt_path)
    if "visual.transformer.resblocks.0.attn.in_proj_weight" in sd:
        return load_clipvision_from_sd(sd, prefix="visual.", convert_keys=True)
    else:
        return load_clipvision_from_sd(sd)
