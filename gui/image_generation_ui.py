import gradio as gr

def image_generation_ui(StoryBlocksUI: gr.Blocks):
    with gr.Tab("Generate Images") as image_generation_ui:
        gr.Markdown("## Generate Image")
        with gr.Row(visible=True):
            with gr.Column():
                assistance = gr.Radio(["AI Generated Image","Custom Image"], label="Type of image generated", value="AI Generated Image", interactive=True)
                prompt = gr.Textbox(label="Prompt", lines=5, placeholder="Write a prompt for your image", interactive=True , visible=True)
                image = gr.Image(label="Custom Image", lines=10, placeholder="Write your Custom Image", interactive=True , visible=False)
                assistance.change(lambda x: (gr.update(visible= x == assistance.choices[0]), gr.update(visible= x == assistance.choices[1])), [assistance], [prompt, image])
                genre = gr.Textbox(label="Genre", placeholder="Write a genre for your image", interactive=True, visible=True)
                createButton = gr.Button(label="Generate Image", size="sm", type="submit", interactive=True, visible=True)
    return image_generation_ui