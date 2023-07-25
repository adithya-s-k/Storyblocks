
import gradio as gr

ERROR_TEMPLATE = """<div style='text-align: center; background: #f2dede; color: #a94442; padding: 20px; border-radius: 5px; margin: 10px;'>
    <h2 style='margin: 0;'>ERROR : {error_message}</h2>
    <p style='margin: 10px 0;'>Traceback Info : {stack_trace}</p>
    <p style='margin: 10px 0;'>If the problem persists, don't hesitate to contact our support. We're here to assist you.</p>
    <a href='https://discord.gg/qn2WJaRH' target='_blank' style='background: #a94442; color: #fff; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; text-decoration: none;'>Get Help on Discord</a>
</div>"""
from gui.story_generation_ui import create_short_automation_ui


def create_content_automation(StoryBlocksUI: gr.Blocks):
    with gr.Tab("Generate") as content_automation_ui:
        gr.Markdown("## Generate Story") 
        create_short_automation_ui(StoryBlocksUI)
    return content_automation_ui