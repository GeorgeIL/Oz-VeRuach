"""
Question 1)
1. Create a list with identification information about your self
2. Print using a loop
"""

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
list_int1 = [1, 2, 3, 4, 5]
list_int2 = [12, 4, 3, 4, 5]
list_wrong_val = [111, 4, 3, "hi", 5]
list_wrong_len = [12, 4, 3, 4, 53, 4, 5]


def combine_lists_greatest_value(list1: list, list2: list):
    # Check the length of both lists
    if len(list1) != len(list2):
        raise ValueError("list1 and list2 must have the same length!")
    # Check the types in both lists
    if not all(isinstance(x, int) for x in list1) or not all(
        isinstance(x, int) for x in list2
    ):
        raise TypeError("All elements in both lists must be integers")

    # Make a new list and get the largest value from each list given (using list comprehension)
    list_new = [
        list1[i] if list1[i] > list2[i] else list2[i] for i in range(len(list1))
    ]
    return list_new


# # Tests

# # List length error check
# print(combine_lists_greatest_value(list_int2, list_wrong_len))
# # List type error check
# print(combine_lists_greatest_value(list_int1, list_wrong_val))

# Valid input check
print(combine_lists_greatest_value(list_int1, list_int2))


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


# Tests (using question 3's lists)
count_even_odd(list_int1)
count_even_odd(list_wrong_val)


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


n_plus_three_dict(5)


"""
Question 6)
1. Create a Python script to concatenate x dictionaries 
"""
dic1 = {1: 10, 2: 20}
dic2 = {2: 30, 4: 40}
dic_dupe = {1: 30, 2: 40}
dic3 = {5: 50, 6: 60}


def concatenate_dicts(*dicts: dict):
    # Raise type error if not all dicts are actual dictionaries
    if not all(isinstance(dic, dict) for dic in dicts):
        raise TypeError("All values given must be of dict type!")

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


if __name__ == "__main__":
    print(concatenate_dicts(dic1, dic2, dic3))


# Question 6)

# Tests
# Valid input
print(concatenate_dicts(dic1, dic2, dic3))
# # Dict with dupe keys (dic1[1], dic_dupe[1])
# print(concatenate_dicts(dic1, dic2, dic3, dic_dupe))
# # String inserted into args
# concatenate_dicts(dic1, "dic2", dic3)


# Question 7)
print(create_char_dict("HANNA"))
print(create_char_dict("HANNA MONTANA"))
