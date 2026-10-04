import json
import os
import sys

import file_tools

from ollama import Client, ResponseError, chat
from dotenv import load_dotenv

from file_tools import read_file

USER = 'user'
ASSISTANT = 'assistant'
TOOL = 'tool'

STEP_LIMIT = 5

load_dotenv()

api_key = os.environ.get('OLLAMA_API_KEY')
if api_key == "" or api_key is None:
    sys.exit("Error: OLLAMA_API_KEY is missing.")

model = os.environ.get('MODEL')
if model == "" or model is None:
    sys.exit("Error: MODEL is missing.")

root_dir = os.environ.get('ROOT_DIR')
if root_dir == "" or root_dir is None:
    sys.exit("Error: ROOT_DIR is missing.")
if not os.path.isdir(root_dir):
    sys.exit(f"Error: ROOT_DIR '{root_dir}' is not a valid directory.")

client = Client(host='https://ollama.com', headers={'Authorization': 'Bearer ' + api_key})

messages = []

def create_message(content, role, tool_name=None):
    """
    Create a message dictionary with the specified content, role, and tool name.
    Use for crafted messages, not for messages from the model.
    """
    m ={
        'role': role,
        'content': content,
        'tool_name': tool_name
    }
    return m

def argument_validator(arguments, parameters):
    if not isinstance(arguments, dict):
        raise ValueError("Arguments must be an object.")

    properties = parameters.get("properties", {})
    missing = set(parameters.get("required", [])) - set(arguments)
    unexpected = set(arguments) - set(properties)

    if missing:
        raise ValueError(f"Missing arguments: {sorted(missing)}")
    if unexpected:
        raise ValueError(f"Unexpected arguments: {sorted(unexpected)}")

    python_types = {"boolean": bool, "string": str}
    for name, value in arguments.items():
        expected = python_types[properties[name]["type"]]
        if not isinstance(value, expected):
            raise ValueError(f"Argument {name} must be {expected.__name__}.")

    return True 

available_functions = {
  'list_files': file_tools.list_files,
  'read_file': file_tools.read_file,
}

available_tools = {
  'list_files': file_tools.list_files_tool,
  'read_file': file_tools.read_file_tool,
}

while True:

    user_request = input("Ask a question. Type 'exit' to quit: ")
    if user_request.lower() == 'exit':
        break

    m = create_message(user_request, role=USER)
    messages.append(m)

    try:
        response = client.chat(model=model, messages=messages, stream=False, tools=available_tools.values())

        step_count = 1

        while response.message.tool_calls and step_count < STEP_LIMIT:
            step_count += 1

            messages.append(response.message)  # Add the tool call message to the conversation

            for tool in response.message.tool_calls:
                if function_to_call := available_functions.get(tool.function.name):
                    print('Calling function:', tool.function.name)
                    print('Arguments:', tool.function.arguments)

                    # Validate the arguments against the tool's parameters
                    try:
                        argument_validator(tool.function.arguments, available_tools[tool.function.name]['function']['parameters'])
                    except ValueError as e:
                        print(f"Error validating arguments for function {tool.function.name}: {e}")
                        output = {'ok': False, 'error': str(e)}
                    else:
                        print("Arguments are valid.")
                        output = function_to_call(**tool.function.arguments)
                else:
                    print(f'Function {tool.function.name} not found')
                    output = 'Function not found'

                # Add each tool result as a separate message
                tool_response = create_message(json.dumps(output), role=TOOL, tool_name=tool.function.name)
                messages.append(tool_response)

            try:
                response = client.chat(model=model, messages=messages, stream=False, tools=available_tools.values())
            except ResponseError as e:
                    print('Error:', e.error) 
                    break
            except ConnectionError as e:
                    print('Connection Error:', str(e))  
                    break

        if step_count >= STEP_LIMIT and response.message.tool_calls:
            print(f"Step limit of {STEP_LIMIT} reached. Stopping further tool calls.")

        messages.append(response.message)  # Add the model's response to the conversation

        print(response.message.content)

    except ResponseError as e:
        messages.pop()  # Remove the last user message if the request fails
        print('Error:', e.error) 
    except ConnectionError as e:
        messages.pop()  # Remove the last user message if the request fails
        print('Connection Error:', str(e))           

    

