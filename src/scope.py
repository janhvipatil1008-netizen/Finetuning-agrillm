"""
scope.py — frozen scope for the plant-protection fine-tune (V1, no RAG).

STATUS: PROVISIONAL. Every `canonical` string below must be reconciled against the
CIBRC "Major Uses of Pesticides" tables in Step 4. CIBRC's pest string is the key
your verifier joins on — if CIBRC says "Jassid", this file must say "Jassid".

chem: "rich"   -> multiple registered label claims expected; normal advisory path
      "thin"   -> few/one registered claim, or seed-treatment only; verify carefully
      "none"   -> no curative chemistry against the pathogen itself.
                  Correct answer = vector/cultural management + escalate.
                  These are your refusal-training cases. Do not let them disappear.
"""

CROPS = ["cotton", "soybean", "tur", "gram", "onion", "tomato", "grape", "pomegranate"]

TARGETS = {
    "cotton": [
        {"canonical": "Pink bollworm", "type": "pest", "chem": "rich"},
        {"canonical": "Whitefly", "type": "pest", "chem": "rich"},
        {"canonical": "Jassid", "type": "pest", "chem": "rich"},
        {"canonical": "Thrips", "type": "pest", "chem": "rich"},
        {"canonical": "Bacterial blight", "type": "disease", "chem": "thin"},
    ],
    "soybean": [
        {"canonical": "Girdle beetle", "type": "pest", "chem": "rich"},
        {"canonical": "Stem fly", "type": "pest", "chem": "rich"},
        {"canonical": "Semilooper", "type": "pest", "chem": "rich"},
        {"canonical": "Rust", "type": "disease", "chem": "rich"},
        {"canonical": "Yellow mosaic", "type": "disease", "chem": "none"},
    ],
    "tur": [
        {"canonical": "Pod borer", "type": "pest", "chem": "rich"},
        {"canonical": "Spotted pod borer", "type": "pest", "chem": "rich"},
        {"canonical": "Pod fly", "type": "pest", "chem": "thin"},
        {"canonical": "Wilt", "type": "disease", "chem": "thin"},
        {"canonical": "Sterility mosaic", "type": "disease", "chem": "none"},
    ],
    "gram": [
        {"canonical": "Gram pod borer", "type": "pest", "chem": "rich"},
        {"canonical": "Cutworm", "type": "pest", "chem": "thin"},
        {"canonical": "Wilt", "type": "disease", "chem": "thin"},
        {"canonical": "Dry root rot", "type": "disease", "chem": "thin"},
        {"canonical": "Collar rot", "type": "disease", "chem": "thin"},
    ],
    "onion": [
        {"canonical": "Thrips", "type": "pest", "chem": "rich"},
        {"canonical": "Purple blotch", "type": "disease", "chem": "rich"},
        {"canonical": "Stemphylium blight", "type": "disease", "chem": "thin"},
        {"canonical": "Basal rot", "type": "disease", "chem": "thin"},
        {"canonical": "Anthracnose", "type": "disease", "chem": "thin"},
    ],
    "tomato": [
        # Phase 6 Step A found these conflated. CIB&RC lists them as separate
        # organisms IN THE SAME CELL (Spinetoram 11.70% SC: "...Leaf miner
        # (Liriomyza trifolii), tomato pinworm (Tuta absoluta)"), and every one
        # of the six in-cell glosses on "leaf miner" reads Liriomyza trifolii.
        # Different species, different registered chemistry, one former target.
        {"canonical": "Leaf miner (Liriomyza trifolii)", "type": "pest", "chem": "rich"},
        {"canonical": "Tomato pinworm (Tuta absoluta)", "type": "pest", "chem": "thin"},
        {"canonical": "Fruit borer", "type": "pest", "chem": "rich"},
        {"canonical": "Early blight", "type": "disease", "chem": "rich"},
        {"canonical": "Late blight", "type": "disease", "chem": "rich"},
        {"canonical": "Leaf curl virus", "type": "disease", "chem": "none"},
    ],
    "grape": [
        {"canonical": "Downy mildew", "type": "disease", "chem": "rich"},
        {"canonical": "Powdery mildew", "type": "disease", "chem": "rich"},
        {"canonical": "Anthracnose", "type": "disease", "chem": "rich"},
        {"canonical": "Thrips", "type": "pest", "chem": "rich"},
        {"canonical": "Mealybug", "type": "pest", "chem": "rich"},
    ],
    "pomegranate": [
        {"canonical": "Bacterial blight", "type": "disease", "chem": "thin"},
        {"canonical": "Fruit borer", "type": "pest", "chem": "rich"},
        {"canonical": "Thrips", "type": "pest", "chem": "rich"},
        {"canonical": "Wilt", "type": "disease", "chem": "none"},
        {"canonical": "Cercospora fruit spot", "type": "disease", "chem": "thin"},
    ],
}

# Farmer-facing strings -> canonical. Used to normalise KCC queries and to generate
# paraphrase variants for training. Marathi transliterations are best-effort and
# MUST be checked by a native speaker before they enter the training set.
SYNONYMS = {
    "gulabi bondhali": "Pink bollworm",
    "pink bollworm": "Pink bollworm",
    "pandhri mashi": "Whitefly",
    "safed makkhi": "Whitefly",
    "tudtude": "Jassid",
    "leafhopper": "Jassid",
    "hopper burn": "Jassid",
    "mava": "Aphid",
    "phulkide": "Thrips",
    "thrips": "Thrips",
    "bhuri": "Powdery mildew",
    "davnya": "Downy mildew",
    "karpa": "Anthracnose",
    "telya": "Bacterial blight",
    "oily spot": "Bacterial blight",
    "helicoverpa": "Pod borer",
    "ghatee ali": "Pod borer",
    "mar rog": "Wilt",
    "anar butterfly": "Fruit borer",
}

# Look-alike pairs the model must discriminate. Build benchmark items in pairs so a
# keyword-matching baseline cannot score well on them.
CONFUSABLE_PAIRS = [
    ("tomato", "Early blight", "tomato", "Late blight"),
    ("onion", "Purple blotch", "onion", "Stemphylium blight"),
    ("grape", "Downy mildew", "grape", "Powdery mildew"),
    ("cotton", "Bacterial blight", "cotton", "Alternaria leaf spot"),
    ("cotton", "Thrips", "cotton", "Jassid"),
    ("gram", "Wilt", "gram", "Dry root rot"),
    ("pomegranate", "Bacterial blight", "pomegranate", "Cercospora fruit spot"),
    ("tur", "Wilt", "tur", "Phytophthora blight"),
]

# Same pest, different crop -> different registered dose and PHI. These are the
# highest-value items in the benchmark: they punish crop-agnostic memorisation.
CROSS_CROP_PESTS = {
    "Helicoverpa armigera": ["cotton", "tur", "gram", "tomato"],
    "Thrips": ["cotton", "onion", "grape", "pomegranate"],
    "Whitefly": ["cotton", "soybean", "tomato"],
}

def all_targets():
    return [(c, t["canonical"], t["type"], t["chem"])
            for c, ts in TARGETS.items() for t in ts]

if __name__ == "__main__":
    rows = all_targets()
    print(f"{len(CROPS)} crops, {len(rows)} targets")
    for label in ("rich", "thin", "none"):
        print(f"  chem={label}: {sum(1 for r in rows if r[3] == label)}")
