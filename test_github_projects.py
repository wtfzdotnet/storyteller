"""Test GitHub Projects API integration."""

import asyncio
import os
from unittest.mock import Mock, patch, MagicMock

# Set dummy environment for testing
os.environ["GITHUB_TOKEN"] = "test_token"
os.environ["DEFAULT_LLM_PROVIDER"] = "github"

from config import Config
from github_handler import GitHubHandler
from models import ProjectData, ProjectField, ProjectFieldValue


class TestGitHubProjectsIntegration:
    """Test GitHub Projects API integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = Config(github_token="test_token")
        self.github_handler = GitHubHandler(self.config)

    @patch("github_handler.requests.post")
    def test_execute_graphql_query(self, mock_post):
        """Test GraphQL query execution."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"test": "success"}}
        mock_post.return_value = mock_response

        query = "query { viewer { login } }"
        result = self.github_handler._execute_graphql_query(query)

        assert result == {"test": "success"}
        mock_post.assert_called_once()

        # Verify headers and payload
        call_args = mock_post.call_args
        assert call_args[1]["headers"]["Authorization"] == "Bearer test_token"
        assert call_args[1]["json"]["query"] == query

    @patch("github_handler.requests.post")
    def test_execute_graphql_query_with_variables(self, mock_post):
        """Test GraphQL query execution with variables."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"result": "ok"}}
        mock_post.return_value = mock_response

        query = "query($login: String!) { user(login: $login) { id } }"
        variables = {"login": "testuser"}

        result = self.github_handler._execute_graphql_query(query, variables)

        assert result == {"result": "ok"}

        # Verify variables were included
        call_args = mock_post.call_args
        assert call_args[1]["json"]["variables"] == variables

    @patch("github_handler.requests.post")
    def test_execute_graphql_query_error_handling(self, mock_post):
        """Test GraphQL query error handling."""
        # Test HTTP error
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        query = "invalid query"

        try:
            self.github_handler._execute_graphql_query(query)
            assert False, "Should have raised exception"
        except Exception as e:
            assert "GraphQL request failed" in str(e)

        # Test GraphQL errors
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Field 'invalid' doesn't exist"}]
        }

        try:
            self.github_handler._execute_graphql_query(query)
            assert False, "Should have raised exception"
        except Exception as e:
            assert "GraphQL errors" in str(e)

    @patch("github_handler.GitHubHandler._execute_graphql_query")
    async def test_create_repository_project(self, mock_graphql):
        """Test creating a repository-level project."""
        # Mock repository
        mock_repo = Mock()
        mock_repo.node_id = "R_test123"

        with patch.object(
            self.github_handler, "get_repository", return_value=mock_repo
        ):
            mock_graphql.return_value = {
                "createProjectV2": {
                    "projectV2": {
                        "id": "PVT_test456",
                        "title": "Test Project",
                        "url": "https://github.com/users/test/projects/1",
                        "number": 1,
                    }
                }
            }

            project_data = ProjectData(
                title="Test Project", description="Test project description"
            )

            result = await self.github_handler.create_project(project_data, "test/repo")

            assert result["id"] == "PVT_test456"
            assert result["title"] == "Test Project"
            mock_graphql.assert_called_once()

    @patch("github_handler.GitHubHandler._execute_graphql_query")
    async def test_create_organization_project(self, mock_graphql):
        """Test creating an organization-level project."""
        # Mock organization query first
        mock_graphql.side_effect = [
            {"organization": {"id": "O_test789"}},  # First call for org ID
            {
                "createProjectV2": {
                    "projectV2": {
                        "id": "PVT_test456",
                        "title": "Org Project",
                        "url": "https://github.com/orgs/testorg/projects/1",
                        "number": 1,
                    }
                }
            },  # Second call for project creation
        ]

        project_data = ProjectData(
            title="Org Project",
            description="Organization project",
            organization_login="testorg",
        )

        result = await self.github_handler.create_project(project_data)

        assert result["id"] == "PVT_test456"
        assert result["title"] == "Org Project"
        assert mock_graphql.call_count == 2

    @patch("github_handler.GitHubHandler._execute_graphql_query")
    async def test_add_issue_to_project(self, mock_graphql):
        """Test adding an issue to a project."""
        # Mock repository and issue
        mock_issue = Mock()
        mock_issue.node_id = "I_test123"
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue

        with patch.object(
            self.github_handler, "get_repository", return_value=mock_repo
        ):
            mock_graphql.return_value = {
                "addProjectV2ItemById": {
                    "item": {
                        "id": "PVTI_test456",
                        "content": {"title": "Test Issue", "number": 123},
                    }
                }
            }

            result = await self.github_handler.add_issue_to_project(
                "PVT_project123", 123, "test/repo"
            )

            assert result["id"] == "PVTI_test456"
            assert result["content"]["number"] == 123
            mock_graphql.assert_called_once()

    @patch("github_handler.GitHubHandler._execute_graphql_query")
    async def test_get_project_fields(self, mock_graphql):
        """Test retrieving project fields."""
        mock_graphql.return_value = {
            "node": {
                "fields": {
                    "nodes": [
                        {
                            "id": "PVTF_test1",
                            "name": "Status",
                            "dataType": "SINGLE_SELECT",
                            "options": [
                                {"id": "opt1", "name": "Todo"},
                                {"id": "opt2", "name": "In Progress"},
                                {"id": "opt3", "name": "Done"},
                            ],
                        },
                        {"id": "PVTF_test2", "name": "Priority", "dataType": "TEXT"},
                    ]
                }
            }
        }

        fields = await self.github_handler.get_project_fields("PVT_project123")

        assert len(fields) == 2
        assert fields[0].name == "Status"
        assert fields[0].data_type == "SINGLE_SELECT"
        assert len(fields[0].options) == 3
        assert fields[1].name == "Priority"
        assert fields[1].data_type == "TEXT"

    @patch("github_handler.GitHubHandler._execute_graphql_query")
    async def test_update_project_item_field(self, mock_graphql):
        """Test updating a project item field."""
        mock_graphql.return_value = {
            "updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_test456"}}
        }

        result = await self.github_handler.update_project_item_field(
            "PVT_project123", "PVTI_test456", "PVTF_status", {"text": "In Progress"}
        )

        assert result["id"] == "PVTI_test456"
        mock_graphql.assert_called_once()

    async def test_bulk_add_issues_to_project(self):
        """Test bulk adding issues to project."""
        with patch.object(self.github_handler, "add_issue_to_project") as mock_add:
            # Mock successful addition for first issue, failure for second
            mock_add.side_effect = [
                {"id": "PVTI_1", "content": {"number": 1}},
                Exception("Failed to add issue 2"),
            ]

            issue_data = [(1, "test/repo"), (2, "test/repo")]
            results = await self.github_handler.bulk_add_issues_to_project(
                "PVT_project123", issue_data
            )

            assert len(results) == 2
            assert results[0]["success"] is True
            assert results[0]["issue_number"] == 1
            assert results[1]["success"] is False
            assert results[1]["issue_number"] == 2

    def test_project_data_to_dict(self):
        """Test ProjectData serialization."""
        project_data = ProjectData(
            title="Test Project",
            description="Test description",
            repository_id="R_123",
            visibility="PUBLIC",
        )

        result = project_data.to_dict()

        assert result["title"] == "Test Project"
        assert result["description"] == "Test description"
        assert result["repository_id"] == "R_123"
        assert result["visibility"] == "PUBLIC"

    def test_project_field_value_creation(self):
        """Test ProjectFieldValue creation."""
        field_value = ProjectFieldValue(
            field_id="PVTF_status", value="In Progress", field_type="single_select"
        )

        assert field_value.field_id == "PVTF_status"
        assert field_value.value == "In Progress"
        assert field_value.field_type == "single_select"


def test_github_projects_integration():
    """Run all GitHub Projects integration tests."""
    test_instance = TestGitHubProjectsIntegration()

    # Run synchronous tests
    test_instance.setup_method()
    test_instance.test_execute_graphql_query()
    print("✓ GraphQL query execution test passed")

    test_instance.setup_method()
    test_instance.test_execute_graphql_query_with_variables()
    print("✓ GraphQL query with variables test passed")

    test_instance.setup_method()
    test_instance.test_execute_graphql_query_error_handling()
    print("✓ GraphQL error handling test passed")

    test_instance.setup_method()
    test_instance.test_project_data_to_dict()
    print("✓ ProjectData serialization test passed")

    test_instance.setup_method()
    test_instance.test_project_field_value_creation()
    print("✓ ProjectFieldValue creation test passed")

    # Run async tests
    async def run_async_tests():
        test_instance.setup_method()
        await test_instance.test_create_repository_project()
        print("✓ Repository project creation test passed")

        test_instance.setup_method()
        await test_instance.test_create_organization_project()
        print("✓ Organization project creation test passed")

        test_instance.setup_method()
        await test_instance.test_add_issue_to_project()
        print("✓ Add issue to project test passed")

        test_instance.setup_method()
        await test_instance.test_get_project_fields()
        print("✓ Get project fields test passed")

        test_instance.setup_method()
        await test_instance.test_update_project_item_field()
        print("✓ Update project item field test passed")

        test_instance.setup_method()
        await test_instance.test_bulk_add_issues_to_project()
        print("✓ Bulk add issues to project test passed")

    asyncio.run(run_async_tests())

    print("\n🎉 All GitHub Projects integration tests passed!")


if __name__ == "__main__":
    test_github_projects_integration()
