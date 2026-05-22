from fastapi import FastAPI
from pydantic import BaseModel

from database import SessionLocal, init_db
from models import Employee


app = FastAPI()


# create tables
init_db()


# request body
class EmployeeCreate(BaseModel):

    name: str
    department: str


# insert employee
@app.post("/employees")
def create_employee(employee: EmployeeCreate):

    db = SessionLocal()

    try:

        new_employee = Employee(
            name=employee.name,
            department=employee.department
        )

        db.add(new_employee)

        db.commit()

        db.refresh(new_employee)

        return {
            "message": "Employee created successfully",
            "employee": {
                "id": new_employee.id,
                "name": new_employee.name,
                "department": new_employee.department
            }
        }

    finally:
        db.close()