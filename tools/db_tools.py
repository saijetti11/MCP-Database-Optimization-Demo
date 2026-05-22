# tools/db_tools.py

import time
import json
from datetime import datetime

from mcp.server.fastmcp import Context

from database import SessionLocal
from models import Employee
from server import mcp


# =========================================================
# BAD VERSION — new DB session per request
# =========================================================

@mcp.tool()
def bad_total_employees() -> str:
    """
    BAD:
    Creates NEW DB session every request.
    """

    start_time = datetime.now()

    # simulate connection overhead
    # time.sleep(2)

    db = SessionLocal()

    try:
        count = db.query(Employee).count()

        total_ms = (
            datetime.now() - start_time
        ).total_seconds() * 1000

        return json.dumps({
            "version": "❌ BAD VERSION",
            "total_employees": count,
            "execution_time_ms": f"{total_ms:.2f} ms",
            "message": "Creates NEW DB session every request"
        }, indent=2)

    finally:
        db.close()



# =========================================================
# OPTIMIZED VERSION — reuses shared session from lifespan
# =========================================================

@mcp.tool()
def optimized_total_employees(ctx: Context) -> str:
    """
    OPTIMIZED:
    Reuses SAME DB session from lifespan context.
    No connection overhead.
    """

    start_time = datetime.now()

    try:
        app_context = ctx.request_context.lifespan_context

        db = app_context["db"]

        count = db.query(Employee).count()

        total_ms = (
            datetime.now() - start_time
        ).total_seconds() * 1000

        return json.dumps({
            "version": "✅ OPTIMIZED VERSION",
            "shared_session_created_at": app_context["created_at"],
            "total_employees": count,
            "execution_time_ms": f"{total_ms:.2f} ms",
            "message": "Reusing SAME shared DB session"
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def optimized_get_employee(employee_id: int, ctx: Context) -> str:
    """
    OPTIMIZED:
    Reuses SAME DB session from lifespan context.
    No connection overhead.
    """

    start_time = datetime.now()

    try:
        app_context = ctx.request_context.lifespan_context

        db = app_context["db"]

        employee = (
            db.query(Employee)
            .filter(Employee.id == employee_id)
            .first()
        )

        total_ms = (
            datetime.now() - start_time
        ).total_seconds() * 1000

        if not employee:
            return json.dumps({"employee": None})

        return json.dumps({
            "version": "✅ OPTIMIZED VERSION",
            "shared_session_created_at": app_context["created_at"],
            "employee": {
                "id": employee.id,
                "name": employee.name,
                "department": employee.department
            },
            "execution_time_ms": f"{total_ms:.2f} ms",
            "message": "Reusing SAME shared DB session"
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)
    



@mcp.tool()
def bad_get_employee(employee_id: int) -> str:
    """
    BAD:
    Creates NEW DB session every request.
    Simulates connection overhead with a 2-second sleep.
    """

    start_time = datetime.now()


    db = SessionLocal()

    try:
        employee = (
            db.query(Employee)
            .filter(Employee.id == employee_id)
            .first()
        )

        total_ms = (
            datetime.now() - start_time
        ).total_seconds() * 1000

        if not employee:
            return json.dumps({"employee": None})

        return json.dumps({
            "version": "❌ BAD VERSION",
            "employee": {
                "id": employee.id,
                "name": employee.name,
                "department": employee.department
            },
            "execution_time_ms": f"{total_ms:.2f} ms",
            "message": "Creates NEW DB session every request"
        }, indent=2)

    finally:
        db.close()
