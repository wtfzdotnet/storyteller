"""Test fixtures and sample data for Storyteller tests."""

# Sample data for testing various components

SAMPLE_REPOSITORIES = {
    "storyteller": {
        "name": "wtfzdotnet/storyteller",
        "type": "backend",
        "description": "Main storyteller application",
        "dependencies": [],
        "story_labels": ["storyteller", "core"],
    },
    "backend": {
        "name": "wtfzdotnet/backend-repo",
        "type": "backend",
        "description": "API services and business logic",
        "dependencies": [],
        "story_labels": ["backend", "api"],
    },
    "frontend": {
        "name": "wtfzdotnet/frontend-repo",
        "type": "frontend",
        "description": "User interface and client applications",
        "dependencies": ["backend"],
        "story_labels": ["frontend", "ui"],
    },
}

SAMPLE_STORY_DATA = {
    "epic": {
        "title": "User Authentication System",
        "description": "Comprehensive user authentication and authorization",
        "business_value": "Secure access control for all users",
        "target_repositories": ["backend", "frontend"],
        "estimated_story_points": 21,
    },
    "user_story": {
        "title": "User can log in with email and password",
        "description": "As a user, I want to log in with my email and password so that I can access my account",
        "user_persona": "Registered User",
        "user_goal": "Access personal account",
        "acceptance_criteria": [
            "User can enter email and password",
            "System validates credentials",
            "User is redirected to dashboard on success",
            "Error message shown for invalid credentials",
        ],
        "target_repositories": ["backend", "frontend"],
        "story_points": 8,
    },
    "sub_story": {
        "title": "Implement login API endpoint",
        "description": "Create REST API endpoint for user authentication",
        "department": "backend",
        "technical_requirements": [
            "POST /api/auth/login endpoint",
            "Password validation and hashing",
            "JWT token generation",
            "Rate limiting for security",
        ],
        "target_repository": "backend",
        "estimated_hours": 12.0,
    },
}

SAMPLE_FILES = {
    "frontend": [
        "package.json",
        "src/App.js",
        "src/components/Login.js",
        "public/index.html",
        "src/styles/main.css",
    ],
    "backend": [
        "requirements.txt",
        "app.py",
        "src/models/user.py",
        "src/auth/login.py",
        "tests/test_auth.py",
    ],
    "mobile": [
        "package.json",
        "android/app/build.gradle",
        "ios/Podfile",
        "src/screens/LoginScreen.js",
    ],
}
