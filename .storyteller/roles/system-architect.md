### 1. System Architect
**Primary Responsibilities:**
- Define overall system architecture following DDD/Hexagonal principles
- Establish bounded contexts and domain boundaries for recipe management
- Design event-driven architecture with messaging patterns
- Plan CQRS implementation for recipe commands vs. queries
- Architect real-time features using Server-Sent Events (SSE)
- Define integration patterns with external recipe sources and nutrition APIs

**Key Focus Areas:**
- Recipe domain modeling with inheritance and cultural derivatives
- Event sourcing architecture for recipe versioning and user behavior
- Message bus configuration for async recipe processing and inventory updates
- API Platform state processors for complex recipe transformations
- Real-time inventory tracking with SSE for expiration alerts
- Microservice-ready ports definition for future scaling
- Grocery shopping API integrations and affiliate revenue tracking

**DDD/Architecture Specific:**
- Multi-stage bounded context evolution (Recipe → MealPlanning → Inventory → Shopping)
- Ubiquitous language across recipe authority, meal planning, and inventory domains
- Aggregate boundaries for recipe families and meal planning sessions
- Repository interfaces for recipe parsing, ingredient normalization
- Command/query separation for recipe authority vs. meal planning operations
- Cross-domain event handling for inventory-driven meal suggestions
