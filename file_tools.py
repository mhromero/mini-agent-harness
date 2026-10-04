def list_files(r=False):
    print("Listing files. Recursive:", r)

list_files_tool = {
  'type': 'function',
  'function': {
    'name': 'list_files',
    'description': 'List all files in the configured root',
    'parameters': {
        'type': 'object',
        'required': ['r'],
        'properties': {
        'r': {'type': 'boolean', 'description': 'Indicates whether to list files recursively in subdirectories'},
        },
    },
  },
}

def read_file(file_path):
    print(f"Reading file: {file_path}")

read_file_tool = {
  'type': 'function',
  'function': {
    'name': 'read_file',
    'description': 'Read the contents of a file. Encoding:UTF-8. Maximum file size: 65,536-byte. If the file is larger than 1MB, it will not be read.',
    'parameters': {
        'type': 'object',
        'required': ['file_path'],
        'properties': {
        'file_path': {'type': 'string', 'description': 'The path to the file to read, relative to the configured root'},
        },
    },
  },
}
