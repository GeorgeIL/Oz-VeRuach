# Class importing
from classes.Vehicle import Vehicle
from classes.Bus import Bus
from classes.Helper import Helper as hlp

import python_basic_2_answers as hw2

if __name__ == "__main__":

    """Question 1"""

    # Vehicle creation
    my_vehicle = Vehicle("Mazda", 180, 20000)

    """Question 2"""

    # Bus creation
    my_bus = Bus("Mercedes", 120, 50000)

    """Question 3"""

    # # Helper class methods tests
    # hlp.get_string("Giora Glovatsky")
    # hlp.print_string()
    # hlp.get_string("Hello World")
    # hlp.print_string()
    # # Invalid input
    # hlp.get_string(24)

    """Question 4"""

    # Added my_id.txt

    """Question 5"""

    # Importing the pathlib library
    import pathlib as pl

    # Creating a path object for the my_id.txt file
    _path = (
        pl.PurePath("Homework")
        / "30.04.2026"
        / "python_basics_hw2"
        / "text_files"
        / "my_id.txt"
    )

    # Using the function to get the dictionary and printing it
    my_dict = hw2.get_word_dict(_path)
    # Print the dict
    print(my_dict)

    """Question 6"""

    # print(hw2.get_longest_word(_path))

    """Question 7"""

    # # Tests
    # # Valid input
    # print(hw2.sum_int_list([1, 2, 3, 4, 5]))
    # # Invalid input
    # print(hw2.sum_int_list("[1, 2, 3, 4, 5]"))
    # # # Invalid elements
    # print(hw2.sum_int_list([1, 2, "3", 4, 5]))

    """Question 8"""

    # # Test, (Validation tests are identical to question 7)
    # print(hw2.mult_int_list([1, 2, 3, 4, 5]))

    """Question 9"""

    # # Test, (Validation tests are identical to question 7)
    # print(hw2.min_value_int_list([1, 2, 3, 4, 5, -231]))

    """Question 10"""

    # # Tests
    # # Valid input
    # print(hw2.count_upper_lower("Hello World!"))
    # # Invalid input
    # print(hw2.count_upper_lower([1, 2, 3, 4, 5]))

    """Question 11"""

    # # Calling the function
    # print(hw2.question_11())

    """Question 12"""

    # # Calling the function
    # print(hw2.make_odd_array(22))
    # # Invalid input
    # print(hw2.make_odd_array("22"))

    """Question 13"""

    # # Calling the function
    # hw2.question_13()

    """Question 14"""

    # # Tests
    # # Check via default python operator
    # print(3**4)
    # print(3**-4)
    # print((-2) ** 4)
    # print((-4) ** -4, "\n")
    # # Valid input
    # print(hw2.recursive_power(3, 4))
    # print(hw2.recursive_power(3, -4))
    # print(hw2.recursive_power(-2, 4))
    # print(hw2.recursive_power(-4, -4))
    # # Invalid input
    # print(hw2.recursive_power("-4", -4))
