import gradio as gr
from storyblocks.config.api_db import get_api_key
from storyblocks.api_utils.eleven_api import getVoices

def getElevenlabsVoices():
    api_key = get_api_key("ELEVEN LABS")
    voices = list(reversed(getVoices(api_key).keys()))
    return voices

voiceChoice = gr.Radio(getElevenlabsVoices(), label="Elevenlabs voice", value="Antoni", interactive=True)

def elevenLabsUI(StoryBlocksUI: gr.Blocks):
  with gr.Row(visible=False) as eleven_labs_ui:
    with gr.Column():
      gr.Markdown("## Elevenlabs Voice")
      voiceChoice.render()
      button = gr.Button("Generate Voice", size="sm", interactive=True, visible=True)
  return eleven_labs_ui

def pythonTTSUI(StoryBlocksUI: gr.Blocks):
  with gr.Row(visible=False) as python_tts_ui:
    gr.Markdown("## Python TTS")
    button = gr.Button("Generate Voice", size="sm", interactive=True, visible=True)
  return python_tts_ui
    

def voice_generation_ui(StoryBlocksUI: gr.Blocks):
  with gr.Tab("Voice Generation") as voice_generation:
    gr.Markdown("## Generate Voice")
    choice_TTS = gr.Radio([ 'Python TTS', 'ElevenLabs'], label="Choose an voice generator")
    eleven_labs_ui = elevenLabsUI(StoryBlocksUI) 
    python_tts_ui = pythonTTSUI(StoryBlocksUI)
    choice_TTS.change(lambda x: (gr.update(visible= x == choice_TTS.choices[1]), gr.update(visible= x == choice_TTS.choices[0])), [choice_TTS], [eleven_labs_ui, python_tts_ui]) # type: ignore
  return voice_generation