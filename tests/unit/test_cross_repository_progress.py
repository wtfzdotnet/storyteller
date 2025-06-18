"""Tests for cross-repository progress tracking functionality."""

import unittest
from datetime import datetime, timezone

from models import (
    CrossRepositoryProgressSnapshot,
    Epic,
    StoryHierarchy,
    StoryStatus,
    SubStory,
    UserStory,
)


class TestCrossRepositoryProgress(unittest.TestCase):
    """Test cross-repository progress tracking functionality."""

    def setUp(self):
        """Set up test data."""
        self.epic = Epic(
            title="Test Epic",
            description="Test epic for cross-repo progress",
            target_repositories=["backend", "frontend"],
        )

        # User story targeting both repos
        self.user_story1 = UserStory(
            epic_id=self.epic.id,
            title="User Story 1",
            target_repositories=["backend", "frontend"],
            status=StoryStatus.DONE,
        )

        # User story targeting only backend
        self.user_story2 = UserStory(
            epic_id=self.epic.id,
            title="User Story 2",
            target_repositories=["backend"],
            status=StoryStatus.IN_PROGRESS,
        )

        # Sub-stories for different repositories
        self.sub_story1 = SubStory(
            user_story_id=self.user_story1.id,
            title="Backend Sub-story",
            target_repository="backend",
            department="backend",
            status=StoryStatus.DONE,
            estimated_hours=8.0,
        )

        self.sub_story2 = SubStory(
            user_story_id=self.user_story1.id,
            title="Frontend Sub-story",
            target_repository="frontend",
            department="frontend",
            status=StoryStatus.IN_PROGRESS,
            estimated_hours=6.0,
        )

        self.sub_story3 = SubStory(
            user_story_id=self.user_story2.id,
            title="Backend API Sub-story",
            target_repository="backend",
            department="backend",
            status=StoryStatus.DRAFT,
            estimated_hours=4.0,
        )

        self.hierarchy = StoryHierarchy(
            epic=self.epic,
            user_stories=[self.user_story1, self.user_story2],
            sub_stories={
                self.user_story1.id: [self.sub_story1, self.sub_story2],
                self.user_story2.id: [self.sub_story3],
            },
        )

    def test_get_cross_repository_progress(self):
        """Test cross-repository progress aggregation."""
        progress = self.hierarchy.get_cross_repository_progress()

        # Check overall progress structure
        self.assertIn("overall", progress)
        self.assertIn("by_repository", progress)

        overall = progress["overall"]
        self.assertEqual(overall["repositories_involved"], 2)

        # Expected calculation:
        # User story 1 (DONE) targets both backend and frontend (counted in both repos)
        # User story 2 (IN_PROGRESS) targets backend only
        # Sub-story 1 (DONE) targets backend
        # Sub-story 2 (IN_PROGRESS) targets frontend
        # Sub-story 3 (DRAFT) targets backend
        # Total: 6 items (user story counted twice + 3 sub-stories)
        # Completed: 3 items (user story counted twice for being done + 1 sub-story done)
        self.assertEqual(overall["total"], 6)
        self.assertEqual(
            overall["completed"], 3
        )  # user story 1 counted twice + sub-story 1
        self.assertEqual(overall["percentage"], 50.0)

        # Check per-repository progress
        by_repo = progress["by_repository"]
        self.assertIn("backend", by_repo)
        self.assertIn("frontend", by_repo)

        # Backend: 2 user stories + 2 sub-stories = 4 total, 1 user story + 1 sub-story = 2 completed
        backend_progress = by_repo["backend"]
        self.assertEqual(backend_progress["total"], 4)
        self.assertEqual(backend_progress["completed"], 2)
        self.assertEqual(backend_progress["percentage"], 50.0)
        self.assertEqual(backend_progress["status"], "in_progress")

        # Frontend: 1 user story + 1 sub-story = 2 total, 1 user story + 0 sub-stories = 1 completed
        frontend_progress = by_repo["frontend"]
        self.assertEqual(frontend_progress["total"], 2)
        self.assertEqual(frontend_progress["completed"], 1)
        self.assertEqual(frontend_progress["percentage"], 50.0)
        self.assertEqual(frontend_progress["status"], "in_progress")

    def test_get_repository_specific_metrics(self):
        """Test repository-specific progress metrics."""
        metrics = self.hierarchy.get_repository_specific_metrics()

        self.assertIn("backend", metrics)
        self.assertIn("frontend", metrics)

        # Test backend metrics
        backend_metrics = metrics["backend"]
        self.assertEqual(backend_metrics["user_stories"]["total"], 2)
        self.assertEqual(backend_metrics["user_stories"]["completed"], 1)
        self.assertEqual(backend_metrics["sub_stories"]["total"], 2)
        self.assertEqual(backend_metrics["sub_stories"]["completed"], 1)
        self.assertEqual(backend_metrics["estimated_hours"], 12.0)  # 8.0 + 4.0

        # Check department breakdown
        dept_breakdown = backend_metrics["department_breakdown"]
        self.assertIn("backend", dept_breakdown)
        self.assertEqual(dept_breakdown["backend"]["total"], 2)
        self.assertEqual(dept_breakdown["backend"]["completed"], 1)

        # Test frontend metrics
        frontend_metrics = metrics["frontend"]
        self.assertEqual(frontend_metrics["user_stories"]["total"], 1)
        self.assertEqual(frontend_metrics["user_stories"]["completed"], 1)
        self.assertEqual(frontend_metrics["sub_stories"]["total"], 1)
        self.assertEqual(frontend_metrics["sub_stories"]["completed"], 0)
        self.assertEqual(frontend_metrics["estimated_hours"], 6.0)

    def test_repository_status_calculation(self):
        """Test repository status calculation logic."""
        # Test completed status
        completed_status = self.hierarchy._get_repository_status(5, 5)
        self.assertEqual(completed_status, "completed")

        # Test in_progress status
        in_progress_status = self.hierarchy._get_repository_status(3, 5)
        self.assertEqual(in_progress_status, "in_progress")

        # Test not_started status
        not_started_status = self.hierarchy._get_repository_status(0, 5)
        self.assertEqual(not_started_status, "not_started")

        # Test empty repository
        empty_status = self.hierarchy._get_repository_status(0, 0)
        self.assertEqual(empty_status, "not_started")

    def test_status_distribution_calculation(self):
        """Test status distribution calculation."""
        stories = [
            self.user_story1,
            self.user_story2,
            self.sub_story1,
            self.sub_story2,
            self.sub_story3,
        ]
        distribution = self.hierarchy._calculate_status_distribution(stories)

        expected = {
            "done": 2,  # user_story1, sub_story1
            "in_progress": 2,  # user_story2, sub_story2
            "draft": 1,  # sub_story3
        }

        self.assertEqual(distribution, expected)


class TestCrossRepositoryProgressSnapshot(unittest.TestCase):
    """Test CrossRepositoryProgressSnapshot functionality."""

    def setUp(self):
        """Set up test data."""
        self.epic = Epic(title="Test Epic", target_repositories=["backend"])

        self.user_story = UserStory(
            epic_id=self.epic.id,
            title="Test User Story",
            target_repositories=["backend"],
            status=StoryStatus.DONE,
        )

        self.hierarchy = StoryHierarchy(
            epic=self.epic, user_stories=[self.user_story], sub_stories={}
        )

    def test_snapshot_creation_from_hierarchy(self):
        """Test creating a progress snapshot from a story hierarchy."""
        snapshot = CrossRepositoryProgressSnapshot.from_story_hierarchy(self.hierarchy)

        self.assertEqual(snapshot.epic_id, self.epic.id)
        self.assertEqual(snapshot.epic_title, self.epic.title)
        self.assertIsNotNone(snapshot.timestamp)
        self.assertIn("total", snapshot.overall_progress)
        self.assertIn("backend", snapshot.repository_progress)

    def test_snapshot_to_dict(self):
        """Test converting snapshot to dictionary."""
        snapshot = CrossRepositoryProgressSnapshot.from_story_hierarchy(self.hierarchy)
        snapshot_dict = snapshot.to_dict()

        required_keys = [
            "epic_id",
            "epic_title",
            "timestamp",
            "overall_progress",
            "repository_progress",
            "repository_metrics",
            "real_time_updates_enabled",
        ]

        for key in required_keys:
            self.assertIn(key, snapshot_dict)

    def test_visualization_data_format(self):
        """Test visualization data formatting."""
        snapshot = CrossRepositoryProgressSnapshot.from_story_hierarchy(self.hierarchy)
        viz_data = snapshot.get_visualization_data()

        # Check structure
        self.assertIn("epic", viz_data)
        self.assertIn("repositories", viz_data)
        self.assertIn("summary", viz_data)
        self.assertIn("timestamp", viz_data)

        # Check epic data
        epic_data = viz_data["epic"]
        self.assertEqual(epic_data["id"], self.epic.id)
        self.assertEqual(epic_data["title"], self.epic.title)

        # Check repositories list
        repositories = viz_data["repositories"]
        self.assertIsInstance(repositories, list)
        self.assertEqual(len(repositories), 1)

        # Check repository data structure
        repo_data = repositories[0]
        required_repo_keys = [
            "name",
            "progress",
            "status",
            "total_items",
            "completed_items",
        ]
        for key in required_repo_keys:
            self.assertIn(key, repo_data)


if __name__ == "__main__":
    unittest.main()
