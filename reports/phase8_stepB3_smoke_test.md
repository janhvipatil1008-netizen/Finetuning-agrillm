# Phase 8 Sub-phase B3 -- live smoke test
Model: `claude-sonnet-4-6` via Anthropic Batch API, single batch, no retries (max_attempts=1). 20 items across all 5 slices plus OFFTOPIC.

## S1_637 -- slice 1 (dose) -- cotton
Query: `APHIDS MANAGEMENT IN COTTON`
Verdict: **accepted**
verify() score: 1.0 | passed: True | excluded: False
Fact-sheet fidelity: True

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Aphid",
      "type": "pest",
      "confidence": 0.95,
      "evidence": "Aphids (Aphis gossypii and related species) are common sucking pests on cotton that colonise the undersides of leaves and tender shoots, causing leaf curl, honeydew deposition, and sooty mould. The farmer has specifically named aphids as the problem."
    }
  ],
  "non_chemical_first": [
    "Monitor fields regularly (at least twice a week) using yellow sticky traps to track aphid population build-up and determine the need for intervention.",
    "Conserve natural enemies such as ladybird beetles (Coccinella spp.), lacewings, and parasitic wasps by avoiding broad-spectrum insecticide sprays early in the season.",
    "Remove and destroy heavily infested plant parts (leaves, shoots) to reduce the local aphid source.",
    "Avoid excessive nitrogen fertilisation, which produces lush, succulent growth that is highly attractive to aphids.",
    "Use reflective silver mulches around the base of plants to deter aphid movement and reduce colonisation."
  ],
  "chemical_options": [
    {
      "active_ingredient": "Acetamiprid 20% SP",
      "formulation": "Acetamiprid 20% SP",
      "dose": {
        "basis": "per_acre",
        "value_min": 20.2339,
        "value_max": null,
        "unit": "g",
        "raw": "50"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 15,
      "phi_not_applicable": false,
      "caution": "Wear protective gloves, mask, and goggles during mixing and spraying. Keep children, livestock, and unprotected persons out of the treated area. Do not spray near water bodies to protect aquatic organisms. Observe a 15-day pre-harvest interval."
    },
    {
      "active_ingredient": "Flonicamid 50%WG",
      "formulation": "Flonicamid 50% WG",
      "dose": {
        "basis": "per_acre",
        "value_min": 60.7017,
        "value_max": null,
        "unit": "g",
        "raw": "150"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 25,
      "phi_not_applicable": false,
      "caution": "Wear full protective equipment including gloves, mask, and eye protection. Re-enter the field only after spray has dried. Observe a 25-day pre-harvest interval. Rotate with a different mode-of-action to delay resistance."
    },
    {
      "active_ingredient": "Spirotetramat 15.31%w/w OD",
      "formulation": "Spirotetramat 15.31% w/w OD",
      "dose": {
        "basis": "per_acre",
        "value_min": 283.2747,
        "value_max": null,
        "unit": "ml",
        "raw": "700"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 52,
      "phi_not_applicable": false,
      "caution": "Wear protective gloves, mask, and goggles. Do not re-enter the treated field for at least 24 hours after application. Observe the 52-day pre-harvest interval strictly. Store the product away from food, feed, and children."
    },
    {
      "active_ingredient": "Thiamethoxam 25%WG",
      "formulation": "Thiamethoxam 25% WG",
      "dose": {
        "basis": "per_acre",
        "value_min": 40.4678,
        "value_max": null,
        "unit": "g",
        "raw": "100"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 21,
      "phi_not_applicable": false,
      "caution": "Wear protective clothing including gloves and mask during application. This product is toxic to bees — do not spray when crop is flowering or when bees are foraging. Observe a 21-day pre-harvest interval. Keep livestock away from treated areas."
    }
  ],
  "safety": [
    "Always wear personal protective equipment (PPE) — gloves, full-sleeved clothing, eye protection, and a nose-mouth mask — when handling and applying any of these insecticides.",
    "Do not eat, drink, or smoke during pesticide mixing or application.",
    "Keep all people, children, and livestock away from the treated field during and immediately after spraying.",
    "Allow the spray to dry completely before allowing re-entry into the field (minimum 24 hours is recommended).",
    "Strictly observe the pre-harvest interval (PHI) stated for each product; do not harvest cotton before the PHI has elapsed after the last spray.",
    "Do not spray near ponds, rivers, or irrigation channels — these products can be toxic to aquatic organisms.",
    "Dispose of empty pesticide containers safely by puncturing and burying them in a designated waste site; do not reuse containers.",
    "In case of accidental poisoning, contact the nearest poison control centre or hospital immediately and carry the product label for reference.",
    "The pesticide label on the container is legally binding under the Insecticides Act, 1968 — always read and follow label directions. This advisory does not substitute for the label or for guidance from the state agriculture department or a qualified agronomist."
  ],
  "escalate_to_expert": false
}
```

## S1_663 -- slice 1 (dose) -- cotton
Query: `Ask about sucking pests problem in cotton crop ( Jassid, Aphid, White Flies)`
Verdict: **rejected: C5: top cause 'Jassid'; the query was about 'White flies', which CIB&RC prints as ['Whiteflies', 'Jassid', 'Aphids']**
verify() score: 0.9 | passed: False | excluded: False
Failures:
- C5: top cause 'Jassid'; the query was about 'White flies', which CIB&RC prints as ['Whiteflies', 'Jassid', 'Aphids']
Fact-sheet fidelity: None

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Jassid",
      "type": "pest",
      "confidence": 0.92,
      "evidence": "Jassids (Amrasca biguttula biguttula) cause upward/downward curling and reddening of cotton leaves by sucking cell sap; common in Maharashtra cotton during kharif season."
    },
    {
      "name": "Aphid",
      "type": "pest",
      "confidence": 0.92,
      "evidence": "Aphids (Aphis gossypii) colonise tender shoots and undersides of leaves, causing leaf curl and honeydew secretion leading to sooty mould in cotton."
    },
    {
      "name": "Whitefly",
      "type": "pest",
      "confidence": 0.92,
      "evidence": "Whitefly (Bemisia tabaci) is a major sucking pest of cotton in Maharashtra; also vectors Cotton Leaf Curl Virus (CLCuV). Adults and nymphs suck sap from leaf undersides."
    }
  ],
  "non_chemical_first": [
    "Install yellow sticky traps (10–12 per acre) to monitor and mass-trap whitefly and aphid adults; replace traps fortnightly.",
    "Remove and destroy severely infested leaves and growing tips showing heavy aphid or jassid colonies to prevent population buildup.",
    "Avoid excessive application of nitrogenous fertilisers, which produce soft, succulent growth that is highly attractive to sucking pests.",
    "Conserve natural enemies such as Chrysoperla carnea (green lacewing), ladybird beetles, and spiders by avoiding broad-spectrum insecticide sprays in the early crop stage.",
    "Maintain field sanitation by removing weeds (especially Hibiscus, Malvaceae family) from field borders, which serve as alternate hosts for jassids and whiteflies.",
    "Adopt reflective silver/silver-grey polyethylene mulches in nursery stages to repel whiteflies and aphids."
  ],
  "chemical_options": [
    {
      "active_ingredient": "Acetamiprid 20% SP",
      "formulation": "Acetamiprid 20% SP",
      "dose": {
        "basis": "per_acre",
        "value_min": 40.4678,
        "value_max": null,
        "unit": "g",
        "raw": "100"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 15,
      "phi_not_applicable": false,
      "caution": "Neonicotinoid — do not spray on open flowers to protect pollinators. Wear chemical-resistant gloves, full-sleeve clothing, and a face mask during mixing and application. Keep children and livestock away from the field. Re-enter the treated field only after the spray has dried completely (minimum 4–6 hours)."
    },
    {
      "active_ingredient": "Flonicamid 50%WG",
      "formulation": "Flonicamid 50% WG",
      "dose": {
        "basis": "per_acre",
        "value_min": 60.7017,
        "value_max": null,
        "unit": "g",
        "raw": "150"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 25,
      "phi_not_applicable": false,
      "caution": "Selective feeding blocker — effective against aphids and whiteflies with low impact on beneficial insects when used correctly. Wear PPE including gloves, mask, and goggles. Do not spray near water bodies. Observe 25-day PHI before harvest."
    },
    {
      "active_ingredient": "Buprofezin 70%DF",
      "formulation": "Buprofezin 70% DF",
      "dose": {
        "basis": "per_acre",
        "value_min": 144.4701,
        "value_max": 173.6069,
        "unit": "g",
        "raw": "357 –429"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 20,
      "phi_not_applicable": false,
      "caution": "Insect growth regulator — acts on nymphal stages of whitefly and jassid; best applied at early nymphal stage. Wear gloves, mask, and protective clothing. Avoid drift onto non-target crops and water sources. Re-entry interval: after spray dries. Observe 20-day PHI before harvest."
    },
    {
      "active_ingredient": "Diafenthiuron 47.80%SC",
      "formulation": "Diafenthiuron 47.80% SC",
      "dose": {
        "basis": "per_acre",
        "value_min": 202.339,
        "value_max": null,
        "unit": "ml",
        "raw": "500"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 41,
      "phi_not_applicable": false,
      "caution": "Pro-insecticide activated by sunlight — spray in morning or evening hours for optimum efficacy. Toxic to fish and aquatic organisms; avoid contamination of water bodies. Wear full PPE including gloves, goggles, and respirator. Observe 41-day PHI strictly before harvesting cotton bolls."
    }
  ],
  "safety": [
    "Always wear chemical-resistant gloves, full-sleeve shirt and trousers, rubber boots, and a nose-mouth mask or respirator when handling and spraying any insecticide.",
    "Mix and load pesticides in a well-ventilated area or open space; never mix pesticides near drinking water sources or food storage areas.",
    "Keep all persons, children, and livestock away from the treated field during spraying and until the spray deposit has dried fully.",
    "Do not eat, drink, or smoke during pesticide application.",
    "Wash hands, face, and all exposed skin thoroughly with soap and water after application; wash contaminated clothing separately before reuse.",
    "Store all pesticides in original labelled containers in a locked store, away from food, feed, and water, and out of reach of children.",
    "Dispose of empty pesticide containers safely by triple-rinsing and puncturing; never reuse or burn them.",
    "Observe the pre-harvest interval (PHI) strictly: do not harvest cotton bolls within the number of days specified for each product after the last spray.",
    "In case of accidental poisoning or skin/eye contact, wash immediately with plenty of water and consult a doctor, carrying the pesticide label or container to the medical facility.",
    "The pesticide label on the container is legally binding under the Insecticides Act, 1968 — always read and follow label directions. This advisory is a guide only and does not replace the state agriculture department or a qualified agronomist."
  ],
  "escalate_to_expert": false
}
```

## S1_668 -- slice 1 (dose) -- tomato
Query: `ASKED ABOUT LEAF MINOR ATTACK ON TOMATO?`
Verdict: **accepted**
verify() score: 1.0 | passed: True | excluded: False
Fact-sheet fidelity: True

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Leaf miner",
      "type": "pest",
      "confidence": 0.9,
      "evidence": "Leaf miners (Liriomyza trifolii and related species) create characteristic serpentine tunnels (mines) within tomato leaf tissue as larvae feed between the upper and lower leaf surfaces, causing yellowing and premature leaf drop."
    }
  ],
  "non_chemical_first": [
    "Remove and destroy heavily mined leaves by collecting them in a bag and burning or burying them away from the field to reduce larval and pupal populations.",
    "Use yellow sticky traps (at least 8–10 per acre) to monitor and mass-trap adult leaf miner flies; replace traps regularly when they become full.",
    "Avoid excessive nitrogen fertilisation, which produces lush, tender foliage that is highly attractive to leaf miners.",
    "Encourage natural parasitoids (e.g., Diglyphus and Opius species) by avoiding broad-spectrum insecticides when pest pressure is low; maintain field margins with flowering plants to harbour beneficials."
  ],
  "chemical_options": [
    {
      "active_ingredient": "Abamectin 01.90 % EC",
      "formulation": "Abamectin 01.90 % EC",
      "dose": {
        "basis": "per_acre",
        "value_min": 182.1051,
        "value_max": 242.8068,
        "unit": "ml",
        "raw": "450 - 600"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 3,
      "phi_not_applicable": false,
      "caution": "Abamectin is highly toxic to bees and aquatic organisms; do not spray near water bodies or during flowering when bees are active. Wear full protective clothing, gloves, and a mask during mixing and application. Re-entry interval: 12 hours after spray has dried."
    },
    {
      "active_ingredient": "Cyantraniliprole 10.26% OD",
      "formulation": "Cyantraniliprole 10.26% OD",
      "dose": {
        "basis": "per_acre",
        "value_min": 364.2103,
        "value_max": null,
        "unit": "ml",
        "raw": "900"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 3,
      "phi_not_applicable": false,
      "caution": "Ensure thorough coverage of leaf undersides where mines are present. Wear protective gloves, goggles, and a mask. Keep livestock and people out of the treated area until spray has dried completely."
    },
    {
      "active_ingredient": "Spinetoram 11.70 %SC",
      "formulation": "Spinetoram 11.70 % SC",
      "dose": {
        "basis": "per_acre",
        "value_min": 151.7543,
        "value_max": 182.1051,
        "unit": "ml",
        "raw": "375-450"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 3,
      "phi_not_applicable": false,
      "caution": "Spinetoram is moderately toxic to bees; avoid application during peak bee foraging hours. Wear gloves, a face mask, and protective clothing. Do not allow spray drift onto adjoining crops or water sources."
    },
    {
      "active_ingredient": "Chlorantraniliprole 4.3% +Abamectin 1.7% SC",
      "formulation": "Chlorantraniliprole 4.3% + Abamectin 1.7% SC",
      "dose": {
        "basis": "per_acre",
        "value_min": 202.339,
        "value_max": null,
        "unit": "ml",
        "raw": "500"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 5,
      "phi_not_applicable": false,
      "caution": "This combination product contains abamectin; highly toxic to bees and aquatic organisms. Wear full PPE including gloves, goggles, and respirator. Do not harvest tomato fruits within 5 days of application. Keep children and livestock away from the treated field."
    }
  ],
  "safety": [
    "Always wear protective clothing including full-sleeved shirt, trousers, chemical-resistant gloves, goggles, and a nose-mouth mask (N95 or equivalent) when mixing and spraying any pesticide.",
    "Do not eat, drink, or smoke during pesticide handling. Wash hands, face, and exposed skin thoroughly with soap and water after application.",
    "Keep all people and livestock out of the treated field during spraying and until the spray deposit has dried completely.",
    "Observe the pre-harvest interval (PHI) strictly — do not harvest tomato fruits before the stated number of days after the last spray.",
    "Dispose of empty pesticide containers safely by triple-rinsing, puncturing, and depositing at an authorised disposal site; never reuse containers.",
    "The pesticide label on the container is legally binding under the Insecticides Act, 1968 — always read and follow label directions. This advisory is a guide only; consult your local Agriculture Department or a qualified agronomist for field-specific advice."
  ],
  "escalate_to_expert": false
}
```

## S1_744 -- slice 1 (dose) -- tomato
Query: `Leaf spot disease    Initially circular black spots on leaves, coalesce and burnt symptoms.in Tomato`
Verdict: **accepted**
verify() score: 1.0 | passed: True | excluded: False
Fact-sheet fidelity: True

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Leaf spot",
      "type": "disease",
      "confidence": 0.85,
      "evidence": "Circular black spots on leaves that coalesce and produce a blighted/burnt appearance are characteristic of fungal leaf spot diseases on tomato (commonly caused by Alternaria solani or Septoria lycopersici)."
    }
  ],
  "non_chemical_first": [
    "Remove and destroy infected leaves and plant debris from the field to reduce the primary inoculum source.",
    "Avoid overhead irrigation; use drip irrigation to keep foliage dry and reduce conditions favourable for fungal sporulation.",
    "Maintain proper plant spacing to improve air circulation within the canopy.",
    "Rotate tomato with non-solanaceous crops for at least two seasons to break the disease cycle."
  ],
  "chemical_options": [
    {
      "active_ingredient": "Captan 70%+ Hexaconazole 5%WP",
      "formulation": "Captan 70%+ Hexaconazole 5%WP",
      "dose": {
        "basis": "per_acre",
        "value_min": 303.5086,
        "value_max": null,
        "unit": "g",
        "raw": "750"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 7,
      "phi_not_applicable": false,
      "caution": "Wear gloves, protective clothing, and a face mask during mixing and spraying. Do not harvest tomatoes within 7 days of the last application."
    },
    {
      "active_ingredient": "Thiophanate methyl 15% (w/w) + Copper Oxychloride 40%(w/w) WP",
      "formulation": "Thiophanate methyl 15% (w/w) + Copper Oxychloride 40%(w/w) WP",
      "dose": {
        "basis": "per_acre",
        "value_min": 809.3562,
        "value_max": null,
        "unit": "g",
        "raw": "2000"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 7,
      "phi_not_applicable": false,
      "caution": "Wear gloves, protective clothing, and a face mask during mixing and spraying. Do not harvest tomatoes within 7 days of the last application. Avoid repeated use of the same fungicide to prevent resistance build-up; alternate with a different mode of action."
    }
  ],
  "safety": [
    "Always wear personal protective equipment (gloves, mask, goggles, and full-sleeved clothing) when handling and applying fungicides.",
    "Keep all people and livestock out of the treated field during spraying and until spray has dried completely.",
    "Do not spray during strong winds or rain, and avoid spraying near water bodies.",
    "Wash hands, face, and exposed skin thoroughly with soap and water after application.",
    "Store chemicals in their original containers, out of reach of children, away from food and feed.",
    "Dispose of empty containers safely as per label instructions; never reuse them.",
    "The pesticide label on the container is legally binding — always read and follow label instructions before use."
  ],
  "escalate_to_expert": false
}
```

## S1_721 -- slice 1 (dose) -- soybean
Query: `Farmer wants to know information about how to control defoliators and girdle beetle in soybean?`
Verdict: **rejected: C5: top cause 'Defoliator'; the query was about 'girdle beetle', which CIB&RC prints as ['Whitefly', 'girdle beetle', 'semi looper']**
verify() score: 0.888889 | passed: False | excluded: False
Failures:
- C5: top cause 'Defoliator'; the query was about 'girdle beetle', which CIB&RC prints as ['Whitefly', 'girdle beetle', 'semi looper']
Fact-sheet fidelity: None

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Defoliator",
      "type": "pest",
      "confidence": 0.9,
      "evidence": "Various caterpillar species (e.g., Spodoptera litura, Chrysodeixis acuta) feed on soybean leaves causing irregular holes and complete defoliation in heavy infestations."
    },
    {
      "name": "Girdle beetle",
      "type": "pest",
      "confidence": 0.9,
      "evidence": "Obereopsis brevis (girdle beetle) adult females girdle stems to lay eggs; larvae bore into the stem causing wilting and stem breakage, a characteristic symptom in soybean."
    }
  ],
  "non_chemical_first": [
    "Deep summer ploughing to expose pupae and soil-dwelling stages of defoliators and girdle beetle to sun and predators.",
    "Collect and destroy egg masses and early instar larval clusters of defoliating caterpillars by hand-picking; similarly remove and destroy girdled stem portions containing girdle beetle eggs and larvae.",
    "Install light traps (1 per acre) to monitor and mass-trap adult moths of defoliating species.",
    "Encourage and conserve natural enemies such as Trichogramma egg parasitoids by avoiding broad-spectrum insecticide sprays early in the season.",
    "Maintain field sanitation — remove and burn crop residues after harvest to reduce overwintering populations of both pests.",
    "Grow soybean at recommended plant spacing to ensure good canopy aeration and to facilitate scouting; avoid excessive nitrogen which promotes lush growth favoured by defoliators."
  ],
  "chemical_options": [
    {
      "active_ingredient": "Chlorantraniliprole 18.50% SC",
      "formulation": "Chlorantraniliprole 18.50% SC",
      "dose": {
        "basis": "per_acre",
        "value_min": 60.7017,
        "value_max": null,
        "unit": "ml",
        "raw": "150"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 22,
      "phi_not_applicable": false,
      "caution": "Wear full-sleeve protective clothing, gloves, mask, and goggles during mixing and spraying. Do not spray near water bodies. Re-entry interval: 24 hours after spraying."
    },
    {
      "active_ingredient": "Emamectin benzoate 01.90%EC",
      "formulation": "Emamectin benzoate 01.90% EC",
      "dose": {
        "basis": "per_acre",
        "value_min": 171.9882,
        "value_max": null,
        "unit": "ml",
        "raw": "425"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 20,
      "phi_not_applicable": false,
      "caution": "Wear protective gloves, mask, and goggles. Avoid inhaling spray mist. Keep children and livestock away from treated fields for at least 48 hours. Do not contaminate water sources."
    },
    {
      "active_ingredient": "Profenofos 50%EC",
      "formulation": "Profenofos 50% EC",
      "dose": {
        "basis": "per_acre",
        "value_min": 404.6781,
        "value_max": null,
        "unit": "ml",
        "raw": "1000"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 40,
      "phi_not_applicable": false,
      "caution": "Organophosphate compound — wear chemical-resistant gloves, mask, goggles, and full protective clothing. Do not eat, drink, or smoke during application. Re-entry interval: 48 hours. Keep away from livestock and water bodies."
    },
    {
      "active_ingredient": "Chlorantraniliprole 09.30%+Lambda-cyhalothrin 04.60% ZC",
      "formulation": "Chlorantraniliprole 09.30% + Lambda-cyhalothrin 04.60% ZC",
      "dose": {
        "basis": "per_acre",
        "value_min": 80.9356,
        "value_max": null,
        "unit": "ml",
        "raw": "200"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 41,
      "phi_not_applicable": false,
      "caution": "Combination product — wear full protective gear including gloves, mask, and goggles. Avoid spray drift onto neighbouring crops and water bodies. Keep people and livestock out of treated area for at least 48 hours."
    }
  ],
  "safety": [
    "Always wear protective equipment: chemical-resistant gloves, full-sleeve clothes, a face mask or respirator, and goggles when handling and applying any pesticide.",
    "Do not eat, drink, or smoke during pesticide mixing or application.",
    "Keep all children, animals, and livestock away from the field during spraying and for a minimum of 48 hours after application.",
    "Spray early in the morning or late in the evening to reduce bee exposure and drift; avoid spraying during windy conditions.",
    "Strictly observe the Pre-Harvest Interval (PHI) for each product — do not harvest the crop before the specified number of days after the last spray.",
    "Dispose of empty pesticide containers safely — rinse three times, puncture, and hand over to authorized collection points; never reuse containers.",
    "In case of accidental ingestion or skin/eye exposure, wash thoroughly with water and seek immediate medical attention. Carry the pesticide label to the doctor.",
    "The pesticide label on the container is legally binding under the Insecticides Act, 1968; always read and follow label instructions before use.",
    "This advisory is a guidance aid only — consult your local Agriculture Department officer or a qualified agronomist for confirmation and field-specific advice."
  ],
  "escalate_to_expert": false
}
```

## S1_742 -- slice 1 (dose) -- soybean
Query: `Farmer wants information regarding control of Collar Rot Disease in Soybean crop?`
Verdict: **accepted**
verify() score: 1.0 | passed: True | excluded: False
Fact-sheet fidelity: True

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Collar rot",
      "type": "disease",
      "confidence": 0.9,
      "evidence": "Collar rot in soybean is caused by Sclerotium rolfsii, leading to rotting of the stem at the soil surface, yellowing, wilting, and plant death, especially in warm and wet conditions."
    }
  ],
  "non_chemical_first": [
    "Use certified, disease-free seeds and practice seed treatment before sowing to reduce soil-borne inoculum.",
    "Adopt deep summer ploughing to expose and destroy sclerotia in the soil before the sowing season.",
    "Ensure proper field drainage to avoid waterlogging, as excess soil moisture promotes collar rot development.",
    "Follow a crop rotation with non-host crops such as cereals (wheat, sorghum) to reduce pathogen build-up in the soil.",
    "Remove and destroy infected plant debris and affected plants promptly to prevent spread of the pathogen."
  ],
  "chemical_options": [
    {
      "active_ingredient": "Carbendazim 12%+ Mancozeb 63% WP",
      "formulation": "Carbendazim 12%+ Mancozeb 63% WP",
      "dose": {
        "basis": "per_acre",
        "value_min": 1.214,
        "value_max": null,
        "unit": "g",
        "raw": "3.0"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": null,
      "phi_not_applicable": true,
      "caution": "This is a seed treatment product. Treat seeds uniformly before sowing. Wear gloves, a mask, and protective clothing during seed treatment. Do not consume treated seeds. Keep treated seeds away from children, livestock, and food items."
    },
    {
      "active_ingredient": "Carboxin37.5%+ Thiram37.5%WS",
      "formulation": "Carboxin 37.5%+ Thiram 37.5% WS",
      "dose": {
        "basis": "per_kg_seed",
        "value_min": 3,
        "value_max": null,
        "unit": "g",
        "raw": "3.0gm/Kg  seed"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": null,
      "phi_not_applicable": true,
      "caution": "This is a seed treatment product. Mix thoroughly with seeds before sowing. Wear protective gloves, mask, and eye protection during handling. Avoid inhalation of dust. Keep away from food, feed, and water sources. Do not use treated seeds for human or animal consumption."
    }
  ],
  "safety": [
    "Always wear protective gloves, a face mask, and full-sleeve clothing when handling and applying fungicides.",
    "Wash hands and exposed skin thoroughly with soap and water after seed treatment or any fungicide application.",
    "Keep all pesticide containers tightly closed and store in a locked, cool, dry place away from children and animals.",
    "Do not allow children, livestock, or poultry near treated seeds or treated fields.",
    "Dispose of empty pesticide containers safely as per local regulations — do not reuse for any purpose.",
    "These recommendations are an advisory aid only. Always read the label on the pesticide container, as the label is legally binding. Consult your local state agriculture department or a qualified agronomist for field-specific guidance."
  ],
  "escalate_to_expert": false
}
```

## S1_648 -- slice 1 (dose) -- gram
Query: `fruit borer in bengal gram`
Verdict: **accepted**
verify() score: 1.0 | passed: True | excluded: False
Fact-sheet fidelity: True

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Pod borer",
      "type": "pest",
      "confidence": 0.9,
      "evidence": "Helicoverpa armigera (gram pod borer) is the primary fruit/pod borer of Bengal gram (chickpea), causing larvae to bore into developing pods and feed on seeds, leading to significant yield loss."
    }
  ],
  "non_chemical_first": [
    "Install pheromone traps (Helicoverpa armigera lure) at 5 traps per acre to monitor adult moth activity and determine spray timing.",
    "Hand-pick and destroy egg masses and early-instar larvae from the crop during scouting rounds.",
    "Intercrop gram with coriander or fennel to attract natural enemies such as parasitic wasps that attack pod borer larvae.",
    "Set up bird perches (T-shaped sticks) at 10 per acre to encourage insectivorous birds to feed on larvae.",
    "Deep plough after harvest to expose and kill pupae in the soil."
  ],
  "chemical_options": [
    {
      "active_ingredient": "Chlorantraniliprole 18.50% SC",
      "formulation": "Chlorantraniliprole 18.50% SC",
      "dose": {
        "basis": "per_acre",
        "value_min": 50.5848,
        "value_max": null,
        "unit": "ml",
        "raw": "125"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 11,
      "phi_not_applicable": false,
      "caution": "Wear full protective clothing including gloves, mask, and goggles during mixing and spraying. Do not re-enter the field for at least 24 hours after application. Keep children and livestock away from treated areas. Do not spray near water bodies. The label on the container is legally binding."
    },
    {
      "active_ingredient": "Flubendiamide 20% WG",
      "formulation": "Flubendiamide 20% WG",
      "dose": {
        "basis": "per_acre",
        "value_min": 101.1695,
        "value_max": null,
        "unit": "g",
        "raw": "250"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 15,
      "phi_not_applicable": false,
      "caution": "Wear gloves, mask, and protective clothing during application. Observe a 15-day pre-harvest interval strictly. Avoid contact with skin and eyes. Keep people and livestock away from the field during and after spraying until spray has dried."
    },
    {
      "active_ingredient": "Emamectin benzoate 05%SG",
      "formulation": "Emamectin benzoate 05% SG",
      "dose": {
        "basis": "per_acre",
        "value_min": 89.0292,
        "value_max": null,
        "unit": "g",
        "raw": "220"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 14,
      "phi_not_applicable": false,
      "caution": "Wear protective equipment including gloves, mask, and goggles. Avoid inhalation of spray mist. Do not re-enter the field for 24 hours after application. Observe a 14-day pre-harvest interval. Keep away from water sources and do not allow run-off into ponds or streams."
    },
    {
      "active_ingredient": "Indoxacarb 14.50% SC",
      "formulation": "Indoxacarb 14.50% SC",
      "dose": {
        "basis": "per_acre",
        "value_min": 161.8712,
        "value_max": 202.339,
        "unit": "ml",
        "raw": "400-500"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 19,
      "phi_not_applicable": false,
      "caution": "Wear gloves, mask, and full protective clothing during application. Observe the 19-day pre-harvest interval. Avoid spraying during windy conditions to prevent drift. Keep children and livestock out of the treated area. Wash hands and exposed skin thoroughly after handling."
    }
  ],
  "safety": [
    "Always wear personal protective equipment (gloves, face mask or respirator, goggles, and full-sleeved clothing) during mixing and spraying of any pesticide.",
    "Do not eat, drink, or smoke while handling pesticides.",
    "Keep all children and livestock away from the field during spraying and until the spray has fully dried.",
    "Strictly observe the pre-harvest interval (PHI) for each product before harvesting pods for human or animal consumption.",
    "Wash all protective equipment and clothing thoroughly after use.",
    "Store unused pesticide in its original labelled container in a locked place away from food, feed, and water.",
    "Dispose of empty containers safely — puncture, rinse three times, and bury away from water sources; do not burn.",
    "In case of accidental poisoning, take the pesticide container to the nearest hospital immediately and seek medical help.",
    "The pesticide label on the container is legally binding and takes precedence over any advisory. Always read the label before use.",
    "Consult your local Agriculture Department or a qualified agronomist for field-specific guidance."
  ],
  "escalate_to_expert": false
}
```

## S1_792 -- slice 1 (dose) -- gram
Query: `Attack of wilt iin Gram ?`
Verdict: **accepted**
verify() score: 1.0 | passed: True | excluded: False
Fact-sheet fidelity: True

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Wilt",
      "type": "disease",
      "confidence": 0.85,
      "evidence": "Wilt in gram (chickpea) is commonly caused by Fusarium oxysporum f. sp. ciceris and/or Sclerotium rolfsii. Symptoms include sudden wilting of plants, yellowing, and browning of internal stem tissue. Seed-borne inoculum and infected soil are primary sources."
    }
  ],
  "non_chemical_first": [
    "Use certified wilt-resistant/tolerant gram varieties (e.g., JG 74, Vijay, Phule G 12181) wherever available in your region.",
    "Follow a long crop rotation (at least 2–3 years) avoiding chickpea and other legumes on the same plot to reduce soil-borne inoculum build-up.",
    "Deep summer ploughing (June–July) to expose and desiccate resting structures of the pathogen in the soil.",
    "Uproot and destroy wilt-affected plants immediately to prevent spread of the disease within the field.",
    "Avoid water-logging; ensure proper field drainage as excess soil moisture favours wilt pathogens."
  ],
  "chemical_options": [
    {
      "active_ingredient": "Tebuconazole 5.4% w/w FS",
      "formulation": "Tebuconazole 5.4% w/w FS",
      "dose": {
        "basis": "per_kg_seed",
        "value_min": 0.4,
        "value_max": null,
        "unit": "ml",
        "raw": "4.0 ml/10 Kg of  seed"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": null,
      "phi_not_applicable": true,
      "caution": "Seed dresser — applied only to seeds before sowing, not as a foliar spray. Wear gloves, a mask, and protective clothing during seed treatment. Treated seed must not be used for food or feed. Keep children and livestock away during the treatment process."
    },
    {
      "active_ingredient": "Prochloraz 5.7% + Tebuconazole 1.4% w/w ES",
      "formulation": "Prochloraz 5.7% + Tebuconazole 1.4% w/w ES",
      "dose": {
        "basis": "per_kg_seed",
        "value_min": 0.3,
        "value_max": null,
        "unit": "ml",
        "raw": "3.0 ml/10 kg  seeds"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": null,
      "phi_not_applicable": true,
      "caution": "Seed dresser — applied only to seeds before sowing, not as a foliar spray. Wear gloves, a mask, and eye protection during seed treatment. Treated seed must not be consumed by humans or animals. Store treated seed separately and label clearly."
    },
    {
      "active_ingredient": "Tebuconazole 15% + Zineb 57% WDG",
      "formulation": "Tebuconazole 15% + Zineb 57% WDG",
      "dose": {
        "basis": "per_ha",
        "value_min": 4,
        "value_max": null,
        "unit": "g",
        "raw": "4.0"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": null,
      "phi_not_applicable": true,
      "caution": "Seed dresser — for seed treatment use only, not for foliar application. Wear full protective gear including gloves, mask, and goggles. Treated seed must not be used as food or feed. Wash hands thoroughly after handling."
    }
  ],
  "safety": [
    "All three fungicide options listed here are seed dressers — apply only to seeds before sowing; do not spray onto standing crops.",
    "Wear chemical-resistant gloves, a nose/mouth mask, and protective eyewear when handling and mixing fungicide formulations for seed treatment.",
    "Avoid inhaling dust or vapour during seed treatment; perform the operation in a well-ventilated area or outdoors.",
    "Store treated seeds in a separate, clearly labelled container away from food, feed, and water sources.",
    "Keep children, livestock, and poultry away from the seed treatment area and away from treated seeds.",
    "Dispose of empty containers safely — do not reuse for food or water storage; follow state/local regulations for pesticide container disposal.",
    "The pesticide label on the container is legally binding — always read and follow label instructions before use.",
    "If disease incidence is high or spreading rapidly in the field, contact your nearest Krishi Vigyan Kendra (KVK) or District Agriculture Officer for a field inspection."
  ],
  "escalate_to_expert": false
}
```

## S2_629 -- slice 2 (clarify) -- gram
Query: `Farmer needs information regarding caterpillar attack in Bengal Gram crop ?`
Verdict: **accepted**
verify() score: 1.0 | passed: True | excluded: False

Raw response:
```json
{
  "in_scope": true,
  "query_understood": false,
  "clarifying_question": "Are the caterpillars attacking the pods and feeding on the developing seeds inside, or are they cutting the stem at ground level and toppling young plants?",
  "likely_causes": [
    {
      "name": "Gram pod borer",
      "type": "pest",
      "confidence": 0.4,
      "evidence": "Helicoverpa armigera (gram pod borer) caterpillars are the most common caterpillar pest on gram, typically boring into pods and eating developing seeds during the reproductive stage."
    },
    {
      "name": "Cutworm",
      "type": "pest",
      "confidence": 0.25,
      "evidence": "Cutworm caterpillars cut seedlings at the base near ground level, causing plants to wilt and collapse, and are more common in early vegetative stages."
    }
  ],
  "non_chemical_first": [],
  "chemical_options": [],
  "safety": [],
  "escalate_to_expert": false
}
```

## S2_630 -- slice 2 (clarify) -- onion
Query: `Farmer needs information regarding how to increase size and production in onion crop?`
Verdict: **accepted**
verify() score: 1.0 | passed: True | excluded: False

Raw response:
```json
{
  "in_scope": false,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [],
  "non_chemical_first": [],
  "chemical_options": [],
  "safety": [],
  "escalate_to_expert": false
}
```

## S2_631 -- slice 2 (clarify) -- pomegranate
Query: `ASKED ABOUT flower drop in pomogranate?`
Verdict: **accepted**
verify() score: 1.0 | passed: True | excluded: False

Raw response:
```json
{
  "in_scope": true,
  "query_understood": false,
  "clarifying_question": "When the flowers drop, do you notice tiny insects (thrips) moving inside the flower, oily water-soaked spots on the flower stalk, or do the flowers simply fall without any visible pest or lesion?",
  "likely_causes": [
    {
      "name": "Thrips",
      "type": "pest",
      "confidence": 0.35,
      "evidence": "Thrips (phulkide) feeding inside flowers is a common cause of flower drop in pomegranate; look for tiny yellowish insects rasping petals and stamens."
    },
    {
      "name": "Bacterial blight",
      "type": "disease",
      "confidence": 0.3,
      "evidence": "Bacterial blight (telya/oily spot) can cause water-soaked, oily lesions on flower stalks leading to flower and fruitlet drop."
    },
    {
      "name": "Wilt",
      "type": "disease",
      "confidence": 0.2,
      "evidence": "Wilt can cause general stress-related flower shedding, though it more typically affects branches and the whole plant progressively."
    }
  ],
  "non_chemical_first": [],
  "chemical_options": [],
  "safety": [],
  "escalate_to_expert": false
}
```

## S2_638 -- slice 2 (clarify) -- cotton
Query: `Ask about all type of pest control`
Verdict: **accepted**
verify() score: 1.0 | passed: True | excluded: False

Raw response:
```json
{
  "in_scope": true,
  "query_understood": false,
  "clarifying_question": "Could you tell me which part of the cotton plant is affected — are you seeing damaged bolls or tunneling inside bolls (suggesting bollworm), white or yellow tiny insects on the underside of leaves causing leaf curl (whitefly/jassid), or silvery streaks and distorted young leaves at the growing tip (thrips)?",
  "likely_causes": [
    {
      "name": "Pink bollworm",
      "type": "pest",
      "confidence": 0.35,
      "evidence": "Very common cotton pest in Maharashtra; damages bolls from inside, often goes unnoticed until bolls open showing rosette/stained lint."
    },
    {
      "name": "Whitefly",
      "type": "pest",
      "confidence": 0.35,
      "evidence": "Widespread sucking pest on cotton, found on leaf undersides; causes yellowing, honeydew, and sooty mould."
    },
    {
      "name": "Jassid",
      "type": "pest",
      "confidence": 0.30,
      "evidence": "Common sucking pest causing hopper burn (reddening/bronzing of leaf margins), easily confused with thrips damage on young leaves."
    }
  ],
  "non_chemical_first": [],
  "chemical_options": [],
  "safety": [],
  "escalate_to_expert": false
}
```

## S3_1638 -- slice 3 (refusal_dose) -- cotton
Query: `Ask for thrips in Cotton`
Verdict: **accepted**
verify() score: 1.0 | passed: True | excluded: False
Fact-sheet fidelity: True

Raw response:
```json
{"in_scope": true, "query_understood": true, "clarifying_question": null, "likely_causes": [{"name": "Thrips", "type": "pest", "confidence": 0.9, "evidence": "Thrips (Thrips tabaci and Frankliniella schultzei) are a major sucking pest of cotton, causing silvering, crinkling, and upward curling of leaves, especially at the growing tips and young leaves."}], "non_chemical_first": ["Use blue sticky traps (25 per acre) for monitoring and mass trapping of thrips.", "Avoid excessive nitrogen fertilisation, which promotes lush growth attractive to thrips.", "Conserve natural enemies such as predatory mites and Chrysoperla species.", "Remove and destroy severely infested plant parts.", "Maintain field hygiene by removing weeds that harbour thrips around field margins.", "Ensure adequate irrigation, as water-stressed plants are more susceptible to thrips damage."], "chemical_options": [{"active_ingredient": "Spinetoram 11.70 %SC", "formulation": "Spinetoram 11.70 %SC", "dose": {"basis": "per_acre", "value_min": 169.9648, "value_max": null, "unit": "ml", "raw": "420"}, "spray_volume_min_l_per_acre": null, "spray_volume_max_l_per_acre": null, "phi_days": 30, "phi_not_applicable": false, "caution": "Wear full protective clothing including gloves, goggles, and face mask during preparation and application. Keep people and livestock out of the treated area until the spray has dried. Do not spray near water bodies."}, {"active_ingredient": "Cyantraniliprole 10.26% OD", "formulation": "Cyantraniliprole 10.26% OD", "dose": {"basis": "per_acre", "value_min": 364.2103, "value_max": null, "unit": "ml", "raw": "900"}, "spray_volume_min_l_per_acre": null, "spray_volume_max_l_per_acre": null, "phi_days": 7, "phi_not_applicable": false, "caution": "Wear gloves, goggles, and a mask during mixing and spraying. Observe the 7-day PHI strictly before harvest. Avoid contact with skin and eyes."}, {"active_ingredient": "Flonicamid 50%WG", "formulation": "Flonicamid 50%WG", "dose": {"basis": "per_acre", "value_min": 60.7017, "value_max": null, "unit": "g", "raw": "150"}, "spray_volume_min_l_per_acre": null, "spray_volume_max_l_per_acre": null, "phi_days": 25, "phi_not_applicable": false, "caution": "Wear protective gloves, mask, and goggles during application. Keep children and livestock away from the treated field. Store unused material away from food and feed."}, {"active_ingredient": "Thiamethoxam 25%WG", "formulation": "Thiamethoxam 25%WG", "dose": {"basis": "per_acre", "value_min": 40.4678, "value_max": null, "unit": "g", "raw": "100"}, "spray_volume_min_l_per_acre": null, "spray_volume_max_l_per_acre": null, "phi_days": 21, "phi_not_applicable": false, "caution": "Highly toxic to bees; do not spray during flowering or when bees are foraging. Wear full protective equipment. Observe re-entry restrictions until spray residues have dried. Dispose of empty containers safely."}], "safety": ["IMPORTANT — Monocrotophos 36% SL is a RESTRICTED chemical. Its registration certificates have been cancelled under Government of India Gazette Notification S.O. 4294(E) dated 03 October 2023. This chemical must NOT be purchased, used, or stored for crop protection purposes. Possession or use of this cancelled product may attract legal liability under the Insecticides Act, 1968. Please dispose of any existing stock through authorised channels and consult your local agriculture officer immediately.", "Wear full personal protective equipment (PPE) — long-sleeved shirt, trousers, gloves, goggles, and a nose-and-mouth mask — whenever handling or applying any pesticide.", "Keep all people, children, and livestock away from the field during spraying and until re-entry is safe (spray residues have dried and the label re-entry interval has elapsed).", "Do not eat, drink, or smoke during pesticide handling.", "Wash hands, face, and exposed skin thoroughly with soap and water after handling pesticides.", "Store all pesticides in their original labelled containers, out of reach of children, and away from food, feed, and water sources.", "In case of accidental exposure or poisoning, contact the nearest hospital immediately and take the pesticide label for reference.", "The pesticide label on the container is a legally binding document — always read and follow it before use.", "This advisory is an aid only. Consult your local Krishi Vigyan Kendra (KVK), State Agriculture Department extension officer, or a qualified agronomist for field-specific guidance."], "escalate_to_expert": true}
```

## S3_1118 -- slice 3 (refusal_clarify) -- cotton
Query: `does emamectin benzoate, copper oxy chloride, monocrotophos can spray at a time`
Verdict: **accepted**
verify() score: 1.0 | passed: True | excluded: False

Raw response:
```json
{
  "in_scope": true,
  "query_understood": false,
  "clarifying_question": "To advise you correctly on what to spray on your cotton crop, could you please tell me which plant part is affected and what symptoms you are seeing — for example, are you noticing leaf curling or yellowing (possible Jassid/Whitefly), silver streaks on leaves or buds (Thrips), holes in bolls with pink larvae inside (Pink bollworm), or water-soaked oily spots on leaves (Bacterial blight)?",
  "likely_causes": [],
  "non_chemical_first": [],
  "chemical_options": [],
  "safety": [
    "IMPORTANT — Monocrotophos 36% SL: The Central Government via S.O. 4294(E) dated 03 October 2023 has cancelled all registration certificates for Monocrotophos 36% SL. No new registrations are being issued, and all existing certificates were cancelled effective 03 October 2024. Stocks remaining from before the cancellation may only be sold until the label expiry date. Farmers should NOT purchase or use Monocrotophos 36% SL going forward. Please consult your local agriculture department or a registered pesticide dealer for currently legal alternatives.",
    "Do not mix or apply any combination of pesticides (including Emamectin Benzoate and Copper Oxychloride) without first confirming the specific pest or disease target and verifying compatibility — incompatible tank-mixes can cause crop phytotoxicity or chemical breakdown.",
    "An expert or local agriculture officer should be consulted before any spray decision, especially given the restricted status of one of the named chemicals."
  ],
  "escalate_to_expert": true
}
```

## S4_smoke_grape0 -- slice 4 (dose) -- grape
Query: `FARMER ASKED ABOUT WHITE POWDERY GROWTH ON GRAPE LEAVES AND BUNCHES AT BERRY STAGE`
Verdict: **accepted**
verify() score: 1.0 | passed: True | excluded: False
Fact-sheet fidelity: True

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Powdery mildew",
      "type": "disease",
      "confidence": 0.95,
      "evidence": "White powdery fungal growth on grape leaves and berry bunches is the classic symptom of Erysiphe necator (grape powdery mildew), especially prevalent during berry development stage."
    }
  ],
  "non_chemical_first": [
    "Remove and destroy all infected leaves, shoots, and berry clusters showing powdery growth to reduce the primary inoculum source in the vineyard.",
    "Improve air circulation by pruning for open canopy management — avoid dense foliage, train shoots properly, and remove excess lateral growth so that humidity within the canopy is reduced.",
    "Avoid overhead irrigation during the cropping season; drip irrigation is preferred as wet foliage promotes fungal sporulation.",
    "Monitor the vineyard regularly from bud burst stage onwards and take up protective fungicide sprays before the disease establishes, especially in cool humid weather."
  ],
  "chemical_options": [
    {
      "active_ingredient": "Myclobutanil 10% WP",
      "formulation": "Myclobutanil 10% WP",
      "dose": {
        "basis": "concentration_pct",
        "value_min": 0.04,
        "value_max": null,
        "unit": "%",
        "raw": "0.04%"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 15,
      "phi_not_applicable": false,
      "caution": "Wear full-sleeved clothing, gloves, and a face mask during mixing and spraying. Do not spray within 15 days of harvest. Keep children, livestock, and bystanders away from the treated area during and after spraying."
    },
    {
      "active_ingredient": "Cyflufenamid 5% EW",
      "formulation": "Cyflufenamid 5% EW",
      "dose": {
        "basis": "per_acre",
        "value_min": 202.339,
        "value_max": null,
        "unit": "ml",
        "raw": "500"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 25,
      "phi_not_applicable": false,
      "caution": "Wear protective gloves, goggles, and a mask during application. Do not apply within 25 days before harvest. Avoid spraying in windy conditions to prevent drift onto adjacent crops or water bodies."
    },
    {
      "active_ingredient": "Hexaconazole 5% EC",
      "formulation": "Hexaconazole 5% EC",
      "dose": {
        "basis": "per_acre",
        "value_min": 202.339,
        "value_max": 404.6781,
        "unit": "ml",
        "raw": "500-1000ml"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 14,
      "phi_not_applicable": false,
      "caution": "Wear gloves, protective clothing, and a mask during application. Do not harvest grapes within 14 days of the last spray. Wash hands and exposed skin thoroughly after use. Keep livestock away from treated vines."
    },
    {
      "active_ingredient": "Difenoconazole 25% EC",
      "formulation": "Difenoconazole 25% EC",
      "dose": {
        "basis": "concentration_pct",
        "value_min": 0.03,
        "value_max": null,
        "unit": "%",
        "raw": "0.03% or  30ml/100 ltr. of  water"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 10,
      "phi_not_applicable": false,
      "caution": "Wear gloves, face shield, and protective clothing during preparation and application. Do not apply within 10 days of harvest. Avoid contamination of water sources. The pesticide label on the container is legally binding — always read and follow it."
    }
  ],
  "safety": [
    "Always wear personal protective equipment — gloves, full-sleeved clothing, goggles or face shield, and an appropriate nose-mouth mask — when mixing and spraying any fungicide.",
    "Keep all children, farm workers not involved in spraying, and livestock away from the treated vineyard during application and until sprays have dried completely.",
    "Observe the pre-harvest interval (PHI) strictly for each product used; do not harvest berries before the specified number of days after the last spray.",
    "Do not eat, drink, or smoke during application. Wash hands, face, and any exposed body parts with soap and water immediately after use.",
    "Dispose of empty pesticide containers safely — do not reuse them for storing food, water, or fodder. Puncture and bury or return to the dealer as per local regulations.",
    "Rotate fungicide groups to delay resistance development; do not apply the same mode-of-action product consecutively.",
    "This advisory is a guide only. The pesticide label on the container is legally binding. Consult your local agriculture department or a qualified agronomist for field-specific decisions."
  ],
  "escalate_to_expert": false
}
```

## S4_smoke_grape1 -- slice 4 (dose) -- grape
Query: `Farmer asked about mealy bug infestation on grape vine, cottony white insects on stem and bunches`
Verdict: **excluded: ambiguous ground truth: C1_dose, C2_phi — the CIB&RC rows this answer could refer to disagree**
verify() score: 1.0 | passed: False | excluded: True
Failures:
- AMBIGUOUS: 'Thiamethoxam 25%WG' dose 161.8712g matches some but not all of the CIB&RC rows it could refer to (161.8712 g ('400'); 40.4678 g ('100')) — ground truth cannot grade it
- AMBIGUOUS: 'Thiamethoxam 25%WG' pre-harvest interval 10 matches some but not all of the CIB&RC rows it could refer to (they state 10/15 days) — ground truth cannot grade it
Fact-sheet fidelity: None

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Mealybug",
      "type": "pest",
      "confidence": 0.95,
      "evidence": "Cottony white waxy masses on stems and bunches are characteristic of mealybug (Maconellicoccus hirsutus and Planococcus ficus) infestation on grapevine. Colonies excrete honeydew, promoting sooty mould."
    }
  ],
  "non_chemical_first": [
    "Prune and destroy heavily infested shoots, canes, and bunches; remove bark and debris from the trunk where mealybugs shelter during dormancy.",
    "Apply a sticky band (adhesive trap) around the trunk base to prevent ant movement up the vine, as ants protect mealybugs from natural enemies.",
    "Release predatory beetles (Cryptolaemus montrouzieri) at 10 beetles per vine at the start of infestation — a registered biological control agent for grape mealybug in India.",
    "Rogue out severely affected vines that serve as persistent pest sources and replace with certified, pest-free planting material."
  ],
  "chemical_options": [
    {
      "active_ingredient": "Buprofezin 25% SC",
      "formulation": "Buprofezin 25% SC",
      "dose": {
        "basis": "per_acre",
        "value_min": 404.6781,
        "value_max": 607.0171,
        "unit": "ml",
        "raw": "1000 –  1500"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 7,
      "phi_not_applicable": false,
      "caution": "Buprofezin is an insect growth regulator; ensure thorough coverage of stems and bunches to reach crawlers under waxy coating. Do not apply more than twice per season to delay resistance. Wear gloves, mask, and full-sleeve clothing during mixing and spraying."
    },
    {
      "active_ingredient": "Spirotetramat 15.31%w/w OD",
      "formulation": "Spirotetramat 15.31%w/w OD",
      "dose": {
        "basis": "per_acre",
        "value_min": 283.2747,
        "value_max": null,
        "unit": "ml",
        "raw": "700"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 60,
      "phi_not_applicable": false,
      "caution": "PHI is 60 days — do NOT apply within 60 days of expected harvest. Spirotetramat has systemic/translaminar action and disrupts lipid biosynthesis in nymphs; add a non-ionic surfactant for better penetration of the wax layer. Wear PPE including goggles and protective clothing."
    },
    {
      "active_ingredient": "Spirotetramat 11.01%+ Imidacloprid 11.01%w/w SC",
      "formulation": "Spirotetramat 11.01%+ Imidacloprid 11.01%w/w SC",
      "dose": {
        "basis": "per_acre",
        "value_min": 303.5086,
        "value_max": null,
        "unit": "ml",
        "raw": "750"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 60,
      "phi_not_applicable": false,
      "caution": "PHI is 60 days — do NOT apply within 60 days of harvest. This combination product provides both systemic and contact action. Avoid application during flowering to protect pollinators. Wear full PPE including gloves, mask, and goggles."
    },
    {
      "active_ingredient": "Thiamethoxam 25%WG",
      "formulation": "Thiamethoxam 25%WG",
      "dose": {
        "basis": "per_acre",
        "value_min": 161.8712,
        "value_max": null,
        "unit": "g",
        "raw": "400"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 10,
      "phi_not_applicable": false,
      "caution": "This entry is for soil drench application only — apply as a drenching solution around the root zone for systemic uptake. PHI is 10 days. Avoid contact with skin and eyes; wear gloves and protective clothing. Keep children and livestock away from treated area."
    }
  ],
  "safety": [
    "Always wear chemical-resistant gloves, full-sleeve shirt, long trousers, closed-toe shoes, and a face mask/respirator when preparing and spraying pesticides.",
    "Do not eat, drink, or smoke during handling. Wash hands and face thoroughly with soap and water after each application.",
    "Keep all workers and livestock out of the treated vineyard for a minimum of 24–48 hours after spraying, or as directed on the product label.",
    "Strictly observe the pre-harvest interval (PHI) — 7 days for Buprofezin, 10 days for Thiamethoxam (soil drench), and 60 days for both Spirotetramat and Spirotetramat + Imidacloprid — before picking any grapes.",
    "Store pesticides in original sealed containers, in a locked, cool, and dry place, away from food, feed, and water sources. Dispose of empty containers safely as per label instructions.",
    "The pesticide label on the container is legally binding under the Insecticides Act, 1968 — always read and follow it. This advisory does not replace guidance from your state agriculture department or a licensed agronomist."
  ],
  "escalate_to_expert": false
}
```

## S5_693 -- slice 5 (nochem) -- onion
Query: `Farmer want to know information about  how to control of root rot attack  in Onion crop ?`
Verdict: **rejected: C5: top cause 'Root Rot (Fusarium basal rot / Pythium spp. / Sclerotium rolfsii)'; the query was about 'root rot'**
verify() score: 0.714286 | passed: False | excluded: False
Failures:
- C5: top cause 'Root Rot (Fusarium basal rot / Pythium spp. / Sclerotium rolfsii)'; the query was about 'root rot'

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Root Rot (Fusarium basal rot / Pythium spp. / Sclerotium rolfsii)",
      "type": "disease",
      "confidence": 0.75,
      "evidence": "Root rot in onion is commonly caused by soilborne fungi such as Fusarium oxysporum f. sp. cepae, Pythium spp., or Sclerotium rolfsii. Symptoms include browning and decay of roots, yellowing of leaves, wilting, and easy pull-out of plants from soil. Waterlogged or poorly drained soils and high soil moisture favour disease onset."
    }
  ],
  "non_chemical_first": [
    "Use only certified disease-free seed and healthy transplants from a reliable source to reduce the initial inoculum load.",
    "Maintain proper field drainage by raising beds or ridges; avoid waterlogging since saturated soils strongly favour root rot pathogens.",
    "Follow a crop rotation of at least 3–4 years with non-allium crops (e.g., cereals or legumes) to reduce soilborne fungal inoculum.",
    "Deep summer ploughing (May–June) exposes soilborne pathogens and sclerotia to solar heat, reducing their survival.",
    "Incorporate well-composted farmyard manure (FYM) to improve soil structure and drainage, and to promote beneficial soil microbiota.",
    "Apply Trichoderma harzianum or Trichoderma viride (bio-control agents) to the soil at 2.5 kg per acre mixed with 50 kg FYM and incorporated before planting to suppress soilborne root rot fungi.",
    "Avoid excess irrigation; use drip irrigation wherever possible and irrigate only when needed to keep soil moisture at optimal levels.",
    "Uproot and destroy (burn or deep-bury away from the field) all infected plants promptly to prevent further spread of the pathogen.",
    "Avoid injury to roots and bulbs during transplanting and weeding operations, as wounds are entry points for pathogens.",
    "Maintain balanced soil nutrition; avoid excess nitrogen fertilisation, which can reduce root integrity and increase susceptibility."
  ],
  "chemical_options": [],
  "safety": [
    "When handling Trichoderma-based bio-agents, wear gloves and a face mask to avoid inhalation of spore dust.",
    "Keep children and livestock away from fields immediately after any soil application of bio-control agents or amendments.",
    "Do not mix Trichoderma bio-agents with chemical fungicides or chemical fertilisers at the time of application, as this can kill the beneficial organisms.",
    "Always read and follow the label instructions on any registered product before use; the label on the container is legally binding under the Insecticides Act, 1968.",
    "Wash hands and exposed skin thoroughly with soap and water after field operations."
  ],
  "escalate_to_expert": true
}
```

## S5_745 -- slice 5 (nochem) -- tur
Query: `root grub management in red gram`
Verdict: **rejected: C5: top cause 'White grub / Root grub (Holotrichia spp. / Leucopholis spp.)'; the query was about 'root grub'**
verify() score: 0.714286 | passed: False | excluded: False
Failures:
- C5: top cause 'White grub / Root grub (Holotrichia spp. / Leucopholis spp.)'; the query was about 'root grub'

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "White grub / Root grub (Holotrichia spp. / Leucopholis spp.)",
      "type": "pest",
      "confidence": 0.85,
      "evidence": "Root grub (white grub) larvae feed on roots of tur (red gram), causing wilting and plant death, especially in sandy loam soils during kharif season after monsoon onset."
    }
  ],
  "non_chemical_first": [
    "Deep summer ploughing (May–June) before sowing to expose pupae and grubs to sun heat and predatory birds, reducing soil population significantly.",
    "Collect and destroy adult beetles during evening hours by hand-picking or light traps, especially during peak emergence in early monsoon (June–July), to reduce egg-laying population.",
    "Encourage natural predators by placing perches in the field for insectivorous birds (e.g., mynas, crows) that feed on exposed grubs during tillage operations.",
    "Avoid applying undecomposed farmyard manure, which attracts egg-laying adult beetles; use only well-composted manure.",
    "Apply Metarhizium anisopliae or Beauveria bassiana-based bioagent formulations (if locally available and certified) as soil treatment at planting, following the supplier's label instructions, to achieve biological control of grub larvae.",
    "Maintain field sanitation by removing weeds and crop debris that serve as alternative hosts or refuges for adult beetles.",
    "If severe infestation is detected early, rogue out and destroy wilting plants to prevent further larval spread within the field."
  ],
  "chemical_options": [],
  "safety": [
    "When applying any biological agents, wear gloves and a face mask to avoid inhalation or skin contact with microbial spores.",
    "Keep children and livestock away from the field during and immediately after any soil treatment operation.",
    "Wash hands and exposed skin thoroughly with soap and water after handling any biological or chemical inputs.",
    "Store all plant protection products in their original labelled containers, out of reach of children and away from food and feed."
  ],
  "escalate_to_expert": true
}
```

## S2_661 -- slice 2 (offtopic) -- tomato
Query: `Farmer asked about average yield of Tomato crop`
Verdict: **accepted**
verify() score: 1.0 | passed: True | excluded: False

Raw response:
```json
{
  "in_scope": false,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [],
  "non_chemical_first": [],
  "chemical_options": [],
  "safety": [
    "This advisory service covers only pest and disease management on eight crops: cotton, soybean, tur (pigeonpea), gram (chickpea), onion, tomato, grape, and pomegranate. For questions about crop yield, variety selection, fertilizer, irrigation, or market prices, please contact your local Krishi Vigyan Kendra or the Maharashtra State Agriculture Department."
  ],
  "escalate_to_expert": false
}
```

## S2_665 -- slice 2 (offtopic) -- gram
Query: `Farmer asked average yield and duration details in Bengal gram crop`
Verdict: **accepted**
verify() score: 1.0 | passed: True | excluded: False

Raw response:
```json
{
  "in_scope": false,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [],
  "non_chemical_first": [],
  "chemical_options": [],
  "safety": [
    "This advisory service covers only pest and disease management on eight crops — cotton, soybean, tur (pigeonpea), gram (chickpea), onion, tomato, grape, and pomegranate. For yield estimates, crop duration, variety selection, fertilizer, irrigation, or other agronomic questions on Bengal gram, please contact your local Krishi Vigyan Kendra (KVK) or the Maharashtra State Agriculture Department."
  ],
  "escalate_to_expert": false
}
```

## Aggregate
- Accepted: 15 / 20 (75%)
- Slice 1 acceptance: 6 / 8 (75%)
- Gate/check failures by name:
  - C5: 4
