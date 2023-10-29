import threading


buffer = []
outputs = []
global_results = []


def worker():
    global buffer, outputs, global_results

    import traceback
    import numpy as np
    import torch
    import time
    import shared
    import random
    import copy
    import modules.default_pipeline as pipeline
    import modules.core as core
    import modules.flags as flags
    import modules.path
    import modules.patch
    import fcbh.model_management
    import fooocus_extras.preprocessors as preprocessors
    import modules.inpaint_worker as inpaint_worker
    import modules.constants as constants
    import modules.advanced_parameters as advanced_parameters
    import fooocus_extras.ip_adapter as ip_adapter

    from modules.sdxl_styles import apply_style, apply_wildcards, fooocus_expansion
    from modules.private_logger import log
    from modules.expansion import safe_str
    from modules.util import join_prompts, remove_empty_str, HWC3, resize_image, \
        get_image_shape_ceil, set_image_shape_ceil, get_shape_ceil, resample_image
    from modules.upscaler import perform_upscale

    try:
        async_gradio_app = shared.gradio_root
        flag = f'''App started successful. Use the app with {str(async_gradio_app.local_url)} or {str(async_gradio_app.server_name)}:{str(async_gradio_app.server_port)}'''
        if async_gradio_app.share:
            flag += f''' or {async_gradio_app.share_url}'''
        print(flag)
    except Exception as e:
        print(e)

    def progressbar(number, text):
        print(f'[Fooocus] {text}')
        outputs.append(['preview', (number, text, None)])

    def yield_result(imgs, do_not_show_finished_images=False):
        global global_results

        if not isinstance(imgs, list):
            imgs = [imgs]

        global_results = global_results + imgs

        if do_not_show_finished_images:
            return

        outputs.append(['results', global_results])
        return

    @torch.no_grad()
    @torch.inference_mode()
    def handler(args):
        execution_start_time = time.perf_counter()

        args.reverse()

        prompt = args.pop()
        negative_prompt = args.pop()
        style_selections = args.pop()
        performance_selection = args.pop()
        aspect_ratios_selection = args.pop()
        image_number = args.pop()
        image_seed = args.pop()
        sharpness = args.pop()
        guidance_scale = args.pop()
        base_model_name = args.pop()
        refiner_model_name = args.pop()
        refiner_switch = args.pop()
        loras = [(args.pop(), args.pop()) for _ in range(5)]
        input_image_checkbox = args.pop()
        current_tab = args.pop()
        uov_method = args.pop()
        uov_input_image = args.pop()
        outpaint_selections = args.pop()
        inpaint_input_image = args.pop()

        cn_tasks = {flags.cn_ip: [], flags.cn_canny: [], flags.cn_cpds: []}
        for _ in range(4):
            cn_img = args.pop()
            cn_stop = args.pop()
            cn_weight = args.pop()
            cn_type = args.pop()
            if cn_img is not None:
                cn_tasks[cn_type].append([cn_img, cn_stop, cn_weight])

        outpaint_selections = [o.lower() for o in outpaint_selections]
        loras_raw = copy.deepcopy(loras)
        raw_style_selections = copy.deepcopy(style_selections)
        uov_method = uov_method.lower()

        if fooocus_expansion in style_selections:
            use_expansion = True
            style_selections.remove(fooocus_expansion)
        else:
            use_expansion = False

        use_style = len(style_selections) > 0

        modules.patch.adaptive_cfg = advanced_parameters.adaptive_cfg
        print(f'[Parameters] Adaptive CFG = {modules.patch.adaptive_cfg}')

        modules.patch.sharpness = sharpness
        print(f'[Parameters] Sharpness = {modules.patch.sharpness}')

        modules.patch.positive_adm_scale = advanced_parameters.adm_scaler_positive
        modules.patch.negative_adm_scale = advanced_parameters.adm_scaler_negative
        modules.patch.adm_scaler_end = advanced_parameters.adm_scaler_end
        print(f'[Parameters] ADM Scale = {modules.patch.positive_adm_scale} : {modules.patch.negative_adm_scale} : {modules.patch.adm_scaler_end}')

        cfg_scale = float(guidance_scale)
        print(f'[Parameters] CFG = {cfg_scale}')

        initial_latent = None
        denoising_strength = 1.0
        tiled = False
        inpaint_worker.current_task = None

        width, height = aspect_ratios_selection.split('×')
        width, height = int(width), int(height)

        skip_prompt_processing = False
        refiner_swap_method = advanced_parameters.refiner_swap_method

        inpaint_image = None
        inpaint_mask = None
        inpaint_head_model_path = None
        controlnet_canny_path = None
        controlnet_cpds_path = None
        clip_vision_path, ip_negative_path, ip_adapter_path = None, None, None

        seed = int(image_seed)
        print(f'[Parameters] Seed = {seed}')

        if performance_selection == 'Speed':
            steps = 30
        else:
            steps = 60

        sampler_name = advanced_parameters.sampler_name
        scheduler_name = advanced_parameters.scheduler_name

        goals = []
        tasks = []

        if input_image_checkbox:
            if (current_tab == 'uov' or (current_tab == 'ip' and advanced_parameters.mixing_image_prompt_and_vary_upscale)) \
                    and uov_method != flags.disabled and uov_input_image is not None:
                uov_input_image = HWC3(uov_input_image)
                if 'vary' in uov_method:
                    goals.append('vary')
                elif 'upscale' in uov_method:
                    goals.append('upscale')
                    if 'fast' in uov_method:
                        skip_prompt_processing = True
                    else:
                        if performance_selection == 'Speed':
                            steps = 18
                        else:
                            steps = 36
                    progressbar(1, 'Downloading upscale models ...')
                    modules.path.downloading_upscale_model()
            if (current_tab == 'inpaint' or (current_tab == 'ip' and advanced_parameters.mixing_image_prompt_and_inpaint))\
                    and isinstance(inpaint_input_image, dict):
                inpaint_image = inpaint_input_image['image']
                inpaint_mask = inpaint_input_image['mask'][:, :, 0]
                inpaint_image = HWC3(inpaint_image)
                if isinstance(inpaint_image, np.ndarray) and isinstance(inpaint_mask, np.ndarray) \
                        and (np.any(inpaint_mask > 127) or len(outpaint_selections) > 0):
                    progressbar(1, 'Downloading inpainter ...')
                    inpaint_head_model_path, inpaint_patch_model_path = modules.path.downloading_inpaint_models(advanced_parameters.inpaint_engine)
                    loras += [(inpaint_patch_model_path, 1.0)]
                    print(f'[Inpaint] Current inpaint model is {inpaint_patch_model_path}')
                    goals.append('inpaint')
            if current_tab == 'ip' or \
                    advanced_parameters.mixing_image_prompt_and_inpaint or \
                    advanced_parameters.mixing_image_prompt_and_vary_upscale:
                goals.append('cn')
                progressbar(1, 'Downloading control models ...')
                if len(cn_tasks[flags.cn_canny]) > 0:
                    controlnet_canny_path = modules.path.downloading_controlnet_canny()
                if len(cn_tasks[flags.cn_cpds]) > 0:
                    controlnet_cpds_path = modules.path.downloading_controlnet_cpds()
                if len(cn_tasks[flags.cn_ip]) > 0:
                    clip_vision_path, ip_negative_path, ip_adapter_path = modules.path.downloading_ip_adapters()
                progressbar(1, 'Loading control models ...')

        # Load or unload CNs
        pipeline.refresh_controlnets([controlnet_canny_path, controlnet_cpds_path])
        ip_adapter.load_ip_adapter(clip_vision_path, ip_negative_path, ip_adapter_path)

        switch = int(round(steps * refiner_switch))

        if advanced_parameters.overwrite_step > 0:
            steps = advanced_parameters.overwrite_step

        if advanced_parameters.overwrite_switch > 0:
            switch = advanced_parameters.overwrite_switch

        if advanced_parameters.overwrite_width > 0:
            width = advanced_parameters.overwrite_width

        if advanced_parameters.overwrite_height > 0:
            height = advanced_parameters.overwrite_height

        print(f'[Parameters] Sampler = {sampler_name} - {scheduler_name}')
        print(f'[Parameters] Steps = {steps} - {switch}')

        progressbar(1, 'Initializing ...')

        if not skip_prompt_processing:

            prompts = remove_empty_str([safe_str(p) for p in prompt.splitlines()], default='')
            negative_prompts = remove_empty_str([safe_str(p) for p in negative_prompt.splitlines()], default='')

            prompt = prompts[0]
            negative_prompt = negative_prompts[0]

            if prompt == '':
                # disable expansion when empty since it is not meaningful and influences image prompt
                use_expansion = False

            extra_positive_prompts = prompts[1:] if len(prompts) > 1 else []
            extra_negative_prompts = negative_prompts[1:] if len(negative_prompts) > 1 else []

            progressbar(3, 'Loading models ...')
            pipeline.refresh_everything(refiner_model_name=refiner_model_name, base_model_name=base_model_name, loras=loras)

            progressbar(3, 'Processing prompts ...')
            tasks = []
            for i in range(image_number):
                task_seed = (seed + i) % (constants.MAX_SEED + 1) # randint is inclusive, % is not
                task_rng = random.Random(task_seed)  # may bind to inpaint noise in the future

                task_prompt = apply_wildcards(prompt, task_rng)
                task_negative_prompt = apply_wildcards(negative_prompt, task_rng)
                task_extra_positive_prompts = [apply_wildcards(pmt, task_rng) for pmt in extra_positive_prompts]
                task_extra_negative_prompts = [apply_wildcards(pmt, task_rng) for pmt in extra_negative_prompts]

                positive_basic_workloads = []
                negative_basic_workloads = []

                if use_style:
                    for s in style_selections:
                        p, n = apply_style(s, positive=task_prompt)
                        positive_basic_workloads = positive_basic_workloads + p
                        negative_basic_workloads = negative_basic_workloads + n
                else:
                    positive_basic_workloads.append(task_prompt)

                negative_basic_workloads.append(task_negative_prompt)  # Always use independent workload for negative.

                positive_basic_workloads = positive_basic_workloads + task_extra_positive_prompts
                negative_basic_workloads = negative_basic_workloads + task_extra_negative_prompts

                positive_basic_workloads = remove_empty_str(positive_basic_workloads, default=task_prompt)
                negative_basic_workloads = remove_empty_str(negative_basic_workloads, default=task_negative_prompt)

                tasks.append(dict(
                    task_seed=task_seed,
                    task_prompt=task_prompt,
                    task_negative_prompt=task_negative_prompt,
                    positive=positive_basic_workloads,
                    negative=negative_basic_workloads,
                    expansion='',
                    c=None,
                    uc=None,
                    positive_top_k=len(positive_basic_workloads),
                    negative_top_k=len(negative_basic_workloads),
                    log_positive_prompt='\n'.join([task_prompt] + task_extra_positive_prompts),
                    log_negative_prompt='\n'.join([task_negative_prompt] + task_extra_negative_prompts),
                ))

            if use_expansion:
                for i, t in enumerate(tasks):
                    progressbar(5, f'Preparing Fooocus text #{i + 1} ...')
                    expansion = pipeline.final_expansion(t['task_prompt'], t['task_seed'])
                    print(f'[Prompt Expansion] New suffix: {expansion}')
                    t['expansion'] = expansion
                    t['positive'] = copy.deepcopy(t['positive']) + [join_prompts(t['task_prompt'], expansion)]  # Deep copy.

            for i, t in enumerate(tasks):
                progressbar(7, f'Encoding positive #{i + 1} ...')
                t['c'] = pipeline.clip_encode(texts=t['positive'], pool_top_k=t['positive_top_k'])

            for i, t in enumerate(tasks):
                progressbar(10, f'Encoding negative #{i + 1} ...')
                t['uc'] = pipeline.clip_encode(texts=t['negative'], pool_top_k=t['negative_top_k'])

        if len(goals) > 0:
            progressbar(13, 'Image processing ...')

        if 'vary' in goals:
            if 'subtle' in uov_method:
                denoising_strength = 0.5
            if 'strong' in uov_method:
                denoising_strength = 0.85
            if advanced_parameters.overwrite_vary_strength > 0:
                denoising_strength = advanced_parameters.overwrite_vary_strength

            shape_ceil = get_image_shape_ceil(uov_input_image)
            if shape_ceil < 1024:
                print(f'[Vary] Image is resized because it is too small.')
                shape_ceil = 1024
            elif shape_ceil > 2048:
                print(f'[Vary] Image is resized because it is too big.')
                shape_ceil = 2048

            uov_input_image = set_image_shape_ceil(uov_input_image, shape_ceil)

            initial_pixels = core.numpy_to_pytorch(uov_input_image)
            progressbar(13, 'VAE encoding ...')
            initial_latent = core.encode_vae(vae=pipeline.final_vae, pixels=initial_pixels)
            B, C, H, W = initial_latent['samples'].shape
            width = W * 8
            height = H * 8
            print(f'Final resolution is {str((height, width))}.')

        if 'upscale' in goals:
            H, W, C = uov_input_image.shape
            progressbar(13, f'Upscaling image from {str((H, W))} ...')

            uov_input_image = core.numpy_to_pytorch(uov_input_image)
            uov_input_image = perform_upscale(uov_input_image)
            uov_input_image = core.pytorch_to_numpy(uov_input_image)[0]
            print(f'Image upscaled.')

            if '1.5x' in uov_method:
                f = 1.5
            elif '2x' in uov_method:
                f = 2.0
            else:
                f = 1.0

            shape_ceil = get_shape_ceil(H * f, W * f)

            if shape_ceil < 1024:
                print(f'[Upscale] Image is resized because it is too small.')
                uov_input_image = set_image_shape_ceil(uov_input_image, 1024)
                shape_ceil = 1024
            else:
                uov_input_image = resample_image(uov_input_image, width=W * f, height=H * f)

            image_is_super_large = shape_ceil > 2800

            if 'fast' in uov_method:
                direct_return = True
            elif image_is_super_large:
                print('Image is too large. Directly returned the SR image. '
                      'Usually directly return SR image at 4K resolution '
                      'yields better results than SDXL diffusion.')
                direct_return = True
            else:
                direct_return = False

            if direct_return:
                d = [('Upscale (Fast)', '2x')]
                log(uov_input_image, d, single_line_number=1)
                yield_result(uov_input_image, do_not_show_finished_images=True)
                return

            tiled = True
            denoising_strength = 0.382

            if advanced_parameters.overwrite_upscale_strength > 0:
                denoising_strength = advanced_parameters.overwrite_upscale_strength

            initial_pixels = core.numpy_to_pytorch(uov_input_image)
            progressbar(13, 'VAE encoding ...')

            initial_latent = core.encode_vae(
                vae=pipeline.final_vae if pipeline.final_refiner_vae is None else pipeline.final_refiner_vae,
                pixels=initial_pixels, tiled=True)
            B, C, H, W = initial_latent['samples'].shape
            width = W * 8
            height = H * 8
            print(f'Final resolution is {str((height, width))}.')
            refiner_swap_method = 'upscale'

        if 'inpaint' in goals:
            if len(outpaint_selections) > 0:
                H, W, C = inpaint_image.shape
                if 'top' in outpaint_selections:
                    inpaint_image = np.pad(inpaint_image, [[int(H * 0.3), 0], [0, 0], [0, 0]], mode='edge')
                    inpaint_mask = np.pad(inpaint_mask, [[int(H * 0.3), 0], [0, 0]], mode='constant',
                                          constant_values=255)
                if 'bottom' in outpaint_selections:
                    inpaint_image = np.pad(inpaint_image, [[0, int(H * 0.3)], [0, 0], [0, 0]], mode='edge')
                    inpaint_mask = np.pad(inpaint_mask, [[0, int(H * 0.3)], [0, 0]], mode='constant',
                                          constant_values=255)

                H, W, C = inpaint_image.shape
                if 'left' in outpaint_selections:
                    inpaint_image = np.pad(inpaint_image, [[0, 0], [int(H * 0.3), 0], [0, 0]], mode='edge')
                    inpaint_mask = np.pad(inpaint_mask, [[0, 0], [int(H * 0.3), 0]], mode='constant',
                                          constant_values=255)
                if 'right' in outpaint_selections:
                    inpaint_image = np.pad(inpaint_image, [[0, 0], [0, int(H * 0.3)], [0, 0]], mode='edge')
                    inpaint_mask = np.pad(inpaint_mask, [[0, 0], [0, int(H * 0.3)]], mode='constant',
                                          constant_values=255)

                inpaint_image = np.ascontiguousarray(inpaint_image.copy())
                inpaint_mask = np.ascontiguousarray(inpaint_mask.copy())

            inpaint_worker.current_task = inpaint_worker.InpaintWorker(image=inpaint_image, mask=inpaint_mask,
                                                                       is_outpaint=len(outpaint_selections) > 0)

            pipeline.final_unet.model.diffusion_model.in_inpaint = True

            if advanced_parameters.debugging_cn_preprocessor:
                yield_result(inpaint_worker.current_task.visualize_mask_processing(), do_not_show_finished_images=True)
                return

            progressbar(13, 'VAE Inpaint encoding ...')

            inpaint_pixel_fill = core.numpy_to_pytorch(inpaint_worker.current_task.interested_fill)
            inpaint_pixel_image = core.numpy_to_pytorch(inpaint_worker.current_task.interested_image)
            inpaint_pixel_mask = core.numpy_to_pytorch(inpaint_worker.current_task.interested_mask)

            latent_inpaint, latent_mask = core.encode_vae_inpaint(
                mask=inpaint_pixel_mask,
                vae=pipeline.final_vae,
                pixels=inpaint_pixel_image)

            latent_swap = None
            if pipeline.final_refiner_vae is not None:
                progressbar(13, 'VAE Inpaint SD15 encoding ...')
                latent_swap = core.encode_vae(
                    vae=pipeline.final_refiner_vae,
                    pixels=inpaint_pixel_fill)['samples']

            progressbar(13, 'VAE encoding ...')
            latent_fill = core.encode_vae(
                vae=pipeline.final_vae,
                pixels=inpaint_pixel_fill)['samples']

            inpaint_worker.current_task.load_latent(latent_fill=latent_fill,
                                                    latent_inpaint=latent_inpaint,
                                                    latent_mask=latent_mask,
                                                    latent_swap=latent_swap,
                                                    inpaint_head_model_path=inpaint_head_model_path)

            B, C, H, W = latent_fill.shape
            height, width = H * 8, W * 8
            final_height, final_width = inpaint_worker.current_task.image.shape[:2]
            initial_latent = {'samples': latent_fill}
            print(f'Final resolution is {str((final_height, final_width))}, latent is {str((height, width))}.')

        if 'cn' in goals:
            for task in cn_tasks[flags.cn_canny]:
                cn_img, cn_stop, cn_weight = task
                cn_img = resize_image(HWC3(cn_img), width=width, height=height)
                cn_img = preprocessors.canny_pyramid(cn_img)
                cn_img = HWC3(cn_img)
                task[0] = core.numpy_to_pytorch(cn_img)
                if advanced_parameters.debugging_cn_preprocessor:
                    yield_result(cn_img, do_not_show_finished_images=True)
                    return
            for task in cn_tasks[flags.cn_cpds]:
                cn_img, cn_stop, cn_weight = task
                cn_img = resize_image(HWC3(cn_img), width=width, height=height)
                cn_img = preprocessors.cpds(cn_img)
                cn_img = HWC3(cn_img)
                task[0] = core.numpy_to_pytorch(cn_img)
                if advanced_parameters.debugging_cn_preprocessor:
                    yield_result(cn_img, do_not_show_finished_images=True)
                    return
            for task in cn_tasks[flags.cn_ip]:
                cn_img, cn_stop, cn_weight = task
                cn_img = HWC3(cn_img)

                # https://github.com/tencent-ailab/IP-Adapter/blob/d580c50a291566bbf9fc7ac0f760506607297e6d/README.md?plain=1#L75
                cn_img = resize_image(cn_img, width=224, height=224, resize_mode=0)

                task[0] = ip_adapter.preprocess(cn_img)
                if advanced_parameters.debugging_cn_preprocessor:
                    yield_result(cn_img, do_not_show_finished_images=True)
                    return

            if len(cn_tasks[flags.cn_ip]) > 0:
                pipeline.final_unet = ip_adapter.patch_model(pipeline.final_unet, cn_tasks[flags.cn_ip])

        if advanced_parameters.freeu_enabled:
            print(f'FreeU is enabled!')
            pipeline.final_unet = core.apply_freeu(
                pipeline.final_unet,
                advanced_parameters.freeu_b1,
                advanced_parameters.freeu_b2,
                advanced_parameters.freeu_s1,
                advanced_parameters.freeu_s2
            )

        all_steps = steps * image_number

        preparation_time = time.perf_counter() - execution_start_time
        print(f'Preparation time: {preparation_time:.2f} seconds')

        outputs.append(['preview', (13, 'Moving model to GPU ...', None)])

        def callback(step, x0, x, total_steps, y):
            done_steps = current_task_id * steps + step
            outputs.append(['preview', (
                int(15.0 + 85.0 * float(done_steps) / float(all_steps)),
                f'Step {step}/{total_steps} in the {current_task_id + 1}-th Sampling',
                y)])

        for current_task_id, task in enumerate(tasks):
            execution_start_time = time.perf_counter()

            try:
                positive_cond, negative_cond = task['c'], task['uc']

                if 'cn' in goals:
                    for cn_flag, cn_path in [
                        (flags.cn_canny, controlnet_canny_path),
                        (flags.cn_cpds, controlnet_cpds_path)
                    ]:
                        for cn_img, cn_stop, cn_weight in cn_tasks[cn_flag]:
                            positive_cond, negative_cond = core.apply_controlnet(
                                positive_cond, negative_cond,
                                pipeline.loaded_ControlNets[cn_path], cn_img, cn_weight, 0, cn_stop)

                imgs = pipeline.process_diffusion(
                    positive_cond=positive_cond,
                    negative_cond=negative_cond,
                    steps=steps,
                    switch=switch,
                    width=width,
                    height=height,
                    image_seed=task['task_seed'],
                    callback=callback,
                    sampler_name=sampler_name,
                    scheduler_name=scheduler_name,
                    latent=initial_latent,
                    denoise=denoising_strength,
                    tiled=tiled,
                    cfg_scale=cfg_scale,
                    refiner_swap_method=refiner_swap_method
                )

                del task['c'], task['uc'], positive_cond, negative_cond  # Save memory

                if inpaint_worker.current_task is not None:
                    imgs = [inpaint_worker.current_task.post_process(x) for x in imgs]

                for x in imgs:
                    d = [
                        ('Prompt', task['log_positive_prompt']),
                        ('Negative Prompt', task['log_negative_prompt']),
                        ('Fooocus V2 Expansion', task['expansion']),
                        ('Styles', str(raw_style_selections)),
                        ('Performance', performance_selection),
                        ('Resolution', str((width, height))),
                        ('Sharpness', sharpness),
                        ('Guidance Scale', guidance_scale),
                        ('ADM Guidance', str((modules.patch.positive_adm_scale, modules.patch.negative_adm_scale))),
                        ('Base Model', base_model_name),
                        ('Refiner Model', refiner_model_name),
                        ('Sampler', sampler_name),
                        ('Scheduler', scheduler_name),
                        ('Seed', task['task_seed'])
                    ]
                    for n, w in loras_raw:
                        if n != 'None':
                            d.append((f'LoRA [{n}] weight', w))
                    log(x, d, single_line_number=3)

                yield_result(imgs, do_not_show_finished_images=len(tasks) == 1)
            except fcbh.model_management.InterruptProcessingException as e:
                if shared.last_stop == 'skip':
                    print('User skipped')
                    continue
                else:
                    print('User stopped')
                    break

            execution_time = time.perf_counter() - execution_start_time
            print(f'Generating and saving time: {execution_time:.2f} seconds')

        pipeline.prepare_text_encoder(async_call=True)
        return

    while True:
        time.sleep(0.01)
        if len(buffer) > 0:
            task = buffer.pop(0)
            try:
                handler(task)
            except:
                traceback.print_exc()
            if len(buffer) == 0:
                outputs.append(['finish', global_results])
                global_results = []
    pass


threading.Thread(target=worker, daemon=True).start()
