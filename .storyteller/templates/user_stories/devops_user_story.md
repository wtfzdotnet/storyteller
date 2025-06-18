# DevOps User Story Template

## User Story
As a **{{ user_persona }}**, I want **{{ user_goal }}** so that **{{ business_value }}**.

## Acceptance Criteria
{% for criteria in acceptance_criteria %}
- [ ] {{ criteria }}
{% endfor %}

## Technical Requirements
- Infrastructure deployment and management
- CI/CD pipeline configuration
- Monitoring and observability setup
- Security and compliance implementation
- Performance optimization
- Disaster recovery planning
- Container orchestration

## Department Focus
- **Primary**: DevOps Engineering
- **Secondary**: Backend Development, Security

## Estimated Story Points
{{ story_points | default(5) }}

## Target Repository
{{ target_repository | default("storyteller") }}

## Dependencies
{% for dependency in dependencies %}
- {{ dependency }}
{% endfor %}

## Sub-stories to Generate
- Infrastructure provisioning
- CI/CD pipeline setup
- Monitoring and alerting configuration
- Security hardening
- Performance tuning
- Backup and disaster recovery
- Documentation and runbooks