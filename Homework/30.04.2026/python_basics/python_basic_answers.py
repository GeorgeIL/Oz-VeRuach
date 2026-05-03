# Import the helper file (for helper functions)
import helper as helper

"""
Question 1)
1. Create a list with identification information about your self
2. Print using a loop
"""


def question_1():
    # List creation
    id_list = ["Giora", "Glovatsky", "26", "0548888888"]

    # List printing using a loop
    for item in id_list:
        print(item)


"""
Question 2)
1. Create a dictionary instead of a list from question 1 with relevant keys for each field
2. Print using a loop
"""


def question_2():
    # Dictionary creation
    id_dict = {
        ("name", "last_name"): "Giora Glovatsky",
        "age": "26",
        "phone_num": "0548888888",
    }

    # Dictionary printing using a loop
    for k, v in id_dict.items():
        print(f"{k}:{v}")


"""
Question 3)
1. Create a Python script that gets 2 lists and creates a new one with the largest value of each index from both lists
    * Lists must be the same length, if not => relevant error
    * Values must be integers
2. Print the new list created
"""


def combine_lists_greatest_value(list1: list, list2: list):
    # Check the length of both lists
    if len(list1) != len(list2):
        raise ValueError("list1 and list2 must have the same length!")

    # Check the types in both lists
    helper.all_instance_checker(*list1, *list2, type_check=int)

    # Make a new list and get the largest value from each list given (using list comprehension)
    list_new = [
        list1[i] if list1[i] > list2[i] else list2[i] for i in range(len(list1))
    ]
    return list_new


"""
Question 4)
1. Create a Python script that gets a list and prints the amount of odd and even numbers in it
    * If encountering a string, break, nullify counters and print "It's a string!"
    * Values must be integers
2. Print the both counters
"""


def count_even_odd(list1: list):
    odd_c = 0
    even_c = 0
    for item in list1:
        if isinstance(item, str):
            print("It's a string!")
            # We will exit the function, nullifying the local variables create ('odd_c' and 'even_c')
            return

        # Assuming int value
        if item % 2 == 0:
            even_c += 1
        else:
            odd_c += 1

    # Print the counters
    print(f"Number of even counters: {even_c}")
    print(f"Number of odd counters: {odd_c}")


"""
Question 5)
1. Create a Python script to generate and print a dictionary 
    * that contains a number (between 1 and n) in the form (x, x+3)
"""


def n_plus_three_dict(n: int):
    # Edge case check - number is not int
    if not isinstance(n, int):
        raise TypeError("'n' must be of integer type!")
    # Dict making
    dict_return = dict()
    for i in range(1, n + 1):
        dict_return[i] = i + 3

    # Print the dict_return
    print(dict_return)
    # Return the new dict
    return dict_return


"""
Question 6)
1. Create a Python script to concatenate x dictionaries 
"""


def concatenate_dicts(*dicts: dict):
    # Raise type error if not all dicts are actual dictionaries
    helper.all_instance_checker(*dicts, type_check=dict)

    # Concatenate all dicts into one
    c_dict = dict()
    found_dupes = False
    for d in dicts:
        for k, v in d.items():
            # Special check to avoid duplicate key errors
            if c_dict.__contains__(k):
                found_dupes = True
                continue
            c_dict[k] = v

    # Return the new dict 'c_dict'
    if found_dupes:
        print("Duplicate key/s found and were skipped.")
    return c_dict


"""
Question 7)
1. Creating a dictionary with the char as key and amount of appearances as value
"""


def create_char_dict(string: str):

    # Check instance of string
    if not isinstance(string, str):
        raise TypeError("Input must be of string type!")

    char_dict = dict()
    for char in string:
        # If we counted the char previously raise the count by 1
        if char_dict.__contains__(char):
            char_dict[char] += 1
            continue
        # Else add it to the dict with the value 1 (first appearance)
        char_dict[char] = 1

    # Return the dictionary
    return char_dict


"""
Question 8)
1. Write a python function that will combine 2 dicts into 1
    * If there are duplicate keys, the value will be combined
"""


def combine_two_dict(dic1: dict, dic2: dict):

    # Check if both inputs are dicts
    if not isinstance(dic1, dict) or not isinstance(dic2, dict):
        raise TypeError("Both inputs must be of dict type!")

    # Check if all values in both dicts are integers or floats (to avoid type errors when combining values)
    helper.all_instance_checker(*dic1.values(), *dic2.values(), type_check=(int, float))

    returned_dict = dict()
    for item1 in dic1.items():
        for item2 in dic2.items():
            # If the keys are the same, combine the values and add to the returned dict
            if item1[0] == item2[0]:
                returned_dict[item1[0]] = item1[1] + item2[1]
                break
            # If the keys are different, add both to the returned dict
            returned_dict[item1[0]] = item1[1]
            returned_dict[item2[0]] = item2[1]

    # Return the dictionary
    return returned_dict


"""
Question 9)
1. Write a python function takes a lists and returns a list without duplicates
"""


def get_unique_list(lst: list):

    # Check if input is a list
    if not isinstance(lst, list):
        raise TypeError("Input must be of list type!")

    # Create a new list without duplicates
    unique_list = []
    for item in lst:
        if item not in unique_list:
            unique_list.append(item)

    # Return the new list
    return unique_list


"""
Question 10)
1. Write a python function takes a number input and builds a number pyramid using nested loops
"""


def print_number_pyramid(n: int):

    # Check if input is an int
    if not isinstance(n, int):
        raise TypeError("Input must be of int type!")

    for i in range(n):
        # +2 to cover the +1 of n, and +1 for j to not stop the loop preemptively
        for j in range(1, i + 2):
            print(j, end="")
        # Go down a line
        print()


def print_five(n: int):

    # Check if input is an int
    if not isinstance(n, int):
        raise TypeError("Input must be of int type!")

    # Top part
    for _ in range(n):
        print("*", end="")
    print()

    # Neck part
    for _ in range(n // 2):
        print("*")

    # Middle part
    storage = n + 1
    for _ in range(2):
        print(" ", end="")
    storage -= n // 2
    for _ in range(n - 1):
        print("*", end="")
    print()

    # Neck (front) part
    for _ in range(n // 2):
        for _ in range(n + 2):
            print(" ", end="")
        print("*")

    # Bottom part
    for _ in range(n):
        print("*", end="")
    print()



