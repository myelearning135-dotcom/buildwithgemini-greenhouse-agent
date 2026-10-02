# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import ast
import operator
import json
import uuid
import urllib.request
import urllib.parse
import base64
import google.auth
import google.auth.transport.requests
from zoneinfo import ZoneInfo
from google import genai
from google.genai import types
from google.cloud import firestore, storage
from google.adk.tools import ToolContext

FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-2993b959a48b"
BUCKET_NAME = "greenhouse-plant-images-qwiklabs-gcp-02-2993b959a48b"


def _get_firestore_client():
    return firestore.Client(project=FIRESTORE_PROJECT_ID)

# Supported math operators for safe calculation
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_ast_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            left = _eval_ast_node(node.left)
            right = _eval_ast_node(node.right)
            return SAFE_OPERATORS[op_type](left, right)
        raise ValueError(f"Unsupported binary operator: {op_type.__name__}")
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            operand = _eval_ast_node(node.operand)
            return SAFE_OPERATORS[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
    else:
        raise ValueError("Invalid mathematical expression")


def calculator(expression: str) -> str:
    """Evaluates a mathematical expression safely.

    Args:
        expression: A string mathematical expression like '125 * 37' or '(10 + 5) / 3'.

    Returns:
        The calculated result as a string, or an error message.
    """
    try:
        parsed = ast.parse(expression.strip(), mode="eval")
        result = _eval_ast_node(parsed.body)
        return f"Result: {result}"
    except Exception as e:
        return f"Error evaluating expression '{expression}': {str(e)}"


def get_current_time(timezone_name: str = "UTC") -> str:
    """Gets the current date and time for a given timezone.

    Args:
        timezone_name: Standard timezone string such as 'UTC', 'America/New_York', 'Europe/London', 'Asia/Tokyo', etc.

    Returns:
        Formatted current date and time string.
    """
    try:
        tz = ZoneInfo(timezone_name)
        now = datetime.datetime.now(tz)
        return f"Current time in {timezone_name}: {now.strftime('%Y-%m-%d %H:%M:%S %Z (%z)')}"
    except Exception as e:
        return f"Unknown timezone '{timezone_name}'. Error: {str(e)}"


def get_weather(location: str) -> str:
    """Simulates getting current weather for a specified location.

    Args:
        location: City or location name.

    Returns:
        Simulated weather report for the location.
    """
    loc_lower = location.lower()
    if "san francisco" in loc_lower or "sf" in loc_lower:
        return "San Francisco weather: 62°F (17°C), Partly Cloudy with light coastal fog."
    elif "tokyo" in loc_lower:
        return "Tokyo weather: 72°F (22°C), Clear skies."
    elif "london" in loc_lower:
        return "London weather: 58°F (14°C), Light drizzle."
    elif "new york" in loc_lower or "nyc" in loc_lower:
        return "New York weather: 75°F (24°C), Sunny."
    else:
        return f"{location} weather: 70°F (21°C), Mostly Sunny."


def get_live_weather_and_gardening_conditions(location: str) -> str:
    """Fetches real-time live weather and outdoor gardening conditions for a location.

    Args:
        location: City or region name (e.g. 'San Francisco', 'Tokyo', 'London').

    Returns:
        Summary of live current temperature, wind speed, and plant care advice.
    """
    try:
        encoded_loc = urllib.parse.quote(location.strip())
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_loc}&count=1"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "GreenhouseAgent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            geo_data = json.loads(resp.read().decode())

        if not geo_data.get("results"):
            return f"Could not find coordinates for location '{location}'."

        loc_info = geo_data["results"][0]
        lat = loc_info["latitude"]
        lon = loc_info["longitude"]
        city_name = loc_info.get("name", location)
        country = loc_info.get("country", "")

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        req_w = urllib.request.Request(weather_url, headers={"User-Agent": "GreenhouseAgent/1.0"})
        with urllib.request.urlopen(req_w, timeout=5) as resp_w:
            weather_data = json.loads(resp_w.read().decode())

        curr = weather_data.get("current_weather", {})
        temp_c = curr.get("temperature")
        wind = curr.get("windspeed")
        temp_f = round((temp_c * 9 / 5) + 32, 1) if temp_c is not None else None

        advice = "Suitable for outdoor plant watering and ventilation."
        if temp_c is not None:
            if temp_c < 10:
                advice = "Cold weather! Keep tropical indoor plants away from unheated windows or outdoor drafts."
            elif temp_c > 30:
                advice = "Hot weather! Check soil moisture frequently and provide shade for delicate plants."

        return (
            f"Live weather for {city_name}, {country}: "
            f"Temperature: {temp_c}°C ({temp_f}°F), Wind Speed: {wind} km/h. "
            f"Gardening advice: {advice}"
        )
    except Exception as e:
        return f"Error fetching live weather for '{location}': {str(e)}"



def list_plants(care_level: str = "") -> str:
    """Lists all plants available in the greenhouse catalog from Firestore.

    Args:
        care_level: Optional filter for plant care level (e.g. 'Easy', 'Moderate', 'High').

    Returns:
        JSON string list of plant documents.
    """
    try:
        db = _get_firestore_client()
        query = db.collection("plants")
        if care_level:
            query = query.where("care_level", "==", care_level)
        docs = query.stream()
        plants = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            plants.append(data)
        if not plants:
            return "No plants found matching the criteria."
        return json.dumps(plants, indent=2)
    except Exception as e:
        return f"Error querying Firestore plants: {str(e)}"


def get_plant_details(plant_name: str) -> str:
    """Gets detailed information about a specific plant by name or ID from Firestore.

    Args:
        plant_name: Name or ID of the plant (e.g., 'Monstera Deliciosa', 'snake_plant').

    Returns:
        JSON string of the plant details, or an error message if not found.
    """
    try:
        db = _get_firestore_client()
        doc_id = plant_name.lower().replace(" ", "_")
        doc_ref = db.collection("plants").document(doc_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            return json.dumps(data, indent=2)

        docs = db.collection("plants").stream()
        for doc in docs:
            data = doc.to_dict()
            if plant_name.lower() in data.get("name", "").lower():
                data["id"] = doc.id
                return json.dumps(data, indent=2)

        return f"Plant '{plant_name}' not found in greenhouse inventory."
    except Exception as e:
        return f"Error retrieving plant details: {str(e)}"


def add_plant_to_catalog(
    name: str,
    species: str,
    care_level: str,
    water_frequency: str,
    sunlight: str,
    price: float,
    stock: int,
    description: str = "",
) -> str:
    """Adds a new plant item to the greenhouse catalog stored in Firestore.

    Args:
        name: Common name of the plant (e.g. 'Calathea Orbifolia').
        species: Botanical species name (e.g. 'Goeppertia orbifolia').
        care_level: Care difficulty level ('Easy', 'Moderate', 'High').
        water_frequency: Recommended watering schedule.
        sunlight: Light requirement (e.g. 'Medium to bright indirect').
        price: Retail price in USD.
        stock: Available inventory count.
        description: Short description of the plant.

    Returns:
        Confirmation string upon successful write to Firestore.
    """
    try:
        db = _get_firestore_client()
        doc_id = name.lower().replace(" ", "_")
        plant_data = {
            "name": name,
            "species": species,
            "care_level": care_level,
            "water_frequency": water_frequency,
            "sunlight": sunlight,
            "price": float(price),
            "stock": int(stock),
            "description": description,
        }
        db.collection("plants").document(doc_id).set(plant_data)
        return f"Successfully added '{name}' to Firestore inventory with document ID '{doc_id}'."
    except Exception as e:
        return f"Error adding plant to Firestore: {str(e)}"


def update_plant_stock(plant_name: str, new_stock: int) -> str:
    """Updates the inventory stock count for a plant in Firestore.

    Args:
        plant_name: Name or ID of the plant to update.
        new_stock: New inventory stock count.

    Returns:
        Confirmation string upon updating stock.
    """
    try:
        db = _get_firestore_client()
        doc_id = plant_name.lower().replace(" ", "_")
        doc_ref = db.collection("plants").document(doc_id)
        doc = doc_ref.get()
        if doc.exists:
            doc_ref.update({"stock": int(new_stock)})
            return f"Updated stock for '{doc.to_dict().get('name')}' to {new_stock}."

        docs = db.collection("plants").stream()
        for doc in docs:
            data = doc.to_dict()
            if plant_name.lower() in data.get("name", "").lower():
                db.collection("plants").document(doc.id).update({"stock": int(new_stock)})
                return f"Updated stock for '{data.get('name')}' to {new_stock}."

        return f"Plant '{plant_name}' not found in inventory."
    except Exception as e:
        return f"Error updating stock in Firestore: {str(e)}"


def lookup_botanical_taxonomy(plant_name: str) -> str:
    """Looks up official botanical taxonomy and scientific classification for a plant species using the GBIF global biodiversity API.

    Args:
        plant_name: Common or scientific name of the plant (e.g. 'Monstera deliciosa', 'Ficus lyrata', 'Peace Lily').

    Returns:
        JSON string containing official scientific name, family, genus, taxonomic status, and rank.
    """
    try:
        encoded_name = urllib.parse.quote(plant_name.strip())
        url = f"https://api.gbif.org/v1/species/match?name={encoded_name}"
        req = urllib.request.Request(url, headers={"User-Agent": "GreenhouseAgent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        if data.get("matchType") == "NONE" or not data.get("scientificName"):
            return f"No botanical taxonomy record found for '{plant_name}'."

        result = {
            "query": plant_name,
            "scientific_name": data.get("scientificName"),
            "family": data.get("family"),
            "genus": data.get("genus"),
            "kingdom": data.get("kingdom"),
            "rank": data.get("rank"),
            "status": data.get("status"),
            "gbif_id": data.get("usageKey"),
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error fetching botanical taxonomy for '{plant_name}': {str(e)}"


def generate_plant_image(
    prompt: str,
    tool_context: ToolContext = None,
) -> str:
    """Generates an image for a plant item using gemini-3.1-flash-lite-image in the global region.

    Saves the image using tool_context.save_artifact for the Playground's Artifacts panel,
    uploads the image bytes directly to Cloud Storage, and returns its public HTTPS URL.

    Args:
        prompt: Detailed visual description of the plant or arrangement to generate.
        tool_context: ADK ToolContext injected automatically by the framework.

    Returns:
        Public HTTPS URL of the generated image (https://storage.googleapis.com/<bucket>/<object>).
    """
    try:
        client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"]
            ),
        )

        image_bytes = None
        mime_type = "image/jpeg"
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    mime_type = part.inline_data.mime_type or "image/jpeg"
                    break

        if not image_bytes:
            return f"Failed to generate image for prompt: '{prompt}'"

        ext = "png" if "png" in mime_type else "jpg"
        unique_id = uuid.uuid4().hex[:8]

        # 1. Save artifact for Playground Artifacts panel
        if tool_context:
            artifact_filename = f"generated_plant_{unique_id}.{ext}"
            part_artifact = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            tool_context.save_artifact(filename=artifact_filename, artifact=part_artifact)

        # 2. Upload same image bytes directly to public Cloud Storage bucket
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        gcs_filename = f"plant_image_{unique_id}.{ext}"
        blob = bucket.blob(gcs_filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{gcs_filename}"
        return public_url
    except Exception as e:
        return f"Error generating plant image: {str(e)}"


def generate_plant_video(
    prompt: str,
    tool_context: ToolContext = None,
) -> str:
    """Generates a short video for a plant, greenhouse item, or care guide using Google's Omni model (gemini-omni-flash-preview)
    in the global region, saves it as an artifact, uploads it directly to Cloud Storage, and returns its public HTTPS URL.

    Args:
        prompt: Visual description of the plant, growth timelapse, or greenhouse scene to generate a video for.
        tool_context: ADK ToolContext injected automatically by the framework.

    Returns:
        Public HTTPS URL of the generated video (https://storage.googleapis.com/<bucket>/<object>).
    """
    try:
        credentials, project = google.auth.default()
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)

        url = f"https://aiplatform.googleapis.com/v1beta1/projects/{FIRESTORE_PROJECT_ID}/locations/global/interactions"
        headers = {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gemini-omni-flash-preview",
            "input": [{"type": "text", "text": prompt}],
            "generation_config": {"video_config": {"task": "text_to_video"}}
        }

        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))

        video_bytes = None
        mime_type = "video/mp4"

        if "steps" in res_json:
            for step in res_json["steps"]:
                if step.get("type") == "model_output" and "content" in step:
                    for part in step["content"]:
                        if part.get("type") == "video" or "data" in part:
                            raw_data = part.get("data") or part.get("inline_data", {}).get("data")
                            mime_type = part.get("mime_type") or "video/mp4"
                            if raw_data:
                                if isinstance(raw_data, str):
                                    video_bytes = base64.b64decode(raw_data)
                                else:
                                    video_bytes = raw_data
                                break

        if not video_bytes:
            return f"Failed to generate video for prompt: '{prompt}'"

        unique_id = uuid.uuid4().hex[:8]
        ext = "mp4"

        # 1. Save artifact for Playground Artifacts panel
        if tool_context:
            artifact_filename = f"generated_plant_video_{unique_id}.{ext}"
            part_artifact = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
            tool_context.save_artifact(filename=artifact_filename, artifact=part_artifact)

        # 2. Upload same video bytes directly to public Cloud Storage bucket
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        gcs_filename = f"plant_video_{unique_id}.{ext}"
        blob = bucket.blob(gcs_filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{gcs_filename}"
        return public_url
    except Exception as e:
        return f"Error generating plant video: {str(e)}"




