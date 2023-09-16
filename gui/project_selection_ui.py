# Import necessary libraries
import os
import shutil
import time
import gradio as gr
from storyblocks.config.api_db import get_api_key
from storyblocks.config.project_db import get_project_name, set_project_name

# Define some Unicode symbols for UI elements
folder_symbol = '\U0001f4c2'  # 📂
refresh_symbol = '\U0001f504'  # 🔄
delete_bin_symbol = '\U0001f5d1\ufe0f'  # 🗑️

# Function to create a new project
def Create_project(project_name, project_description):
    if not project_name:
        raise gr.Error("Please write down your project's name")
    elif not project_description:
        raise gr.Error("Please write down your project's description")
    else:
        # Create project directory structure
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

# Function to select a project
def Select_project(project_name_input):
    if not project_name_input:
        raise gr.Error("Please select a project")
    set_project_name(project_name_input)
    return f"{project_name_input}"

# Function to update the list of projects
def Update_projects_list(name):
    new_project = os.listdir("projects")
    return gr.update(choices=new_project, value=name), gr.update(choices=new_project) , gr.update(value=name)

# Function to get the current project
def get_current_project():
    if get_project_name() not in os.listdir("projects"):
        set_project_name("")
        return ""
    return get_project_name()

# Function to delete a project
def Delete_project(project_name):
    if not project_name:
        raise gr.Error("Please select a project to delete")
    elif project_name == "":
        raise gr.Error("Please select a project to delete")
    else:
        # Remove the project directory and associated files
        shutil.rmtree(f"projects/{project_name}")
        if project_name == get_project_name():
            set_project_name("")
            return gr.update(choices=os.listdir("projects"), value=""), gr.update(choices=os.listdir("projects"), value=""), gr.update(value="")
        return gr.update(choices=os.listdir("projects"), value=get_project_name()), gr.update(choices=os.listdir("projects")), gr.update(value="")

# Function to create the project management UI
def select_project_ui(StoryBlocksUI: gr.Blocks):
    with gr.Tab("Manage Projects") as select_project:
        # Create a Textbox to display the current selected project
        current_project = gr.Textbox(value=get_current_project(), label="Current Project", interactive=False, visible=True)
        
        with gr.Row(visible=True):
            with gr.Column():
                # Textbox for entering a new project name
                project_name = gr.Textbox(label="Project Name", placeholder="Project Name", interactive=True, visible=True)
                # Textbox for entering a project description
                project_description = gr.Textbox(label="Project Description", placeholder="Write a description for your project", interactive=True, visible=True)
                # Button to create a new project
                create_project_button = gr.Button(f"{folder_symbol} Create Project", interactive=True, visible=True , size="lg" )
            with gr.Column():
                # Get a list of existing projects
                existing_projects = os.listdir("projects")
                # Dropdown to select an existing project
                existing_projects_options = gr.Dropdown(existing_projects, label="Select Existing Project",)
                # Function to handle selecting an existing project
                existing_projects_options.select(Select_project, inputs=existing_projects_options, outputs=current_project)
                
                # Dropdown to select a project to delete
                delete_projects_options = gr.Dropdown(existing_projects, label="Select Project to Delete",)
                
                with gr.Row():
                    # Button to delete a project
                    delete_project_button = gr.Button(f"{delete_bin_symbol} Delete", size="lg", interactive=True, visible=True)
                    # Button to refresh the list of projects
                    refresh_project_button = gr.Button(f"{refresh_symbol} Refresh", size="lg", interactive=True, visible=True)
                
                # Function to handle deleting a project
                delete_project_button.click(Delete_project, inputs=delete_projects_options, outputs=[existing_projects_options, delete_projects_options, current_project])
                
                # Function to update the list of projects after a project is created
                refresh_project_button.click(Update_projects_list, inputs=current_project, outputs=[existing_projects_options, delete_projects_options , current_project])
                
                # Function to create a new project and update the UI
                create_project_button.click(Create_project, inputs=[project_name, project_description])
                create_project_button.click(Select_project, inputs=project_name, outputs=current_project)
                create_project_button.click(Update_projects_list, inputs=project_name, outputs=[existing_projects_options, delete_projects_options])

    return select_project