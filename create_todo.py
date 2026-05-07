import ollama
import json
import sys
import os
import re
import time
from datetime import datetime
from dotenv import load_dotenv
from notion import setup_notion_client, create_notion_event, query

from config import (
    Task_Notion_Name,
    Date_Notion_Name,
    ExtraInfo_Notion_Name,
    Folder_Notion_Name,
    EventType_Notion_Name,
)

# --- LOAD ENV ---
load_dotenv()

# --- CONFIG ---
NOTION_TOKEN_PATH = os.getenv(
    "NOTION_TOKEN_PATH", os.path.join(os.getcwd(), "notion_token.txt")
)
CREDENTIALS_LOCATION = os.getenv(
    "CREDENTIALS_LOCATION", os.path.join(os.getcwd(), "token.pkl")
)
DATA_SOURCE_ID = os.getenv("DATA_SOURCE_ID")
COURSES_DB_ID = os.getenv("COURSE_SOURCE_ID")

notion = setup_notion_client(NOTION_TOKEN_PATH)


# --- LLM LOGIC ---
def parse_prompt(prompt):
    # system_msg = f"""
    # You are a scheduling assistant. Extract data into JSON.
    # Current Time: {datetime.now().strftime("%Y-%m-%d %H:%M")}
    # Return ONLY JSON with keys: title, start, end, type, course.
    # 'type' must be: Assignment, Exam, Task, or Event.
    # 'course' is a code like PHYS 340, a project name or null.
    # """

    system_msg = f"""
    You are a strict JSON generator. 
    Current Time: {datetime.now().strftime("%Y-%m-%d %H:%M")}

    Rules:
    - Output ONLY valid JSON.
    - No conversational text or explanations.
    - Keys: "title", "start", "end", "type", "course", "notes".
    - "type" MUST be one of: ["📝 Task", "📔 Test", "✏ Assignments", "🖋 Exams", "📅 Events"].
    - Timestamps MUST be simple ISO 8601 strings (YYYY-MM-DDTHH:MM:SS).
    - If an end time is not required, leave as empty in "end" key.
    - Workday is from 9am to 5pm.
    - If no time is given assume today all day so no hour and minute in the timestamp.

    User Prompt: """

    response = ollama.generate(
        model="llama3", prompt=system_msg + f"\nPrompt: {prompt}", format="json"
    )
    return json.loads(response["response"])


# --- NOTION LOGIC ---
def get_course_id(course_code):
    if not course_code:
        return None

    # Simple search for the course code in your Course database
    query_result = query(
        notion, COURSES_DB_ID, {"property": "Name", "title": {"contains": course_code}}
    )

    return query_result[0]["id"] if query_result and len(query_result) > 1 else None


def get_local_offset():
    # Calculates the offset in seconds (e.g., -14400 for EDT)
    offset_sec = -time.timezone if (time.localtime().tm_isdst == 0) else -time.altzone
    # Converts to ISO format: -04:00
    hours = int(offset_sec / 3600)
    minutes = int((abs(offset_sec) % 3600) / 60)
    return f"{hours:+03d}:{minutes:02d}"


def clean_iso_string(timestamp):
    if not timestamp:
        return None

    # 1. Basic sanitization
    raw_ts = str(timestamp)[:19]
    clean_ts = re.sub(r"[^0-9T:-]", "", raw_ts)

    if len(clean_ts) < 10:
        return None

    # 2. Add the dynamic offset
    if "T" in clean_ts:
        # Standardize length to YYYY-MM-DDTHH:MM:SS
        if len(clean_ts) == 16:
            clean_ts += ":00"
        elif len(clean_ts) == 18:  # Fix for Phi-3 cutting off a digit
            clean_ts += "0"

        offset = get_local_offset()
        return f"{clean_ts}{offset}"

    return clean_ts


def create_entry(data):
    # 1. Safe extraction (no more KeyErrors)
    course_name = data.get("course")
    title = data.get("title", "New Task")
    event_type = data.get("type", "Task")

    # 2. Resolve Course ID only if course_name exists
    course_id = get_course_id(course_name) if course_name else None

    # 3. Clean timestamps
    start_time = clean_iso_string(data.get("start"))
    end_time = clean_iso_string(data.get("end"))

    # Prepare the date property
    date_prop = {"start": start_time}
    if end_time:
        date_prop["end"] = end_time

    # 4. Construct properties safely
    properties = {
        Task_Notion_Name: {"title": [{"text": {"content": title}}]},
        # Ensure type is one of your allowed Select options
        EventType_Notion_Name: {"multi_select": [{"name": event_type}]},
        Date_Notion_Name: {"date": date_prop},
    }

    # Add optional Rich Text
    if data.get("notes"):
        properties[ExtraInfo_Notion_Name] = {
            "rich_text": [{"text": {"content": data["notes"]}}]
        }

    # Add Relation only if we found a match in your Courses/Folders DB
    if course_id:
        properties[Folder_Notion_Name] = {"relation": [{"id": course_id}]}

    # 5. Final Send
    try:
        create_notion_event(notion, DATA_SOURCE_ID, properties)
    except Exception as e:
        print(f"Failed to create Notion event: {e}")


user_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Task: ")
try:
    extracted = parse_prompt(user_input)
    print(extracted)
    create_entry(extracted)
    os.system(
        f'notify-send "Notion" "✅ Added {extracted["type"]}: {extracted["title"]}"'
    )
except Exception as e:
    os.system(f'notify-send "Notion Error" "{str(e)}"')
    print(f"Error: {e}")
