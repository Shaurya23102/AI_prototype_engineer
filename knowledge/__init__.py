"""Knowledge pipeline — role resolution and concept loading."""

from .role_resolver import resolve_role, get_persona
from .loader import load_roles, get_concepts

__all__ = ["resolve_role", "get_persona", "load_roles", "get_concepts"]
