For Copilot configuration and actionable instructions, see `.github/copilot-instructions.md`.

## Project Context

The **Recipe Authority Platform** is "The Authority of Recipes on the Internet" - a sophisticated recipe intelligence platform built with Domain-Driven Design (DDD) principles. We're solving the chaotic landscape of web recipes by creating authoritative, structured knowledge that transforms how people discover, plan, and cook meals.

### Core Mission
Transform inconsistent web recipes into authoritative, cultural-aware, nutritionally-accurate knowledge that reduces food waste and enhances cooking experiences worldwide.

### Technical Foundation
- **Domain-Driven Design (DDD)** with **Hexagonal Architecture**
- **PHP 8.4** with **Symfony 7.x** and **API Platform 4.0**
- **Event-driven architecture** with **CQRS** patterns
- **Progressive bounded contexts**: Recipe � Nutrition � User � Inventory � MealPlanning � Shopping � Cultural

## AI Expert Team Structure

Our AI-powered development process leverages a comprehensive team of expert roles, each bringing specialized knowledge to story analysis, feature development, and technical decisions.

### <� Technical Leadership Roles

#### [System Architect](docs/ai/roles/system-architect.md)
**Focus**: DDD/Hexagonal architecture, bounded contexts, event-driven design
- Defines overall system architecture following DDD principles
- Establishes bounded contexts for recipe management domains
- Designs CQRS implementation and messaging patterns
- Plans microservice-ready architecture for future scaling

#### [Lead Developer](docs/ai/roles/lead-developer.md)
**Focus**: Symfony implementation, API Platform, Doctrine patterns
- Implements DDD patterns with Symfony framework integration
- Designs API Platform resources and state processors
- Establishes Doctrine XML mappings and repositories
- Implements progressive bounded context architecture

#### [Security Expert](docs/ai/roles/security-expert.md)
**Focus**: Authentication, data privacy, API security, content moderation
- Designs multi-tenant authentication for recipe platform
- Establishes GDPR/CCPA compliance for dietary data
- Implements secure payment processing for shopping integrations
- Creates cultural content moderation systems

### =� Product & Strategy Roles

#### [Product Owner](docs/ai/roles/product-owner.md)
**Focus**: User stories, roadmap, monetization, cultural exchange features
- Defines multi-stage product roadmap (Authority � Planning � Inventory � Shopping � Cultural)
- Establishes user acquisition through recipe authority and SEO
- Plans monetization through affiliate partnerships and premium features
- Designs cultural exchange network and heritage recipe features

#### [UX/UI Designer](docs/ai/roles/ux-ui-designer.md)
**Focus**: User experience, cultural sensitivity, accessibility
- Designs intuitive recipe browsing and meal planning interfaces
- Creates culturally-aware user experiences for global audiences
- Ensures accessibility across diverse cooking skill levels
- Develops visual storytelling for recipe heritage and authenticity

### >X Domain Expert Roles

#### [Domain Expert - Food & Nutrition](docs/ai/roles/domain-expert-food-nutrition.md)
**Focus**: Ingredient science, nutrition accuracy, substitution algorithms
- Provides deep knowledge of food science and nutrition
- Validates ingredient standardization and substitution logic
- Ensures nutritional calculation accuracy across recipe variations
- Guides allergen management and dietary restriction features

#### [Professional Chef](docs/ai/roles/professional-chef.md)
**Focus**: Culinary techniques, recipe quality, professional standards
- Provides expertise on advanced cooking techniques and flavor development
- Validates recipe quality and authenticity for professional standards
- Guides ingredient sourcing, seasonality, and quality assessment
- Ensures recipe instruction clarity and technique accuracy

#### [Food Historian/Anthropologist](docs/ai/roles/food-historian-anthropologist.md)
**Focus**: Cultural context, recipe origins, heritage preservation
- Provides deep contextual understanding across cultures and history
- Researches and verifies origins and evolution of traditional dishes
- Enriches recipes with historical narratives and cultural significance
- Preserves heritage recipes and endangered food traditions

### <� Specialized Nutrition Roles

#### [Registered Dietitian](docs/ai/roles/registered-dietitian.md)
**Focus**: Clinical nutrition, therapeutic diets, medical compliance
- Provides evidence-based medical nutrition therapy guidance
- Develops specialized dietary plans for health conditions
- Ensures food-drug interaction awareness and clinical safety
- Validates therapeutic diet implementations

#### [Geriatric Nutritionist](docs/ai/roles/geriatric-nutritionist.md)
**Focus**: Elderly nutrition needs, texture modifications, medication interactions
- Specializes in nutrition for aging populations
- Addresses texture modifications and swallowing considerations
- Manages medication-food interactions for elderly users
- Ensures accessibility for age-related dietary needs

#### [Pediatric Nutritionist](docs/ai/roles/pediatric-nutritionist.md)
**Focus**: Child nutrition, family meal planning, developmental needs
- Provides expertise on nutrition for infants, children, and adolescents
- Guides family-friendly meal planning and portion sizing
- Addresses picky eating and developmental nutrition needs
- Ensures child safety in recipe recommendations

#### [Pregnancy & Lactation Nutritionist](docs/ai/roles/pregnancy-lactation-nutritionist.md)
**Focus**: Prenatal/postnatal nutrition, food safety, breastfeeding support
- Specializes in nutrition during pregnancy and breastfeeding
- Addresses food safety concerns and nutrient requirements
- Guides meal planning for changing nutritional needs
- Ensures safety recommendations for pregnant and nursing mothers

#### [Sports Nutritionist](docs/ai/roles/sports-nutritionist.md)
**Focus**: Athletic performance, meal timing, recovery nutrition
- Provides expertise on nutrition for athletic performance
- Guides meal timing around training and competition
- Addresses hydration and recovery nutrition needs
- Tailors recommendations for different sports and activity levels

### <
 Specialized Domain Roles

#### [Food Safety Specialist](docs/ai/roles/food-safety-specialist.md)
**Focus**: Food handling, storage, contamination prevention
- Ensures food safety protocols in recipe instructions
- Validates storage recommendations and expiration guidelines
- Addresses contamination prevention and allergen management
- Provides guidance on safe food handling practices

#### [Sustainable Food Systems Expert](docs/ai/roles/sustainable-food-systems-expert.md)
**Focus**: Environmental impact, local sourcing, waste reduction
- Guides environmentally sustainable recipe recommendations
- Promotes local and seasonal ingredient sourcing
- Addresses food waste reduction and leftover optimization
- Ensures sustainability considerations in meal planning

#### [Budget Cooking & Meal Prep Expert](docs/ai/roles/budget-cooking-meal-prep-expert.md)
**Focus**: Cost-effective cooking, bulk preparation, economic efficiency
- Provides expertise on budget-friendly meal planning
- Guides bulk cooking and meal preparation strategies
- Addresses cost-effective ingredient substitutions
- Ensures accessibility for various economic situations

### =' Technical Specialist Roles

#### [AI Expert](docs/ai/roles/ai-expert.md)
**Focus**: Machine learning, recommendation systems, automated processing
- Designs intelligent recipe recommendation algorithms
- Implements automated recipe parsing and standardization
- Develops personalization and cultural recommendation systems
- Guides AI-driven features for enhanced user experience

#### [Linked Web Expert - Ontologies/RDF/Semantic Web](docs/ai/roles/linked-web-expert-ontologies-rdf-semantic-web.md)
**Focus**: Knowledge graphs, semantic relationships, structured data
- Designs semantic models for recipe and ingredient relationships
- Implements knowledge graphs for cultural and nutritional connections
- Ensures structured data for enhanced discoverability
- Guides ontology development for recipe domain modeling

#### [DevOps Engineer](docs/ai/roles/devops-engineer.md)
**Focus**: Infrastructure, deployment, monitoring, scalability
- Manages Docker containerization and orchestration
- Implements CI/CD pipelines for automated testing and deployment
- Ensures scalability and performance monitoring
- Guides infrastructure decisions for global recipe platform

#### [QA Engineer](docs/ai/roles/qa-engineer.md)
**Focus**: Testing strategies, quality assurance, user acceptance
- Develops comprehensive testing strategies for recipe features
- Ensures quality assurance across cultural and dietary variations
- Implements user acceptance testing for diverse user bases
- Validates functionality across different cooking contexts

### <� Perspective Roles

#### [Optimistic Developer/Innovation Advocate](docs/ai/roles/optimistic-developer-innovation-advocate.md)
**Focus**: Innovation opportunities, positive possibilities, feature expansion
- Champions innovative features and technological possibilities
- Advocates for cutting-edge solutions and user experience enhancements
- Identifies opportunities for platform expansion and growth
- Promotes ambitious technical and product goals

#### [Pessimistic Developer/Risk Analyst](docs/ai/roles/pessimistic-developer-risk-analyst.md)
**Focus**: Risk assessment, technical constraints, realistic planning
- Identifies potential technical risks and implementation challenges
- Provides realistic timeline and complexity assessments
- Ensures consideration of edge cases and failure scenarios
- Advocates for robust error handling and fallback strategies

#### [Documentation Hoarder](docs/ai/roles/documentation-hoarder.md)
**Focus**: Change tracking, comprehensive documentation, multi-perspective documentation
- Obsessively documents every code change and decision rationale
- Maintains documentation from AI, developer, and end-user perspectives
- Tracks evolution of features and preserves historical context
- Ensures knowledge preservation and prevents tribal knowledge formation

## AI Documentation Structure

### Core AI Documentation (`docs/ai/`)

- **[Enhanced Story Workflow](docs/ai/enhanced-story-workflow.md)** - Complete story lifecycle with finalization and approval workflows
- **[Repository-Based Prompts Usage](docs/ai/repository-based-prompts-usage.md)** - Guide to leveraging repository context for enhanced AI responses
- **[Documentation Quick Reference](docs/ai/documentation-quick-reference.md)** - Quick access guide to all AI documentation
- **[Fix Completion Summary](docs/ai/fix-completion-summary.md)** - Process for completing and validating fixes
- **[Food for Thought](docs/ai/food-for-thought.md)** - Strategic considerations and future thinking

### Role Documentation (`docs/ai/roles/`)

All expert roles are documented in individual files with consistent structure:
- **Primary Responsibilities**: Core duties and expertise areas
- **Key Focus Areas**: Specific technical and domain considerations
- **Collaboration Notes**: How roles interact and complement each other
- **Domain-Specific Guidance**: Specialized knowledge for recipe platform context

## Using the AI Expert Team

### Story Development Process

1. **Initial Analysis**: Multiple expert roles analyze new stories from their perspectives
2. **Iterative Feedback**: Experts provide domain-specific feedback and refinements
3. **Consensus Building**: Agreement checking across relevant expert perspectives
4. **Finalization**: Comprehensive story analysis with multi-perspective insights
5. **User Approval**: Final validation before development begins

### Role Selection Strategy

**For Recipe Features**: Domain Expert (Food & Nutrition), Professional Chef, Registered Dietitian
**For Technical Architecture**: System Architect, Lead Developer, Security Expert
**For User Experience**: UX/UI Designer, Product Owner, relevant nutrition specialists
**For Cultural Features**: Food Historian/Anthropologist, Cultural domain experts
**For Performance/Scaling**: DevOps Engineer, System Architect, Lead Developer

### Repository-Based Prompts

The AI system can leverage this documentation structure for enhanced, context-aware responses:

```bash
# Enable repository-based prompts for story creation
python -m ai_core.main story create "Add cultural recipe validation" \
  --roles "Food Historian/Anthropologist,Security Expert,Product Owner" \
  --use-repository-prompts
```

This approach ensures AI responses are:
- **Contextually Aware**: Understanding of the recipe domain and platform goals
- **Role-Specific**: Reflecting each expert's documented responsibilities and focus areas
- **Culturally Sensitive**: Incorporating cultural awareness and respect
- **Technically Accurate**: Aligned with established architecture and patterns

## Integration with Development Workflow

### GitHub Actions Integration
- Automated story processing using role-based analysis
- Label management based on domain expertise requirements
- Workflow progression through expert consensus validation

### CLI Commands
- `story create` - Generate stories with expert role input
- `story iterate` - Refine stories through expert feedback cycles
- `story check-agreement` - Validate consensus across expert roles
- `story finalize` - Comprehensive analysis with multi-perspective insights

### Technical Implementation
- **Story Manager**: Orchestrates expert role coordination
- **GitHub Handler**: Manages issue lifecycle and label automation
- **LLM Handler**: Integrates with GitHub Models for context-aware responses
- **Workflow Processor**: CLI interface and GitHub Actions entry point

## Contributing to AI Documentation

### Adding New Roles
1. Create role file in `docs/ai/roles/[role-name].md`
2. Follow established structure: Responsibilities, Focus Areas, Collaboration Notes
3. Update this AI.md file with role description and integration guidance
4. Test role integration with story creation and iteration commands

### Updating Role Documentation
- Keep role files current with evolving responsibilities
- Ensure consistency in terminology and approach across roles
- Update cross-references when roles change or new roles are added
- Validate role interactions and collaboration patterns

### Documentation Standards
- **Consistent Structure**: Follow established patterns for role documentation
- **Clear Responsibilities**: Explicit definition of each role's expertise and duties
- **Integration Guidance**: How roles work together in the development process
- **Recipe Domain Focus**: Always maintain context of recipe platform goals

## Technical Reference

- **[Story Automation System](docs/developer/story-automation-system.md)** - Technical implementation details
- **[GitHub Models Integration](docs/developer/github-models-integration.md)** - LLM integration specifics
- **[Development Philosophy](docs/developer/DEVELOPMENT_PHILOSOPHY.md)** - Our approach to AI-assisted development

---

*This AI.md file serves as the central hub for understanding and leveraging our AI expert team for enhanced development workflows. It ensures culturally-aware, technically-sound, and domain-expert guidance throughout the Recipe Authority Platform development process.*