import python_basic_answers as hw1

if __name__ == "__main__":

    """Question 1 tests:"""

    # # Test
    # hw1.question_1()

    """Question 2 tests:"""

    # # Test
    # hw1.question_2()

    """Question 3 tests:"""

    list_int1 = [1, 2, 3, 4, 5]
    list_int2 = [12, 4, 3, 4, 5]
    list_wrong_val = [111, 4, 3, "hi", 5]
    list_wrong_len = [12, 4, 3, 4, 53, 4, 5]

    # # Tests
    # # Valid input check
    # print(hw1.combine_lists_greatest_value(list_int1, list_int2))
    # # List length error check
    # print(hw1.combine_lists_greatest_value(list_int2, list_wrong_len))
    # # List type error check
    # print(hw1.combine_lists_greatest_value(list_int1, list_wrong_val))

    """Question 4 tests:"""

    # # Tests (using question 3's lists)
    # hw1.count_even_odd(list_int1)
    # hw1.count_even_odd(list_wrong_val)

    """Question 5 tests:"""

    # # Tests
    # # Valid input
    # hw1.n_plus_three_dict(5)
    # # Invalid input (string)
    # hw1.n_plus_three_dict("5")

    """Question 6 tests:"""

    dic1 = {1: 10, 2: 20}
    dic2 = {3: 30, 4: 40}
    dic3 = {5: 50, 6: 60}
    dic_dupe = {1: 30, 2: 40}

    # # Tests
    # # Valid input
    # print(hw1.concatenate_dicts(dic1, dic2, dic3))
    # # Dict with dupe keys (dic1[1], dic_dupe[1])
    # print(hw1.concatenate_dicts(dic1, dic2, dic3, dic_dupe))
    # # String inserted into args
    # hw1.concatenate_dicts(dic1, "dic2", dic3)

    """Question 7 tests:"""

    # # Tests
    # # Valid input
    # print(hw1.create_char_dict("HANNA MONTANA"))
    # # Invalid input (number)
    # print(hw1.create_char_dict(2))

    """Question 8 tests:"""

    # # Tests
    # # Valid input
    # print(hw1.combine_two_dict({"a": 1, "b": 2}, {"b": 3, "c": 4}))
    # # String inserted into args
    # print(hw1.combine_two_dict({"a": 1, "b": 2}, "not a dict"))
    # # Dict with string as value
    # print(hw1.combine_two_dict({"a": 1, "b": 2}, {"b": "not a number", "c": 4}))

    """Question 9 tests:"""

    # # Tests
    # # Valid input
    # print(hw1.get_unique_list([1, 2, 3, 4, 5, 5, 4, 3, 2, 1]))
    # # Invalid input (string in list)
    # print(hw1.get_unique_list("not a list"))

    """Question 10 tests:"""

    # # Tests
    # # Valid input
    # hw1.print_number_pyramid(8)
    # # Invalid input (string in list)
    # hw1.print_number_pyramid(":)")

    """Question 11 tests:"""

    # # Tests
    # # Valid input
    # hw1.print_five(4)
    # hw1.print_five(10)
    # Invalid input (string in list)
    # hw1.print_five(":<")

    import matplotlib.pyplot as plt

   plt.sc