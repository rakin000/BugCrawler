from openai import OpenAI
import json
import os
from dotenv import load_dotenv

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
env_path = os.path.join(parent_dir, ".env")
if load_dotenv and os.path.exists(env_path):
    load_dotenv(env_path)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


def call_openai(prompt, api_key=OPENAI_API_KEY, model="gpt-4.1", temperature=0.001):
    """Call the OpenAI API with a given prompt and return text response.
    Uses the API key imported from the parent .env by default.
    """
    if not api_key:
        raise RuntimeError("No OpenAI API key found. Please add OPENAI_API_KEY to ../.env or pass api_key to call_openai")


    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature
    )
    return response.choices[0].message.content
