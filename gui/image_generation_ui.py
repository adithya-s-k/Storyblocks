import gradio as gr


def Automatic1111API(StoryBlocksUI: gr.Blocks):
    with gr.Row(visible=False) as automatic1111_api:
        with gr.Column():
            gr.Markdown("## Automatic1111 API")
    return automatic1111_api

def SDXLLocal(StoryBlocksUI: gr.Blocks):
    with gr.Row(visible=False) as sdxl_local:
        with gr.Column():
            gr.Markdown("## SDXL Local")
            gr.Markdown("### Coming Soon")
    return sdxl_local

def StabilityAIAPI(StoryBlocksUI: gr.Blocks):
    with gr.Row(visible=False) as stability_ai_api:
        with gr.Column():
            gr.Markdown("## Stability AI API")
            gr.Markdown("### Coming Soon")
    return stability_ai_api

def image_generation_ui(StoryBlocksUI: gr.Blocks):
    with gr.Tab("Generate Images") as image_generation_ui:
        gr.Markdown("## Generate Image")
        image_generator_option = gr.Radio(["Automatic1111 API", "SDXL Local" , "Stability AI API"], label="Choose an image generator")
        
        automatic1111_api = Automatic1111API(StoryBlocksUI)
        sdxl_local = SDXLLocal(StoryBlocksUI)
        stability_ai_api = StabilityAIAPI(StoryBlocksUI)
        
        generate_image_button = gr.Button("Generate Images", size="sm", interactive=True, visible=True)
        image_generator_option.change(lambda x: (gr.update(visible= x == image_generator_option.choices[0]), gr.update(visible= x == image_generator_option.choices[1]), gr.update(visible= x == image_generator_option.choices[2])), [image_generator_option], [automatic1111_api , sdxl_local ,stability_ai_api ]) # type: ignore
        
    return image_generation_ui


