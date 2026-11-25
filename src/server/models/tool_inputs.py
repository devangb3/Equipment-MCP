"""Parameter descriptions published in the MCP tools' input schemas."""

from typing import Annotated

from pydantic import Field

from .requests import Intent

EmployeeID = Annotated[
    str, Field(description="Employee ID supplied with the request, such as M1.")
]
EmployeeRole = Annotated[
    str,
    Field(description="Current role returned by get_employee_info, such as Manager."),
]
EquipmentItem = Annotated[
    str,
    Field(description="One type of equipment requested, such as laptop or monitor."),
]
RequestText = Annotated[
    str, Field(description="The employee's original request text, in their own words.")
]
ReviewReason = Annotated[
    str,
    Field(
        description="The specific fact or policy exception requiring human review, such as a missing laptop issue date."
    ),
]
RequestIntent = Annotated[
    Intent,
    Field(
        description=(
            "Use routine for a first issue or standard refresh, additional for an extra device, "
            "broken for replacement of faulty equipment, and unclear when the wording is ambiguous."
        )
    ),
]
