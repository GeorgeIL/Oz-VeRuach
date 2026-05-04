class Helper:

    # Creating a class attribute that will hold the string at any given time
    global_string = ""

    @classmethod
    def get_string(cls, s: str):
        if not isinstance(s, str):
            raise TypeError("Input must be of string type only!")
        # Save the string as a static variable / class attribute
        cls.global_string = s

    @classmethod
    # Because we touch the class attribute 'global_string' it will be a class method.
    def print_string(cls):
        print(cls.global_string.upper())

