import os
import sys

from ollama import Client, ResponseError
from dotenv import load_dotenv

USER = 'user'
ASSISTANT = 'assistant'

load_dotenv()

api_key = os.environ.get('OLLAMA_API_KEY')
if api_key == "" or api_key is None:
    sys.exit("Error: OLLAMA_API_KEY is missing.")

model = os.environ.get('MODEL')
if model == "" or model is None:
    sys.exit("Error: MODEL is missing.")

client = Client(host='https://ollama.com', headers={'Authorization': 'Bearer ' + api_key})

messages = []

def create_message(content, role):
    m ={
        'role': role,
        'content': content,
    }
    return m

while True:

    user_request = input("Ask a question. Type 'exit' to quit: ")
    if user_request.lower() == 'exit':
        break

    m = create_message(user_request, role=USER)
    messages.append(m)

    try:
        response = client.chat(model=model, messages=messages, stream=False)

        chat_response = create_message(response.message.content, role=ASSISTANT)
        messages.append(chat_response)

        print(response.message.content)
    except ResponseError as e:
        messages.pop()  # Remove the last user message if the request fails
        print('Error:', e.error) 
    except ConnectionError as e:
        messages.pop()  # Remove the last user message if the request fails
        print('Connection Error:', str(e))           

    


