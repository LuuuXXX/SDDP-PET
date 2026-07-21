"""sddp CLI entry point (D0-9).

Per spec cli-runner requirement 1: provides `sddp run` command via Typer.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from ..engine.agents import AgentFactory
from ..engine.cost_meter import CostMeter
from ..engine.flows.phase_0_2_linear import LinearPhase02Flow
from ..engine.kg_tools import KGTools
from ..schemas.renderer import to_markdown, from_markdown
from ..schemas import Proposal, DeltaSpec, DeltaDesign
from .feedback_adapter import CLIHumanFeedbackAdapter
from . import flow_state

app = typer.Typer(
    name="sddp",
    help="SDDP-PET engine CLI (Dev-Phase 0)",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _read_proposal_input(proposal_arg: str) -> str:
    """If proposal_arg is a file path, read its content; else use as string."""
    p = Path(proposal_arg)
    if p.is_file():
        return p.read_text(encoding="utf-8")
    return proposal_arg


@app.command()
def run(
    proposal: Annotated[str, typer.Argument(help="Proposal text, or path to a .txt file containing it")],
    project: Annotated[Path, typer.Option("--project", "-p", help="Path to the project to scan for KG")] = Path("."),
    output: Annotated[Path, typer.Option("--output", "-o", help="Output directory for produced docs")] = Path("./out"),
    kg_db: Annotated[Path, typer.Option("--kg-db", help="KG SQLite path")] = Path("knowledge_graph.db"),
    flow_db: Annotated[Path, typer.Option("--flow-db", help="Flow state SQLite path")] = Path(
        os.environ.get("SDDP_FLOW_STATE_DB", str(Path.home() / ".sddp-pet" / "flow_state.db"))
    ),
    resume: Annotated[Optional[str], typer.Option("--resume", help="Resume a paused/aborted flow by id")] = None,
    mock: Annotated[bool, typer.Option("--mock", help="Use mock LLM (no OpenAI API call)")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Auto-approve all confirmation points")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show full cost report")] = False,
) -> None:
    """Run the SDDP Phase 0 + 2 linear flow on a proposal.

    Examples:
        sddp run "给这个 Python 项目加一个配置热重载功能" --project ./my-proj
        sddp run proposals/sample.txt --project ./my-proj --mock  # mock mode, no API key needed
    """
    proposal_text = _read_proposal_input(proposal)

    # Set up flow_id
    flow_id = resume or str(uuid.uuid4())
    console.print(f"[bold]Flow ID:[/bold] {flow_id}")

    # Initialize Flow state DB
    flow_state.DEFAULT_DB_PATH = flow_db

    # Load prior state on resume (D0-10): {step_name: step_output} for skip-on-resume
    prior_state: dict[str, dict] = {}
    if resume:
        for step_name in flow_state.list_steps(flow_id, db_path=flow_db):
            loaded = flow_state.load_state(flow_id, step=step_name, db_path=flow_db)
            if loaded is not None:
                prior_state[step_name] = loaded
        if prior_state:
            console.print(f"[green]Resuming:[/green] {len(prior_state)} cached step(s) → {sorted(prior_state)}")
        else:
            console.print("[yellow]Resume requested but no prior state found; running from scratch[/yellow]")

    # Determine LLM mode
    use_mock = mock or not os.environ.get("OPENAI_API_KEY")
    if use_mock and not mock:
        console.print("[yellow]OPENAI_API_KEY not set; using --mock mode automatically[/yellow]")

    # Build factory
    from ..engine.agents import DEFAULT_ROLE_MODELS
    cost_meter = CostMeter(default_model=DEFAULT_ROLE_MODELS["orchestrator"])
    kg_tools = None
    if project.is_dir():
        # Pre-scan the project to populate KG
        from ..kg.scan import scan_project
        try:
            summary = scan_project(project, db_path=kg_db, prefer_scip=False)
            console.print(
                f"[green]KG pre-scan:[/green] {summary.get('parsed_files', 0)} files, "
                f"{summary.get('total_symbols', 0)} symbols → {kg_db}"
            )
            kg_tools = KGTools(kg_db)
        except Exception as e:
            console.print(f"[yellow]KG pre-scan failed (non-fatal):[/yellow] {e}")

    factory = AgentFactory(
        llm_client=None if use_mock else _build_openai_client(),
        cost_meter=cost_meter,
        kg_tools=kg_tools,
        mock_mode=use_mock,
    )

    # Build feedback adapter
    feedback = CLIHumanFeedbackAdapter(auto_approve=yes or use_mock)

    # Build flow with @persist wiring (D0-10)
    def _persist_step(fid: str, step_name: str, step_output: dict) -> None:
        flow_state.save_state(fid, step_name, step_output, db_path=flow_db)

    flow = LinearPhase02Flow(
        agent_factory=factory,
        kg_db_path=str(kg_db),
        human_feedback_handler=feedback,
        flow_id=flow_id,
        prior_state=prior_state,
        persist_step=_persist_step,
    )

    # Create/update flow meta
    inputs = {"requirement": proposal_text, "project_path": str(project)}
    flow_state.create_flow_meta(flow_id, inputs, db_path=flow_db)

    # Run
    try:
        result = flow.kickoff(inputs)
        flow_state.update_flow_status(flow_id, "completed", db_path=flow_db)
    except KeyboardInterrupt:
        flow_state.update_flow_status(flow_id, "paused", db_path=flow_db)
        console.print(f"\n[yellow]Interrupted. Resume with:[/yellow] sddp run ... --resume {flow_id}")
        raise
    except Exception as e:
        flow_state.update_flow_status(flow_id, "aborted", db_path=flow_db)
        console.print(f"[red]Flow failed:[/red] {e}")
        raise

    # Write outputs
    output.mkdir(parents=True, exist_ok=True)
    _write_outputs(result, output, cost_meter)
    _print_summary(result, cost_meter, verbose=verbose)


def _build_openai_client():
    """Construct OpenAI client lazily (only if not mock)."""
    try:
        from openai import OpenAI
        return OpenAI()
    except Exception as e:
        console.print(f"[red]Failed to construct OpenAI client:[/red] {e}")
        raise


def _write_outputs(result, output: Path, cost_meter: CostMeter) -> None:
    """Write the 4 markdown docs + cost_report.json."""
    # Proposal
    if result.proposal:
        try:
            p = Proposal.model_validate(result.proposal) if isinstance(result.proposal, dict) else result.proposal
            (output / "proposal.md").write_text(to_markdown(p), encoding="utf-8")
        except Exception as e:
            (output / "proposal.raw.json").write_text(json.dumps(result.proposal, indent=2, default=str), encoding="utf-8")
            console.print(f"[yellow]proposal.md render failed; wrote raw json:[/yellow] {e}")

    # delta_spec
    if result.delta_spec:
        try:
            ds = DeltaSpec.model_validate(result.delta_spec) if isinstance(result.delta_spec, dict) else result.delta_spec
            (output / "delta_spec.md").write_text(to_markdown(ds), encoding="utf-8")
        except Exception as e:
            (output / "delta_spec.raw.json").write_text(json.dumps(result.delta_spec, indent=2, default=str), encoding="utf-8")

    # delta_design
    if result.delta_design:
        try:
            dd = DeltaDesign.model_validate(result.delta_design) if isinstance(result.delta_design, dict) else result.delta_design
            (output / "delta_design.md").write_text(to_markdown(dd), encoding="utf-8")
        except Exception:
            (output / "delta_design.raw.json").write_text(json.dumps(result.delta_design, indent=2, default=str), encoding="utf-8")

    # architecture_research (only if produced)
    if result.architecture_research:
        try:
            from ..schemas import ArchitectureResearch
            ar = ArchitectureResearch.model_validate(result.architecture_research) if isinstance(result.architecture_research, dict) else result.architecture_research
            (output / "architecture_research.md").write_text(to_markdown(ar), encoding="utf-8")
        except Exception:
            (output / "architecture_research.raw.json").write_text(json.dumps(result.architecture_research, indent=2, default=str), encoding="utf-8")

    # cost_report
    cost_meter.write_report(output / "cost_report.json")


def _print_summary(result, cost_meter: CostMeter, *, verbose: bool) -> None:
    """Print cost summary to stdout."""
    report = cost_meter.to_report_dict()
    table = Table(title="Cost Summary")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Cost (USD)", f"${report['measured_cost_usd']:.4f}")
    table.add_row("Wall clock (min, no human wait)", f"{report['wall_clock_minutes_excluding_human_wait']:.2f}")
    table.add_row("Structured output compliance", f"{report['structured_output_first_try_rate'] * 100:.1f}%")
    table.add_row("Total tokens", str(report['total_tokens']))
    table.add_row("Call count", str(report['call_count']))
    console.print(table)

    if result.completed_steps:
        steps_table = Table(title="Completed Steps")
        steps_table.add_column("#")
        steps_table.add_column("Step")
        for i, step in enumerate(result.completed_steps, 1):
            steps_table.add_row(str(i), step)
        console.print(steps_table)

    dod = report.get("dod_checks", {})
    if dod:
        console.print("\n[bold]DoD threshold checks:[/bold]")
        for check, passed in dod.items():
            icon = "[green]✓[/green]" if passed else "[red]✗[/red]"
            console.print(f"  {icon} {check}")

    if verbose:
        console.print("\n[bold]Full cost report:[/bold]")
        console.print_json(json.dumps(report))


@app.command()
def flows(
    flow_db: Annotated[Path, typer.Option("--flow-db")] = Path(
        os.environ.get("SDDP_FLOW_STATE_DB", str(Path.home() / ".sddp-pet" / "flow_state.db"))
    ),
) -> None:
    """List pending/running flows (resumable)."""
    flows = flow_state.list_pending_flows(db_path=flow_db)
    if not flows:
        console.print("[yellow]No pending flows.[/yellow]")
        return
    table = Table(title="Pending Flows")
    table.add_column("Flow ID")
    table.add_column("Status")
    table.add_column("Updated")
    for f in flows:
        table.add_row(f["flow_id"], f["status"], f["updated_at"])
    console.print(table)


@app.command()
def scan(
    project: Annotated[Path, typer.Argument(help="Project to scan")],
    kg_db: Annotated[Path, typer.Option("--kg-db")] = Path("knowledge_graph.db"),
) -> None:
    """Pre-scan a project into the knowledge graph (without running the flow)."""
    from ..kg.scan import scan_project
    summary = scan_project(project, db_path=kg_db, prefer_scip=False)
    if "error" in summary:
        console.print(f"[red]Error:[/red] {summary['error']}")
        raise typer.Exit(2)
    console.print_json(json.dumps(summary, default=str))


@app.command()
def serve(
    project: Annotated[Path, typer.Option("--project", "-p", help="Path to the project to scan for KG")] = Path("."),
    kg_db: Annotated[Path, typer.Option("--kg-db", help="KG SQLite path")] = Path("knowledge_graph.db"),
    flow_db: Annotated[Path, typer.Option("--flow-db", help="Flow state SQLite path")] = Path(
        os.environ.get("SDDP_FLOW_STATE_DB", str(Path.home() / ".sddp-pet" / "flow_state.db"))
    ),
    host: Annotated[str, typer.Option("--host", help="Bind host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="Bind port")] = 8765,
    mock: Annotated[bool, typer.Option("--mock", help="Use mock LLM (no OPENAI_API_KEY needed)")] = False,
) -> None:
    """Start the WebSocket IPC server (Dev-Phase 1 D1-4).

    Listens on ws://<host>:<port> (default ws://127.0.0.1:8765) for the Electron
    frontend. Runs the SDDP flow in a worker thread per `start_flow` RPC; pushes
    state changes / documents / cost updates back to the client.

    Examples:
        sddp serve                              # real-LLM mode (needs OPENAI_API_KEY)
        sddp serve --mock                       # mock-LLM mode (CI / dev / frontend dev)
        sddp serve --port 9000                  # custom port
    """
    import uvicorn

    use_mock = mock or not os.environ.get("OPENAI_API_KEY")
    if use_mock and not mock:
        console.print("[yellow]OPENAI_API_KEY not set; --mock mode auto-enabled[/yellow]")
    if project.is_dir():
        from ..kg.scan import scan_project
        try:
            summary = scan_project(project, db_path=kg_db, prefer_scip=False)
            console.print(
                f"[green]KG pre-scan:[/green] {summary.get('parsed_files', 0)} files, "
                f"{summary.get('total_symbols', 0)} symbols → {kg_db}"
            )
        except Exception as e:
            console.print(f"[yellow]KG pre-scan failed (non-fatal):[/yellow] {e}")

    def factory_factory(cost_meter=None, kg_tools=None):
        from ..engine.agents import AgentFactory
        llm_client = None if use_mock else _build_openai_client_silent()
        return AgentFactory(
            llm_client=llm_client,
            cost_meter=cost_meter or CostMeter(),
            kg_tools=kg_tools,
            mock_mode=use_mock,
        )

    from ..ipc.server import create_app
    app = create_app(
        agent_factory_factory=factory_factory,
        kg_db_path=str(kg_db),
        flow_db_path=str(flow_db),
        mock_mode=use_mock,
    )
    console.print(f"[bold green]SDDP IPC server[/bold green] → ws://{host}:{port}  (mock={use_mock})")
    uvicorn.run(app, host=host, port=port, log_level="info")


def _build_openai_client_silent():
    """Like _build_openai_client but suppresses rich error printing (used by `serve`)."""
    try:
        from openai import OpenAI
        return OpenAI()
    except Exception as e:
        console.print(f"[red]Failed to construct OpenAI client:[/red] {e}")
        raise


if __name__ == "__main__":
    app()
