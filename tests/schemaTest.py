import logging
import os
from publ import model, config

logging.basicConfig(level=logging.INFO)

config.database_config['filename'] = os.path.join(os.getcwd(), 'test.db')

model.setup()
