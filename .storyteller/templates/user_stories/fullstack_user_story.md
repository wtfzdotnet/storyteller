# Full-Stack User Story Template

## User Story
As a **{{ user_persona }}**, I want **{{ user_goal }}** so that **{{ business_value }}**.

## Acceptance Criteria
{% for criteria in acceptance_criteria %}
- [ ] {{ criteria }}
{% endfor %}

## Technical Requirements
- Backend API development
- Frontend interface implementation
- Database integration
- End-to-end data flow
- Authentication/authorization (if needed)
- Comprehensive testing across stack

## Department Focus
- **Primary**: Backend Development, Frontend Development
- **Secondary**: UX/UI Design, QA Engineering, DevOps

## Estimated Story Points
{{ story_points | default(8) }}

## Target Repositories
- backend
- frontend

## Dependencies
{% for dependency in dependencies %}
- {{ dependency }}
{% endfor %}

## Sub-stories to Generate
- Backend API endpoints
- Database schema and models
- Frontend components and views
- API integration layer
- Authentication flow (if needed)
- End-to-end testing
- Performance optimization
- Documentation