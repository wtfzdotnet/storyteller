"""REST API for Epic management in the Storyteller system."""

from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from models import Epic, StoryStatus

# Initialize FastAPI app
app = FastAPI(
    title="Storyteller Epic Management API",
    description="REST API for managing Epics in the AI Story Management System",
    version="1.0.0",
)

# Initialize StoryManager lazily
story_manager = None


def get_story_manager():
    """Get or initialize the StoryManager instance."""
    global story_manager
    if story_manager is None:
        from story_manager import StoryManager

        story_manager = StoryManager()
    return story_manager


# Pydantic models for API validation
class EpicCreateRequest(BaseModel):
    """Request model for creating an Epic."""

    title: str = Field(..., min_length=1, max_length=200, description="Epic title")
    description: str = Field(..., min_length=1, description="Epic description")
    business_value: str = Field(default="", description="Business value statement")
    acceptance_criteria: List[str] = Field(
        default_factory=list, description="List of acceptance criteria"
    )
    target_repositories: List[str] = Field(
        default_factory=list, description="Target repositories"
    )
    estimated_duration_weeks: Optional[int] = Field(
        default=None, ge=1, description="Estimated duration in weeks"
    )


class EpicUpdateRequest(BaseModel):
    """Request model for updating an Epic."""

    title: Optional[str] = Field(
        None, min_length=1, max_length=200, description="Epic title"
    )
    description: Optional[str] = Field(
        None, min_length=1, description="Epic description"
    )
    business_value: Optional[str] = Field(None, description="Business value statement")
    acceptance_criteria: Optional[List[str]] = Field(
        None, description="List of acceptance criteria"
    )
    target_repositories: Optional[List[str]] = Field(
        None, description="Target repositories"
    )
    estimated_duration_weeks: Optional[int] = Field(
        None, ge=1, description="Estimated duration in weeks"
    )
    status: Optional[str] = Field(None, description="Epic status")


class EpicResponse(BaseModel):
    """Response model for Epic data."""

    id: str
    title: str
    description: str
    business_value: str
    acceptance_criteria: List[str]
    target_repositories: List[str]
    estimated_duration_weeks: Optional[int]
    status: str
    created_at: datetime
    updated_at: datetime


class EpicListResponse(BaseModel):
    """Response model for listing Epics."""

    epics: List[EpicResponse]
    total: int


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
    success: bool = True


def epic_to_response(epic: Epic) -> EpicResponse:
    """Convert Epic model to EpicResponse."""
    return EpicResponse(
        id=epic.id,
        title=epic.title,
        description=epic.description,
        business_value=epic.business_value,
        acceptance_criteria=epic.acceptance_criteria,
        target_repositories=epic.target_repositories,
        estimated_duration_weeks=epic.estimated_duration_weeks,
        status=epic.status.value,
        created_at=epic.created_at,
        updated_at=epic.updated_at,
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "storyteller-api"}


@app.post("/epics", response_model=EpicResponse, status_code=201)
async def create_epic(epic_data: EpicCreateRequest):
    """Create a new Epic."""
    try:
        sm = get_story_manager()
        epic = sm.create_epic(
            title=epic_data.title,
            description=epic_data.description,
            business_value=epic_data.business_value,
            acceptance_criteria=epic_data.acceptance_criteria,
            target_repositories=epic_data.target_repositories,
            estimated_duration_weeks=epic_data.estimated_duration_weeks,
        )
        return epic_to_response(epic)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create epic: {str(e)}")


@app.get("/epics", response_model=EpicListResponse)
async def list_epics(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of epics to return"
    ),
    offset: int = Query(0, ge=0, description="Number of epics to skip"),
):
    """List all Epics with optional filtering."""
    try:
        sm = get_story_manager()
        all_epics = sm.get_all_epics()

        # Filter by status if provided
        if status:
            try:
                status_enum = StoryStatus(status.lower())
                all_epics = [epic for epic in all_epics if epic.status == status_enum]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Valid values: {[s.value for s in StoryStatus]}",
                )

        # Apply pagination
        total = len(all_epics)
        epics = all_epics[offset:offset + limit]

        return EpicListResponse(
            epics=[epic_to_response(epic) for epic in epics],
            total=total,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list epics: {str(e)}")


@app.get("/epics/{epic_id}", response_model=EpicResponse)
async def get_epic(epic_id: str):
    """Get a specific Epic by ID."""
    try:
        sm = get_story_manager()
        epic = sm.get_story(epic_id)
        if not epic:
            raise HTTPException(status_code=404, detail="Epic not found")

        if not isinstance(epic, Epic):
            raise HTTPException(status_code=400, detail="Story is not an Epic")

        return epic_to_response(epic)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get epic: {str(e)}")


@app.put("/epics/{epic_id}", response_model=EpicResponse)
async def update_epic(epic_id: str, update_data: EpicUpdateRequest):
    """Update an existing Epic."""
    try:
        sm = get_story_manager()
        # Get existing epic
        epic = sm.get_story(epic_id)
        if not epic:
            raise HTTPException(status_code=404, detail="Epic not found")

        if not isinstance(epic, Epic):
            raise HTTPException(status_code=400, detail="Story is not an Epic")

        # Update fields that were provided
        if update_data.title is not None:
            epic.title = update_data.title
        if update_data.description is not None:
            epic.description = update_data.description
        if update_data.business_value is not None:
            epic.business_value = update_data.business_value
        if update_data.acceptance_criteria is not None:
            epic.acceptance_criteria = update_data.acceptance_criteria
        if update_data.target_repositories is not None:
            epic.target_repositories = update_data.target_repositories
        if update_data.estimated_duration_weeks is not None:
            epic.estimated_duration_weeks = update_data.estimated_duration_weeks
        if update_data.status is not None:
            try:
                epic.status = StoryStatus(update_data.status.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Valid values: {[s.value for s in StoryStatus]}",
                )

        # Update timestamp
        epic.updated_at = datetime.now()

        # Save to database
        sm.database.save_story(epic)

        return epic_to_response(epic)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update epic: {str(e)}")


@app.delete("/epics/{epic_id}", response_model=MessageResponse)
async def delete_epic(epic_id: str):
    """Delete an Epic and all its child stories (cascade)."""
    try:
        sm = get_story_manager()
        # Check if epic exists
        epic = sm.get_story(epic_id)
        if not epic:
            raise HTTPException(status_code=404, detail="Epic not found")

        if not isinstance(epic, Epic):
            raise HTTPException(status_code=400, detail="Story is not an Epic")

        # Delete epic and children (cascade)
        success = sm.delete_story(epic_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete epic")

        return MessageResponse(
            message=f"Epic {epic_id} and all child stories deleted successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete epic: {str(e)}")


@app.get("/epics/{epic_id}/hierarchy")
async def get_epic_hierarchy(epic_id: str):
    """Get complete Epic hierarchy including all user stories and sub-stories."""
    try:
        sm = get_story_manager()
        hierarchy = sm.get_epic_hierarchy(epic_id)
        if not hierarchy:
            raise HTTPException(status_code=404, detail="Epic hierarchy not found")

        # Convert to a JSON-serializable format
        return {
            "epic": epic_to_response(hierarchy.epic).model_dump(),
            "user_stories": [
                {
                    "id": us.id,
                    "title": us.title,
                    "description": us.description,
                    "status": us.status.value,
                    "user_persona": us.user_persona,
                    "user_goal": us.user_goal,
                    "acceptance_criteria": us.acceptance_criteria,
                    "target_repositories": us.target_repositories,
                    "story_points": us.story_points,
                    "created_at": us.created_at.isoformat(),
                    "updated_at": us.updated_at.isoformat(),
                }
                for us in hierarchy.user_stories
            ],
            "sub_stories": {
                us_id: [
                    {
                        "id": ss.id,
                        "title": ss.title,
                        "description": ss.description,
                        "status": ss.status.value,
                        "department": ss.department,
                        "technical_requirements": ss.technical_requirements,
                        "dependencies": ss.dependencies,
                        "target_repository": ss.target_repository,
                        "assignee": ss.assignee,
                        "estimated_hours": ss.estimated_hours,
                        "created_at": ss.created_at.isoformat(),
                        "updated_at": ss.updated_at.isoformat(),
                    }
                    for ss in sub_stories
                ]
                for us_id, sub_stories in hierarchy.sub_stories.items()
            },
            "progress": hierarchy.get_epic_progress(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get epic hierarchy: {str(e)}"
        )


# Epic breakdown endpoints

class EpicBreakdownRequest(BaseModel):
    """Request model for breaking down an epic into user stories."""

    max_user_stories: int = Field(
        default=5, ge=1, le=20, description="Maximum number of user stories to create"
    )
    target_repositories: Optional[List[str]] = Field(
        default=None, description="Target repositories for user stories"
    )


class UserStoryResponse(BaseModel):
    """Response model for User Story data."""

    id: str
    epic_id: str
    title: str
    description: str
    user_persona: str
    user_goal: str
    acceptance_criteria: List[str]
    target_repositories: List[str]
    story_points: Optional[int]
    status: str
    created_at: datetime
    updated_at: datetime


class EpicBreakdownResponse(BaseModel):
    """Response model for epic breakdown operation."""

    epic_id: str
    user_stories_created: int
    user_stories: List[UserStoryResponse]
    breakdown_summary: str


@app.post("/epics/{epic_id}/breakdown", response_model=EpicBreakdownResponse)
async def breakdown_epic(epic_id: str, request: EpicBreakdownRequest):
    """Break down an epic into user stories using AI analysis."""
    try:
        sm = get_story_manager()

        # Perform the breakdown
        user_stories = await sm.breakdown_epic_to_user_stories(
            epic_id=epic_id,
            max_user_stories=request.max_user_stories,
            target_repositories=request.target_repositories,
        )

        # Convert to response format
        user_story_responses = [
            UserStoryResponse(
                id=us.id,
                epic_id=us.epic_id,
                title=us.title,
                description=us.description,
                user_persona=us.user_persona,
                user_goal=us.user_goal,
                acceptance_criteria=us.acceptance_criteria,
                target_repositories=us.target_repositories,
                story_points=us.story_points,
                status=us.status.value,
                created_at=us.created_at,
                updated_at=us.updated_at,
            )
            for us in user_stories
        ]

        return EpicBreakdownResponse(
            epic_id=epic_id,
            user_stories_created=len(user_stories),
            user_stories=user_story_responses,
            breakdown_summary=(
                f"Successfully created {len(user_stories)} user stories "
                f"from epic {epic_id}"
            ),
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to break down epic: {str(e)}"
        )
