import requests
from typing import List
from pathlib import Path

from rapidfuzz import process, fuzz
from pydantic import BaseModel, Field
from requests.auth import HTTPBasicAuth

from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from ibm_watsonx_orchestrate.run import connections
from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType

# ======================================================
# CONSTANTS
# ======================================================
SNOW_CONNECTION = "ServiceNow_Auth"
DEFAULT_CATALOG_ID = "99a39fcf83ac0f1023fc7fc6feaad3a3"

SOFTWARE_NAMES_FILE = "software_names.txt"
tool_dir = Path(__file__).parent

# ======================================================
# AUTOCORRECT
# ======================================================
def autocorrect_name(name: str, threshold: int = 75) -> str:
    if not name:
        return name

    with open(tool_dir / SOFTWARE_NAMES_FILE, encoding="utf-8") as f:
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
# SERVICENOW LOOKUP
# ======================================================
def servicenow_lookup_with_fallback(
    name: str,
    catalog_id: str,
    base_url: str,
    auth: HTTPBasicAuth,
) -> List[dict]:

    def query(q):
        resp = requests.get(
            f"{base_url}/api/now/table/sc_cat_item",
            auth=auth,
            timeout=20,
            params={
                "sysparm_query": f"active=true^sc_catalogs={catalog_id}^nameLIKE{q}",
                "sysparm_fields": "name,short_description,description,u_installation_link,price,u_software_disposition,u_meta_data",
                "sysparm_limit": 50,
            },
        )
        resp.raise_for_status()
        return resp.json().get("result", [])

    # Primary search
    results = query(name)

    if results:
        return results

    # Fallback only if no result found
    corrected = autocorrect_name(name)

    if corrected.lower() != name.lower():
        return query(corrected)

    return []


# ======================================================
# RESPONSE MODELS
# ======================================================
class SoftwareEntry(BaseModel):
    name: str
    short_description: str = ""
    description: str = ""
    link: str = ""
    cost: str = ""
    disposition: str = ""
    meta_data: str = ""


class ResolveSoftwareResponse(BaseModel):
    valid_software: bool = False
    original_software: str = ""
    original_disposition: str = ""
    Valid_Software: List[SoftwareEntry] = Field(default_factory=list)
    ALT_Standard: List[SoftwareEntry] = Field(default_factory=list)


# ======================================================
# TOOL
# ======================================================
@tool(
    name="get_software_details",
    description="Check if software exists in ServiceNow catalog",
    permission=ToolPermission.ADMIN,
    expected_credentials=[
        {
            "app_id": SNOW_CONNECTION,
            "type": ConnectionType.BASIC_AUTH
        }
    ]
)
def resolve_software_and_disposition(
    software_name: str,
    catalog_id: str = DEFAULT_CATALOG_ID,
) -> ResolveSoftwareResponse:

    # Get credentials from Orchestrate
    creds = connections.basic_auth(SNOW_CONNECTION)

    base_url = creds.url.rstrip("/")

    response = ResolveSoftwareResponse(
        original_software=software_name
    )

    # --------------------------------------------------
    # SERVICENOW SEARCH
    # --------------------------------------------------
    sn_results = servicenow_lookup_with_fallback(
        software_name,
        catalog_id,
        base_url,
        HTTPBasicAuth(creds.username, creds.password),
    )

    # --------------------------------------------------
    # FOUND
    # --------------------------------------------------
    if sn_results:
        response.valid_software = True

        response.original_disposition = sn_results[0].get(
            "u_software_disposition",
            "Available in Catalog"
        )

        seen = set()

        for sw in sn_results:
            name_key = sw.get("name", "").strip().lower()

            if name_key in seen:
                continue

            seen.add(name_key)

            response.Valid_Software.append(
                SoftwareEntry(
                    name=sw.get("name", ""),
                    short_description=sw.get("short_description", ""),
                    description=sw.get("description", ""),
                    link=sw.get("u_installation_link", ""),
                    cost=sw.get("price", ""),
                    disposition=sw.get("u_software_disposition", ""),
                    meta_data=sw.get("u_meta_data", ""),
                )
            )

        return response

    # --------------------------------------------------
    # NOT FOUND
    # --------------------------------------------------
    response.valid_software = False
    response.original_disposition = "Not Available in Catalog"

    return response


# ======================================================
# LOCAL TEST
# ======================================================
'''
if __name__ == "__main__":
    from pprint import pprint

    result = resolve_software_and_disposition("CircleCI Enterprise")
    pprint(result)
'''
