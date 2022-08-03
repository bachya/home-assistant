"""Define Outbreaks Near Me data models."""
from dataclasses import dataclass


@dataclass
class OutbreaksNearMeEntityDescriptionMixin:
    """Define an Outbreaks Near Me entity description mixin."""

    api_category: str
