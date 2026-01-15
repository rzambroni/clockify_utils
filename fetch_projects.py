#!/usr/bin/env python3
"""
Fetch Project IDs

Helper script to list all projects and their IDs in your Clockify workspace.
Use this to populate your config.yaml file.
"""

import os
import sys

from dotenv import load_dotenv

from clockify_client import ClockifyClient


def main():
    load_dotenv()
    
    api_key = os.environ.get("CLOCKIFY_API_KEY")
    workspace_id = os.environ.get("CLOCKIFY_WORKSPACE_ID")
    
    if not api_key:
        print("❌ CLOCKIFY_API_KEY not set")
        print("   Set it in your .env file or environment")
        sys.exit(1)
    
    if not workspace_id:
        # Try to get workspaces
        import requests
        session = requests.Session()
        session.headers.update({"X-Api-Key": api_key})
        
        print("🔍 Fetching your workspaces...\n")
        response = session.get("https://api.clockify.me/api/v1/workspaces")
        response.raise_for_status()
        workspaces = response.json()
        
        print("Your workspaces:")
        print("-" * 60)
        for ws in workspaces:
            print(f"  📁 {ws['name']}")
            print(f"     ID: {ws['id']}")
            print()
        
        if len(workspaces) == 1:
            workspace_id = workspaces[0]["id"]
            print(f"Using the only workspace: {workspaces[0]['name']}\n")
        else:
            print("Set CLOCKIFY_WORKSPACE_ID to one of the above IDs")
            sys.exit(0)
    
    client = ClockifyClient(api_key=api_key, workspace_id=workspace_id)
    
    print("🔍 Fetching projects...\n")
    projects = client.get_projects()
    
    print("Your projects:")
    print("-" * 60)
    
    for project in sorted(projects, key=lambda p: p.get("name", "")):
        name = project.get("name", "Unknown")
        project_id = project.get("id")
        client_name = project.get("clientName", "")
        
        print(f"  📊 {name}")
        if client_name:
            print(f"     Client: {client_name}")
        print(f"     ID: {project_id}")
        print()
    
    print("-" * 60)
    print(f"Total: {len(projects)} projects")
    print()
    print("Copy the project IDs to your config.yaml file!")


if __name__ == "__main__":
    main()
