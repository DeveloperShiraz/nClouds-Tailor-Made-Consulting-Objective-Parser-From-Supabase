import streamlit as st
import pandas as pd
import json
import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
st.set_page_config(page_title="CMMC Objective Parser", layout="wide")

# --- AWS Bedrock Setup ---
@st.cache_resource
def get_bedrock_clients():
    """Initializes AWS Bedrock clients."""
    try:
        session = boto3.Session(
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1")
        )
        bedrock_runtime = session.client("bedrock-runtime")
        bedrock_agent_runtime = session.client("bedrock-agent-runtime")
        return bedrock_runtime, bedrock_agent_runtime
    except Exception as e:
        st.error(f"Failed to initialize AWS clients: {e}")
        return None, None

bedrock_runtime, bedrock_agent_runtime = get_bedrock_clients()
KB_ID = os.getenv("BEDROCK_KB_ID")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

# --- Helper Functions ---
def retrieve_from_kb(query, tier, intent):
    """
    Retrieves information from Bedrock Knowledge Base with metadata filters.
    """
    if not bedrock_agent_runtime or not KB_ID:
        return "Knowledge Base configuration missing."

    print(f"DEBUG: Querying KB with filters - Tier: {tier}, Intent: {intent}") # Debug log

    # Construct retrieval configuration with filters
    retrieval_config = {
        "vectorSearchConfiguration": {
            "numberOfResults": 5
        }
    }
    
    # Add metadata filters if inferred
    filter_conditions = []
    if tier and tier.lower() != "none":
        filter_conditions.append({
            "equals": {
                "key": "tier",
                "value": tier
            }
        })
    if intent and intent.lower() != "none":
        filter_conditions.append({
            "equals": {
                "key": "intent",
                "value": intent
            }
        })
        
    if filter_conditions:
        if len(filter_conditions) > 1:
            retrieval_config["vectorSearchConfiguration"]["filter"] = {
                "andAll": filter_conditions
            }
        else:
            retrieval_config["vectorSearchConfiguration"]["filter"] = filter_conditions[0]

    try:
        response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=KB_ID,
            retrievalQuery={"text": query},
            retrievalConfiguration=retrieval_config
        )
        
        results = []
        for result in response.get("retrievalResults", []):
            results.append(result.get("content", {}).get("text", ""))
        
        return "\n\n".join(results) if results else "No relevant information found in Knowledge Base."
        
    except ClientError as e:
        return f"Error querying Knowledge Base: {e}"

def chat_with_bedrock(user_input):
    """
    Orchestrates the LLM chat with function calling for KB retrieval.
    """
    if not bedrock_runtime:
        return "AWS Bedrock client not initialized.", None, None

    # Define the tool (function) for the model
    tool_config = {
        "tools": [
            {
                "toolSpec": {
                    "name": "search_knowledge_base",
                    "description": "Search the CMMC knowledge base for information. You MUST infer the 'tier' (e.g., Level 1, Level 2) and 'intent' (e.g., policy, technical, generic) from the user's request to filter the search.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "The search query based on user input"},
                                "tier": {"type": "string", "description": "Inferred CMMC level/tier (e.g., 'Level 2'). Use 'None' if unclear."},
                                "intent": {"type": "string", "description": "Inferred intent (e.g., 'policy', 'technical'). Use 'None' if unclear."}
                            },
                            "required": ["query", "tier", "intent"]
                        }
                    }
                }
            }
        ]
    }

    # System prompt to guide the model
    system_prompts = [{"text": "You are a CMMC expert. Analyze the user's question. You MUST use the 'search_knowledge_base' tool to retrieve information. infer the 'tier' and 'intent' metadata from their question to pass to the tool. Start by calling the tool, then answer based on the results."}]

    messages = [{"role": "user", "content": [{"text": user_input}]}]

    try:
        # 1. Initial Call to Model (to trigger tool use)
        response = bedrock_runtime.converse(
            modelId=MODEL_ID,
            messages=messages,
            system=system_prompts,
            toolConfig=tool_config
        )
        
        output_message = response['output']['message']
        messages.append(output_message)
        
        inferred_tier = None
        inferred_intent = None

        # 2. Process Tool Requests
        if 'content' in output_message:
            for content_block in output_message['content']:
                if 'toolUse' in content_block:
                    tool_use = content_block['toolUse']
                    tool_name = tool_use['name']
                    tool_use_id = tool_use['toolUseId']
                    
                    if tool_name == 'search_knowledge_base':
                        tool_input = tool_use['input']
                        query = tool_input.get('query')
                        inferred_tier = tool_input.get('tier')
                        inferred_intent = tool_input.get('intent')
                        
                        # Execute the tool
                        tool_result = retrieve_from_kb(query, inferred_tier, inferred_intent)
                        
                        # Add tool result to messages
                        tool_result_message = {
                            "role": "user",
                            "content": [
                                {
                                    "toolResult": {
                                        "toolUseId": tool_use_id,
                                        "content": [{"json": {"result": tool_result}}]
                                    }
                                }
                            ]
                        }
                        messages.append(tool_result_message)

        # 3. Final Call to Model (to generate answer with tool results)
        final_response = bedrock_runtime.converse(
            modelId=MODEL_ID,
            messages=messages,
            system=system_prompts,
            toolConfig=tool_config
        )
        
        final_text = final_response['output']['message']['content'][0]['text']
        return final_text, inferred_tier, inferred_intent

    except ClientError as e:
        return f"Error processing request: {e}", None, None

# --- Data Loading ---
@st.cache_data
def load_data():
    """Loads CMMC data from JSON files."""
    try:
        # Get the directory of the current script
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        with open(os.path.join(base_dir, 'cmmc-practices.json'), 'r') as f:
            practices = json.load(f)
        
        with open(os.path.join(base_dir, 'cmmc-objectives.json'), 'r') as f:
            objectives = json.load(f)
            
        with open(os.path.join(base_dir, 'cmmc-assessments.json'), 'r') as f:
            assessments = json.load(f)
            
        return pd.DataFrame(practices), pd.DataFrame(objectives), pd.DataFrame(assessments)
    except FileNotFoundError as e:
        st.error(f"Error loading data files: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_practices, df_objectives, df_assessments = load_data()

# --- UI Layout ---

# Top Bar: Title and Org Selection
col1, col2 = st.columns([3, 1])

with col1:
    st.title("CMMC Objective Parser")

with col2:
    # "Org-id (dropdown)"
    # We extract unique Org IDs from the assessments table
    if not df_assessments.empty:
        org_ids = df_assessments['org_id'].unique().tolist()
        selected_org_id = st.selectbox("Organization ID", org_ids)
    else:
        st.warning("No Assessment Data Found")
        selected_org_id = None

st.divider()

# Main Content Area
if not df_practices.empty and not df_objectives.empty:
    
    # 1. Practice Selection
    # Format: "ID - Title" for readability
    practice_options = df_practices.apply(
        lambda x: f"{x['practice_id']} - {x['title']}", axis=1
    ).tolist()
    
    selected_practice_str = st.selectbox("Select Practice", practice_options)
    
    # Extract the practice_id string (e.g., "AC.L2-3.1.1") to filter objectives
    # We also need the internal UUID for the foreign key relationship
    if selected_practice_str:
        # Find the row corresponding to the selection
        selected_practice_row = df_practices[
            df_practices.apply(lambda x: f"{x['practice_id']} - {x['title']}", axis=1) == selected_practice_str
        ].iloc[0]
        
        practice_uuid = selected_practice_row['id']
        
        # 2. Objective Selection
        # Filter objectives based on the selected practice UUID
        filtered_objectives = df_objectives[df_objectives['practice_id'] == practice_uuid]
        
        if not filtered_objectives.empty:
            objective_options = filtered_objectives.apply(
                lambda x: f"{x['objective_code']} - {x['objective_text']}", axis=1
            ).tolist()
            selected_objective_str = st.selectbox("Select Objective", objective_options)
        else:
            st.info("No objectives found for this practice.")
            selected_objective_str = None

    # 3. User Question/Input
    user_input = st.text_input("User Question / Input", placeholder="Enter your question or input here...")

    # 4. Buttons
    btn_col1, btn_col2 = st.columns(2)
    
    with btn_col1:
        ask_help = st.button("Ask help", use_container_width=True)
        
    with btn_col2:
        validate = st.button("Validate", use_container_width=True)

    # 5. Answer/Output
    if ask_help:
        with st.spinner("Analyzing with Bedrock AI..."):
            response_text, tier, intent = chat_with_bedrock(user_input)
            
            st.markdown("### AI Analysis")
            st.markdown(f"**Inferred Tier:** `{tier}` | **Inferred Intent:** `{intent}`")
            st.info(response_text)
        
    if validate:
        st.success(f"**Validation**: Input '{user_input}' validated against '{selected_practice_str}'.")

else:
    st.error("Data could not be loaded. Please ensure JSON files are in the same directory.")
