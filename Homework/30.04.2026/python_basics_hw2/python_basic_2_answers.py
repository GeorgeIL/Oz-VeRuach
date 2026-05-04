# import the checker function from helper
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from python_basics.helper import all_instance_checker

# numpy import
import numpy as np 

"""
Question 5)
1. Create a Python function to count frequency of words in a file
    * Function receives path of file
    * Function returns a dictionary
        - Keys: words
        - Values: frequency
"""


def get_word_dict(path_to_file):

    with open(path_to_file, "r") as file:
        # Get a string of all of the text inside of the file
        content = file.read()
        # File is automatically closed here

    # Create a list from the string of the words
    content_list = content.split()

    # Create the dictionary that will hold all words
    word_dict = dict()
    for word in content_list:
        if not word_dict.keys().__contains__(word):
            word_dict[word] = 1  # Add the word
            continue
        word_dict[word] += 1  # Add +1 frequency

    # Return word_dict
    return word_dict


"""
Question 6)
1. Create a Python function to count frequency of words in a file
    * Function receives path of file
    * Function returns a longest word in file
"""


def get_longest_word(path_to_file):
    # Create a word dict from all of the words
    word_dict = get_word_dict(path_to_file)

    longest = ""
    for word in word_dict.keys():
        if len(word) > len(longest):
            longest = word

    return longest


"""
Question 7)
1. Create a Python function to calculate the sum of integers in a list
    * Function receives a list, all values are integers
    * Function returns the sum of all integers
"""


def sum_int_list(list_sent: list):
    # Check list_sent first
    all_instance_checker(list_sent, type_check=list)
    # Unpack the list and check all of it's elements
    all_instance_checker(*list_sent, type_check=int)

    total = sum(list_sent)

    return total


"""
Question 8)
1. Create a Python function to mult all of integers in a list
    * Function receives a list, all values are integers
    * Function returns the mult value of all integers
"""


def mult_int_list(list_sent: list):
    # Check list_sent first
    all_instance_checker(list_sent, type_check=list)
    # Unpack the list and check all of it's elements
    all_instance_checker(*list_sent, type_check=int)

    from functools import reduce

    # reduce() carries the result forward, using an anonymous function to mult the entire list
    total = reduce(lambda x, y: x * y, list_sent)

    return total


"""
Question 9)
1. Create a Python function to get the min value of a list
    * Function receives a list, all values are integers
    * Function returns the mult value of all integers
"""


def min_value_int_list(list_sent: list):
    # Check list_sent first
    all_instance_checker(list_sent, type_check=list)
    # Unpack the list and check all of it's elements
    all_instance_checker(*list_sent, type_check=int)

    my_list = list_sent.copy()  # To avoid changing the list sent
    my_list.sort()

    return my_list[0]


"""
Question 10)
1. Create a Python function to count upper and lower cases in string
    * Function receives a string
    * Will return a dictionary with the values
"""


def count_upper_lower(string_sent: str):
    # Check string_sent first
    all_instance_checker(string_sent, type_check=str)

    dict_return = {"UPPER": 0, "lower": 0}
    # Go over every char in the string and update the dictionary accordingly
    for char in string_sent:
        if "a" <= char <= "z":
            dict_return["lower"] += 1
        elif "A" <= char <= "Z":
            dict_return["UPPER"] += 1

    return dict_return


"""
Question 11)
1. Create a Python function to count upper and lower cases in string
    * Function receives a string
    * Will return a dictionary with the values
"""
