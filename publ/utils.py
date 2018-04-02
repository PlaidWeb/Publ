# utils.py
# Some useful utilities that don't belong anywhere else


''' A utility class for template handlers; turns the stringify operator into a call '''
class SelfStrCall:
    def __str__(self):
        return self()
