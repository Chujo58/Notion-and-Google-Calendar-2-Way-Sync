import os
from datetime import datetime, timedelta

import logging
from dotenv import load_dotenv
from gcal import setup_gcal_service, make_cal_event, update_cal_event
from notion import (
    setup_notion_client,
    get_events_to_sync,
    update_notion_event,
    create_notion_event,
    make_notion_datetime,
)
from config import (
    Task_Notion_Name,
    Date_Notion_Name,
    Initiative_Notion_Name,
    ExtraInfo_Notion_Name,
    On_GCal_Notion_Name,
    NeedGCalUpdate_Notion_Name,
    GCalEventId_Notion_Name,
    LastUpdatedTime_Notion_Name,
    Calendar_Notion_Name,
    Current_Calendar_Id_Notion_Name,
    Delete_Notion_Name,
    calendarDictionary,
    DEFAULT_CALENDAR_ID,
    DEFAULT_CALENDAR_NAME,
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
DEFAULT_CALENDAR_NAME = os.getenv("DEFAULT_CALENDAR_NAME", DEFAULT_CALENDAR_NAME)
DEFAULT_CALENDAR_ID = os.getenv("DEFAULT_CALENDAR_ID", DEFAULT_CALENDAR_ID)
TIMEZONE = os.getenv("TIMEZONE", "America/New_York")
ALL_DAY_EVENT_OPTION = int(os.getenv("ALL_DAY_EVENT_OPTION", 0))
DEFAULT_EVENT_START = int(os.getenv("DEFAULT_EVENT_START", 8))
DEFAULT_EVENT_LENGTH = int(os.getenv("DEFAULT_EVENT_LENGTH", 60))

# --- SETUP ---
notion = setup_notion_client(NOTION_TOKEN_PATH)
service = setup_gcal_service(CREDENTIALS_LOCATION, DEFAULT_CALENDAR_ID)
TIMEZONE = "America/New_York"
ALL_DAY_EVENT_OPTION = 0
DEFAULT_EVENT_START = 8
DEFAULT_EVENT_LENGTH = 60

# --- SETUP ---
notion = setup_notion_client(NOTION_TOKEN_PATH)
service = setup_gcal_service(CREDENTIALS_LOCATION, DEFAULT_CALENDAR_ID)


def formatTime(time):
    formatedTime = ""
    try:
        formatedTime = datetime.strptime(time, "%Y-%m-%d")
    except:
        try:
            formatedTime = datetime.strptime(time[:-6], "%Y-%m-%dT%H:%M:%S.000")
        except:
            formatedTime = datetime.strptime(time[:-6], "%Y-%m-%dT%H:%M:%S.%f")
    return formatedTime


def makeDescription(folder, notes):
    if folder == "" and notes == "":
        return ""
    elif notes == "":
        return folder
    elif folder == "":
        return notes
    else:
        return f"Folder: {folder}\n{notes}"


def syncNotion2GCal():
    """
    Part 1: Take Notion Events not on GCal and move them over to GCal
    """

    today = datetime.today().strftime("%Y-%m-%d")
    filter_obj = {
        "and": [
            {"property": On_GCal_Notion_Name, "checkbox": {"equals": False}},
            {"property": Date_Notion_Name, "date": {"on_or_after": today}},
            {"property": Delete_Notion_Name, "checkbox": {"equals": False}},
        ]
    }
    notion_events = get_events_to_sync(notion, DATA_SOURCE_ID, filter_obj)
    print(f"Found {len(notion_events)} Notion events to sync.")

    for event in notion_events:
        props = event["properties"]
        event_name = (
            props[Task_Notion_Name]["title"][0]["plain_text"]
            if props[Task_Notion_Name]["title"]
            else ""
        )
        event_description = (
            props[ExtraInfo_Notion_Name]["rich_text"][0]["plain_text"]
            if props[ExtraInfo_Notion_Name]["rich_text"]
            else ""
        )
        start_date = props[Date_Notion_Name]["date"]["start"]
        end_date = props[Date_Notion_Name]["date"].get("end") or start_date

        source_url = event.get("url", "")
        # Calendar selection logic (default to DEFAULT_CALENDAR_ID)
        cal_id = DEFAULT_CALENDAR_ID
        if Calendar_Notion_Name in props and props[Calendar_Notion_Name].get("formula"):
            cal_name = props[Calendar_Notion_Name]["formula"]["string"]
            cal_id = calendarDictionary.get(cal_name, DEFAULT_CALENDAR_ID)

        # Convert to datetime
        start_dt = formatTime(start_date)
        end_dt = formatTime(end_date)

        # Make the description
        description = makeDescription(
            props[Calendar_Notion_Name]["formula"]["string"], event_description
        )

        # Create event in GCal
        gcal_event_id = make_cal_event(
            service,
            event_name,
            description,
            start_dt,
            source_url,
            end_dt,
            cal_id,
            TIMEZONE,
            ALL_DAY_EVENT_OPTION,
            DEFAULT_EVENT_START,
            DEFAULT_EVENT_LENGTH,
        )

        # If there is no calendar assigned on Notion do a general update:
        if cal_id == DEFAULT_CALENDAR_ID:
            update_notion_event(
                notion,
                event["id"],
                {
                    On_GCal_Notion_Name: {"checkbox": True},
                    GCalEventId_Notion_Name: {
                        "rich_text": [{"text": {"content": gcal_event_id}}]
                    },
                    Current_Calendar_Id_Notion_Name: {
                        "rich_text": [{"text": {"content": cal_id}}]
                    },
                    Calendar_Notion_Name: {"formula": {"string": DEFAULT_CALENDAR_ID}},
                    LastUpdatedTime_Notion_Name: {
                        "date": {
                            "start": make_notion_datetime(datetime.now()),
                            "end": None,
                        }
                    },
                },
            )
        else:  # just a regular update
            update_notion_event(
                notion,
                event["id"],
                {
                    On_GCal_Notion_Name: {"checkbox": True},
                    GCalEventId_Notion_Name: {
                        "rich_text": [{"text": {"content": gcal_event_id}}]
                    },
                    Current_Calendar_Id_Notion_Name: {
                        "rich_text": [{"text": {"content": cal_id}}]
                    },
                },
            )

        print(f"Synced event '{event_name}' to Google Calendar.")


def notionUpdate2GCal():
    today = datetime.today().strftime("%Y-%m-%d")
    filter_obj = {
        "and": [
            {
                "property": Calendar_Notion_Name,
                "formula": {"string": {"is_empty": True}},
            },
            {
                "or": [
                    {"property": Date_Notion_Name, "date": {"equals": today}},
                    {"property": Date_Notion_Name, "date": {"next_week": {}}},
                ]
            },
        ]
    }

    notion_events = get_events_to_sync(notion, DATA_SOURCE_ID, filter_obj)
    print(f"Found {len(notion_events)} Notion events to update.")


if __name__ == "__main__":
    syncNotion2GCal()
    notionUpdate2GCal()
