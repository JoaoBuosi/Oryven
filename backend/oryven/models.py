from typing import Any, Literal, Union
from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CommandRequest(Strict):
    text: str = Field(min_length=1, max_length=500)


class DecisionRequest(Strict):
    decision: Literal["approve", "deny"]


class SearchIntent(Strict):
    kind: Literal["browser.search"] = "browser.search"
    query: str = Field(min_length=1, max_length=180)


class AppLaunchIntent(Strict):
    kind: Literal["app.launch"] = "app.launch"
    app_id: Literal["notepad", "calculator", "explorer"]


class WindowListIntent(Strict):
    kind: Literal["computer.windows.list"] = "computer.windows.list"


class WindowTreeIntent(Strict):
    kind: Literal["computer.window.inspect"] = "computer.window.inspect"
    handle: int = Field(gt=0, le=18446744073709551615)


class BrowserInspectIntent(Strict):
    kind: Literal["browser.inspect"] = "browser.inspect"
    url: str = Field(min_length=14, max_length=400)


class BunoChatIntent(Strict):
    kind: Literal["buno.chat"] = "buno.chat"
    message: str = Field(min_length=1, max_length=500)


class WindowFocusIntent(Strict):
    kind: Literal["computer.window.focus"] = "computer.window.focus"
    handle: int = Field(gt=0, le=18446744073709551615)
    process_id: int = Field(gt=0)
    window_class: str = Field(min_length=1, max_length=100)
    window_title: str = Field(min_length=1, max_length=110)
    window_title_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class WindowButtonIntent(WindowFocusIntent):
    kind: Literal["computer.button.invoke"] = "computer.button.invoke"
    path: tuple[int, ...] = Field(min_length=1, max_length=2)
    button_name: str = Field(min_length=1, max_length=90)
    button_automation_id: str = Field(default="", max_length=100)


class DynamicAppLaunchIntent(Strict):
    kind: Literal["app.launch.dynamic"] = "app.launch.dynamic"
    app_name: str = Field(min_length=1, max_length=180)
    launch_target: str = Field(min_length=1, max_length=1000)
    target_type: Literal["executable", "shortcut"] = "executable"


class WindowControlInvokeIntent(WindowFocusIntent):
    kind: Literal["computer.control.invoke"] = "computer.control.invoke"
    path: tuple[int, ...] = Field(min_length=1, max_length=4)
    control_type: str = Field(min_length=1, max_length=60)
    control_name: str = Field(default="", max_length=120)
    control_automation_id: str = Field(default="", max_length=120)


class WindowVisualSnapshotIntent(WindowFocusIntent):
    kind: Literal["computer.window.capture"] = "computer.window.capture"


class WindowUnderstandIntent(WindowFocusIntent):
    kind: Literal["computer.window.understand"] = "computer.window.understand"
    prompt: str = Field(default="", max_length=800)


class WindowTextInputIntent(WindowFocusIntent):
    kind: Literal["computer.control.set_text"] = "computer.control.set_text"
    path: tuple[int, ...] = Field(min_length=1, max_length=4)
    control_type: str = Field(min_length=1, max_length=60)
    control_name: str = Field(default="", max_length=120)
    control_automation_id: str = Field(default="", max_length=120)
    text: str = Field(min_length=1, max_length=2000)
    replace: bool = True


DeveloperAction = Literal[
    "workspace.inspect",
    "git.status",
    "git.diff",
    "git.push",
    "test.python",
    "test.npm",
    "test.maven",
    "build.npm",
    "build.maven",
    "deploy.vercel.preview",
    "deploy.vercel.production",
]


class DeveloperActionIntent(Strict):
    kind: Literal["developer.action"] = "developer.action"
    action: DeveloperAction
    workspace: str = Field(min_length=1, max_length=500)


WorkAction = Literal[
    "filesystem.list",
    "filesystem.read",
    "filesystem.write_text",
    "filesystem.append_text",
    "filesystem.mkdir",
    "terminal.run",
]



ProfessionalAction = Literal[
    "documents.compose",
    "documents.docx.compose",
    "spreadsheet.analyze",
    "spreadsheet.xlsx.create",
    "spreadsheet.xlsx.analyze",
    "analytics.analyze",
    "datasets.prepare",
    "design.assist",
    "database.query",
    "knowledge.organize",
    "maya.assist",
    "maya.execute",
    "blender.assist",
    "blender.execute",
    "cad.assets.inspect",
    "bim.assets.inspect",
    "media.assets.inspect",
    "presentation.compose",
    "presentation.pptx.compose",
    "pdf.compose",
    "marketing.plan",
    "ecommerce.catalog.audit",
    "crm.pipeline.analyze",
    "operations.sop.compose",
    "logistics.analyze",
    "hr.organize",
    "finance.workbook.analyze",
    "accounting.reconcile.preview",
    "support.triage",
    "office.report.from.xlsx",
    "office.open.document",
]


class ProfessionalActionIntent(Strict):
    kind: Literal["professional.action"] = "professional.action"
    action: ProfessionalAction
    workspace: str = Field(min_length=1, max_length=500)
    arguments: dict[str, Any] = Field(default_factory=dict)

class WorkActionIntent(Strict):
    kind: Literal["work.action"] = "work.action"
    action: WorkAction
    workspace: str = Field(min_length=1, max_length=500)
    path: str = Field(default=".", max_length=500)
    content: str | None = Field(default=None, max_length=20000)
    executable: str | None = Field(default=None, max_length=80)
    args: list[str] = Field(default_factory=list, max_length=32)


ExecutableIntent = Union[
    SearchIntent,
    AppLaunchIntent,
    WindowListIntent,
    WindowTreeIntent,
    BrowserInspectIntent,
    BunoChatIntent,
    WindowFocusIntent,
    WindowButtonIntent,
    DynamicAppLaunchIntent,
    WindowControlInvokeIntent,
    WindowVisualSnapshotIntent,
    WindowUnderstandIntent,
    WindowTextInputIntent,
    DeveloperActionIntent,
    WorkActionIntent,
    ProfessionalActionIntent,
]


class PendingAction(Strict):
    id: str
    kind: Literal[
        "browser.search", "app.launch", "computer.windows.list", "computer.window.inspect",
        "browser.inspect", "buno.chat", "computer.window.focus", "computer.button.invoke",
        "app.launch.dynamic", "computer.control.invoke", "computer.window.capture", "computer.window.understand", "computer.control.set_text",
        "developer.action", "work.action", "professional.action"
    ]
    description: str
    target: str
    expires_at: float
    fingerprint: str


class Event(Strict):
    id: int
    kind: str
    message: str
    at: str


class MissionVerification(Strict):
    confirmed: bool


class BrowserInspectionRequest(Strict):
    url: str = Field(min_length=14, max_length=400)


class WindowInspectionRequest(Strict):
    handle: int = Field(gt=0, le=18446744073709551615)


class BunoChatRequest(Strict):
    message: str = Field(min_length=1, max_length=500)


class WindowFocusRequest(Strict):
    handle: int = Field(gt=0, le=18446744073709551615)


class WindowButtonRequest(WindowFocusRequest):
    path: tuple[int, ...] = Field(min_length=1, max_length=2)


class DeveloperActionRequest(Strict):
    action: DeveloperAction
    workspace: str = Field(min_length=1, max_length=500)


class ProfessionalTaskRequest(Strict):
    objective: str = Field(min_length=1, max_length=1200)
    agent_id: str | None = Field(default=None, max_length=100)


class WorkActionRequest(Strict):
    action: WorkAction
    workspace: str = Field(min_length=1, max_length=500)
    path: str = Field(default=".", max_length=500)
    content: str | None = Field(default=None, max_length=20000)
    executable: str | None = Field(default=None, max_length=80)
    args: list[str] = Field(default_factory=list, max_length=32)


class SkillProposalRequest(Strict):
    arguments: dict[str, Any] = Field(default_factory=dict)


class SkillMissionStep(Strict):
    skill_id: str = Field(min_length=2, max_length=120)
    arguments: dict[str, Any] = Field(default_factory=dict)


class SkillMissionRequest(Strict):
    objective: str = Field(min_length=1, max_length=1200)
    steps: list[SkillMissionStep] = Field(min_length=1, max_length=8)


class DynamicAppLaunchRequest(Strict):
    app_name: str = Field(min_length=1, max_length=180)


class WindowVisualSnapshotRequest(WindowFocusRequest):
    pass


class WindowUnderstandingRequest(WindowFocusRequest):
    prompt: str = Field(default="", max_length=800)


class MultiAppMissionRequest(Strict):
    objective: str = Field(min_length=1, max_length=1200)
    workspace: str | None = Field(default=None, max_length=500)
    spreadsheet_path: str | None = Field(default=None, max_length=500)
    report_path: str | None = Field(default=None, max_length=500)


class AutonomousMissionRequest(Strict):
    objective: str = Field(min_length=1, max_length=1200)
    context: dict[str, Any] = Field(default_factory=dict)
    steps: list[SkillMissionStep] = Field(default_factory=list, max_length=8)
    max_steps: int = Field(default=8, ge=1, le=8)
    recovery_budget: int = Field(default=1, ge=0, le=2)


class MissionContextRequest(Strict):
    workspace: str = Field(min_length=1, max_length=500)
    spreadsheet_path: str = Field(min_length=1, max_length=500)
    report_path: str = Field(default="oryven-report.docx", min_length=1, max_length=500)


class FunctionalMVPRequest(Strict):
    objective: str = Field(default="", max_length=1200)
    context: dict[str, Any] = Field(default_factory=dict)


class WindowControlRequest(WindowFocusRequest):
    path: tuple[int, ...] = Field(min_length=1, max_length=4)


class WindowTextInputRequest(WindowControlRequest):
    text: str = Field(min_length=1, max_length=2000)
    replace: bool = True
