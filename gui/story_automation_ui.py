import traceback
import gradio as gr
from storyblocks.config.api_db import get_api_key
from storyblocks.api_utils.eleven_api import getVoices
import time

import gradio as gr
import random
import os
import time

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

