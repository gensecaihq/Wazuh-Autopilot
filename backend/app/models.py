import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("usr"))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(default=True)
    last_login_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class ApiToken(Base):
    __tablename__ = "api_tokens"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("tok"))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32))
    prefix: Mapped[str] = mapped_column(String(16))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[Optional[datetime]]
    last_used_at: Mapped[Optional[datetime]]


class Setting(Base):
    """One row per settings section (org, wazuh, model, policy, ...)."""

    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(default=dict)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class AgentDef(Base):
    __tablename__ = "agents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    codename: Mapped[str] = mapped_column(String(64))
    persona: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    responsibilities: Mapped[list] = mapped_column(default=list)
    tier: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(16))
    icon: Mapped[str] = mapped_column(String(40))
    avatar_color: Mapped[str] = mapped_column(String(16))
    skills: Mapped[list] = mapped_column(default=list)
    standards: Mapped[list] = mapped_column(default=list)
    tools: Mapped[list] = mapped_column(default=list)
    handoffs: Mapped[list] = mapped_column(default=list)
    enabled: Mapped[bool] = mapped_column(default=True)
    model_override: Mapped[Optional[dict]]
    autonomy_cap: Mapped[str] = mapped_column(String(16), default="autonomous")
    temperature: Mapped[Optional[float]]
    max_tokens: Mapped[Optional[int]]
    system_prompt_extra: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class SkillOverride(Base):
    """Custom skills and edits to built-in skills. Built-ins ship as SKILL.md files."""

    __tablename__ = "skills"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32))
    standards: Mapped[list] = mapped_column(default=list)
    tools: Mapped[list] = mapped_column(default=list)
    body_md: Mapped[str] = mapped_column(Text)
    builtin: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Workflow(Base):
    __tablename__ = "workflows"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(default=True)
    trigger: Mapped[dict] = mapped_column(default=dict)
    entry_agent: Mapped[str] = mapped_column(String(64))
    steps: Mapped[list] = mapped_column(default=list)
    last_run_at: Mapped[Optional[datetime]]
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("alr"))
    wazuh_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    ts: Mapped[datetime] = mapped_column(index=True)
    rule_id: Mapped[str] = mapped_column(String(16), index=True)
    rule_level: Mapped[int] = mapped_column(Integer, index=True)
    rule_description: Mapped[str] = mapped_column(Text)
    rule_groups: Mapped[list] = mapped_column(default=list)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    agent_id: Mapped[Optional[str]] = mapped_column(String(16), index=True)
    agent_name: Mapped[Optional[str]] = mapped_column(String(128))
    agent_ip: Mapped[Optional[str]] = mapped_column(String(64))
    src_ip: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    src_country: Mapped[Optional[str]] = mapped_column(String(64))
    src_lat: Mapped[Optional[float]]
    src_lon: Mapped[Optional[float]]
    dst_user: Mapped[Optional[str]] = mapped_column(String(128))
    mitre: Mapped[list] = mapped_column(default=list)
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)
    case_id: Mapped[Optional[str]] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), index=True)
    raw: Mapped[dict] = mapped_column(default=dict)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("case"))
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    confidence: Mapped[float] = mapped_column(default=0.5)
    assignee_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    entities: Mapped[list] = mapped_column(default=list)
    mitre: Mapped[list] = mapped_column(default=list)
    agents_involved: Mapped[list] = mapped_column(default=list)
    group_key: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    resolved_at: Mapped[Optional[datetime]]

    assignee: Mapped[Optional[User]] = relationship(lazy="joined")


class TimelineEvent(Base):
    __tablename__ = "timeline"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("tl"))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(default=utcnow)
    kind: Mapped[str] = mapped_column(String(16))
    actor: Mapped[str] = mapped_column(String(120))
    text: Mapped[str] = mapped_column(Text)
    ref_id: Mapped[Optional[str]] = mapped_column(String(40))


class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("fnd"))
    case_id: Mapped[Optional[str]] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(40))
    agent: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(300))
    body_md: Mapped[str] = mapped_column(Text)
    standard_refs: Mapped[list] = mapped_column(default=list)
    confidence: Mapped[Optional[float]]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("cmt"))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    author: Mapped[User] = relationship(lazy="joined")


class Action(Base):
    __tablename__ = "actions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("act"))
    case_id: Mapped[Optional[str]] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(40))
    plan_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    type: Mapped[str] = mapped_column(String(32))
    target: Mapped[str] = mapped_column(String(300))
    params: Mapped[dict] = mapped_column(default=dict)
    risk: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(default=0.5)
    rationale: Mapped[str] = mapped_column(Text, default="")
    proposed_by: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="proposed", index=True)
    autonomy: Mapped[str] = mapped_column(String(16), default="manual")
    auto_approved: Mapped[bool] = mapped_column(default=False)
    approved_by_id: Mapped[Optional[str]] = mapped_column(String(40))
    approved_by_name: Mapped[Optional[str]] = mapped_column(String(120))
    approved_at: Mapped[Optional[datetime]]
    rejected_reason: Mapped[Optional[str]] = mapped_column(Text)
    executed_by: Mapped[Optional[str]] = mapped_column(String(120))
    executed_at: Mapped[Optional[datetime]]
    result: Mapped[dict] = mapped_column(default=dict)
    verification: Mapped[dict] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    expires_at: Mapped[Optional[datetime]]


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("run"))
    workflow_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    workflow_name: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    trigger: Mapped[str] = mapped_column(String(16))
    case_id: Mapped[Optional[str]] = mapped_column(String(40), index=True)
    input: Mapped[dict] = mapped_column(default=dict)
    output_md: Mapped[str] = mapped_column(Text, default="")
    agents: Mapped[list] = mapped_column(default=list)
    handoffs: Mapped[list] = mapped_column(default=list)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(default=0.0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text)
    dry_run: Mapped[bool] = mapped_column(default=False)
    started_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    finished_at: Mapped[Optional[datetime]]
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)


class Span(Base):
    __tablename__ = "spans"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("spn"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[Optional[str]] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(200))
    agent_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="ok")
    started_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    attributes: Mapped[dict] = mapped_column(default=dict)
    input_preview: Mapped[str] = mapped_column(Text, default="")
    output_preview: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[Optional[str]] = mapped_column(Text)


Index("ix_spans_agent_started", Span.agent_id, Span.started_at)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("aud"))
    ts: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    actor_id: Mapped[Optional[str]] = mapped_column(String(64))
    actor_name: Mapped[str] = mapped_column(String(120))
    actor_type: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str] = mapped_column(String(300), default="")
    detail: Mapped[dict] = mapped_column(default=dict)
    ip: Mapped[Optional[str]] = mapped_column(String(64))


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("rpt"))
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(300))
    body_md: Mapped[str] = mapped_column(Text)
    agent: Mapped[str] = mapped_column(String(64))
    run_id: Mapped[Optional[str]] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class DetectionProposal(Base):
    __tablename__ = "detections"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("det"))
    title: Mapped[str] = mapped_column(String(300))
    rule_format: Mapped[str] = mapped_column(String(32))
    rule_body: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    mitre: Mapped[list] = mapped_column(default=list)
    agent: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class PlaygroundSession(Base):
    __tablename__ = "playground_sessions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("pg"))
    agent_id: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(String(40))
    dry_run: Mapped[bool] = mapped_column(default=True)
    messages: Mapped[list] = mapped_column(default=list)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class EvalSuite(Base):
    __tablename__ = "eval_suites"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    agent_id: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    cases: Mapped[list] = mapped_column(default=list)
    evaluators: Mapped[list] = mapped_column(default=list)


class EvalRun(Base):
    __tablename__ = "eval_runs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("evr"))
    suite_id: Mapped[str] = mapped_column(ForeignKey("eval_suites.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[Optional[datetime]]
    overall_score: Mapped[Optional[float]]
    pass_rate: Mapped[Optional[float]]
    results: Mapped[list] = mapped_column(default=list)
    error: Mapped[Optional[str]] = mapped_column(Text)
