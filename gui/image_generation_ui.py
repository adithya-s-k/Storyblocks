from image_generator.python_hijack import *

import gradio as gr
import random
import os
import time
import image_generator.shared
import image_generator.modules.path
import image_generator.modules.html
import image_generator.modules.async_worker as worker
import image_generator.modules.constants as constants
import image_generator.modules.flags as flags
import image_generator.modules.gradio_hijack as grh
import image_generator.modules.advanced_parameters as advanced_parameters
# import gui.args_manager

from image_generator.modules.sdxl_styles import legal_style_names
from image_generator.modules.private_logger import get_current_html_path
from image_generator.modules.ui_gradio_extensions import reload_javascript
from image_generator.modules.auth import auth_enabled, check_auth

def generate_clicked(*args):
    # outputs=[progress_html, progress_window, progress_gallery, gallery]
    print(args)
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

    yield gr.update(visible=True, value=modules.html.make_progress_html(1, 'Initializing ...')), \
        gr.update(visible=True, value=None), \
        gr.update(visible=False, value=None), \
        gr.update(visible=False)

    worker.buffer.append(list(args))
    finished = False

    while not finished:
        time.sleep(0.01)
        if len(worker.outputs) > 0:
            flag, product = worker.outputs.pop(0)
            if flag == 'preview':
                percentage, title, image = product
                yield gr.update(visible=True, value=modules.html.make_progress_html(percentage, title)), \
                    gr.update(visible=True, value=image) if image is not None else gr.update(), \
                    gr.update(), \
                    gr.update(visible=False)
            if flag == 'results':
                yield gr.update(visible=True), \
                    gr.update(visible=True), \
                    gr.update(visible=True, value=product), \
                    gr.update(visible=False)
            if flag == 'finish':
                yield gr.update(visible=False), \
                    gr.update(visible=False), \
                    gr.update(visible=False), \
                    gr.update(visible=True, value=product)
                finished = True

    execution_time = time.perf_counter() - execution_start_time
    print(f'Total time: {execution_time:.2f} seconds')
    return


reload_javascript()


def Automatic1111API(StoryBlocksUI: gr.Blocks):
    with gr.Row(visible=False) as automatic1111_api:
        with gr.Column():
            gr.Markdown("## Automatic1111 API")
            gr.Markdown("### Coming Soon")
    return automatic1111_api

def SDXLLocal(StoryBlocksUI: gr.Blocks):
    with gr.Row(visible=False) as sdxl_local:
        with gr.Column():
            gr.Markdown("## SDXL Local")
        with gr.Row():
            with gr.Column(scale=2):
                with gr.Row():
                    progress_window = grh.Image(label='Preview', show_label=True, height=640, visible=False)
                    progress_gallery = gr.Gallery(label='Finished Images', show_label=True, object_fit='contain', height=640, visible=False)
                progress_html = gr.HTML(value=modules.html.make_progress_html(32, 'Progress 32%'), visible=False, elem_id='progress-bar', elem_classes='progress-bar')
                gallery = gr.Gallery(label='Gallery', show_label=False, object_fit='contain', height=745, visible=True, elem_classes='resizable_area')
                with gr.Row(elem_classes='type_row'):
                    with gr.Column(scale=17):
                        prompt = gr.Textbox(show_label=False, placeholder="Type prompt here.",
                                            container=False, autofocus=True, elem_classes='type_row', lines=1024)

                        default_prompt = modules.path.default_prompt
                        if isinstance(default_prompt, str) and default_prompt != '':
                            shared.gradio_root.load(lambda: default_prompt, outputs=prompt)

                    with gr.Column(scale=3, min_width=0):
                        generate_button = gr.Button(label="Generate", value="Generate", elem_classes='type_row', elem_id='generate_button', visible=True)
                        skip_button = gr.Button(label="Skip", value="Skip", elem_classes='type_row_half', visible=False)
                        stop_button = gr.Button(label="Stop", value="Stop", elem_classes='type_row_half', elem_id='stop_button', visible=False)

                        def stop_clicked():
                            import fcbh.model_management as model_management
                            shared.last_stop = 'stop'
                            model_management.interrupt_current_processing()
                            return [gr.update(interactive=False)] * 2

                        def skip_clicked():
                            import fcbh.model_management as model_management
                            shared.last_stop = 'skip'
                            model_management.interrupt_current_processing()
                            return

                        stop_button.click(stop_clicked, outputs=[skip_button, stop_button], queue=False, _js='cancelGenerateForever')
                        skip_button.click(skip_clicked, queue=False)
                with gr.Row(elem_classes='advanced_check_row'):
                    advanced_checkbox = gr.Checkbox(label='Advanced', value=modules.path.default_advanced_checkbox, container=False, elem_classes='min_check')

                def update_default_image(x):
                    global default_image
                    if isinstance(x, dict):
                        default_image = x['image']
                    else:
                        default_image = x
                    return

                def clear_default_image():
                    global default_image
                    default_image = None
                    return
            with gr.Column(scale=1, visible=modules.path.default_advanced_checkbox) as advanced_column:
                with gr.Tab(label='Setting'):
                    performance_selection = gr.Radio(label='Performance', choices=['Speed', 'Quality'], value='Speed')
                    aspect_ratios_selection = gr.Radio(label='Aspect Ratios', choices=modules.path.available_aspect_ratios,
                                                    value=modules.path.default_aspect_ratio, info='width × height')
                    image_number = gr.Slider(label='Image Number', minimum=1, maximum=32, step=1, value=modules.path.default_image_number)
                    negative_prompt = gr.Textbox(label='Negative Prompt', show_label=True, placeholder="Type prompt here.",
                                                info='Describing what you do not want to see.', lines=2,
                                                value=modules.path.default_prompt_negative)
                    seed_random = gr.Checkbox(label='Random', value=True)
                    image_seed = gr.Textbox(label='Seed', value=0, max_lines=1, visible=False) # workaround for https://github.com/gradio-app/gradio/issues/5354

                    def random_checked(r):
                        return gr.update(visible=not r)

                    def refresh_seed(r, seed_string):
                        if r:
                            return random.randint(constants.MIN_SEED, constants.MAX_SEED)
                        else:
                            try:
                                seed_value = int(seed_string)
                                if constants.MIN_SEED <= seed_value <= constants.MAX_SEED:
                                    return seed_value
                            except ValueError:
                                pass
                            return random.randint(constants.MIN_SEED, constants.MAX_SEED)

                    seed_random.change(random_checked, inputs=[seed_random], outputs=[image_seed], queue=False)

                    gr.HTML(f'<a href="/file={get_current_html_path()}" target="_blank">\U0001F4DA History Log</a>')

                with gr.Tab(label='Style'):
                    style_selections = gr.CheckboxGroup(show_label=False, container=False,
                                                        choices=legal_style_names,
                                                        value=modules.path.default_styles,
                                                        label='Image Style')
                with gr.Tab(label='Model'):
                    with gr.Row():
                        base_model = gr.Dropdown(label='Base Model (SDXL only)', choices=modules.path.model_filenames, value=modules.path.default_base_model_name, show_label=True)
                        refiner_model = gr.Dropdown(label='Refiner (SDXL or SD 1.5)', choices=['None'] + modules.path.model_filenames, value=modules.path.default_refiner_model_name, show_label=True)
                    with gr.Accordion(label='LoRAs', open=True):
                        lora_ctrls = []
                        for i in range(5):
                            with gr.Row():
                                lora_model = gr.Dropdown(label=f'SDXL LoRA {i+1}', choices=['None'] + modules.path.lora_filenames, value=modules.path.default_lora_name if i == 0 else 'None')
                                lora_weight = gr.Slider(label='Weight', minimum=-2, maximum=2, step=0.01, value=modules.path.default_lora_weight)
                                lora_ctrls += [lora_model, lora_weight]
                    with gr.Row():
                        model_refresh = gr.Button(label='Refresh', value='\U0001f504 Refresh All Files', variant='secondary', elem_classes='refresh_button')
                with gr.Tab(label='Advanced'):
                    sharpness = gr.Slider(label='Sampling Sharpness', minimum=0.0, maximum=30.0, step=0.001, value=2.0,
                                        info='Higher value means image and texture are sharper.')
                    guidance_scale = gr.Slider(label='Guidance Scale', minimum=1.0, maximum=30.0, step=0.01, value=modules.path.default_cfg_scale,
                                        info='Higher value means style is cleaner, vivider, and more artistic.')
                    refiner_switch = gr.Slider(label='Refiner Switch At', minimum=0.0, maximum=1.0, step=0.0001,
                                            info='When to switch from base model to the refiner (if refiner is used).',
                                            value=modules.path.default_refiner_switch)

                    # gr.HTML('<a href="https://github.com/lllyasviel/Fooocus/discussions/117" target="_blank">\U0001F4D4 Document</a>')
                    # dev_mode = gr.Checkbox(label='Developer Debug Mode', value=False, container=False)

                    # with gr.Column(visible=False) as dev_tools:
                    #     with gr.Tab(label='Developer Debug Tools'):
                    #         adm_scaler_positive = gr.Slider(label='Positive ADM Guidance Scaler', minimum=0.1, maximum=3.0,
                    #                                         step=0.001, value=1.5, info='The scaler multiplied to positive ADM (use 1.0 to disable). ')
                    #         adm_scaler_negative = gr.Slider(label='Negative ADM Guidance Scaler', minimum=0.1, maximum=3.0,
                    #                                         step=0.001, value=0.8, info='The scaler multiplied to negative ADM (use 1.0 to disable). ')
                    #         adm_scaler_end = gr.Slider(label='ADM Guidance End At Step', minimum=0.0, maximum=1.0,
                    #                                    step=0.001, value=0.3,
                    #                                    info='When to end the guidance from positive/negative ADM. ')

                    #         refiner_swap_method = gr.Dropdown(label='Refiner swap method', value='joint',
                    #                                           choices=['joint', 'separate', 'vae'])

                    #         adaptive_cfg = gr.Slider(label='CFG Mimicking from TSNR', minimum=1.0, maximum=30.0, step=0.01, value=7.0,
                    #                                  info='Enabling Fooocus\'s implementation of CFG mimicking for TSNR '
                    #                                       '(effective when real CFG > mimicked CFG).')
                    #         sampler_name = gr.Dropdown(label='Sampler', choices=flags.sampler_list,
                    #                                    value=modules.path.default_sampler,
                    #                                    info='Only effective in non-inpaint mode.')
                    #         scheduler_name = gr.Dropdown(label='Scheduler', choices=flags.scheduler_list,
                    #                                      value=modules.path.default_scheduler,
                    #                                      info='Scheduler of Sampler.')

                    #         overwrite_step = gr.Slider(label='Forced Overwrite of Sampling Step',
                    #                                    minimum=-1, maximum=200, step=1, value=-1,
                    #                                    info='Set as -1 to disable. For developer debugging.')
                    #         overwrite_switch = gr.Slider(label='Forced Overwrite of Refiner Switch Step',
                    #                                      minimum=-1, maximum=200, step=1, value=-1,
                    #                                      info='Set as -1 to disable. For developer debugging.')
                    #         overwrite_width = gr.Slider(label='Forced Overwrite of Generating Width',
                    #                                     minimum=-1, maximum=2048, step=1, value=-1,
                    #                                     info='Set as -1 to disable. For developer debugging. '
                    #                                          'Results will be worse for non-standard numbers that SDXL is not trained on.')
                    #         overwrite_height = gr.Slider(label='Forced Overwrite of Generating Height',
                    #                                      minimum=-1, maximum=2048, step=1, value=-1,
                    #                                      info='Set as -1 to disable. For developer debugging. '
                    #                                           'Results will be worse for non-standard numbers that SDXL is not trained on.')
                    #         overwrite_vary_strength = gr.Slider(label='Forced Overwrite of Denoising Strength of "Vary"',
                    #                                             minimum=-1, maximum=1.0, step=0.001, value=-1,
                    #                                             info='Set as negative number to disable. For developer debugging.')
                    #         overwrite_upscale_strength = gr.Slider(label='Forced Overwrite of Denoising Strength of "Upscale"',
                    #                                                minimum=-1, maximum=1.0, step=0.001, value=-1,
                    #                                                info='Set as negative number to disable. For developer debugging.')

                    #         inpaint_engine = gr.Dropdown(label='Inpaint Engine', value='v1', choices=['v1', 'v2.5'],
                    #                                      info='Version of Fooocus inpaint model')

                    #     with gr.Tab(label='Control Debug'):
                    #         debugging_cn_preprocessor = gr.Checkbox(label='Debug Preprocessors', value=False)

                    #         mixing_image_prompt_and_vary_upscale = gr.Checkbox(label='Mixing Image Prompt and Vary/Upscale',
                    #                                                            value=False)
                    #         mixing_image_prompt_and_inpaint = gr.Checkbox(label='Mixing Image Prompt and Inpaint',
                    #                                                       value=False)

                    #         controlnet_softness = gr.Slider(label='Softness of ControlNet', minimum=0.0, maximum=1.0,
                    #                                         step=0.001, value=0.25,
                    #                                         info='Similar to the Control Mode in A1111 (use 0.0 to disable). ')

                    #         with gr.Tab(label='Canny'):
                    #             canny_low_threshold = gr.Slider(label='Canny Low Threshold', minimum=1, maximum=255,
                    #                                             step=1, value=64)
                    #             canny_high_threshold = gr.Slider(label='Canny High Threshold', minimum=1, maximum=255,
                    #                                              step=1, value=128)

                    #     with gr.Tab(label='FreeU'):
                    #         freeu_enabled = gr.Checkbox(label='Enabled', value=False)
                    #         freeu_b1 = gr.Slider(label='B1', minimum=0, maximum=2, step=0.01, value=1.01)
                    #         freeu_b2 = gr.Slider(label='B2', minimum=0, maximum=2, step=0.01, value=1.02)
                    #         freeu_s1 = gr.Slider(label='S1', minimum=0, maximum=4, step=0.01, value=0.99)
                    #         freeu_s2 = gr.Slider(label='S2', minimum=0, maximum=4, step=0.01, value=0.95)
                    #         freeu_ctrls = [freeu_enabled, freeu_b1, freeu_b2, freeu_s1, freeu_s2]

                    # adps = [adm_scaler_positive, adm_scaler_negative, adm_scaler_end, adaptive_cfg, sampler_name,
                    #         scheduler_name, overwrite_step, overwrite_switch, overwrite_width, overwrite_height,
                    #         overwrite_vary_strength, overwrite_upscale_strength,
                    #         mixing_image_prompt_and_vary_upscale, mixing_image_prompt_and_inpaint,
                    #         debugging_cn_preprocessor, controlnet_softness, canny_low_threshold, canny_high_threshold,
                    #         inpaint_engine, refiner_swap_method]
                    # adps += freeu_ctrls

                    # def dev_mode_checked(r):
                    #     return gr.update(visible=r)


                    # dev_mode.change(dev_mode_checked, inputs=[dev_mode], outputs=[dev_tools], queue=False)

                    def model_refresh_clicked():
                        modules.path.update_all_model_names()
                        results = []
                        results += [gr.update(choices=modules.path.model_filenames), gr.update(choices=['None'] + modules.path.model_filenames)]
                        for i in range(5):
                            results += [gr.update(choices=['None'] + modules.path.lora_filenames), gr.update()]
                        return results

                    model_refresh.click(model_refresh_clicked, [], [base_model, refiner_model] + lora_ctrls, queue=False)

            advanced_checkbox.change(lambda x: gr.update(visible=x), advanced_checkbox, advanced_column, queue=False)

            ctrls = [
                prompt, negative_prompt, style_selections,
                performance_selection, aspect_ratios_selection, image_number, image_seed, sharpness, guidance_scale
            ]

            ctrls += [base_model, refiner_model, refiner_switch] + lora_ctrls
            # ctrls += [input_image_checkbox, current_tab]
            # ctrls += [uov_method, uov_input_image]
            # ctrls += [outpaint_selections, inpaint_input_image]
            # ctrls += ip_ctrls

            generate_button.click(lambda: (gr.update(visible=True, interactive=True), gr.update(visible=True, interactive=True), gr.update(visible=False), []), outputs=[stop_button, skip_button, generate_button, gallery]) \
                .then(fn=refresh_seed, inputs=[seed_random, image_seed], outputs=image_seed) \
                .then(fn=generate_clicked, inputs=ctrls, outputs=[progress_html, progress_window, progress_gallery, gallery
                                                                ]) \
                .then(lambda: (gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)), outputs=[generate_button, stop_button, skip_button]) \
                # .then(fn=None, _js='playNotification')
                # .then(advanced_parameters.set_all_advanced_parameters, inputs=adps) \            
    return sdxl_local

def StabilityAIAPI(StoryBlocksUI: gr.Blocks):
    with gr.Row(visible=False) as stability_ai_api:
        with gr.Column():
            gr.Markdown("## Stability AI API")
            gr.Markdown("### Coming Soon")
    return stability_ai_api

def image_generation_ui(StoryBlocksUI: gr.Blocks):
    with gr.Tab("Generate Images") as image_generation_ui:
        gr.Markdown("## Generate Image")
        image_generator_option = gr.Radio(["Automatic1111 API", "SDXL Local" , "Stability AI API"], label="Choose an image generator")
        
        automatic1111_api = Automatic1111API(StoryBlocksUI)
        sdxl_local = SDXLLocal(StoryBlocksUI)
        stability_ai_api = StabilityAIAPI(StoryBlocksUI)
        
        generate_image_button = gr.Button("Generate Images", size="sm", interactive=True, visible=True)
        image_generator_option.change(lambda x: (gr.update(visible= x == image_generator_option.choices[0]), gr.update(visible= x == image_generator_option.choices[1]), gr.update(visible= x == image_generator_option.choices[2])), [image_generator_option], [automatic1111_api , sdxl_local ,stability_ai_api ]) # type: ignore
        
    return image_generation_ui


