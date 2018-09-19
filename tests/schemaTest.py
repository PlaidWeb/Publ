import logging
import os
from pony import orm
from publ import model, config

logging.basicConfig(level=logging.INFO)

config.database_config['filename'] = os.path.join(os.getcwd(), 'test.db')

model.setup()

with orm.db_session:
    cat = model.Category.get(category='test')
    if not cat:
        print("creating anew")
        cat = model.Category(
            category='test', file_path='path', sort_name='asdfadsf')
    orm.commit()

    print(cat.category, cat.file_path, cat.sort_name)

    blank = model.Category.get(category='')
    if not blank:
        print("making fresh")
        blank = model.Category(category='', file_path='blah', sort_name='asdf')
