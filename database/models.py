"""Hierarchical story data models."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship, backref

from .base import Base


class Epic(Base):
    """Epic: Top-level story container for major features or initiatives."""
    
    __tablename__ = "epics"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    story_id = Column(String(50), unique=True, nullable=False, index=True)  # External story ID
    
    # Status and metadata
    status = Column(String(50), default="open", index=True)
    priority = Column(String(20), default="medium")
    labels = Column(JSON)  # Store as JSON array
    
    # GitHub integration
    github_repository = Column(String(255))
    github_issue_number = Column(Integer)
    github_url = Column(String(500))
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    stories = relationship("Story", back_populates="epic", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Epic(id={self.id}, title='{self.title}', story_id='{self.story_id}')>"


class Story(Base):
    """User Story: Mid-level story that belongs to an Epic."""
    
    __tablename__ = "stories"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    story_id = Column(String(50), unique=True, nullable=False, index=True)  # External story ID
    
    # Hierarchical relationship
    epic_id = Column(Integer, ForeignKey("epics.id"), nullable=True, index=True)
    
    # Status and metadata
    status = Column(String(50), default="open", index=True)
    priority = Column(String(20), default="medium")
    labels = Column(JSON)  # Store as JSON array
    story_points = Column(Integer)
    
    # Content and analysis
    original_content = Column(Text)
    synthesized_analysis = Column(Text)
    expert_analyses_count = Column(Integer, default=0)
    target_repositories = Column(JSON)  # Store as JSON array
    
    # GitHub integration
    github_repository = Column(String(255))
    github_issue_number = Column(Integer)
    github_url = Column(String(500))
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    epic = relationship("Epic", back_populates="stories")
    sub_stories = relationship("SubStory", back_populates="story", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Story(id={self.id}, title='{self.title}', story_id='{self.story_id}')>"


class SubStory(Base):
    """Sub-story: Lowest level task that belongs to a User Story."""
    
    __tablename__ = "sub_stories"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    story_id = Column(String(50), unique=True, nullable=False, index=True)  # External story ID
    
    # Hierarchical relationship
    story_id_fk = Column(Integer, ForeignKey("stories.id"), nullable=False, index=True)
    
    # Status and metadata
    status = Column(String(50), default="open", index=True)
    priority = Column(String(20), default="medium")
    labels = Column(JSON)  # Store as JSON array
    story_points = Column(Integer)
    
    # Implementation details
    acceptance_criteria = Column(JSON)  # Store as JSON array
    technical_requirements = Column(Text)
    estimated_hours = Column(Integer)
    
    # GitHub integration
    github_repository = Column(String(255))
    github_issue_number = Column(Integer)
    github_url = Column(String(500))
    
    # Assignment
    assigned_to = Column(String(255))
    assigned_role = Column(String(100))  # Expert role responsible
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    story = relationship("Story", back_populates="sub_stories")
    
    def __repr__(self):
        return f"<SubStory(id={self.id}, title='{self.title}', story_id='{self.story_id}')>"


# Helper methods for querying hierarchies
def get_epic_hierarchy(db_session, epic_id: int) -> Optional[Epic]:
    """Get an epic with all its stories and sub-stories."""
    return (
        db_session.query(Epic)
        .filter(Epic.id == epic_id)
        .first()
    )


def get_story_hierarchy(db_session, story_id: int) -> Optional[Story]:
    """Get a story with all its sub-stories."""
    return (
        db_session.query(Story)
        .filter(Story.id == story_id)
        .first()
    )


def get_all_epics_with_counts(db_session) -> List[dict]:
    """Get all epics with story and sub-story counts."""
    from sqlalchemy import func
    
    return (
        db_session.query(
            Epic,
            func.count(Story.id).label("story_count"),
            func.count(SubStory.id).label("sub_story_count")
        )
        .outerjoin(Story)
        .outerjoin(SubStory)
        .group_by(Epic.id)
        .all()
    )