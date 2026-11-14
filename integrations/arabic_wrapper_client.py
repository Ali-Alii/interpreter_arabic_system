"""Example server-side adapter. Store HF_TOKEN in hosting Secrets, never client code."""
import os
from gradio_client import Client, handle_file


def evaluate(audio_path, reference_text='', mode='transcribe'):
    client = Client(os.getenv('SAWT_SPACE', 'Ali-Alii/sawt-arabic-gpu'),
                    hf_token=os.getenv('HF_TOKEN') or None)
    return client.predict(handle_file(audio_path), reference_text, mode, api_name='/evaluate')
