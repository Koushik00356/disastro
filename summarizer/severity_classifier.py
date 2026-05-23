from transformers import pipeline


classifier = pipeline(
    "text-classification",
    model="facebook/bart-large-mnli"
)


text = """
Massive floods destroyed hundreds of homes.
Thousands evacuated.
Rescue operations ongoing.
"""


labels = [
    "low severity disaster",
    "medium severity disaster",
    "high severity disaster"
]


result = classifier(
    text,
    candidate_labels=labels
)


print(result)