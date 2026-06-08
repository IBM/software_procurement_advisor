from typing import List
import requests
from pathlib import Path
from pydantic import BaseModel, Field
from rapidfuzz import process, fuzz
from requests.auth import HTTPBasicAuth

from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from ibm_watsonx_orchestrate.run import connections
from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType

# ======================================================
# CONSTANTS
# ======================================================
SNOW_CONNECTION = "ServiceNow_Auth"

TOOL_DIR = Path(__file__).parent
SOFTWARE_NAMES_FILE = "software_names.txt"

ALLOWED_DISPOSITIONS = {
    "acceptable standard"
}

# ======================================================
# MODELS
# ======================================================
class SoftwareEntry(BaseModel):
    name: str = ""
    short_description: str = ""
    description: str = ""
    price: str = ""
    link: str = ""
    meta_data: str = ""
    disposition: str = ""


class RecommendationResponse(BaseModel):
    recommended_software: List[SoftwareEntry] = Field(default_factory=list)


# ======================================================
# AUTOCORRECT (same as previous tool)
# ======================================================
def autocorrect_name(name: str, threshold: int = 75) -> str:
    if not name:
        return name

    file_path = TOOL_DIR / SOFTWARE_NAMES_FILE

    if not file_path.exists():
        return name

    with open(file_path, encoding="utf-8") as f:
        canonical = [line.strip() for line in f if line.strip()]

    lookup = {n.lower(): n for n in canonical}

    match = process.extractOne(
        name.lower(),
        lookup.keys(),
        scorer=fuzz.WRatio,
    )

    if match and match[1] >= threshold:
        return lookup[match[0]]

    return name


# ======================================================
# CONNECTION
# ======================================================
def get_connection(app_id: str):
    creds = connections.basic_auth(app_id)
    return creds.url.rstrip("/"), HTTPBasicAuth(
        creds.username,
        creds.password
    )


# ======================================================
# SERVICENOW LOOKUP
# ======================================================
def fetch_servicenow_candidates(
    keyphrases: List[str],
    software_names: List[str],
) -> List[dict]:

    base_url, auth = get_connection(SNOW_CONNECTION)

    query_parts = []

    # Search descriptions + metadata
    if keyphrases:
        for kp in keyphrases:
            query_parts.append(f"descriptionLIKE{kp}")
            query_parts.append(f"u_meta_dataLIKE{kp}")

    # Search names + autocorrect
    if software_names:
        for name in software_names:
            query_parts.append(f"nameLIKE{name}")

            corrected = autocorrect_name(name)

            if corrected.lower() != name.lower():
                query_parts.append(f"nameLIKE{corrected}")

    if not query_parts:
        return []

    sysparm_query = "^OR".join(query_parts) + "^active=true"

    params = {
        "sysparm_query": sysparm_query,
        "sysparm_fields": "name,short_description,description,price,u_installation_link,u_meta_data,u_software_disposition",
        "sysparm_limit": 50,
    }

    response = requests.get(
        f"{base_url}/api/now/table/sc_cat_item",
        auth=auth,
        params=params,
        timeout=20,
    )

    response.raise_for_status()

    return response.json().get("result", [])


# ======================================================
# MAIN TOOL
# ======================================================
@tool(
    name="recommend_software_by_functionality",
    description="Recommend acceptable standard software using ServiceNow catalog",
    permission=ToolPermission.ADMIN,
    expected_credentials=[
        {
            "app_id": SNOW_CONNECTION,
            "type": ConnectionType.BASIC_AUTH
        }
    ],
)
def recommend_software_by_functionality(
    software_functionality: str = "",
    keyphrases: List[str] = None,
    software_names: List[str] = None,
) -> RecommendationResponse:

    keyphrases = keyphrases or []
    software_names = software_names or []

    results = fetch_servicenow_candidates(
        keyphrases,
        software_names
    )

    recommendations: List[SoftwareEntry] = []
    seen = set()

    for item in results:
        original_name = item.get("name", "").strip()

        if not original_name:
            continue

        disposition = item.get(
            "u_software_disposition",
            ""
        ).strip().lower()

        # Keep only acceptable standard
        if disposition not in ALLOWED_DISPOSITIONS:
            continue

        name_key = original_name.lower()

        if name_key in seen:
            continue

        seen.add(name_key)

        recommendations.append(
            SoftwareEntry(
                name=original_name,
                short_description=item.get("short_description", ""),
                description=item.get("description", ""),
                price=item.get("price", "") or "",
                link=item.get("u_installation_link", ""),
                meta_data=item.get("u_meta_data", ""),
                disposition=item.get("u_software_disposition", ""),
            )
        )

    return RecommendationResponse(
        recommended_software=recommendations
    )


# ======================================================
# LOCAL TEST
# ======================================================
'''
if __name__ == "__main__":
    keyphrases = [
        "AI code editor",
        "code generation",
        "auto-completion",
        "developer productivity"
    ]

    software_names = [
        "GitHub Copilot",
        "Cursor",
        "Tabnine",
        "JetBrains AI Assistant"
    ]

    result = recommend_software_by_functionality(
        software_functionality="Get me AI coding tools",
        keyphrases=keyphrases,
        software_names=software_names,
    )

    from pprint import pprint
    pprint(result.model_dump())

'''
