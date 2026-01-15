"""
Description Generator

Generates realistic description variations for time entries based on templates.
"""

import random
from typing import Optional


class DescriptionGenerator:
    """Generates varied descriptions from templates and history."""
    
    # Common activity variations for different contexts
    ACTIVITY_MODIFIERS = [
        "reviewed", "worked on", "updated", "finished", "continued with",
        "made progress on", "completed", "started"
    ]
    
    TIME_CONTEXT = [
        "weekly", "daily", "end of week", "mid-week", "ongoing"
    ]
    
    def __init__(self, templates: Optional[list[str]] = None):
        """
        Initialize the description generator.
        
        Args:
            templates: List of description template strings
        """
        self.templates = templates or []
        self._used_recently: list[str] = []
    
    def add_templates(self, templates: list[str]) -> None:
        """Add more templates to the pool."""
        self.templates.extend(templates)
    
    def generate(self) -> str:
        """
        Generate a description variation.
        
        Returns:
            A description string
        """
        if not self.templates:
            return "general work and updates"
        
        # Avoid repeating the same description consecutively
        available = [t for t in self.templates if t not in self._used_recently]
        if not available:
            available = self.templates
            self._used_recently.clear()
        
        chosen = random.choice(available)
        self._used_recently.append(chosen)
        
        # Keep only last 3 used
        if len(self._used_recently) > 3:
            self._used_recently.pop(0)
        
        return self._create_variation(chosen)
    
    def _create_variation(self, template: str) -> str:
        """
        Create a slight variation of the template.
        
        Args:
            template: Base template string
            
        Returns:
            Varied description
        """
        # Split into activities
        activities = [a.strip() for a in template.split(",")]
        
        # Occasionally shuffle order
        if len(activities) > 1 and random.random() < 0.3:
            random.shuffle(activities)
        
        # Occasionally drop one activity if there are many
        if len(activities) > 2 and random.random() < 0.2:
            activities = random.sample(activities, len(activities) - 1)
        
        return ", ".join(activities)
    
    @classmethod
    def from_history(cls, entries: list[dict], project_id: str) -> "DescriptionGenerator":
        """
        Create a generator from historical entries for a specific project.
        
        Args:
            entries: List of time entry dictionaries
            project_id: Project ID to filter by
            
        Returns:
            DescriptionGenerator instance with extracted templates
        """
        templates = []
        seen = set()
        
        for entry in entries:
            if entry.get("projectId") != project_id:
                continue
            
            desc = entry.get("description", "").strip()
            if desc and desc not in seen:
                templates.append(desc)
                seen.add(desc)
        
        return cls(templates=templates)
