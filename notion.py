import os
from notion_client import Client
from datetime import datetime
import logging


def setup_notion_client(token_path):
    NOTION_TOKEN = open(token_path, "r").read().strip()
    return Client(auth=NOTION_TOKEN)


def get_events_to_sync(notion, data_source_id, filter_obj=None):
    # filter_obj should be a dict matching the new Notion API v3 filter format
    response = notion.data_sources.query(
        data_source_id, filter=filter_obj if filter_obj else None
    )
    return response.get("results", [])


def update_notion_event(notion, page_id, properties):
    # properties: dict of property updates
    return notion.pages.update(page_id=page_id, properties=properties)


def create_notion_event(notion, data_source_id, properties):
    # properties: dict of property values for the new event
    return notion.pages.create(
        parent={"type": "data_source_id", "data_source_id": data_source_id},
        properties=properties,
    )


def make_notion_datetime(dt: datetime, tz_offset="-04:00"):
    # Helper to format datetime for Notion
    return dt.strftime(f"%Y-%m-%dT%H:%M:%S{tz_offset}")
