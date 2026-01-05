import argparse
import yaml
import json
import random
import hashlib
import datetime
import sys
import time

# Fake/Mock mode if URL is not real
MOCK_MODE = False


class JiraSeeder:
    def __init__(
        self,
        url,
        user,
        token,
        story_map_path,
        seed_str,
        output_path,
        assignees=None,
        dry_run=False,
    ):
        self.url = url.rstrip("/")
        self.user = user
        self.token = token
        self.output_path = output_path
        self.assignees = assignees or []
        self.dry_run = dry_run

        with open(story_map_path, "r") as f:
            self.story_map = yaml.safe_load(f)

        # Deterministic seeding
        seed_hash = int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest(), 16) % (
            10**8
        )
        random.seed(seed_hash)

        self.stats = {"projects": {}, "total_issues": 0, "incidents": 0}

        self.account_ids = []

    def log(self, msg):
        print(f"[Seeder] {msg}")

    def api_request(self, method, endpoint, data=None):
        if MOCK_MODE:
            # Return dummy data structure matching expectation
            if "user/search" in endpoint:
                return [{"accountId": f"mock-{random.randint(100, 999)}"}]
            return {"key": f"MOCK-{random.randint(1000, 9999)}", "id": "10000"}

        import requests
        from requests.auth import HTTPBasicAuth

        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        url = f"{self.url}{endpoint}"

        # Simple retry logic
        for attempt in range(3):
            try:
                response = requests.request(
                    method,
                    url,
                    data=json.dumps(data) if data else None,
                    headers=headers,
                    auth=HTTPBasicAuth(self.user, self.token),
                    timeout=30,
                )

                if response.status_code in [200, 201, 204]:
                    return response.json() if response.content else {}
                else:
                    self.log(
                        f"Error {response.status_code} on {method} {endpoint} (attempt {attempt + 1}/3): {response.text}"
                    )
            except requests.RequestException as e:
                self.log(f"Exception (attempt {attempt + 1}/3): {e}")

            time.sleep(1)

        return None

    def resolve_assignees(self):
        if not self.assignees:
            return

        self.log(f"Resolving {len(self.assignees)} assignees...")
        for email in self.assignees:
            email = email.strip()
            if not email:
                continue

            # API endpoint to find user by query
            data = self.api_request("GET", f"/rest/api/3/user/search?query={email}")
            if data and isinstance(data, list) and len(data) > 0:
                acc_id = data[0].get("accountId")
                if acc_id:
                    self.account_ids.append(acc_id)
            else:
                self.log(f"Could not find user for email: {email}")

        self.log(f"Resolved {len(self.account_ids)} valid account IDs for assignment.")

    def create_project(self, key, name, team):
        # In real usage, check if exists first. For seeding, we assume creation or ignore 400s.
        # This script focuses on content generation.
        self.stats["projects"][key] = {"total": 0, "by_type": {}}

    def generate_issue(self, project_key, issue_type, summary, created_dt, fields=None):
        f = fields or {}

        # Random assignment if we have users
        if self.account_ids and random.random() > 0.1:  # 90% chance to assign
            f["assignee"] = {"id": random.choice(self.account_ids)}

        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": issue_type},
                # Note: "created" field often requires admin import permission
                # "created": created_dt.isoformat(),
                **f,
            }
        }

        if not self.dry_run:
            self.api_request("POST", "/rest/api/3/issue", payload)
        self.stats["total_issues"] += 1
        self.stats["projects"][project_key]["total"] += 1

        type_cnt = self.stats["projects"][project_key]["by_type"].get(issue_type, 0)
        self.stats["projects"][project_key]["by_type"][issue_type] = type_cnt + 1

    def run(self):
        self.log("Starting generation...")

        # Resolve users first
        self.resolve_assignees()

        start_date = datetime.datetime.now() - datetime.timedelta(
            days=730
        )  # 2 years ago

        for project in self.story_map["projects"]:
            self.create_project(project["key"], project["name"], project["team"])

        # Iterate months
        for month in range(24):
            current_date = start_date + datetime.timedelta(days=month * 30)

            # Find Arc
            arc = next(
                (
                    a
                    for a in self.story_map["arcs"]
                    if a["start_month"] <= month <= a["end_month"]
                ),
                None,
            )
            if not arc:
                continue

            self.log(f"Month {month}: Arc={arc['name']}")

            for project in self.story_map["projects"]:
                # Determine volume (approx 50 per month +/- variance)
                vol = int(random.gauss(50, 10))

                for _ in range(vol):
                    # Pick type based on weights
                    weights = arc["weights"]
                    w_keys = list(weights.keys())
                    w_vals = list(weights.values())

                    category = random.choices(w_keys, weights=w_vals, k=1)[0]

                    # Map category to Issue Type
                    if category == "bug":
                        issue_type = "Bug"
                    elif category == "unplanned":
                        issue_type = "Task"  # Proxy
                    else:
                        issue_type = "Story"

                    # Inject Incidents based on probability
                    if random.random() < arc.get("incident_probability", 0):
                        issue_type = "Incident"  # JSM type
                        category = "reliability"

                    summary = f"Generated {category} work for {project['key']} - {random.randint(1000, 9999)}"

                    self.generate_issue(
                        project["key"],
                        issue_type,
                        summary,
                        current_date,
                        fields={
                            "labels": [
                                category,
                                f"arc:{arc['name'].replace(' ', '-').lower()}",
                            ],
                            "description": f"Auto-generated for arc {arc['name']}",
                        },
                    )

        # Write Manifest
        with open(self.output_path, "w") as f:
            json.dump(self.stats, f, indent=2)

        self.log(f"Done. Manifest written to {self.output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--story", required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--assignees", required=False, help="Comma separated list of emails"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate stats/manifest without creating Jira issues",
    )

    args = parser.parse_args()

    # Check if URL looks like a placeholder or empty
    if "your-domain" in args.url or not args.url.startswith("http"):
        MOCK_MODE = True
        print("Running in MOCK MODE (no API calls)")

    assignee_list = args.assignees.split(",") if args.assignees else []

    seeder = JiraSeeder(
        args.url,
        args.user,
        args.token,
        args.story,
        args.seed,
        args.output,
        assignee_list,
        dry_run=args.dry_run,
    )
    seeder.run()
