import pathlib

# External imports
try:
    from simple_term_menu import TerminalMenu
except (ImportError, NotImplementedError):
    TerminalMenu = None
import pandas as pd
from colorama import Fore
from pyfiglet import Figlet
from tabulate import tabulate

# Internal imports
from Passenger import Passenger
import functions as f


def choose_menu_option(options):
    if TerminalMenu is not None:
        terminal_menu = TerminalMenu(options)
        choice_index = terminal_menu.show()
        if choice_index is None:
            return options[-1]
        return options[choice_index]

    print("Choose an option:")
    for index, option in enumerate(options, start=1):
        print(f"{index}. {option}")

    while True:
        selection = input("Enter option number: ").strip()
        if selection.isdigit():
            choice_number = int(selection)
            if 1 <= choice_number <= len(options):
                return options[choice_number - 1]
        print(Fore.RED + "Invalid menu option. Please try again." + Fore.RESET)


def main():

    base_dir = pathlib.Path(__file__).resolve().parent

    # Get the titanic data set from the script directory
    titanic = pd.read_csv(base_dir / "titanic.csv")

    all_passengers = titanic[["name", "ticket"]].to_dict("records")
    newly_added_passengers = []  # This will store the passengers added in this session

    """
    Because all of the min values of the classes are 0, 
    I'm going to use the median as the threshold for classifying passengers into classes. 
    If the fare is above the median of the higher class I'll classify them into a higher class.
    If not they will stay in the same assigned class.
    """
    # Get the median payment of each class
    c1_fare_median = titanic[titanic["pclass"] == 1]["fare"].dropna().median()
    c2_fare_median = titanic[titanic["pclass"] == 2]["fare"].dropna().median()
    c3_fare_median = titanic[titanic["pclass"] == 3]["fare"].dropna().median()
    # Get the min and max payment of all classes for input validation
    min_fare = titanic["fare"].min()
    max_fare = titanic["fare"].max()

    # Make a nice title for the program
    title_maker = Figlet(font="slant")
    print(title_maker.renderText("Titanic Death Calculator"))

    options = ["Add Passenger", "Show Recent Passengers", "Show All Passengers", "Exit"]

    while True:
        choice = choose_menu_option(options)

        if choice == options[0]:  # "Add Passenger"
            # Get all of the details from the user and store them in variables
            t_name, t_sex, t_age, t_fare = f.get_user_input(
                min_fare=min_fare, max_fare=max_fare
            )

            # Classify the passenger in a class using the classify_passenger()
            t_class = f.classify_passenger(
                t_fare, c1_fare_median, c2_fare_median, c3_fare_median
            )

            # Generate a random ticket number that is not in the data set and assign it to the passenger
            # NOTE: I will not be changing the data in the original csv file, so I will just check the existing tickets as well as newly added in THIS session.
            existing_tickets = set(
                passenger["ticket"] for passenger in all_passengers
            )  # Get existing tickets from the data set
            t_ticket = f.ticket_gen(existing_tickets)

            # Create a passenger object and assign all of the details to it
            passenger = Passenger(
                name=t_name,
                sex=t_sex,
                age=t_age,
                fare=t_fare,
                pc=t_class,
                ticket=t_ticket,
            )

            path_t = base_dir / "tickets"
            path_t.mkdir(
                exist_ok=True
            )  # Create the tickets directory if it doesn't exist
            passenger.print_to_file(path_t)

            # Print the survival chance to the user
            survival_chance = passenger.calculate_survival_chance(titanic)

            print(
                Fore.GREEN
                + f"Dear {t_name}, your chances to die on our trip are {100 - survival_chance * 100:.2f}%.\nEnjoy your trip 🙂"
                + Fore.RESET
            )
            # Add the passenger to the list of recently added passengers
            newly_added_passengers.append([t_name, t_ticket])
            all_passengers.append({"name": t_name, "ticket": t_ticket})
            f.back_to_menu()

        elif choice == options[1]:  # "Show Recent Passengers"
            if not newly_added_passengers:
                print(
                    Fore.YELLOW
                    + "No passengers added in this session yet."
                    + Fore.RESET
                )
            else:
                print(tabulate(newly_added_passengers, tablefmt="grid"))
            f.back_to_menu()

        elif choice == options[2]:  # "Show All Passengers"
            print(tabulate(all_passengers, tablefmt="grid"))
            f.back_to_menu()

        elif choice == options[3]:  # "Exit"
            break


if __name__ == "__main__":
    main()
