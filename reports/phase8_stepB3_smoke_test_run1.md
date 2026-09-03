# Phase 8 Sub-phase B3 -- live smoke test
Model: `claude-sonnet-4-6` via Anthropic Batch API, single batch, no retries (max_attempts=1). 20 items across all 5 slices plus OFFTOPIC.

## S1_637 -- slice 1 (dose) -- cotton
Query: `APHIDS MANAGEMENT IN COTTON`
Verdict: **rejected: C5: top cause 'Aphid (Aphis gossypii / Aphididae)'; the query was about 'Aphids', which CIB&RC prints as ['Aphids', 'Jassids', 'Jassid']**
verify() score: 0.9 | passed: False | excluded: False
Failures:
- C5: top cause 'Aphid (Aphis gossypii / Aphididae)'; the query was about 'Aphids', which CIB&RC prints as ['Aphids', 'Jassids', 'Jassid']
Fact-sheet fidelity: None

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Aphid (Aphis gossypii / Aphididae)",
      "type": "pest",
      "confidence": 0.95,
      "evidence": "Query explicitly states aphid management on cotton, a common sucking pest on cotton causing leaf curl, honeydew secretion, and sooty mould."
    }
  ],
  "non_chemical_first": [
    "Monitor fields regularly (at least twice a week) using yellow sticky traps to detect early aphid build-up and act before populations exceed economic threshold.",
    "Conserve and encourage natural enemies such as ladybird beetles (Coccinella spp.), lacewings (Chrysoperla spp.), and parasitic wasps (Lysiphlebus spp.) by avoiding broad-spectrum insecticides early in the season.",
    "Avoid excessive nitrogen fertilisation, which promotes soft, succulent growth that attracts and sustains aphid populations.",
    "Use reflective silver/aluminium mulches between rows to repel winged aphids (alate forms) and reduce colonisation in the early crop stage.",
    "Remove and destroy heavily infested shoot tips and leaves to reduce local aphid colonies before spraying becomes necessary."
  ],
  "chemical_options": [
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
      "caution": "Flonicamid is a selective feeding blocker with low mammalian toxicity; wear gloves, mask, and protective clothing during mixing and spraying. Do not apply within 25 days of harvest. Keep children and livestock out of treated fields during and after application until spray has dried."
    },
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
      "caution": "Neonicotinoid — rotate with non-neonicotinoid chemistries to prevent resistance development in aphid populations. Wear full PPE (gloves, mask, goggles). Avoid spraying during flowering hours to protect pollinators. Observe 15-day PHI before harvest."
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
      "caution": "Spirotetramat is a lipid-biosynthesis inhibitor effective against all mobile aphid stages including eggs; ensure thorough coverage of leaf undersides. Wear gloves and mask. Observe strict 52-day PHI before harvest. Store away from food, feed, and water sources."
    },
    {
      "active_ingredient": "Flonicamid 18% + Spirotetramat 13.5% w/w SC",
      "formulation": "Flonicamid 18% + Spirotetramat 13.5% w/w SC",
      "dose": {
        "basis": "per_acre",
        "value_min": 222.5729,
        "value_max": null,
        "unit": "ml",
        "raw": "550"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 86,
      "phi_not_applicable": false,
      "caution": "Combination product with a very long PHI of 86 days — use only in early-to-mid crop stages well before boll development approaches harvest. Wear full PPE. Do not allow spray drift onto neighbouring crops or water bodies. Keep livestock out of the field for at least 48 hours after application."
    }
  ],
  "safety": [
    "Always read the label on the pesticide container before use — the label is legally binding and overrides any advisory.",
    "Wear personal protective equipment (PPE): chemical-resistant gloves, full-sleeved clothing, a face mask or respirator, and eye protection during mixing and spraying.",
    "Do not spray against the wind; spray early morning or late evening to minimise drift, heat stress, and exposure to beneficial insects.",
    "Re-entry interval: do not allow farm workers or family members to enter the treated field until the spray has completely dried (minimum 4–6 hours); for organophosphate- or neonicotinoid-containing products follow the label re-entry interval.",
    "Keep all livestock, poultry, and domestic animals out of the treated area during spraying and until residues have dried.",
    "Do not eat, drink, or smoke while handling pesticides. Wash hands and face with soap and water immediately after application.",
    "Strictly observe the pre-harvest interval (PHI) stated for each product — do not harvest cotton bolls before the PHI has elapsed.",
    "Dispose of empty pesticide containers safely; do not reuse them for food, water, or feed storage. Triple-rinse containers before puncturing and burying at an approved disposal site.",
    "In case of accidental poisoning, contact the nearest hospital or Poison Control Centre immediately; carry the product label for reference."
  ],
  "escalate_to_expert": false
}
```

## S1_663 -- slice 1 (dose) -- cotton
Query: `Ask about sucking pests problem in cotton crop ( Jassid, Aphid, White Flies)`
Verdict: **rejected: C5: top cause 'Jassid (Amrasca biguttula biguttula)'; the query was about 'White flies', which CIB&RC prints as ['Whiteflies', 'Jassid', 'Aphids']**
verify() score: 0.9 | passed: False | excluded: False
Failures:
- C5: top cause 'Jassid (Amrasca biguttula biguttula)'; the query was about 'White flies', which CIB&RC prints as ['Whiteflies', 'Jassid', 'Aphids']
Fact-sheet fidelity: None

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Jassid (Amrasca biguttula biguttula)",
      "type": "pest",
      "confidence": 0.95,
      "evidence": "Classic sucking pest of cotton; causes leaf curling, yellowing and hopper burn; common in Maharashtra cotton fields."
    },
    {
      "name": "Aphid (Aphis gossypii)",
      "type": "pest",
      "confidence": 0.95,
      "evidence": "Colonies on undersides of leaves and tender shoots; cause leaf curl, stunting and honeydew-sooty mould; widespread in Maharashtra cotton."
    },
    {
      "name": "Whitefly (Bemisia tabaci)",
      "type": "pest",
      "confidence": 0.95,
      "evidence": "Adults and nymphs on leaf underside; cause direct feeding damage and transmit cotton leaf curl virus; a major sucking pest in Maharashtra cotton."
    }
  ],
  "non_chemical_first": [
    "Install yellow sticky traps at a rate of 10–15 traps per acre to monitor and mass-trap whitefly and aphid adults; inspect traps weekly and replace when full.",
    "Remove and destroy heavily infested leaves, shoot tips, and volunteer cotton plants to reduce pest build-up and cut off whitefly/aphid colonies before they establish.",
    "Avoid excessive use of nitrogenous fertilisers, which promotes lush vegetative growth that favours sucking pest populations.",
    "Conserve natural enemies such as Chrysoperla, coccinellid beetles, and parasitoid wasps by avoiding broad-spectrum insecticide sprays early in the season.",
    "Adopt recommended plant spacing to improve canopy aeration and reduce microclimate conditions favourable to whitefly and aphid multiplication."
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
      "caution": "Neonicotinoid; wear full-sleeve clothing, gloves, and a mask during mixing and application. Do not spray near flowering crops or water bodies to protect pollinators and aquatic organisms. Re-entry interval: 24 hours. Keep people and livestock away from treated field for at least 24 hours."
    },
    {
      "active_ingredient": "Flonicamid 50%WG",
      "formulation": "Flonicamid 50%WG",
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
      "caution": "Selective aphicide and whitefly-active compound. Wear gloves, mask, and protective eyewear during mixing and spraying. Avoid inhalation of spray mist. Re-entry interval: 24 hours. Do not allow children or livestock near the field until spray has dried."
    },
    {
      "active_ingredient": "Diafenthiuron 47.80%SC",
      "formulation": "Diafenthiuron 47.80%SC",
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
      "caution": "Effective against jassid, aphid, and whitefly. Wear protective clothing, gloves, and a mask during application. Avoid breathing spray vapour. Do not spray in windy conditions. Re-entry interval: 24 hours. Keep people and livestock away from treated area."
    },
    {
      "active_ingredient": "Buprofezin 70%DF",
      "formulation": "Buprofezin 70%DF",
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
      "caution": "Insect growth regulator; particularly effective against whitefly nymphs and jassid nymphs. Wear gloves, mask, and eye protection during handling. Avoid contamination of water sources. Re-entry interval: 24 hours. Rotate with a different mode-of-action insecticide to prevent resistance build-up."
    }
  ],
  "safety": [
    "Always read and follow the pesticide label on the container — the label is legally binding and overrides any general advice.",
    "Wear full-sleeve protective clothing, chemical-resistant gloves, a face mask or respirator, and protective eyewear during mixing and spraying.",
    "Never eat, drink, or smoke while handling pesticides.",
    "Mix and apply pesticides in a well-ventilated area; avoid spraying during strong winds to prevent drift onto adjacent crops, water bodies, or human habitations.",
    "Keep all people, children, and livestock out of the treated field during spraying and until the spray has fully dried (minimum 24 hours).",
    "Do not harvest or consume the crop before the pre-harvest interval (PHI) for the chosen product has elapsed after the last spray.",
    "Dispose of empty pesticide containers safely as per label instructions — do not reuse them for any purpose.",
    "In case of accidental skin or eye contact, flush immediately with large amounts of clean water and seek medical attention; carry the product label to the doctor.",
    "Store pesticides in original, tightly closed containers, locked away from food, feed, and out of reach of children and animals."
  ],
  "escalate_to_expert": false
}
```

## S1_668 -- slice 1 (dose) -- tomato
Query: `ASKED ABOUT LEAF MINOR ATTACK ON TOMATO?`
Verdict: **rejected: C5: top cause 'Leaf Miner (Liriomyza trifolii / Tuta absoluta)'; the query was about 'leaf minor', which CIB&RC prints as ['Red spider mites', 'Leaf Miner', 'Fruit borer']**
verify() score: 0.888889 | passed: False | excluded: False
Failures:
- C5: top cause 'Leaf Miner (Liriomyza trifolii / Tuta absoluta)'; the query was about 'leaf minor', which CIB&RC prints as ['Red spider mites', 'Leaf Miner', 'Fruit borer']
Fact-sheet fidelity: None

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Leaf Miner (Liriomyza trifolii / Tuta absoluta)",
      "type": "pest",
      "confidence": 0.88,
      "evidence": "Leaf miner is a common and economically important pest on tomato in Maharashtra; larvae mine between leaf surfaces creating characteristic winding or blotch-shaped tunnels visible on leaves."
    }
  ],
  "non_chemical_first": [
    "Install yellow sticky traps (at least 10 traps per acre) at crop canopy level to monitor and mass-trap adult leaf miner flies.",
    "Physically remove and destroy heavily mined leaves by collecting them in a bag and burying or burning them away from the field to reduce larval population.",
    "Encourage natural enemies such as parasitic wasps (Diglyphus spp.) by avoiding broad-spectrum insecticides and preserving field margins with flowering plants.",
    "Practice crop rotation with non-host crops (e.g., cereals) to break the pest cycle and reduce soil-pupae populations in subsequent seasons."
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
      "caution": "Abamectin is toxic to bees and beneficial insects; avoid spraying during flowering or when bees are active. Wear full-sleeved protective clothing, gloves, and a face mask during mixing and spraying. Do not re-enter the treated field for at least 12 hours after application."
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
      "caution": "Spinetoram can be toxic to bees; do not spray on open flowers. Wear protective gloves, goggles, and a mask during application. Keep livestock and children away from treated fields until the spray has dried."
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
      "caution": "Rotate with chemicals of a different mode of action to prevent resistance development. Wear protective clothing, gloves, and a mask during preparation and application. Do not allow spray drift onto neighbouring crops or water bodies."
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
      "caution": "This combination product contains Abamectin, which is highly toxic to bees and aquatic organisms; keep spray away from water sources and beehives. Use full personal protective equipment including gloves, mask, and goggles. Observe a 5-day pre-harvest interval strictly before picking fruits for consumption or sale."
    }
  ],
  "safety": [
    "Always wear full-sleeved protective clothing, chemical-resistant gloves, a face mask or respirator, and goggles when handling and applying any of these insecticides.",
    "Keep all children, elderly persons, and livestock away from the field during spraying and until the spray deposit has dried completely.",
    "Do not eat, drink, or smoke while handling pesticides; wash hands and face thoroughly with soap and water after application.",
    "Strictly observe the pre-harvest interval (PHI) listed for each product before harvesting tomatoes for consumption or sale.",
    "Store pesticides in their original labelled containers in a locked, well-ventilated store away from food, feed, and water sources.",
    "Dispose of empty pesticide containers safely by triple-rinsing and puncturing them; never reuse containers for food or water storage.",
    "The pesticide label on the container is legally binding under the Insecticides Act, 1968 — always read and follow it before use.",
    "If accidental poisoning is suspected, contact the nearest hospital immediately and carry the product label or container for reference."
  ],
  "escalate_to_expert": false
}
```

## S1_744 -- slice 1 (dose) -- tomato
Query: `Leaf spot disease    Initially circular black spots on leaves, coalesce and burnt symptoms.in Tomato`
Verdict: **rejected: C5: top cause 'Early Blight (Alternaria solani)'; the query was about 'Leaf spot', which CIB&RC prints as ['Leaf spot', 'Late blight', 'Buckeye rot']**
verify() score: 0.888889 | passed: False | excluded: False
Failures:
- C5: top cause 'Early Blight (Alternaria solani)'; the query was about 'Leaf spot', which CIB&RC prints as ['Leaf spot', 'Late blight', 'Buckeye rot']
Fact-sheet fidelity: None

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Early Blight (Alternaria solani)",
      "type": "disease",
      "confidence": 0.85,
      "evidence": "Circular to irregular black/dark brown spots on leaves that coalesce and cause blighted, burnt appearance are characteristic of Alternaria early blight on tomato."
    },
    {
      "name": "Septoria Leaf Spot (Septoria lycopersici)",
      "type": "disease",
      "confidence": 0.65,
      "evidence": "Small circular dark-bordered spots that can coalesce and cause leaf scorch are also consistent with Septoria leaf spot on tomato."
    }
  ],
  "non_chemical_first": [
    "Remove and destroy infected leaves and plant debris immediately to reduce primary inoculum source; do not compost infected material.",
    "Avoid overhead irrigation; use drip or furrow irrigation to keep foliage dry and reduce leaf wetness duration that favours fungal infection.",
    "Maintain adequate plant spacing to improve air circulation within the canopy, reducing humidity and slowing disease spread.",
    "Practice crop rotation with non-solanaceous crops for at least 2–3 years to reduce soilborne inoculum levels."
  ],
  "chemical_options": [
    {
      "active_ingredient": "Captan 70%+ Hexaconazole 5%WP",
      "formulation": "Captan 70% + Hexaconazole 5% WP",
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
      "caution": "Wear full-sleeved clothing, gloves, mask, and eye protection during mixing and application. Do not spray within 7 days of harvest. Re-entry interval: 24 hours after spray."
    },
    {
      "active_ingredient": "Thiophanate methyl 15% (w/w) + Copper Oxychloride 40%(w/w) WP",
      "formulation": "Thiophanate methyl 15% (w/w) + Copper Oxychloride 40% (w/w) WP",
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
      "caution": "Wear protective gloves, mask, and eye protection. Avoid inhaling spray mist. Do not harvest within 7 days of last application. Keep children and livestock away from treated area."
    }
  ],
  "safety": [
    "Always wear gloves, a face mask, protective eyewear, and full-sleeved clothing when handling and applying fungicides.",
    "Do not eat, drink, or smoke during pesticide application.",
    "Keep all people and livestock away from the treated field during and immediately after spraying.",
    "Observe the pre-harvest interval (PHI) of 7 days for both recommended products — do not harvest tomatoes within 7 days of the last spray.",
    "Wash hands, face, and exposed skin thoroughly with soap and water after application.",
    "Store unused pesticides in original labelled containers, locked away from food, feed, and water sources.",
    "Dispose of empty containers safely as per local regulations — do not reuse them.",
    "The pesticide label on the container is legally binding; always read and follow label instructions."
  ],
  "escalate_to_expert": false
}
```

## S1_721 -- slice 1 (dose) -- soybean
Query: `Farmer wants to know information about how to control defoliators and girdle beetle in soybean?`
Verdict: **rejected: C5: top cause 'Defoliators (Spodoptera litura, Helicoverpa armigera, semi-loopers)'; the query was about 'girdle beetle', which CIB&RC prints as ['Whitefly', 'girdle beetle', 'semi looper']**
verify() score: 0.888889 | passed: False | excluded: False
Failures:
- C5: top cause 'Defoliators (Spodoptera litura, Helicoverpa armigera, semi-loopers)'; the query was about 'girdle beetle', which CIB&RC prints as ['Whitefly', 'girdle beetle', 'semi looper']
Fact-sheet fidelity: None

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Defoliators (Spodoptera litura, Helicoverpa armigera, semi-loopers)",
      "type": "pest",
      "confidence": 0.9,
      "evidence": "Defoliators are among the most common and damaging pests of soybean in Maharashtra, causing characteristic leaf feeding, skeletonization, and complete defoliation under heavy pressure."
    },
    {
      "name": "Girdle Beetle (Obereopsis brevis)",
      "type": "pest",
      "confidence": 0.9,
      "evidence": "Girdle beetle is a key soybean pest in Maharashtra where the female girdles the stem to lay eggs, causing wilting and drying of the affected stem portion, leading to significant yield loss."
    }
  ],
  "non_chemical_first": [
    "Deep summer ploughing (June, before sowing) to expose and kill pupae of defoliators and girdle beetle present in the soil.",
    "Collect and destroy egg masses and early instar larvae of defoliators by hand-picking; also remove and burn girdled stem portions promptly to destroy girdle beetle eggs and larvae inside.",
    "Set up light traps (1 per acre) and pheromone traps for Spodoptera litura (5 traps per acre) to monitor and mass-trap adult moths.",
    "Maintain field sanitation by removing crop debris and alternate host weeds that harbour defoliator populations.",
    "Follow crop rotation with non-host crops (e.g., sorghum, maize) to break the pest cycle of girdle beetle and defoliators.",
    "Release Trichogramma chilonis egg parasitoids (1.5 lakh eggs per acre) at the time of egg-laying to suppress defoliator populations biologically.",
    "Spray nuclear polyhedrosis virus (NPV) for Spodoptera and Helicoverpa as a biological option where available."
  ],
  "chemical_options": [
    {
      "active_ingredient": "Chlorantraniliprole 09.30%+Lambda-cyhalothrin 04.60% ZC",
      "formulation": "Chlorantraniliprole 09.30%+Lambda-cyhalothrin 04.60% ZC",
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
      "caution": "This combination insecticide is effective against both defoliators (via chlorantraniliprole) and girdle beetle adults (via lambda-cyhalothrin). Wear full-sleeve clothing, chemical-resistant gloves, and a face mask during mixing and spraying. Do not spray near water bodies."
    },
    {
      "active_ingredient": "Emamectin benzoate 01.90%EC",
      "formulation": "Emamectin benzoate 01.90%EC",
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
      "caution": "Highly effective against defoliator larvae including Spodoptera and Helicoverpa. Avoid inhalation of spray mist; wear protective eyewear and gloves. Do not allow re-entry into sprayed field for at least 24 hours."
    },
    {
      "active_ingredient": "Profenofos 50%EC",
      "formulation": "Profenofos 50%EC",
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
      "caution": "Broad-spectrum organophosphate effective against defoliators and girdle beetle. Highly toxic — wear rubber gloves, protective clothing, and a respirator during application. Keep children and livestock away from the field. Do not contaminate irrigation channels."
    },
    {
      "active_ingredient": "Tetraniliprole 18.18% w/w SC",
      "formulation": "Tetraniliprole 18.18% w/w SC",
      "dose": {
        "basis": "per_acre",
        "value_min": 101.1695,
        "value_max": 121.4034,
        "unit": "ml",
        "raw": "250 – 300"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 35,
      "phi_not_applicable": false,
      "caution": "Diamide insecticide with excellent efficacy against lepidopteran defoliators. Wear chemical-resistant gloves and mask during use. Rotate with insecticides of different mode of action to prevent resistance development."
    }
  ],
  "safety": [
    "Always read the pesticide label on the container before use — the label is legally binding and governs the correct dose, timing, and safety requirements.",
    "Wear personal protective equipment (PPE) including long-sleeved clothing, chemical-resistant gloves, a face mask/respirator, and protective eyewear during mixing and spraying.",
    "Do not eat, drink, or smoke while handling pesticides.",
    "Keep all children, women (especially pregnant), and livestock away from the field during spraying and until the spray has dried.",
    "Observe the pre-harvest interval (PHI) strictly — do not harvest the crop before the stated number of days after the last spray.",
    "Dispose of empty pesticide containers safely by triple-rinsing and puncturing; never reuse them for food or water storage.",
    "Spray in the early morning or late evening to minimise exposure to beneficial insects (especially pollinators) and to reduce evaporation.",
    "If poisoning is suspected, seek medical attention immediately and carry the pesticide label or container to the doctor.",
    "This advisory is a guide only and does not replace the advice of the state agriculture department or a qualified agronomist. Consult your local Krishi Vigyan Kendra (KVK) or Agriculture Officer for field-level support."
  ],
  "escalate_to_expert": false
}
```

## S1_742 -- slice 1 (dose) -- soybean
Query: `Farmer wants information regarding control of Collar Rot Disease in Soybean crop?`
Verdict: **rejected: C5: top cause 'Collar Rot (Sclerotium rolfsii)'; the query was about 'Collar rot', which CIB&RC prints as ['Collar rot', 'Charcoal rot', 'Seedling rot']**
verify() score: 0.888889 | passed: False | excluded: False
Failures:
- C5: top cause 'Collar Rot (Sclerotium rolfsii)'; the query was about 'Collar rot', which CIB&RC prints as ['Collar rot', 'Charcoal rot', 'Seedling rot']
Fact-sheet fidelity: None

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Collar Rot (Sclerotium rolfsii)",
      "type": "disease",
      "confidence": 0.88,
      "evidence": "Collar Rot in soybean is caused by the soilborne fungus Sclerotium rolfsii, which attacks the stem at or near the soil surface, causing wilting, rotting at the collar region, and eventual plant death. It is common in warm, humid conditions and in fields with poor drainage."
    }
  ],
  "non_chemical_first": [
    "Use deep summer ploughing to expose and destroy sclerotia (resting bodies of Sclerotium rolfsii) in the soil before sowing.",
    "Avoid waterlogging and ensure proper field drainage, as the pathogen thrives in moist soils — raise beds or use ridges to improve drainage.",
    "Practice crop rotation with non-host cereals (e.g., sorghum, maize) for at least one to two seasons to reduce soilborne inoculum levels.",
    "Remove and destroy infected plant debris and collar-rotted plants promptly from the field to prevent further spread of the disease.",
    "Avoid sowing in heavily infested fields during warm and humid weather, and use certified disease-free seed from a reliable source."
  ],
  "chemical_options": [
    {
      "active_ingredient": "Carbendazim 12%+ Mancozeb 63% WP",
      "formulation": "Carbendazim 12% + Mancozeb 63% WP",
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
      "caution": "This is a seed treatment product. Treat seeds before sowing; do not use treated seed for human or animal consumption. Wear protective gloves, a dust mask, and eye protection while handling the treated seed. Keep treated seeds away from children and livestock."
    },
    {
      "active_ingredient": "Carboxin37.5%+ Thiram37.5%WS",
      "formulation": "Carboxin 37.5% + Thiram 37.5% WS",
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
      "caution": "This is a seed treatment product applied at 3 g per kg of seed. Do not use treated seed for food or feed. Wear gloves, a mask, and protective clothing during seed treatment. Store treated seeds in a secure place away from children and animals."
    }
  ],
  "safety": [
    "Always wear personal protective equipment (PPE) including chemical-resistant gloves, a dust/respirator mask, safety goggles, and full-sleeved clothing when handling and applying any fungicide or treated seed.",
    "Keep children, pets, and livestock away from treated seeds and treated areas at all times.",
    "Do not eat, drink, or smoke while handling fungicide-treated seeds or during application.",
    "Wash hands, face, and exposed skin thoroughly with soap and water after handling treated seeds or chemicals.",
    "Store all fungicides and treated seeds in their original labelled containers, out of reach of children and animals, in a cool and dry place away from food and feed.",
    "Dispose of empty pesticide containers safely by triple-rinsing and puncturing them; do not reuse containers.",
    "The pesticide label on the container is legally binding — always read and follow label instructions before use.",
    "This advisory is a guide only; consult your local agriculture department officer or a qualified agronomist for field-level confirmation and updated registration status."
  ],
  "escalate_to_expert": false
}
```

## S1_648 -- slice 1 (dose) -- gram
Query: `fruit borer in bengal gram`
Verdict: **rejected: C5: top cause 'Gram pod borer (Helicoverpa armigera)'; the query was about 'fruit borer', which CIB&RC prints as ['Pod borers', 'Pod borer', 'Tobacco caterpillar']**
verify() score: 0.9 | passed: False | excluded: False
Failures:
- C5: top cause 'Gram pod borer (Helicoverpa armigera)'; the query was about 'fruit borer', which CIB&RC prints as ['Pod borers', 'Pod borer', 'Tobacco caterpillar']
Fact-sheet fidelity: None

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Gram pod borer (Helicoverpa armigera)",
      "type": "pest",
      "confidence": 0.92,
      "evidence": "Helicoverpa armigera is the primary fruit/pod borer of Bengal gram (chickpea), causing extensive damage by boring into developing pods and feeding on seeds."
    }
  ],
  "non_chemical_first": [
    "Install pheromone traps (Helicoverpa lure) at 5 traps per acre to monitor adult moth activity and time sprays accurately; replace lures every 3–4 weeks.",
    "Collect and destroy larval-infested pods and larvae by hand-picking during early crop stages, especially before pod formation.",
    "Intercrop gram with coriander or sorghum to disrupt pest movement and attract natural enemies such as parasitic wasps.",
    "Avoid excessive nitrogen fertilisation, which promotes lush vegetative growth attractive to egg-laying adults.",
    "Encourage natural enemies by avoiding broad-spectrum insecticides early in the season; conserve parasitoids like Trichogramma by releasing them at egg stage (@ 50,000 eggs/acre) at pod initiation."
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
      "caution": "Wear full-sleeve clothing, chemical-resistant gloves, and a face mask during mixing and spraying. Do not spray during high winds. Keep children and livestock away from treated fields for at least 24 hours."
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
      "caution": "Wear gloves, mask, and goggles during application. Avoid inhalation of spray mist. Re-entry into treated fields should not be done for at least 24 hours."
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
      "caution": "Wear gloves, mask, and protective clothing. Do not spray near water bodies or when bees are active. Observe 14-day pre-harvest interval strictly."
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
      "caution": "Wear full protective equipment including gloves, goggles, and mask. Do not allow drift onto neighbouring crops. Keep livestock away from sprayed area for at least 48 hours."
    }
  ],
  "safety": [
    "Always wear chemical-resistant gloves, long-sleeved clothing, a face mask or respirator, and eye protection while mixing and applying any pesticide.",
    "Never eat, drink, or smoke during pesticide application.",
    "Observe the specified Pre-Harvest Interval (PHI) for each product strictly — do not harvest pods before the PHI has elapsed.",
    "Re-entry into treated fields should be avoided for at least 24 hours after spraying, or longer if odour persists.",
    "Keep children, pregnant women, and livestock away from the field during application and until the spray has dried.",
    "Wash hands, face, and all exposed skin thoroughly with soap and water after handling pesticides.",
    "Dispose of empty pesticide containers safely — do not reuse them for food, water, or any other purpose.",
    "Store pesticides in their original labelled containers, in a locked facility away from food, feed, and water sources.",
    "In case of accidental ingestion or poisoning, contact the nearest hospital immediately and carry the pesticide label with you.",
    "The pesticide label on the container is legally binding — always read and follow label instructions before use."
  ],
  "escalate_to_expert": false
}
```

## S1_792 -- slice 1 (dose) -- gram
Query: `Attack of wilt iin Gram ?`
Verdict: **rejected: C5: top cause 'Wilt (Fusarium oxysporum f. sp. ciceris / Sclerotium rolfsii)'; the query was about 'Wilt', which CIB&RC prints as ['Root rot', 'Wilt', 'Seedling wilt']**
verify() score: 0.9 | passed: False | excluded: False
Failures:
- C5: top cause 'Wilt (Fusarium oxysporum f. sp. ciceris / Sclerotium rolfsii)'; the query was about 'Wilt', which CIB&RC prints as ['Root rot', 'Wilt', 'Seedling wilt']
Fact-sheet fidelity: None

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Wilt (Fusarium oxysporum f. sp. ciceris / Sclerotium rolfsii)",
      "type": "disease",
      "confidence": 0.85,
      "evidence": "Wilt is a common and serious soil-borne fungal disease of gram (chickpea) in Maharashtra, causing wilting of plants, often starting at seedling or early vegetative stage. Seed-borne and soil-borne inoculum are primary sources."
    }
  ],
  "non_chemical_first": [
    "Use certified, wilt-resistant/tolerant gram varieties such as JG 74, Vijay, or locally recommended resistant cultivars to reduce wilt incidence.",
    "Follow a crop rotation of at least 2–3 years with non-host crops (e.g., sorghum, maize) to reduce soil-borne inoculum buildup.",
    "Deep summer ploughing (May–June) to expose soil to high temperatures, which helps to reduce pathogen survival in soil.",
    "Remove and destroy infected plant debris and wilted plants promptly to prevent further spread of the pathogen.",
    "Avoid waterlogging and ensure proper field drainage, as excess moisture favours wilt pathogen development.",
    "Treat seed before sowing with recommended seed-dressing fungicide to protect against seed-borne inoculum."
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
      "caution": "This is a seed dresser — apply only to seeds before sowing, not as a foliar spray. Wear chemical-resistant gloves, a face mask, and protective clothing when handling treated seed. Do not use treated seed for food or feed. Keep treated seed away from children and livestock."
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
      "caution": "This is a seed dresser — apply only to seeds before sowing, not as a foliar spray. Wear chemical-resistant gloves, a face mask, and protective clothing during seed treatment. Do not consume or feed treated seed to animals. Store treated seed away from food items."
    },
    {
      "active_ingredient": "Tebuconazole 15% + Zineb 57% WDG",
      "formulation": "Tebuconazole 15% + Zineb 57% WDG",
      "dose": {
        "basis": "per_ha",
        "value_min": 4.0,
        "value_max": null,
        "unit": "g",
        "raw": "4.0"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": null,
      "phi_not_applicable": true,
      "caution": "This is a seed dresser — apply only to seeds before sowing. Wear appropriate personal protective equipment including gloves, mask, and full-sleeved clothing. Do not use treated seed as food or feed. Keep away from children and livestock."
    }
  ],
  "safety": [
    "Always wear chemical-resistant gloves, a face mask/respirator, full-sleeved shirt, and long trousers when handling any seed-treatment fungicide.",
    "Wash hands, face, and all exposed skin thoroughly with soap and water after handling treated seeds or pesticide formulations.",
    "Do not eat, drink, or smoke while handling pesticide or treated seeds.",
    "Store all pesticides and treated seed in their original labelled containers, locked away and out of reach of children and livestock.",
    "Dispose of empty pesticide containers safely — do not reuse for food, water, or other purposes.",
    "Consult the pesticide label on the container — it is legally binding and takes precedence over any advisory.",
    "In case of accidental ingestion or skin contact, seek immediate medical attention and carry the pesticide label or container to the doctor."
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
  "clarifying_question": "Is the caterpillar feeding on the pods and boring into them (leaving entry holes with frass), or is it cutting the stem at ground level and causing the plant to fall over?",
  "likely_causes": [
    {
      "name": "Gram pod borer",
      "type": "pest",
      "confidence": 0.4,
      "evidence": "Most common caterpillar pest on gram; larvae bore into pods and feed on developing seeds, especially during podding stage."
    },
    {
      "name": "Cutworm",
      "type": "pest",
      "confidence": 0.2,
      "evidence": "Cutworm larvae cut the stem near ground level, causing seedlings or young plants to collapse; active mostly at vegetative stage."
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
Verdict: **rejected: clarifying_question is missing or too short to be specific**
verify() score: 1.0 | passed: False | excluded: False
Failures:
- clarifying_question is missing or too short to be specific

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
  "clarifying_question": "When the flowers drop, do you also notice tiny insects (thrips) or dark/oily spots on the flower stalks and buds, or do the flowers simply fall off without any visible pest or discolouration?",
  "likely_causes": [
    {
      "name": "Thrips",
      "type": "pest",
      "confidence": 0.35,
      "evidence": "Thrips (phulkide) feeding on flower buds and petals is a common cause of flower drop in pomegranate; tiny silvery or scarred tissue may be visible on buds."
    },
    {
      "name": "Bacterial blight",
      "type": "disease",
      "confidence": 0.30,
      "evidence": "Bacterial blight (telya/oily spot) can affect flower stalks and cause premature flower drop, often accompanied by dark, water-soaked or oily lesions."
    },
    {
      "name": "Wilt",
      "type": "disease",
      "confidence": 0.20,
      "evidence": "Wilt (mar rog) causes general plant stress that can manifest as flower and fruit drop in advanced stages."
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
  "clarifying_question": "Could you tell me which part of the cotton plant is being damaged — are you seeing holes or entry marks on the bolls (indicating Pink bollworm), yellowing or curling at the leaf edges (Jassid/Thrips), or a white powdery or sticky coating on the undersides of leaves (Whitefly)?",
  "likely_causes": [
    {
      "name": "Pink bollworm",
      "type": "pest",
      "confidence": 0.35,
      "evidence": "A very common and damaging pest of cotton bolls in Maharashtra; farmer did not specify affected plant part, so boll damage cannot be ruled out."
    },
    {
      "name": "Whitefly",
      "type": "pest",
      "confidence": 0.35,
      "evidence": "Widespread sucking pest on cotton leaves; often reported across Maharashtra cotton belt but symptom details are absent."
    },
    {
      "name": "Jassid",
      "type": "pest",
      "confidence": 0.30,
      "evidence": "Another common sucking pest causing leaf-margin yellowing (hopper burn) on cotton; indistinguishable from Thrips damage without closer observation."
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
Verdict: **rejected: C5: top cause 'Thrips (Thrips tabaci / Frankliniella schultzei)'; the query was about 'thrips', which CIB&RC prints as ['Jassid', 'Aphids', 'thrips']**
verify() score: 0.888889 | passed: False | excluded: False
Failures:
- C5: top cause 'Thrips (Thrips tabaci / Frankliniella schultzei)'; the query was about 'thrips', which CIB&RC prints as ['Jassid', 'Aphids', 'thrips']
Fact-sheet fidelity: None

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Thrips (Thrips tabaci / Frankliniella schultzei)",
      "type": "pest",
      "confidence": 0.95,
      "evidence": "Thrips are a major sucking pest of cotton in Maharashtra, causing silvering, crinkling, and upward curling of leaves, especially on young seedlings and during early vegetative stages."
    }
  ],
  "non_chemical_first": [
    "Monitor fields regularly using blue or yellow sticky traps to detect thrips populations early.",
    "Avoid excessive nitrogen fertilisation, which promotes soft tissue attractive to thrips.",
    "Remove and destroy heavily infested plant parts to reduce local population build-up.",
    "Maintain field hygiene by clearing crop debris and alternate hosts around the field.",
    "Use reflective mulches to deter thrips from settling on young plants.",
    "Conserve natural enemies such as predatory mites and anthocorid bugs by minimising broad-spectrum insecticide use.",
    "Irrigate the crop adequately, as water-stressed plants are more susceptible to thrips damage."
  ],
  "chemical_options": [
    {
      "active_ingredient": "Fipronil 05% SC",
      "formulation": "Fipronil 05% SC",
      "dose": {
        "basis": "per_acre",
        "value_min": 607.0171,
        "value_max": 809.3562,
        "unit": "ml",
        "raw": "1500 –2000 ml/ha"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 6,
      "phi_not_applicable": false,
      "caution": "Fipronil is toxic to bees and aquatic organisms; do not spray near water bodies or during flowering. Wear full protective clothing, gloves, and a mask during mixing and application. Observe a 6-day pre-harvest interval."
    },
    {
      "active_ingredient": "Thiamethoxam 25%WG",
      "formulation": "Thiamethoxam 25%WG",
      "dose": {
        "basis": "per_acre",
        "value_min": 40.4678,
        "value_max": null,
        "unit": "g",
        "raw": "100 g/ha"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 21,
      "phi_not_applicable": false,
      "caution": "Neonicotinoid — highly toxic to bees; avoid application during bloom and near pollinators. Wear protective gloves, mask, and eyewear. Observe a 21-day pre-harvest interval."
    },
    {
      "active_ingredient": "Spinetoram 11.70 %SC",
      "formulation": "Spinetoram 11.70 %SC",
      "dose": {
        "basis": "per_acre",
        "value_min": 169.9648,
        "value_max": null,
        "unit": "ml",
        "raw": "420 ml/ha"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 30,
      "phi_not_applicable": false,
      "caution": "Spinetoram is toxic to bees when wet; apply in the evening or early morning when bees are less active. Wear gloves and a mask during application. Observe a 30-day pre-harvest interval."
    },
    {
      "active_ingredient": "Flonicamid 50%WG",
      "formulation": "Flonicamid 50%WG",
      "dose": {
        "basis": "per_acre",
        "value_min": 60.7017,
        "value_max": null,
        "unit": "g",
        "raw": "150 g/ha"
      },
      "spray_volume_min_l_per_acre": null,
      "spray_volume_max_l_per_acre": null,
      "phi_days": 25,
      "phi_not_applicable": false,
      "caution": "Wear protective gloves, mask, and goggles during mixing and application. Avoid spray drift onto adjacent crops. Observe a 25-day pre-harvest interval."
    }
  ],
  "safety": [
    "RESTRICTED CHEMICAL — DO NOT USE Monocrotophos: The dominant registered formulation, Monocrotophos 36% SL, has been cancelled under S.O. 4294(E) dated 2023-10-03. No new registration certificates are being issued, all existing 36% SL certificates are cancelled (with sale only permitted to clear existing stock until certificate expiry). Any stock of Monocrotophos 36% SL in your possession should not be used on cotton or any crop; consult your local agriculture officer for safe disposal guidance.",
    "A qualified agronomist or state agriculture department officer should visit the farm immediately to assess the situation, advise on safe disposal of any restricted chemical, and confirm the most appropriate registered alternative.",
    "Keep all pesticides in their original labelled containers, locked away from children, livestock, and food/feed.",
    "Wear full personal protective equipment (PPE) — chemical-resistant gloves, face mask or respirator, goggles, and protective clothing — when handling any of the recommended products.",
    "Do not re-enter treated fields until the spray has dried completely; follow the label-specified re-entry interval for each product.",
    "Keep people, children, and livestock away from treated areas during and after spraying until the spray has dried.",
    "Do not spray near water bodies, fish ponds, or bee hives; these products are toxic to aquatic organisms and beneficial insects.",
    "Dispose of empty pesticide containers safely as per label instructions; never reuse containers for food, water, or feed storage.",
    "The pesticide label on the container is the legally binding document; always read and follow all label instructions before use.",
    "This advisory is a guide only and does not replace the advice of the state agriculture department or a qualified agronomist."
  ],
  "escalate_to_expert": true
}
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
  "clarifying_question": "To help you decide which of these products is appropriate, please describe: which part of the cotton plant is affected (leaf, boll, stem, or whole plant), what the damage or symptom looks like (holes, discolouration, wilting, sticky deposits, or spots), and what the current crop stage is (seedling, vegetative, flowering, or boll formation)?",
  "likely_causes": [],
  "non_chemical_first": [],
  "chemical_options": [],
  "safety": [
    "IMPORTANT – Monocrotophos 36% SL is a RESTRICTED chemical: under Gazette Notification S.O. 4294(E) dated 03-Oct-2023, all registration certificates for Monocrotophos 36% SL have been cancelled (effective from 03-Oct-2024); no new certificates are being issued and sale is permitted only to clear existing stock until label expiry. Do NOT procure or use Monocrotophos 36% SL unless you can confirm it is from a batch legally sold before the cancellation date. Consult your local agriculture department or a qualified agronomist before using any remaining stock.",
    "Mixing multiple pesticides (tank-mix) can cause chemical incompatibility, phytotoxicity, or illegal use of a cancelled product — never mix without verifying compatibility and legal registration for each product on the specific pest and crop.",
    "If you have already applied Monocrotophos recently, inform your local agriculture extension officer or Krishi Vigyan Kendra immediately.",
    "Keep all pesticides — including copper oxychloride and emamectin benzoate — away from children, food, feed, and water sources.",
    "Always wear full personal protective equipment (PPE): gloves, goggles, full-sleeved clothing, and a mask when handling any pesticide.",
    "Do not allow people or livestock to re-enter the treated field until the label-specified re-entry interval has elapsed.",
    "Read the label on every container before use — the label is legally binding."
  ],
  "escalate_to_expert": true
}
```

## S4_smoke_grape0 -- slice 4 (dose) -- grape
Query: `FARMER ASKED ABOUT WHITE POWDERY GROWTH ON GRAPE LEAVES AND BUNCHES AT BERRY STAGE`
Verdict: **rejected: C5: top cause 'Powdery Mildew (Erysiphe necator / Uncinula necator)'; the query was about 'Powdery mildew', which CIB&RC prints as ['Downy mildew', 'Powdery mildew', 'Anthracnose']**
verify() score: 0.9 | passed: False | excluded: False
Failures:
- C5: top cause 'Powdery Mildew (Erysiphe necator / Uncinula necator)'; the query was about 'Powdery mildew', which CIB&RC prints as ['Downy mildew', 'Powdery mildew', 'Anthracnose']
Fact-sheet fidelity: None

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Powdery Mildew (Erysiphe necator / Uncinula necator)",
      "type": "disease",
      "confidence": 0.95,
      "evidence": "White powdery growth on grape leaves and bunches at berry stage is the classic symptom of powdery mildew, caused by the obligate biotrophic fungus Erysiphe necator. The fungal mycelium and conidia appear as white-grey powdery coating on both leaves and developing berries, and is common in Maharashtra grape-growing regions during warm, dry conditions with high humidity at night."
    }
  ],
  "non_chemical_first": [
    "Remove and destroy heavily infected leaves, shoots, and bunches from the vineyard to reduce inoculum load; do not compost infected material.",
    "Ensure adequate vine canopy management by timely pruning, shoot positioning, and leaf removal around berry clusters to improve air circulation and reduce humidity within the canopy.",
    "Avoid excessive nitrogen fertilisation, which promotes lush vegetative growth that is more susceptible to powdery mildew.",
    "Monitor the vineyard regularly from bud break onwards and initiate sprays at the first sign of infection or at the pre-flowering stage as a preventive measure."
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
      "caution": "Wear chemical-resistant gloves, protective eyewear, and a mask during mixing and spraying. Do not re-enter the treated area until the spray has dried. Keep children and livestock away from treated vines. Do not apply within 15 days before harvest."
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
      "caution": "Wear full protective clothing including gloves, goggles, and a respirator. Ensure thorough coverage of both leaf surfaces and berry clusters. Do not apply within 25 days before harvest. Rotate with fungicides of different modes of action to prevent resistance development."
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
      "caution": "Wear gloves, protective eyewear, and a mask. Avoid inhalation of spray mist. Do not apply within 14 days before harvest. Do not apply during windy conditions to avoid spray drift to neighbouring crops."
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
      "caution": "Wear protective gloves, eyewear, and a face mask during preparation and application. Do not apply within 10 days before harvest. Wash hands and exposed skin thoroughly after handling. Store away from food, feed, and water sources."
    }
  ],
  "safety": [
    "Always wear chemical-resistant gloves, full-sleeved clothing, protective eyewear, and a nose-mouth mask or respirator when handling and applying fungicides.",
    "Do not eat, drink, or smoke during mixing or application of any fungicide.",
    "Keep all people, children, and livestock out of the treated vineyard until sprays have fully dried and the re-entry interval specified on the product label has elapsed.",
    "Strictly observe the pre-harvest interval (PHI) for the chosen product — do not harvest berries before the stated number of days after the last spray.",
    "Dispose of empty containers safely as per local regulations; do not reuse containers for any other purpose.",
    "If accidental skin or eye contact occurs, wash immediately with copious clean water and seek medical attention if irritation persists.",
    "Rotate fungicide modes of action across spray rounds to delay the development of resistance in the powdery mildew pathogen.",
    "This advisory is a guide only. The pesticide label on the container is legally binding — always read and follow label instructions. Consult your local Krishi Vigyan Kendra or state agriculture department officer for site-specific advice."
  ],
  "escalate_to_expert": false
}
```

## S4_smoke_grape1 -- slice 4 (dose) -- grape
Query: `Farmer asked about mealy bug infestation on grape vine, cottony white insects on stem and bunches`
Verdict: **excluded: ambiguous ground truth: C1_dose, C2_phi — the CIB&RC rows this answer could refer to disagree**
verify() score: 0.888889 | passed: False | excluded: True
Failures:
- AMBIGUOUS: 'Thiamethoxam 25%WG' dose 161.8712g matches some but not all of the CIB&RC rows it could refer to (161.8712 g ('400'); 40.4678 g ('100')) — ground truth cannot grade it
- AMBIGUOUS: 'Thiamethoxam 25%WG' pre-harvest interval 10 matches some but not all of the CIB&RC rows it could refer to (they state 10/15 days) — ground truth cannot grade it
- C5: top cause 'Mealybug (Maconellicoccus hirsutus / Planococcus ficus)'; the query was about 'mealybug', which CIB&RC prints as ['Mealy bugs', 'Thrips', 'Jassids']
Fact-sheet fidelity: None

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "Mealybug (Maconellicoccus hirsutus / Planococcus ficus)",
      "type": "pest",
      "confidence": 0.95,
      "evidence": "Cottony white waxy masses on stems and grape bunches are the classic field sign of mealybug infestation on grapevine; both grape mealybug species are common in Maharashtra vineyards."
    }
  ],
  "non_chemical_first": [
    "Remove and destroy heavily infested shoot tips, leaves, and bunches; do not leave infested material on the ground or compost heap.",
    "Scrape off loose bark on the main trunk and cordons where mealybugs and their egg sacs shelter; destroy the scrapings.",
    "Apply a sticky band (tree-banding grease/adhesive tape) around the trunk base to prevent ant movement up the vine, as ants protect mealybugs from natural enemies and facilitate their spread.",
    "Release the parasitoid Anagyrus dactylopii or the predatory beetle Cryptolaemus montrouzieri (mealybug destroyer) if available from local biocontrol labs — at least 10 Cryptolaemus adults per vine at early infestation stage.",
    "Avoid excessive nitrogen fertilisation, which produces lush soft growth favoured by mealybugs.",
    "Inspect planting material carefully and source certified, mealybug-free rootstocks and cuttings."
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
      "caution": "Buprofezin is an insect growth regulator effective against nymphs; ensure thorough spray coverage on stems and bunches. Wear full-sleeve protective clothing, gloves, and a mask during mixing and spraying. PHI is 7 days — do not harvest grapes within 7 days of application."
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
      "caution": "Spirotetramat is a systemic lipid biosynthesis inhibitor with translaminar movement; it controls all mealybug life stages including those hidden under waxy cover. PHI is 60 days — plan application timing carefully well before harvest. Wear gloves, mask, and protective eyewear. Keep people and livestock away from treated area for at least 24 hours."
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
      "caution": "This combination product provides both systemic contact action (imidacloprid) and lipid biosynthesis inhibition (spirotetramat). PHI is 60 days — do not apply close to harvest. Wear full protective gear including gloves, mask, and goggles. Do not apply when bees are foraging; spray early morning or evening to minimise pollinator exposure."
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
      "caution": "This entry is for soil drench application only; ensure adequate soil moisture before application for good uptake. PHI is 10 days. Wear protective clothing, gloves, and mask. Keep children and livestock away from treated soil. Avoid application near water bodies."
    }
  ],
  "safety": [
    "Always read and follow the label on the pesticide container — the label is legally binding under the Insecticides Act, 1968.",
    "Wear full-sleeve shirt, trousers, chemical-resistant gloves, a nose-and-mouth mask, and protective eyewear when mixing and applying any pesticide.",
    "Never eat, drink, or smoke while handling pesticides.",
    "Mix pesticides in the open or in a well-ventilated area; do not mix near drinking water sources.",
    "Keep all people and livestock out of the treated area during spraying and until the spray has dried completely (minimum 2–4 hours for foliar sprays).",
    "Observe the pre-harvest interval (PHI) strictly: Buprofezin — 7 days; Thiamethoxam (foliar) — 15 days; Thiamethoxam (soil drench) — 10 days; Spirotetramat OD — 60 days; Spirotetramat + Imidacloprid SC — 60 days.",
    "Wash hands, face, and any exposed skin thoroughly with soap and water after handling pesticides.",
    "Dispose of empty pesticide containers safely — puncture, rinse three times, and bury or return to dealer; never reuse containers for food or water.",
    "Store pesticides in original containers in a locked, well-ventilated store away from food, feed, children, and animals.",
    "In case of accidental poisoning, take the victim immediately to the nearest hospital with the pesticide label/container."
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
      "evidence": "Root rot in onion is commonly caused by soil-borne fungi such as Fusarium oxysporum f. sp. cepae, Pythium spp., or Sclerotium rolfsii. These pathogens cause rotting and browning of the basal plate and roots, leading to yellowing, wilting, and collapse of the plant. Wet, poorly drained soils and infected planting material favour the disease."
    }
  ],
  "non_chemical_first": [
    "Use certified, disease-free onion sets or transplants from a reliable and reputable source to reduce the risk of introducing soil-borne pathogens.",
    "Practice crop rotation of at least 3–4 years, avoiding planting onion or other Allium species in the same field where root rot was previously observed.",
    "Improve field drainage by adopting raised-bed planting or providing proper drainage channels to prevent water stagnation, which favours Pythium and Fusarium infection.",
    "Avoid over-irrigation and waterlogging; adopt drip irrigation wherever possible to keep the soil around the base of the plant relatively dry.",
    "Remove and destroy (burn or deep-bury) infected plant debris and bulbs immediately after harvest to reduce the inoculum load in the soil.",
    "Solarise the soil during summer (cover moistened soil with transparent polythene sheet for 4–6 weeks) to reduce populations of soil-borne pathogens before transplanting.",
    "Incorporate well-decomposed farmyard manure or compost to improve soil structure and encourage beneficial microbial activity that can suppress soil-borne pathogens.",
    "Apply Trichoderma viride or Trichoderma harzianum (biocontrol agents) to the nursery soil and in the main field at transplanting as per recommended rates on the product label, to suppress root-rot pathogens — consult your local Krishi Vigyan Kendra (KVK) or Agriculture Department for locally available formulations and doses.",
    "Maintain optimum plant spacing to ensure good air circulation and reduce humidity around the base of plants.",
    "Avoid injury to roots and basal plates during transplanting and weeding, as wounds serve as entry points for pathogens."
  ],
  "chemical_options": [],
  "safety": [
    "When applying any biocontrol product (e.g., Trichoderma), wear gloves and a dust mask to avoid inhalation of spores.",
    "Wash hands thoroughly with soap and water after handling any plant protection product or infected plant material.",
    "Keep children and livestock away from treated fields and areas where infected crop debris is being handled or burned.",
    "Follow all instructions on the product label; the label on the container is legally binding under the Insecticides Act, 1968.",
    "Store any plant protection products in a locked place, away from food, feed, and water sources."
  ],
  "escalate_to_expert": true
}
```

## S5_745 -- slice 5 (nochem) -- tur
Query: `root grub management in red gram`
Verdict: **rejected: C5: top cause 'White grub (root grub) – Holotrichia spp. / Leucopholis spp.'; the query was about 'root grub'**
verify() score: 0.714286 | passed: False | excluded: False
Failures:
- C5: top cause 'White grub (root grub) – Holotrichia spp. / Leucopholis spp.'; the query was about 'root grub'

Raw response:
```json
{
  "in_scope": true,
  "query_understood": true,
  "clarifying_question": null,
  "likely_causes": [
    {
      "name": "White grub (root grub) – Holotrichia spp. / Leucopholis spp.",
      "type": "pest",
      "confidence": 0.85,
      "evidence": "Root grub damage on tur (red gram) is characterised by wilting and yellowing of plants, often in patches, with C-shaped white larvae found feeding on roots below the soil surface. 'Root grub' in red gram most commonly refers to white grub species."
    }
  ],
  "non_chemical_first": [
    "Deep summer ploughing (2–3 times) after harvest to expose larvae, pupae, and eggs to sunlight and predatory birds, reducing the soil population before sowing.",
    "Collect and destroy adult beetles during their peak evening flight period (typically during pre-monsoon showers) by shaking trees near the field; hand-pick and kill the adults.",
    "Encourage natural predators by allowing birds (crows, mynahs) to forage in ploughed fields immediately after tillage.",
    "Apply well-decomposed farmyard manure (FYM) only; avoid fresh or partially decomposed organic matter, which attracts egg-laying adult beetles.",
    "Intercrop tur with sorghum or maize where feasible, as dense root systems can reduce grub movement and allow easier detection.",
    "Monitor fields regularly from germination onwards, especially in fields with a history of white grub; uproot affected plants, locate and destroy larvae manually.",
    "Use light traps near the field boundary during the adult flight period (June–July) to mass-trap beetles and reduce the next generation population.",
    "Drench the root zone with a suspension of entomopathogenic fungus Metarhizium anisopliae or Beauveria bassiana (locally available biopesticide formulations) as a biological option; follow the manufacturer's label for dose and application timing."
  ],
  "chemical_options": [],
  "safety": [
    "When applying any biopesticide drench (e.g., Metarhizium or Beauveria), wear rubber gloves and avoid inhaling dust; wash hands and exposed skin thoroughly after handling.",
    "Keep children and livestock away from freshly treated field areas until the soil drench has been incorporated.",
    "Store any purchased biopesticide formulation away from direct sunlight and heat, and use before the expiry date.",
    "Always read and follow the label on any product container – the label is legally binding under the Insecticides Act, 1968.",
    "If you suspect a severe or spreading infestation affecting a large area, contact your local Krishi Vigyan Kendra (KVK) or the State Agriculture Department for a field inspection before investing in further control measures."
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
    "This advisory service covers only pest and disease management on eight crops: cotton, soybean, tur (pigeonpea), gram (chickpea), onion, tomato, grape, and pomegranate. For questions about crop yield, variety selection, fertilization, irrigation, or market prices, please contact your local Krishi Vigyan Kendra (KVK) or the Maharashtra State Agriculture Department."
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
    "This advisory service covers only pest and disease management on eight crops: cotton, soybean, tur (pigeonpea), gram (chickpea), onion, tomato, grape, and pomegranate. For questions about average yield, crop duration, variety selection, fertilizer, irrigation, or market information, please contact your local Krishi Vigyan Kendra (KVK) or the Maharashtra State Agriculture Department."
  ],
  "escalate_to_expert": false
}
```

## Aggregate
- Accepted: 6 / 20 (30%)
- Slice 1 acceptance: 0 / 8 (0%)
- Gate/check failures by name:
  - C5: 12
  - clarifying_question is missing or too short to be specific: 1
