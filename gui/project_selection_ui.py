import os
import gradio as gr
from storyblocks.config.api_db import get_api_key
from storyblocks.config.project_db import get_project_name, set_project_name

def create_project(project_name, project_description):
    if not project_name:
        raise gr.Error("Please write down your project's name")
    elif not project_description:
        raise gr.Error("Please write down your project's description")
    else:
        if not os.path.exists("projects"):
            os.mkdir("projects")
        if os.path.exists(f"projects/{project_name}"):
            raise gr.Error("Project already exists")
        else:
            os.mkdir(f"projects/{project_name}")
            os.mkdir(f"projects/{project_name}/images")
            with open(f"projects/{project_name}/content.json", "w") as f:
                f.write(f"""{{ "name": "{project_name}", "description": "{project_description}" }}""")
            set_project_name(project_name)
    return gr.update(visible=True)


def select_project_ui(StoryBlocksUI: gr.Blocks):
    with gr.Tab("Create Project") as select_project:
        with gr.Row(visible=True):
            with gr.Column():
                project_name = gr.Textbox(label="Project Name", placeholder="Write a name for your project", interactive=True, visible=True)
                project_description = gr.Textbox(label="Project Description", placeholder="Write a description for your project", interactive=True, visible=True)
                # create_project_button = gr.Button(label="Create Project", size="sm", type="submit", interactive=True, visible=True)
                with gr.Row():
                    button_project = gr.Button("Create Project", size="sm", interactive=True, visible=True ,)

        with gr.Column():
            
            gr.Markdown("## Previous Projects")
            list_of_projects = os.listdir("projects")
            with gr.Row():
                for i in range(len(list_of_projects)):
                    gr.Button(list_of_projects[i], size="sm" , interactive=True, visible=True)

            
        generation_error = gr.HTML(visible=False)
        button_project.click(create_project , inputs=[project_name, project_description])

    return select_project