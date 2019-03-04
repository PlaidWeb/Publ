import random

for _ in range(0, 100):
    date = '2012-01-{:0>2} {:0>2}:00:00{:0=+3}:00'.format(random.randint(
        1, 31), random.randint(0, 23), random.randint(-11, 12))
    with open(date.replace(' ', '-').replace(':', '') + '.md', 'w') as file:
        print("""\
Title: {date}
Date: {date}

This is a test for {date}""".format(date=date), file=file)
