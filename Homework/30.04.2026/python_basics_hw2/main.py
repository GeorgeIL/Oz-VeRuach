# Class importing
from classes.Vehicle import Vehicle
from classes.Bus import Bus
from classes.Helper import Helper as hlp

if __name__ == "__main__":

    """Question 1"""

    # Vehicle creation
    my_vehicle = Vehicle("Mazda", 180, 20000)

    """Question 2"""

    # Bus creation
    my_bus = Bus("Mercedes", 120, 50000)

    """Question 3"""

    # Helper class methods tests
    hlp.get_string("Giora Glovatsky")
    hlp.print_string()
    hlp.get_string("Hello World")
    hlp.print_string()
    # # Invalid input
    # hlp.get_string(24)

    """Question 4"""
    # Added my_id.txt

    """Question 5"""
    # Added my_id.txt
