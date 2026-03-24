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
        return f"Folder: {folder}"
    elif folder == "":
        return f"Notes: {notes}"
    else:
        return f"Folder: {folder}\nNotes: {notes}"


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
        props[GCalEventId_Notion_Name]["rich_text"][0]["plain_text"]
        if props[GCalEventId_Notion_Name]["rich_text"]
        else ""
    )

    gcal_id = (
        props[Current_Calendar_Id_Notion_Name]["rich_text"][0]["plain_text"]
        if props[Current_Calendar_Id_Notion_Name]["rich_text"]
        else ""
    )

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
    """
    Part 2: Update GCal events that need to be updated from Notion.
    """
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


def syncNotionGCals2Notion():
    """
    Part 3: Let's grab the events in Notion that don't have updates and are in GCal, we only query those back to GCal to avoid rate limits.
    """

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

        new_notion_cal_id = ""

        # Get the event from GCal:
        for calid in calendarDictionary.keys():
            try:
                x = (
                    service.events()
                    .get(calendarId=calendarDictionary[calid], eventId=gcal_eid)
                    .execute()
                )
                print(f"Event found in {calid}: {name} from {start_dt} to {end_dt}")
            except:
                # print(f"Event not found in {calid}: {name} from {start_dt} to {end_dt}")
                x = {"status": "unconfirmed"}

            if x["status"] == "confirmed":
                value = x
                new_notion_cal_id = calid

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
        new_notion_start = gCalStart if gCalStart != start_dt else start_dt
        new_notion_end = gCalEnd if gCalEnd != end_dt else end_dt

        # Bunch of if statements for updating the notion:
        # If both start and end time are to be updated:
        if new_notion_start and new_notion_end:
            start = new_notion_start
            end = new_notion_end
            _updateNotionWithGCalStuff(event, start, end)
        # Only start time needs to be updated
        elif new_notion_start:
            start = new_notion_start
            end = end_dt
            _updateNotionWithGCalStuff(event, start, end)

        # Only end time needs to be updated
        elif new_notion_end:
            start = start_dt
            end = new_notion_end
            _updateNotionWithGCalStuff(event, start, end)

        # else:
        #     continue

        # Just update the calendar the event is on:
        update_notion_event(
            notion,
            event["id"],
            {
                Current_Calendar_Id_Notion_Name: {
                    "rich_text": [
                        {"text": {"content": calendarDictionary[new_notion_cal_id]}}
                    ]
                },
                # Calendar_Notion_Name: {"formula": {"string": cal_id}},
                LastUpdatedTime_Notion_Name: {
                    "date": {"start": make_notion_datetime(datetime.now()), "end": None}
                },
            },
        )


def _updateNotionWithGCalStuff(event, start, end):
    # 12AM datetimes so you want to enter them as dates not datetimes in Notion
    if start.hour == 0 and start.minute == 0 and start == end:
        update_notion_event(
            notion,
            event["id"],
            {
                Date_Notion_Name: {
                    "date": {
                        "start": start.strftime("%Y-%m-%d"),
                        "end": None,
                    }
                },
                LastUpdatedTime_Notion_Name: {
                    "date": {
                        "start": make_notion_datetime(datetime.now()),
                        "end": None,
                    }
                },
            },
        )
    # 12 AM datetimes so enter them as dates not datetimes.
    elif start.hour == 0 and start.minute == 0 and end.hour == 0 and end.minute == 0:
        update_notion_event(
            notion,
            event["id"],
            {
                Date_Notion_Name: {
                    "date": {
                        "start": start.strftime("%Y-%m-%d"),
                        "end": end.strftime("%Y-%m-%d"),
                    }
                },
                LastUpdatedTime_Notion_Name: {
                    "date": {
                        "start": make_notion_datetime(datetime.now()),
                        "end": None,
                    }
                },
            },
        )

    else:
        update_notion_event(
            notion,
            event["id"],
            {
                Date_Notion_Name: {
                    "date": {
                        "start": make_notion_datetime(start),
                        "end": make_notion_datetime(end),
                    }
                }
            },
        )


def googleQuery():
    time_min = (datetime.now() - timedelta(days=1)).astimezone()
    return time_min.isoformat()


def syncGCal2Notion():
    """
    Part 4: Bring events not in Notion to Notion!
    """
    yesterday_iso = (datetime.now() - timedelta(days=2)).astimezone().isoformat()
    # 1. Get existing Notion IDs (using your helper)
    notion_events = get_events_to_sync(
        notion,
        DATA_SOURCE_ID,
        {
            "and": [
                # Only get events with a GCal ID
                {
                    "property": GCalEventId_Notion_Name,
                    "rich_text": {"is_not_empty": True},
                },
                # ONLY get events from yesterday onwards
                {"property": Date_Notion_Name, "date": {"on_or_after": yesterday_iso}},
            ]
        },
    )

    ALL_notion_gCal_Ids = set()
    for event in notion_events:
        try:
            _, _, _, _, _, _, gcal_eid, _ = getEventProperties(event)
            if gcal_eid:
                ALL_notion_gCal_Ids.add(gcal_eid)
        except:
            continue

    # 2. Get events from Google (Keep your existing fetch logic)
    all_gCal_items = []
    for el in calendarDictionary.keys():
        x = (
            service.events()
            .list(
                calendarId=calendarDictionary[el],
                maxResults=2000,
                timeMin=googleQuery(),
            )
            .execute()
        )
        # Add the calendar name to each item so we can use it later
        for item in x.get("items", []):
            item["_temp_cal_name"] = el
            all_gCal_items.append(item)

    # 3. The Loop
    for item in all_gCal_items:
        gcal_id = item["id"]

        if gcal_id not in ALL_notion_gCal_Ids:
            summary = item.get("summary", "Untitled Event")
            description = item.get("description", " ")
            cal_id_email = item["organizer"]["email"]
            cal_name = item["_temp_cal_name"]

            # --- Date Logic ---
            if "date" in item["start"]:  # All-day event
                start_date = item["start"]["date"]
                # GCal all-day end dates are exclusive, so subtract 1 day for Notion
                end_dt = datetime.strptime(item["end"]["date"], "%Y-%m-%d") - timedelta(
                    days=1
                )
                end_date = end_dt.strftime("%Y-%m-%d")

                # If it's a 1-day event, end is None. Otherwise, use the adjusted end.
                notion_end = None if start_date == end_date else end_date
                date_prop = {"start": start_date, "end": notion_end}

            else:  # Regular timed event
                # Use your make_notion_datetime helper
                start_dt = datetime.fromisoformat(
                    item["start"]["dateTime"].replace("Z", "+00:00")
                )
                end_dt = datetime.fromisoformat(
                    item["end"]["dateTime"].replace("Z", "+00:00")
                )
                date_prop = {
                    "start": make_notion_datetime(start_dt),
                    "end": make_notion_datetime(end_dt),
                }

            # --- The Update ---
            # Construct the properties dict exactly as your DB expects
            props = {
                Task_Notion_Name: {"title": [{"text": {"content": summary}}]},
                Date_Notion_Name: {"date": date_prop},
                LastUpdatedTime_Notion_Name: {
                    "date": {"start": make_notion_datetime(datetime.now())}
                },
                ExtraInfo_Notion_Name: {
                    "rich_text": [{"text": {"content": description}}]
                },
                GCalEventId_Notion_Name: {
                    "rich_text": [{"text": {"content": gcal_id}}]
                },
                On_GCal_Notion_Name: {"checkbox": True},
                Current_Calendar_Id_Notion_Name: {
                    "rich_text": [{"text": {"content": cal_id_email}}]
                },
                # Calendar_Notion_Name: {"select": {"name": cal_name}},
            }

            # Use your helper!
            create_notion_event(notion, DATA_SOURCE_ID, props)
            print(f"Added: {summary}")


if __name__ == "__main__":
    syncNotion2GCal()
    verifyNotionForEmptyCalendar()
    updatedNotion2GCal()
    syncNotionGCals2Notion()
    syncGCal2Notion()
