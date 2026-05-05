# import the checker function from helper
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from python_basics.helper import all_instance_checker
from classes.Stack import Stack

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
1. Create a 1D numpy array without any loops
"""


def question_11():
    arr = np.arange(10)
    return arr


"""
Question 12)
1. Create a 1D numpy array with number values
    * Extract all odd numbers into a new numpy array
    * No loops allowed
"""


def make_odd_array(n: int):
    # Check n first
    all_instance_checker(n, type_check=int)

    arr = np.arange(n)

    odd_arr = arr[arr % 2 != 0]
    return odd_arr


"""
Question 13)
1. Create a numpy eye array 5x5
    * All values > 0 => -1
    * No loops allowed
"""


def question_13():

    arr = np.eye(5)
    print(f"\nBefore\n{arr}")
    arr[arr > 0] = -1
    print(f"\nAfter\n{arr}")


"""
Question 14)
1. Create recursive function to calculate a^b
    * Function will work with whole numbers only
    * Function will allow negative numbers
    * No loops allowed
"""


def recursive_power(a: int, b: int):

    # Make sure only int types are sent
    all_instance_checker(a, b, type_check=int)

    if b == 0:  # Will always be 1
        return 1

    if b < 0:
        return 1 / _recursive_internal(a, -b)

    return _recursive_internal(a, b)


def _recursive_internal(a, b, res=1):
    # Stop con
    if b <= 0:
        return res

    # Recursive call
    return _recursive_internal(a, b - 1, res=res * a)


"""
Question 15)
1. Create function to determine if parenthesis are valid
    * Function gets a string value
    * Function returns boolean value
    * Using a Stack class
"""


def is_valid_parenthesis(string_sent: str):

    openers = ("(", "[", "{")
    closers = (")", "]", "}")

    # Make sure only str types are sent
    all_instance_checker(string_sent, type_check=str)

    # Strip the string from irrelevant values using the function below
    clean_str = keep_only_chars(string_sent, *openers, *closers)

    stk = Stack()
    # Call the parenthesis checker
    result = parenthesis_checker(clean_str, stk, openers, closers)

    # If checker found a mismatch, return False immediately
    if not result:
        return False

    # Valid only if the stack is empty (all openers were matched)
    return stk.is_empty()


def keep_only_chars(string_sent, *chars_to_keep):
    return "".join(c for c in string_sent if c in chars_to_keep)


def parenthesis_checker(clean_str: str, stk: Stack, openers, closers):

    # Build a dict from each closer to its matching opener
    match = {closers[i]: openers[i] for i in range(len(openers))}

    for char in clean_str:
        if char in openers:
            # Push opener onto the stack
            stk.push(char)
        elif char in closers:
            # A closer with nothing to match against is invalid
            if stk.is_empty():
                return False
            # Top of stack must be the matching opener
            if stk.peek() != match[char]:
                return False
            stk.pop()

    return True
