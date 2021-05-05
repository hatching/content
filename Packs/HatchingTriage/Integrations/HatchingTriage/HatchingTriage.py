import demistomock as demisto
from CommonServerPython import *
from CommonServerUserPython import *
import json


class Client(BaseClient):
    def __init__(self, base_url, *args, **kwarg):
        super().__init__(base_url, *args, **kwarg)


def test_module(client: Client) -> str:

    r = client._http_request(
        "GET", "users", resp_type="response", ok_codes=(200, 401, 404)
    )

    if r.status_code == 404:
        return "Page not found, possibly wrong base_url"
    if r.status_code == 401:
        return "Bad API Key"

    return "ok"

def map_scores_to_dbot(score):
    if 0 <= score <= 4:
        return 1
    elif 5 <= score <= 7:
        return 2
    elif 8 <= score <= 10:
        return 3

def query_samples(client, **args) -> CommandResults:
    params = {"subset": args.get("subset")}

    r = client._http_request("GET", "samples", params=params)

    results = CommandResults(
        outputs_prefix="Triage.samples", outputs_key_field="id", outputs=r["data"]
    )
    return results


def submit_sample(client: Client, **args) -> CommandResults:
    data = {"kind": args.get("kind"), "interactive": False}

    if args.get("profiles", []):
        profiles_data = []
        for i in args.get("profiles", "").split(","):
            profiles_data.append({"profile": i, "pick": "sample"})
        data["profiles"] = profiles_data

    if data["kind"] == "url":
        data.update({"url": args.get("data")})
        r = client._http_request("POST", "samples", json_data=data)
    elif data["kind"] == "file":
        file_path = demisto.getFilePath(demisto.args().get("data")).get("path")
        with open(file_path, "rb") as f:
            files = {"file": f}
            r = client._http_request("POST", "samples", json_data=data, files=files)
    else:
        return_error(
            f'Type of sample needs to be selected, either "file" or "url", the selected type was: {data["kind"]}'
        )

    results = CommandResults(
        outputs_prefix="Triage.submissions", outputs_key_field="id", outputs=r
    )
    return results


def get_sample(client: Client, **args) -> CommandResults:
    sample_id = args.get("sample_id")
    r = client._http_request("GET", f"samples/{sample_id}")

    results = CommandResults(
        outputs_prefix="Triage.samples", outputs_key_field="id", outputs=r
    )
    return results


def get_sample_summary(client: Client, **args) -> CommandResults:
    sample_id = args.get("sample_id")
    r = client._http_request("GET", f"samples/{sample_id}/summary")

    results = CommandResults(
        outputs_prefix="Triage.sample-summaries", outputs_key_field="sample", outputs=r
    )
    return results


def delete_sample(client: Client, **args) -> str:
    sample_id = args.get("sample_id")
    client._http_request("DELETE", f"samples/{sample_id}")

    return f"Sample {sample_id} successfully deleted"


def set_sample_profile(client: Client, **args) -> str:
    """
    Used to move a submitted sample from static analysis to behavioural by giving it a profile to run under
    """
    sample_id = args.get("sample_id")

    data = {
        "auto": argToBoolean(args.get("auto", True)),
        "pick": argToList(args.get("pick", [])),
    }
    if args.get("profiles"):
        data.update({"profiles": [{"profile": args.get("profiles", "")}]})
    data = json.dumps(data)

    client._http_request("POST", f"samples/{sample_id}/profile", data=data)

    return f"Profile successfully set for sample {sample_id}"


def get_static_report(client: Client, **args) -> CommandResults:
    """
    Get's the static analysis report from a given sample
    """
    sample_id = args.get("sample_id")

    r = client._http_request("GET", f"samples/{sample_id}/reports/static")

    score = 0
    if 'analysis' in r:
        if 'score' in r['analysis']:
            score = map_scores_to_dbot(r['analysis']['score'])

    indicator = None
    if 'sample' in r:
        target = r['sample']['target']
        if r['sample']['kind'] == "file":
            # Static can include data on multiple files e.g. in case of .zip upload.
            # sample.target identifies the actual analysis subject so only get
            # the results for that file
            for file in r['files']:
                if file['filename'] == target:
                    dbot_score = Common.DBotScore(
                        indicator=file['sha256'],
                        indicator_type=DBotScoreType.FILE,
                        integration_name="Hatching Triage",
                        score = score
                    )
                    indicator = Common.File(
                        name=r['sample']['target'],
                        sha256=file['sha256'],
                        md5=file['md5'],
                        sha1=file['sha1'],
                        dbot_score=dbot_score
                    )
        else:
            # Static often doesn't include scores for URL analyses so only
            # include results which do, rather than potentially reporting
            # false-negatives to DBot
            if 'score' in r['analysis']:
                dbot_score = Common.DBotScore(
                    indicator=target,
                    indicator_type=DBotScoreType.URL,
                    integration_name="Hatching Triage",
                    score=score
                )
                indicator = Common.URL(
                    url=target,
                    dbot_score=dbot_score
                )
    if indicator is not None:
        results = CommandResults(
            outputs_prefix="Triage.sample.reports.static",
            outputs_key_field="sample.sample",
            outputs=r,
            indicator=indicator
        )
    else:
        results = CommandResults(
            outputs_prefix="Triage.sample.reports.static",
            outputs_key_field="sample.sample",
            outputs=r
        )

    return results


def get_report_triage(client: Client, **args) -> CommandResults:
    """
    Outputs a score, should map to a DBot score
    """
    sample_id = args.get("sample_id")
    task_id = args.get("task_id")

    r = client._http_request("GET", f"samples/{sample_id}/{task_id}/report_triage.json")

    score = 0
    if 'sample' in r:
        if 'score' in r['sample']:
            score = map_scores_to_dbot(r['sample']['score'])

    target = r['sample']['target']
    indicator = None
    if not "sha256" in r['sample']:
        dbot_score = Common.DBotScore(
            indicator=target,
            indicator_type=DBotScoreType.URL,
            integration_name="Hatching Triage",
            score=score
        )
        indicator = Common.URL(
            url=target,
            dbot_score=dbot_score
        )
    else:
        dbot_score = Common.DBotScore(
            indicator=r['sample']['sha256'],
            indicator_type=DBotScoreType.FILE,
            integration_name="Hatching Triage",
            score=score
        )
        indicator = Common.File(
            name=target,
            sha256=r['sample']['sha256'],
            md5=r['sample']['md5'],
            sha1=r['sample']['sha1'],
            dbot_score=dbot_score
        )

    if indicator is not None:
        results = CommandResults(
            outputs_prefix="Triage.sample.reports.triage",
            outputs_key_field="sample.id",
            outputs=r,
            indicator=indicator
        )
    else:
        results = CommandResults(
            outputs_prefix="Triage.sample.reports.triage",
            outputs_key_field="sample.id",
            outputs=r
        )
    #dbot_score_data = []
    #dbot_score_data.append({
    #    "Indicator": target,
    #    "Score": score,
    #    "Type": "file",
    #    "Vendor": "Hatching Triage"
    #})
    #appendContext("DBotScore", dbot_score_data)
    return results


def get_kernel_monitor(client: Client, **args) -> dict:
    sample_id = args.get("sample_id")
    task_id = args.get("task_id")

    r = client._http_request(
        "GET", f"samples/{sample_id}/{task_id}/logs/onemon.json", resp_type="text"
    )

    return_results("Kernel monitor results:")
    results = fileResult(f"{sample_id}-{task_id}-kernel-monitor.json", r)

    return results


def get_pcap(client: Client, **args) -> dict:
    sample_id = args.get("sample_id")
    task_id = args.get("task_id")

    r = client._http_request(
        "GET", f"samples/{sample_id}/{task_id}/dump.pcap", resp_type="response"
    )

    filename = f"{sample_id}.pcap"
    file_content = r.content

    return_results("PCAP results:")
    return fileResult(filename, file_content)


def get_dumped_files(client: Client, **args) -> dict:
    sample_id = args.get("sample_id")
    task_id = args.get("task_id")
    file_name = args.get("file_name")

    r = client._http_request(
        "GET", f"samples/{sample_id}/{task_id}/{file_name}", resp_type="content"
    )

    results = fileResult(f"{file_name}", r)

    return results


def get_users(client: Client, **args) -> CommandResults:
    if args.get("userID"):
        url_suffix = f'users/{args.get("userID")}'
    else:
        url_suffix = "users"

    r = client._http_request("GET", url_suffix)

    # Depending on the api endpoint used, the results are either in the 'data' key or not
    if r.get("data"):
        r = r["data"]

    results = CommandResults(
        outputs_prefix="Triage.users", outputs_key_field="id", outputs=r
    )

    return results


def create_user(client: Client, **args) -> CommandResults:
    data = {
        "username": args.get("username"),
        "first_name": args.get("firstName"),
        "last_name": args.get("lastName"),
        "password": args.get("password"),
        "permissions": argToList(args.get("permissions")),
    }

    data = json.dumps(data)

    r = client._http_request("POST", "users", data=data)

    results = CommandResults(
        outputs_prefix="Triage.users", outputs_key_field="id", outputs=r
    )

    return results


def delete_user(client: Client, **args) -> str:
    userID = args.get("userID")

    client._http_request("DELETE", f"users/{userID}")

    results = "User successfully deleted"

    return results


def create_apikey(client: Client, **args) -> CommandResults:
    userID = args.get("userID")
    name = args.get("name")

    data = json.dumps({"name": name})

    r = client._http_request("POST", f"users/{userID}/apikeys", data=data)

    results = CommandResults(
        outputs_prefix="Triage.apikey", outputs_key_field="key", outputs=r
    )

    return results


def get_apikey(client: Client, **args) -> CommandResults:
    userID = args.get("userID")
    r = client._http_request("GET", f"users/{userID}/apikeys")

    results = CommandResults(
        outputs_prefix="Triage.apikey", outputs_key_field="key", outputs=r.get("data")
    )

    return results


def delete_apikey(client: Client, **args) -> str:
    userID = args.get("userID")
    apiKeyName = args.get("name")

    client._http_request("DELETE", f"users/{userID}/apikeys/{apiKeyName}")

    results = f"API key {apiKeyName} was successfully deleted"

    return results


def get_profile(client: Client, **args) -> CommandResults:
    profileID = args.get("profileID")

    if profileID:
        url_suffix = f"profiles/{profileID}"
    else:
        url_suffix = "profiles"

    r = client._http_request("GET", url_suffix)

    if not profileID and r.get("data"):
        r = r["data"]

    results = CommandResults(
        outputs_prefix="Triage.profiles", outputs_key_field="id", outputs=r
    )

    return results


def create_profile(client: Client, **args) -> CommandResults:
    data = json.dumps(
        {
            "name": args.get("name"),
            "tags": argToList(args.get("tags")),
            "timeout": int(args.get("timeout", 120)),
            "network": args.get("network"),
            "browser": args.get("browser"),
        }
    )

    r = client._http_request("POST", "profiles", data=data)

    results = CommandResults(
        outputs_prefix="Triage.profiles", outputs_key_field="id", outputs=r
    )

    return results


def update_profile(client: Client, **args) -> str:
    profileID = args.get("profileID")

    data = {}

    for arg in args:
        if arg == "timeout":
            data[arg] = int(args.get(arg, 60))
        if arg == "tags":
            data[arg] = argToList(args.get(arg))
        if arg == "timeout":
            data[arg] = args.get(arg, None)

    client._http_request("PUT", f"profiles/{profileID}", data=json.dumps(data))

    results = "Profile updated successfully"

    return results


def delete_profile(client: Client, **args) -> str:
    profileID = args.get("profileID")

    client._http_request("DELETE", f"profiles/{profileID}")

    results = f"Profile {profileID} successfully deleted"

    return results


def main():
    params = demisto.params()
    args = demisto.args()
    client = Client(
        params.get("base_url"),
        verify=params.get("Verify SSL"),
        headers={"Authorization": f'Bearer {params.get("API Key")}'},
    )

    commands = {
        "test-module": test_module,
        "triage-query-samples": query_samples,
        "triage-submit-sample": submit_sample,
        "triage-get-sample": get_sample,
        "triage-get-sample-summary": get_sample_summary,
        "triage-delete-sample": delete_sample,
        "triage-set-sample-profile": set_sample_profile,
        "triage-get-static-report": get_static_report,
        "triage-get-report-triage": get_report_triage,
        "triage-get-kernel-monitor": get_kernel_monitor,
        "triage-get-pcap": get_pcap,
        "triage-get-dumped-file": get_dumped_files,
        "triage-get-users": get_users,
        "triage-create-user": create_user,
        "triage-delete-user": delete_user,
        "triage-create-api-key": create_apikey,
        "triage-get-api-key": get_apikey,
        "triage-delete-api-key": delete_apikey,
        "triage-get-profiles": get_profile,
        "triage-create-profile": create_profile,
        "triage-update-profile": update_profile,
        "triage-delete-profile": delete_profile,
    }

    command = demisto.command()
    if command in commands:
        return_results(commands[command](client, **args))  # type: ignore
    else:
        return_error(f"Command {command} is not available in this integration")


if __name__ in ["__main__", "__builtin__", "builtins"]:
    main()
