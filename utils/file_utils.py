import json

def load_dictionary(filename):
    """Load a dictionary from a JSON file"""
    try:
        with open(filename, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

def save_list(items, filename):
    """Save a list to a file, one item per line"""
    with open(filename, "w") as file:
        for item in items:
            file.write(f"{item}\n")
