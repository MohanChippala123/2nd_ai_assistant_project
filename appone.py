import os
import streamlit as st
from google.cloud import aiplatform, firestore
from vertexai.generative_models import GenerativeModel
from google.oauth2 import service_account
from datetime import datetime, date
import pandas as pd
import json

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import pickle

# === GCP CREDENTIAL SETUP === #
gcp_credentials_dict = st.secrets["gcp_key"]
with open("gcp-key.json", "w") as f:
    json.dump(dict(gcp_credentials_dict), f)

credentials = service_account.Credentials.from_service_account_info(gcp_credentials_dict)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcp-key.json"

# === GOOGLE CALENDAR AUTH === #
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
CLIENT_SECRETS_FILE = "gcp-key.json"

def authenticate_google():
    if 'credentials' not in st.session_state:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri='http://localhost:8501/')
        auth_url, _ = flow.authorization_url(prompt='consent')
        st.markdown(f"[Click here to authenticate with Google Calendar]({auth_url})")
        code = st.text_input("Paste the code from the redirect URL:")
        if code:
            flow.fetch_token(code=code)
            creds = flow.credentials
            st.session_state['credentials'] = creds
            st.success("Authenticated successfully!")

def get_calendar_events():
    creds = st.session_state.get('credentials', None)
    if not creds:
        st.warning("Authenticate with Google Calendar to view events.")
        return []
    service = build('calendar', 'v3', credentials=creds)
    now = datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
        calendarId='primary', timeMin=now,
        maxResults=5, singleEvents=True,
        orderBy='startTime').execute()
    return events_result.get('items', [])

# === VERTEX AI CONFIG === #
PROJECT_ID = "second-ai-assistant"
LOCATION = "us-central1"
MODEL_NAME = "gemini-2.5-flash"

def setup_vertex():
    aiplatform.init(project=PROJECT_ID, location=LOCATION, credentials=credentials)

def send_to_gemini(prompt):
    setup_vertex()
    model = GenerativeModel(MODEL_NAME)
    response = model.generate_content(prompt)
    return response.text

# === FIRESTORE === #
firestore_client = firestore.Client(credentials=credentials, project=PROJECT_ID)
task_collection = firestore_client.collection("tasks")

def add_task(description, due_date):
    task_collection.add({
        "description": description,
        "due_date": due_date,
        "created_at": datetime.now()
    })

def get_tasks():
    return task_collection.order_by("due_date").stream()

def get_tasks_for_date(selected_date):
    return task_collection.where("due_date", "==", selected_date).stream()

# === STREAMLIT UI === #
st.title("🧠 Personal AI Assistant")
st.caption("Manage tasks, talk to Gemini, and view your Google Calendar!")

# === Gemini Section === #
user_input = st.text_input("What do you want to ask Gemini?")
if st.button("Ask Gemini") and user_input:
    with st.spinner("Thinking..."):
        response = send_to_gemini(user_input)
        st.success(response)

# === Tasks Section === #
if st.expander("📋 Show My Tasks", expanded=False).checkbox("Show"):
    st.subheader("Your Tasks")
    tasks = get_tasks()
    for task in tasks:
        task_data = task.to_dict()
        st.markdown(f"- **{task_data['description']}** (Due: {task_data['due_date']})")

with st.expander("➕ Add Task Manually", expanded=False):
    task_desc = st.text_input("Task Description")
    task_due = st.date_input("Due Date", min_value=date.today())
    if st.button("Add Task"):
        add_task(task_desc, str(task_due))
        st.success("Task added!")

with st.expander("📅 View Tasks for a Specific Date", expanded=False):
    selected_date = st.date_input("Select Date to View Tasks", min_value=date.today())
    if st.button("Get Reminders"):
        daily_tasks = get_tasks_for_date(str(selected_date))
        st.subheader(f"Tasks for {selected_date}")
        count = 0
        for task in daily_tasks:
            task_data = task.to_dict()
            st.markdown(f"- {task_data['description']}")
            count += 1
        if count == 0:
            st.info("No tasks found for this date.")

# === Google Calendar Events === #
with st.expander("📆 Google Calendar Events", expanded=False):
    authenticate_google()
    if 'credentials' in st.session_state:
        events = get_calendar_events()
        if events:
            st.subheader("Upcoming Events")
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                st.markdown(f"- **{event['summary']}** at {start}")
        else:
            st.info("No upcoming events found.")


'''
import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import os
import pickle
import datetime
import json

# Constants
SCOPES = ["https://www.googleapis.com/auth/calendar"]
CLIENT_SECRET_FILE = "client_secret.json"
TOKEN_FILE = "token.pkl"

def authenticate_user():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            credentials = pickle.load(token)
    else:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri="https://mohanvittal-second-ai-assistant.streamlit.app"
        )

        auth_url, _ = flow.authorization_url(prompt="consent")
        st.markdown(f"[Click here to authenticate with Google Calendar]({auth_url})")

        code = st.text_input("Paste the full redirect URL after logging in:")
        if code:
            try:
                # Extract the full code from the URL
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(code)
                query = parse_qs(parsed.query)
                full_code = query.get("code")[0]

                flow.fetch_token(code=full_code)
                credentials = flow.credentials

                with open(TOKEN_FILE, "wb") as token:
                    pickle.dump(credentials, token)
                st.success("Authenticated successfully!")
            except Exception as e:
                st.error(f"Authentication failed: {e}")
                return None
        else:
            return None
    return credentials

def list_calendar_events(credentials):
    service = build("calendar", "v3", credentials=credentials)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    events_result = service.events().list(
        calendarId='primary', timeMin=now,
        maxResults=10, singleEvents=True, orderBy='startTime').execute()

    events = events_result.get("items", [])
    if not events:
        st.info("No upcoming events found.")
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        st.write(f"- {start}: {event['summary']}")

# ==== Streamlit App ====
st.title("🔒 Google Calendar OAuth 2.0 Integration")

creds = authenticate_user()
if creds:
    st.success("You’re authenticated!")
    if st.button("Show my upcoming calendar events"):
        list_calendar_events(creds)


import os
import streamlit as st
from google.cloud import aiplatform, firestore
from vertexai.generative_models import GenerativeModel
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, date, timedelta
import pandas as pd
import json

# Load GCP credentials from Streamlit secrets
gcp_credentials_dict = st.secrets["gcp_key"]
with open("gcp-key.json", "w") as f:
    json.dump(dict(gcp_credentials_dict), f)

# Explicitly set credentials for Vertex AI and Google APIs
credentials = service_account.Credentials.from_service_account_info(gcp_credentials_dict)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "ai.json"

# === CONFIGURATION === #
PROJECT_ID = "second-ai-assistant"
LOCATION = "us-central1"
MODEL_NAME = "gemini-2.5-flash"

# === Setup Vertex === #
def setup_vertex():
    aiplatform.init(
        project=PROJECT_ID,
        location=LOCATION,
        credentials=credentials
    )

# === Vertex AI Gemini Function === #
def send_to_gemini(prompt):
    setup_vertex()
    model = GenerativeModel(MODEL_NAME)
    response = model.generate_content(prompt)
    return response.text

# === Firestore Setup === #
firestore_client = firestore.Client(credentials=credentials, project=PROJECT_ID)
task_collection = firestore_client.collection("tasks")

def add_task(description, due_date):
    task_collection.add({
        "description": description,
        "due_date": due_date,
        "created_at": datetime.now()
    })

def get_tasks():
    return task_collection.order_by("due_date").stream()

def get_tasks_for_date(selected_date):
    return task_collection.where("due_date", "==", selected_date).stream()

# === Google Calendar API Setup === #
SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'gcp-key.json'  # Your service account key file

def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    # IMPORTANT: To access a specific user's calendar, impersonate user:
    # creds = creds.with_subject('user@example.com')
    # Otherwise, calendar must be shared with service account email.

    service = build('calendar', 'v3', credentials=creds)
    return service

def list_upcoming_events(max_results=10):
    service = get_calendar_service()
    now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time

    events_result = service.events().list(
        calendarId='primary', timeMin=now,
        maxResults=max_results, singleEvents=True,
        orderBy='startTime').execute()
    events = events_result.get('items', [])

    return events

def add_event_to_calendar(summary, start_time, end_time):
    service = get_calendar_service()
    event = {
      'summary': summary,
      'start': {
        'dateTime': start_time.isoformat(),
        'timeZone': 'UTC',
      },
      'end': {
        'dateTime': end_time.isoformat(),
        'timeZone': 'UTC',
      },
    }

    created_event = service.events().insert(calendarId='primary', body=event).execute()
    return created_event.get('htmlLink')

# === Streamlit UI === #
st.title("🧠 Personal AI Assistant")
st.caption("Manage tasks, see calendar summaries, and talk to Gemini AI!")

# Gemini AI input
user_input = st.text_input("What do you want to ask Gemini?")
if st.button("Ask Gemini") and user_input:
    with st.spinner("Thinking..."):
        response = send_to_gemini(user_input)
        st.success(response)

# Show Firestore tasks
if st.expander("📋 Show My Tasks", expanded=False).checkbox("Show"):
    st.subheader("Your Tasks")
    tasks = get_tasks()
    for task in tasks:
        task_data = task.to_dict()
        st.markdown(f"- **{task_data['description']}** (Due: {task_data['due_date']})")

# Add Firestore task
with st.expander("➕ Add Task Manually", expanded=False):
    task_desc = st.text_input("Task Description", key="task_desc")
    task_due = st.date_input("Due Date", min_value=date.today(), key="task_due")
    if st.button("Add Task", key="add_task_btn"):
        if task_desc.strip() == "":
            st.error("Task description cannot be empty.")
        else:
            add_task(task_desc, str(task_due))
            st.success("Task added!")

# View tasks for a specific date
with st.expander("📅 View Tasks for a Specific Date", expanded=False):
    selected_date = st.date_input("Select Date to View Tasks", min_value=date.today(), key="view_date")
    if st.button("Get Reminders", key="get_reminders_btn"):
        daily_tasks = get_tasks_for_date(str(selected_date))
        st.subheader(f"Tasks for {selected_date}")
        count = 0
        for task in daily_tasks:
            task_data = task.to_dict()
            st.markdown(f"- {task_data['description']}")
            count += 1
        if count == 0:
            st.info("No tasks found for this date.")

# === Google Calendar Integration === #
with st.expander("📅 Google Calendar Events", expanded=False):
    if st.checkbox("Show my upcoming Google Calendar events"):
        try:
            events = list_upcoming_events()
            if not events:
                st.write("No upcoming events found.")
            else:
                for event in events:
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    st.write(f"- {start}: {event.get('summary', 'No Title')}")
        except Exception as e:
            st.error(f"Failed to fetch calendar events: {e}")

with st.expander("➕ Add Event to Google Calendar", expanded=False):
    event_summary = st.text_input("Event Title", key="event_summary")
    event_start = st.date_input("Start Date & Time", datetime.now(), key="event_start_date")
    event_start_time = st.time_input("Start Time", datetime.now().time(), key="event_start_time")
    event_end = st.date_input("End Date & Time", datetime.now() + timedelta(hours=1), key="event_end_date")
    event_end_time = st.time_input("End Time", (datetime.now() + timedelta(hours=1)).time(), key="event_end_time")

    # Combine date and time into datetime objects
    start_datetime = datetime.combine(event_start, event_start_time)
    end_datetime = datetime.combine(event_end, event_end_time)

    if st.button("Add Event to Google Calendar", key="add_event_btn"):
        if event_summary.strip() == "":
            st.error("Event title cannot be empty.")
        elif end_datetime <= start_datetime:
            st.error("End time must be after start time.")
        else:
            try:
                link = add_event_to_calendar(event_summary, start_datetime, end_datetime)
                st.success(f"Event created! [View it on Google Calendar]({link})")
            except Exception as e:
                st.error(f"Failed to add event: {e}")
                '''
