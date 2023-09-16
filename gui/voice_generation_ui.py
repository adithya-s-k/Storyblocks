import os
import json
import pyttsx3
import gradio as gr
from storyblocks.config.api_db import get_api_key
from storyblocks.api_utils.eleven_api import getVoices
from storyblocks.config.project_db import get_project_name, set_project_name
from elevenlabs import generate, set_api_key , save

def getElevenlabsVoices():
    api_key = get_api_key("ELEVEN LABS")
    voices = list(reversed(getVoices(api_key).keys()))
    return voices

voiceChoice = gr.Radio(getElevenlabsVoices(), label="Elevenlabs voice", value="Antoni", interactive=True)

def generateVoice_ElevenLabs(selected_voice):
  set_api_key(get_api_key("ELEVEN LABS"))

  current_selected_project = get_project_name()
  
  with open(f"projects/{current_selected_project}/content.json", "r") as f:
    content = json.load(f)
    story = content["content"]
    
  print(story)

  audio = generate(
    text=story,
    voice=selected_voice
  )
  
  audio_file_path = f"projects/{current_selected_project}/audio.mp3"
  save(audio, audio_file_path)
  
  return  gr.update(value=f"projects/{current_selected_project}/audio.mp3")

def generateVoice_PythonTTS():
  current_selected_project = get_project_name()
  
  with open(f"projects/{current_selected_project}/content.json", "r") as f:
    content = json.load(f)
    story = content["content"]
    
  print(story)
  engine = pyttsx3.init()
  
  engine.save_to_file(story, f"projects/{current_selected_project}/audio.mp3")
  engine.runAndWait()
  
  return  gr.update(value=f"projects/{current_selected_project}/audio.mp3")


def elevenLabsUI(StoryBlocksUI: gr.Blocks):
  with gr.Row(visible=False) as eleven_labs_ui:
    with gr.Column():
      gr.Markdown("## Elevenlabs Voice")
      voiceChoice.render()
      elevenlab_generate_button = gr.Button("Generate Voice", size="sm", interactive=True, visible=True)
      generated_audio = gr.Audio(label="Audio", interactive=True, visible=False)
      elevenlab_generate_button.click(lambda : gr.update(visible=True), outputs=[generated_audio]).success(generateVoice_ElevenLabs ,inputs=[voiceChoice] , outputs=[generated_audio])
  return eleven_labs_ui

def pythonTTSUI(StoryBlocksUI: gr.Blocks):
  with gr.Row(visible=False) as python_tts_ui:
    with gr.Column():
      gr.Markdown("## Python TTS")
      pyttsx3_generate_button = gr.Button("Generate Voice", size="sm", interactive=True, visible=True)
      generated_audio = gr.Audio(label="Audio", interactive=True, visible=False)
      pyttsx3_generate_button.click(lambda : gr.update(visible=True), outputs=[generated_audio]).success(generateVoice_PythonTTS , outputs=[generated_audio])
  return python_tts_ui
    

def voice_generation_ui(StoryBlocksUI: gr.Blocks):
  with gr.Tab("Voice Generation") as voice_generation:
    gr.Markdown("## Generate Voice")
    choice_TTS = gr.Radio([ 'Python TTS', 'ElevenLabs'], label="Choose an voice generator")
    eleven_labs_ui = elevenLabsUI(StoryBlocksUI) 
    python_tts_ui = pythonTTSUI(StoryBlocksUI)
    choice_TTS.change(lambda x: (gr.update(visible= x == choice_TTS.choices[1]), gr.update(visible= x == choice_TTS.choices[0])), [choice_TTS], [eleven_labs_ui, python_tts_ui]) # type: ignore
  return voice_generation