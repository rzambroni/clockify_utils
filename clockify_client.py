"""
Clockify API Client

A Python client for interacting with the Clockify REST API.
"""

import os
from datetime import datetime
from typing import Optional
import requests


class ClockifyClient:
    """Client for Clockify API interactions."""
    
    BASE_URL = "https://api.clockify.me/api/v1"
    
    def __init__(self, api_key: str, workspace_id: str):
        """
        Initialize the Clockify client.
        
        Args:
            api_key: Clockify API key
            workspace_id: Workspace ID to operate on
        """
        self.api_key = api_key
        self.workspace_id = workspace_id
        self.session = requests.Session()
        self.session.headers.update({
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        })
        self._user_id: Optional[str] = None
    
    @property
    def user_id(self) -> str:
        """Get and cache the current user's ID."""
        if self._user_id is None:
            self._user_id = self.get_user()["id"]
        return self._user_id
    
    def get_user(self) -> dict:
        """Get current user info."""
        response = self.session.get(f"{self.BASE_URL}/user")
        response.raise_for_status()
        return response.json()
    
    def get_projects(self, archived: bool = False) -> list[dict]:
        """
        Get all projects in the workspace.
        
        Args:
            archived: Whether to include archived projects
            
        Returns:
            List of project dictionaries
        """
        params = {"archived": str(archived).lower()}
        response = self.session.get(
            f"{self.BASE_URL}/workspaces/{self.workspace_id}/projects",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def get_time_entries(
        self,
        start: datetime,
        end: datetime,
        project_id: Optional[str] = None
    ) -> list[dict]:
        """
        Get time entries for the current user within a date range.
        
        Args:
            start: Start datetime
            end: End datetime
            project_id: Optional project ID to filter by
            
        Returns:
            List of time entry dictionaries
        """
        params = {
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "page-size": 500  # Max allowed
        }
        if project_id:
            params["project"] = project_id
            
        response = self.session.get(
            f"{self.BASE_URL}/workspaces/{self.workspace_id}/user/{self.user_id}/time-entries",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def create_time_entry(
        self,
        start: datetime,
        end: datetime,
        project_id: str,
        description: str,
        billable: bool = True
    ) -> dict:
        """
        Create a new time entry.
        
        Args:
            start: Start datetime
            end: End datetime
            project_id: Project ID
            description: Entry description
            billable: Whether the entry is billable
            
        Returns:
            Created time entry dictionary
        """
        payload = {
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "projectId": project_id,
            "description": description,
            "billable": billable,
            "type": "REGULAR"
        }
        
        response = self.session.post(
            f"{self.BASE_URL}/workspaces/{self.workspace_id}/time-entries",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def get_existing_entries_by_project_and_date(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> dict[str, set[str]]:
        """
        Get a mapping of project IDs to dates that already have entries.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Dictionary mapping project_id -> set of date strings (YYYY-MM-DD)
        """
        entries = self.get_time_entries(start_date, end_date)
        existing: dict[str, set[str]] = {}
        
        for entry in entries:
            project_id = entry.get("projectId")
            if not project_id:
                continue
            
            # Extract date from start time
            start_str = entry.get("timeInterval", {}).get("start", "")
            if start_str:
                date_str = start_str[:10]  # YYYY-MM-DD
                if project_id not in existing:
                    existing[project_id] = set()
                existing[project_id].add(date_str)
        
        return existing
