"""Automation module for AI Story Management System."""

from .label_manager import LabelManager, LabelRule
from .workflow_processor import WorkflowProcessor, WorkflowResult

__all__ = ["LabelManager", "LabelRule", "WorkflowProcessor", "WorkflowResult"]
