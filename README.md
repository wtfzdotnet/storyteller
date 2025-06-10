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

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- GitHub account with API access
- Virtual environment setup

### Quick Setup

```bash
# Clone and setup
git clone https://github.com/wtfzdotnet/storyteller.git
cd storyteller

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your GitHub token and repository settings
```

### Configuration

Configure multi-repository setup in `.storyteller/config.json`:

```json
{
  "repositories": {
    "storyteller": {
      "name": "wtfzdotnet/storyteller",
      "type": "storyteller",
      "description": "Storyteller is a tool for managing and automating software development workflows",
      "dependencies": [],
      "story_labels": ["user_story"]
    },
    "backend": {
      "name": "wtfzdotnet/recipeer",
      "type": "backend",
      "description": "Backend microservices that provide api's and services",
      "dependencies": [],
      "story_labels": ["backend", "api"],
      "auto_assign": {
        "assignee": ["wtfzdotnet"]
      }
    },
    "frontend": {
      "name": "wtfzdotnet/recipes-frontend", 
      "type": "frontend",
      "description": "User interface and client applications",
      "dependencies": ["backend"],
      "story_labels": ["frontend", "ui"],
      "auto_assign": {
        "assignee": ["wtfzdotnet"]
      }
    }
  },
  "default_repository": "backend",
  "story_workflow": {
    "create_subtickets": true,
    "respect_dependencies": true
  }
}

```

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
