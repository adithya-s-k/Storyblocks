from setuptools import setup, find_packages
import codecs
import os

here = os.path.abspath(os.path.dirname(__file__))

with codecs.open(os.path.join(here, "README.md"), encoding="utf-8") as fh:
    long_description = "\n" + fh.read()

VERSION = '0.0.1'
DESCRIPTION = 'Automating visual narrative/Flash cards creation with AI'
LONG_DESCRIPTION = ''

# Setting up
setup(
    name="storyblocks",
    version=VERSION,
    author="Adithya S K",
    author_email="adithyaskolavi@gmail.com",
    description=DESCRIPTION,
    long_description_content_type="text/markdown",
    long_description=long_description,
    packages=find_packages(),
    install_requires=[
        'ffmpeg', 
        'python-dotenv', 
        'gradio',
        'openai', 
        'tiktoken',
        'tinydb',
        'tinymongo',
        'proglog',
        'yt-dlp',
        'torch', 
        'torchaudio',
        'protobuf==3.20.0',
        'langchain',
        'moviepy',
        'termcolor',
        'progress',
        'questionary',
    ],
    keywords=['python', 'video', 'content creation', 'AI', 'automation', 'editing', 'voiceover synthesis', 'video captions', 'asset sourcing', 'tinyDB'],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Operating System :: Unix",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
    ]
)