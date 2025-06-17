"""Test database migration from scratch."""

import os
import sys
from pathlib import Path
import subprocess

# Add project root to path  
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_migration_from_scratch():
    """Test that migrations can be run from scratch."""
    print("Testing migration from scratch...")
    
    # Remove existing database if it exists
    db_path = project_root / "storyteller_test.db"
    if db_path.exists():
        db_path.unlink()
        print("✓ Removed existing test database")
    
    # Set test database URL
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    
    try:
        # Run migration
        result = subprocess.run([
            "alembic", "upgrade", "head"
        ], capture_output=True, text=True, cwd=project_root)
        
        if result.returncode != 0:
            print(f"❌ Migration failed: {result.stderr}")
            return False
            
        print("✓ Migration completed successfully")
        
        # Verify database was created
        if not db_path.exists():
            print("❌ Database file was not created")
            return False
            
        print("✓ Database file created")
        
        # Test that we can connect and use the database
        from database.base import get_db_session
        from database.repository import StoryRepository
        
        db_gen = get_db_session()
        db = next(db_gen)
        repo = StoryRepository(db)
        
        # Test basic operations
        epic = repo.create_epic(
            title="Test Epic",
            description="Test epic for migration validation",
            story_id="test_epic_001"
        )
        
        print(f"✓ Created test epic with ID: {epic.id}")
        
        # Cleanup
        db.close()
        db_path.unlink()
        print("✓ Cleaned up test database")
        
        print("✅ Migration test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Migration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Reset environment
        if "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]


if __name__ == "__main__":
    success = test_migration_from_scratch()
    if not success:
        sys.exit(1)