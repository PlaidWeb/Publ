# template.py
# Wrapper for template information

import os
import arrow

class Template:
    def __init__(self, name, filename, file_path):
        self.name = name
        self.filename = filename
        self.last_modified = arrow.get(os.stat(file_path).st_mtime)
