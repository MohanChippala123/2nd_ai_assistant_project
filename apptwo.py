import os
import streamlit as st
from google.cloud import aiplatform, firestore
from vertexai.generative_models import GenerativeModel
from google.oauth2 import service_account
from datetime import datetime, date
import pandas as pd
import json

# Load GCP credentials from Streamlit secrets
gcp_credentials_dict = st.secrets["gcp_key"]
with open("gcp-key.json", "w") as f:
    json.dump(dict(gcp_credentials_dict), f)

# Explicitly set credentials for Vertex AI
credentials = service_account.Credentials.from_service_account_info(gcp_credentials_dict)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcp-key.json"

# === CONFIGURATION === #
PROJECT_ID = "hasini-gcp"
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

# === Streamlit UI === #
st.title("🧠 Personal AI Assistant")
st.caption("Manage tasks, see calendar summaries, and talk to Gemini AI!")

user_input = st.text_input("What do you want to ask Gemini?")
if st.button("Ask Gemini") and user_input:
    with st.spinner("Thinking..."):
        response = send_to_gemini(user_input)
        st.success(response)

# === Show Tasks === #
if st.expander("📋 Show My Tasks", expanded=False).checkbox("Show"):
    st.subheader("Your Tasks")
    tasks = get_tasks()
    for task in tasks:
        task_data = task.to_dict()
        st.markdown(f"- **{task_data['description']}** (Due: {task_data['due_date']})")

# === Add Task === #
with st.expander("➕ Add Task Manually", expanded=False):
    task_desc = st.text_input("Task Description")
    task_due = st.date_input("Due Date", min_value=date.today())
    if st.button("Add Task"):
        add_task(task_desc, str(task_due))
        st.success("Task added!")

# === Daily Summary === #
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