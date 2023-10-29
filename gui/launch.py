from python_hijack import *
import os
import sys
import platform


from build_launcher import build_launcher
from modules.launch_util import is_installed, run, python, run_pip, requirements_met
from modules.model_loader import load_file_from_url
from modules.path import modelfile_path, lorafile_path, vae_approx_path, fooocus_expansion_path, \
    checkpoint_downloads, embeddings_path, embeddings_downloads, lora_downloads


REINSTALL_ALL = False
TRY_INSTALL_XFORMERS = False


def prepare_environment():
    torch_index_url = os.environ.get('TORCH_INDEX_URL', "https://download.pytorch.org/whl/cu121")
    torch_command = os.environ.get('TORCH_COMMAND',
                                   f"pip install torch==2.1.0 torchvision==0.16.0 --extra-index-url {torch_index_url}")
    requirements_file = os.environ.get('REQS_FILE', "requirements_versions.txt")

    print(f"Python {sys.version}")

    if REINSTALL_ALL or not is_installed("torch") or not is_installed("torchvision"):
        run(f'"{python}" -m {torch_command}', "Installing torch and torchvision", "Couldn't install torch", live=True)

    if TRY_INSTALL_XFORMERS:
        if REINSTALL_ALL or not is_installed("xformers"):
            xformers_package = os.environ.get('XFORMERS_PACKAGE', 'xformers==0.0.20')
            if platform.system() == "Windows":
                if platform.python_version().startswith("3.10"):
                    run_pip(f"install -U -I --no-deps {xformers_package}", "xformers", live=True)
                else:
                    print("Installation of xformers is not supported in this version of Python.")
                    print(
                        "You can also check this and build manually: https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/Xformers#building-xformers-on-windows-by-duckness")
                    if not is_installed("xformers"):
                        exit(0)
            elif platform.system() == "Linux":
                run_pip(f"install -U -I --no-deps {xformers_package}", "xformers")

    if REINSTALL_ALL or not requirements_met(requirements_file):
        run_pip(f"install -r \"{requirements_file}\"", "requirements")

    return


vae_approx_filenames = [
    ('xlvaeapp.pth', 'https://huggingface.co/lllyasviel/misc/resolve/main/xlvaeapp.pth'),
    ('vaeapp_sd15.pth', 'https://huggingface.co/lllyasviel/misc/resolve/main/vaeapp_sd15.pt'),
    ('xl-to-v1_interposer-v3.1.safetensors',
     'https://huggingface.co/lllyasviel/misc/resolve/main/xl-to-v1_interposer-v3.1.safetensors')
]


def download_models():
    for file_name, url in checkpoint_downloads.items():
        load_file_from_url(url=url, model_dir=modelfile_path, file_name=file_name)
    for file_name, url in embeddings_downloads.items():
        load_file_from_url(url=url, model_dir=embeddings_path, file_name=file_name)
    for file_name, url in lora_downloads.items():
        load_file_from_url(url=url, model_dir=lorafile_path, file_name=file_name)
    for file_name, url in vae_approx_filenames:
        load_file_from_url(url=url, model_dir=vae_approx_path, file_name=file_name)

    load_file_from_url(
        url='https://huggingface.co/lllyasviel/misc/resolve/main/fooocus_expansion.bin',
        model_dir=fooocus_expansion_path,
        file_name='pytorch_model.bin'
    )

    return


def ini_cbh_args():
    from args_manager import args
    return args


prepare_environment()
build_launcher()
ini_cbh_args()
download_models()

from webui import *
