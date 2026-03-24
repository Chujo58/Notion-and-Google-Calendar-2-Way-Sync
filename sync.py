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
            {
                "property": On_GCal_Notion_Name,
                "checkbox": {"equals": False},
            },  # Not in GCal
            {
                "or": [
                    {"property": Date_Notion_Name, "date": {"equals": today}},
                    {"property": Date_Notion_Name, "date": {"next_week": {}}},
                ]
            },  # Between today and next week
            {"property": Delete_Notion_Name, "checkbox": {"equals": False}},
        ]
    }
    notion_events = get_events_to_sync(notion, DATA_SOURCE_ID, filter_obj)
    print(f"Found {len(notion_events)} Notion events to sync.")

    for event in notion_events:
        event_name, source_url, cal_id, start_dt, end_dt, description, _, _ = (
            getEventProperties(event)
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


def getEventProperties(event):
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

    # Also get the gcal_event_id:
    gcal_eid = (
        props[GCalEventId_Notion_Name]["rich_text"][0]["content"]
        if props[GCalEventId_Notion_Name]["rich_text"]
        else ""
    )

    gcal_id = props[Current_Calendar_Id_Notion_Name]["rich_text"][0]["content"]

    return (
        event_name,
        source_url,
        cal_id,
        start_dt,
        end_dt,
        description,
        gcal_eid,
        gcal_id,
    )


def verifyNotionForEmptyCalendar():
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
    print(f"Found {len(notion_events)} Notion events missing a calendar name.")

    for event in notion_events:
        update_notion_event(
            notion,
            event["id"],
            {
                Calendar_Notion_Name: {"formula": {"string": DEFAULT_CALENDAR_NAME}},
                LastUpdatedTime_Notion_Name: {
                    "date": {
                        "start": make_notion_datetime(datetime.now()),
                        "end": None,
                    }
                },
            },
        )


def updatedNotion2GCal():
    today = datetime.today().strftime("%Y-%m-%d")
    filter_obj = {
        "and": [
            {"property": NeedGCalUpdate_Notion_Name, "checkbox": {"equals": True}},
            {"property": On_GCal_Notion_Name, "checkbox": {"equals": True}},
            {
                "or": [
                    {"property": Date_Notion_Name, "date": {"equals": today}},
                    {"property": Date_Notion_Name, "date": {"next_week": {}}},
                ]
            },
            {"property": Delete_Notion_Name, "checkbox": {"equals": False}},
        ]
    }

    notion_events = get_events_to_sync(notion, DATA_SOURCE_ID, filter_obj)
    print(f"Found {len(notion_events)} Notion events to update.")

    for event in notion_events:
        (
            event_name,
            source_url,
            cal_id,
            start_dt,
            end_dt,
            description,
            gcal_eid,
            gcal_id,
        ) = getEventProperties(event)

        # Update event in GCal
        gcal_event_id = update_cal_event(
            service,
            event_name,
            description,
            start_dt,
            source_url,
            gcal_eid,
            end_dt,
            gcal_id,
            cal_id,
            TIMEZONE,
            ALL_DAY_EVENT_OPTION,
            DEFAULT_EVENT_START,
            DEFAULT_EVENT_LENGTH,
        )

        # Update the event in Notion
        update_notion_event(
            notion,
            event["id"],
            {
                On_GCal_Notion_Name: {"checkbox": True},
                LastUpdatedTime_Notion_Name: {
                    "date": {
                        "start": make_notion_datetime(datetime.now()),
                        "end": None,
                    }
                },
                Current_Calendar_Id_Notion_Name: {
                    "rich_text": [{"text": {"content": gcal_id}}]
                },
            },
        )


def syncGCal2Notion():
    # Let's grab the events in Notion that don't have updates and are in GCal, we only query those back to GCal to avoid rate limits.

    today = datetime.today().strftime("%Y-%m-%d")
    filter_obj = {
        "and": [
            {
                "property": NeedGCalUpdate_Notion_Name,
                "formula": {"checkbox": {"equals": False}},
            },
            {"property": On_GCal_Notion_Name, "checkbox": {"equals": True}},
            {
                "or": [
                    {"property": Date_Notion_Name, "date": {"equals": today}},
                    {"property": Date_Notion_Name, "date": {"next_week": {}}},
                ]
            },
            {"property": Delete_Notion_Name, "checkbox": {"equals": False}},
        ]
    }

    notion_events = get_events_to_sync(notion, DATA_SOURCE_ID, filter_obj)
    print(f"Found {len(notion_events)} Notion events to query in GCal.")

    for event in notion_events:
        name, _, cal_id, start_dt, end_dt, _, gcal_eid, gcal_id = getEventProperties(
            event
        )
        value = ""
        gCalStart = ""
        gCalEnd = ""

        # Get the event from GCal:
        for calid in calendarDictionary.keys():
            try:
                x = (
                    service.events()
                    .get(calendarId=calendarDictionary[calid], eventId=gcal_eid)
                    .execute()
                )
            except:
                print(f"Event not found in {calid}: {name} from {start_dt} to {end_dt}")
                x = {"status": "unconfirmed"}

            if x["status"] == "confirmed":
                value = x

        try:
            gCalStart = datetime.strptime(
                value["start"]["dateTime"][:-6], "%Y-%m-%dT%H:%M:%S"
            )
            gCalEnd = datetime.strptime(
                value["end"]["dateTime"][:-6], "%Y-%m-%dT%H:%M:%S"
            )
        except:
            gCalStart = datetime.strptime(value["start"]["date"], "%Y-%m-%d")
            gCalEnd = datetime.strptime(value["end"]["date"], "%Y-%m-%d")

            gCalStart = datetime(
                gCalStart.year, gCalStart.month, gCalStart.day, 0, 0, 0
            )
            gCalEnd = datetime(
                gCalEnd.year, gCalEnd.month, gCalEnd.day, 0, 0, 0
            ) - timedelta(days=1)

        # Now we got the google calendar start and end times, update the notion start and end times if they aren't the same:
        notion_start = gCalStart if gCalStart != start_dt else start_dt
        notion_end = gCalEnd if gCalEnd != end_dt else end_dt

    pass


if __name__ == "__main__":
    syncNotion2GCal()
    verifyNotionForEmptyCalendar()
    updatedNotion2GCal()
