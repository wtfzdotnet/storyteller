"""Tests for dependency-based issue ordering functionality."""

import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager
from models import Epic, UserStory


class TestDependencyOrdering(unittest.TestCase):
    """Test dependency-based issue ordering functionality."""

    def setUp(self):
        """Set up test database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_manager = DatabaseManager(self.temp_db.name)

    def tearDown(self):
        """Clean up test database."""
        Path(self.temp_db.name).unlink(missing_ok=True)

    def test_topological_sort_linear_dependencies(self):
        """Test topological sorting with linear dependency chain."""
        # Create stories: A -> B -> C (A depends on B, B depends on C)
        story_c = Epic(title="Story C - Foundation")
        story_b = Epic(title="Story B - Middle")
        story_a = Epic(title="Story A - Top")

        self.db_manager.save_story(story_c)
        self.db_manager.save_story(story_b)
        self.db_manager.save_story(story_a)

        # Add dependencies: A depends on B, B depends on C
        db = self.db_manager
        db.add_story_relationship(story_a.id, story_b.id, "depends_on")
        db.add_story_relationship(story_b.id, story_c.id, "depends_on")

        # Get topological order
        ordered_stories = self.db_manager.get_stories_topological_order(
            [story_a.id, story_b.id, story_c.id]
        )

        # Should be ordered C, B, A (dependencies first)
        self.assertEqual(len(ordered_stories), 3)
        self.assertEqual(ordered_stories[0], story_c.id)
        self.assertEqual(ordered_stories[1], story_b.id)
        self.assertEqual(ordered_stories[2], story_a.id)

    def test_topological_sort_parallel_dependencies(self):
        """Test topological sorting with parallel dependencies."""
        # Create stories: A depends on both B and C
        story_a = Epic(title="Story A - Main")
        story_b = Epic(title="Story B - Backend")
        story_c = Epic(title="Story C - Frontend")

        self.db_manager.save_story(story_a)
        self.db_manager.save_story(story_b)
        self.db_manager.save_story(story_c)

        # Add dependencies: A depends on both B and C
        db = self.db_manager
        db.add_story_relationship(story_a.id, story_b.id, "depends_on")
        db.add_story_relationship(story_a.id, story_c.id, "depends_on")

        # Get topological order
        ordered_stories = self.db_manager.get_stories_topological_order(
            [story_a.id, story_b.id, story_c.id]
        )

        # Should have B and C before A
        self.assertEqual(len(ordered_stories), 3)
        self.assertEqual(ordered_stories[2], story_a.id)  # A should be last
        # B should be in first two
        self.assertIn(story_b.id, ordered_stories[:2])
        # C should be in first two
        self.assertIn(story_c.id, ordered_stories[:2])

    def test_dependency_priority_calculation(self):
        """Test priority calculation based on dependency depth."""
        # Create complex dependency chain
        story_d = Epic(title="Story D - Base")
        story_c = Epic(title="Story C - Level 2")
        story_b = Epic(title="Story B - Level 3")
        story_a = Epic(title="Story A - Top")

        self.db_manager.save_story(story_d)
        self.db_manager.save_story(story_c)
        self.db_manager.save_story(story_b)
        self.db_manager.save_story(story_a)

        # Create chain: A -> B -> C -> D
        db = self.db_manager
        db.add_story_relationship(story_a.id, story_b.id, "depends_on")
        db.add_story_relationship(story_b.id, story_c.id, "depends_on")
        db.add_story_relationship(story_c.id, story_d.id, "depends_on")

        # Calculate priorities
        priorities = self.db_manager.calculate_dependency_priorities(
            [story_a.id, story_b.id, story_c.id, story_d.id]
        )

        # Base story should have highest priority
        # (lowest number = highest priority)
        self.assertEqual(priorities[story_d.id], 1)  # Base level
        self.assertEqual(priorities[story_c.id], 2)  # Level 2
        self.assertEqual(priorities[story_b.id], 3)  # Level 3
        self.assertEqual(priorities[story_a.id], 4)  # Top level

    def test_dependency_cycle_resolution(self):
        """Test that cycle detection prevents invalid ordering."""
        # Create stories
        story_a = Epic(title="Story A")
        story_b = Epic(title="Story B")
        story_c = Epic(title="Story C")

        self.db_manager.save_story(story_a)
        self.db_manager.save_story(story_b)
        self.db_manager.save_story(story_c)

        # Create valid dependency chain: A -> B -> C
        db = self.db_manager
        db.add_story_relationship(story_a.id, story_b.id, "depends_on")
        db.add_story_relationship(story_b.id, story_c.id, "depends_on")

        # Try to create cycle: C -> A (should be prevented)
        with self.assertRaises(ValueError):
            db.add_story_relationship(story_c.id, story_a.id, "depends_on")

    def test_get_ordered_stories_for_epic(self):
        """Test getting ordered stories within an epic."""
        # Create epic with user stories
        epic = Epic(title="Test Epic")
        us1 = UserStory(title="User Story 1", epic_id=epic.id)
        us2 = UserStory(title="User Story 2", epic_id=epic.id)
        us3 = UserStory(title="User Story 3", epic_id=epic.id)

        self.db_manager.save_story(epic)
        self.db_manager.save_story(us1)
        self.db_manager.save_story(us2)
        self.db_manager.save_story(us3)

        # Add dependencies: US1 -> US2 -> US3
        db = self.db_manager
        db.add_story_relationship(us1.id, us2.id, "depends_on")
        db.add_story_relationship(us2.id, us3.id, "depends_on")

        # Get ordered stories for epic
        ordered_stories = db.get_ordered_stories_for_parent(epic.id)

        # Should be ordered US3, US2, US1
        self.assertEqual(len(ordered_stories), 3)
        self.assertEqual(ordered_stories[0]["id"], us3.id)
        self.assertEqual(ordered_stories[1]["id"], us2.id)
        self.assertEqual(ordered_stories[2]["id"], us1.id)

    def test_dependency_depth_analysis(self):
        """Test analysis of dependency depth for complex hierarchies."""
        # Create stories with varying dependency depths
        base_story = Epic(title="Base Story")
        mid_story = Epic(title="Mid Story")
        top_story = Epic(title="Top Story")
        independent_story = Epic(title="Independent Story")

        self.db_manager.save_story(base_story)
        self.db_manager.save_story(mid_story)
        self.db_manager.save_story(top_story)
        self.db_manager.save_story(independent_story)

        # Create dependencies
        db = self.db_manager
        db.add_story_relationship(top_story.id, mid_story.id, "depends_on")
        db.add_story_relationship(mid_story.id, base_story.id, "depends_on")

        # Analyze dependency depths
        depths = self.db_manager.analyze_dependency_depths(
            [base_story.id, mid_story.id, top_story.id, independent_story.id]
        )

        self.assertEqual(depths[base_story.id], 0)  # No dependencies
        self.assertEqual(depths[mid_story.id], 1)  # Depends on base
        self.assertEqual(
            depths[top_story.id], 2
        )  # Depends on mid, which depends on base
        self.assertEqual(depths[independent_story.id], 0)  # No dependencies

    def test_dependency_visualization(self):
        """Test visual dependency representation."""
        # Create stories with dependencies
        story_a = Epic(title="Frontend Feature")
        story_b = Epic(title="Backend API")
        story_c = Epic(title="Database Schema")

        self.db_manager.save_story(story_a)
        self.db_manager.save_story(story_b)
        self.db_manager.save_story(story_c)

        # Create dependency chain: Frontend -> Backend -> Database
        db = self.db_manager
        db.add_story_relationship(story_a.id, story_b.id, "depends_on")
        db.add_story_relationship(story_b.id, story_c.id, "depends_on")

        # Generate visualization
        visualization = db.generate_dependency_visualization(
            [story_a.id, story_b.id, story_c.id]
        )

        # Check that visualization contains expected elements
        self.assertIn("Dependency Visualization", visualization)
        self.assertIn("Execution Order", visualization)
        self.assertIn("Database Schema", visualization)
        self.assertIn("Backend API", visualization)
        self.assertIn("Frontend Feature", visualization)
        self.assertIn("depends on", visualization)


if __name__ == "__main__":
    unittest.main()
