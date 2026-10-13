"""Unit tests for Notion schema resolution and payload formatting."""

from unittest.mock import MagicMock
from notion_pomodoro.notion import NotionLogger


def test_resolve_property_mapping_user_schema():
    logger = NotionLogger(api_key="secret_test", database_id="db123")
    
    # User's exact schema + recommended tracking columns
    mock_properties = {
        "Task": {"type": "title"},
        "Status": {"type": "status"},
        "Project/client": {"type": "select"},
        "Deadline": {"type": "date"},
        "Parent item": {"type": "relation"},
        "Pomodoros": {"type": "number"},
        "Time Spent (min)": {"type": "number"},
    }

    mapping = logger._resolve_property_mapping(mock_properties)
    assert mapping["title"] == ("Task", "title")
    assert mapping["status"] == ("Status", "status")
    assert mapping["project_client"] == ("Project/client", "select")
    assert mapping["pomodoros"] == ("Pomodoros", "number")
    assert mapping["time_spent"] == ("Time Spent (min)", "number")
    # Deadline should NOT be used as session date
    assert mapping["session_date"] is None


def test_resolve_property_mapping_variations():
    logger = NotionLogger(api_key="secret_test", database_id="db123")
    
    mock_properties = {
        "Name": {"type": "title"},
        "Status": {"type": "select"},
        "Client": {"type": "multi_select"},
        "🍅": {"type": "number"},
        "Duration": {"type": "number"},
        "Date": {"type": "date"},
    }

    mapping = logger._resolve_property_mapping(mock_properties)
    assert mapping["title"] == ("Name", "title")
    assert mapping["status"] == ("Status", "select")
    assert mapping["project_client"] == ("Client", "multi_select")
    assert mapping["pomodoros"] == ("🍅", "number")
    assert mapping["time_spent"] == ("Duration", "number")
    assert mapping["session_date"] == ("Date", "date")


def test_resolve_property_mapping_pomodoro_tracking():
    logger = NotionLogger(api_key="secret_test", database_id="db123")
    
    mock_properties = {
        "Task": {"type": "title"},
        "pomodoro-tracking": {"type": "number"},
        "Time Spent (min)": {"type": "number"},
    }

    mapping = logger._resolve_property_mapping(mock_properties)
    assert mapping["pomodoros"] == ("pomodoro-tracking", "number")
    assert mapping["time_spent"] == ("Time Spent (min)", "number")


def test_record_or_increment_task_creates_new():
    logger = NotionLogger(api_key="secret_test", database_id="db123")
    
    mock_db = {
        "properties": {
            "Task": {"type": "title"},
            "Status": {"type": "status", "status": {"options": [{"name": "In Progress"}, {"name": "Done"}]}},
            "Project/client": {"type": "select"},
            "Pomodoros": {"type": "number"},
            "Time Spent (min)": {"type": "number"},
        }
    }
    logger.client.databases.retrieve = MagicMock(return_value=mock_db)
    logger.client.databases.query = MagicMock(return_value={"results": []})
    logger.client.pages.create = MagicMock(return_value={"id": "page-new-123", "url": "https://notion.so/page-new-123"})

    res = logger.record_or_increment_task(
        task_name="Implement Auth",
        duration_minutes=25,
        pomodoros_count=1,
        project_client="Acme Corp",
        mark_completed=False,
    )

    assert res["action"] == "created"
    assert res["id"] == "page-new-123"
    assert res["pomodoros"] == 1
    assert res["time_spent"] == 25
    
    logger.client.pages.create.assert_called_once()
    props = logger.client.pages.create.call_args[1]["properties"]
    assert props["Task"]["title"][0]["text"]["content"] == "Implement Auth"
    assert props["Pomodoros"]["number"] == 1
    assert props["Time Spent (min)"]["number"] == 25
    assert props["Project/client"]["select"]["name"] == "Acme Corp"
    assert props["Status"]["status"]["name"] == "In Progress"


def test_record_or_increment_task_updates_existing():
    logger = NotionLogger(api_key="secret_test", database_id="db123")
    
    mock_db = {
        "properties": {
            "Task": {"type": "title"},
            "Status": {"type": "status", "status": {"options": [{"name": "In Progress"}, {"name": "Done"}]}},
            "Pomodoros": {"type": "number"},
            "Time Spent (min)": {"type": "number"},
        }
    }
    mock_existing_page = {
        "id": "existing-page-456",
        "url": "https://notion.so/existing-page-456",
        "properties": {
            "Task": {"title": [{"plain_text": "Write Report"}]},
            "Pomodoros": {"number": 2},
            "Time Spent (min)": {"number": 50},
            "Status": {"status": {"name": "In Progress"}},
        }
    }
    logger.client.databases.retrieve = MagicMock(return_value=mock_db)
    logger.client.pages.retrieve = MagicMock(return_value=mock_existing_page)
    logger.client.pages.update = MagicMock(return_value=mock_existing_page)

    res = logger.record_or_increment_task(
        task_name="Write Report",
        page_id="existing-page-456",
        duration_minutes=25,
        pomodoros_count=1,
        mark_completed=True,
    )

    assert res["action"] == "updated"
    assert res["pomodoros"] == 3
    assert res["time_spent"] == 75
    
    logger.client.pages.update.assert_called_once()
    call_args = logger.client.pages.update.call_args[1]
    assert call_args["page_id"] == "existing-page-456"
    props = call_args["properties"]
    assert props["Pomodoros"]["number"] == 3
    assert props["Time Spent (min)"]["number"] == 75
    assert props["Status"]["status"]["name"] == "Done"

