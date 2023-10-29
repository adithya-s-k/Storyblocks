import torch
import contextlib
import math

from fcbh import model_management
from .ldm.util import instantiate_from_config
from .ldm.models.autoencoder import AutoencoderKL, AutoencodingEngine
import yaml

import fcbh.utils

from . import clip_vision
from . import gligen
from . import diffusers_convert
from . import model_base
from . import model_detection

from . import sd1_clip
from . import sd2_clip
from . import sdxl_clip

import fcbh.model_patcher
import fcbh.lora
import fcbh.t2i_adapter.adapter
import fcbh.supported_models_base

def load_model_weights(model, sd):
    m, u = model.load_state_dict(sd, strict=False)
    m = set(m)
    unexpected_keys = set(u)

    k = list(sd.keys())
    for x in k:
        if x not in unexpected_keys:
            w = sd.pop(x)
            del w
    if len(m) > 0:
        print("missing", m)
    return model

def load_clip_weights(model, sd):
    k = list(sd.keys())
    for x in k:
        if x.startswith("cond_stage_model.transformer.") and not x.startswith("cond_stage_model.transformer.text_model."):
            y = x.replace("cond_stage_model.transformer.", "cond_stage_model.transformer.text_model.")
            sd[y] = sd.pop(x)

    if 'cond_stage_model.transformer.text_model.embeddings.position_ids' in sd:
        ids = sd['cond_stage_model.transformer.text_model.embeddings.position_ids']
        if ids.dtype == torch.float32:
            sd['cond_stage_model.transformer.text_model.embeddings.position_ids'] = ids.round()

    sd = fcbh.utils.transformers_convert(sd, "cond_stage_model.model.", "cond_stage_model.transformer.text_model.", 24)
    return load_model_weights(model, sd)


def load_lora_for_models(model, clip, lora, strength_model, strength_clip):
    key_map = fcbh.lora.model_lora_keys_unet(model.model)
    key_map = fcbh.lora.model_lora_keys_clip(clip.cond_stage_model, key_map)
    loaded = fcbh.lora.load_lora(lora, key_map)
    new_modelpatcher = model.clone()
    k = new_modelpatcher.add_patches(loaded, strength_model)
    new_clip = clip.clone()
    k1 = new_clip.add_patches(loaded, strength_clip)
    k = set(k)
    k1 = set(k1)
    for x in loaded:
        if (x not in k) and (x not in k1):
            print("NOT LOADED", x)

    return (new_modelpatcher, new_clip)


class CLIP:
    def __init__(self, target=None, embedding_directory=None, no_init=False):
        if no_init:
            return
        params = target.params.copy()
        clip = target.clip
        tokenizer = target.tokenizer

        load_device = model_management.text_encoder_device()
        offload_device = model_management.text_encoder_offload_device()
        params['device'] = offload_device
        if model_management.should_use_fp16(load_device, prioritize_performance=False):
            params['dtype'] = torch.float16
        else:
            params['dtype'] = torch.float32

        self.cond_stage_model = clip(**(params))

        self.tokenizer = tokenizer(embedding_directory=embedding_directory)
        self.patcher = fcbh.model_patcher.ModelPatcher(self.cond_stage_model, load_device=load_device, offload_device=offload_device)
        self.layer_idx = None

    def clone(self):
        n = CLIP(no_init=True)
        n.patcher = self.patcher.clone()
        n.cond_stage_model = self.cond_stage_model
        n.tokenizer = self.tokenizer
        n.layer_idx = self.layer_idx
        return n

    def add_patches(self, patches, strength_patch=1.0, strength_model=1.0):
        return self.patcher.add_patches(patches, strength_patch, strength_model)

    def clip_layer(self, layer_idx):
        self.layer_idx = layer_idx

    def tokenize(self, text, return_word_ids=False):
        return self.tokenizer.tokenize_with_weights(text, return_word_ids)

    def encode_from_tokens(self, tokens, return_pooled=False):
        if self.layer_idx is not None:
            self.cond_stage_model.clip_layer(self.layer_idx)
        else:
            self.cond_stage_model.reset_clip_layer()

        self.load_model()
        cond, pooled = self.cond_stage_model.encode_token_weights(tokens)
        if return_pooled:
            return cond, pooled
        return cond

    def encode(self, text):
        tokens = self.tokenize(text)
        return self.encode_from_tokens(tokens)

    def load_sd(self, sd):
        return self.cond_stage_model.load_sd(sd)

    def get_sd(self):
        return self.cond_stage_model.state_dict()

    def load_model(self):
        model_management.load_model_gpu(self.patcher)
        return self.patcher

    def get_key_patches(self):
        return self.patcher.get_key_patches()

class VAE:
    def __init__(self, sd=None, device=None, config=None):
        if 'decoder.up_blocks.0.resnets.0.norm1.weight' in sd.keys(): #diffusers format
            sd = diffusers_convert.convert_vae_state_dict(sd)

        if config is None:
            #default SD1.x/SD2.x VAE parameters
            ddconfig = {'double_z': True, 'z_channels': 4, 'resolution': 256, 'in_channels': 3, 'out_ch': 3, 'ch': 128, 'ch_mult': [1, 2, 4, 4], 'num_res_blocks': 2, 'attn_resolutions': [], 'dropout': 0.0}
            self.first_stage_model = AutoencoderKL(ddconfig=ddconfig, embed_dim=4)
        else:
            self.first_stage_model = AutoencoderKL(**(config['params']))
        self.first_stage_model = self.first_stage_model.eval()

        m, u = self.first_stage_model.load_state_dict(sd, strict=False)
        if len(m) > 0:
            print("Missing VAE keys", m)

        if len(u) > 0:
            print("Leftover VAE keys", u)

        if device is None:
            device = model_management.vae_device()
        self.device = device
        self.offload_device = model_management.vae_offload_device()
        self.vae_dtype = model_management.vae_dtype()
        self.first_stage_model.to(self.vae_dtype)

    def decode_tiled_(self, samples, tile_x=64, tile_y=64, overlap = 16):
        steps = samples.shape[0] * fcbh.utils.get_tiled_scale_steps(samples.shape[3], samples.shape[2], tile_x, tile_y, overlap)
        steps += samples.shape[0] * fcbh.utils.get_tiled_scale_steps(samples.shape[3], samples.shape[2], tile_x // 2, tile_y * 2, overlap)
        steps += samples.shape[0] * fcbh.utils.get_tiled_scale_steps(samples.shape[3], samples.shape[2], tile_x * 2, tile_y // 2, overlap)
        pbar = fcbh.utils.ProgressBar(steps)

        decode_fn = lambda a: (self.first_stage_model.decode(a.to(self.vae_dtype).to(self.device)) + 1.0).float()
        output = torch.clamp((
            (fcbh.utils.tiled_scale(samples, decode_fn, tile_x // 2, tile_y * 2, overlap, upscale_amount = 8, pbar = pbar) +
            fcbh.utils.tiled_scale(samples, decode_fn, tile_x * 2, tile_y // 2, overlap, upscale_amount = 8, pbar = pbar) +
             fcbh.utils.tiled_scale(samples, decode_fn, tile_x, tile_y, overlap, upscale_amount = 8, pbar = pbar))
            / 3.0) / 2.0, min=0.0, max=1.0)
        return output

    def encode_tiled_(self, pixel_samples, tile_x=512, tile_y=512, overlap = 64):
        steps = pixel_samples.shape[0] * fcbh.utils.get_tiled_scale_steps(pixel_samples.shape[3], pixel_samples.shape[2], tile_x, tile_y, overlap)
        steps += pixel_samples.shape[0] * fcbh.utils.get_tiled_scale_steps(pixel_samples.shape[3], pixel_samples.shape[2], tile_x // 2, tile_y * 2, overlap)
        steps += pixel_samples.shape[0] * fcbh.utils.get_tiled_scale_steps(pixel_samples.shape[3], pixel_samples.shape[2], tile_x * 2, tile_y // 2, overlap)
        pbar = fcbh.utils.ProgressBar(steps)

        encode_fn = lambda a: self.first_stage_model.encode((2. * a - 1.).to(self.vae_dtype).to(self.device)).float()
        samples = fcbh.utils.tiled_scale(pixel_samples, encode_fn, tile_x, tile_y, overlap, upscale_amount = (1/8), out_channels=4, pbar=pbar)
        samples += fcbh.utils.tiled_scale(pixel_samples, encode_fn, tile_x * 2, tile_y // 2, overlap, upscale_amount = (1/8), out_channels=4, pbar=pbar)
        samples += fcbh.utils.tiled_scale(pixel_samples, encode_fn, tile_x // 2, tile_y * 2, overlap, upscale_amount = (1/8), out_channels=4, pbar=pbar)
        samples /= 3.0
        return samples

    def decode(self, samples_in):
        self.first_stage_model = self.first_stage_model.to(self.device)
        try:
            memory_used = (2562 * samples_in.shape[2] * samples_in.shape[3] * 64) * 1.7
            model_management.free_memory(memory_used, self.device)
            free_memory = model_management.get_free_memory(self.device)
            batch_number = int(free_memory / memory_used)
            batch_number = max(1, batch_number)

            pixel_samples = torch.empty((samples_in.shape[0], 3, round(samples_in.shape[2] * 8), round(samples_in.shape[3] * 8)), device="cpu")
            for x in range(0, samples_in.shape[0], batch_number):
                samples = samples_in[x:x+batch_number].to(self.vae_dtype).to(self.device)
                pixel_samples[x:x+batch_number] = torch.clamp((self.first_stage_model.decode(samples).cpu().float() + 1.0) / 2.0, min=0.0, max=1.0)
        except model_management.OOM_EXCEPTION as e:
            print("Warning: Ran out of memory when regular VAE decoding, retrying with tiled VAE decoding.")
            pixel_samples = self.decode_tiled_(samples_in)

        self.first_stage_model = self.first_stage_model.to(self.offload_device)
        pixel_samples = pixel_samples.cpu().movedim(1,-1)
        return pixel_samples

    def decode_tiled(self, samples, tile_x=64, tile_y=64, overlap = 16):
        self.first_stage_model = self.first_stage_model.to(self.device)
        output = self.decode_tiled_(samples, tile_x, tile_y, overlap)
        self.first_stage_model = self.first_stage_model.to(self.offload_device)
        return output.movedim(1,-1)

    def encode(self, pixel_samples):
        self.first_stage_model = self.first_stage_model.to(self.device)
        pixel_samples = pixel_samples.movedim(-1,1)
        try:
            memory_used = (2078 * pixel_samples.shape[2] * pixel_samples.shape[3]) * 1.7 #NOTE: this constant along with the one in the decode above are estimated from the mem usage for the VAE and could change.
            model_management.free_memory(memory_used, self.device)
            free_memory = model_management.get_free_memory(self.device)
            batch_number = int(free_memory / memory_used)
            batch_number = max(1, batch_number)
            samples = torch.empty((pixel_samples.shape[0], 4, round(pixel_samples.shape[2] // 8), round(pixel_samples.shape[3] // 8)), device="cpu")
            for x in range(0, pixel_samples.shape[0], batch_number):
                pixels_in = (2. * pixel_samples[x:x+batch_number] - 1.).to(self.vae_dtype).to(self.device)
                samples[x:x+batch_number] = self.first_stage_model.encode(pixels_in).cpu().float()

        except model_management.OOM_EXCEPTION as e:
            print("Warning: Ran out of memory when regular VAE encoding, retrying with tiled VAE encoding.")
            samples = self.encode_tiled_(pixel_samples)

        self.first_stage_model = self.first_stage_model.to(self.offload_device)
        return samples

    def encode_tiled(self, pixel_samples, tile_x=512, tile_y=512, overlap = 64):
        self.first_stage_model = self.first_stage_model.to(self.device)
        pixel_samples = pixel_samples.movedim(-1,1)
        samples = self.encode_tiled_(pixel_samples, tile_x=tile_x, tile_y=tile_y, overlap=overlap)
        self.first_stage_model = self.first_stage_model.to(self.offload_device)
        return samples

    def get_sd(self):
        return self.first_stage_model.state_dict()

class StyleModel:
    def __init__(self, model, device="cpu"):
        self.model = model

    def get_cond(self, input):
        return self.model(input.last_hidden_state)


def load_style_model(ckpt_path):
    model_data = fcbh.utils.load_torch_file(ckpt_path, safe_load=True)
    keys = model_data.keys()
    if "style_embedding" in keys:
        model = fcbh.t2i_adapter.adapter.StyleAdapter(width=1024, context_dim=768, num_head=8, n_layes=3, num_token=8)
    else:
        raise Exception("invalid style model {}".format(ckpt_path))
    model.load_state_dict(model_data)
    return StyleModel(model)


def load_clip(ckpt_paths, embedding_directory=None):
    clip_data = []
    for p in ckpt_paths:
        clip_data.append(fcbh.utils.load_torch_file(p, safe_load=True))

    class EmptyClass:
        pass

    for i in range(len(clip_data)):
        if "transformer.resblocks.0.ln_1.weight" in clip_data[i]:
            clip_data[i] = fcbh.utils.transformers_convert(clip_data[i], "", "text_model.", 32)

    clip_target = EmptyClass()
    clip_target.params = {}
    if len(clip_data) == 1:
        if "text_model.encoder.layers.30.mlp.fc1.weight" in clip_data[0]:
            clip_target.clip = sdxl_clip.SDXLRefinerClipModel
            clip_target.tokenizer = sdxl_clip.SDXLTokenizer
        elif "text_model.encoder.layers.22.mlp.fc1.weight" in clip_data[0]:
            clip_target.clip = sd2_clip.SD2ClipModel
            clip_target.tokenizer = sd2_clip.SD2Tokenizer
        else:
            clip_target.clip = sd1_clip.SD1ClipModel
            clip_target.tokenizer = sd1_clip.SD1Tokenizer
    else:
        clip_target.clip = sdxl_clip.SDXLClipModel
        clip_target.tokenizer = sdxl_clip.SDXLTokenizer

    clip = CLIP(clip_target, embedding_directory=embedding_directory)
    for c in clip_data:
        m, u = clip.load_sd(c)
        if len(m) > 0:
            print("clip missing:", m)

        if len(u) > 0:
            print("clip unexpected:", u)
    return clip

def load_gligen(ckpt_path):
    data = fcbh.utils.load_torch_file(ckpt_path, safe_load=True)
    model = gligen.load_gligen(data)
    if model_management.should_use_fp16():
        model = model.half()
    return fcbh.model_patcher.ModelPatcher(model, load_device=model_management.get_torch_device(), offload_device=model_management.unet_offload_device())

def load_checkpoint(config_path=None, ckpt_path=None, output_vae=True, output_clip=True, embedding_directory=None, state_dict=None, config=None):
    #TODO: this function is a mess and should be removed eventually
    if config is None:
        with open(config_path, 'r') as stream:
            config = yaml.safe_load(stream)
    model_config_params = config['model']['params']
    clip_config = model_config_params['cond_stage_config']
    scale_factor = model_config_params['scale_factor']
    vae_config = model_config_params['first_stage_config']

    fp16 = False
    if "unet_config" in model_config_params:
        if "params" in model_config_params["unet_config"]:
            unet_config = model_config_params["unet_config"]["params"]
            if "use_fp16" in unet_config:
                fp16 = unet_config.pop("use_fp16")
                if fp16:
                    unet_config["dtype"] = torch.float16

    noise_aug_config = None
    if "noise_aug_config" in model_config_params:
        noise_aug_config = model_config_params["noise_aug_config"]

    model_type = model_base.ModelType.EPS

    if "parameterization" in model_config_params:
        if model_config_params["parameterization"] == "v":
            model_type = model_base.ModelType.V_PREDICTION

    clip = None
    vae = None

    class WeightsLoader(torch.nn.Module):
        pass

    if state_dict is None:
        state_dict = fcbh.utils.load_torch_file(ckpt_path)

    class EmptyClass:
        pass

    model_config = fcbh.supported_models_base.BASE({})

    from . import latent_formats
    model_config.latent_format = latent_formats.SD15(scale_factor=scale_factor)
    model_config.unet_config = unet_config

    if config['model']["target"].endswith("ImageEmbeddingConditionedLatentDiffusion"):
        model = model_base.SD21UNCLIP(model_config, noise_aug_config["params"], model_type=model_type)
    else:
        model = model_base.BaseModel(model_config, model_type=model_type)

    if config['model']["target"].endswith("LatentInpaintDiffusion"):
        model.set_inpaint()

    if fp16:
        model = model.half()

    offload_device = model_management.unet_offload_device()
    model = model.to(offload_device)
    model.load_model_weights(state_dict, "model.diffusion_model.")

    if output_vae:
        vae_sd = fcbh.utils.state_dict_prefix_replace(state_dict, {"first_stage_model.": ""}, filter_keys=True)
        vae = VAE(sd=vae_sd, config=vae_config)

    if output_clip:
        w = WeightsLoader()
        clip_target = EmptyClass()
        clip_target.params = clip_config.get("params", {})
        if clip_config["target"].endswith("FrozenOpenCLIPEmbedder"):
            clip_target.clip = sd2_clip.SD2ClipModel
            clip_target.tokenizer = sd2_clip.SD2Tokenizer
        elif clip_config["target"].endswith("FrozenCLIPEmbedder"):
            clip_target.clip = sd1_clip.SD1ClipModel
            clip_target.tokenizer = sd1_clip.SD1Tokenizer
        clip = CLIP(clip_target, embedding_directory=embedding_directory)
        w.cond_stage_model = clip.cond_stage_model
        load_clip_weights(w, state_dict)

    return (fcbh.model_patcher.ModelPatcher(model, load_device=model_management.get_torch_device(), offload_device=offload_device), clip, vae)

def load_checkpoint_guess_config(ckpt_path, output_vae=True, output_clip=True, output_clipvision=False, embedding_directory=None, output_model=True):
    sd = fcbh.utils.load_torch_file(ckpt_path)
    sd_keys = sd.keys()
    clip = None
    clipvision = None
    vae = None
    model = None
    model_patcher = None
    clip_target = None

    parameters = fcbh.utils.calculate_parameters(sd, "model.diffusion_model.")
    unet_dtype = model_management.unet_dtype(model_params=parameters)

    class WeightsLoader(torch.nn.Module):
        pass

    model_config = model_detection.model_config_from_unet(sd, "model.diffusion_model.", unet_dtype)
    if model_config is None:
        raise RuntimeError("ERROR: Could not detect model type of: {}".format(ckpt_path))

    if model_config.clip_vision_prefix is not None:
        if output_clipvision:
            clipvision = clip_vision.load_clipvision_from_sd(sd, model_config.clip_vision_prefix, True)

    if output_model:
        inital_load_device = model_management.unet_inital_load_device(parameters, unet_dtype)
        offload_device = model_management.unet_offload_device()
        model = model_config.get_model(sd, "model.diffusion_model.", device=inital_load_device)
        model.load_model_weights(sd, "model.diffusion_model.")

    if output_vae:
        vae_sd = fcbh.utils.state_dict_prefix_replace(sd, {"first_stage_model.": ""}, filter_keys=True)
        vae = VAE(sd=vae_sd)

    if output_clip:
        w = WeightsLoader()
        clip_target = model_config.clip_target()
        if clip_target is not None:
            clip = CLIP(clip_target, embedding_directory=embedding_directory)
            w.cond_stage_model = clip.cond_stage_model
            sd = model_config.process_clip_state_dict(sd)
            load_model_weights(w, sd)

    left_over = sd.keys()
    if len(left_over) > 0:
        print("left over keys:", left_over)

    if output_model:
        model_patcher = fcbh.model_patcher.ModelPatcher(model, load_device=model_management.get_torch_device(), offload_device=model_management.unet_offload_device(), current_device=inital_load_device)
        if inital_load_device != torch.device("cpu"):
            print("loaded straight to GPU")
            model_management.load_model_gpu(model_patcher)

    return (model_patcher, clip, vae, clipvision)


def load_unet(unet_path): #load unet in diffusers format
    sd = fcbh.utils.load_torch_file(unet_path)
    parameters = fcbh.utils.calculate_parameters(sd)
    unet_dtype = model_management.unet_dtype(model_params=parameters)
    if "input_blocks.0.0.weight" in sd: #ldm
        model_config = model_detection.model_config_from_unet(sd, "", unet_dtype)
        if model_config is None:
            raise RuntimeError("ERROR: Could not detect model type of: {}".format(unet_path))
        new_sd = sd

    else: #diffusers
        model_config = model_detection.model_config_from_diffusers_unet(sd, unet_dtype)
        if model_config is None:
            print("ERROR UNSUPPORTED UNET", unet_path)
            return None

        diffusers_keys = fcbh.utils.unet_to_diffusers(model_config.unet_config)

        new_sd = {}
        for k in diffusers_keys:
            if k in sd:
                new_sd[diffusers_keys[k]] = sd.pop(k)
            else:
                print(diffusers_keys[k], k)
    offload_device = model_management.unet_offload_device()
    model = model_config.get_model(new_sd, "")
    model = model.to(offload_device)
    model.load_model_weights(new_sd, "")
    return fcbh.model_patcher.ModelPatcher(model, load_device=model_management.get_torch_device(), offload_device=offload_device)

def save_checkpoint(output_path, model, clip, vae, metadata=None):
    model_management.load_models_gpu([model, clip.load_model()])
    sd = model.model.state_dict_for_saving(clip.get_sd(), vae.get_sd())
    fcbh.utils.save_torch_file(sd, output_path, metadata=metadata)
