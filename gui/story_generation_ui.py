import traceback
import gradio as gr
from storyblocks.config.api_db import get_api_key
from storyblocks.api_utils.eleven_api import getVoices
from storyblocks.config.languages import Language
import time

import gradio as gr
import random
import os
import time

language_choices = [lang.value.upper() for lang in Language]

ERROR_TEMPLATE = """
<div style='text-align: center; background: #9fcbc3; color: #3f4039; 
padding: 20px; border-radius: 5px; margin: 10px;'>
    <h2 style='margin: 0;'>ERROR | {error_message}</h2>
    <p style='margin: 10px 0;'>Traceback Info : {stack_trace}</p>
    <p style='margin: 10px 0;'>If the problem persists, don't hesitate to 
contact our support. We're here to assist you.</p>
    <a href='' target='_blank' 
style='background: #3f4039; color: #fff; border: none; padding: 10px 20px; 
border-radius: 5px; cursor: pointer; text-decoration: none;'>Get Help on Discord</a>
</div>"""

def getElevenlabsVoices():
    api_key = get_api_key("ELEVEN LABS")
    voices = list(reversed(getVoices(api_key).keys()))
    return voices

voiceChoice = gr.Radio(getElevenlabsVoices(), label="Elevenlabs voice", value="Antoni", interactive=True)

def create_short_automation_ui(StoryBlocksUI: gr.Blocks):
    with gr.Row(visible=True) as story_generation:
        with gr.Column():
            assistance = gr.Radio(["AI Generated Story","Custom Story"], label="Type of story generated", value="AI Generated Story", interactive=True)
            prompt = gr.Textbox(label="Prompt", lines=5, placeholder="Write a prompt for your story", interactive=True , visible=True)
            story = gr.Textbox(label="Custom Story", lines=10, placeholder="Write your Custom Story", interactive=True , visible=False)
            assistance.change(lambda x: (gr.update(visible= x == assistance.choices[0]), gr.update(visible= x == assistance.choices[1])), [assistance], [prompt, story])
            genre = gr.Textbox(label="Genre", placeholder="Write a genre for your story", interactive=True, visible=True)
            duration = gr.Slider(minimum=0, maximum=2, step=.2, label="Duration in minutes", value=2, interactive=True, visible=True)
            language = gr.Radio(language_choices, label="Language", value="ENGLISH")
            createButton = gr.Button(label="Generate Story", size="sm", type="submit", interactive=True, visible=True)
    return story_generation