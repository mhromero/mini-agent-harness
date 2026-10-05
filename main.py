import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import file_tools

from ollama import Client, ResponseError, chat
from dotenv import load_dotenv

from file_tools import read_file

USER = 'user'
ASSISTANT = 'assistant'
TOOL = 'tool'

STEP_LIMIT = 5
LOG_PATH = Path(__file__).with_name('harness.jsonl')


def log_event(event, turn_id, step, **details):
    record = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'turn_id': turn_id,
        'step': step,
        'event': event,
        **details,
    }
    with LOG_PATH.open('a', encoding='utf-8') as log:
        log.write(json.dumps(record) + '\n')


def call_model(turn_id, step):
    started = perf_counter()
    log_event('model_call_started', turn_id, step, history_items=len(messages))
    try:
        response = client.chat(model=model, messages=messages, stream=False, tools=available_tools.values())
    except (ResponseError, ConnectionError) as error:
        log_event('model_call_finished', turn_id, step, outcome='api_failure',
                  error_type=type(error).__name__, status_code=getattr(error, 'status_code', None),
                  duration_ms=round((perf_counter() - started) * 1000, 2))
        raise
    log_event('model_call_finished', turn_id, step, outcome='success',
              tool_request_count=len(response.message.tool_calls or []),
              duration_ms=round((perf_counter() - started) * 1000, 2))
    return response

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
    if user_request.lower() == '/reset':
        messages.clear()
        print('Conversation history cleared.')
        continue

    turn_id = uuid4().hex
    turn_started = perf_counter()
    turn_failed = False
    step_count = 1
    log_event('turn_started', turn_id, 0)
    m = create_message(user_request, role=USER)
    messages.append(m)

    try:
        response = call_model(turn_id, step_count)

        while response.message.tool_calls and step_count < STEP_LIMIT:
            messages.append(response.message)  # Add the tool call message to the conversation

            for request_index, tool in enumerate(response.message.tool_calls):
                safe_tool_name = tool.function.name if tool.function.name in available_functions else 'unknown'
                log_event('tool_requested', turn_id, step_count,
                          request_index=request_index, tool_name=safe_tool_name)
                if function_to_call := available_functions.get(tool.function.name):
                    print('Calling function:', tool.function.name)
                    print('Arguments:', tool.function.arguments)

                    # Validate the arguments against the tool's parameters
                    try:
                        argument_validator(tool.function.arguments, available_tools[tool.function.name]['function']['parameters'])
                    except ValueError as e:
                        print(f"Error validating arguments for function {tool.function.name}: {e}")
                        output = {'ok': False, 'error': str(e)}
                        log_event('tool_rejected', turn_id, step_count,
                                  request_index=request_index, tool_name=safe_tool_name,
                                  outcome='invalid_arguments')
                    else:
                        print("Arguments are valid.")
                        tool_started = perf_counter()
                        log_event('tool_started', turn_id, step_count,
                                  request_index=request_index, tool_name=safe_tool_name)
                        try:
                            output = function_to_call(root_dir=root_dir, **tool.function.arguments)
                        except Exception as error:
                            log_event('tool_finished', turn_id, step_count,
                                      request_index=request_index, tool_name=safe_tool_name,
                                      outcome='exception', error_type=type(error).__name__,
                                      duration_ms=round((perf_counter() - tool_started) * 1000, 2))
                            log_event('turn_finished', turn_id, step_count, outcome='unexpected_error',
                                      duration_ms=round((perf_counter() - turn_started) * 1000, 2))
                            raise
                        log_event('tool_finished', turn_id, step_count,
                                  request_index=request_index, tool_name=safe_tool_name,
                                  outcome='success' if output.get('ok') else 'tool_error',
                                  content_characters=len(output.get('content') or ''),
                                  entry_count=len(output.get('entries') or []),
                                  truncated=output.get('truncated', False),
                                  duration_ms=round((perf_counter() - tool_started) * 1000, 2))
                else:
                    print(f'Function {tool.function.name} not found')
                    output = 'Function not found'
                    log_event('tool_rejected', turn_id, step_count,
                              request_index=request_index, tool_name='unknown', outcome='unknown_tool')

                # Add each tool result as a separate message
                tool_response = create_message(json.dumps(output), role=TOOL, tool_name=tool.function.name)
                messages.append(tool_response)

            try:
                step_count += 1
                response = call_model(turn_id, step_count)
            except ResponseError as e:
                    turn_failed = True
                    print(f'API Error ({e.status_code}):', e.error)
                    log_event('turn_finished', turn_id, step_count, outcome='api_failure',
                              status_code=e.status_code,
                              duration_ms=round((perf_counter() - turn_started) * 1000, 2))
                    if e.status_code in (401, 403):
                        sys.exit('Authentication or access rejected. Check your key and account permissions.')
                    break
            except ConnectionError as e:
                    turn_failed = True
                    print('Connection Error:', str(e))  
                    log_event('turn_finished', turn_id, step_count, outcome='api_failure',
                              duration_ms=round((perf_counter() - turn_started) * 1000, 2))
                    break

        if turn_failed:
            turn_failed = False
            continue
        if step_count >= STEP_LIMIT and response.message.tool_calls:
            print(f"Step limit of {STEP_LIMIT} reached. Stopping further tool calls.")
            log_event('turn_finished', turn_id, step_count, outcome='budget_exhausted',
                      duration_ms=round((perf_counter() - turn_started) * 1000, 2))
            continue

        messages.append(response.message)  # Add the model's response to the conversation

        print(response.message.content)
        log_event('turn_finished', turn_id, step_count, outcome='completed',
                  duration_ms=round((perf_counter() - turn_started) * 1000, 2))

    except ResponseError as e:
        messages.pop()  # Remove the last user message if the request fails
        print(f'API Error ({e.status_code}):', e.error)
        log_event('turn_finished', turn_id, step_count, outcome='api_failure', status_code=e.status_code,
                  duration_ms=round((perf_counter() - turn_started) * 1000, 2))
        if e.status_code in (401, 403):
            sys.exit('Authentication or access rejected. Check your key and account permissions.')
    except ConnectionError as e:
        messages.pop()  # Remove the last user message if the request fails
        print('Connection Error:', str(e))           
        log_event('turn_finished', turn_id, step_count, outcome='api_failure',
                  duration_ms=round((perf_counter() - turn_started) * 1000, 2))

    
