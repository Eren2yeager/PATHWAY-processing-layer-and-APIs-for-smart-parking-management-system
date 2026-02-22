"""
Test if Pathway works in Docker container
"""
import sys

print("=" * 60)
print("Testing Pathway Installation in Docker")
print("=" * 60)

# Test 1: Import Pathway
print("\n1. Importing Pathway...")
try:
    import pathway as pw
    print("   ✅ Pathway imported successfully!")
    print(f"   Version: {pw.__version__}")
except Exception as e:
    print(f"   ❌ Failed to import Pathway: {e}")
    sys.exit(1)

# Test 2: Create a simple table
print("\n2. Creating Pathway Table...")
try:
    class InputSchema(pw.Schema):
        value: int
    
    # Create empty table
    table = pw.debug.table_from_markdown("""
    value
    1
    2
    3
    """)
    
    print("   ✅ Pathway table created successfully!")
except Exception as e:
    print(f"   ❌ Failed to create table: {e}")
    sys.exit(1)

# Test 3: Simple transformation
print("\n3. Testing Pathway Transformation...")
try:
    result = table.select(doubled=pw.this.value * 2)
    print("   ✅ Pathway transformation works!")
except Exception as e:
    print(f"   ❌ Transformation failed: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("🎉 All Pathway tests passed!")
print("=" * 60)
