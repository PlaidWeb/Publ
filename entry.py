# entry.py
# Functions for handling entry content

import email
import markdown

def parse(filepath):
    with open(filepath, 'r') as file:
        message = email.message_from_file(file)

    entry = {k.lower() : v for k,v in message.items()}

    entry_text = message.get_payload()
    body, more = entry_text.split('~~~~~')
    entry['body'] = markdown.markdown(body)
    entry['more'] = markdown.markdown(more)



    # TODO add entry ID, date as appropriate

    return entry

