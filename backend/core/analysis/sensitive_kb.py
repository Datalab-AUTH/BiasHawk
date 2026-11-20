KNOWLEDGE_BASE = {
    "RACE_ETHNICITY": {
        "description": "Information revealing racial or ethnic origin.",
        "keywords": ["race", "ethnic", "ethnicity", "tribe", "nationality", "origin_country"],
        "rationale": "Explicitly mentioned as special category data (EU AI Act, Art. 9 GDPR). NIST SP 1270 highlights this as a key demographic for bias analysis.",
        "sources": ["EU AI Act (via GDPR Art. 9(1))", "NIST SP 1270 Sec 3.1, 4.2"],
        "base_sensitivity_score": 90 # Score out of 100 for direct, unambiguous match
    },
    "POLITICAL_OPINIONS": {
        "description": "Information revealing political opinions.",
        "keywords": ["political_party", "political_view", "voting_record", "political_affiliation", "election_choice"],
        "rationale": "Special category data (EU AI Act, Art. 9 GDPR).",
        "sources": ["EU AI Act (via GDPR Art. 9(1))"],
        "base_sensitivity_score": 85
    },
    "RELIGIOUS_PHILOSOPHICAL_BELIEFS": {
        "description": "Information revealing religious or philosophical beliefs.",
        "keywords": ["religion", "belief", "faith", "denomination", "philosophy", "church", "mosque", "temple", "spiritual"],
        "rationale": "Special category data (EU AI Act, Art. 9 GDPR). NIST SP 1270 includes religion in demographic groups.",
        "sources": ["EU AI Act (via GDPR Art. 9(1))", "NIST SP 1270 Sec 3.1"],
        "base_sensitivity_score": 85
    },
    "TRADE_UNION_MEMBERSHIP": {
        "description": "Information revealing trade union membership.",
        "keywords": ["union_member", "trade_union", "labor_union"],
        "rationale": "Special category data (EU AI Act, Art. 9 GDPR).",
        "sources": ["EU AI Act (via GDPR Art. 9(1))"],
        "base_sensitivity_score": 80
    },
    "GENETIC_DATA": {
        "description": "Personal data relating to the inherited or acquired genetic characteristics of a natural person.",
        "keywords": ["genetic", "dna", "genome", "gene_sequence", "hereditary_disease_marker"],
        "rationale": "Special category data (EU AI Act, Art. 9 GDPR).",
        "sources": ["EU AI Act (via GDPR Art. 9(1))"],
        "base_sensitivity_score": 95
    },
    "BIOMETRIC_DATA_FOR_IDENTIFICATION": {
        "description": "Biometric data for the purpose of uniquely identifying a natural person (e.g., facial images, dactyloscopic data).",
        "keywords": ["biometric", "fingerprint", "face_recognition", "iris_scan", "voice_print", "retina_scan", "face_template", "keystroke_dynamics_id"],
        "rationale": "Special category data (EU AI Act, Art. 9 GDPR). EU AI Act has strict rules, especially for remote biometric identification (Art. 5). NIST SP 1270 also discusses biometric systems.",
        "sources": ["EU AI Act Art. 5, Art. 9(1) GDPR", "NIST SP 1270 Sec 4.3.2"],
        "base_sensitivity_score": 98 # Very high due to identification purpose
    },
    "HEALTH_DATA": {
        "description": "Personal data related to the physical or mental health of a natural person.",
        "keywords": ["health", "medical_condition", "disability", "disease", "diagnosis", "hospital_record", "medication", "mental_state", "psychological_assessment", "wellness_tracker_data"],
        "rationale": "Special category data (EU AI Act, Art. 9 GDPR). NIST SP 1270 frequently mentions health and disability.",
        "sources": ["EU AI Act (via GDPR Art. 9(1))", "NIST SP 1270 Sec 3.1, 4.2"],
        "base_sensitivity_score": 90
    },
    "SEXUAL_LIFE_ORIENTATION": {
        "description": "Data concerning a natural person's sex life or sexual orientation.",
        "keywords": ["sexual_orientation", "sex_life", "gender_identity", "lgbtq", "preferred_pronoun", "relationship_status_explicit"], # gender_identity sometimes separate, sometimes here
        "rationale": "Special category data (EU AI Act, Art. 9 GDPR). NIST SP 1270 covers gender identity and sexual orientation.",
        "sources": ["EU AI Act (via GDPR Art. 9(1))", "NIST SP 1270 Sec 3.1"],
        "base_sensitivity_score": 90
    },
    "GENDER_SEX": { # Not "special category" under GDPR but critical for bias (NIST)
        "description": "Information about an individual's gender or sex.",
        "keywords": ["gender", "sex", "male", "female", "non_binary", "intersex"],
        "rationale": "Key demographic for bias analysis (NIST SP 1270). While not 'special category' itself under GDPR, it's often protected and crucial for fairness.",
        "sources": ["NIST SP 1270 Sec 3.1, 4.2"],
        "base_sensitivity_score": 75
    },
    "AGE": {
        "description": "Information about an individual's age or date of birth.",
        "keywords": ["age", "date_of_birth", "dob", "birth_year", "age_group"],
        "rationale": "Common demographic for bias analysis (NIST SP 1270). Age discrimination is a concern.",
        "sources": ["NIST SP 1270 Sec 3.1, 4.2"],
        "base_sensitivity_score": 70
    },
    "SOCIOECONOMIC_STATUS_PROXIES": {
        "description": "Features that can act as proxies for socioeconomic status, potentially leading to bias.",
        "keywords": ["zip_code", "postal_code", "income", "income_range", "education_level", "highest_education", "occupation", "neighborhood_type", "property_value", "credit_score", "location_geohash_medium_precision", "vehicle_type_owned"],
        "rationale": "NIST SP 1270 emphasizes identifying proxies for sensitive attributes. These can lead to allocative or representational harms.",
        "sources": ["NIST SP 1270 Sec 3.2, 4.4"],
        "base_sensitivity_score": 60 # Lower base, as it's a proxy, sensitivity more context-dependent
    },
    "DISABILITY_STATUS": { # Often part of Health, but NIST gives it focus
        "description": "Information about an individual's physical or mental disabilities.",
        "keywords": ["disability", "disabled", "handicap", "impairment", "accessibility_need", "assistive_technology_user"],
        "rationale": "Covered under Health Data (special category) and a key focus in NIST SP 1270 for fairness and bias.",
        "sources": ["EU AI Act (via GDPR Art. 9(1) - Health)", "NIST SP 1270 Sec 3.1, 4.2"],
        "base_sensitivity_score": 88
    },
    "LOCATION_PRECISE": {
        "description": "Precise geolocation data that can identify an individual's location with high accuracy.",
        "keywords": ["gps_coordinates", "exact_address", "location_geohash_high_precision", "real_time_location"],
        "rationale": "Can be highly sensitive, revealing patterns of life, and potentially inferring other sensitive attributes. EU AI Act mentions location data in context of high-risk systems (e.g. law enforcement). NIST discusses location as a potential source of bias.",
        "sources": ["EU AI Act (contextually, e.g. Art 10 data governance)", "NIST SP 1270 Sec 4.4"],
        "base_sensitivity_score": 75
    },
    # Potentially add more based on thorough review of NIST SP 1270 (e.g., familial status, veteran status if relevant context)
}