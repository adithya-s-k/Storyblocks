import os
import time
import gradio as gr
from storyblocks.config.api_db import get_api_key
from storyblocks.config.project_db import get_project_name, set_project_name

def Create_project(project_name, project_description):
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

def Select_project(project_name_input):
    if not project_name_input:
        raise gr.Error("Please select a project")    
    set_project_name(project_name_input)
    return f"{project_name_input}"

def Update_projects_list(name):
    new_project = os.listdir("projects")
    return gr.update(choices=new_project , value=name)

def get_current_project():
    if get_project_name() not in os.listdir("projects"):
        set_project_name("")
        return ""
    return get_project_name()

def select_project_ui(StoryBlocksUI: gr.Blocks):
    with gr.Tab("Manage Projects") as select_project:
        current_project = gr.Textbox(value=get_current_project(), label="Current Project", interactive=False, visible=True)
        with gr.Row(visible=True):
            with gr.Column():
                project_name = gr.Textbox(label="Project Name",placeholder="Project Name" ,interactive=True, visible=True)
                project_description = gr.Textbox(label="Project Description", placeholder="Write a description for your project", interactive=True, visible=True)
                create_project_button = gr.Button("Create Project", size="sm", interactive=True, visible=True )
            with gr.Column():
                existing_projects = os.listdir("projects")
                existing_projects_options = gr.Dropdown(existing_projects,label="Select Existing Project",)
                existing_projects_options.select(Select_project, inputs=existing_projects_options , outputs=current_project)
                create_project_button.click(Create_project, inputs=[project_name, project_description])
                create_project_button.click(Select_project, inputs=project_name , outputs=current_project)
                create_project_button.click(Update_projects_list, inputs=project_name , outputs=existing_projects_options)
    return select_project