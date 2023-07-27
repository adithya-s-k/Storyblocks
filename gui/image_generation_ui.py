import gradio as gr

def image_generation_ui(StoryBlocksUI: gr.Blocks):
    with gr.Tab("Generate Images") as image_generation_ui:
        gr.Markdown("## Generate Image")
        with gr.Row(visible=True):
            with gr.Column():
              checkpoints = gr.Radio(["", ""], label="Choose an image generator")
              button = gr.Button("Generate Images", size="sm", interactive=True, visible=True)
    return image_generation_ui