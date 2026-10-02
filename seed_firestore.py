# Copyright 2026 Google LLC
# Seed script for greenhouse-agent Firestore collection

from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-02-2993b959a48b"
COLLECTION_NAME = "plants"

INITIAL_PLANTS = [
    {
        "id": "monstera_deliciosa",
        "name": "Monstera Deliciosa",
        "species": "Monstera deliciosa",
        "care_level": "Easy",
        "water_frequency": "Every 1-2 weeks",
        "sunlight": "Bright, indirect light",
        "price": 29.99,
        "stock": 12,
        "description": "Popular tropical plant with iconic split leaves.",
    },
    {
        "id": "fiddle_leaf_fig",
        "name": "Fiddle Leaf Fig",
        "species": "Ficus lyrata",
        "care_level": "Moderate",
        "water_frequency": "Once a week when top soil is dry",
        "sunlight": "Bright, filtered light",
        "price": 45.00,
        "stock": 8,
        "description": "Stunning indoor tree with large, violin-shaped leaves.",
    },
    {
        "id": "snake_plant",
        "name": "Snake Plant",
        "species": "Dracaena trifasciata",
        "care_level": "Easy",
        "water_frequency": "Every 2-3 weeks",
        "sunlight": "Low to bright indirect light",
        "price": 19.99,
        "stock": 20,
        "description": "Hardy air-purifying plant with upright sword-like leaves.",
    },
    {
        "id": "peace_lily",
        "name": "Peace Lily",
        "species": "Spathiphyllum",
        "care_level": "Easy",
        "water_frequency": "Weekly, prefers moist soil",
        "sunlight": "Medium to low light",
        "price": 24.50,
        "stock": 15,
        "description": "Elegant plant known for white blooms and air purifying qualities.",
    },
    {
        "id": "golden_pothos",
        "name": "Golden Pothos",
        "species": "Epipremnum aureum",
        "care_level": "Easy",
        "water_frequency": "Every 1-2 weeks",
        "sunlight": "Low to bright indirect light",
        "price": 14.99,
        "stock": 25,
        "description": "Fast-growing trailing vine with heart-shaped variegated leaves.",
    },
]


def seed_database():
    print(f"Connecting to Firestore for project: {PROJECT_ID}...")
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection(COLLECTION_NAME)

    for plant in INITIAL_PLANTS:
        plant_id = plant["id"]
        doc_data = {k: v for k, v in plant.items() if k != "id"}
        collection_ref.document(plant_id).set(doc_data)
        print(f"Seeded plant: '{plant['name']}' (ID: {plant_id})")

    print("Firestore seeding complete!")


if __name__ == "__main__":
    seed_database()
