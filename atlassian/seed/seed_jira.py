import argparse
import datetime
import hashlib
import json
import os
import random
import time
from collections import defaultdict

import yaml


class JiraClient:
    """
    A wrapper for Jira Cloud REST API interactions.
    
    Note on dry_run behavior:
    - When dry_run=True, write operations (POST, PUT) return stubbed responses.
    - Read operations (GET) still execute to validate connectivity and fetch metadata
      like issue types, boards, and transitions.
    """
    def __init__(self, url, user, token, dry_run=False):
        self.url = url.rstrip("/")
        self.user = user
        self.token = token
        self.dry_run = dry_run
        self._issue_types = None

    def log(self, msg):
        print(f"[Seeder] {msg}")

    def api_request(self, method, endpoint, data=None, params=None):
        if self.dry_run:
            return {}

        import requests
        from requests.auth import HTTPBasicAuth

        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        url = f"{self.url}{endpoint}"

        for attempt in range(3):
            try:
                resp = requests.request(
                    method,
                    url,
                    data=json.dumps(data) if data else None,
                    params=params,
                    headers=headers,
                    auth=HTTPBasicAuth(self.user, self.token),
                    # Timeout increased from 30s to 40s to accommodate slower Jira Cloud API responses
                    timeout=40,
                )
                if resp.status_code in [200, 201, 204]:
                    return resp.json() if resp.content else {}
                self.log(
                    f"Error {resp.status_code} on {method} {endpoint} (attempt {attempt + 1}/3): {resp.text}"
                )
            except requests.RequestException as exc:
                self.log(f"Exception (attempt {attempt + 1}/3): {exc}")

            time.sleep(1)

        return None

    def get_issue_types(self):
        if self._issue_types is None:
            data = self.api_request("GET", "/rest/api/3/issuetype")
            if data is None:
                self._issue_types = []
            else:
                self._issue_types = [i.get("name") for i in data if i.get("name")]
        return self._issue_types

    def search(self, jql, fields=None, max_results=100, start_at=0):
        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": ",".join(fields or ["labels"]),
        }
        return self.api_request("GET", "/rest/api/3/search", params=params)

    def create_issue(self, payload):
        return self.api_request("POST", "/rest/api/3/issue", payload)

    def create_issues_bulk(self, payloads):
        if self.dry_run:
            return {"issues": [{"id": f"dry-{i}", "key": f"DRY-{i}"} for i in range(len(payloads))]}
        return self.api_request("POST", "/rest/api/3/issue/bulk", {"issueUpdates": payloads})

    def set_issue_property(self, issue_id_or_key, property_key, value):
        return self.api_request(
            "PUT",
            f"/rest/api/3/issue/{issue_id_or_key}/properties/{property_key}",
            value,
        )

    def add_comment(self, issue_key, body):
        return self.api_request("POST", f"/rest/api/3/issue/{issue_key}/comment", {"body": body})

    def transition_issue(self, issue_key, transition_id):
        payload = {"transition": {"id": transition_id}}
        return self.api_request(
            "POST", f"/rest/api/3/issue/{issue_key}/transitions", payload
        )

    def get_transitions(self, issue_key):
        return self.api_request(
            "GET", f"/rest/api/3/issue/{issue_key}/transitions"
        )

    def create_issue_link(self, link_type, inward_key, outward_key):
        payload = {
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_key},
            "outwardIssue": {"key": outward_key},
        }
        return self.api_request("POST", "/rest/api/3/issueLink", payload)

    def create_board(self, name, project_key):
        payload = {
            "name": name,
            "type": "scrum",
            "filterId": None,
            "location": {"type": "project", "projectKeyOrId": project_key},
        }
        return self.api_request("POST", "/rest/agile/1.0/board", payload)

    def get_boards(self, project_key):
        return self.api_request(
            "GET", "/rest/agile/1.0/board", params={"projectKeyOrId": project_key}
        )

    def create_sprint(self, name, board_id, start_date, end_date):
        payload = {
            "name": name,
            "originBoardId": board_id,
            "startDate": start_date,
            "endDate": end_date,
            "state": "closed",
        }
        return self.api_request("POST", "/rest/agile/1.0/sprint", payload)

    def add_issues_to_sprint(self, sprint_id, issue_keys):
        payload = {"issues": issue_keys}
        return self.api_request(
            "POST", f"/rest/agile/1.0/sprint/{sprint_id}/issue", payload
        )


def adf_text(text):
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


def stable_hash(value, length=12):
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return digest[:length]


def month_key(dt):
    return dt.strftime("%Y-%m")


def pick_weighted(rng, weights):
    keys = list(weights.keys())
    vals = list(weights.values())
    return rng.choices(keys, weights=vals, k=1)[0]


def clamp_int(value, minimum=1):
    return max(minimum, int(value))


def dwell_bucket(days):
    if days <= 1:
        return "0-1d"
    if days <= 3:
        return "1-3d"
    if days <= 7:
        return "3-7d"
    if days <= 14:
        return "7-14d"
    return "14d+"


class JiraSeeder:
    def __init__(self, args):
        self.args = args
        with open(args.story, "r") as handle:
            self.story = yaml.safe_load(handle)

        self.start_date, self.end_date, self.month_count = self.resolve_date_range()
        seed_input = f"{self.story.get('org_slug', 'org')}::{args.seed}"
        seed_hash = int(hashlib.sha256(seed_input.encode("utf-8")).hexdigest(), 16)
        self.rng = random.Random(seed_hash)

        self.client = JiraClient(args.url, args.user, args.token, dry_run=args.dry_run)
        self.issue_types = set(self.client.get_issue_types())

        self.existing_ids = defaultdict(set)
        self.assignees = []

        self.manifest = {
            "meta": {
                "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
                "seed": args.seed,
                "months": self.month_count,
            },
            "counts": {
                "by_project": defaultdict(lambda: defaultdict(int)),
                "by_team": defaultdict(lambda: defaultdict(int)),
                "by_month": defaultdict(lambda: defaultdict(int)),
            },
            "incidents": {"severity_by_month": defaultdict(lambda: defaultdict(int))},
            "dwell": {"histogram": defaultdict(lambda: defaultdict(int))},
            "hotspots": {"service_counts": defaultdict(int)},
            "dependencies": {"cross_project_epics": 0},
        }

        self.created_issues = []
        self.epic_keys = defaultdict(list)
        self.initiative_keys = defaultdict(list)
        self.incident_keys = []
        self.issue_key_by_external_id = {}
        self.issues_by_project_month = defaultdict(lambda: defaultdict(list))
        self.followup_specs = []
        self.sprints_by_project = {}
        self.team_primary_project = {
            t["id"]: t["primary_project"] for t in self.story.get("teams", [])
        }
        self.shared_team_by_project = defaultdict(list)
        for team in self.story.get("teams", []):
            shared_project = team.get("shared_project")
            if shared_project:
                self.shared_team_by_project[shared_project].append(team["id"])

    def resolve_date_range(self):
        if self.args.start_date:
            start = self.parse_iso_date(self.args.start_date, "start-date")
            if self.args.end_date:
                end = self.parse_iso_date(self.args.end_date, "end-date")
            else:
                end = datetime.datetime.utcnow()
            if end <= start:
                raise ValueError("--end-date must be later than --start-date.")
            total_days = (end - start).days
            month_count = max(1, int(round(total_days / 30.0)))
            return start, end, month_count

        if self.args.end_date:
            raise ValueError("--start-date is required when --end-date is provided.")

        end = datetime.datetime.utcnow()
        start = end - datetime.timedelta(days=730)
        return start, end, 24

    def parse_iso_date(self, value, label):
        cleaned = value.rstrip("Z")
        try:
            dt = datetime.datetime.fromisoformat(cleaned)
        except ValueError as exc:
            raise ValueError(f"--{label} must be ISO-8601 (e.g. 2023-01-31).") from exc
        if dt.tzinfo:
            dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return dt

    def log(self, msg):
        self.client.log(msg)

    def resolve_assignees(self):
        if not self.args.assignees:
            return
        emails = [e.strip() for e in self.args.assignees.split(",") if e.strip()]
        if not emails:
            return
        self.log(f"Resolving {len(emails)} assignees...")
        for email in emails:
            data = self.client.api_request(
                "GET", f"/rest/api/3/user/search?query={email}"
            )
            if data and isinstance(data, list):
                acc_id = data[0].get("accountId")
                if acc_id:
                    self.assignees.append(acc_id)
        self.log(f"Resolved {len(self.assignees)} assignees")

    def prefetch_existing(self, project_key):
        start_at = 0
        found = set()
        while True:
            data = self.client.search(
                f'project = {project_key} AND labels = "seeded"',
                fields=["labels"],
                max_results=100,
                start_at=start_at,
            )
            if not data or "issues" not in data:
                break
            issues = data.get("issues", [])
            for issue in issues:
                labels = issue.get("fields", {}).get("labels", []) or []
                for label in labels:
                    if label.startswith("extid-"):
                        found.add(label)
            if start_at + 100 >= data.get("total", 0):
                break
            start_at += 100
        self.existing_ids[project_key] = found
        if found:
            self.log(f"Found {len(found)} existing seeded issues in {project_key}")

    def ensure_issue_type(self, desired):
        if desired in self.issue_types:
            return desired
        fallback = "Task" if "Task" in self.issue_types else "Story"
        self.log(f"Issue type {desired} not found, using {fallback}")
        return fallback

    def make_labels(self, external_id, team_id, work_type, investment, service, story_arc, severity=None):
        labels = [
            "seeded",
            f"extid-{external_id}",
            f"team:{team_id}",
            f"work_type:{work_type}",
            f"investment:{investment}",
            f"service:{service}",
            f"story_arc:{story_arc}",
        ]
        if severity:
            labels.append(f"severity:{severity}")
        return labels

    def record_manifest(self, project_key, team_id, issue_type, created_at, service, severity=None):
        month = month_key(created_at)
        self.manifest["counts"]["by_project"][project_key][issue_type] += 1
        self.manifest["counts"]["by_team"][team_id][issue_type] += 1
        self.manifest["counts"]["by_month"][month][issue_type] += 1
        if severity:
            self.manifest["incidents"]["severity_by_month"][month][severity] += 1
        self.manifest["hotspots"]["service_counts"][service] += 1

    def record_dwell(self, state, days):
        bucket = dwell_bucket(days)
        self.manifest["dwell"]["histogram"][state][bucket] += 1

    def simulate_dwell(self, arc):
        review_days = max(0.5, self.rng.gauss(arc["dwell_profile"]["review_days_mean"], 0.8))
        blocked_days = max(0.2, self.rng.gauss(arc["dwell_profile"]["blocked_days_mean"], 0.5))
        progress_days = max(0.5, self.rng.gauss(2.0, 1.0))
        self.record_dwell("In Progress", progress_days)
        self.record_dwell("In Review", review_days)
        if blocked_days > 0.6:
            self.record_dwell("Blocked", blocked_days)

    def maybe_assign(self, fields):
        if self.assignees and self.rng.random() > 0.1:
            fields["assignee"] = {"id": self.rng.choice(self.assignees)}

    def build_issue_payload(self, project_key, issue_type, summary, description, labels):
        fields = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
            "description": adf_text(description),
            "labels": labels,
        }
        self.maybe_assign(fields)
        return {"fields": fields}

    def create_issues(self, payloads):
        if not payloads:
            return []
        response = self.client.create_issues_bulk(payloads)
        issues = response.get("issues", []) if response else []
        created = []
        for payload, issue in zip(payloads, issues):
            key = issue.get("key")
            if key:
                created.append({"key": key, "fields": payload.get("fields", {})})
        return created

    def apply_transitions(self, issue_key, target_status):
        if not self.args.enable_transitions:
            return
        transitions = self.client.get_transitions(issue_key)
        if not transitions:
            return
        desired = None
        for t in transitions.get("transitions", []):
            if t.get("to", {}).get("name", "").lower() == target_status.lower():
                desired = t
                break
        if desired:
            self.client.transition_issue(issue_key, desired.get("id"))

    def maybe_comment(self, issue_key, arc_name):
        if not self.args.enable_comments:
            return
        if self.rng.random() > 0.25:
            return
        body = adf_text(f"Seeder note: progress update during {arc_name} phase.")
        self.client.add_comment(issue_key, body)

    def ensure_epics_and_initiatives(self, project_key, team_id):
        epics = []
        initiatives = []
        for year in range(2):
            for idx in range(2):
                seed = f"{project_key}-init-{year}-{idx}"
                ext = stable_hash(seed)
                label = f"extid-{ext}"
                issue_type = self.ensure_issue_type("Initiative")
                manifest_type = "Initiative"
                month_idx = year * 12 + self.rng.randint(0, 11)
                created_at = self.start_date + datetime.timedelta(
                    days=month_idx * 30 + self.rng.randint(0, 28)
                )
                self.record_manifest(
                    project_key, team_id, manifest_type, created_at, "svc-a"
                )
                if label in self.existing_ids[project_key]:
                    continue
                summary = f"Initiative {year + 1}-{idx + 1} for {project_key}"
                labels = self.make_labels(ext, team_id, "feature", "product", "svc-a", "launch")
                payload = self.build_issue_payload(
                    project_key,
                    issue_type,
                    summary,
                    "Seeded initiative for portfolio tracking.",
                    labels,
                )
                issue = self.client.create_issue(payload)
                if issue and issue.get("key"):
                    self.client.set_issue_property(
                        issue.get("key"),
                        "seed_meta",
                        {
                            "external_id": ext,
                            "created_at": created_at.isoformat() + "Z",
                            "team_id": team_id,
                            "issue_type": issue_type,
                            "seed_type": manifest_type,
                            "project_key": project_key,
                            "arc": "Launch",
                            "month_idx": month_idx,
                        },
                    )
                    initiatives.append(issue.get("key"))
                    self.existing_ids[project_key].add(label)
        for quarter in range(8):
            for idx in range(3):
                seed = f"{project_key}-epic-{quarter}-{idx}"
                ext = stable_hash(seed)
                label = f"extid-{ext}"
                issue_type = self.ensure_issue_type("Epic")
                manifest_type = "Epic"
                month_idx = quarter * 3 + self.rng.randint(0, 2)
                created_at = self.start_date + datetime.timedelta(
                    days=month_idx * 30 + self.rng.randint(0, 28)
                )
                self.record_manifest(
                    project_key, team_id, manifest_type, created_at, "svc-b"
                )
                if label in self.existing_ids[project_key]:
                    continue
                summary = f"Epic Q{quarter + 1}-{idx + 1} for {project_key}"
                labels = self.make_labels(ext, team_id, "feature", "product", "svc-b", "launch")
                payload = self.build_issue_payload(
                    project_key,
                    issue_type,
                    summary,
                    "Seeded epic for roadmap structure.",
                    labels,
                )
                issue = self.client.create_issue(payload)
                if issue and issue.get("key"):
                    self.client.set_issue_property(
                        issue.get("key"),
                        "seed_meta",
                        {
                            "external_id": ext,
                            "created_at": created_at.isoformat() + "Z",
                            "team_id": team_id,
                            "issue_type": issue_type,
                            "seed_type": manifest_type,
                            "project_key": project_key,
                            "arc": "Launch",
                            "month_idx": month_idx,
                        },
                    )
                    epics.append(issue.get("key"))
                    self.existing_ids[project_key].add(label)
        self.epic_keys[project_key] = epics
        self.initiative_keys[project_key] = initiatives

    def link_epics_cross_project(self, project_keys):
        all_epics = []
        for key in project_keys:
            for epic_key in self.epic_keys.get(key, []):
                all_epics.append((key, epic_key))
        target_count = int(len(all_epics) * 0.15)
        for _ in range(target_count):
            src = self.rng.choice(all_epics)
            dst = self.rng.choice(all_epics)
            if src[0] == dst[0]:
                continue
            self.client.create_issue_link("Blocks", src[1], dst[1])
            self.manifest["dependencies"]["cross_project_epics"] += 1

    def generate_month_issues(self, project, month_idx, arc):
        project_key = project["key"]
        default_team_id = project["team_id"]
        if self.args.monthly_issue_count is not None:
            base_count = clamp_int(self.args.monthly_issue_count, 1)
        else:
            base_count = clamp_int(self.rng.gauss(arc["monthly_volume_mean"], arc["monthly_volume_std"]), 20)
        incident_count = int(base_count * arc.get("incident_rate", 0)) if self.args.enable_incidents else 0
        work_count = base_count - incident_count

        work_type_mix = arc["issue_type_mix"].copy()
        work_type_mix.pop("incident", None)
        for idx in range(work_count):
            issue_type = pick_weighted(self.rng, work_type_mix)
            work_type = pick_weighted(self.rng, arc["work_type_mix"])
            investment = pick_weighted(self.rng, arc["investment_mix"])
            service = self.rng.choice(self.story["services"])
            story_arc = arc["name"].lower().replace(" ", "-")
            team_id = default_team_id
            shared_candidates = self.shared_team_by_project.get(project_key, [])
            extra_team = None
            if shared_candidates and self.rng.random() < 0.15:
                team_id = self.rng.choice(shared_candidates)
            if issue_type in ["story", "task"] and shared_candidates and self.rng.random() < 0.10:
                extra_team = self.rng.choice(shared_candidates)

            # Calculate created_at using 30-day months (approximation for demo data)
            # This creates some drift over 24 months but is acceptable for synthetic data
            created_at = self.start_date + datetime.timedelta(days=month_idx * 30 + self.rng.randint(0, 28))
            ext_seed = f"{project_key}-{month_idx}-{idx}-{work_type}-{issue_type}"
            external_id = stable_hash(ext_seed)
            label = f"extid-{external_id}"

            summary = f"{work_type.title()} {issue_type.title()} for {project_key}"
            manifest_type = issue_type.title()
            self.record_manifest(project_key, team_id, manifest_type, created_at, service)
            self.simulate_dwell(arc)
            if label in self.existing_ids[project_key]:
                continue
            issue_type_name = self.ensure_issue_type(issue_type.title())
            severity = None
            if issue_type == "bug":
                severity = self.rng.choice(["sev1", "sev2", "sev3", "sev4"])
            labels = self.make_labels(
                external_id, team_id, work_type, investment, service, story_arc, severity=severity
            )
            if extra_team and extra_team != team_id:
                labels.append(f"team:{extra_team}")
            payload = self.build_issue_payload(
                project_key,
                issue_type_name,
                summary,
                f"Seeded {issue_type} during {arc['name']} phase.",
                labels,
            )
            payload["_seed_meta"] = {
                "external_id": external_id,
                "created_at": created_at.isoformat() + "Z",
                "team_id": team_id,
                "issue_type": issue_type_name,
                "project_key": project_key,
                "arc": arc["name"],
                "month_idx": month_idx,
            }
            self.created_issues.append(payload)
            self.existing_ids[project_key].add(label)

        for idx in range(incident_count):
            self.generate_incident(project, month_idx, arc, idx)

    def generate_incident(self, project, month_idx, arc, incident_idx):
        incident_project = self.story.get("incident_project_key", project["key"])
        incident_project_key = incident_project
        team_id = project["team_id"]
        created_at = self.start_date + datetime.timedelta(days=month_idx * 30 + self.rng.randint(0, 28))
        severity = self.rng.choice(["sev1", "sev2", "sev3", "sev4"])
        service = self.rng.choice(self.story["services"])
        story_arc = arc["name"].lower().replace(" ", "-")

        ext_seed = f"incident-{incident_project_key}-{month_idx}-{team_id}-{incident_idx}"
        external_id = stable_hash(ext_seed)
        label = f"extid-{external_id}"

        issue_type_name = self.ensure_issue_type("Incident")
        manifest_type = "Incident"
        self.record_manifest(
            incident_project_key,
            team_id,
            manifest_type,
            created_at,
            service,
            severity,
        )
        self.simulate_dwell(arc)
        if severity in ["sev1", "sev2"]:
            self.followup_specs.append(
                {
                    "incident_external_id": external_id,
                    "team_id": team_id,
                    "service": service,
                    "month_idx": month_idx,
                }
            )
        if label in self.existing_ids[incident_project_key]:
            return
        summary = f"Incident {severity.upper()} on {service}"
        labels = self.make_labels(external_id, team_id, "unplanned", "reliability", service, story_arc, severity=severity)
        payload = self.build_issue_payload(
            incident_project_key,
            issue_type_name,
            summary,
            f"Seeded incident during {arc['name']} phase.",
            labels,
        )
        payload["_seed_meta"] = {
            "external_id": external_id,
            "created_at": created_at.isoformat() + "Z",
            "team_id": team_id,
            "issue_type": issue_type_name,
            "seed_type": manifest_type,
            "project_key": incident_project_key,
            "arc": arc["name"],
            "severity": severity,
            "month_idx": month_idx,
        }
        self.created_issues.append(payload)
        self.existing_ids[incident_project_key].add(label)

        return

    def flush_batches(self):
        batch = []
        for payload in self.created_issues:
            batch.append(payload)
            if len(batch) >= self.args.batch_size:
                self.process_batch(batch)
                batch = []
        if batch:
            self.process_batch(batch)

    def process_batch(self, batch):
        grouped = defaultdict(list)
        for item in batch:
            project_key = item["fields"]["project"]["key"]
            grouped[project_key].append(item)

        for project_key, items in grouped.items():
            payloads = [{"fields": item["fields"]} for item in items]
            created = self.create_issues(payloads)
            for issue_meta, created_issue in zip(items, created):
                issue_key = created_issue.get("key")
                if not issue_key:
                    continue
                meta = issue_meta.get("_seed_meta", {})
                labels = issue_meta.get("fields", {}).get("labels", [])
                ext_label = next((l for l in labels if l.startswith("extid-")), None)
                if ext_label:
                    self.issue_key_by_external_id[ext_label.replace("extid-", "")] = issue_key
                self.client.set_issue_property(issue_key, "seed_meta", meta)
                self.maybe_comment(issue_key, meta.get("arc", ""))

                issue_type = issue_meta.get("fields", {}).get("issuetype", {}).get("name", "")
                if issue_type.lower() == "incident":
                    target_status = "Resolved"
                else:
                    target_status = "Done"
                self.apply_transitions(issue_key, target_status)

                month_idx = meta.get("month_idx")
                if isinstance(month_idx, int) and issue_type.lower() in ["story", "task", "bug"]:
                    self.issues_by_project_month[project_key][month_idx].append(issue_key)

                link_external = issue_meta.get("_link_external_id")
                link_type = issue_meta.get("_link_type")
                if link_external and link_type:
                    target_key = self.issue_key_by_external_id.get(link_external)
                    if target_key:
                        self.client.create_issue_link(link_type, issue_key, target_key)

    def generate_followups(self):
        if not self.followup_specs or not self.args.enable_incidents:
            return
        for spec in self.followup_specs:
            project_key = self.team_primary_project.get(spec["team_id"])
            if not project_key:
                continue
            for idx in range(self.rng.randint(3, 8)):
                month_idx = self.rng.choice([16, 17, 18, 19])
                created_at = self.start_date + datetime.timedelta(
                    days=month_idx * 30 + self.rng.randint(0, 28)
                )
                work_type = self.rng.choice(["refactor", "maintenance"])
                investment = self.rng.choice(["reliability", "ops", "platform"])
                story_arc = "recovery"
                ext_seed = f"followup-{spec['incident_external_id']}-{idx}"
                external_id = stable_hash(ext_seed)
                label = f"extid-{external_id}"
                summary = f"Postmortem follow-up on {spec['service']}"
                issue_type_name = self.ensure_issue_type("Task")
                self.record_manifest(
                    project_key,
                    spec["team_id"],
                    "Task",
                    created_at,
                    spec["service"],
                )
                if label in self.existing_ids[project_key]:
                    continue
                labels = self.make_labels(
                    external_id,
                    spec["team_id"],
                    work_type,
                    investment,
                    spec["service"],
                    story_arc,
                )
                payload = self.build_issue_payload(
                    project_key,
                    issue_type_name,
                    summary,
                    "Seeded postmortem follow-up task.",
                    labels,
                )
                payload["_seed_meta"] = {
                    "external_id": external_id,
                    "created_at": created_at.isoformat() + "Z",
                    "team_id": spec["team_id"],
                    "issue_type": issue_type_name,
                    "project_key": project_key,
                    "arc": "Recovery",
                    "month_idx": month_idx,
                }
                payload["_link_external_id"] = spec["incident_external_id"]
                payload["_link_type"] = "Relates"
                self.created_issues.append(payload)
                self.existing_ids[project_key].add(label)

    def build_sprint_map(self):
        sprint_map = []
        sprint_count = self.month_count * 2
        for idx in range(sprint_count):
            start_dt = self.start_date + datetime.timedelta(days=idx * 14)
            end_dt = start_dt + datetime.timedelta(days=13)
            sprint_map.append((start_dt, end_dt))
        return sprint_map

    def build_sprints(self, project_key, sprint_map):
        if not self.args.enable_sprints:
            return {}
        cached = self.sprints_by_project.get(project_key)
        if cached is not None:
            return cached
        boards = self.client.get_boards(project_key) or {}
        board_id = None
        for board in boards.get("values", []) or []:
            if board.get("name") == f"{project_key} Scrum":
                board_id = board.get("id")
                break
        if board_id is None:
            created = self.client.create_board(f"{project_key} Scrum", project_key) or {}
            board_id = created.get("id")
        if not board_id:
            self.log(f"Skipping sprints for {project_key}, no board available")
            self.sprints_by_project[project_key] = {}
            return {}

        sprints = {}
        for idx, (start_dt, end_dt) in enumerate(sprint_map):
            name = f"Sprint {idx + 1}"
            sprint = self.client.create_sprint(
                name,
                board_id,
                start_dt.isoformat() + "Z",
                end_dt.isoformat() + "Z",
            )
            if sprint and sprint.get("id"):
                sprints[name] = sprint.get("id")
        self.sprints_by_project[project_key] = sprints
        return sprints

    def precreate_sprints(self):
        if not self.args.enable_sprints:
            return
        sprint_map = self.build_sprint_map()
        for project in self.story["projects"]:
            self.build_sprints(project["key"], sprint_map)

    def assign_sprints(self, project_key, sprint_map, issue_keys_by_month):
        if not self.args.enable_sprints:
            return
        sprints = self.build_sprints(project_key, sprint_map)
        if not sprints:
            return
        sprint_names = list(sprints.keys())
        for idx, month_issues in issue_keys_by_month.items():
            if not month_issues:
                continue
            sprint_index = min(idx * 2, len(sprint_names) - 1)
            primary_id = sprints[sprint_names[sprint_index]]
            spillover_index = min(sprint_index + 1, len(sprint_names) - 1)
            spillover_id = sprints[sprint_names[spillover_index]]

            self.rng.shuffle(month_issues)
            split = max(1, int(len(month_issues) * 0.8))
            primary_issues = month_issues[:split]
            spillover_issues = month_issues[split:]

            if primary_issues:
                self.client.add_issues_to_sprint(primary_id, primary_issues)
            if spillover_issues:
                self.client.add_issues_to_sprint(spillover_id, spillover_issues)

    def assign_all_sprints(self):
        if not self.args.enable_sprints:
            return
        sprint_map = self.build_sprint_map()
        for project in self.story["projects"]:
            project_key = project["key"]
            month_map = self.issues_by_project_month.get(project_key, {})
            if month_map:
                self.assign_sprints(project_key, sprint_map, month_map)

    def run(self):
        self.resolve_assignees()

        project_keys = [p["key"] for p in self.story["projects"]]
        incident_project = self.story.get("incident_project_key")
        for key in project_keys:
            self.prefetch_existing(key)
        if incident_project and incident_project not in project_keys:
            self.prefetch_existing(incident_project)

        self.precreate_sprints()

        for project in self.story["projects"]:
            self.ensure_epics_and_initiatives(project["key"], project["team_id"])

        self.link_epics_cross_project(project_keys)

        arcs = self.story["arcs"]
        for month_idx in range(self.month_count):
            arc = next(
                (a for a in arcs if a["start_month"] <= month_idx <= a["end_month"]),
                None,
            )
            if not arc:
                continue
            self.log(f"Month {month_idx}: {arc['name']}")
            for project in self.story["projects"]:
                self.generate_month_issues(project, month_idx, arc)

        self.generate_followups()
        self.flush_batches()
        self.assign_all_sprints()

        manifest_path = self.args.manifest
        with open(manifest_path, "w") as handle:
            json.dump(self._serialize_manifest(), handle, indent=2)
        self.log(f"Manifest written to {manifest_path}")

    def _serialize_manifest(self):
        def convert(obj):
            if isinstance(obj, defaultdict):
                return {k: convert(v) for k, v in obj.items()}
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            return obj

        return convert(self.manifest)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--user", required=True)
    # Token is read from JIRA_TOKEN environment variable for security
    parser.add_argument("--story", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--assignees", default="")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--monthly-issue-count", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--disable-sprints", action="store_true")
    parser.add_argument("--disable-transitions", action="store_true")
    parser.add_argument("--enable-comments", action="store_true")
    parser.add_argument("--disable-incidents", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    # Read token from environment variable to avoid exposing it in process listings
    args.token = os.environ.get("JIRA_TOKEN")
    if not args.token:
        raise ValueError("JIRA_TOKEN environment variable is required")

    args.enable_sprints = not args.disable_sprints
    args.enable_transitions = not args.disable_transitions
    args.enable_comments = args.enable_comments
    args.enable_incidents = not args.disable_incidents

    seeder = JiraSeeder(args)
    seeder.run()
