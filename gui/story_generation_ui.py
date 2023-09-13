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


def generate_story(prompt, genre, duration):
    number_of_words = duration * 150
    chat = ChatOpenAI(temperature=0.9 , model="gpt-3.5-turbo-16k", client=any , openai_api_key=get_api_key)

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
    story = chat(messages).content
    lenght_of_ai_story = len(story.split(" "))
    current_selected_project = get_project_name()
    with open(f"project/{current_selected_project}/story.txt", "w") as file:
        file.write(story)

    print(f"AI story is {lenght_of_ai_story} words long")
    print(story)

def story_generation_ui(StoryBlocksUI: gr.Blocks):
    with gr.Tab("Generate Story") as  story_generation:
        gr.Markdown("## Generate Story") 
        with gr.Row(visible=True):
            with gr.Column():
                assistance = gr.Radio(["AI Generated Story","Custom Story"], label="Type of story generated", value="AI Generated Story", interactive=True)
                prompt = gr.Textbox(label="Prompt", lines=5, placeholder="Write a prompt for your story", interactive=True , visible=True)
                # story = gr.Textbox(label="Custom Story", lines=10, placeholder="Write your Custom Story", interactive=True , visible=False)
                # assistance.change(lambda x: (gr.update(visible= x == assistance.choices[0]), gr.update(visible= x == assistance.choices[1])), [assistance], [prompt, story])
                genre = gr.Textbox(label="Genre", placeholder="Write a genre for your story", interactive=True, visible=True)
                duration = gr.Slider(minimum=0, maximum=2, step=.2, label="Duration in minutes", value=2, interactive=True, visible=True)
                # language = gr.Radio(language_choices, label="Language", value="ENGLISH")
                generate_story_button = gr.Button("Generate Story", size="sm", interactive=True, visible=True)
                
                generate_story_button.click(generate_story, inputs=[prompt, genre, duration])
                
    return story_generation