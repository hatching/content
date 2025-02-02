Automate response actions like quarantining effected resources or snapshots to stop the spread of ransomware and avoid reinfection or contamination spread.

## Dependencies

This playbook uses the following sub-playbooks, integrations, and scripts.

### Sub-playbooks

This playbook does not use any sub-playbooks.

### Integrations

* Druva Ransomware Response

### Scripts

* IsIntegrationAvailable

### Commands

* druva-find-sharePointSites
* druva-quarantine-resource
* druva-find-userDevice
* druva-find-sharedDrives
* druva-find-user
* druva-find-device

## Playbook Inputs

---

| **Name** | **Description** | **Default Value** | **Required** |
| --- | --- | --- | --- |
| UserName | UserName is used to search userID  of user | ${incident.users} | Optional |
| ResourceName | ResourceName is used to search resource of type FS,NAS and VMware | ${incident.devicename} | Optional |
| SiteURL | SiteURL is used to search sharedrive and sharepoint resources   | ${incident.urls} | Optional |
| DateOfOccurrence | Date is used to quarantine device  | incident.occurred | Optional |

## Playbook Outputs

---
There are no outputs for this playbook.