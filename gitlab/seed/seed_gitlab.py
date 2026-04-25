#!/usr/bin/env python3
"""GitLab seeder for deterministic Developer Health fixture data."""

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
from urllib.parse import quote

import yaml


THEMES = {
    "Feature Delivery",
    "Operational / Support",
    "Maintenance / Tech Debt",
    "Quality / Reliability",
    "Risk / Security",
}

CI_CONFIG = """stages:\n  - build\n  - test\n  - security\n  - deploy\n\n.seeded-job:\n  image: alpine:3.20\n  script:\n    - echo \"seeded $CI_JOB_STAGE job for Developer Health fixtures\"\n    - if [ \"$FAIL_STAGE\" = \"$CI_JOB_STAGE\" ]; then exit 1; fi\n\nbuild:compile:\n  extends: .seeded-job\n  stage: build\n\ntest:unit:\n  extends: .seeded-job\n  stage: test\n\nsecurity:scan:\n  extends: .seeded-job\n  stage: security\n\ndeploy:review:\n  extends: .seeded-job\n  stage: deploy\n"""


def stable_hash(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def stable_int(value: str, modulo: int = 900_000) -> int:
    return int(stable_hash(value, 8), 16) % modulo + 1000


def utcnow_naive() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


def slug(value: str) -> str:
    cleaned = value.lower().replace("/", "-").replace(" ", "-")
    return "-".join(part for part in cleaned.split("-") if part)


def month_key(value: dt.datetime) -> str:
    return value.strftime("%Y-%m")


def parse_iso_date(value: str, label: str) -> dt.datetime:
    cleaned = value.rstrip("Z")
    try:
        parsed = dt.datetime.fromisoformat(cleaned)
    except ValueError as exc:
        msg = f"--{label} must be ISO-8601, e.g. 2024-01-31"
        raise ValueError(msg) from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(dt.UTC).replace(tzinfo=None)
    return parsed


def pick_weighted(rng: random.Random, weights: dict[str, float]) -> str:
    keys = list(weights.keys())
    vals = list(weights.values())
    return rng.choices(keys, weights=vals, k=1)[0]


def as_plain_dict(value):
    if isinstance(value, defaultdict):
        return {key: as_plain_dict(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {key: as_plain_dict(item) for key, item in value.items()}
    if isinstance(value, list):
        return [as_plain_dict(item) for item in value]
    return value


class GitLabClient:
    """Small GitLab REST + GraphQL API wrapper.

    Dry-run mode never performs network calls. Write calls in real mode are retried
    to tolerate transient rate-limit and gateway failures.
    """

    def __init__(self, base_url: str, token: str | None, dry_run: bool = False):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.dry_run = dry_run

    def log(self, message: str) -> None:
        print(f"[GitLabSeeder] {message}")

    @property
    def web_url(self) -> str:
        if self.base_url.endswith("/api/v4"):
            return self.base_url[: -len("/api/v4")]
        return self.base_url

    def request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        params: dict | None = None,
    ):
        if self.dry_run:
            self.log(f"DRY {method} {endpoint}")
            return None

        import requests

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "PRIVATE-TOKEN": self.token or "",
        }
        url = f"{self.base_url}{endpoint}"
        for attempt in range(3):
            try:
                response = requests.request(
                    method,
                    url,
                    json=data,
                    params=params,
                    headers=headers,
                    timeout=40,
                )
            except requests.RequestException as exc:
                self.log(f"Exception on {method} {endpoint}: {exc}")
                time.sleep(2**attempt)
                continue

            if response.status_code in {200, 201, 202, 204}:
                return response.json() if response.content else {}
            if response.status_code == 404 and method == "GET":
                return None
            self.log(
                f"Error {response.status_code} on {method} {endpoint} "
                f"(attempt {attempt + 1}/3): {response.text[:300]}"
            )
            if response.status_code not in {409, 429, 500, 502, 503, 504}:
                break
            time.sleep(2**attempt)
        return None

    def graphql(self, query: str, variables: dict | None = None):
        if self.dry_run:
            self.log("DRY POST /graphql")
            return None
        return self.request(
            "POST",
            "/graphql",
            data={"query": query, "variables": variables or {}},
        )


class GitLabSeeder:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        with Path(args.story).open(encoding="utf-8") as handle:
            self.story = yaml.safe_load(handle)
        self.validate_story()

        self.start_date, self.end_date, self.month_count = self.resolve_date_range()
        seed_input = f"{self.story.get('org_slug', 'org')}::{args.seed}"
        seed_hash = int(hashlib.sha256(seed_input.encode("utf-8")).hexdigest(), 16)
        self.rng = random.Random(seed_hash)  # nosec B311 - deterministic fixtures
        self.client = GitLabClient(args.base_url, args.token, args.dry_run)

        self.group: dict = {}
        self.projects: dict[str, dict] = {}
        self.existing_labels: dict[str, set[str]] = defaultdict(set)
        self.reviewers: list[int] = []
        self.team_primary_project = {
            team["id"]: team["primary_project"] for team in self.story.get("teams", [])
        }
        self.shared_team_by_project: dict[str, list[str]] = defaultdict(list)
        for team in self.story.get("teams", []):
            shared_project = team.get("shared_project")
            if shared_project:
                self.shared_team_by_project[shared_project].append(team["id"])

        self.manifest = {
            "meta": {
                "generated_at": dt.datetime.now(dt.UTC).isoformat(),
                "seed": args.seed,
                "months": self.month_count,
                "dry_run": args.dry_run,
                "base_url": args.base_url,
                "group_path": args.group_path,
            },
            "counts": {
                "by_project": defaultdict(lambda: defaultdict(int)),
                "by_team": defaultdict(lambda: defaultdict(int)),
                "by_month": defaultdict(lambda: defaultdict(int)),
                "by_theme": defaultdict(int),
            },
            "merge_requests": {"created": 0, "merged": 0, "closed": 0},
            "pipelines": {
                "created": 0,
                "by_arc": defaultdict(lambda: defaultdict(int)),
                "failure_stage": defaultdict(int),
                "jobs": defaultdict(lambda: defaultdict(int)),
            },
            "releases": {"created": 0, "by_project": defaultdict(int)},
            "comments": {"issues": 0, "merge_requests": 0},
            "graphql": {"project_lookups": 0},
        }

    def validate_story(self) -> None:
        configured = set(self.story.get("canonical_themes", []))
        if configured != THEMES:
            missing = sorted(THEMES - configured)
            extra = sorted(configured - THEMES)
            raise ValueError(
                "story_map.yaml canonical_themes must exactly match Investment View "
                f"themes; missing={missing}, extra={extra}"
            )
        for arc in self.story.get("arcs", []):
            arc_themes = set(arc.get("investment_theme_mix", {}))
            if arc_themes != THEMES:
                raise ValueError(f"Arc {arc['name']} has invalid theme mix keys")

    def resolve_date_range(self) -> tuple[dt.datetime, dt.datetime, int]:
        if self.args.start_date:
            start = parse_iso_date(self.args.start_date, "start-date")
            end = (
                parse_iso_date(self.args.end_date, "end-date")
                if self.args.end_date
                else utcnow_naive()
            )
            if end < start:
                raise ValueError("--end-date must be later than --start-date")
            month_count = max(1, int(round((end - start).days / 30.0)))
            return start, end, month_count
        if self.args.end_date:
            raise ValueError("--start-date is required when --end-date is provided")
        end = utcnow_naive()
        return end - dt.timedelta(days=730), end, 24

    def log(self, message: str) -> None:
        self.client.log(message)

    def encoded_project(self, project: dict) -> str:
        return quote(project["path_with_namespace"], safe="")

    def ensure_group(self) -> dict:
        if self.args.dry_run:
            self.group = {
                "id": stable_int(self.args.group_path),
                "full_path": self.args.group_path,
                "name": self.args.group_path,
            }
            return self.group
        endpoint = f"/groups/{quote(self.args.group_path, safe='')}"
        group = self.client.request("GET", endpoint)
        if group:
            self.group = group
            return group
        path = self.args.group_path.split("/")[-1]
        group = self.client.request(
            "POST",
            "/groups",
            data={"name": path.replace("-", " ").title(), "path": path},
        )
        if not group:
            raise RuntimeError(
                f"Unable to create or fetch GitLab group {self.args.group_path}"
            )
        self.group = group
        return group

    def graphql_project(self, full_path: str) -> dict | None:
        query = """
        query ProjectSeedLookup($fullPath: ID!) {
          project(fullPath: $fullPath) {
            id
            fullPath
            repository { rootRef }
          }
        }
        """
        result = self.client.graphql(query, {"fullPath": full_path})
        self.manifest["graphql"]["project_lookups"] += 1
        if not result:
            return None
        return result.get("data", {}).get("project")

    def ensure_project(self, project_spec: dict) -> dict:
        full_path = f"{self.args.group_path}/{project_spec['path']}"
        if self.args.dry_run:
            project = {
                "id": stable_int(full_path),
                "path": project_spec["path"],
                "name": project_spec["name"],
                "path_with_namespace": full_path,
                "default_branch": "main",
                "graphql": {"id": f"gid://gitlab/Project/{stable_int(full_path)}"},
            }
            self.projects[project_spec["path"]] = project
            return project

        encoded = quote(full_path, safe="")
        project = self.client.request("GET", f"/projects/{encoded}")
        if not project:
            project = self.client.request(
                "POST",
                "/projects",
                data={
                    "name": project_spec["name"],
                    "path": project_spec["path"],
                    "namespace_id": self.group["id"],
                    "initialize_with_readme": True,
                    "visibility": "private",
                },
            )
        if not project:
            raise RuntimeError(f"Unable to create or fetch project {full_path}")
        project["graphql"] = self.graphql_project(full_path) or {}
        self.projects[project_spec["path"]] = project
        return project

    def ensure_repository_seed_files(self, project: dict) -> None:
        if self.args.dry_run:
            return
        project_id = self.encoded_project(project)
        self.ensure_file(
            project_id,
            ".gitlab-ci.yml",
            CI_CONFIG,
            "seed: add deterministic fixture pipeline config",
        )
        self.ensure_file(
            project_id,
            "README.md",
            "# Seeded Dev Health Project\n\nGenerated by gitlab/seed/seed_gitlab.py.\n",
            "seed: add fixture project readme",
        )

    def ensure_file(
        self, project_id: str, file_path: str, content: str, commit_message: str
    ) -> None:
        encoded_file = quote(file_path, safe="")
        exists = self.client.request(
            "GET",
            f"/projects/{project_id}/repository/files/{encoded_file}",
            params={"ref": "main"},
        )
        method = "PUT" if exists else "POST"
        self.client.request(
            method,
            f"/projects/{project_id}/repository/files/{encoded_file}",
            data={
                "branch": "main",
                "content": content,
                "commit_message": commit_message,
            },
        )

    def resolve_reviewers(self) -> None:
        usernames = [
            item.strip() for item in self.args.reviewers.split(",") if item.strip()
        ]
        if not usernames or self.args.dry_run:
            self.reviewers = [stable_int(name, 100_000) for name in usernames]
            return
        for username in usernames:
            users = self.client.request("GET", "/users", params={"username": username})
            if users:
                self.reviewers.append(users[0]["id"])
        self.log(f"Resolved {len(self.reviewers)} GitLab reviewers")

    def prefetch_existing(self, project: dict) -> None:
        if self.args.dry_run:
            return
        project_id = self.encoded_project(project)
        page = 1
        labels: set[str] = set()
        while True:
            issues = self.client.request(
                "GET",
                f"/projects/{project_id}/issues",
                params={"labels": "seeded", "per_page": 100, "page": page},
            )
            if not issues:
                break
            for issue in issues:
                for label in issue.get("labels", []) or []:
                    if label.startswith("extid::"):
                        labels.add(label)
            if len(issues) < 100:
                break
            page += 1
        self.existing_labels[project["path"]] = labels
        if labels:
            self.log(f"Found {len(labels)} existing seeded issues in {project['path']}")

    def record_issue(
        self,
        project_path: str,
        team_id: str,
        month: dt.datetime,
        issue_type: str,
        theme: str,
    ) -> None:
        self.manifest["counts"]["by_project"][project_path][issue_type] += 1
        self.manifest["counts"]["by_team"][team_id][issue_type] += 1
        self.manifest["counts"]["by_month"][month_key(month)][issue_type] += 1
        self.manifest["counts"]["by_theme"][theme] += 1

    def build_labels(
        self,
        external_id: str,
        team_id: str,
        issue_type: str,
        theme: str,
        service: str,
        arc_name: str,
    ) -> list[str]:
        return [
            "seeded",
            f"extid::{external_id}",
            f"team::{team_id}",
            f"issue_type::{issue_type}",
            f"theme::{theme}",
            f"service::{service}",
            f"story_arc::{slug(arc_name)}",
            "refs::CHAOS-246",
        ]

    def create_issue(self, project: dict, spec: dict) -> dict:
        project_path = project["path"]
        ext_label = f"extid::{spec['external_id']}"
        if ext_label in self.existing_labels[project_path]:
            return {"iid": stable_int(spec["external_id"], 50_000), "skipped": True}
        if self.args.dry_run:
            self.existing_labels[project_path].add(ext_label)
            return {"iid": stable_int(spec["external_id"], 50_000), "dry_run": True}

        payload = {
            "title": spec["title"],
            "description": spec["description"],
            "labels": ",".join(spec["labels"]),
            "created_at": spec["created_at"].isoformat() + "Z",
        }
        issue = self.client.request(
            "POST", f"/projects/{self.encoded_project(project)}/issues", data=payload
        )
        if issue:
            self.existing_labels[project_path].add(ext_label)
            if self.args.enable_comments and self.rng.random() < spec["comment_rate"]:
                self.add_issue_note(project, issue["iid"], spec["arc_name"])
        return issue or {"iid": stable_int(spec["external_id"], 50_000), "error": True}

    def add_issue_note(self, project: dict, issue_iid: int, arc_name: str) -> None:
        body = f"Seeder note: work progressed during the {arc_name} arc."
        if not self.args.dry_run:
            self.client.request(
                "POST",
                f"/projects/{self.encoded_project(project)}/issues/{issue_iid}/notes",
                data={"body": body},
            )
        self.manifest["comments"]["issues"] += 1

    def create_branch_and_commit(self, project: dict, branch: str, spec: dict) -> None:
        if self.args.dry_run:
            return
        project_id = self.encoded_project(project)
        branch_data = self.client.request(
            "GET",
            f"/projects/{project_id}/repository/branches/{quote(branch, safe='')}",
        )
        if not branch_data:
            self.client.request(
                "POST",
                f"/projects/{project_id}/repository/branches",
                data={"branch": branch, "ref": project.get("default_branch") or "main"},
            )
        content = (
            f"# {spec['title']}\n\n"
            f"- external_id: {spec['external_id']}\n"
            f"- theme: {spec['theme']}\n"
            f"- arc: {spec['arc_name']}\n"
        )
        self.client.request(
            "POST",
            f"/projects/{project_id}/repository/commits",
            data={
                "branch": branch,
                "commit_message": f"seed: fixture change for {spec['external_id']}",
                "actions": [
                    {
                        "action": "create",
                        "file_path": f"fixtures/{spec['external_id']}.md",
                        "content": content,
                    }
                ],
            },
        )

    def create_merge_request(
        self, project: dict, issue: dict, spec: dict, arc: dict
    ) -> None:
        branch = f"seed/chaos-246/{spec['external_id']}"
        self.create_branch_and_commit(project, branch, spec)
        reviewers = self.pick_reviewers(arc)
        state = (
            "merged"
            if self.rng.random() < arc["review_profile"]["merge_rate"]
            else "closed"
        )
        self.manifest["merge_requests"]["created"] += 1
        self.manifest["merge_requests"][state] += 1

        if self.args.dry_run:
            mr = {"iid": stable_int(f"mr-{spec['external_id']}", 50_000)}
        else:
            payload = {
                "source_branch": branch,
                "target_branch": project.get("default_branch") or "main",
                "title": f"{spec['title']} (!seed)",
                "description": spec["description"],
                "labels": ",".join(spec["labels"]),
                "remove_source_branch": True,
            }
            if reviewers:
                payload["reviewer_ids"] = reviewers
            mr = self.client.request(
                "POST",
                f"/projects/{self.encoded_project(project)}/merge_requests",
                data=payload,
            ) or {"iid": stable_int(f"mr-{spec['external_id']}", 50_000)}
            if state == "closed" and mr.get("iid"):
                self.client.request(
                    "PUT",
                    f"/projects/{self.encoded_project(project)}/merge_requests/{mr['iid']}",
                    data={"state_event": "close"},
                )

        if (
            self.args.enable_comments
            and self.rng.random() < arc["review_profile"]["comment_rate"]
        ):
            self.add_merge_request_note(project, mr["iid"], spec["arc_name"])
        if self.args.enable_pipelines:
            self.create_pipeline(project, branch, spec, arc)

    def pick_reviewers(self, arc: dict) -> list[int]:
        if not self.reviewers:
            return []
        mean = arc["review_profile"].get("reviewer_count_mean", 1.0)
        count = max(1, min(len(self.reviewers), round(self.rng.gauss(mean, 0.5))))
        shuffled = self.reviewers[:]
        self.rng.shuffle(shuffled)
        return shuffled[:count]

    def add_merge_request_note(self, project: dict, mr_iid: int, arc_name: str) -> None:
        body = f"Seeder review note: changes were discussed during {arc_name}."
        if not self.args.dry_run:
            self.client.request(
                "POST",
                f"/projects/{self.encoded_project(project)}/merge_requests/{mr_iid}/notes",
                data={"body": body},
            )
        self.manifest["comments"]["merge_requests"] += 1

    def create_pipeline(self, project: dict, ref: str, spec: dict, arc: dict) -> None:
        success = self.rng.random() < arc["pipeline_success_rate"]
        fail_stage = ""
        status = "success"
        if not success:
            fail_stage = pick_weighted(self.rng, arc["pipeline_failure_stage_mix"])
            status = "failed"
            self.manifest["pipelines"]["failure_stage"][fail_stage] += 1

        for stage in ["build", "test", "security", "deploy"]:
            job_status = "failed" if stage == fail_stage else "success"
            self.manifest["pipelines"]["jobs"][stage][job_status] += 1
        self.manifest["pipelines"]["created"] += 1
        self.manifest["pipelines"]["by_arc"][spec["arc_name"]][status] += 1

        if self.args.dry_run:
            return
        self.client.request(
            "POST",
            f"/projects/{self.encoded_project(project)}/pipeline",
            data={
                "ref": ref,
                "variables": [
                    {"key": "SEED_EXTERNAL_ID", "value": spec["external_id"]},
                    {"key": "SEED_THEME", "value": spec["theme"]},
                    {"key": "FAIL_STAGE", "value": fail_stage},
                ],
            },
        )

    def create_release(self, project: dict, month_idx: int, arc: dict) -> None:
        tag_name = f"seed-v{month_idx + 1}-{slug(arc['name'])}"
        self.manifest["releases"]["created"] += 1
        self.manifest["releases"]["by_project"][project["path"]] += 1
        if self.args.dry_run:
            return
        project_id = self.encoded_project(project)
        tag = self.client.request(
            "GET", f"/projects/{project_id}/repository/tags/{tag_name}"
        )
        if not tag:
            self.client.request(
                "POST",
                f"/projects/{project_id}/repository/tags",
                data={
                    "tag_name": tag_name,
                    "ref": project.get("default_branch") or "main",
                },
            )
        release = self.client.request(
            "GET", f"/projects/{project_id}/releases/{tag_name}"
        )
        if not release:
            self.client.request(
                "POST",
                f"/projects/{project_id}/releases",
                data={
                    "name": f"Seeded {arc['name']} release {month_idx + 1}",
                    "tag_name": tag_name,
                    "description": "Seeded release for Developer Health demo data.",
                },
            )

    def build_issue_spec(
        self, project_spec: dict, project: dict, month_idx: int, arc: dict, idx: int
    ) -> dict:
        issue_type = pick_weighted(self.rng, arc["issue_type_mix"])
        theme = pick_weighted(self.rng, arc["investment_theme_mix"])
        service = self.rng.choice(self.story["services"])
        team_id = project_spec["team_id"]
        shared_candidates = self.shared_team_by_project.get(project_spec["path"], [])
        if shared_candidates and self.rng.random() < 0.12:
            team_id = self.rng.choice(shared_candidates)

        created_at = self.start_date + dt.timedelta(
            days=month_idx * 30 + self.rng.randint(0, 28)
        )
        external_id = stable_hash(
            f"{project_spec['path']}-{month_idx}-{idx}-{issue_type}-{theme}"
        )
        labels = self.build_labels(
            external_id, team_id, issue_type, theme, service, arc["name"]
        )
        title = f"{issue_type.title()} work in {project_spec['name']}"
        description = (
            f"Seeded GitLab {issue_type} for {project['path_with_namespace']}.\n\n"
            f"Theme: {theme}\nService: {service}\nArc: {arc['name']}\n"
            f"External ID: {external_id}\nRefs CHAOS-246"
        )
        self.record_issue(project_spec["path"], team_id, created_at, issue_type, theme)
        return {
            "external_id": external_id,
            "title": title,
            "description": description,
            "labels": labels,
            "created_at": created_at,
            "issue_type": issue_type,
            "theme": theme,
            "service": service,
            "team_id": team_id,
            "arc_name": arc["name"],
            "comment_rate": arc["review_profile"]["comment_rate"],
        }

    def generate_month(
        self, project_spec: dict, project: dict, month_idx: int, arc: dict
    ) -> None:
        if self.args.monthly_issue_count and self.args.monthly_issue_count > 0:
            issue_count = self.args.monthly_issue_count
        else:
            mean = arc["monthly_issue_mean"]
            std = arc["monthly_issue_std"]
            issue_count = max(2, int(self.rng.gauss(mean, std)))

        for idx in range(issue_count):
            spec = self.build_issue_spec(project_spec, project, month_idx, arc, idx)
            issue = self.create_issue(project, spec)
            if self.args.enable_merge_requests and self.rng.random() < arc["mr_ratio"]:
                self.create_merge_request(project, issue, spec, arc)

        interval = max(1, int(arc.get("release_interval_months", 2)))
        if self.args.enable_releases and month_idx % interval == 0:
            self.create_release(project, month_idx, arc)

    def run(self) -> None:
        self.ensure_group()
        self.resolve_reviewers()
        for project_spec in self.story["projects"]:
            project = self.ensure_project(project_spec)
            self.prefetch_existing(project)
            self.ensure_repository_seed_files(project)

        arcs = self.story["arcs"]
        for month_idx in range(self.month_count):
            arc = next(
                (
                    item
                    for item in arcs
                    if item["start_month"] <= month_idx <= item["end_month"]
                ),
                None,
            )
            if not arc:
                continue
            self.log(f"Month {month_idx}: {arc['name']}")
            for project_spec in self.story["projects"]:
                project = self.projects[project_spec["path"]]
                self.generate_month(project_spec, project, month_idx, arc)

        manifest_path = Path(self.args.manifest)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(as_plain_dict(self.manifest), handle, indent=2, sort_keys=True)
        self.log(f"Manifest written to {manifest_path}")


def parse_args() -> argparse.Namespace:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default=os.environ.get("GITLAB_BASE_URL", "https://gitlab.com/api/v4"),
    )
    parser.add_argument(
        "--group-path", default=os.environ.get("GITLAB_GROUP_PATH", "dev-health-demo")
    )
    parser.add_argument("--story", default=str(base_dir / "story_map.yaml"))
    parser.add_argument(
        "--manifest", default=str(base_dir.parent / "out" / "manifest.json")
    )
    parser.add_argument(
        "--seed", default=os.environ.get("GITLAB_SEED", "dev-health-demo")
    )
    parser.add_argument("--reviewers", default=os.environ.get("GITLAB_REVIEWERS", ""))
    parser.add_argument(
        "--batch-size", "--batch_size", dest="batch_size", type=int, default=50
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
    parser.add_argument("--enable-comments", action="store_true")
    parser.add_argument("--disable-pipelines", action="store_true")
    parser.add_argument("--disable-merge-requests", action="store_true")
    parser.add_argument("--disable-releases", action="store_true")
    args = parser.parse_args()

    args.token = os.environ.get("GITLAB_TOKEN")
    if not args.dry_run and not args.token:
        raise ValueError(
            "GITLAB_TOKEN environment variable is required outside dry-run"
        )
    args.enable_pipelines = not args.disable_pipelines
    args.enable_merge_requests = not args.disable_merge_requests
    args.enable_releases = not args.disable_releases
    return args


if __name__ == "__main__":
    GitLabSeeder(parse_args()).run()
