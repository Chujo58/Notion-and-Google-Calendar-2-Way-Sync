import pickle
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import logging
import os


def setup_gcal_service(credentialsLocation, calendar_id):
    credentials = pickle.load(open(credentialsLocation, "rb"))
    service = build("calendar", "v3", credentials=credentials)
    while True:
        try:
            calendar = service.calendars().get(calendarId=calendar_id).execute()
            break
        except OSError as e:
            if e.errno == 101:
                print("Network error. Please check your internet connection.")
                import time

                time.sleep(5)
        except Exception:
            # Token refresh logic should be handled externally
            raise
    return service


def make_cal_event(
    service,
    eventName,
    eventDescription,
    eventStartTime,
    sourceURL,
    eventEndTime,
    calId,
    timezone,
    AllDayEventOption,
    DEFAULT_EVENT_START,
    DEFAULT_EVENT_LENGTH,
):
    print(
        f"Making event: {eventName} from {eventStartTime} to {eventEndTime} on calendar {calId}"
    )
    if (
        eventStartTime.hour == 0
        and eventStartTime.minute == 0
        and eventEndTime == eventStartTime
    ):
        if AllDayEventOption == 1:
            eventStartTime = datetime.combine(
                eventStartTime, datetime.min.time()
            ) + timedelta(hours=DEFAULT_EVENT_START)
            eventEndTime = eventStartTime + timedelta(minutes=DEFAULT_EVENT_LENGTH)
            event = {
                "summary": eventName,
                "description": eventDescription,
                "start": {
                    "dateTime": eventStartTime.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": timezone,
                },
                "end": {
                    "dateTime": eventEndTime.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": timezone,
                },
                "source": {
                    "title": "Notion Link",
                    "url": sourceURL,
                },
            }
        else:
            eventEndTime = eventEndTime + timedelta(days=1)
            event = {
                "summary": eventName,
                "description": eventDescription,
                "start": {
                    "date": eventStartTime.strftime("%Y-%m-%d"),
                    "timeZone": timezone,
                },
                "end": {
                    "date": eventEndTime.strftime("%Y-%m-%d"),
                    "timeZone": timezone,
                },
                "source": {
                    "title": "Notion Link",
                    "url": sourceURL,
                },
            }
    elif (
        eventStartTime.hour == 0
        and eventStartTime.minute == 0
        and eventEndTime.hour == 0
        and eventEndTime.minute == 0
        and eventStartTime != eventEndTime
    ):
        eventEndTime = eventEndTime + timedelta(days=1)
        event = {
            "summary": eventName,
            "description": eventDescription,
            "start": {
                "date": eventStartTime.strftime("%Y-%m-%d"),
                "timeZone": timezone,
            },
            "end": {
                "date": eventEndTime.strftime("%Y-%m-%d"),
                "timeZone": timezone,
            },
            "source": {
                "title": "Notion Link",
                "url": sourceURL,
            },
        }
    else:
        event = {
            "summary": eventName,
            "description": eventDescription,
            "start": {
                "dateTime": eventStartTime.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": timezone,
            },
            "end": {
                "dateTime": eventEndTime.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": timezone,
            },
            "source": {
                "title": "Notion Link",
                "url": sourceURL,
            },
        }
    logging.info(f"Adding this event to calendar: {eventName}")
    x = service.events().insert(calendarId=calId, body=event).execute()
    return x["id"]


def update_cal_event(
    service,
    eventName,
    eventDescription,
    eventStartTime,
    sourceURL,
    eventId,
    eventEndTime,
    currentCalId,
    CalId,
    timezone,
    AllDayEventOption,
    DEFAULT_EVENT_START,
    DEFAULT_EVENT_LENGTH,
):
    print(
        f"Updating event: {eventName} from {eventStartTime} to {eventEndTime} on calendar {CalId}"
    )
    if (
        eventStartTime.hour == 0
        and eventStartTime.minute == 0
        and eventEndTime == eventStartTime
    ):
        if AllDayEventOption == 1:
            eventStartTime = datetime.combine(
                eventStartTime, datetime.min.time()
            ) + timedelta(hours=DEFAULT_EVENT_START)
            eventEndTime = eventStartTime + timedelta(minutes=DEFAULT_EVENT_LENGTH)
            event = {
                "summary": eventName,
                "description": eventDescription,
                "start": {
                    "dateTime": eventStartTime.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": timezone,
                },
                "end": {
                    "dateTime": eventEndTime.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": timezone,
                },
                "source": {
                    "title": "Notion Link",
                    "url": sourceURL,
                },
            }
        else:
            eventEndTime = eventEndTime + timedelta(days=1)
            event = {
                "summary": eventName,
                "description": eventDescription,
                "start": {
                    "date": eventStartTime.strftime("%Y-%m-%d"),
                    "timeZone": timezone,
                },
                "end": {
                    "date": eventEndTime.strftime("%Y-%m-%d"),
                    "timeZone": timezone,
                },
                "source": {
                    "title": "Notion Link",
                    "url": sourceURL,
                },
            }
    elif (
        eventStartTime.hour == 0
        and eventStartTime.minute == 0
        and eventEndTime.hour == 0
        and eventEndTime.minute == 0
        and eventStartTime != eventEndTime
    ):
        eventEndTime = eventEndTime + timedelta(days=1)
        event = {
            "summary": eventName,
            "description": eventDescription,
            "start": {
                "date": eventStartTime.strftime("%Y-%m-%d"),
                "timeZone": timezone,
            },
            "end": {
                "date": eventEndTime.strftime("%Y-%m-%d"),
                "timeZone": timezone,
            },
            "source": {
                "title": "Notion Link",
                "url": sourceURL,
            },
        }
    else:
        event = {
            "summary": eventName,
            "description": eventDescription,
            "start": {
                "dateTime": eventStartTime.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": timezone,
            },
            "end": {
                "dateTime": eventEndTime.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": timezone,
            },
            "source": {
                "title": "Notion Link",
                "url": sourceURL,
            },
        }
    logging.info(f"Updating this event to calendar: {eventName}")
    if currentCalId == CalId:
        x = (
            service.events()
            .update(calendarId=CalId, eventId=eventId, body=event)
            .execute()
        )
    else:
        service.events().delete(calendarId=currentCalId, eventId=eventId).execute()
        x = service.events().insert(calendarId=CalId, body=event).execute()
    return x["id"]
