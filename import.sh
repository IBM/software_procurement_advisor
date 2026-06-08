# Create connection
orchestrate connections add -a ServiceNow_Auth

# Configure Draft Environment
orchestrate connections configure \
  -a ServiceNow_Auth \
  --env draft \
  --kind basic \
  --type team

# Set Draft Credentials
orchestrate connections set-credentials \
  -a ServiceNow_Auth \
  --env draft \
  -u <servicenow_username> \
  -p <servicenow_password>

# Configure Live Environment
orchestrate connections configure \
  -a ServiceNow_Auth \
  --env live \
  --kind basic \
  --type team

# Set Live Credentials
orchestrate connections set-credentials \
  -a ServiceNow_Auth \
  --env live \
  -u <servicenow_username> \
  -p <servicenow_password>

# Verify Connections
orchestrate connections list

# Import NSR ServiceNow Request Tool
orchestrate tools import \
  -k python \
  -f tools/CreateNSRServiceNowRequest/service_now_request_creation_new.py \
  -p tools/CreateNSRServiceNowRequest \
  --app-id ServiceNow_Auth

# Import Software Recommendation Tool
orchestrate tools import \
  -k python \
  -f tools/recommend_software_by_functionality/get_software_recommendations.py \
  -p tools/recommend_software_by_functionality \
  --app-id ServiceNow_Auth

# Import Software Details Tool
orchestrate tools import \
  -k python \
  -f tools/get_software_details/get_software_details.py \
  -p tools/get_software_details \
  --app-id ServiceNow_Auth

# Import NSR Workflow
orchestrate tools import \
  -k flow \
  -f tools/NSR_workflow_1418uw/NSR_workflow_1418uw.json

# Import Software Procurement Advisor Agent
orchestrate agents import \
  -f agents/native/Software_Procurement_Advisor_6689eB.yaml
