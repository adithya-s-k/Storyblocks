import gradio as gr

def video_generation_ui(StoryBlocksUI: gr.Blocks):
  with gr.Tab("Voice Generation") as voice_generation:
    gr.Markdown("## Generate Voice")
    with gr.Row(visible=True):
      with gr.Column():
        assistance = gr.Radio(["AI Generated Voice","Custom Voice"], label="Type of voice generated", value="AI Generated Voice", interactive=True)
        prompt = gr.Textbox(label="Prompt", lines=5, placeholder="Write a prompt for your voice", interactive=True , visible=True)
        voice = gr.Image(label="Custom Voice", lines=10, placeholder="Write your Custom Voice", interactive=True , visible=False)
        assistance.change(lambda x: (gr.update(visible= x == assistance.choices[0]), gr.update(visible= x == assistance.choices[1])), [assistance], [prompt, voice])
        genre = gr.Textbox(label="Genre", placeholder="Write a genre for your voice", interactive=True, visible=True)
        createButton = gr.Button(label="Generate Voice", size="sm", type="submit", interactive=True, visible=True)
  return voice_generation