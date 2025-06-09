# Story Management Workflow - User Guide

This guide explains how to submit user stories and interact with the AI-powered story management system for the Recipe Authority Platform.

## Overview

The story management system provides intelligent assistance for creating, refining, and tracking user stories. It leverages our expert AI team to provide contextual feedback specific to the recipe management domain.

## Submission Methods

### Method 1: GitHub Issues (Recommended)

The primary way to submit and manage user stories is through GitHub Issues with automated AI assistance.

#### Creating a New Story

1. **Navigate to Issues**: Go to the GitHub repository and click "Issues"
2. **Create New Issue**: Click "New issue"
3. **Write Your Story**: Describe your user story or feature request
4. **Add Labels**: The system will automatically suggest and apply relevant labels
5. **Submit**: Click "Submit new issue"

#### Story Labels

The system uses labels to categorize and route stories:

- **`story`**: Marks the issue as a user story
- **`needs-analysis`**: Requires deeper analysis from the AI team
- **`in-review`**: Currently being reviewed by AI experts
- **`feedback-provided`**: AI feedback has been added
- **`ready-for-development`**: Story is ready for implementation
- **`blocked`**: Story is blocked and needs attention

Domain-specific labels:
- **`recipe-domain`**: Recipe-related functionality
- **`nutrition-domain`**: Nutrition and dietary features
- **`inventory-domain`**: Inventory management features
- **`meal-planning-domain`**: Meal planning functionality
- **`shopping-domain`**: Shopping and grocery features
- **`cultural-domain`**: Cultural recipe features

#### Automated Workflow

When you submit or update a story, the system automatically:

1. **Analyzes the content** using our AI expert team
2. **Applies relevant labels** based on domain and complexity
3. **Generates expert feedback** from relevant specialists
4. **Updates the story** with recommendations and technical insights
5. **Tracks progress** through the development lifecycle

#### Getting AI Feedback

The AI team will automatically provide feedback, but you can also:

- **Add comments** asking specific questions
- **Use @mentions** to request specific expert input (e.g., "Could the @nutrition-expert review this?")
- **Update the story** description to trigger re-analysis

### Method 2: CLI Interface (Advanced Users)

For developers and advanced users, there's a command-line interface available.

#### Setup

```bash
# Navigate to the AI directory
cd ai/

# Install dependencies
pip install -r requirements.txt

# Authenticate (requires GitHub token)
export GITHUB_TOKEN="your_github_token"
```

#### Creating Stories via CLI

```bash
# Create a new story
python -m ai_core.main create-story \
  --title "Recipe import from popular cooking websites" \
  --description "As a user, I want to import recipes from cooking websites so that I can easily add them to my cookbook" \
  --labels "story,recipe-domain"

# Get feedback on existing story
python -m ai_core.main analyze-story \
  --issue-number 123 \
  --roles "domain-expert,system-architect"

# Update story status
python -m ai_core.main update-story \
  --issue-number 123 \
  --status "ready-for-development"
```

#### CLI Commands

- **`create-story`**: Create a new user story
- **`analyze-story`**: Get AI analysis and feedback
- **`update-story`**: Update story status or content
- **`list-stories`**: List all stories with filters
- **`get-feedback`**: Retrieve AI feedback for a story

## Story Writing Best Practices

### User Story Format

Follow the standard format:
```
As a [user type], I want [functionality] so that [benefit/goal].
```

**Example:**
```
As a home cook, I want to automatically scale recipe ingredients 
so that I can cook for different numbers of people without manual calculations.
```

### Acceptance Criteria

Include clear acceptance criteria:
```
**Acceptance Criteria:**
- [ ] Recipe ingredients scale proportionally
- [ ] Nutritional information updates automatically
- [ ] Serving size can be adjusted from 1-20 people
- [ ] Fractional measurements are handled correctly
- [ ] Imperial and metric units are supported
```

### Domain Context

Provide context about the recipe domain:
- **Recipe types** involved (main course, dessert, etc.)
- **Dietary considerations** (allergies, restrictions)
- **Cultural aspects** (regional variations, authenticity)
- **Nutritional requirements** (calorie tracking, macros)
- **User personas** (home cook, professional chef, nutritionist)

## AI Expert Team Feedback

### What to Expect

The AI expert team provides feedback from relevant specialists:

#### Technical Feedback
- **System Architect**: Technical feasibility and architecture considerations
- **Lead Developer**: Implementation complexity and Symfony-specific guidance
- **Security Expert**: Security implications and data privacy concerns

#### Domain Feedback  
- **Domain Expert (Food & Nutrition)**: Culinary science and nutrition accuracy
- **Food Historian**: Cultural authenticity and historical context
- **Professional Chef**: Practical cooking workflow considerations

#### Product Feedback
- **Product Owner**: User value, prioritization, and business impact
- **UX/UI Designer**: User experience and interface design implications
- **QA Engineer**: Testing considerations and quality assurance

### Interpreting Feedback

AI feedback includes:

1. **Feasibility Assessment**: Technical and domain feasibility
2. **Implementation Guidance**: Specific technical recommendations
3. **Risk Analysis**: Potential challenges and mitigation strategies
4. **Enhancement Suggestions**: Ways to improve the story
5. **Related Considerations**: Cross-domain impacts and dependencies

### Example Feedback

```markdown
## AI Expert Team Feedback

**System Architect:**
This story involves the Recipe Domain and Nutrition Domain. Consider implementing 
ingredient scaling as a domain service with proper aggregate boundaries.

**Domain Expert (Food & Nutrition):**
Scaling algorithms must account for non-linear ingredient relationships. Some 
ingredients (like salt, spices) don't scale proportionally.

**Lead Developer:**
Implement using Symfony's calculation services. Consider caching scaled recipes 
for performance.

**UX/UI Designer:**
Include visual feedback for scaling adjustments. Consider preset serving sizes 
for common scenarios.
```

## Story Lifecycle

### 1. Submission
- Story is created via GitHub Issues or CLI
- Initial labels are applied automatically
- System triggers AI analysis

### 2. Analysis
- AI expert team analyzes the story
- Relevant specialists provide feedback
- Technical feasibility is assessed
- Labels are updated based on analysis

### 3. Refinement
- Story author can address feedback
- Additional iterations with AI team
- Acceptance criteria are refined
- Dependencies are identified

### 4. Ready for Development
- Story has clear requirements
- Technical approach is defined
- All blockers are resolved
- Development team can begin work

### 5. Implementation Tracking
- Progress is tracked through development
- AI team can provide implementation guidance
- Story is validated against acceptance criteria

## Tips for Effective Stories

### Be Specific
Instead of: "Better recipe search"
Write: "As a user with dietary restrictions, I want to filter recipes by allergens so that I can safely find meals I can eat."

### Include Context
- Mention specific user personas
- Reference relevant domains (recipe, nutrition, etc.)
- Consider cultural and international aspects
- Think about mobile and kitchen contexts

### Consider Technical Constraints
- Our platform uses Symfony/DDD architecture
- We support both web and mobile interfaces
- Consider real-time requirements (SSE)
- Think about data sourcing and quality

### Cultural Sensitivity
- Consider international users
- Respect diverse food traditions
- Think about regional ingredient variations
- Consider multi-language support needs

## Troubleshooting

### Common Issues

**Story not getting AI feedback:**
- Check that the `story` label is applied
- Ensure the description is detailed enough
- Try adding a comment to trigger re-analysis

**Labels not applying correctly:**
- The system may need a few minutes to process
- Manual label correction is possible
- Contact administrators for persistent issues

**CLI authentication issues:**
- Verify GitHub token has correct permissions
- Ensure token has `repo` and `issues` scopes
- Check token hasn't expired

### Getting Help

- **GitHub Discussions**: For general questions about the story process
- **Issues**: For bugs or problems with the automation system
- **Documentation**: Check [docs/developer/](../developer/) for technical details
- **AI Team**: Add comments requesting specific expert input

## Advanced Features

### Batch Story Creation
Create multiple related stories:
```bash
python -m ai_core.main create-epic \
  --title "Recipe Import Feature Epic" \
  --stories "web-scraping,data-parsing,user-interface,error-handling"
```

### Story Dependencies
Link related stories:
```markdown
**Dependencies:**
- Blocked by #45 (Ingredient standardization)
- Blocks #67 (Meal planning integration)
```

### Custom AI Analysis
Request specific expert combinations:
```bash
python -m ai_core.main analyze-story \
  --issue-number 123 \
  --roles "system-architect,security-expert,ux-designer" \
  --focus "architecture,security"
```

---

*This guide covers the complete story management workflow. For technical implementation details, see the [developer documentation](../developer/). For domain-specific guidance, consult the [AI role documentation](../ai/roles/).*

