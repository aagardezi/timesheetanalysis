import time
import traceback
import os
import streamlit as st
from streamlit_float import *
from streamlit_google_auth import Authenticate
from streamlit_pills import pills
import vertexai
# from vertexai.generative_models import FunctionDeclaration, GenerativeModel, Tool, Part, FinishReason, SafetySetting
from google import genai
from google.genai import types
from google.cloud import bigquery

import logging
import json

from tenacity import retry, wait_random_exponential

import helperbqfunction

import gemini20functionfinhub
import gemini20functiongeneral
import gemini20functionalphavantage
import gemini20functionshareprice
import gemini20functiontimesheet

import helperfinhub
import helperalphavantage
import helpercode
import helperstreamlit
import helpersharepricefunction
import helpertimesheetdata


import gemini20handler


from google.cloud import pubsub_v1



BIGQUERY_DATASET_ID = "lseg_data_normalised"
PROJECT_ID = helpercode.get_project_id()
LOCATION = "us-central1"
USE_AUTHENTICATION = os.getenv('USEAUTH', True)==True
TOPIC_ID = os.getenv('TOPICID', "marketmind-async-topic")

HELP = """You can use the this to create an analyst report for US stocks and companies.
The Gemini based agent uses finhub.io to access their data API via tools and analyse the data to create the report.
Once you generate the report you can chat with the data/responses or ask to create a new report. 
The reports can also be compared and summarised. You can ask a full question or just the symbol for a company (GOOGL / META). 
For example you can ask the following
* Can you create an analyst report for the company ALPHABET INC-CL A that includes basic financials, company news for the year 2024 and
company profile . Include the actual numbers as well. Include a summary of the analysis as well.
* Can you create an analyst report for the company META
* Can you compare the above analyst reprots and give me a sumary list pros and cons with a rating (Buy, Sell, Hold)

or

* GOOGL for the last 6 months
* META for the last 6 months"""

#logging initialised
helpercode.init_logging()
logger = logging.getLogger("MarketMind")


stringoutputcount = 0

@st.dialog("Choose the Model")
def select_model():
    logger.warning("Selecting Model")
    modelname = st.selectbox(
        "Select the Gemini version you would like to use",
        ( "gemini-2.5-flash","gemini-2.5-pro"),
        index=0,
        placeholder="Select a Model",
    )
    if st.button("Choose Model"):
        logger.warning(f"""Button pressed, model selected: {modelname}""")
        st.session_state.modelname = modelname
        st.rerun()

@st.dialog("View System Instructions", width="large")
def view_systeminstruction():
    logger.warning("Viewing System Instruction")
    st.markdown(SYSTEM_INSTRUCTION.replace('\t', ''))

@st.dialog("View help", width="large")
def view_help():
    logger.warning("Viewing Help")
    st.markdown(HELP)

def on_async_change():
    logger.warning("Async change detected")
    init_chat_session(st.session_state.gemini20, st.session_state.gemini15)
    logger.warning(f"Async status: {st.session_state.asyncagent}")
    if st.session_state.asyncagent:
        logger.warning("Setting up the publisher")
        logger.warning(f"Topic ID: {TOPIC_ID}")
        st.session_state.publisher = pubsub_v1.PublisherClient()
        st.session_state.topic_path = st.session_state.publisher.topic_path(PROJECT_ID, TOPIC_ID)



def handle_external_function(api_requests_and_responses, params, function_name):
    """This function handesl the call to the external function once Gemini has determined a function call is required"""
    if function_name in helpercode.function_handler.keys():
        logger.warning("General function found")
        api_response = helpercode.function_handler[function_name]()
        api_requests_and_responses.append(
                                [function_name, params, api_response]
                        )

    if function_name in helperbqfunction.function_handler.keys():
        logger.warning("BQ function found")
        api_response = helperbqfunction.function_handler[function_name](st.session_state.client, params)
        api_requests_and_responses.append(
                                [function_name, params, api_response]
                        )

    if function_name in helperfinhub.function_handler.keys():
        logger.warning("finhub function found")
        api_response = helperfinhub.function_handler[function_name](params)
        api_requests_and_responses.append(
                                [function_name, params, api_response]
                        )
    
    if function_name in helperalphavantage.function_handler.keys():
        logger.warning("alpha vantage function found")
        api_response = helperalphavantage.function_handler[function_name](params)
        api_requests_and_responses.append(
                                [function_name, params, api_response]
                        )
    
    if function_name in helpersharepricefunction.function_handler.keys():
        logger.warning("share proce function found")
        api_response = helpersharepricefunction.function_handler[function_name](params)
        api_requests_and_responses.append(
                                [function_name, params, api_response]
                        )
    
    if function_name in helpertimesheetdata.function_handler.keys():
        logger.warning("timesheet data function found")
        api_response = helpertimesheetdata.function_handler[function_name]()
        api_requests_and_responses.append(
                                [function_name, params, api_response]
                        )
    
                
    return api_response



def display_restore_messages(logger):
    logger.warning("Checking if messages to restore")
    md5cache = []
    for message in st.session_state.messages:
        logger.warning("Restoring messages")
        if message["role"] in ["assistant"]:
            if(message["md5has"] not in md5cache):
                md5cache.append(message["md5has"])
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
            else:
                logger.warning("Message already restored, ignoring")
        else:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    logger.warning("Messages restored")

# market_query_tool = Tool(
#     function_declarations=[
#         geminifunctionsbq.sql_query_func,
#         geminifunctionsbq.list_datasets_func,
#         geminifunctionsbq.list_tables_func,
#         geminifunctionsbq.get_table_func,
#         geminifunctionsbq.sql_query_func,
#         geminifunctionfinhub.symbol_lookup,
#         geminifunctionfinhub.company_news,
#         geminifunctionfinhub.company_profile,
#         geminifunctionfinhub.company_basic_financials,
#         geminifunctionfinhub.company_peers,
#         geminifunctionfinhub.insider_sentiment,
#         geminifunctionfinhub.financials_reported,
#         geminifunctionfinhub.sec_filings,
#     ],
# )

market_query20_tool = types.Tool(
    function_declarations=[
        # geminifunctionsbq.sql_query_func,
        # geminifunctionsbq.list_datasets_func,
        # geminifunctionsbq.list_tables_func,
        # geminifunctionsbq.get_table_func,
        # geminifunctionsbq.sql_query_func,
        # gemini20functionfinhub.symbol_lookup,
        # gemini20functionfinhub.company_news,
        # gemini20functionfinhub.company_profile,
        # gemini20functionfinhub.company_basic_financials,
        # gemini20functionfinhub.company_peers,
        # gemini20functionfinhub.insider_sentiment,
        # gemini20functionfinhub.financials_reported,
        # gemini20functionfinhub.sec_filings,
        # gemini20functiongeneral.current_date,
        # gemini20functionshareprice.shareprice,
        gemini20functiontimesheet.get_timesheet_data
        # gemini20functionalphavantage.monthly_stock_price,
        # gemini20functionalphavantage.market_sentiment,
    ], code_execution=type.ToolCodeExecution()
)

TEMP_INSTRUCTION = f"""lseg tick history data and uses RIC and ticker symbols to analyse stocks
                        When writing SQL query ensure you use the Date_Time field in the where clause.
                        {PROJECT_ID}.{BIGQUERY_DATASET_ID}.lse_normalised table is the main trade table
                        RIC is the column to search for a stock
                        When accessing news use the symbol for the company instead of the RIC cod.
                        If a function call reqires a date range and one is not supplied always use the current year.
                        In order to get the right date use the current_date function."""

# SYSTEM_INSTRUCTION = """You are a financial analyst that understands financial data. Do the analysis like and asset management 
#                             investor and create a detaild report
#                             You can lookup the symbol using the symbol lookup function. Make sure to run the symbol_lookup 
#                             before any subsequent functions.
#                             When doing an analysis of the company, include the company profile, company news, 
#                             company basic financials and an analysis of the peers
#                             Also get the insider sentiment and add a section on that. Include a section on SEC filings. If a tool 
#                             requires a data and its not present the use the current year
#                             If a function call reqires a date range and one is not supplied always use the current year.
#                             In order to get the right date use the current_date function.
#                             Once you have the current date, use it to determine the start and end date for the year.
#                             Use those as the start and end dates in fuction calls where the user has not supplied a date range.
#                             When identifing a symbol for a company from a list of symbols make sure its a primary symbol.
#                             Usually primary symbols dont have a dot . in the name"""

SYSTEM_INSTRUCTION = """Gemini 2.5 System Instruction: Brevan Howard Timesheet Analysis Engine (Internal Tool)

Version: 1.0
Date: 2023-10-27
Purpose: To provide accurate, actionable, and compliant insights from employee timesheet data for Brevan Howard internal operations and HR analysis.
1. Role and Persona

You are "Chronos AI," a highly specialized, analytical assistant dedicated to processing and interpreting Brevan Howard's employee timesheet data. Your operational context is strictly internal, supporting HR, Operations, and Management teams in understanding timesheet compliance, efficiency, and organizational patterns. You are designed for precision, confidentiality, and clarity, operating with the highest standards of data integrity.
2. Core Objective

Your primary objective is to transform raw timesheet records into meaningful, actionable insights regarding:

    Timeliness of submissions (on-time, late, severity of lateness).
    Overall timesheet status and compliance.
    Identification of trends, anomalies, and areas for operational improvement.
    General statistical summaries of timesheet activity.

3. Input Data Structure

You will call the function get_timesheet_data to get the data.

The function call will return a markup data set. this is based on the pandas data frame. 

You will receive timesheet data as a markup data set from the above function call, where each record represents a distinct timesheet action or status. The fields available for analysis are precisely defined as follows:

    TimesheetStartDate (Date): The start date of the reporting period for the timesheet.
    TimesheetEndDate (Date): The end date of the reporting period for the timesheet. This is the target date for on-time submission.
    TimesheetOwner (String): The name of the employee who owns the timesheet.
    TimesheetOwnerEmail (String): The email address of the timesheet owner.
    ActionByUser (String): The name of the user who performed the Action.
    ActionByUserEmail (String): The email address of the user who performed the Action.
    Action (String): The specific action performed on the timesheet (e.g., 'Submitted', 'Approved', 'Rejected', 'Recalled', 'Saved', 'Pending Approval').
    ActionDate (Datetime): The date and time when the Action was performed.
    ProjectName (String): The name of the project associated with the timesheet entry.
    ProjectNumber (String): The unique identifier for the project.
    ClientName (String): The name of the client associated with the project.
    HasAttestation (Boolean): Indicates if the timesheet includes an attestation (True/False).
    OldStatus (String): The status of the timesheet before the Action.
    NewStatus (String): The current/new status of the timesheet after the Action.
    FullName (String): The full name of the employee associated with the record (could be owner or actioner).
    EmailAddress (String): The email address of the employee associated with the record.
    Employee (String): A general employee identifier or name.
    TimesheetApprover (String): The name of the employee responsible for approving this timesheet.
    Status (String): The overall current status of the timesheet (e.g., 'Approved', 'Pending', 'Rejected', 'Draft').
    Division (String): The organizational division of the employee (TimesheetOwner).
    Security (String): Security clearance or group (if applicable).

4. Key Analytical Capabilities & Definitions

You must be able to perform the following analyses based on user queries, providing precise definitions for all metrics:
4.1. Timesheet Timeliness Analysis

    On-Time Submission: A timesheet is considered "on-time" if the ActionDate for the Action 'Submitted' is on or before the TimesheetEndDate.
        Calculation: ActionDate <= TimesheetEndDate where Action == 'Submitted'.
    Late Submission: A timesheet is considered "late" if the ActionDate for the Action 'Submitted' is after the TimesheetEndDate.
        Calculation: ActionDate > TimesheetEndDate where Action == 'Submitted'.
    Lateness Calculation (Days): For late submissions, calculate the number of days (and optionally hours if precision allows) between TimesheetEndDate and the ActionDate for the Action 'Submitted'.
        Calculation: (ActionDate - TimesheetEndDate) in days, rounded up to the nearest full day for reporting. E.g., 23 hours late = 1 day late. 1 day 1 hour late = 2 days late.
    Average Lateness: The average number of late days across a specified group (e.g., by division, by employee, per period).
    Submission Rate: Percentage of timesheets submitted vs. expected for a period/group.

4.2. Timesheet Status & Compliance Analysis

    Status Distribution: Count of timesheets in 'Approved', 'Pending', 'Rejected', 'Draft', 'Recalled' status.
    Approval Rates: Percentage of submitted timesheets that reach 'Approved' status within a defined timeframe or overall.
    Rejection Rates: Percentage of submitted timesheets that reach 'Rejected' status.
    Attestation Compliance: Percentage of submitted timesheets that have HasAttestation as True.
    Approver Performance: Analyze average approval time for TimesheetApprover and identify potential bottlenecks (e.g., number of pending approvals per approver, average time to approve).

4.3. General Timesheet Overview & Trends

    Volume Analysis: Total number of timesheet actions, submissions, or approvals within a specified period.
    Division/Employee Performance: Compare timeliness, approval rates, and overall compliance across divisions or for individual employees (anonymized in summary, specific if requested for action).
    Project/Client Activity: Identify projects or clients with high timesheet activity, or specific submission patterns.
    Anomaly Detection: Identify unusual spikes, drops, or consistent deviations from norms in submission patterns or lateness.

5. Output Guidelines

Your output must be:

    Clear and Concise: Present information in an easy-to-understand manner.
    Structured: Utilize Markdown for tables, bullet points, and headings to organize insights. For raw data aggregations or detailed lists, JSON format is preferred.
    Actionable: Highlight key findings, trends, and potential areas for improvement.
    Contextual: Refer back to Brevan Howard's operational context.
    Confidential: NEVER disclose raw, personally identifiable information (PII) of employees unless explicitly requested for a specific analytical purpose (e.g., "List employees who were late 3+ times last quarter"). Aggregate data and report on trends or statistics whenever possible. Grouping and anonymization is preferred for general reports.

6. Operational Directives & Constraints

    Data Privacy and Security (PARAMOUNT):
        Treat all input data as highly confidential and internal to Brevan Howard.
        Do not store or retain specific input data beyond the immediate processing of a query.
        Do not share any information derived from the data externally.
        Prioritize aggregation and statistical summaries over individual employee details in general reports.
        When listing individual data points (e.g., "list late submissions"), ensure the request is legitimate and the context is internal analysis.
    Accuracy and Precision: All calculations must be numerically precise. Rounding rules (e.g., for days late) must be consistently applied as defined above.
    Assumptions:
        The TimesheetEndDate is the de facto due date for timesheet submissions.
        The ActionDate corresponding to the Action 'Submitted' is the timestamp for submission.
    Error Handling:
        If input data is malformed or critical fields are missing, clearly state the issue and explain that the analysis may be incomplete or impossible.
        If a request is ambiguous, ask clarifying questions.
    Scope: Stay strictly within the domain of timesheet analysis. Do not engage in general conversation, provide investment advice, or discuss non-timesheet related topics.
    Efficiency: Process queries efficiently and provide timely responses.
    Tone: Professional, objective, and analytical.

7. Example Interactions (Internal thought process for expected queries)

    User Query: "Show me the top 5 employees with the highest average lateness in timesheet submission for the past quarter, alongside their average lateness in days."
        Chronos AI Response: Identifies relevant 'Submitted' actions, calculates lateness for each, averages per employee, sorts, and presents in a Markdown table.
    User Query: "Provide a summary of timesheet approval statuses by division for the current active period."
        Chronos AI Response: Aggregates counts of 'Approved', 'Pending', 'Rejected' etc., by Division and Status, presents in a Markdown table.
    User Query: "Identify any projects that have a unusually high number of 'Rejected' timesheets in the last month."
        Chronos AI Response: Analyzes ProjectName and NewStatus for 'Rejected' actions, identifies outliers, and lists them with counts.

By adhering to these instructions, Chronos AI will serve as an invaluable tool for Brevan Howard's operational efficiency and compliance monitoring related to timesheet management.
                        """

TEMP_SYSTEM_INSTRUCTION = """
                            When creating the report also inlcude a seciton on market sentiment (accessed via a tool) and 
                            use the monthly stock prices (obtained via a tool) and review it as part of the analysis"""

PROMPT_ENHANCEMENT = """ """

generation_config = {
    "max_output_tokens": 8192,
    "temperature": 1,
    "top_p": 0.95,
}

generate_config_20 = types.GenerateContentConfig(
    temperature = 1,
    top_p = 0.95,
    max_output_tokens = 8192,
    response_modalities = ["TEXT"],
    safety_settings = [types.SafetySetting(
      category="HARM_CATEGORY_HATE_SPEECH",
      threshold="OFF"
    ),types.SafetySetting(
      category="HARM_CATEGORY_DANGEROUS_CONTENT",
      threshold="OFF"
    ),types.SafetySetting(
      category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
      threshold="OFF"
    ),types.SafetySetting(
      category="HARM_CATEGORY_HARASSMENT",
      threshold="OFF"
    )],
    system_instruction=[types.Part.from_text(text=SYSTEM_INSTRUCTION)],
    tools= [market_query20_tool],
)

# safety_settings = [
#     SafetySetting(
#         category=SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
#         threshold=SafetySetting.HarmBlockThreshold.OFF
#     ),
#     SafetySetting(
#         category=SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
#         threshold=SafetySetting.HarmBlockThreshold.OFF
#     ),
#     SafetySetting(
#         category=SafetySetting.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
#         threshold=SafetySetting.HarmBlockThreshold.OFF
#     ),
#     SafetySetting(
#         category=SafetySetting.HarmCategory.HARM_CATEGORY_HARASSMENT,
#         threshold=SafetySetting.HarmBlockThreshold.OFF
#     ),
# ]


def handle_api_response(message_placeholder, api_requests_and_responses, backend_details):
    backend_details += "- Function call:\n"
    backend_details += (
                        "   - Function name: ```"
                        + str(api_requests_and_responses[-1][0])
                        + "```"
                    )
    backend_details += "\n\n"
    backend_details += (
                        "   - Function parameters: ```"
                        + str(api_requests_and_responses[-1][1])
                        + "```"
                    )
    backend_details += "\n\n"
    backend_details += (
                        "   - API response: ```"
                        + str(api_requests_and_responses[-1][2])
                        + "```"
                    )
    backend_details += "\n\n"
    with message_placeholder.container():
        st.markdown(backend_details)
    return backend_details







def authenticate_user(logger, PROJECT_ID, USE_AUTHENTICATION):
    logger.warning(f"""Auth as bool is set to {USE_AUTHENTICATION}""")
    logger.warning(f"""Auth as string is set to {os.getenv('USEAUTH')}""")

    authenticator = Authenticate(
        secret_credentials_path=helpercode.create_temp_credentials_file(helpercode.access_secret_version(PROJECT_ID, "AssetMPlatformKey")),
        cookie_name='logincookie',
        cookie_key='this_is_secret',
        redirect_uri='https://marketmind-884152252139.us-central1.run.app/',
    )

    # if not st.session_state.get('connected', False):
    #     authorization_url = authenticator.get_authorization_url()
    #     st.markdown(f'[Login]({authorization_url})')
    #     st.link_button('Login', authorization_url)

    logger.warning(f"""Connected status is {st.session_state['connected']} and use auth is {USE_AUTHENTICATION}""")

    clientinfo = helperstreamlit.get_remote_ip()
    logger.warning(f"""Client info is {clientinfo}""")


    authstatus = ((not st.session_state['connected']) and ( USE_AUTHENTICATION))


    logger.warning(f"""final auth status is {authstatus}""")

    if authstatus:
        logger.warning("Auth Starting")
        time.sleep(5)
        authenticator.check_authentification()
        st.logo("images/chronosailogo.png")
    # Create the login button
        authenticator.login()
    return authenticator


def get_chat_history():
    messages = []
    messageicon = []
    for message in st.session_state.messages:
        if message["role"] in ["user"]:
            messages.append(message['content'][:15])
            messageicon.append('➕')
    if len(messages) > 0:
        with st.sidebar:
            pills("Chat History", messages, messageicon)

def init_chat_session(client):
    st.session_state.messages = []
    st.session_state.sessioncount = 0
    st.session_state.client = bigquery.Client(project="genaillentsearch")
    st.session_state.chat = client
    st.session_state.aicontent = []
    # st.session_state.chat15 = model.start_chat()


def display_sidebar(logger, view_systeminstruction, USE_AUTHENTICATION, get_chat_history, init_chat_session, authenticator):
    with st.sidebar:
        st.logo("images/chronosailogo.png")
        if USE_AUTHENTICATION:
            st.image(st.session_state['user_info'].get('picture'))
            if st.button('Log out'):
                authenticator.logout()
        st.header("ChronosAI")
        st.toggle("Async Agent",False, on_change=on_async_change, key="asyncagent")
        get_chat_history()
        if st.button("Start new Chat"):
            init_chat_session(st.session_state.gemini20, st.session_state.gemini15)
            st.rerun()
        st.header("Debug")

        if st.button("Help"):
            view_help()
        if st.button("Reload"):
            pass
        if st.button("System Instruction"):
            view_systeminstruction()
            
        st.session_state.sessioncount = st.session_state.sessioncount +1
        logger.warning(f"""Session count is {st.session_state.sessioncount}""")
        st.text(f"""#: {st.session_state.sessioncount}""")
        st.text(f"AsyncAgent: {st.session_state.asyncagent}")

def serialise_message(aicontent):
    returndata = []
    logger.warning("priting aicontent")
    logger.warning(aicontent)
    logger.warning("priting aicontent done")
    for item in aicontent:
        returndata.append({
            "role": item.role,
            "content": item.parts[0].text
        })
    
    testing_data = []
    for item in returndata:
        testing_data.append(types.Content(role=item["role"], parts=[types.Part(text=item["content"])]))
    
    logger.warning("priting testing_data")
    logger.warning(testing_data)
    logger.warning("priting testing_data done")

    return json.dumps(returndata).encode("utf-8")   

def send_async_gemini_message(prompt):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.aicontent.append(types.Content(role='user', parts=[types.Part(text=prompt+PROMPT_ENHANCEMENT )]))
    future = st.session_state.publisher.publish(st.session_state.topic_path,
                                        serialise_message(st.session_state.aicontent),
                                        model = st.session_state.modelname.encode("utf-8"),
                                        session_id = st.session_state.session_id,
                                        prompt = prompt.encode("utf-8"))
    st.session_state.aysncmessagesent = True
                
    logger.warning(f"Published message, status: {future.result()}")


st.set_page_config(layout="wide")
# st.set_page_config()
float_init(theme=True, include_unstable_primary=False)

authenticator = authenticate_user(logger, PROJECT_ID, USE_AUTHENTICATION)

if st.session_state['connected'] or not USE_AUTHENTICATION:

    if "modelname" not in st.session_state:
        logger.warning("model name session state not initialised")
        # st.session_state.modelname = "gemini-1.5-pro-002"
        select_model()
        # logger.warning(f"""In initialiser function model name is {st.session_state.modelname}""")
    else:
        logger.warning(f"""model name session state initialised and it is: {st.session_state.modelname}""")
        if "chatstarted" not in st.session_state:
            #Gemini 2 client
            client = genai.Client(
                vertexai=True,
                project=PROJECT_ID,
                location=LOCATION
            )

            #Gemini1.5 Client
            # vertexai.init(project=PROJECT_ID, location=LOCATION)
            # model = GenerativeModel(
            #     # "gemini-1.5-pro-002",
            #     st.session_state.modelname,
            #     system_instruction=[SYSTEM_INSTRUCTION],
            #     tools=[market_query_tool],
            # )
            # st.session_state.gemini15 = model
            st.session_state.gemini20 = client
            init_chat_session(client)
            st.session_state.chatstarted = True
            if "session_id" not in st.session_state:
                st.session_state.session_id = str(uuid.uuid4())
                logging.warning(f"Session id created: {st.session_state.session_id}")
            

        # if "messages" not in st.session_state:
        #     st.session_state.messages = []
        # st.write(f"Hello, {st.session_state['user_info'].get('name')}")
        display_sidebar(logger, view_systeminstruction, USE_AUTHENTICATION, get_chat_history, init_chat_session, authenticator)

        # if "modelname" not in st.session_state:
        #     logger.warning("model name session state not initialised")
        #     # st.session_state.modelname = "gemini-1.5-pro-002"
        #     select_model()
        #     # logger.warning(f"""In initialiser function model name is {st.session_state.modelname}""")
        # else:
        
        st.image("images/chronosailogo.png")
        if USE_AUTHENTICATION:
            st.title(f"""{st.session_state['user_info'].get('name')}! ChronosAI: built using {st.session_state.modelname}""")
        else:
            st.title(f"""ChronosAI: built using {st.session_state.modelname}""")
        
        st.caption(f"Currently only available for US Securities -- {helpercode._get_session().id}")

        # if "sessioncount" not in st.session_state:
        #     st.session_state.sessioncount = 0
        # else:
        # st.session_state.sessioncount = st.session_state.sessioncount +1
        
        # logger.warning(f"""Session count is {st.session_state.sessioncount}""")

        # with st.sidebar:
        #     st.text(f"""#: {st.session_state.sessioncount}""")

        # st.text(f"""Currently only available for US Securities {st.session_state.sessioncount}""")

        display_restore_messages(logger)
        
        
        # if "client" not in st.session_state:
        #     st.session_state.client = bigquery.Client(project="genaillentsearch")
        try:
            if prompt := st.chat_input("What is up?"):
                # # Display user message in chat message container
                with st.chat_message("user"):
                    st.markdown(prompt)
                if st.session_state.asyncagent:
                    send_async_gemini_message(prompt+PROMPT_ENHANCEMENT)
                    with st.chat_message("assistant"):
                        st.markdown("Message sent awaiting response...")
                else:
                    # if st.session_state.modelname.startswith("gemini-1.5"):
                    #     gemini15handler.handle_gemini15(prompt, logger, PROJECT_ID, LOCATION, PROMPT_ENHANCEMENT, 
                    #                                     generation_config, safety_settings, handle_api_response, handle_external_function)
                    # else:
                    gemini20handler.handle_gemini20(prompt, logger, PROJECT_ID, LOCATION, PROMPT_ENHANCEMENT, 
                                                    generate_config_20, handle_api_response, handle_external_function)
        except Exception as e:
            with st.chat_message("error",avatar=":material/chat_error:"):
                message_placeholder = st.empty()
                with message_placeholder.container():
                    with st.expander("Error message and stack trace"):
                        st.markdown(f"An error occurred: {e}")
                        st.markdown(traceback.format_exc())
                