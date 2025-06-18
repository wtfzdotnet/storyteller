# Backend User Story Template

## User Story
As a **{{ user_persona }}**, I want **{{ user_goal }}** so that **{{ business_value }}**.

## Acceptance Criteria
{% for criteria in acceptance_criteria %}
- [ ] {{ criteria }}
{% endfor %}

## Technical Requirements
- Backend API development
- Database schema changes (if needed)
- Business logic implementation
- Error handling and validation
- Unit and integration tests

## Department Focus
- **Primary**: Backend Development
- **Secondary**: QA Engineering, DevOps

## Estimated Story Points
{{ story_points | default(3) }}

## Target Repository
backend

## Dependencies
{% for dependency in dependencies %}
- {{ dependency }}
{% endfor %}

## Sub-stories to Generate
- API endpoint implementation
- Database schema updates
- Business logic layer
- Input validation and error handling
- Unit tests
- Integration tests
- API documentation