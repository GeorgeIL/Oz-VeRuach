class Vehicle:

    def __init__(self, name, max_speed, mileage):
        self.name = name
        self.max_speed = max_speed
        self.mileage = mileage      

    def get_info(self):
        return f"{self.name} {self.max_speed} {self.mileage}"
