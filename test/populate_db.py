"""
Populate database with sample employee data
"""
from database import SessionLocal, init_db
from models import Employee

print("Initializing database...")
init_db()

db = SessionLocal()

# Clear existing data
db.query(Employee).delete()
db.commit()

# Create sample employees
employees_data = [
    {"id": 1, "name": "John Doe", "department": "Engineering"},
    {"id": 2, "name": "Jane Smith", "department": "Marketing"},
    {"id": 3, "name": "Bob Johnson", "department": "Sales"},
    {"id": 4, "name": "Alice Brown", "department": "Engineering"},
    {"id": 5, "name": "Charlie Wilson", "department": "HR"},
]

print(f"\nCreating {len(employees_data)} sample employees...\n")

for data in employees_data:
    emp = Employee(
        id=data["id"],
        name=data["name"],
        department=data["department"]
    )
    db.add(emp)
    print(f"✅ Added: ID {emp.id} - {emp.name} ({emp.department})")

db.commit()

# Verify
total = db.query(Employee).count()
print(f"\n✅ Database populated successfully!")
print(f"📊 Total employees: {total}\n")

db.close()
