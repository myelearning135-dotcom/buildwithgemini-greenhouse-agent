# ruff: noqa
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

import json
import os
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.genai import types

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from app.a2ui_utils import a2ui_callback
from app.tools import (
    add_plant_to_catalog,
    calculator,
    generate_plant_image,
    generate_plant_video,
    get_current_time,
    get_live_weather_and_gardening_conditions,
    get_plant_details,
    get_weather,
    list_plants,
    lookup_botanical_taxonomy,
    update_plant_stock,
)

# Load Reasoning Engine / Agent Engine resource name from deployment_metadata.json
AGENT_ENGINE_RESOURCE_NAME = "projects/736030590369/locations/us-east1/reasoningEngines/4323245635554770944"
metadata_path = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
if os.path.exists(metadata_path):
    try:
        with open(metadata_path) as f:
            meta = json.load(f)
            if meta.get("remote_agent_runtime_id"):
                AGENT_ENGINE_RESOURCE_NAME = meta["remote_agent_runtime_id"]
    except Exception:
        pass

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=AGENT_ENGINE_RESOURCE_NAME
)


from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool


async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are an expert Greenhouse & Plant Care Assistant for our plant shop catalog. "
        "You help customers explore plant inventory, look up care instructions, "
        "look up official botanical taxonomy for plant species, generate visual preview images for plants, "
        "add new plant stock to our Firestore database, check live gardening weather, and update plant stock counts. "
        "You have cross-session long-term memory enabled. Pay special attention to and remember: "
        "- User watering schedules (e.g. 'water Monstera every Tuesday', 'overwatered Peace Lily'). "
        "- User plant inventory (e.g. 'I own 3 snake plants', 'my indoor collection'). "
        "- Plant issues & health concerns (e.g. 'yellow leaves on fiddle leaf fig', 'gnats in soil'). "
        "Use your memory and available tools (list_plants, get_plant_details, lookup_botanical_taxonomy, "
        "generate_plant_image, add_plant_to_catalog, update_plant_stock, "
        "get_live_weather_and_gardening_conditions, calculator, get_current_time) to give tailored, memory-aware plant care."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        list_plants,
        get_plant_details,
        lookup_botanical_taxonomy,
        generate_plant_image,
        generate_plant_video,
        add_plant_to_catalog,
        update_plant_stock,
        get_live_weather_and_gardening_conditions,
        calculator,
        get_current_time,
        get_weather,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)



