import getpass
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
import os
import datetime
from PIL import Image
from PIL import Image, ImageFont, ImageDraw
from diffusechain import Automatic1111
from rich import print
from langchain.output_parsers import GuardrailsOutputParser
from langchain.prompts import PromptTemplate
from langchain.llms import OpenAI
from elevenlabs import generate, play, set_api_key, save
import pyttsx3
from moviepy.editor import ImageClip, concatenate_videoclips
from moviepy.audio.io.AudioFileClip import AudioFileClip



useElevenLabs = True
ELEVENLABS_API = ""


automatic1111URL = input("Enter the URL of the automatic1111 URL: ")
try:
    api = Automatic1111(baseurl=f"{automatic1111URL}",
                    sampler= "Euler a",
                    steps= 25
                    )
    test_generation = api.txt2img(prompt="hello world",
                    seed=-1,
                    steps=30
                    )
except:
    print("Enter valid url: " + automatic1111URL)
    exit()
    
project = input("Enter the name of the project: ")
project = project.replace(" ", "_")
if project == "":
    print("Enter a valid project name")
    exit()
if os.path.exists(project):
    print("project already exists, content will be overwrite")
    os.chdir(project)
    os.mkdir("images")
else:    
    os.mkdir(project)
    os.chdir(project)
    os.mkdir("images")

OPENAI_API_KEY = getpass.getpass("OPEN AI API KEY: ")
elevenLabsCheck = input("Do you have an Eleven Labs API key? (y/n): ")
if elevenLabsCheck == "y":
    useElevenLabs = True
    ELEVENLABS_API = getpass.getpass("ELEVEN LABS API KEY: ")
else:
    useElevenLabsCheck = False
    
subtitles_check = input("Do you want sutitles in the video? (y/n): ")
    
inputAIassist = input("Do you want to use AI assist? (y/n): ")
if inputAIassist == "y":
    inputPlot = input("Enter the plot of the story.max 10 words")
    duraction = input("Enter the duraction of the story in minutes: 0.5 , 1 ,2")
    print("The story should be " + str(float(duraction) * 150) + " words long")
    number_of_words = float(duraction) * 150
    genre = input("Enter the genre of the story: horror, comedy, romance, sci-fi, fantasy, action, thriller, drama, mystery, crime, animation, adventure, family, war, history, western, music, documentary, sport, musical, film-noir, news, reality-tv, talk-show, game-show, adult, short, biography")
    chat = ChatOpenAI(temperature=0.9 , model="gpt-3.5-turbo-16k", client=any , openai_api_key=OPENAI_API_KEY)

    messages = [
        SystemMessage(
            content="In a world of boundless creativity, you are an AI storyteller who weaves intriguing tales with depth. Join us on a journey where words come alive, characters thrive, and stories leave an everlasting impact. Let's create something magical together.",
        ),
        HumanMessage(
            content=
            f""" Write a story with the following plot : {inputPlot}
                with the following genre : {genre}
                The story should be {number_of_words} words long.
                Instead of pronouns, use the names of the characters.
            """,
        ),
    ]
    story = chat(messages).content
    lenght_of_ai_story = len(story.split(" "))
    with open("story.txt", "w") as file:
        file.write(story)

    print(f"AI story is {lenght_of_ai_story} words long")
    
else:
    story = input("Enter the story: ")
    
def convert_to_list(string):
    words = string.split()  # Split the string into a list of words
    result = [' '.join(words[i:i+15]) for i in range(0, len(words), 15)]  # Split the list into strings of six words each
    return result
# Example usage
word_lists = convert_to_list(story)
print(word_lists)
    

character_rail = """
<rail version="0.1">

<output>
    <list name="characters" description="Generate a list of characters">
        <object>
            <string name="character_name" description="The characters name"/>
            <string name="character_description" description="character description in words"/>
            <string name="character_prompts" description="describe how the character looks physically in words the word should be a physical trait" format="word-list:1"/>
        </object>
    </list>
</output>


<prompt>

given the following story, please extract a list of characters and generate their description

{{story}}

@complete_json_suffix_v2
</prompt>
</rail>
"""

output_parser = GuardrailsOutputParser.from_rail_string(character_rail)

prompt = PromptTemplate(
    template=output_parser.guard.base_prompt,
    input_variables=output_parser.guard.prompt.variable_names,
)

model = OpenAI(temperature=0.9 , openai_api_key=OPENAI_API_KEY) # type: ignore

characters = model(prompt.format_prompt(story=story).to_string())
characters = output_parser.parse(characters)
print(characters)

chat = ChatOpenAI(temperature=0.9 , model="gpt-3.5-turbo-16k", client=any , openai_api_key=OPENAI_API_KEY)

image_description_list = []
start_time = datetime.datetime.now()
filename = start_time.strftime("%Y%m%d%H%M%S") + ".txt"
with open(filename, "w") as file:
  for index, phrase in enumerate(word_lists):
    messages = [
        SystemMessage(
            content="You are an AI which is straight to the point and tell out 4 to 5 word description of the image.",
        ),
        HumanMessage(
            content=
            f"""section: {phrase}
                and here are the characters: {characters}
                
                Here is what you have to do
                -dont use names only use descriptions of the characters and physical traits Never use names of the characters because the image generator will not understand them
                -remeber the action thats happening in the image is really important so emphasis on the action a lot and less on the character description
                -give most importance to that section of that story and generate description only and only based on that section
                -you should generate a 10 word description of the image which the image generator will understand
                -dont mention he , him , her ,they and any other pronouns the image generator will not understand them
                -dont use names at all
                
                here are some examples
                section:Leo guided Sammy through the wilderness, sharing his wisdom and protecting him from danger. As gratitude
                character: Sammy : squirrel , Leo : Lion
                output description: Lion guided squirrel through the wilderness, sharing Lion's wisdom and protecting squirrel from danger. As gratitude
                
                always return a  word description of the image
            """,
        ),
    ]
    image_description = chat(messages).content
    image_description_list.append(str(image_description))
    progress = (index + 1) / len(word_lists) * 100
    print(f"Progress for image generation prompts: {progress:.2f}%")

if useElevenLabs:
    set_api_key(ELEVENLABS_API)
    audio = generate(
    text=f"{story}",
    voice="Bella",
    model="eleven_monolingual_v1"
    )
    # play(audio)
    save(audio,'audio.mp3') # type: ignore
else:
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[1].id)
    engine.save_to_file(f"{story}" , f'audio_{1}.mp3')
    engine.runAndWait()
    

def add_text_to_image(image_path, text):
    # Open the image
    image = Image.open(image_path)

    # Calculate the font size based on the image size
    width, height = image.size
    font_size = int(height * 0.06)  # Adjust this multiplier to control the font size

    # Load the font
    font = ImageFont.truetype('arial.ttf', font_size)

    # Estimate the text size by getting the bounding box
    text_bbox = font.getbbox(text)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    # Adjust the font size if the text is wider than the image
    while text_width > width:
        font_size -= 1
        font = ImageFont.truetype('arial.ttf', font_size)
        text_bbox = font.getbbox(text)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

    # Calculate the position of the text at the bottom center of the image
    text_x = (width - text_width) // 2
    text_y = height - text_height - int(height * 0.05)  # Adjust this multiplier to control the vertical position

    # Create a translucent background for the text
    background_color = (0, 0, 0, 128)  # RGBA value with alpha transparency
    text_background = Image.new('RGBA', (text_width, text_height), background_color)

    # Draw the text on the background
    draw = ImageDraw.Draw(text_background)
    draw.text((0, 0), text, font=font, fill=(255, 255, 255))

    # Paste the text background onto the image
    image.paste(text_background, (text_x, text_y), mask=text_background)

    # Save the resulting image
    image.save(image_path)
    
seed = -1

for index, image_generation_dict in enumerate(image_description_list):
    print(image_generation_dict)
    positive_prompts = ",(((text))),((color)),(shading),background,noise,dithering,gradient,detailed,out of frame,ugly,error,Illustration, watermark,(((vector graphic))),medium detail, oil painting from studio ghibli film, by noriyuki morimoto, digital artist, bright and bold colors, expansive sky, sense of adventure, epic scope studio ghibli"
    negative_prompts = "(((text))),((color)),(shading),background,noise,dithering,gradient,detailed,out of frame,ugly,error,Illustration, watermark, Blurry, ugly, tiling, poorly drawn hands, poorly drawn feet, poorly drawn face, out of frame, extra limbs, disfigured, deformed, body out of frame, bad anatomy, watermark, signature, cut off, Low quality, Bad quality, Long neck"
    
    result = api.txt2img(prompt=f"{image_generation_dict}{positive_prompts}",
                    negative_prompt=f"{negative_prompts}",
                    width=512,
                    height=512,
                    sampler_index="DPM++ 2M SDE Karras",
                    sampler_name="DPM++ 2M SDE Karras",
                    save_images=True,
                    seed=-1,
                    steps=30
                    )
    
    seed = result.info["seed"] # type: ignore
    result.image.save(f"images/image_{index}.png") # type: ignore
    if subtitles_check == "y":
        add_text_to_image(f"images/image_{index}.png", f'{word_lists[index]}')
    
def create_video(image_dir, audio_file, subtitle_list, output_file):
    # Load the sequence of images
    image_files = sorted(os.listdir(image_dir))

    # Calculate the duration for each image based on the audio duration
    audio = AudioFileClip(audio_file)
    duration_per_image = audio.duration / len(image_files)

    clips = []
    for i, img in enumerate(image_files):
        # Create an ImageClip for each image with the specified duration
        image_path = os.path.join(image_dir, img)
        image = ImageClip(image_path, duration=duration_per_image)

        clips.append(image)

    # Concatenate the clips to create the final video
    final_clip = concatenate_videoclips(clips)

    # Set the audio for the final clip
    final_clip = final_clip.set_audio(audio)

    # Set the frame rate for the final clip
    final_clip.fps = 24

    # Write the video file
    final_clip.write_videofile(output_file, codec='libx264', audio_codec='aac', fps=24)

# Provide the image directory, audio file, and output file path
# only give the
project_dir = '.'
image_directory = f'{project_dir}/images'
audio_file = f'{project_dir}/audio.mp3'
output_file = f'{project_dir}/output_video_1.mp4'
subtitle = word_lists


# Call the create_video function
create_video(image_directory, audio_file, subtitle, output_file)