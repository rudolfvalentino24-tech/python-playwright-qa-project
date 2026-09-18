b = 54
a = "{} {}".format("Value is", b)
print(a)
greeting  = "Welcome to Python Programming"
InstructorName = "Rahul!"
print(greeting + InstructorName)

age = 25
height = 5.9
favorite_color = "blue"

print("Age: {} | Type: {}".format(age, type(age)))
print("Height: {} | Type: {}".format(height, type(height)))
print("Favorite Color: {} | Type: {}".format(favorite_color, type(favorite_color)))

fruits = ["apple", "banana", "cherry", "date", "elderberry"]

print("First fruit:", fruits[0])
print("Last fruit:", fruits[-1])
print("Fruits from index 1 to 2:", fruits[1:3])

person = ("Rahul", 25, 5.9)

print("Age:", person[1])

car = {
    "make": "Toyota",
    "model": "Camry",
    "year": 2020,
    "color": "Blue"
}

print("Car model:", car["model"])

car["owner"] = "Rahul"

print("Updated car dictionary:", car)

greeting = "Hello"

if greeting == "Hello":
    print("Hello there!")
    print("How can I assist you today?")
else:
    print("Greetings!")

print("Program has completed.")

class BasicCalculator:
    def __init__(self, num1, num2):
        self.num1 = num1
        self.num2 = num2

    def addition(self):
        return self.num1 + self.num2

    def subtraction(self):
        return self.num1 - self.num2

    def multiplication(self):
        return self.num1 * self.num2

    def division(self):
        return self.num1 / self.num2


calculator = BasicCalculator(10, 5)

print("Addition:", calculator.addition())
print("Subtraction:", calculator.subtraction())
print("Multiplication:", calculator.multiplication())
print("Division:", calculator.division())

def GreetUser(username):
    print("Hello, {}! Welcome to the Python course.".format(username))


GreetUser("John")

with open("file1.txt", "r") as file:
    content = file.read()

print(content)