import json, os
import random

from locust import HttpUser, between, task, SequentialTaskSet
from docker import run_command
from conf import HOSTNAME, REPO_NAME
from dotenv import load_dotenv


class JFTest(SequentialTaskSet):
    load_dotenv()

    USERNAME = os.getenv("USERNAME")
    PASSWORD = os.getenv("PASSWORD")
    HEADERS = {
        "Content-Type": "application/json",
        "Authorization": os.getenv("TOKEN")
    }
    platform_url = HOSTNAME

    image = "alpine:3.9"
    tag = "new-image"
    version = "latest"

    @task
    def create_repo(self):
        body = {
            "key": REPO_NAME,
            "projectKey": "",
            "packageType": "docker",
            "rclass": "local",
            "xrayIndex": True
        }
        with self.client.put(url=f"/artifactory/api/repositories/{REPO_NAME}",
                             catch_response=True,
                             headers=self.HEADERS,
                             data=json.dumps(body),
                             name="create_repo") as response:
            if response.status_code == 400 and "repository key already exists" in str(response.content):
                print("Repository already created")
                response.success()
            elif response.status_code >= 400:
                response.failure("Return status code: " + str(response.status_code)
                                 + " Return response : " + str(response.content))

            else:
                response.success()

    @task
    def verify_repo(self):
        with self.client.get(url="/artifactory/api/repositories",
                             catch_response=True,
                             headers=self.HEADERS,
                             name="verify_repo") as response:
            if response.status_code >= 400:
                response.failure("Return status code: " + str(response.status_code)
                                 + " Return response : " + str(response.content))
            else:
                response.success()

    @task
    def docker_plugin(self):
        load_dotenv()

        USERNAME = os.getenv("USERNAME")
        PASSWORD = os.getenv("PASSWORD")

        if not run_command(["docker", "pull", f"{self.image}"], "docker pull", self.user.environment):
            return

        if not run_command(["docker", "login", self.platform_url, "-u", USERNAME, "-p", PASSWORD],
                           "docker login", self.user.environment):
            return

        if not run_command(["docker", "tag", self.image, f"{self.platform_url}/{REPO_NAME}/{self.tag}/{self.version}"],
                           "docker tag",
                           self.user.environment):
            return

        if not run_command(["docker", "push", f"{self.platform_url}/{REPO_NAME}/{self.tag}/{self.version}"],
                           "docker push",
                           self.user.environment):
            return

    def create_policy(self, policy_name):
        body = {
            "name": policy_name,
            "description": "This is a specific CVEs security policy",
            "type": "security",
            "rules": [
                {
                    "name": "some_rule",
                    "criteria": {
                        "malicious_package": False,
                        "fix_version_dependant": False,
                        "min_severity": "high"
                    },
                    "actions": {
                        "mails": [],
                        "webhooks": [],
                        "fail_build": False,
                        "block_release_bundle_distribution": False,
                        "block_release_bundle_promotion": False,
                        "notify_deployer": False,
                        "notify_watch_recipients": False,
                        "create_ticket_enabled": False,
                        "block_download": {
                            "active": False,
                            "unscanned": False
                        }
                    },
                    "priority": 1
                }
            ]
        }

        with self.client.post(url="/xray/api/v2/policies",
                              catch_response=True,
                              headers=self.HEADERS,
                              data=json.dumps(body),
                              name="create_policy") as response:
            if response.status_code >= 400:
                response.failure("Return status code: " + str(response.status_code)
                                 + " Return response : " + str(response.content))
            else:
                response.success()

    def create_watch(self, policy_name, watch_name):
        body = {
            "general_data": {
                "name": watch_name,
                "description": "This is an example watch #1",
                "active": True
            },
            "project_resources": {
                "resources": [
                    {
                        "type": "repository",
                        "bin_mgr_id": "default",
                        "name": REPO_NAME,
                        "filters": [
                            {
                                "type": "regex",
                                "value": ".*"
                            }
                        ]
                    }
                ]
            },
            "assigned_policies": [
                {
                    "name": policy_name,
                    "type": "security"
                }
            ]
        }

        with self.client.post(url="/xray/api/v2/watches",
                              catch_response=True,
                              headers=self.HEADERS,
                              data=json.dumps(body),
                              name="create_watch") as response:
            if response.status_code >= 400:
                response.failure("Return status code: " + str(response.status_code)
                                 + " Return response : " + str(response.content))
            else:
                response.success()

    def apply_watch(self, watch_name):
        body = {
            "watch_names": [
                watch_name
            ],
            "date_range": {
                "start_date": "2025-05-10T00:00:00+05:00",  #UTC time in RFC3339 formatYYYY-MM-DDTHH:MM:SSZ
                "end_date": "2025-05-15T00:00:00+05:30"  #UTC time in RFC3339 formatYYYY-MM-DDTHH:MM:SSZ
            }
        }

        with self.client.post(url="/xray/api/v1/applyWatch",
                              catch_response=True,
                              headers=self.HEADERS,
                              data=json.dumps(body),
                              name="apply_watch") as response:
            if response.status_code >= 400:
                response.failure("Return status code: " + str(response.status_code)
                                 + " Return response : " + str(response.content))
            else:
                response.success()

    def check_scan_status(self):
        body = {
            "repo": REPO_NAME,
            "path": f"/{self.tag}/{self.version}/manifest.json"
        }

        with self.client.post(url="/xray/api/v1/artifact/status",
                              catch_response=True,
                              headers=self.HEADERS,
                              data=json.dumps(body),
                              name="check_scan_status") as response:
            if response.status_code >= 400:
                response.failure("Return status code: " + str(response.status_code)
                                 + " Return response : " + str(response.content))
            else:
                response.success()

    def verify_violations(self, watch_name):
        body = {
            "filters": {
                "watch_name": watch_name,
                "violation_type": "Security",
                "min_severity": "High",
                "resources": {
                    "artifacts": [
                        {
                            "repo": REPO_NAME,
                            "path": f"/{self.tag}/{self.version}/manifest.json"
                        }
                    ]
                }
            },
            "pagination": {
                "order_by": "created",
                "direction": "asc",
                "limit": 100,
                "offset": 1
            }
        }

        with self.client.post(url="/xray/api/v1/violations",
                              catch_response=True,
                              headers=self.HEADERS,
                              data=json.dumps(body),
                              name="verify_violations") as response:
            if response.status_code >= 400:
                response.failure("Return status code: " + str(response.status_code)
                                 + " Return response : " + str(response.content))
            else:
                response.success()

    @task
    def create_and_apply_policy_and_watch(self):
        policy_name = "sec_policy_" + str(random.randint(10000, 99999))
        watch_name = "watch" + str(random.randint(10000, 99999))

        self.create_policy(policy_name)
        self.create_watch(policy_name, watch_name)
        self.apply_watch(watch_name)
        self.check_scan_status()
        self.verify_violations(watch_name)


class VUser(HttpUser):
    host = f"https://{HOSTNAME}"
    wait_time = between(1, 3)
    tasks = [JFTest]
