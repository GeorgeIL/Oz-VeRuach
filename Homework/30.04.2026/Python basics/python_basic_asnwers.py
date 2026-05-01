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
1. Create a program that gets 2 lists and creates a new one with the largest value of each index from both lists
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
    list_new = [list1[i] if list1[i] > list2[i] else list2[i] for i in range(len(list1))]
    return list_new

# # Tests

# # List length error check
# print(combine_lists_greatest_value(list_int2, list_wrong_len))
# # List type error check
# print(combine_lists_greatest_value(list_int1, list_wrong_val))

# Valid input check
print(combine_lists_greatest_value(list_int1, list_int2))
