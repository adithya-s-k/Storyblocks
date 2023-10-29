from fcbh import sd1_clip
import torch
import os

class SD2ClipModel(sd1_clip.SD1ClipModel):
    def __init__(self, arch="ViT-H-14", device="cpu", max_length=77, freeze=True, layer="penultimate", layer_idx=None, textmodel_path=None, dtype=None):
        if layer == "penultimate":
            layer="hidden"
            layer_idx=23

        textmodel_json_config = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sd2_clip_config.json")
        super().__init__(device=device, freeze=freeze, layer=layer, layer_idx=layer_idx, textmodel_json_config=textmodel_json_config, textmodel_path=textmodel_path, dtype=dtype)
        self.empty_tokens = [[49406] + [49407] + [0] * 75]

class SD2Tokenizer(sd1_clip.SD1Tokenizer):
    def __init__(self, tokenizer_path=None, embedding_directory=None):
        super().__init__(tokenizer_path, pad_with_end=False, embedding_directory=embedding_directory, embedding_size=1024)
