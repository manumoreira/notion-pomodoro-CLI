"""Notion API client integration for validating databases and logging Pomodoro sessions."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from notion_client import Client
from notion_client.errors import APIResponseError, RequestTimeoutError


class NotionError(Exception):
    """Custom exception for Notion API operations."""
    pass


class NotionLogger:
    """Handles communication with the Notion API to manage and update tasks & Pomodoro sessions."""

    def __init__(self, api_key: str, database_id: str):
        self.api_key = api_key
        self.database_id = database_id
        self.client = Client(auth=api_key)

    def _get_db_info(self) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[str]]:
        """
        Retrieve database object, properties dictionary, and primary data_source_id.
        Handles both traditional database schemas and Notion API 2025+ data_sources schemas.
        """
        db = self.client.databases.retrieve(database_id=self.database_id)
        properties = db.get("properties") or {}
        data_source_id = None

        data_sources = db.get("data_sources", [])
        if data_sources:
            data_source_id = data_sources[0].get("id")
            if not properties and hasattr(self.client, "data_sources") and data_source_id:
                try:
                    ds = self.client.data_sources.retrieve(data_source_id=data_source_id)
                    properties = ds.get("properties") or {}
                except Exception:
                    pass

        return db, properties, data_source_id

    def _query_database(self, data_source_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Query database records supporting both client.data_sources.query and client.databases.query.
        """
        if data_source_id and hasattr(self.client, "data_sources"):
            return self.client.data_sources.query(data_source_id=data_source_id, **kwargs)
        if hasattr(self.client.databases, "query"):
            return self.client.databases.query(database_id=self.database_id, **kwargs)
        if hasattr(self.client, "data_sources"):
            _, _, ds_id = self._get_db_info()
            if ds_id:
                return self.client.data_sources.query(data_source_id=ds_id, **kwargs)
        raise NotionError("Could not query Notion database: no supported query method found.")

    def validate_connection(self) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validate authentication and database access.
        
        Returns:
            (is_valid: bool, message: str, db_metadata: dict)
        """
        try:
            # 1. Check API token validity
            user = self.client.users.me()
            bot_name = user.get("name", "Notion Integration")

            # 2. Check Database access
            db, properties, data_source_id = self._get_db_info()
            
            # Extract database title
            title_list = db.get("title", [])
            db_title = "".join([t.get("plain_text", "") for t in title_list]) or "Untitled Database"
            
            schema_summary = {
                name: prop.get("type") for name, prop in properties.items()
            }

            return True, f"Successfully connected to '{db_title}' via bot '{bot_name}'", {
                "title": db_title,
                "bot_name": bot_name,
                "properties": schema_summary,
                "raw_properties": properties,
                "data_source_id": data_source_id
            }

        except APIResponseError as err:
            if err.code == "unauthorized":
                return False, "Invalid Notion API key (Unauthorized 401). Please check your NOTION_API_KEY.", {}
            elif err.code == "object_not_found":
                return (
                    False,
                    "Database not found (404). Please verify NOTION_DATABASE_ID and ensure your "
                    "Notion Integration has been shared with the database:\n"
                    "  1. Open your database in Notion.\n"
                    "  2. Click the '...' menu at the top right.\n"
                    "  3. Click 'Connections' -> Add your integration.",
                    {}
                )
            elif err.code == "rate_limited":
                return False, "Notion API rate limit exceeded. Please try again in a few moments.", {}
            else:
                return False, f"Notion API error: {err.message} (code: {err.code})", {}

        except RequestTimeoutError:
            return False, "Notion API request timed out. Please check your network connection.", {}
        except Exception as e:
            return False, f"Unexpected error connecting to Notion: {str(e)}", {}

    def _resolve_property_mapping(self, db_properties: Dict[str, Any]) -> Dict[str, Optional[Tuple[str, str]]]:
        """
        Intelligently map logical fields (title, status, project_client, pomodoros, time_spent, session_date)
        to actual properties in the user's Notion database.
        """
        mapping: Dict[str, Optional[Tuple[str, str]]] = {
            "title": None,
            "status": None,
            "project_client": None,
            "pomodoros": None,
            "time_spent": None,
            "session_date": None,
        }

        # 1. Title property (required by Notion on all databases)
        for name, prop in db_properties.items():
            if prop.get("type") == "title":
                mapping["title"] = (name, "title")
                break

        # 2. Status property (status or select)
        for name, prop in db_properties.items():
            p_type = prop.get("type")
            if p_type in ["status", "select"]:
                if name.lower() in ["status", "state"]:
                    mapping["status"] = (name, p_type)
                    break
                elif mapping["status"] is None and p_type == "status":
                    mapping["status"] = (name, p_type)

        # 3. Project / Client property (select, multi_select, rich_text, relation)
        project_candidates = ["project/client", "project / client", "project", "client", "tags", "tag", "category"]
        for name, prop in db_properties.items():
            p_type = prop.get("type")
            if p_type in ["select", "multi_select", "relation", "rich_text"]:
                if name.lower() in project_candidates:
                    mapping["project_client"] = (name, p_type)
                    if "project" in name.lower() or "client" in name.lower():
                        break
                elif mapping["project_client"] is None and name != (mapping["status"][0] if mapping["status"] else None):
                    mapping["project_client"] = (name, p_type)

        # 4. Pomodoros counter (number)
        pomo_candidates = [
            "pomodoros", "pomodoro", "pomodoro-tracking", "pomodoro tracking",
            "pomodoro_tracking", "pomodoro count", "🍅", "cycles", "poms"
        ]
        for name, prop in db_properties.items():
            if prop.get("type") == "number":
                if name.lower() in pomo_candidates or "pomodoro" in name.lower() or "🍅" in name:
                    mapping["pomodoros"] = (name, "number")
                    break

        # 5. Time Spent / Duration (number)
        duration_candidates = [
            "time spent (min)", "time spent (mins)", "time spent", "duration (min)",
            "duration (mins)", "duration", "minutes", "min", "time tracked", "time", "focus time"
        ]
        for name, prop in db_properties.items():
            if prop.get("type") == "number":
                # Ensure we don't accidentally assign the same column as Pomodoros
                if mapping["pomodoros"] and name == mapping["pomodoros"][0]:
                    continue
                if name.lower() in duration_candidates or "time spent" in name.lower():
                    mapping["time_spent"] = (name, "number")
                    break
                elif mapping["time_spent"] is None and not mapping["pomodoros"]:
                    mapping["time_spent"] = (name, "number")

        # 6. Session Date (date - excluding Deadline/Due Date)
        date_candidates = ["date", "last worked", "completed at", "timestamp", "logged at"]
        for name, prop in db_properties.items():
            if prop.get("type") == "date":
                if "deadline" in name.lower() or "due" in name.lower():
                    # Preserve deadline - do not map as session date
                    continue
                if name.lower() in date_candidates or mapping["session_date"] is None:
                    mapping["session_date"] = (name, "date")
                    if name.lower() in ["date", "last worked", "completed at"]:
                        break

        return mapping

    def fetch_recent_tasks(self, limit: int = 15) -> list[Dict[str, Any]]:
        """
        Fetch recently active or updated tasks from the Notion database.
        Returns a list of dicts: [{'id': page_id, 'title': str, 'status': str, 'project': str, 'pomodoros': int, 'time_spent': int, 'url': str}]
        """
        try:
            db, properties, data_source_id = self._get_db_info()
            mapping = self._resolve_property_mapping(properties)
            title_prop = mapping.get("title", ("Task", "title"))[0]

            response = self._query_database(
                data_source_id=data_source_id,
                page_size=limit,
                sorts=[{"timestamp": "last_edited_time", "direction": "descending"}]
            )

            tasks = []
            for page in response.get("results", []):
                props = page.get("properties", {})
                
                # Extract title
                title_objs = props.get(title_prop, {}).get("title", [])
                task_title = "".join([t.get("plain_text", "") for t in title_objs]).strip()
                if not task_title:
                    continue

                # Extract status
                status_val = "Not Started"
                if mapping.get("status"):
                    s_name, s_type = mapping["status"]
                    s_obj = props.get(s_name, {})
                    if s_type == "status" and s_obj.get("status"):
                        status_val = s_obj["status"].get("name", "")
                    elif s_type == "select" and s_obj.get("select"):
                        status_val = s_obj["select"].get("name", "")

                # Extract project/client
                project_val = ""
                if mapping.get("project_client"):
                    p_name, p_type = mapping["project_client"]
                    p_obj = props.get(p_name, {})
                    if p_type == "select" and p_obj.get("select"):
                        project_val = p_obj["select"].get("name", "")
                    elif p_type == "multi_select" and p_obj.get("multi_select"):
                        project_val = ", ".join([m.get("name", "") for m in p_obj["multi_select"]])

                # Extract pomodoros
                pomodoros_val = 0
                if mapping.get("pomodoros"):
                    pomo_name, _ = mapping["pomodoros"]
                    pomodoros_val = props.get(pomo_name, {}).get("number") or 0

                # Extract time spent
                time_val = 0
                if mapping.get("time_spent"):
                    time_name, _ = mapping["time_spent"]
                    time_val = props.get(time_name, {}).get("number") or 0

                tasks.append({
                    "id": page.get("id"),
                    "title": task_title,
                    "status": status_val,
                    "project": project_val,
                    "pomodoros": pomodoros_val,
                    "time_spent": time_val,
                    "url": page.get("url", f"https://notion.so/{page.get('id', '').replace('-', '')}"),
                    "raw_page": page
                })

            return tasks
        except Exception:
            # Fall back to empty list on error
            return []

    def find_task_by_title(self, task_title: str) -> Optional[Dict[str, Any]]:
        """Search for an existing task in the database matching title (case-insensitive)."""
        clean_title = task_title.strip().lower()
        if not clean_title:
            return None

        try:
            db, properties, data_source_id = self._get_db_info()
            mapping = self._resolve_property_mapping(properties)
            title_prop_name = mapping.get("title", ("Task", "title"))[0]

            response = self._query_database(
                data_source_id=data_source_id,
                filter={
                    "property": title_prop_name,
                    "title": {
                        "equals": task_title.strip()
                    }
                }
            )

            results = response.get("results", [])
            if not results:
                # Try contains filter if exact match returned nothing
                response = self._query_database(
                    data_source_id=data_source_id,
                    filter={
                        "property": title_prop_name,
                        "title": {
                            "contains": task_title.strip()
                        }
                    }
                )
                results = response.get("results", [])

            if results:
                page = results[0]
                props = page.get("properties", {})
                
                pomodoros_val = 0
                if mapping.get("pomodoros"):
                    pomodoros_val = props.get(mapping["pomodoros"][0], {}).get("number") or 0

                time_val = 0
                if mapping.get("time_spent"):
                    time_val = props.get(mapping["time_spent"][0], {}).get("number") or 0

                status_val = ""
                if mapping.get("status"):
                    s_name, s_type = mapping["status"]
                    s_obj = props.get(s_name, {})
                    if s_type == "status" and s_obj.get("status"):
                        status_val = s_obj["status"].get("name", "")
                    elif s_type == "select" and s_obj.get("select"):
                        status_val = s_obj["select"].get("name", "")

                return {
                    "id": page.get("id"),
                    "title": task_title,
                    "status": status_val,
                    "pomodoros": pomodoros_val,
                    "time_spent": time_val,
                    "url": page.get("url", f"https://notion.so/{page.get('id', '').replace('-', '')}"),
                    "raw_page": page
                }
        except Exception:
            return None

        return None

    def record_or_increment_task(
        self,
        task_name: str,
        duration_minutes: int,
        pomodoros_count: int = 1,
        page_id: Optional[str] = None,
        project_client: Optional[str] = None,
        status: Optional[str] = None,
        mark_completed: bool = False,
        completed_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Record or increment task progress in Notion.
        
        If page_id is provided or task exists:
          - Increments 'Pomodoros' count
          - Adds duration to 'Time Spent (min)'
          - Updates Status (e.g. 'In Progress' or 'Done' / 'Completed')
          - Updates Session Date if available
        If task does not exist:
          - Creates new page with initial values.
        """
        now = completed_at or datetime.now(timezone.utc)

        try:
            db, properties_schema, data_source_id = self._get_db_info()
        except Exception as e:
            raise NotionError(f"Could not retrieve Notion database schema: {e}") from e

        mapping = self._resolve_property_mapping(properties_schema)

        # Look up existing page if page_id not provided
        existing_task = None
        if page_id:
            try:
                raw_page = self.client.pages.retrieve(page_id=page_id)
                props = raw_page.get("properties", {})
                pomo_num = 0
                if mapping.get("pomodoros"):
                    pomo_num = props.get(mapping["pomodoros"][0], {}).get("number") or 0
                time_num = 0
                if mapping.get("time_spent"):
                    time_num = props.get(mapping["time_spent"][0], {}).get("number") or 0

                existing_task = {
                    "id": page_id,
                    "pomodoros": pomo_num,
                    "time_spent": time_num,
                    "url": raw_page.get("url", f"https://notion.so/{page_id.replace('-', '')}")
                }
            except Exception:
                existing_task = None
        else:
            existing_task = self.find_task_by_title(task_name)

        # Prepare property updates
        updated_props: Dict[str, Any] = {}

        # 1. Title (always set on creation, optional on update)
        title_prop = mapping.get("title")
        if title_prop:
            prop_name, _ = title_prop
            updated_props[prop_name] = {
                "title": [{"type": "text", "text": {"content": task_name}}]
            }

        # 2. Pomodoros increment
        if mapping.get("pomodoros"):
            prop_name, _ = mapping["pomodoros"]
            curr_poms = (existing_task["pomodoros"] if existing_task else 0) or 0
            new_poms = curr_poms + pomodoros_count
            updated_props[prop_name] = {"number": new_poms}
        else:
            new_poms = pomodoros_count

        # 3. Time Spent increment
        if mapping.get("time_spent"):
            prop_name, _ = mapping["time_spent"]
            curr_time = (existing_task["time_spent"] if existing_task else 0) or 0
            new_time = curr_time + duration_minutes
            updated_props[prop_name] = {"number": new_time}
        else:
            new_time = duration_minutes

        # 4. Status update
        if mapping.get("status"):
            prop_name, prop_type = mapping["status"]
            # Determine target status
            target_status = status
            if not target_status:
                target_status = "Done" if mark_completed else "In Progress"
            
            # Check available status options in schema if possible
            schema_prop = properties_schema.get(prop_name, {})
            options = []
            if prop_type == "status":
                options = [opt.get("name") for opt in schema_prop.get("status", {}).get("options", [])]
            elif prop_type == "select":
                options = [opt.get("name") for opt in schema_prop.get("select", {}).get("options", [])]

            # Match case-insensitively with available options
            matched_option = target_status
            if options:
                for opt in options:
                    if opt.lower() == target_status.lower():
                        matched_option = opt
                        break
                    elif mark_completed and opt.lower() in ["done", "completed", "complete", "finished"]:
                        matched_option = opt
                        break
                    elif not mark_completed and opt.lower() in ["in progress", "doing", "in-progress", "active"]:
                        matched_option = opt
                        break

            if prop_type == "status":
                updated_props[prop_name] = {"status": {"name": matched_option}}
            elif prop_type == "select":
                updated_props[prop_name] = {"select": {"name": matched_option}}

        # 5. Project / Client
        if project_client and mapping.get("project_client"):
            prop_name, prop_type = mapping["project_client"]
            if prop_type == "select":
                updated_props[prop_name] = {"select": {"name": project_client}}
            elif prop_type == "multi_select":
                updated_props[prop_name] = {"multi_select": [{"name": project_client}]}
            elif prop_type == "rich_text":
                updated_props[prop_name] = {"rich_text": [{"type": "text", "text": {"content": project_client}}]}

        # 6. Session Date (only if date column is NOT deadline)
        if mapping.get("session_date"):
            prop_name, _ = mapping["session_date"]
            updated_props[prop_name] = {"date": {"start": now.isoformat()}}

        try:
            if existing_task:
                # Update existing page
                target_id = existing_task["id"]
                page = self.client.pages.update(
                    page_id=target_id,
                    properties=updated_props
                )
                action = "updated"
            else:
                # Create new page
                parent_arg = {"data_source_id": data_source_id} if data_source_id else {"database_id": self.database_id}
                try:
                    page = self.client.pages.create(
                        parent=parent_arg,
                        properties=updated_props
                    )
                except APIResponseError:
                    if "data_source_id" in parent_arg:
                        page = self.client.pages.create(
                            parent={"database_id": self.database_id},
                            properties=updated_props
                        )
                    else:
                        raise
                action = "created"

            page_id = page.get("id")
            return {
                "action": action,
                "id": page_id,
                "url": page.get("url", f"https://notion.so/{page_id.replace('-', '')}"),
                "pomodoros": new_poms,
                "time_spent": new_time,
                "updated_properties": list(updated_props.keys())
            }

        except APIResponseError as err:
            raise NotionError(f"Failed to save task to Notion: {err.message} ({err.code})") from err
        except Exception as e:
            raise NotionError(f"Unexpected error while saving to Notion: {e}") from e

    # Backwards compatibility alias
    def log_session(self, task_name: str, duration_minutes: int, tag: Optional[str] = None, status: str = "Completed", **kwargs) -> Dict[str, Any]:
        """Convenience method wrapping record_or_increment_task."""
        return self.record_or_increment_task(
            task_name=task_name,
            duration_minutes=duration_minutes,
            pomodoros_count=1,
            project_client=tag,
            status=status,
            mark_completed=(status.lower() in ["completed", "done"]),
            completed_at=kwargs.get("completed_at")
        )
