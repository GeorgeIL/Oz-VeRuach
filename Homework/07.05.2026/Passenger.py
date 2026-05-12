from tabulate import tabulate
import pathlib


class Passenger:
    def __init__(self, name, sex, age, fare, pc, ticket):
        self.name = name
        self.sex = sex
        self.age = age
        self.fare = fare
        self.ticket = ticket
        self.pclass = pc

    # Print the passenger details to a file in a nice format using tabulate
    def print_to_file(self, file_path):

        data = [
            ["ticket: " + str(self.ticket), "fare: " + "{:.2f}".format(self.fare)],
            ["age: " + str(self.age), "class: " + str(self.pclass)],
            ["sex: " + str(self.sex), "name: " + str(self.name)],
        ]

        file_path = pathlib.Path(file_path)
        with open(file_path / f"{self.name}.{self.ticket}.txt", "w") as file:
            file.write(tabulate(data, tablefmt="grid"))

    # Calculate the survival chance of the passenger based on the titanic data set
    def calculate_survival_chance(self, titanic_data):
        # Filter the titanic data set based on
        # Age: 18 >= age < 18
        # Sex: male or female
        # Class: 1, 2, or 3

        # Calculate survival chance
        survival_chance = titanic_data[
            (titanic_data["sex"] == self.sex)
            & (titanic_data["pclass"] == self.pclass)
            & (
                titanic_data["age"] >= 18
                if self.age >= 18
                else titanic_data["age"] < 18
            )
        ]["survived"].mean()

        return survival_chance

    # str function for passenger
    def __str__(self):
        return f"Name: {self.name}, Sex: {self.sex}, Age: {self.age}, Fare: {self.fare}, Ticket: {self.ticket}, Class: {self.pclass}"
