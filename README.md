# Recipe Authority Platform - AI-Powered Story Management

> **"The Authority of Recipes on the Internet"** - Enterprise-grade AI story management system for building the world's most comprehensive, culturally-respectful, and intelligent recipe platform.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![CI/CD Pipeline](https://github.com/wtfzdotnet/storyteller/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/wtfzdotnet/storyteller/actions)

## 🎯 Mission Statement

**Transform the chaotic landscape of web recipes into authoritative, cultural-aware, nutritionally-accurate knowledge that reduces food waste and enhances cooking experiences worldwide.**

This isn't just another development tool—it's the strategic foundation for building **the definitive global food knowledge platform** that establishes authority, preserves heritage, reduces waste, bridges cultures, and enhances health through intelligent AI-powered story management.

## 🚀 Strategic Product Vision

### 5-Phase Evolution Roadmap

**Phase 1: Recipe Authority Foundation** (Months 1-6)  
Establish platform as definitive source for standardized, culturally-authentic recipes with SEO-optimized content authority and community-driven authenticity verification.

**Phase 2: Intelligent Meal Ecosystem** (Months 6-12)  
Create comprehensive meal planning with cultural awareness, AI-powered personalization, and social validation features.

**Phase 3: Smart Inventory Integration** (Months 12-18)  
Real-time inventory management with waste reduction focus, automated tracking, and smart meal optimization.

**Phase 4: Global Shopping Network** (Months 18-24)  
Monetized affiliate shopping integration with local sourcing and intelligent shopping list generation.

**Phase 5: Cultural Exchange Platform** (Months 24+)  
Premium cultural heritage preservation network with global food diplomacy and advanced personalization.

## 🧠 AI Expert Team Intelligence

### Revolutionary Multi-Expert Collaboration

Our AI story management system leverages **20+ specialized expert roles** that collaborate to ensure every feature is analyzed through professional-level domain expertise:

#### 🏗️ **Technical Leadership**
- **[System Architect](/.storyteller/roles/system-architect.md)**: DDD/Hexagonal architecture, bounded contexts, event-driven design
- **[Lead Developer](/.storyteller/roles/lead-developer.md)**: Symfony implementation, API Platform, Doctrine patterns  
- **[Security Expert](/.storyteller/roles/security-expert.md)**: Authentication, data privacy, cultural content moderation
- **[AI Expert](/.storyteller/roles/ai-expert.md)**: ML architecture, recommendation systems, automated processing

#### 📊 **Product & Strategy**
- **[Product Owner](/.storyteller/roles/product-owner.md)**: Strategic roadmap, monetization, cultural exchange features
- **[UX/UI Designer](/.storyteller/roles/ux-ui-designer.md)**: Cultural-sensitive design, accessibility leadership

#### 🍳 **Domain Expertise**
- **[Professional Chef](/.storyteller/roles/professional-chef.md)**: Culinary excellence, recipe quality, professional standards
- **[Food Historian/Anthropologist](/.storyteller/roles/food-historian-anthropologist.md)**: Cultural authenticity, heritage preservation
- **[Domain Expert - Food & Nutrition](/.storyteller/roles/domain-expert-food-nutrition.md)**: Ingredient science, nutrition accuracy

#### 🏥 **Specialized Nutrition**
- **[Registered Dietitian](/.storyteller/roles/registered-dietitian.md)**: Clinical nutrition, therapeutic diets
- **[Geriatric](/.storyteller/roles/geriatric-nutritionist.md)** | **[Pediatric](/.storyteller/roles/pediatric-nutritionist.md)** | **[Sports](/.storyteller/roles/sports-nutritionist.md)** | **[Pregnancy](/.storyteller/roles/pregnancy-lactation-nutritionist.md)** Nutritionists

#### 🌱 **Specialized Systems**
- **[Food Safety Specialist](/.storyteller/roles/food-safety-specialist.md)**: HACCP protocols, contamination prevention
- **[Sustainable Food Systems](/.storyteller/roles/sustainable-food-systems-expert.md)**: Environmental impact, waste reduction
- **[Budget Cooking Expert](/.storyteller/roles/budget-cooking-meal-prep-expert.md)**: Cost-effective strategies

### Expert Team Philosophy

- **Domain-First Approach**: Every feature analyzed through relevant domain expert lenses
- **Cultural Sensitivity**: Cultural experts ensure respectful and authentic representation
- **Professional Standards**: Industry professionals maintain quality and authenticity standards
- **Collaborative Intelligence**: Multiple expert perspectives create comprehensive solutions

## 🏗️ Technical Architecture

### Modern Technology Stack

- **Golang microservices** that expose REST api endpoints that are consumed on the frontend
- **React+Vite+Material UI+Tailwind** a very well tested combination for a powerful frontend
- **Storybook** the frontend also contains storybook, which must be meticioulsy maintained with new smaller components, cards, etc.
- **Event-driven architecture** with **CQRS** patterns for complex data flows
- **Progressive bounded contexts**: Recipe → Nutrition → User → Inventory → MealPlanning → Shopping → Cultural
- **AI-First Integration**: Machine learning embedded throughout platform architecture

## ⚡ Key Features

### 🤖 **Intelligent Story Processing**
- **Multi-Expert Analysis**: Stories analyzed by relevant domain experts before implementation
- **Cultural Authenticity**: Food historian validation for culturally-sensitive features
- **Professional Standards**: Chef and nutritionist expertise for recipe-related stories
- **Technical Excellence**: System architect and security expert guidance for all implementations

### 🏢 **Multi-Repository Management**
- **Backend/Frontend Separation**: Intelligent story distribution based on repository type
- **Dependency Management**: Automatic handling of cross-repository dependencies
- **Auto-Assignment**: Configurable automatic assignment of stories to team members
- **Label Automation**: Smart labeling based on story content and repository type

### 🔄 **Advanced Workflow Automation**
- **GitHub Actions Integration**: Automated story processing in CI/CD pipelines
- **CLI Management**: Full command-line interface for story creation and management
- **MCP Support**: Model Context Protocol integration for AI assistant usage
- **Real-time Processing**: Async/await patterns for scalable story processing

### 🌍 **Cultural Intelligence**
- **Heritage Preservation**: Expert-guided preservation of traditional recipe knowledge
- **Authenticity Validation**: Multi-expert validation of cultural content
- **Respectful Adaptation**: Guidelines for culturally-appropriate recipe modifications
- **Global Perspective**: Expert team spans diverse cultural and culinary traditions

## 🤖 GitHub Copilot & Enhanced MCP Integration

### Overview

The Recipe Authority Platform now features deep integration with GitHub Copilot and the Model Context Protocol (MCP), enabling seamless, AI-powered story management and expert collaboration directly from your development environment or AI assistant. This integration empowers developers and teams to:
- Automate story creation, analysis, and distribution across repositories
- Leverage 20+ expert AI roles for domain-specific insights and validation
- Interact with the platform via standardized MCP endpoints for Copilot, LLMs, and custom tools
- Ensure secure, high-performance, and auditable workflows for enterprise and open-source teams

### MCP API Endpoints

The MCP server exposes a robust set of endpoints for Copilot and AI assistant workflows:

#### Story Methods
- `story/create` – Create a new story with expert analysis and GitHub issue creation
- `story/analyze` – Analyze a story with multi-expert input (no GitHub issue)
- `story/status` – Retrieve processing status and expert consensus for a story

#### Role Methods
- `role/query` – Query a specific expert role with a question or scenario
- `role/list` – List all available expert roles and their documentation
- `role/analyze_story` – Get a role-specific analysis for a given story

#### Repository Methods
- `repository/list` – List all configured repositories and their types
- `repository/get_config` – Retrieve configuration for a specific repository

#### System Methods
- `system/health` – Health check for MCP server
- `system/capabilities` – List all available methods and features
- `system/validate` – Validate current configuration and environment

#### File & Codebase Methods (Copilot Integration)
- `file/read` – Read the contents of a file in the codebase
- `file/write` – Write content to a file in the codebase
- `codebase/scan` – Scan the codebase for files, structure, or patterns
- `codebase/analyze` – Analyze the codebase for metrics, dependencies, or issues

#### Test & QA Methods
- `test/analyze` – Analyze test coverage and quality for the codebase or file
- `test/suggest` – Suggest new tests or improvements for the codebase or file
- `test/generate` – Generate new tests for the codebase or file
- `qa/strategy` – Suggest or analyze QA strategies for the project

#### Component & Storybook Methods
- `component/analyze` – Analyze a component for structure, usage, or best practices
- `component/generate` – Generate a new component or suggest improvements
- `storybook/scan` – Scan Storybook stories for coverage and structure
- `storybook/suggest` – Suggest new Storybook stories or improvements

#### Context, Suggestion, and Workflow Methods
- `context/provide` – Provide context for Copilot or LLM workflows
- `suggestion/improve` – Suggest improvements for code, tests, or documentation
- `workflow/automate` – Automate a workflow or process in the codebase

> These endpoints enable advanced Copilot/AI workflows for file access, codebase intelligence, test generation, component analysis, and workflow automation.

### Example Requests & Responses

#### Create Story
```json
{
  "id": "req-001",
  "method": "story/create",
  "params": {
    "content": "As a user, I want to save favorite recipes.",
    "repository": "backend",
    "roles": ["product-owner", "ux-ui-designer", "lead-developer"]
  }
}
```
_Response:_
```json
{
  "id": "req-001",
  "result": {
    "success": true,
    "message": "Story created and analyzed by experts.",
    "data": { "story_id": "story_abc123", ... }
  }
}
```

#### Analyze Story
```json
{
  "id": "req-002",
  "method": "story/analyze",
  "params": {
    "content": "Add cultural recipe validation.",
    "roles": ["food-historian-anthropologist", "professional-chef"]
  }
}
```

#### Query Expert Role
```json
{
  "id": "req-003",
  "method": "role/query",
  "params": {
    "role_name": "ai-expert",
    "question": "How can we improve recipe recommendations?"
  }
}
```

#### List Roles
```json
{
  "id": "req-004",
  "method": "role/list",
  "params": {}
}
```

#### Health Check
```json
{
  "id": "req-005",
  "method": "system/health",
  "params": {}
}
```

### Security & Performance Requirements
- **Authentication**: All endpoints require secure API tokens (see `.env.example`)
- **Role-Based Access**: Sensitive operations are restricted by role and repository configuration
- **Rate Limiting**: MCP server enforces per-user and per-IP rate limits for stability
- **Audit Logging**: All requests and expert analyses are logged for traceability
- **Performance**: Sub-second response times for most operations; async/await for scalable processing

### Expert Roles in Copilot/MCP Workflows
- **Automated Multi-Expert Analysis**: Every story is reviewed by relevant expert roles, ensuring professional, culturally-sensitive, and technically-sound outcomes
- **Role Documentation**: Each expert role is fully documented in [AI Expert Team Documentation](/.storyteller/README.md) and discoverable via `role/list`
- **Customizable Workflows**: Developers can specify which expert roles to involve per story or query
- **Consensus & Validation**: Copilot and MCP workflows leverage expert consensus for higher quality and reliability

### Further Reading & Integration
- See [USAGE.md](USAGE.md) for endpoint usage examples, configuration, and troubleshooting
- See [AI Expert Team Documentation](/.storyteller/README.md) for detailed role definitions and collaboration patterns
- Endpoint and workflow documentation is continually updated for Copilot/MCP compatibility

---

## 📊 Success Metrics

### Platform Authority Metrics
- **Content Quality**: Expert validation scores and cultural authenticity ratings
- **User Engagement**: Story completion rates and expert consensus achievement  
- **Development Velocity**: Story processing time and implementation success rates
- **Cultural Impact**: Heritage preservation contributions and community validation

### Technical Excellence Metrics
- **Code Quality**: 100% Black formatting, zero critical flake8 errors
- **Test Coverage**: Comprehensive test coverage for all story workflows
- **Performance**: Sub-second story analysis with multi-expert collaboration
- **Reliability**: Zero-downtime story processing with async/await architecture

## 📚 Documentation

- **[AI Expert Team Documentation](/.storyteller/README.md)**: Comprehensive expert role definitions and collaboration guidelines

## 🔮 Future Vision

This AI story management system serves as the foundation for building **the most authoritative, culturally-respectful, and intelligent recipe platform on the internet**. Through the collaboration of 20+ expert AI roles, we ensure every feature meets professional standards across culinary, technical, cultural, and health domains.

**Join us in transforming global food knowledge through AI-powered expert collaboration.**

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Cultural Communities**: For sharing traditional knowledge and validating authenticity
- **Domain Experts**: Professional chefs, nutritionists, and food historians who inform our AI expert roles
- **Technical Community**: Open source contributors who make intelligent story management possible
- **Global Vision**: Everyone working toward a more connected, respectful, and sustainable food future
