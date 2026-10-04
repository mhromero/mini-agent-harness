import os
from pathlib import Path


MAX_ENTRIES = 100
MAX_FILE_BYTES = 65_536


def list_files(root_dir, r=False):
    entries = []
    try:
        root = Path(root_dir).resolve()
        pending = [root]
        while pending:
            directory = pending.pop()
            with os.scandir(directory) as children:
                for child in children:
                    if len(entries) == MAX_ENTRIES:
                        return {'ok': True, 'entries': entries, 'truncated': True, 'error': None}

                    path = Path(child.path)
                    if child.is_symlink():
                        entry_type = 'symlink'
                    elif child.is_dir(follow_symlinks=False):
                        entry_type = 'directory'
                        if r:
                            pending.append(path)
                    elif child.is_file(follow_symlinks=False):
                        entry_type = 'file'
                    else:
                        entry_type = 'other'

                    entries.append({'path': path.relative_to(root).as_posix(), 'type': entry_type})

        return {'ok': True, 'entries': entries, 'truncated': False, 'error': None}
    except OSError as error:
        return {'ok': False, 'entries': [], 'truncated': False, 'error': str(error)}

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

def read_file(file_path, root_dir):
    try:
        root = Path(root_dir).resolve()
        requested = Path(file_path)
        if requested.is_absolute():
            raise ValueError('File path must be relative to the configured root.')

        path = (root / requested).resolve()
        if not path.is_relative_to(root):
            raise ValueError('File path is outside the configured root.')
        if not path.is_file():
            raise ValueError('Path does not identify an existing regular file.')
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(f'File exceeds the {MAX_FILE_BYTES}-byte limit.')

        with path.open('rb') as source:
            data = source.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise ValueError(f'File exceeds the {MAX_FILE_BYTES}-byte limit.')
        if b'\x00' in data:
            raise ValueError('File contains null bytes; only UTF-8 text is supported.')
        content = data.decode('utf-8')
        return {'ok': True, 'content': content, 'truncated': False, 'error': None}
    except (OSError, ValueError) as error:
        return {'ok': False, 'content': None, 'truncated': False, 'error': str(error)}

read_file_tool = {
  'type': 'function',
  'function': {
    'name': 'read_file',
    'description': 'Read the contents of a file. Encoding:UTF-8. Maximum file size: 65,536-byte. If the file is larger, it will not be read.',
    'parameters': {
        'type': 'object',
        'required': ['file_path'],
        'properties': {
        'file_path': {'type': 'string', 'description': 'The path to the file to read, relative to the configured root'},
        },
    },
  },
}
