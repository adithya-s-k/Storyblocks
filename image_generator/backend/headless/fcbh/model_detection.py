import fcbh.supported_models
import fcbh.supported_models_base

def count_blocks(state_dict_keys, prefix_string):
    count = 0
    while True:
        c = False
        for k in state_dict_keys:
            if k.startswith(prefix_string.format(count)):
                c = True
                break
        if c == False:
            break
        count += 1
    return count

def detect_unet_config(state_dict, key_prefix, dtype):
    state_dict_keys = list(state_dict.keys())

    unet_config = {
        "use_checkpoint": False,
        "image_size": 32,
        "out_channels": 4,
        "use_spatial_transformer": True,
        "legacy": False
    }

    y_input = '{}label_emb.0.0.weight'.format(key_prefix)
    if y_input in state_dict_keys:
        unet_config["num_classes"] = "sequential"
        unet_config["adm_in_channels"] = state_dict[y_input].shape[1]
    else:
        unet_config["adm_in_channels"] = None

    unet_config["dtype"] = dtype
    model_channels = state_dict['{}input_blocks.0.0.weight'.format(key_prefix)].shape[0]
    in_channels = state_dict['{}input_blocks.0.0.weight'.format(key_prefix)].shape[1]

    num_res_blocks = []
    channel_mult = []
    attention_resolutions = []
    transformer_depth = []
    context_dim = None
    use_linear_in_transformer = False


    current_res = 1
    count = 0

    last_res_blocks = 0
    last_transformer_depth = 0
    last_channel_mult = 0

    while True:
        prefix = '{}input_blocks.{}.'.format(key_prefix, count)
        block_keys = sorted(list(filter(lambda a: a.startswith(prefix), state_dict_keys)))
        if len(block_keys) == 0:
            break

        if "{}0.op.weight".format(prefix) in block_keys: #new layer
            if last_transformer_depth > 0:
                attention_resolutions.append(current_res)
            transformer_depth.append(last_transformer_depth)
            num_res_blocks.append(last_res_blocks)
            channel_mult.append(last_channel_mult)

            current_res *= 2
            last_res_blocks = 0
            last_transformer_depth = 0
            last_channel_mult = 0
        else:
            res_block_prefix = "{}0.in_layers.0.weight".format(prefix)
            if res_block_prefix in block_keys:
                last_res_blocks += 1
                last_channel_mult = state_dict["{}0.out_layers.3.weight".format(prefix)].shape[0] // model_channels

            transformer_prefix = prefix + "1.transformer_blocks."
            transformer_keys = sorted(list(filter(lambda a: a.startswith(transformer_prefix), state_dict_keys)))
            if len(transformer_keys) > 0:
                last_transformer_depth = count_blocks(state_dict_keys, transformer_prefix + '{}')
                if context_dim is None:
                    context_dim = state_dict['{}0.attn2.to_k.weight'.format(transformer_prefix)].shape[1]
                    use_linear_in_transformer = len(state_dict['{}1.proj_in.weight'.format(prefix)].shape) == 2

        count += 1

    if last_transformer_depth > 0:
        attention_resolutions.append(current_res)
    transformer_depth.append(last_transformer_depth)
    num_res_blocks.append(last_res_blocks)
    channel_mult.append(last_channel_mult)
    transformer_depth_middle = count_blocks(state_dict_keys, '{}middle_block.1.transformer_blocks.'.format(key_prefix) + '{}')

    if len(set(num_res_blocks)) == 1:
        num_res_blocks = num_res_blocks[0]

    if len(set(transformer_depth)) == 1:
        transformer_depth = transformer_depth[0]

    unet_config["in_channels"] = in_channels
    unet_config["model_channels"] = model_channels
    unet_config["num_res_blocks"] = num_res_blocks
    unet_config["attention_resolutions"] = attention_resolutions
    unet_config["transformer_depth"] = transformer_depth
    unet_config["channel_mult"] = channel_mult
    unet_config["transformer_depth_middle"] = transformer_depth_middle
    unet_config['use_linear_in_transformer'] = use_linear_in_transformer
    unet_config["context_dim"] = context_dim
    return unet_config

def model_config_from_unet_config(unet_config):
    for model_config in fcbh.supported_models.models:
        if model_config.matches(unet_config):
            return model_config(unet_config)

    print("no match", unet_config)
    return None

def model_config_from_unet(state_dict, unet_key_prefix, dtype, use_base_if_no_match=False):
    unet_config = detect_unet_config(state_dict, unet_key_prefix, dtype)
    model_config = model_config_from_unet_config(unet_config)
    if model_config is None and use_base_if_no_match:
        return fcbh.supported_models_base.BASE(unet_config)
    else:
        return model_config

def unet_config_from_diffusers_unet(state_dict, dtype):
    match = {}
    attention_resolutions = []

    attn_res = 1
    for i in range(5):
        k = "down_blocks.{}.attentions.1.transformer_blocks.0.attn2.to_k.weight".format(i)
        if k in state_dict:
            match["context_dim"] = state_dict[k].shape[1]
            attention_resolutions.append(attn_res)
        attn_res *= 2

    match["attention_resolutions"] = attention_resolutions

    match["model_channels"] = state_dict["conv_in.weight"].shape[0]
    match["in_channels"] = state_dict["conv_in.weight"].shape[1]
    match["adm_in_channels"] = None
    if "class_embedding.linear_1.weight" in state_dict:
        match["adm_in_channels"] = state_dict["class_embedding.linear_1.weight"].shape[1]
    elif "add_embedding.linear_1.weight" in state_dict:
        match["adm_in_channels"] = state_dict["add_embedding.linear_1.weight"].shape[1]

    SDXL = {'use_checkpoint': False, 'image_size': 32, 'out_channels': 4, 'use_spatial_transformer': True, 'legacy': False,
            'num_classes': 'sequential', 'adm_in_channels': 2816, 'dtype': dtype, 'in_channels': 4, 'model_channels': 320,
            'num_res_blocks': 2, 'attention_resolutions': [2, 4], 'transformer_depth': [0, 2, 10], 'channel_mult': [1, 2, 4],
            'transformer_depth_middle': 10, 'use_linear_in_transformer': True, 'context_dim': 2048, "num_head_channels": 64}

    SDXL_refiner = {'use_checkpoint': False, 'image_size': 32, 'out_channels': 4, 'use_spatial_transformer': True, 'legacy': False,
                    'num_classes': 'sequential', 'adm_in_channels': 2560, 'dtype': dtype, 'in_channels': 4, 'model_channels': 384,
                    'num_res_blocks': 2, 'attention_resolutions': [2, 4], 'transformer_depth': [0, 4, 4, 0], 'channel_mult': [1, 2, 4, 4],
                    'transformer_depth_middle': 4, 'use_linear_in_transformer': True, 'context_dim': 1280, "num_head_channels": 64}

    SD21 = {'use_checkpoint': False, 'image_size': 32, 'out_channels': 4, 'use_spatial_transformer': True, 'legacy': False,
            'adm_in_channels': None, 'dtype': dtype, 'in_channels': 4, 'model_channels': 320, 'num_res_blocks': 2,
            'attention_resolutions': [1, 2, 4], 'transformer_depth': [1, 1, 1, 0], 'channel_mult': [1, 2, 4, 4],
            'transformer_depth_middle': 1, 'use_linear_in_transformer': True, 'context_dim': 1024, "num_head_channels": 64}

    SD21_uncliph = {'use_checkpoint': False, 'image_size': 32, 'out_channels': 4, 'use_spatial_transformer': True, 'legacy': False,
                    'num_classes': 'sequential', 'adm_in_channels': 2048, 'dtype': dtype, 'in_channels': 4, 'model_channels': 320,
                    'num_res_blocks': 2, 'attention_resolutions': [1, 2, 4], 'transformer_depth': [1, 1, 1, 0], 'channel_mult': [1, 2, 4, 4],
                    'transformer_depth_middle': 1, 'use_linear_in_transformer': True, 'context_dim': 1024, "num_head_channels": 64}

    SD21_unclipl = {'use_checkpoint': False, 'image_size': 32, 'out_channels': 4, 'use_spatial_transformer': True, 'legacy': False,
                    'num_classes': 'sequential', 'adm_in_channels': 1536, 'dtype': dtype, 'in_channels': 4, 'model_channels': 320,
                    'num_res_blocks': 2, 'attention_resolutions': [1, 2, 4], 'transformer_depth': [1, 1, 1, 0], 'channel_mult': [1, 2, 4, 4],
                    'transformer_depth_middle': 1, 'use_linear_in_transformer': True, 'context_dim': 1024}

    SD15 = {'use_checkpoint': False, 'image_size': 32, 'out_channels': 4, 'use_spatial_transformer': True, 'legacy': False,
            'adm_in_channels': None, 'dtype': dtype, 'in_channels': 4, 'model_channels': 320, 'num_res_blocks': 2,
            'attention_resolutions': [1, 2, 4], 'transformer_depth': [1, 1, 1, 0], 'channel_mult': [1, 2, 4, 4],
            'transformer_depth_middle': 1, 'use_linear_in_transformer': False, 'context_dim': 768, "num_heads": 8}

    SDXL_mid_cnet = {'use_checkpoint': False, 'image_size': 32, 'out_channels': 4, 'use_spatial_transformer': True, 'legacy': False,
            'num_classes': 'sequential', 'adm_in_channels': 2816, 'dtype': dtype, 'in_channels': 4, 'model_channels': 320,
            'num_res_blocks': 2, 'attention_resolutions': [4], 'transformer_depth': [0, 0, 1], 'channel_mult': [1, 2, 4],
            'transformer_depth_middle': 1, 'use_linear_in_transformer': True, 'context_dim': 2048, "num_head_channels": 64}

    SDXL_small_cnet = {'use_checkpoint': False, 'image_size': 32, 'out_channels': 4, 'use_spatial_transformer': True, 'legacy': False,
            'num_classes': 'sequential', 'adm_in_channels': 2816, 'dtype': dtype, 'in_channels': 4, 'model_channels': 320,
            'num_res_blocks': 2, 'attention_resolutions': [], 'transformer_depth': [0, 0, 0], 'channel_mult': [1, 2, 4],
            'transformer_depth_middle': 0, 'use_linear_in_transformer': True, "num_head_channels": 64, 'context_dim': 1}

    SDXL_diffusers_inpaint = {'use_checkpoint': False, 'image_size': 32, 'out_channels': 4, 'use_spatial_transformer': True, 'legacy': False,
            'num_classes': 'sequential', 'adm_in_channels': 2816, 'dtype': dtype, 'in_channels': 9, 'model_channels': 320,
            'num_res_blocks': 2, 'attention_resolutions': [2, 4], 'transformer_depth': [0, 2, 10], 'channel_mult': [1, 2, 4],
            'transformer_depth_middle': 10, 'use_linear_in_transformer': True, 'context_dim': 2048, "num_head_channels": 64}

    supported_models = [SDXL, SDXL_refiner, SD21, SD15, SD21_uncliph, SD21_unclipl, SDXL_mid_cnet, SDXL_small_cnet, SDXL_diffusers_inpaint]

    for unet_config in supported_models:
        matches = True
        for k in match:
            if match[k] != unet_config[k]:
                matches = False
                break
        if matches:
            return unet_config
    return None

def model_config_from_diffusers_unet(state_dict, dtype):
    unet_config = unet_config_from_diffusers_unet(state_dict, dtype)
    if unet_config is not None:
        return model_config_from_unet_config(unet_config)
    return None
