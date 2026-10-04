import os
import sys

from ollama import Client
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get('OLLAMA_API_KEY')
if api_key == "" or api_key is None:
    sys.exit("Error: OLLAMA_API_KEY is missing.")

client = Client(host='https://ollama.com', headers={'Authorization': 'Bearer ' + api_key})

messages = [
  {
    'role': 'user',
    'content': 'Why is the sky blue?',
  },
]

response = client.chat(model='gpt-oss:120b', messages=messages, stream=False)

# api request failure or successs
print(response)
print("---"*4)
print(response.message.content)
