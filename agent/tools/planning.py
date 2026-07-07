"""agent/tools/planning.py — Planning tool that lets the agent decompose objectives.

The agent maintains a plan as a list of tasks. Each task has a status
(pending, in_progress, done, blocked, skipped). The planning tool lets the
agent create, update, and query the plan during an engagement.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from .registry import Tool, ToolResult


@dataclass
class Task:
    """One task in the plan."""
    id: str
    description: str
    status: str = "pending"  # pending | in_progress | done | blocked | skipped
    depends_on: list[str] = field(default_factory=list)
    notes: str = ""
    tool_results: list[str] = field(default_factory=list)


class PlanManager:
    """Holds the current plan. Lives in working memory."""

    def __init__(self):
        self.tasks: list[Task] = []
        self._counter = 0

    def add_task(self, description: str, depends_on: list[str] | None = None) -> Task:
        self._counter += 1
        task = Task(
            id=f"task-{self._counter:03d}",
            description=description,
            depends_on=depends_on or [],
        )
        self.tasks.append(task)
        return task

    def update_task(self, task_id: str, status: str = "", notes: str = "") -> Task | None:
        for t in self.tasks:
            if t.id == task_id:
                if status:
                    t.status = status
                if notes:
                    t.notes = (t.notes + "\n" + notes).strip() if t.notes else notes
                return t
        return None

    def get_next_task(self) -> Task | None:
        """Return the next pending task whose dependencies are done."""
        done_ids = {t.id for t in self.tasks if t.status == "done"}
        for t in self.tasks:
            if t.status == "pending":
                if all(dep in done_ids for dep in t.depends_on):
                    return t
        return None

    def summary(self) -> str:
        if not self.tasks:
            return "(no plan yet)"
        lines = []
        for t in self.tasks:
            status_icon = {
                "pending": "[ ]", "in_progress": "[~]", "done": "[x]",
                "blocked": "[!]", "skipped": "[-]",
            }.get(t.status, "[?]")
            deps = f" (after {','.join(t.depends_on)})" if t.depends_on else ""
            lines.append(f"  {status_icon} {t.id}: {t.description}{deps}")
        return "\n".join(lines)


def _make_planning_tools(plan_manager: PlanManager) -> list[Tool]:
    """Build planning tools bound to a PlanManager instance."""

    def _create_plan(tasks: list[dict]) -> ToolResult:
        """Replace the entire plan with a new list of tasks."""
        plan_manager.tasks.clear()
        plan_manager._counter = 0
        # Map old ids to new ids so dependencies resolve
        id_map: dict[str, str] = {}
        for t in tasks:
            new_task = plan_manager.add_task(t["description"])
            id_map[t.get("id", new_task.id)] = new_task.id
        # Now wire dependencies (use original ids mapped to new)
        for orig, new in id_map.items():
            pass  # we'll handle deps in second pass on plan_manager.tasks
        # Second pass: set dependencies
        for orig_task, t in zip(tasks, plan_manager.tasks):
            deps = orig_task.get("depends_on", []) or []
            t.depends_on = [id_map.get(d, d) for d in deps]
        return ToolResult(
            success=True,
            output=f"Created plan with {len(plan_manager.tasks)} tasks:\n{plan_manager.summary()}",
        )

    create_plan_tool = Tool(
        name="plan_create",
        description=(
            "Create or replace the engagement plan. Pass an array of tasks; each task has "
            "'description' (string) and optional 'depends_on' (array of task ids that must "
            "complete first). Replaces any existing plan."
        ),
        parameters={
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Optional task id"},
                            "description": {"type": "string", "description": "What to do"},
                            "depends_on": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["description"],
                    },
                },
            },
            "required": ["tasks"],
        },
        handler=_create_plan,
    )

    def _update_task(task_id: str, status: str = "", notes: str = "") -> ToolResult:
        valid = {"pending", "in_progress", "done", "blocked", "skipped"}
        if status and status not in valid:
            return ToolResult(success=False, output=f"Invalid status '{status}'. Must be one of: {valid}", error="bad_status")
        t = plan_manager.update_task(task_id, status=status, notes=notes)
        if not t:
            return ToolResult(success=False, output=f"Task not found: {task_id}", error="not_found")
        return ToolResult(success=True, output=f"Updated {task_id} -> {t.status}\n{plan_manager.summary()}")

    update_task_tool = Tool(
        name="plan_update_task",
        description="Update a task's status or add notes. Statuses: pending, in_progress, done, blocked, skipped.",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task id (e.g., task-001)"},
                "status": {"type": "string", "description": "New status", "default": ""},
                "notes": {"type": "string", "description": "Notes to append", "default": ""},
            },
            "required": ["task_id"],
        },
        handler=_update_task,
    )

    def _view_plan() -> ToolResult:
        return ToolResult(success=True, output=f"Current plan:\n{plan_manager.summary()}")

    view_plan_tool = Tool(
        name="plan_view",
        description="View the current engagement plan with all tasks and their statuses.",
        parameters={"type": "object", "properties": {}},
        handler=_view_plan,
    )

    return [create_plan_tool, update_task_tool, view_plan_tool]
