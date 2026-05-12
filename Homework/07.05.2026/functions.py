"""
This module contains functions for the Titanic passenger program.
"""

import os
import random
from colorama import Fore
from pyfiglet import Figlet


def get_user_input(max_fare, min_fare):

    # No need to verify the name as instructed.
    t_name = input("Please enter your name: ")

    t_sex = get_valid_input(
        prompt="Please enter your sex (M/F): ",
        expected_type=str,
        exact_input=("M", "F"),
        error_message="The sex value is illegal. Please enter M or F.",
    )

    if t_sex == "M":
        t_sex = "male"
    else:
        t_sex = "female"

    t_age = get_valid_input(
        prompt="Please enter your age: ",
        expected_type=int,
        min_value=0,
        max_value=130,
        error_message="Your age is wrong! Please enter a valid whole number between 0 and 130.",
    )

    t_fare = get_valid_input(
        prompt="Please enter the fare you paid: ",
        expected_type=float,
        min_value=min_fare,
        max_value=max_fare,
        error_message=f"Illegal payment! Please enter a numeric value between {min_fare} and {max_fare}.",
    )

    return t_name, t_sex, t_age, t_fare


# A function to verify user input, Will return false or true if the input is valid or not
def verify_input(input_value, expected_type, exact_input=None, exact_input_type=None):
    if exact_input is not None and input_value not in exact_input:
        return False
    try:
        # If expected type, return true
        value = expected_type(input_value)
        if exact_input_type is not None and not isinstance(value, exact_input_type):
            return False
        return True
    # If not the expected type, return false
    except (TypeError, ValueError):
        return False


def get_valid_input(
    prompt,
    expected_type=str,
    exact_input=None,
    min_value=None,
    max_value=None,
    error_message="Invalid input. Please try again.",
):
    while True:
        value = input(prompt).strip()
        if expected_type is str:
            # Avoid case sensitivity for string inputs
            value = value.upper()
        if verify_input(value, expected_type, exact_input):
            typed_value = expected_type(value)
            if min_value is not None and typed_value < min_value:
                print(Fore.RED + error_message + Fore.RESET)
                continue
            if max_value is not None and typed_value > max_value:
                print(Fore.RED + error_message + Fore.RESET)
                continue
            return typed_value
        print(Fore.RED + error_message + Fore.RESET)


def ticket_gen(tickets):
    while True:
        # 6 digit ticket
        new_ticket = random.randint(100000, 1000000)
        if new_ticket not in tickets:
            return new_ticket


# Will first classify the passenger into a class, based on the median of the fare of each class.
def classify_passenger(fare, c1_fare_median, c2_fare_median, c3_fare_median):
    # Calculate distance from fare to each class median
    diff1 = abs(fare - c1_fare_median)
    diff2 = abs(fare - c2_fare_median)
    diff3 = abs(fare - c3_fare_median)

    # Classify as the lower class by default
    current_class = 3

    # Find which is closest to 0
    if diff1 < diff2 and diff1 < diff3:
        current_class = 1
    elif diff2 < diff3:
        current_class = 2

    # Check if the passenger can be upgraded
    current_class = upgrade_passenger(
        fare, current_class, c1_fare_median, c2_fare_median
    )

    return current_class


# Upgrade function that checks if the passenger can be upgraded to the upper class
def upgrade_passenger(fare, current_class, c1_fare_median, c2_fare_median):
    if current_class == 3 and fare > c2_fare_median:
        return 2
    elif current_class == 2 and fare > c1_fare_median:
        return 1
    else:
        return current_class  # No upgrade

    # Back function to go back to the main menu
def back_to_menu():
    print(Fore.BLUE + "Press any button to go back ↩️" + Fore.RESET)
    input()
    os.system("cls" if os.name == "nt" else "clear")
    title_maker = Figlet(font="slant")
    print(title_maker.renderText("Titanic Death Calculator"))
