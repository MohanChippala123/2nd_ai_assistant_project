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
with open("ai.json", "w") as f:
    json.dump(dict(gcp_credentials_dict), f)

credentials = service_account.Credentials.from_service_account_info(gcp_credentials_dict)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "ai.json"

# === GOOGLE CALENDAR AUTH === #
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
CLIENT_SECRETS_FILE = "client_secret.json"

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