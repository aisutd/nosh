# the one list of things everyone is assumed to always have
STAPLES = ["water", "salt", "pepper", "ice", "sugar", "oil", "butter", "black pepper"]

# "white sugar" and "olive oil" count too, because they contain a staple word
def is_staple(name):
    return any(word in STAPLES for word in name.lower().split())