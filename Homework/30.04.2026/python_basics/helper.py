"""In this file I will write helper functions"""


# A function to check if all arguments are of a specific type (or types)
def all_instance_checker(*args, type_check):
    if not all(isinstance(arg, type_check) for arg in args):
        raise TypeError(f"All arguments must be of {type_check} type!")
