from pip4a.tree import JSONVal, Tree


sample_1: JSONVal = {
    "key_one": "one",
    "key_two": 42,
    "key_three": True,
    "key_four": None,
    "key_five": ["one", "two", "three"],
    "key_six": {
        "key_one": "one",
        "key_two": 42,
        "key_three": True,
        "key_four": None,
        "key_five": ["one", "two", "three"],
        "key_six": {
            "key_one": "one",
            "key_two": 42,
            "key_three": True,
            "key_four": None,
            "key_five": ["one", "two", "three"],
            "key_six": {
                "key_one": "one",
                "key_two": 42,
                "key_three": True,
                "key_four": None,
                "key_five": ["one", "two", "three"],
            },
        },
    },
    "key_seven": [{"foo": [1, 2, 3]}],
    "key_eight": [1, 2, 3],
    "key_nine": [{1: 2}, {3: {4: 5}}],
}

sample_2: JSONVal = {
    "key_one": True,
    "key_two": 42,
    "key_three": None,
    "key_four": "four",
    "key_five": [{"a": 1}, {"b": 2}],
}

sample_3: JSONVal = [
    {1: 2},
    [2, 2.1, 2.2, 2.3],
    3,
    4,
    {5: 6},
]

tree = Tree(obj=sample_3)
print(tree.render())
