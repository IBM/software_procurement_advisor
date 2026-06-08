import requests
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field

from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from ibm_watsonx_orchestrate.run import connections
from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType

# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------
CONNECTION_SNOW = "ServiceNow_Auth"
CATALOG_ITEM_SYS_ID = "3d3aedb383ec435023fc7fc6feaad337"


# ---------------------------------------------------------
# NORMALIZATION HELPERS
# ---------------------------------------------------------
def bool_to_yes_no(value: Optional[bool], default: str = "No") -> str:
    """Boolean → ServiceNow Yes/No"""
    if value is None:
        return default
    return "Yes" if value else "No"


def ensure_string(value: Optional[str], default: str = "NA") -> str:
    return value if value else default


# ---------------------------------------------------------
# INPUT SCHEMA — 8 REQUIRED FIELDS
# ---------------------------------------------------------
class NSRRequestInput(BaseModel):
    software: str = Field(..., description="Software name")
    website: Optional[str] = Field("NA", description="Software website URL")
    urgency: Optional[str] = Field("3 - Moderate", description="Urgency level (1 - Critical, 2 - High, 3 - Moderate, 4 - Low)")
    subscription: Optional[str] = Field("NA", description="Subscription type or plan")
    features: Optional[str] = Field("NA", description="Key features of the software")
    no_of_users: Optional[int] = Field(0, description="Number of users/licenses needed")
    date: Optional[datetime] = Field(None, description="Required date or timeline")
    hardware_required: Optional[str] = Field("No", description="Is hardware required? (Yes/No)")

class NSRResponse(BaseModel):
    request_number: str
    sys_id: str
    status: str = "Submitted"


# ---------------------------------------------------------
# TOOL — CREATE NSR REQUEST WITH BASIC AUTH
# ---------------------------------------------------------
@tool(
    permission=ToolPermission.READ_WRITE,
    expected_credentials=[
        {"app_id": CONNECTION_SNOW, "type": ConnectionType.BASIC_AUTH}
    ]
)
def CreateNSRServiceNowRequest(nsr_params: NSRRequestInput) -> str:
    """Creates a ServiceNow Non-Standard Software Request (NSR) with only 4 required parameters."""

    creds = connections.basic_auth(CONNECTION_SNOW)
    base_url = creds.url
    username = creds.username
    password = creds.password

    #base_url = "https://dev285892.service-now.com"
    #username = "admin"
    #password = "cuQAha7W6$N-"

    url = (
        f"{base_url}/api/sn_sc/servicecatalog/items/"
        f"{CATALOG_ITEM_SYS_ID}/order_now"
    )

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    raw = nsr_params
    # ---------------- ALL 8 REQUIRED VARIABLES ----------------
    # Format date if provided
    date_value = raw.get("date")
    if isinstance(date_value, datetime):
        date_str = date_value.strftime("%Y-%m-%d")
    elif date_value:
        date_str = str(date_value)
    else:
        date_str = "NA"
    
    variables = {
        "software": ensure_string(raw.get("software")),
        "website": ensure_string(raw.get("website")),
        "urgency": ensure_string(raw.get("urgency"), "3 - Moderate"),
        "subscription": ensure_string(raw.get("subscription")),
        "u_features": ensure_string(raw.get("features")),
        "num_licenses": str(raw.get("no_of_users", 0)),
        "date": date_str,
        "hardware_required": ensure_string(raw.get("hardware_required"), "No"),
    }

    payload = {
        "sysparm_quantity": "1",
        "sysparm_requested_for": "04025500c3a106d0060a303a05013109",
        "sysparm_no_validation": "true",
        "variables": variables,
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        auth=(username, password)
    )
    response.raise_for_status()

    body = response.json()
    if "result" not in body:
        raise RuntimeError(f"Unexpected ServiceNow response: {body}")

    result = body["result"]

    return NSRResponse(
        request_number=result["request_number"],
        sys_id=result["sys_id"]
    ).model_dump_json()

# Example usage (commented out)
'''
def main():
    # ---- SAMPLE INPUT WITH ALL 8 VARIABLES ----
    from datetime import datetime
    
    nsr_input = NSRRequestInput(
        software="Adobe Creative Cloud",
        website="https://www.adobe.com",
        urgency="2 - High",
        subscription="Annual",
        features="Photo editing, Video editing, Graphic design",
        no_of_users=10,
        date=datetime(2026, 6, 1),  # datetime object
        hardware_required="Yes"  # String "Yes" or "No"
    )

    # ---- CALL TOOL ----
    try:
        response = CreateNSRServiceNowRequest(nsr_input)
        print("ServiceNow Response:")
        print(response)
    except Exception as e:
        print("Error while creating NSR:")
        print(e)


if __name__ == "__main__":
    main()
'''
