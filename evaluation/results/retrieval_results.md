# Retrieval quality results

Model: `all-MiniLM-L6-v2`. Index: 961 unique recipes. k = 5.

Hit@5: **91.7%** (11/12 queries). MRR@5: **0.854**.

Hit@k means at least one predefined relevant recipe appeared in the first k results. MRR@k averages the reciprocal rank of the first relevant result (zero on a miss).

These are 12 small, manually specified development cases, including exact names, paraphrases, ingredient queries, and a time filter. Expected titles were fixed before the first evaluation run. They are incomplete relevance labels; these metrics do not measure precision, dietary safety, generation quality, or performance on unseen users. The corpus is heavily fruit-focused. Similarity is not calibrated confidence; unrelated queries still return nearest neighbors. Long chunks may be truncated by the embedding model.

| Query | First relevant rank | Top results |
|---|---:|---|
| A creamy mashed avocado dip with lime for tortilla chips | 4 | Seven-Layer Dip; Avocado Dessert; Grilled Avocados; Traditional Mexican Guacamole; Mexican Baked Fish |
| Bake a sweet loaf using overripe bananas | 1 | The Best Banana Bread; Almost No Fat Banana Bread; Banana Loaf; Simple Banana Bread; Easy Banana Loaf Cake |
| A refreshing drink made with squeezed lemons water and sugar | 1 | Old-Fashioned Lemonade; Refreshing Cucumber Lemonade; Flavored Water; Orange Crush! Fresh Squeezed Orange and Vodka Cocktail; Watermelon and Strawberry Lemonade |
| Rice simmered in coconut milk as a side dish | 1 | Coconut Rice; Sweet Coconut Rice; Coconut Jasmine Rice; Coconut Lime Rice; Creamy Coconut Milk Rice Pudding |
| Fresh Mango Salsa | 1 | Fresh Mango Salsa; Mango Papaya Salsa; Mango, Peach and Pineapple Salsa; Avocado Mango Salsa; Spicy Mango Salad |
| Baked apples with a crunchy oat and cinnamon topping | 1 | Easy Apple Crisp with Oat Topping; Apple Crisp; Apple Oatmeal Crisp; Apple Cinnamon Oatmeal Muffins; Apple and Pear Crumble |
| Blend banana and peanut butter into a breakfast drink | 1 | Peanut Butter Banana Smoothie; Chocolate Banana Peanut Butter Protein Shake; Strawberry Banana Protein Smoothie; Mango Oatmeal Breakfast Smoothie; Healthy Chocolate Smoothie |
| Bake salmon with lemon in a foil packet | 1 | Baked Salmon in Foil; Parchment Baked Salmon; Lemon Rosemary Salmon; Blackened Salmon Tacos with Chunky Mango Avocado Salsa; Smoked Salmon Poke Bowl |
| Sweet dates stuffed with cheese and wrapped in crispy bacon | 1 | Bacon Wrapped Dates Stuffed with Blue Cheese; Bacon and Date Appetizer; Bacon Wrapped Dates; Date Balls; Date-Nut Balls |
| Toast topped with avocado and an egg for breakfast | 1 | Avocado Toast with Egg; Avocado Breakfast Sandwich; Avocado Toast (Vegan); Avocado Egg Salad; Meyer Lemon Avocado Toast |
| Avocado lime dip | miss | Grilled Avocados; Avocado Salad; Filipino Avocado Milkshake; Avocado Dressing; Meyer Lemon Avocado Toast |
| To Die For Blueberry Muffins | 1 | To Die For Blueberry Muffins; Todd's Famous Blueberry Pancakes; Melt in Your Mouth Blueberry Cake; Homemade Blueberry Pie; Easy Blueberry Cobbler |

Full ranked results, source URLs, distances, timing, dependency versions, and hashes are in `retrieval_results.json`. Timing excludes model startup and is not a load test.

Reproduce: `python -m evaluation.evaluate_retrieval`
