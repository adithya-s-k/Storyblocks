from python_hijack import *
import random
import os
import time
import shared
import modules.path
import modules.html
import modules.async_worker as worker
import modules.constants as constants
import modules.flags as flags
import modules.advanced_parameters as advanced_parameters

from modules.sdxl_styles import legal_style_names
from modules.private_logger import get_current_html_path
from modules.ui_gradio_extensions import reload_javascript
from modules.auth import auth_enabled, check_auth


def generate_image(args):
    adm_scaler_positive = 1.5
    adm_scaler_negative = 0.8
    adm_scaler_end = 0.3
    refiner_swap_method = 'joint'
    adaptive_cfg = 7.0
    sampler_name=modules.path.default_sampler
    scheduler_name=modules.path.default_scheduler
    # The default values for sampler_name and scheduler_name are not provided in the code snippet.
    overwrite_step = -1
    overwrite_switch = -1
    overwrite_width = -1
    overwrite_height = -1
    overwrite_vary_strength = -1
    overwrite_upscale_strength = -1
    inpaint_engine = 'v1'
    debugging_cn_preprocessor = False
    mixing_image_prompt_and_vary_upscale = False
    mixing_image_prompt_and_inpaint = False
    controlnet_softness = 0.25
    canny_low_threshold = 64
    canny_high_threshold = 128
    freeu_enabled = False
    freeu_b1 = 1.01
    freeu_b2 = 1.02
    freeu_s1 = 0.99
    freeu_s2 = 0.95
    freeu_ctrls = [freeu_enabled, freeu_b1, freeu_b2, freeu_s1, freeu_s2]
    
    adps = [adm_scaler_positive, adm_scaler_negative, adm_scaler_end, adaptive_cfg, sampler_name,
        scheduler_name, overwrite_step, overwrite_switch, overwrite_width, overwrite_height,
        overwrite_vary_strength, overwrite_upscale_strength,
        mixing_image_prompt_and_vary_upscale, mixing_image_prompt_and_inpaint,
        debugging_cn_preprocessor, controlnet_softness, canny_low_threshold, canny_high_threshold,
        inpaint_engine, refiner_swap_method]
    adps += freeu_ctrls
    advanced_parameters.set_all_advanced_parameters(*adps)
    
    execution_start_time = time.perf_counter()
    
    worker.outputs = []
    
    worker.buffer.append(list(args))    
    finished = False
    
    while not finished:
        time.sleep(0.01)
        if len(worker.outputs)>0:
            flag, product = worker.outputs.pop(0)
            if flag == "preview":
                percentage ,title, image = product
                print(f"Currently Generating the image {percentage}....\n")
            if flag == "results":
                print("completed Generation")
            if flag == "finish":
                print("Finished")
                finished = True
    execution_time = time.perf_counter() - execution_start_time
    print(f'Total time: {execution_time:.2f} seconds')
    return

arguments = ['boy going to the moon', '', ['Fooocus V2', 'Fooocus Enhance', 'Fooocus Sharp'], 'Speed', '1152×896', 2, '3865406845012980985', 2, 7, 'sd_xl_base_1.0_0.9vae.safetensors', 'sd_xl_refiner_1.0_0.9vae.safetensors', 0.8, 'sd_xl_offset_example-lora_1.0.safetensors', 0.5, 'None', 0.5, 'None', 0.5, 'None', 0.5, 'None' , 0.5]


generate_image(arguments)