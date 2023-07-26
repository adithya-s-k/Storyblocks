import gradio as gr

def select_project_ui(StoryBlocksUI: gr.Blocks):
  with gr.Tab("Create Project") as select_project:
    with gr.Row(visible=True):
      with gr.Column():
          project_name = gr.Textbox(label="Project Name", placeholder="Write a name for your project", interactive=True, visible=True)
          project_description = gr.Textbox(label="Project Description", placeholder="Write a description for your project", interactive=True, visible=True)
          create_project_button = gr.Button(label="Create Project", size="sm", type="submit", interactive=True, visible=True)
    return select_project