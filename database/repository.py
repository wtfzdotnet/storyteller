"""Repository layer for hierarchical story management."""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, desc

from .models import Epic, Story, SubStory


class StoryRepository:
    """Repository for managing hierarchical story data."""

    def __init__(self, db_session: Session):
        self.db = db_session

    # Epic operations
    def create_epic(self, title: str, description: str, story_id: str, **kwargs) -> Epic:
        """Create a new epic."""
        epic = Epic(
            title=title,
            description=description,
            story_id=story_id,
            **kwargs
        )
        self.db.add(epic)
        self.db.commit()
        self.db.refresh(epic)
        return epic

    def get_epic(self, epic_id: int) -> Optional[Epic]:
        """Get epic by ID with all related data."""
        return (
            self.db.query(Epic)
            .options(
                selectinload(Epic.stories).selectinload(Story.sub_stories)
            )
            .filter(Epic.id == epic_id)
            .first()
        )

    def get_epic_by_story_id(self, story_id: str) -> Optional[Epic]:
        """Get epic by external story ID."""
        return (
            self.db.query(Epic)
            .options(
                selectinload(Epic.stories).selectinload(Story.sub_stories)
            )
            .filter(Epic.story_id == story_id)
            .first()
        )

    def list_epics(self, limit: int = 50, offset: int = 0) -> List[Epic]:
        """List all epics with story counts."""
        return (
            self.db.query(Epic)
            .order_by(desc(Epic.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    # Story operations
    def create_story(
        self, 
        title: str, 
        description: str, 
        story_id: str, 
        epic_id: Optional[int] = None,
        **kwargs
    ) -> Story:
        """Create a new story."""
        story = Story(
            title=title,
            description=description,
            story_id=story_id,
            epic_id=epic_id,
            **kwargs
        )
        self.db.add(story)
        self.db.commit()
        self.db.refresh(story)
        return story

    def get_story(self, story_id: int) -> Optional[Story]:
        """Get story by ID with related data."""
        return (
            self.db.query(Story)
            .options(
                selectinload(Story.sub_stories),
                selectinload(Story.epic)
            )
            .filter(Story.id == story_id)
            .first()
        )

    def get_story_by_external_id(self, story_id: str) -> Optional[Story]:
        """Get story by external story ID."""
        return (
            self.db.query(Story)
            .options(
                selectinload(Story.sub_stories),
                selectinload(Story.epic)
            )
            .filter(Story.story_id == story_id)
            .first()
        )

    def list_stories_by_epic(self, epic_id: int) -> List[Story]:
        """List all stories for an epic."""
        return (
            self.db.query(Story)
            .options(selectinload(Story.sub_stories))
            .filter(Story.epic_id == epic_id)
            .order_by(desc(Story.created_at))
            .all()
        )

    # Sub-story operations
    def create_sub_story(
        self,
        title: str,
        description: str,
        story_id: str,
        parent_story_id: int,
        **kwargs
    ) -> SubStory:
        """Create a new sub-story."""
        sub_story = SubStory(
            title=title,
            description=description,
            story_id=story_id,
            story_id_fk=parent_story_id,
            **kwargs
        )
        self.db.add(sub_story)
        self.db.commit()
        self.db.refresh(sub_story)
        return sub_story

    def get_sub_story(self, sub_story_id: int) -> Optional[SubStory]:
        """Get sub-story by ID."""
        return (
            self.db.query(SubStory)
            .options(selectinload(SubStory.story))
            .filter(SubStory.id == sub_story_id)
            .first()
        )

    def get_sub_story_by_external_id(self, story_id: str) -> Optional[SubStory]:
        """Get sub-story by external story ID."""
        return (
            self.db.query(SubStory)
            .options(selectinload(SubStory.story))
            .filter(SubStory.story_id == story_id)
            .first()
        )

    def list_sub_stories_by_story(self, story_id: int) -> List[SubStory]:
        """List all sub-stories for a story."""
        return (
            self.db.query(SubStory)
            .filter(SubStory.story_id_fk == story_id)
            .order_by(desc(SubStory.created_at))
            .all()
        )

    # Hierarchy queries
    def get_full_hierarchy(self, epic_id: int) -> Optional[Epic]:
        """Get complete hierarchy starting from epic."""
        return self.get_epic(epic_id)

    def get_hierarchy_stats(self) -> Dict[str, int]:
        """Get hierarchy statistics."""
        epic_count = self.db.query(func.count(Epic.id)).scalar()
        story_count = self.db.query(func.count(Story.id)).scalar()
        sub_story_count = self.db.query(func.count(SubStory.id)).scalar()
        
        return {
            "epics": epic_count,
            "stories": story_count,
            "sub_stories": sub_story_count,
            "total_items": epic_count + story_count + sub_story_count
        }

    def search_by_title(self, search_term: str, limit: int = 20) -> Dict[str, List]:
        """Search across all story types by title."""
        search_pattern = f"%{search_term}%"
        
        epics = (
            self.db.query(Epic)
            .filter(Epic.title.ilike(search_pattern))
            .limit(limit)
            .all()
        )
        
        stories = (
            self.db.query(Story)
            .filter(Story.title.ilike(search_pattern))
            .limit(limit)
            .all()
        )
        
        sub_stories = (
            self.db.query(SubStory)
            .filter(SubStory.title.ilike(search_pattern))
            .limit(limit)
            .all()
        )
        
        return {
            "epics": epics,
            "stories": stories,
            "sub_stories": sub_stories
        }

    # Status management
    def update_status(self, item_type: str, item_id: int, status: str) -> bool:
        """Update status of any story item."""
        if item_type == "epic":
            item = self.db.query(Epic).filter(Epic.id == item_id).first()
        elif item_type == "story":
            item = self.db.query(Story).filter(Story.id == item_id).first()
        elif item_type == "sub_story":
            item = self.db.query(SubStory).filter(SubStory.id == item_id).first()
        else:
            return False
            
        if item:
            item.status = status
            self.db.commit()
            return True
        return False