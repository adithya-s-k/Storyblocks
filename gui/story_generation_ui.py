import os
import json
import traceback
import gradio as gr
from storyblocks.config.languages import Language
import time
from storyblocks.config.api_db import get_api_key
from storyblocks.config.project_db import get_project_name, set_project_name
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage


language_choices = [lang.value.upper() for lang in Language]

ERROR_TEMPLATE = """
<div style='text-align: center; background: #9fcbc3; color: #3f4039; 
padding: 20px; border-radius: 5px; margin: 10px;'>
    <h2 style='margin: 0;'>ERROR | {error_message}</h2>
    <p style='margin: 10px 0;'>Traceback Info : {stack_trace}</p>
    <p style='margin: 10px 0;'>If the problem persists, don't hesitate to 
contact our support. We're here to assist you.</p>
    <a href='' target='_blank' 
style='background: #3f4039; color: #fff; border: none; padding: 10px 20px; 
border-radius: 5px; cursor: pointer; text-decoration: none;'>Get Help on Discord</a>
</div>"""


def generate_story(prompt, genre, number_of_words):
    embedHTML = '<div style="display: flex; overflow-x: auto; gap: 20px;">'
    try:
        # Multiply the duration by 150 to get the number of words. Average reading speed is 150 words per minute.
        number_of_words = int(number_of_words)
        #using langchain to generate the story
        chat = ChatOpenAI(temperature=0.9 , model="gpt-3.5-turbo-16k", client=any , openai_api_key=get_api_key("OPENAI"))

        # prompt template
        messages = [
            SystemMessage(
                content="In a world of boundless creativity, you are an AI storyteller who weaves intriguing tales with depth. Join us on a journey where words come alive, characters thrive, and stories leave an everlasting impact. Let's create something magical together.",
            ),
            HumanMessage(
                content=
                f""" Write a story with the following plot : {prompt}
                    with the following genre : {genre}
                    The story should be {number_of_words} words long.
                    Instead of pronouns, use the names of the characters.
                """,
            ),
        ]
        
        try:
            story = chat(messages).content
            lenght_of_ai_story = len(story.split(" "))
            words = story.split()  # Split the string into a list of words
            # Split the list into strings of six words each
            word_list = [' '.join(words[i:i+15]) for i in range(0, len(words), 15)]
        except Exception as e:
            raise gr.Error("Something went wrong while generating the story. Please try again later.") 
        
        
        print(f"AI story is {lenght_of_ai_story} words long")
        print(story)
        
        try:
            current_selected_project = get_project_name()
            if current_selected_project is None:
                raise gr.Error("Please select a project first")
            else:
                json_file_path = f"projects/{current_selected_project}/content.json"
                if os.path.exists(json_file_path):
                    with open(json_file_path, "r") as json_file:
                        existing_data = json.load(json_file)

                # Update the existing data with the new values
                existing_data["content"] = str(story)
                existing_data["word_lists"] = str(word_list)    
                with open(json_file_path, "w") as json_file:
                    json.dump(existing_data, json_file)
        
        except Exception as e:
            raise gr.Error("Please select a project first")

        # embedHTML = f'''
        # <div style="display: flex; flex-direction: column; align-items: center;">
        #     <h3>{story}</h3>
        #     <h4>Word Count : {len(story.split())}</h4>
        # </div>'''
        # yield embedHTML + '</div>', 
        return gr.update(value = story , visible=True)
        
    except Exception as e:
        raise gr.Error("Something went wrong while generating the story. Please try again later.")
        # traceback_str = ''.join(traceback.format_tb(e.__traceback__))
        # error_name = type(e).__name__.capitalize()+ " : " +f"{e.args[0]}"
        # print("Error", traceback_str)
        # yield embedHTML + '</div>', gr.Button.update(visible=True), gr.update(value=ERROR_TEMPLATE.format(error_message=error_name, stack_trace=traceback_str), visible=True)
    

def Toggel_ui(assistance_level):
    if assistance_level == "Use AI to Generate Story":
        return gr.update(visible=True), gr.update(visible=False) , gr.update(visible=False)
    elif assistance_level == "Type your Story":
        return gr.update(visible=False), gr.update(visible=True) , gr.update(visible=False)

def Set_story(story):
    embedHTML = '<div style="display: flex; overflow-x: auto; gap: 20px;">'
    try:
        try:    
            story = story
            words = story.split()  # Split the string into a list of words
            word_list = [' '.join(words[i:i+15]) for i in range(0, len(words), 15)]
        except Exception as e:
            raise gr.Error("Something went wrong while generating the story. Please try again later.") 

        try:
            current_selected_project = get_project_name()
            if current_selected_project is None:
                raise gr.Error("Please select a project first")
            else:
                json_file_path = f"projects/{current_selected_project}/content.json"
                if os.path.exists(json_file_path):
                    with open(json_file_path, "r") as json_file:
                        existing_data = json.load(json_file)

                # Update the existing data with the new values
                existing_data["content"] = str(story)
                existing_data["word_lists"] = str(word_list)    
                with open(json_file_path, "w") as json_file:
                    json.dump(existing_data, json_file)
        
        except Exception as e:
            raise gr.Error("Please select a project first")
        embedHTML = f'''
        <div style="display: flex; flex-direction: column; align-items: center;">
            <h3>{story}</h3>
            <h4>Word Count : {len(story.split())}</h4>
        </div>'''
        yield embedHTML + '</div>', 
    except Exception as e:
        traceback_str = ''.join(traceback.format_tb(e.__traceback__))
        error_name = type(e).__name__.capitalize()+ " : " +f"{e.args[0]}"
        print("Error", traceback_str)
        yield embedHTML + '</div>', gr.Button.update(visible=True), gr.update(value=ERROR_TEMPLATE.format(error_message=error_name, stack_trace=traceback_str), visible=True)
        
def get_story():
    try:
        current_selected_project = get_project_name()
        if current_selected_project is None:
            raise gr.Error("Please select a project first")
        else:
            json_file_path = f"projects/{current_selected_project}/content.json"
            if os.path.exists(json_file_path):
                with open(json_file_path, "r") as json_file:
                    existing_data = json.load(json_file)
                    story = existing_data["content"]
                    return story
            else:
                return ""
    except Exception as e:
        raise gr.Error("Please select a project first")


def story_generation_ui(StoryBlocksUI: gr.Blocks):
    with gr.Tab("Generate Story") as  story_generation:
        gr.Markdown("## Generate Story") 
        with gr.Row(visible=True):
            with gr.Column(visible=True):
                assistance = gr.Radio(["Use AI to Generate Story","Type your Story"], label="Type of story generated", interactive=True)
                with gr.Column(visible=False) as story_generation_column:
                    prompt = gr.Textbox(label="Prompt", lines=5, placeholder="Write a prompt for your story", interactive=True , visible=True)
                    genre = gr.Textbox(label="Genre", placeholder="Write a genre for your story", interactive=True, visible=True)
                    duration = gr.Slider(minimum=0, maximum=120, step=1, label="Duration in seconds", value=60, interactive=True, visible=True)
                    number_of_words = gr.Textbox(label="Number of words", placeholder=150, visible=True)
                    duration.change(lambda x: gr.update(value=float(x*150/60)), [duration], [number_of_words])
                    generate_story_button = gr.Button("Generate Story", size="sm", interactive=True, visible=True) 
                
                with gr.Column(visible=False) as edit_generation_column:
                    edit_story = gr.Textbox(label="Edit Story" ,lines=10, value="",interactive=True , visible=True)
                    set_edited_story_button = gr.Button("Set Story", size="sm", interactive=True, visible=True)
                
                with gr.Column(visible=False) as custom_story_column:    
                    story = gr.Textbox(label="Custom Story", lines=10, placeholder="Write your Custom Story", interactive=True , visible=True)
                    set_story_button = gr.Button("Set Story", size="sm", interactive=True, visible=True)
                
                generation_error = gr.HTML(visible=False)
                output = gr.HTML()

                assistance.change(Toggel_ui, inputs=[assistance], outputs=[story_generation_column, custom_story_column , edit_generation_column])
                generate_story_button.click(inspect_create_inputs, inputs=[prompt, genre, duration] , outputs=[generation_error]).success(lambda : gr.update(visible=True) , outputs=[edit_generation_column]).success(generate_story, inputs=[prompt, genre, duration] , outputs=[edit_story])
                set_edited_story_button.click(Set_story, inputs=[edit_story] , outputs=[output])
                set_story_button.click(Set_story, inputs=[story] , outputs=[output])
                
                # assistance.change(lambda x: (gr.update(visible= x == assistance.choices[0]), gr.update(visible= x == assistance.choices[1]), gr.update(visible= x == genre)), [assistance], [prompt, story, genre])

    return story_generation

def inspect_create_inputs(
    prompt,
    genre,
    duration,
    ):
    if not prompt:
        raise gr.Error("Please write down your story's prompt")
    if not genre:
        raise gr.Error("Please write down your story's genre")
    if not duration:
        raise gr.Error("Please write down your story's duration")
    openai_key = get_api_key("OPENAI")
    if not openai_key:
        raise gr.Error("OPENAI API key is missing. Please go to the config tab and enter the API key.")
    return gr.update(visible=False)