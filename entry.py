# entry.py
# Functions for handling entry content

import email
import markdown

def parse(filepath):
    with open(filepath, 'r') as file:
        message = email.message_from_file(file)

    entry = {k.lower() : v for k,v in message.items()}
    entry['body'] = markdown.markdown(message.get_payload())

    # TODO add entry ID, date as appropriate

    return entry

