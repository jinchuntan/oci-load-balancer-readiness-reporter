# OCI Load Balancer Readiness Reporter

Standalone OCI automation tool that inventories load balancers, listeners, backend sets, and backend health, correlates backend targets to Compute instances/VNICs, and uploads JSON + Markdown reports to OCI Object Storage.

## Purpose

This tool gives operations teams a clear readiness view of OCI Load Balancer backend health and dependency mapping.

Services used:

- OCI Load Balancer
- OCI Compute
- OCI Virtual Network
- OCI Identity
- OCI Object Storage

No destructive actions are performed.

## Quick Start (Windows PowerShell)

```powershell
cd <path-to-repo>\oci-load-balancer-readiness-reporter
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Local-only run (skip Object Storage upload):

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 -SkipUpload
```

## Manual Setup

```powershell
cd <path-to-repo>\oci-load-balancer-readiness-reporter
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe run_audit.py
```

## Configuration Before the First Run

Copy `.env.example` to `.env` once, then edit `.env` before running. Preserve an
existing `.env` when updating. The template documents every supported setting
and uses the same defaults as the application's configuration loader.

- Leave `OCI_CONFIG_FILE` unset to use `~/.oci/config`; use an absolute path if overriding it.
- A blank `OCI_ROOT_COMPARTMENT_OCID` selects the tenancy. Set a compartment OCID
  and adjust `OCI_INCLUDE_SUBCOMPARTMENTS` to limit the scan.
- To upload only to a chosen bucket, set `OCI_OBJECT_STORAGE_BUCKET` and
  `OCI_AUTO_DISCOVER_BUCKET=false`. Otherwise, the tool may try other discovered
  buckets if the first upload fails. It does not create buckets.
- `OCI_OUTPUT_DIR` defaults to `output/`. `OCI_FAIL_ON_UPLOAD_ERROR=true` makes
  upload failures return a nonzero exit code; local reports remain available.
- For a first run that only writes reports locally, use
  `.\.venv\Scripts\python.exe run_audit.py --skip-upload` after installing dependencies.
  This still calls OCI to collect data and requires a configured SDK profile.

`.env`, signing keys, virtual environments and generated report folders are
ignored by Git. The example template remains tracked.

## Environment Variables

See `.env.example`.

Common values:

- `OCI_CONFIG_PROFILE`
- `OCI_REGION`
- `OCI_ROOT_COMPARTMENT_OCID`
- `OCI_INCLUDE_SUBCOMPARTMENTS`
- `OCI_OBJECT_STORAGE_NAMESPACE` (optional)
- `OCI_OBJECT_STORAGE_BUCKET` (optional; auto-discovery if omitted)
- `OCI_OBJECT_STORAGE_PREFIX`

## Output Artifacts

Local folder (default `output/`):

- `lb_readiness_report_<timestamp>.json`
- `lb_readiness_report_<timestamp>.md`

Uploaded URI pattern:

- `oci://<bucket>@<namespace>/<prefix>/lb_readiness_report_<timestamp>.json`
- `oci://<bucket>@<namespace>/<prefix>/lb_readiness_report_<timestamp>.md`

## Evidence Steps

### Terminal evidence

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Capture:

- compartment discovery count
- per-compartment LB collection logs
- generated local report paths
- uploaded `oci://...` object URIs

### Object Storage evidence

Use namespace and bucket from the printed URI:

```powershell
oci os object list `
  --namespace-name <namespace> `
  --bucket-name <bucket> `
  --prefix lb-readiness-report
```

Optional object metadata check:

```powershell
oci os object head `
  --namespace-name <namespace> `
  --bucket-name <bucket> `
  --name "lb-readiness-report/<artifact-file-name>"
```

### Output
<img width="805" height="120" alt="image" src="https://github.com/user-attachments/assets/771044a4-2d74-4ab0-96ae-46b19e8aafd6" />
<img width="1918" height="991" alt="image" src="https://github.com/user-attachments/assets/2491575c-2b88-446e-8cf9-4c3a25e1b223" />

## Safety

- Read-only API calls to Load Balancer/Compute/Networking/Identity
- Only write operation is Object Storage upload
- No create/update/delete resource actions

