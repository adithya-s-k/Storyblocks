import gradio as gr

def create_complie_ui(StoryBlocksUI : gr.Blocks):
    with gr.Tab("Compile Video") as compile_ui:
        with gr.Column():
            with gr.Row():
              gr.Markdown("## Compile Video")
    return compile_ui