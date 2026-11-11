import subprocess

recipe = """
Spaghetti Aglio e Olio.

Step 1: Bring a large pot of water to a boil.

Step 2: Add the pasta and cook until al dente.

Step 3: Heat olive oil in a pan over medium heat.

Step 4: Add chopped garlic and cook until lightly golden.

Step 5: Drain the pasta and add it to the pan.

Step 6: Toss everything together and serve.
"""

print("NOSH - TTS Test")
print(recipe)

print("Reading recipe aloud...")

subprocess.run(["say", recipe])

print("Finished.")