#!/usr/bin/env python3
"""Linear seeder for deterministic Developer Health demo fixtures."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests
import yaml


API_URL = "https://api.linear.app/graphql"
CANONICAL_THEMES = {
    "Feature Delivery",
    "Operational / Support",
    "Maintenance / Tech Debt",
    "Quality / Reliability",
    "Risk / Security",
}
LABEL_COLORS = {
    "Feature Delivery": "#5E6AD2",
    "Operational / Support": "#F2C94C",
    "Maintenance / Tech Debt": "#828282",
    "Quality / Reliability": "#27AE60",
    "Risk / Security": "#EB5757",
    "seeded": "#888888",
}


def stable_hash(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_iso_date(value: str, label: str) -> dt.datetime:
    cleaned = value.rstrip("Z")
    try:
        parsed = dt.datetime.fromisoformat(cleaned)
    except ValueError as exc:
        msg = f"--{label} must be ISO-8601, for example 2024-01-31"
        raise ValueError(msg) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def month_key(value: dt.datetime) -> str:
    return value.strftime("%Y-%m")


def clamp_int(value: float, minimum: int = 1) -> int:
    return max(minimum, int(round(value)))


def pick_weighted(rng: random.Random, weights: dict[Any, float]) -> Any:
    keys = list(weights.keys())
    vals = list(weights.values())
    return rng.choices(keys, weights=vals, k=1)[0]


def priority_name(priority: int) -> str:
    return {1: "urgent", 2: "high", 3: "normal", 4: "low"}.get(priority, "none")


class LinearClient:
    """Small Linear GraphQL client with dry-run stubs for write operations."""

    def __init__(self, api_key: str | None, dry_run: bool = False) -> None:
        self.api_key = api_key
        self.dry_run = dry_run
        self._counter = 0

    def log(self, message: str) -> None:
        print(f"[LinearSeeder] {message}")

    def graphql(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        if self.dry_run:
            if write:
                self._counter += 1
                return {"dryRun": {"id": f"dry-{self._counter}"}}
            return {}

        if not self.api_key:
            raise ValueError("LINEAR_API_KEY is required when not running --dry-run")

        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {"query": query, "variables": variables or {}}
        for attempt in range(3):
            response = requests.post(API_URL, headers=headers, json=payload, timeout=40)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "2"))
                time.sleep(max(1, retry_after))
                continue
            if response.status_code >= 500:
                self.log(
                    f"Linear {response.status_code} on attempt {attempt + 1}/3: "
                    f"{response.text[:300]}"
                )
                time.sleep(1 + attempt)
                continue
            data = response.json()
            if data.get("errors"):
                raise RuntimeError(json.dumps(data["errors"], indent=2))
            return data.get("data", {})
        raise RuntimeError("Linear GraphQL request failed after 3 attempts")

    def find_team(self, key: str) -> dict[str, Any] | None:
        query = """
        query TeamByKey($key: String!) {
          teams(filter: { key: { eq: $key } }, first: 1) {
            nodes { id key name }
          }
        }
        """
        data = self.graphql(query, {"key": key})
        nodes = data.get("teams", {}).get("nodes", [])
        return nodes[0] if nodes else None

    def create_team(self, key: str, name: str, description: str) -> dict[str, Any]:
        mutation = """
        mutation CreateTeam($input: TeamCreateInput!) {
          teamCreate(input: $input) {
            success
            team { id key name }
          }
        }
        """
        if self.dry_run:
            return {"id": f"team-{key}", "key": key, "name": name}
        data = self.graphql(
            mutation,
            {"input": {"key": key, "name": name, "description": description}},
            write=True,
        )
        return data["teamCreate"]["team"]

    def find_project(self, name: str) -> dict[str, Any] | None:
        query = """
        query ProjectByName($name: String!) {
          projects(filter: { name: { eq: $name } }, first: 1) {
            nodes { id name }
          }
        }
        """
        data = self.graphql(query, {"name": name})
        nodes = data.get("projects", {}).get("nodes", [])
        return nodes[0] if nodes else None

    def create_project(
        self,
        name: str,
        team_id: str,
        description: str,
    ) -> dict[str, Any]:
        mutation = """
        mutation CreateProject($input: ProjectCreateInput!) {
          projectCreate(input: $input) {
            success
            project { id name }
          }
        }
        """
        if self.dry_run:
            return {"id": f"project-{stable_hash(name)}", "name": name}
        data = self.graphql(
            mutation,
            {
                "input": {
                    "name": name,
                    "description": description,
                    "teamIds": [team_id],
                }
            },
            write=True,
        )
        return data["projectCreate"]["project"]

    def find_label(self, team_id: str, name: str) -> dict[str, Any] | None:
        query = """
        query LabelByName($teamId: ID!, $name: String!) {
          issueLabels(
            filter: { team: { id: { eq: $teamId } }, name: { eq: $name } }
            first: 1
          ) {
            nodes { id name }
          }
        }
        """
        data = self.graphql(query, {"teamId": team_id, "name": name})
        nodes = data.get("issueLabels", {}).get("nodes", [])
        return nodes[0] if nodes else None

    def create_label(self, team_id: str, name: str, color: str) -> dict[str, Any]:
        mutation = """
        mutation CreateLabel($input: IssueLabelCreateInput!) {
          issueLabelCreate(input: $input) {
            success
            issueLabel { id name }
          }
        }
        """
        if self.dry_run:
            return {"id": f"label-{stable_hash(team_id + name)}", "name": name}
        data = self.graphql(
            mutation,
            {"input": {"teamId": team_id, "name": name, "color": color}},
            write=True,
        )
        return data["issueLabelCreate"]["issueLabel"]

    def find_cycle(self, team_id: str, name: str) -> dict[str, Any] | None:
        query = """
        query CycleByName($teamId: ID!, $name: String!) {
          cycles(
            filter: { team: { id: { eq: $teamId } }, name: { eq: $name } }
            first: 1
          ) {
            nodes { id name number startsAt endsAt }
          }
        }
        """
        data = self.graphql(query, {"teamId": team_id, "name": name})
        nodes = data.get("cycles", {}).get("nodes", [])
        return nodes[0] if nodes else None

    def create_cycle(
        self,
        team_id: str,
        name: str,
        starts_at: dt.datetime,
        ends_at: dt.datetime,
    ) -> dict[str, Any]:
        mutation = """
        mutation CreateCycle($input: CycleCreateInput!) {
          cycleCreate(input: $input) {
            success
            cycle { id name number startsAt endsAt }
          }
        }
        """
        if self.dry_run:
            return {"id": f"cycle-{stable_hash(team_id + name)}", "name": name}
        data = self.graphql(
            mutation,
            {
                "input": {
                    "teamId": team_id,
                    "name": name,
                    "startsAt": starts_at.date().isoformat(),
                    "endsAt": ends_at.date().isoformat(),
                }
            },
            write=True,
        )
        return data["cycleCreate"]["cycle"]

    def find_issue(self, team_id: str, external_id: str) -> dict[str, Any] | None:
        query = """
        query IssueByExternalId($teamId: ID!, $needle: String!) {
          issues(
            filter: { team: { id: { eq: $teamId } }, title: { contains: $needle } }
            first: 1
          ) {
            nodes { id identifier title }
          }
        }
        """
        data = self.graphql(query, {"teamId": team_id, "needle": external_id})
        nodes = data.get("issues", {}).get("nodes", [])
        return nodes[0] if nodes else None

    def create_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        mutation = """
        mutation CreateIssue($input: IssueCreateInput!) {
          issueCreate(input: $input) {
            success
            issue { id identifier title }
          }
        }
        """
        if self.dry_run:
            return {
                "id": f"issue-{stable_hash(payload['title'])}",
                "identifier": f"DRY-{self._counter + 1}",
                "title": payload["title"],
            }
        data = self.graphql(mutation, {"input": payload}, write=True)
        return data["issueCreate"]["issue"]

    def create_comment(self, issue_id: str, body: str) -> dict[str, Any]:
        mutation = """
        mutation CreateComment($input: CommentCreateInput!) {
          commentCreate(input: $input) {
            success
            comment { id }
          }
        }
        """
        if self.dry_run:
            return {"id": f"comment-{stable_hash(issue_id + body)}"}
        data = self.graphql(
            mutation,
            {"input": {"issueId": issue_id, "body": body}},
            write=True,
        )
        return data["commentCreate"]["comment"]

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        query = """
        query UserByEmail($email: String!) {
          users(filter: { email: { eq: $email } }, first: 1) {
            nodes { id email name }
          }
        }
        """
        data = self.graphql(query, {"email": email})
        nodes = data.get("users", {}).get("nodes", [])
        return nodes[0] if nodes else None


class LinearSeeder:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        with Path(args.story).open("r", encoding="utf-8") as handle:
            self.story = yaml.safe_load(handle)

        self.validate_story()
        self.start_date, self.end_date, self.month_count = self.resolve_date_range()
        seed_input = f"{self.story.get('org_slug', 'org')}::{args.seed}"
        seed_hash = int(hashlib.sha256(seed_input.encode("utf-8")).hexdigest(), 16)
        self.rng = random.Random(seed_hash)  # nosec B311 - deterministic fixtures
        self.client = LinearClient(args.linear_api_key, dry_run=args.dry_run)

        self.teams: dict[str, dict[str, Any]] = {}
        self.projects: dict[str, dict[str, Any]] = {}
        self.labels_by_team: dict[str, dict[str, str]] = defaultdict(dict)
        self.cycles_by_team_month: dict[str, dict[int, dict[str, Any]]] = defaultdict(
            dict
        )
        self.assignees: list[dict[str, Any]] = []
        self.sample_issues: list[dict[str, Any]] = []

        self.manifest: dict[str, Any] = {
            "meta": {
                "generated_at": utc_now().isoformat(),
                "seed": args.seed,
                "dry_run": args.dry_run,
                "months": self.month_count,
                "start_date": self.start_date.date().isoformat(),
                "end_date": self.end_date.date().isoformat(),
            },
            "counts": {
                "teams": 0,
                "projects": 0,
                "cycles": 0,
                "issues_planned": 0,
                "issues_created": 0,
                "issues_skipped_existing": 0,
                "comments": 0,
                "by_theme": defaultdict(int),
                "by_team": defaultdict(int),
                "by_month": defaultdict(int),
                "by_arc": defaultdict(int),
            },
            "samples": [],
        }

    def validate_story(self) -> None:
        themes = set(self.story.get("investment_themes", []))
        if themes != CANONICAL_THEMES:
            missing = ", ".join(sorted(CANONICAL_THEMES - themes))
            extra = ", ".join(sorted(themes - CANONICAL_THEMES))
            raise ValueError(
                "story_map.yaml must use canonical Investment View themes "
                f"(missing: {missing or 'none'}; extra: {extra or 'none'})"
            )
        for arc in self.story.get("arcs", []):
            arc_themes = set(arc.get("investment_mix", {}))
            if arc_themes != CANONICAL_THEMES:
                raise ValueError(f"Arc {arc.get('name')} has non-canonical theme mix")

    def resolve_date_range(self) -> tuple[dt.datetime, dt.datetime, int]:
        if self.args.start_date:
            start = parse_iso_date(self.args.start_date, "start-date")
            end = (
                parse_iso_date(self.args.end_date, "end-date")
                if self.args.end_date
                else utc_now()
            )
            if end < start:
                raise ValueError("--end-date must be after --start-date")
            months = max(1, int(round((end - start).days / 30.0)))
            return start, end, months
        if self.args.end_date:
            raise ValueError("--start-date is required when --end-date is provided")
        months = int(self.story.get("timeline_months", 24))
        end = utc_now()
        start = end - dt.timedelta(days=months * 30)
        return start, end, months

    def log(self, message: str) -> None:
        self.client.log(message)

    def ensure_structure(self) -> None:
        for team in self.story["teams"]:
            existing = self.client.find_team(team["key"])
            created = existing or self.client.create_team(
                team["key"],
                team["name"],
                f"Seeded Developer Health fixture team for {team['domain']}.",
            )
            self.teams[team["key"]] = created
            self.manifest["counts"]["teams"] += int(existing is None)

        for project in self.story["projects"]:
            team_id = self.teams[project["team_key"]]["id"]
            existing = self.client.find_project(project["name"])
            created = existing or self.client.create_project(
                project["name"], team_id, project.get("description", "")
            )
            self.projects[project["name"]] = created
            self.manifest["counts"]["projects"] += int(existing is None)

        for team_key, team_obj in self.teams.items():
            for label in ["seeded", *sorted(CANONICAL_THEMES)]:
                found = self.client.find_label(team_obj["id"], label)
                created = found or self.client.create_label(
                    team_obj["id"], label, LABEL_COLORS.get(label, "#888888")
                )
                self.labels_by_team[team_key][label] = created["id"]

    def resolve_assignees(self) -> None:
        emails = [e.strip() for e in self.args.assignees.split(",") if e.strip()]
        if not emails:
            return
        for email in emails:
            user = self.client.find_user_by_email(email)
            if user:
                self.assignees.append(user)
        self.log(f"Resolved {len(self.assignees)} Linear assignees")

    def build_cycles(self) -> None:
        if not self.args.enable_cycles:
            return
        for team_key, team_obj in self.teams.items():
            for month_idx in range(self.month_count):
                for half in range(2):
                    cycle_idx = month_idx * 2 + half
                    starts_at = self.start_date + dt.timedelta(days=cycle_idx * 14)
                    ends_at = starts_at + dt.timedelta(days=13)
                    name = f"DH Seed {month_key(starts_at)}-{half + 1}"
                    existing = self.client.find_cycle(team_obj["id"], name)
                    cycle = existing or self.client.create_cycle(
                        team_obj["id"], name, starts_at, ends_at
                    )
                    self.cycles_by_team_month[team_key][cycle_idx] = cycle
                    self.manifest["counts"]["cycles"] += int(existing is None)

    def arc_for_month(self, month_idx: int) -> dict[str, Any] | None:
        return next(
            (
                arc
                for arc in self.story["arcs"]
                if arc["start_month"] <= month_idx <= arc["end_month"]
            ),
            None,
        )

    def make_issue_spec(
        self,
        team: dict[str, Any],
        project: dict[str, Any],
        month_idx: int,
        item_idx: int,
        arc: dict[str, Any],
    ) -> dict[str, Any]:
        created_at = self.start_date + dt.timedelta(
            days=month_idx * 30 + self.rng.randint(0, 27),
            hours=self.rng.randint(8, 18),
        )
        theme = pick_weighted(self.rng, arc["investment_mix"])
        priority = int(pick_weighted(self.rng, arc["priority_mix"]))
        estimate_min, estimate_max = arc.get("estimate_range", [1, 8])
        estimate = self.rng.choice([1, 2, 3, 5, 8, 13])
        estimate = max(estimate_min, min(estimate, estimate_max))
        service = self.rng.choice(self.story["services"])
        template = self.rng.choice(self.story["issue_templates"][theme])
        external_id = stable_hash(
            f"{team['key']}::{project['name']}::{month_idx}::{item_idx}::{theme}"
        )
        due_date = created_at + dt.timedelta(days=max(3, estimate * 2))
        title = template.format(service=service, domain=team["domain"])
        title = f"[{external_id}] {title}"
        cycle_idx = min(
            month_idx * 2 + self.rng.randint(0, 1), self.month_count * 2 - 1
        )

        description = "\n".join(
            [
                "Seeded Linear fixture for Developer Health analytics.",
                f"External ID: {external_id}",
                f"Simulated created_at: {created_at.isoformat()}",
                f"Story arc: {arc['name']}",
                f"Investment theme: {theme}",
                f"Team domain: {team['domain']}",
                f"Service: {service}",
                "This metadata is deterministic and safe to re-run.",
            ]
        )
        return {
            "external_id": external_id,
            "team_key": team["key"],
            "project_name": project["name"],
            "month_idx": month_idx,
            "created_at": created_at,
            "arc": arc["name"],
            "theme": theme,
            "priority": priority,
            "estimate": estimate,
            "service": service,
            "cycle_idx": cycle_idx,
            "title": title,
            "description": description,
            "due_date": due_date.date().isoformat(),
            "comment": (
                f"Seed note: {arc['name']} appears to lean toward {theme}; "
                f"simulated activity date {created_at.date().isoformat()}."
            ),
        }

    def issue_payload(self, spec: dict[str, Any]) -> dict[str, Any]:
        team_id = self.teams[spec["team_key"]]["id"]
        label_ids = [
            self.labels_by_team[spec["team_key"]]["seeded"],
            self.labels_by_team[spec["team_key"]][spec["theme"]],
        ]
        payload: dict[str, Any] = {
            "teamId": team_id,
            "title": spec["title"],
            "description": spec["description"],
            "priority": spec["priority"],
            "estimate": spec["estimate"],
            "dueDate": spec["due_date"],
            "labelIds": label_ids,
        }
        project = self.projects.get(spec["project_name"])
        if project:
            payload["projectId"] = project["id"]
        cycle = self.cycles_by_team_month.get(spec["team_key"], {}).get(
            spec["cycle_idx"]
        )
        if cycle:
            payload["cycleId"] = cycle["id"]
        if self.assignees and self.rng.random() > 0.15:
            payload["assigneeId"] = self.rng.choice(self.assignees)["id"]
        return payload

    def record_spec(
        self, spec: dict[str, Any], created: bool, skipped: bool = False
    ) -> None:
        counts = self.manifest["counts"]
        counts["issues_planned"] += 1
        counts["issues_created"] += int(created)
        counts["issues_skipped_existing"] += int(skipped)
        counts["by_theme"][spec["theme"]] += 1
        counts["by_team"][spec["team_key"]] += 1
        counts["by_month"][month_key(spec["created_at"])] += 1
        counts["by_arc"][spec["arc"]] += 1
        if len(self.sample_issues) < 8:
            self.sample_issues.append(
                {
                    "external_id": spec["external_id"],
                    "team": spec["team_key"],
                    "theme": spec["theme"],
                    "arc": spec["arc"],
                    "priority": priority_name(spec["priority"]),
                    "title": spec["title"],
                }
            )

    def seed_issue(self, spec: dict[str, Any], issue_number: int) -> None:
        team_id = self.teams[spec["team_key"]]["id"]
        existing = self.client.find_issue(team_id, spec["external_id"])
        if existing:
            self.record_spec(spec, created=False, skipped=True)
            return
        issue = self.client.create_issue(self.issue_payload(spec))
        self.record_spec(spec, created=True)
        if self.args.enable_comments and self.rng.random() <= self.arc_for_comment_rate(
            spec
        ):
            self.client.create_comment(issue["id"], spec["comment"])
            self.manifest["counts"]["comments"] += 1
        if issue_number % max(1, self.args.batch_size) == 0:
            self.log(f"Processed {issue_number} issues")

    def arc_for_comment_rate(self, spec: dict[str, Any]) -> float:
        arc = next(a for a in self.story["arcs"] if a["name"] == spec["arc"])
        return float(arc.get("comment_rate", 0.0))

    def generate_issues(self) -> None:
        issue_number = 0
        projects_by_team = {p["team_key"]: p for p in self.story["projects"]}
        for month_idx in range(self.month_count):
            arc = self.arc_for_month(month_idx)
            if not arc:
                continue
            self.log(f"Month {month_idx + 1}/{self.month_count}: {arc['name']}")
            for team in self.story["teams"]:
                project = projects_by_team[team["key"]]
                if self.args.monthly_issue_count and self.args.monthly_issue_count > 0:
                    count = self.args.monthly_issue_count
                else:
                    count = clamp_int(
                        self.rng.gauss(
                            arc["monthly_volume_mean"], arc["monthly_volume_std"]
                        ),
                        2,
                    )
                for item_idx in range(count):
                    issue_number += 1
                    spec = self.make_issue_spec(team, project, month_idx, item_idx, arc)
                    self.seed_issue(spec, issue_number)

    def run(self) -> None:
        self.log(
            "Dry run enabled; no Linear API writes will be made"
            if self.args.dry_run
            else "Writing to Linear"
        )
        self.ensure_structure()
        self.resolve_assignees()
        self.build_cycles()
        self.generate_issues()
        self.manifest["samples"] = self.sample_issues
        manifest_path = Path(self.args.manifest)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(self.serialize_manifest(), handle, indent=2, sort_keys=True)
        self.log(f"Manifest written to {manifest_path}")

    def serialize_manifest(self) -> dict[str, Any]:
        def convert(value: Any) -> Any:
            if isinstance(value, defaultdict):
                return {k: convert(v) for k, v in value.items()}
            if isinstance(value, dict):
                return {k: convert(v) for k, v in value.items()}
            return value

        return convert(self.manifest)


def default_story_path() -> Path:
    return Path(__file__).with_name("story_map.yaml")


def default_manifest_path() -> Path:
    return Path(__file__).resolve().parents[1] / "out" / "manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", default=str(default_story_path()))
    parser.add_argument("--manifest", default=str(default_manifest_path()))
    parser.add_argument("--seed", default="dev-health-linear-demo")
    parser.add_argument("--assignees", default="")
    parser.add_argument(
        "--batch-size", "--batch_size", dest="batch_size", type=int, default=25
    )
    parser.add_argument("--start-date", "--start_date", dest="start_date", default=None)
    parser.add_argument("--end-date", "--end_date", dest="end_date", default=None)
    parser.add_argument(
        "--monthly-issue-count",
        "--monthly_issue_count",
        dest="monthly_issue_count",
        type=int,
        default=None,
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--disable-cycles", action="store_true")
    parser.add_argument("--disable-comments", action="store_true")
    args = parser.parse_args()
    args.enable_cycles = not args.disable_cycles
    args.enable_comments = not args.disable_comments
    args.linear_api_key = os.environ.get("LINEAR_API_KEY")
    if not args.dry_run and not args.linear_api_key:
        raise ValueError("LINEAR_API_KEY environment variable is required")
    return args


if __name__ == "__main__":
    LinearSeeder(parse_args()).run()
